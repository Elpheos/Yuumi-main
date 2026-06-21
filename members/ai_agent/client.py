# members/ai_agent/client.py
#
# Architecture validee manuellement dans le shell, maintenant transformee
# en vrai code reutilisable :
#
#   1. understand_intent()    -> Appel 1 : agent avec web_search, repond en
#                                 texte libre. Comprend l'intention generale.
#   2. extract_search_params() -> Appel 2a : chat.complete() classique avec
#                                 JSON Schema strict. Transforme le texte
#                                 libre en categories/parametres garantis.
#   3. recommend_stores()      -> Appel 2b : chat.complete() avec JSON Schema
#                                 strict, recoit une liste de VRAIS commerces
#                                 (avec leur ID) et choisit parmi eux.
#
# Entre les etapes 2 et 3, c'est members/ai_agent/search.py (a part) qui va
# chercher les vrais commerces en base - aucune IA n'intervient a cette etape.

import os
import json
import logging

from .schema import PARAMETER_SCHEMA, build_json_schema, build_recommendation_schema

logger = logging.getLogger(__name__)

MISTRAL_MODEL = "mistral-small-latest"

# Cet agent est cree une seule fois et reutilise - pas besoin d'en recreer un
# a chaque requete. Son ID est stocke ici une fois cree (voir note plus bas).
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
    pas encore. En pratique, une fois cree, son ID devrait etre stocke dans
    MISTRAL_INTENT_AGENT_ID (variable d'environnement) pour ne pas en
    recreer un nouveau a chaque redemarrage du serveur Django - chaque
    agent cree reste indefiniment dans le compte Mistral.
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
    Genere le prompt systeme pour l'appel d'extraction (etape 2a), a partir
    du schema de parametres et de la liste de categories reelles.
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
"""


def understand_intent(user_query):
    """
    Appel 1 : agent avec web_search, repond en texte libre.

    Renvoie le texte de la reponse (str), ou None en cas d'echec.
    """
    try:
        client = _get_client()
        agent_id = _get_or_create_intent_agent(client)

        response = client.beta.conversations.start(
            agent_id=agent_id,
            inputs=user_query,
        )

        # outputs peut contenir un ToolExecutionEntry (si web_search a ete
        # declenche) suivi d'un MessageOutputEntry - on veut toujours le
        # DERNIER element, qui est la reponse finale du modele.
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


def recommend_stores(user_query, stores_queryset):
    """
    Appel 2b : recoit une liste de VRAIS commerces (un queryset Django) et
    choisit parmi eux, en renvoyant uniquement des ID exacts.

    stores_queryset : un queryset de Store, deja filtre par categorie/ville
    par le code appelant (voir search.py) - cette fonction ne fait aucune
    recherche en base elle-meme, elle ne fait que demander a l'IA de choisir
    parmi ce qu'on lui donne.

    Renvoie une liste de dicts {"id": int, "raison": str}, ou None en cas
    d'echec. Le code appelant doit ensuite verifier que chaque ID existe
    reellement (au cas tres rare ou l'IA en inventerait un malgre la
    consigne - le JSON Schema garantit le FORMAT, pas le CONTENU).
    """
    if not stores_queryset:
        return []

    commerces_avec_id = "\n".join(
        f"- ID {store.id} : {store.nom} ({store.categorie.name if store.categorie else 'Sans categorie'})"
        for store in stores_queryset
    )

    try:
        client = _get_client()

        response = client.chat.complete(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": (
                    "Tu es l'assistant de recherche de Yuumi. Voici une liste de "
                    "commerces REELS disponibles :\n\n" + commerces_avec_id + "\n\n"
                    "Recommande 2 a 3 commerces parmi CETTE LISTE UNIQUEMENT, en "
                    "utilisant leur ID EXACT tel que donne ci-dessus. Donne une "
                    "raison courte pour chaque recommandation. Ne jamais inventer "
                    "un ID qui n'est pas dans cette liste."
                )},
                {"role": "user", "content": user_query},
            ],
            response_format=build_recommendation_schema(),
            temperature=0.3,
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return result.get("commerces_recommandes", [])

    except Exception as e:
        logger.error(f"recommend_stores a echoue : {e}")
        return None
