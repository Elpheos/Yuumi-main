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
    from mistralai.client import Mistral

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY absente de l'environnement.")
    return Mistral(api_key=api_key)


def _get_or_create_intent_agent(client):
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
"""


def understand_intent(user_query):
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
    stores_list : liste Python de Store (fusion categories + produits).

    store_ids_par_produit : ensemble des ID de Store trouves via une
    correspondance produit EXACTE (table Product). Marque ces commerces
    comme vendant reellement le produit recherche.

    Renvoie un dict {message_intro, commerces_recommandes} ou None en cas
    d'echec. message_intro est la "bulle" affichee avant la liste.
    """
    if not stores_list:
        return {"message_intro": "", "commerces_recommandes": []}

    store_ids_par_produit = store_ids_par_produit or set()

    lignes = []
    for store in stores_list:
        confirmation = ""
        if store.id in store_ids_par_produit:
            confirmation = " [CE COMMERCE VEND REELLEMENT UN PRODUIT CORRESPONDANT A LA RECHERCHE]"
        lignes.append(
            f"- ID {store.id} : {store.nom} "
            f"({store.categorie.name if store.categorie else 'Sans categorie'}) "
            f"- {store.descriptionpetite or 'Pas de description disponible.'}"
            f"{confirmation}"
        )
    commerces_avec_id = "\n".join(lignes)

    try:
        client = _get_client()

        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": (
                    "Tu es l'assistant de recherche de Yuumi. Voici une liste de "
                    "commerces REELS disponibles, avec leur description :\n\n"
                    + commerces_avec_id + "\n\n"
                    "Tu dois produire deux choses :\n\n"
                    "1) message_intro : un court texte (1 a 3 phrases) affiche "
                    "AVANT la liste. Commence de facon accueillante, puis reste "
                    "factuel. REGLE IMPORTANTE : si la requete de l'utilisateur "
                    "contient un critere que tu ne peux PAS verifier depuis les "
                    "descriptions ci-dessus (par exemple 'haut de gamme', 'pas "
                    "cher', 'romantique', 'chaleureux', 'le meilleur'...), ne le "
                    "valide JAMAIS comme un fait : signale-le honnetement dans "
                    "l'intro comme un point a confirmer sur place (ex: 'le "
                    "positionnement haut de gamme reste a confirmer directement "
                    "aupres du commerce'). Si la requete est neutre et sans "
                    "critere invraisemblable a verifier, reste simplement "
                    "accueillant et direct, sans ajouter de reserve inutile.\n\n"
                    "2) commerces_recommandes : recommande jusqu'a 10 commerces "
                    "parmi CETTE LISTE UNIQUEMENT, en utilisant leur ID EXACT. "
                    "Si un commerce est marque [CE COMMERCE VEND REELLEMENT UN "
                    "PRODUIT CORRESPONDANT A LA RECHERCHE], cela signifie qu'il "
                    "vend vraiment ce qui est recherche, meme si sa description "
                    "generale ne le precise pas - recommande-le en priorite. "
                    "Pour chaque commerce, donne une raison COURTE et FACTUELLE, "
                    "basee UNIQUEMENT sur sa description - ne repete pas un "
                    "qualificatif non verifiable (comme 'haut de gamme') dans la "
                    "raison, et n'invente aucun detail. Ne jamais inventer un ID "
                    "qui n'est pas dans cette liste."
                )},
                {"role": "user", "content": user_query},
            ],
            response_format=build_recommendation_schema(),
            temperature=0.3,
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return {
            "message_intro": result.get("message_intro", ""),
            "commerces_recommandes": result.get("commerces_recommandes", []),
        }

    except Exception as e:
        logger.error(f"recommend_stores a echoue : {e}")
        return None
