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

# Variante du prompt utilisee uniquement pour le fallback sans outil (voir
# understand_intent) - retire toute mention de web_search, puisque l'appel
# de repli n'a justement plus cet outil a sa disposition. Sans ce
# changement, le modele pourrait essayer d'expliquer qu'il "aurait du"
# chercher sur le web, ce qui n'apporte rien a l'etape suivante
# (extract_search_params) et peut meme la perturber.
_INTENT_FALLBACK_INSTRUCTIONS = (
    "Tu travailles pour Yuumi, un annuaire de commerces locaux francais. "
    "Ton role est UNIQUEMENT de comprendre l'intention de recherche de "
    "l'utilisateur a partir de tes connaissances generales. "
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


def _is_web_search_quota_error(exception):
    """
    Detecte si une exception correspond specifiquement a un rate limit ou
    quota depasse sur l'outil web_search (par opposition a une erreur
    d'authentification, un probleme reseau, ou un rate limit general sur
    l'API elle-meme).

    Observe en prod (tier gratuit Mistral) : "API error occurred: Status
    429. Body: {"detail":"web_search rate limit reached."}" - un message
    DIFFERENT du rate limit generique de l'API ("Rate limit exceeded" /
    "Requests rate limit exceeded" sans mention de web_search), ce qui
    suggere un quota separe et plus restrictif specifique a cet outil,
    notamment en tier gratuit.

    Volontairement restrictif (cherche "429" ET "web_search" ensemble) :
    un 429 generique sur l'API (vrai rate limit de compte) ne doit PAS
    declencher le fallback sans outil, puisque l'appel de repli passerait
    de toute facon par la meme API et echouerait probablement aussi - dans
    ce cas, mieux vaut laisser l'erreur remonter normalement et activer
    fallback_to_tree cote views.py, plutot que de masquer un vrai
    probleme de quota global par une fausse reussite partielle.
    """
    message = str(exception).lower()
    return "429" in message and "web_search" in message


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
- Le champ "categories" doit toujours contenir au moins une categorie pertinente parmi la liste ci-dessus, SAUF si hors_sujet=true (dans ce cas, laisse categories vide).
- Si la requete est ambigue et peut correspondre a plusieurs categories, inclus-les toutes plutot que d'en choisir une seule arbitrairement.

Hors-sujet et categorie absente (deux cas DIFFERENTS, ne jamais les confondre) :
- hors_sujet=true : UNIQUEMENT si la demande n'a AUCUN sens commercial, meme en theorie (mots isoles sans signification, insultes, contenu absurde). Dans ce cas, categories=[] et categorie_absente=false.
- categorie_absente=true : si la demande decrit un VRAI type de commerce ou produit qui a du sens, mais qu'AUCUNE des categories listees ci-dessus ne correspond reellement (ex: "armurerie", "magasin de drones", alors qu'aucune categorie Yuumi ne couvre cela). Dans ce cas, hors_sujet=false et categories=[].
- REGLE ABSOLUE ET NON NEGOCIABLE : que ce soit hors_sujet=true OU categorie_absente=true, categories DOIT TOUJOURS etre une liste vide [] - JAMAIS une categorie approximative ou la moins mauvaise possible. Il n'existe AUCUNE exception.
- Exemple : "armurerie" -> hors_sujet=false, categorie_absente=true, categories=[] (la demande a un sens commercial reel, mais Yuumi ne reference pas ce type de commerce).
- Exemple : "pipi" -> hors_sujet=true, categorie_absente=false, categories=[] (aucun sens commercial).
- Si une categorie reelle correspond, hors_sujet=false ET categorie_absente=false, et categories est rempli normalement.

