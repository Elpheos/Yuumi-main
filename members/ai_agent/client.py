# members/ai_agent/client.py

import os
import json
import logging

from .schema import PARAMETER_SCHEMA, build_json_schema, build_recommendation_schema

logger = logging.getLogger(__name__)

MISTRAL_MODEL = "mistral-small-latest"

_INTENT_AGENT_ID = os.environ.get("MISTRAL_INTENT_AGENT_ID")

_INTENT_AGENT_INSTRUCTIONS = (
    "Tu travailles pour Yuumi, un annuaire de commerces locaux francais. "
    "Ton role est UNIQUEMENT de comprendre l'intention de recherche de "
    "l'utilisateur, en utilisant web_search si besoin pour des informations "
    "changeantes ou recentes (meteo, actualite, tendances). "
    "Ne recommande JAMAIS de sites externes, de concurrents, ou de liens "
    "vers d'autres plateformes. Concentre-toi uniquement sur la nature de "
    "la demande : quel type de commerce, quelles contraintes, quelles "
    "idees de produits ou cadeaux pertinentes. Reponds de facon concise."
)


def _get_client():
    """
    Cree un client Mistral. Fonction separee pour pouvoir la simuler
    facilement dans des tests plus tard, et pour centraliser la lecture
    de la cle API a un seul endroit.
    """
    from mistralai.client import Mistral

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY absente de l'environnement.")
    return Mistral(api_key=api_key)


def _get_or_create_intent_agent(client):
    """
    Recupere l'agent de comprehension d'intention, ou le cree s'il n'existe
    pas encore. Une fois cree, son ID devrait etre stocke dans
    MISTRAL_INTENT_AGENT_ID (variable d'environnement) pour ne pas en
    recreer un nouveau a chaque redemarrage du serveur Django.
    """
    global _INTENT_AGENT_ID

    if _INTENT_AGENT_ID:
        return _INTENT_AGENT_ID

    agent = client.beta.agents.create(
        model=MISTRAL_MODEL,
        description="Agent de comprehension d'intention pour Yuumi",
        name="Yuumi Intent Agent",
        instructions=_INTENT_AGENT_INSTRUCTIONS,
        tools=[{"type": "web_search"}],
    )
    _INTENT_AGENT_ID = agent.id
    logger.warning(
        f"Nouvel agent Yuumi cree avec l'ID {agent.id} - pense a l'ajouter "
        f"a MISTRAL_INTENT_AGENT_ID dans le .env pour ne pas en recreer un "
        f"a chaque redemarrage."
    )
    return _INTENT_AGENT_ID


def get_categories_block():
    """
    Reconstruit la liste des categories reelles depuis la base de donnees,
    A CHAQUE APPEL - jamais une liste figee en dur dans le code.
    """
    from members.models import Category

    categories = (
        Category.objects
        .select_related("super_categorie")
        .order_by("super_categorie__name", "name")
        .values_list("slug", "name", "super_categorie__name")
    )

    lignes = [
        f"- {slug} ({name}, famille: {super_name or 'Autres'})"
        for slug, name, super_name in categories
    ]
    return "\n".join(lignes)


def build_system_prompt():
    """
    Genere le prompt systeme pour l'appel d'extraction (etape 2a : intention
    generale -> categories + parametres de filtre), a partir du schema de
    parametres et de la liste de categories reelles.
    """
    categories_block = get_categories_block()

    parametres_block = "\n".join(
        f"- {p['field']} ({p['type']}) : {p['description']}"
        for p in PARAMETER_SCHEMA
    )

    return f"""Tu es l'assistant de recherche de Yuumi, un annuaire de commerces locaux en France.

Ta tache : analyser la requete de l'utilisateur et en extraire les parametres de recherche structures, selon le schema suivant :

{parametres_block}

Categories reellement disponibles sur Yuumi (tu ne peux choisir QUE parmi celles-ci, jamais en inventer une nouvelle) :

{categories_block}

Regles strictes :
- Ne remplis un parametre optionnel QUE si l'utilisateur l'exprime clairement, explicitement ou implicitement. Ne jamais inventer une valeur par defaut.
- Le champ "categories" doit toujours contenir au moins une categorie pertinente parmi la liste ci-dessus.
- Si la requete est ambigue et peut correspondre a plusieurs categories, inclus-les toutes plutot que d'en choisir une seule arbitrairement.

Clarification :
- Si la demande est trop generale pour produire des idees_produits utiles (typiquement une demande de cadeau ou d'occasion sans destinataire, sans contexte, sans budget - ex: "un cadeau", "une idee de sortie"), mets besoin_clarification=true et propose 1 a 2 questions courtes avec des options cliquables (ex: question "Pour qui ?" avec options ["Conjoint(e)", "Ami(e)", "Parent", "Collegue"]).
- Si la demande contient deja assez de contexte pour chercher directement (ex: "foie gras", "un restaurant ouvert maintenant", "un cadeau pour ma mere qui aime le jardinage"), mets besoin_clarification=false et questions_clarification=[].
- Une demande de type produit_precis ou commerce_precis n'a presque jamais besoin de clarification - c'est surtout les demandes tres ouvertes ("besoin"/cadeau sans contexte) qui en ont besoin.
"""


