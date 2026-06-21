# members/ai_agent/client.py

import os
import json
import logging

from .schema import PARAMETER_SCHEMA, build_json_schema

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"


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
    Genere le prompt systeme a partir du schema de parametres et de la
    liste de categories reelles.
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


def call_mistral_extraction(user_query):
    """
    Appelle l'API Mistral pour traduire une requete en langage libre vers
    le JSON structure defini par schema.py.

    Renvoie un dict Python en cas de succes, ou None en cas d'echec.
    """
    import requests

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.error("MISTRAL_API_KEY absente de l'environnement - appel IA annule.")
        return None

    system_prompt = build_system_prompt()

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        "response_format": build_json_schema(),
        "temperature": 0,
        "max_tokens": 300,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            MISTRAL_API_URL,
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Appel Mistral echoue : {e}")
        return None

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Reponse Mistral invalide ou inattendue : {e}")
        return None