Clarification :
- Si la demande est trop generale pour produire des idees_produits utiles (typiquement une demande de cadeau ou d'occasion sans destinataire, sans contexte, sans budget - ex: "un cadeau", "une idee de sortie"), mets besoin_clarification=true et propose 1 a 2 questions courtes avec des options cliquables.
- REGLE GENERALE OBLIGATOIRE : pour CHAQUE question de clarification, la derniere option doit TOUJOURS etre une option de sortie du type "Je ne sais pas" ou "Surprends-moi" - peu importe le sujet de la question (type de produit, centre d'interet, occasion, budget, ou autre). Cette regle s'applique systematiquement, sans exception, car l'utilisateur qui pose une question generale ne sait souvent pas lui-meme repondre a une question precise - il doit toujours pouvoir avancer sans etre bloque.
- Les questions peuvent porter aussi bien sur le contexte de la situation (pour qui, quelle occasion, quel budget) que sur une preference de nature du produit (quel type de cadeau, quel style) - tant que l'option de sortie est presente, les deux types de questions sont valides.
- Exemples de bonnes questions, toujours avec l'option de sortie en derniere position : "Pour qui ?" (options: Conjoint(e), Ami(e), Parent, Collegue, Enfant, Je ne sais pas), "Quel type de cadeau ?" (options: Bijou, Livre, Experience, Objet deco, Surprends-moi), "Quel budget approximatif ?" (options: Moins de 20e, 20-50e, 50-100e, Peu importe).
- REGLE ANTI-BOUCLE OBLIGATOIRE : si le message de l'utilisateur contient deja une indication explicite du type "surprends-moi", "je ne sais pas", "peu importe", ou une formulation equivalente signalant qu'il ne veut plus etre interroge sur un point precis, tu DOIS mettre besoin_clarification=false et chercher directement avec ce que tu sais deja - meme si l'information reste incomplete. Ne JAMAIS poser une nouvelle question de clarification apres un signal explicite de ce type, meme sur un sujet different de la question precedente. Dans ce cas, choisis toi-meme des idees_produits larges et variees a partir du peu de contexte disponible, plutot que de redemander.
- Une demande qui a deja recu une reponse a une premiere serie de questions de clarification (visible si le message utilisateur contient deja des reponses, format "question - reponse - reponse") ne doit JAMAIS declencher une deuxieme serie de clarification - a ce stade, cherche directement avec le contexte disponible, meme partiel.
- Si un segment de reponse contient le mot " ou " entre plusieurs valeurs (ex: "Bijou ou Livre"), cela signifie que l'utilisateur a selectionne plusieurs options comme des ALTERNATIVES valables, pas une contrainte cumulative - traite chaque valeur comme une piste independante a explorer (ex: produire des idees_produits couvrant a la fois les bijoux ET les livres, pas seulement l'intersection des deux).
- Si la demande contient deja assez de contexte pour chercher directement (ex: "foie gras", "un restaurant ouvert maintenant", "un cadeau pour ma mere qui aime le jardinage"), mets besoin_clarification=false et questions_clarification=[].
"""


def understand_intent(user_query):
    """
    Appel 1 : agent avec web_search, repond en texte libre. Comprend
    l'intention generale, peut chercher sur le web si besoin (infos
    changeantes), mais ne connait jamais la base Yuumi elle-meme.

    Renvoie le texte de la reponse (str), TOUJOURS une vraie chaine de
    caracteres - jamais une liste d'objets. Quand web_search est utilise
    avec des citations, Mistral renvoie le contenu comme une LISTE de
    chunks (TextChunk, ToolReferenceChunk, ...) plutot qu'une simple
    chaine. Si on transmet cette liste brute a l'etape suivante
    (extract_search_params), l'API la rejette avec une cascade d'erreurs
    de validation - d'ou l'extraction systematique du texte ici, qui
    ignore les chunks de reference et ne garde que le texte lisible.

    FALLBACK SANS OUTIL : le tier gratuit Mistral impose un quota distinct
    et tres restrictif sur l'outil web_search (observe en prod : 429 avec
    le detail "web_search rate limit reached", different du rate limit
    generique de l'API). Plutot que de faire echouer toute la recherche
    pour une requete qui, le plus souvent, n'avait meme pas besoin d'une
    recherche web (ex: "armurerie" ne necessite aucune info recente ou
    changeante), on retente une fois SANS l'agent/l'outil, via un simple
    chat.complete. Ce fallback ne se declenche QUE si l'erreur identifiee
    concerne specifiquement web_search (voir _is_web_search_quota_error) -
    un vrai probleme de cle API, reseau, ou rate limit general sur l'API
    elle-meme continue de faire echouer la fonction normalement.

    Renvoie None en cas d'echec (y compris si le fallback lui-meme echoue).
    """
    client = None
    try:
        client = _get_client()
        agent_id = _get_or_create_intent_agent(client)

        response = client.beta.conversations.start(
            agent_id=agent_id,
            inputs=user_query,
        )

        content = response.outputs[-1].content

        if isinstance(content, str):
            return content

        # content est une liste de chunks (TextChunk, ToolReferenceChunk,
        # etc.) - on ne garde que le texte des TextChunk, dans l'ordre.
        texte_complet = ""
        for chunk in content:
            chunk_type = getattr(chunk, "type", None)
            if chunk_type == "text":
                texte_complet += getattr(chunk, "text", "")

        return texte_complet.strip() if texte_complet.strip() else None

    except Exception as e:
        if _is_web_search_quota_error(e):
            logger.warning(
                f"understand_intent : quota web_search atteint, "
                f"retentative sans outil. Erreur originale : {e}"
            )
            return _understand_intent_fallback(client, user_query)

        logger.error(f"understand_intent a echoue : {e}")
        return None


def _understand_intent_fallback(client, user_query):
    """
    Retentative de understand_intent SANS l'agent ni l'outil web_search,
    via un simple appel chat.complete. Voir le commentaire FALLBACK SANS
    OUTIL dans understand_intent pour le contexte complet.

    client peut etre None si _get_client() avait elle-meme echoue avant
    d'atteindre le bloc try - dans ce cas on en recree un proprement
    plutot que de planter sur un None.

    Renvoie une str (texte libre, comme l'appel normal), ou None si meme
    ce fallback echoue.
    """
    try:
        if client is None:
            client = _get_client()

        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": _INTENT_FALLBACK_INSTRUCTIONS},
                {"role": "user", "content": user_query},
            ],
        )
        texte = response.choices[0].message.content
        if isinstance(texte, str) and texte.strip():
            return texte.strip()
        return None

    except Exception as e:
        logger.error(f"understand_intent (fallback sans web_search) a echoue : {e}")
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
            prompt_cache_key="yuumi-extract-search-params",
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
        result = json.loads(content)

        # Garde-fou cote code, independant du prompt : si hors_sujet=true
        # OU categorie_absente=true, on force categories=[] nous-memes,
        # plutot que de faire confiance uniquement a l'instruction textuelle
        # - un modele peut occasionnellement remplir categories par reflexe
        # de formatage meme quand on lui dit de ne pas le faire (observe en
        # test reel avec "armurerie" -> categories rempli avec 'telephonie'
        # malgre hors_sujet=true avant l'ajout de ce garde-fou).
        if result.get("hors_sujet") or result.get("categorie_absente"):
            result["categories"] = []

        return result

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
            prompt_cache_key="yuumi-recommend-stores",
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