def understand_intent(user_query):
    """
    Appel 1 : agent avec web_search, repond en texte libre. Comprend
    l'intention generale, peut chercher sur le web si besoin (infos
    changeantes), mais ne connait jamais la base Yuumi elle-meme.

    Renvoie le texte de la reponse (str), ou None en cas d'echec.
    """
    try:
        client = _get_client()
        agent_id = _get_or_create_intent_agent(client)

        response = client.beta.conversations.start(
            agent_id=agent_id,
            inputs=user_query,
        )

        return response.outputs[-1].content

    except Exception as e:
        logger.error(f"understand_intent a echoue : {e}")
        return None


def extract_search_params(user_query, intent_text):
    """
    Appel 2a : transforme le texte libre de l'appel 1 en JSON structure
    garanti (categories, ouvert_maintenant, rayon_km, idees_produits).

    Renvoie un dict Python, ou None en cas d'echec.
    """
    if intent_text is None:
        logger.error("extract_search_params : intent_text est None, appel annule.")
        return None

    try:
        client = _get_client()

        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": intent_text},
                {"role": "user", "content": "Traduis cette intention en JSON structure selon le schema fourni."},
            ],
            response_format=build_json_schema(),
            temperature=0,
        )
        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        logger.error(f"extract_search_params a echoue : {e}")
        return None


def recommend_stores(user_query, stores_list, store_ids_par_produit=None):
    """
    Appel 2b : implementation de la methode formalisee (voir documents
    "Methode assistant yuumi" / "Prompt assistant yuumi").

    Classifie l'intention (produit_precis / commerce_precis / besoin /
    hors_sujet), distingue confirme vs deduit pour chaque resultat, et
    ne peut JAMAIS citer un commerce absent de stores_list - le modele
    ne fait que choisir et justifier parmi ce qu'on lui fournit.

    stores_list : liste Python de Store (resultat de la fusion
    categories + produits, deja plafonnee a un nombre raisonnable de
    candidats par search.py - voir MAX_CANDIDATES_TO_LLM).

    store_ids_par_produit : ensemble des ID de Store trouves via une
    correspondance produit EXACTE (table Product) - marque ces
    commerces comme [CONFIRME] dans le prompt, ce qui autorise l'IA a
    leur attribuer confiance="confirme" meme si leur description
    generale ne mentionne pas explicitement le produit.

    Renvoie un dict {intention, message, resultats, aucun_resultat},
    ou None en cas d'echec technique (reseau, JSON invalide).
    """
    store_ids_par_produit = store_ids_par_produit or set()

    if not stores_list:
        commerces_avec_id = "(aucun candidat disponible pour cette recherche)"
    else:
        lignes = []
        for store in stores_list:
            confirmation = ""
            if store.id in store_ids_par_produit:
                confirmation = " [CONFIRME : vend reellement un produit correspondant a la recherche]"
            lignes.append(
                f"- ID {store.id} : {store.nom} "
                f"({store.categorie.name if store.categorie else 'Sans categorie'}) "
                f"- {store.descriptionpetite or 'Pas de description disponible.'}"
                f"{confirmation}"
            )
        commerces_avec_id = "\n".join(lignes)

    system_prompt = (
        "Tu es l'assistant de Yuumi. Tu aides l'utilisateur a trouver des "
        "produits et des commerces locaux.\n\n"
        "Tu ne peux citer QUE les commerces presents dans la liste candidats "
        "fournie ci-dessous. Tu n'inventes jamais un commerce, une adresse "
        "ou la disponibilite d'un produit. Si aucun candidat ne convient, "
        "dis-le.\n\n"
        f"Candidats (seuls commerces autorises) :\n{commerces_avec_id}\n\n"
        "Pour chaque demande :\n"
        "1. Classe l'intention : produit_precis, commerce_precis, besoin, "
        "ou hors_sujet.\n"
        "   - hors_sujet (sans rapport avec produits/commerces locaux) -> "
        "resultats vide, message de recadrage poli vers la mission de Yuumi.\n"
        "2. Selectionne parmi les candidats ceux qui repondent a la demande, "
        "les plus pertinents d'abord. Pas de limite arbitraire de nombre - "
        "recommande tout ce qui est reellement pertinent parmi les candidats.\n"
        "3. Pour chaque resultat :\n"
        "   - confiance='confirme' si le candidat est marque [CONFIRME] ou si "
        "sa description mentionne explicitement le produit/service demande.\n"
        "   - confiance='deduit' si tu deduis seulement depuis sa categorie "
        "generale (ce type de commerce en propose generalement). Dans ce cas, "
        "le dire explicitement dans la justification ('a confirmer', "
        "'generalement').\n"
        "   - justification : une phrase courte expliquant pourquoi ce "
        "commerce, basee UNIQUEMENT sur les informations fournies ci-dessus. "
        "Ne jamais ajouter de details que tu ne peux pas verifier, comme un "
        "positionnement tarifaire ('haut de gamme', 'le meilleur') qui n'est "
        "confirme par aucune donnee fournie.\n"
        "4. Pour une demande 'besoin' (cadeau, occasion) : tu peux t'appuyer "
        "sur tes connaissances pour identifier des types de produits "
        "pertinents, MAIS les commerces cites doivent toujours venir des "
        "candidats fournis. Si aucun candidat ne couvre une idee, n'invente "
        "pas de commerce - mentionne juste que tu n'as pas trouve "
        "d'etablissement correspondant dans la liste.\n"
        "Ne jamais inventer un ID qui n'est pas dans la liste des candidats."
    )

    try:
        client = _get_client()

        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
            response_format=build_recommendation_schema(),
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        logger.error(f"recommend_stores a echoue : {e}")
        return None
