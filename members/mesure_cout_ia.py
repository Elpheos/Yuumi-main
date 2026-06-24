#!/usr/bin/env python3
"""
Mesure du cout reel du pipeline ai_agent de Yuumi, en appelant directement
l'API Mistral avec les memes prompts que client.py / schema.py.

Usage :
    export MISTRAL_API_KEY="ta_cle"
    python3 mesure_cout_ia.py

Necessite : pip install mistralai --break-system-packages (ou dans un venv)
"""

import os
import json
import sys

try:
    from mistralai import Mistral
except ImportError:
    print("Le package 'mistralai' n'est pas installe.")
    print("Installe-le avec : pip install mistralai")
    sys.exit(1)

MISTRAL_MODEL = "mistral-small-latest"

# Tarifs officiels mistral-small-latest (verifies sur docs.mistral.ai, juin 2026)
PRIX_INPUT_PAR_MILLION = 0.15   # $ / 1M tokens input
PRIX_OUTPUT_PAR_MILLION = 0.60  # $ / 1M tokens output


# ---------------------------------------------------------------------------
# Reconstruction fidele des prompts de members/ai_agent/client.py et schema.py
# (categories factices proches de celles d'un vrai catalogue Yuumi, pour ne
# pas dependre d'un acces a la base de donnees Django dans ce script isole)
# ---------------------------------------------------------------------------

CATEGORIES_FACTICES = """- boulangerie (Boulangerie, famille: Alimentation)
- charcuterie (Charcuterie, famille: Alimentation)
- epicerie-fine (Epicerie fine, famille: Alimentation)
- fleuriste (Fleuriste, famille: Maison & deco)
- librairie (Librairie, famille: Culture & loisirs)
- bijouterie (Bijouterie, famille: Mode & accessoires)
- restaurant (Restaurant, famille: Restauration)
- bar (Bar, famille: Restauration)
- pret-a-porter (Pret-a-porter, famille: Mode & accessoires)
- decoration (Decoration, famille: Maison & deco)"""

PARAMETER_SCHEMA = [
    {
        "field": "categories", "type": "list[str]",
        "description": ("Liste des slugs de categories Yuumi pertinentes pour la requete. "
                         "Doit etre choisie UNIQUEMENT parmi la liste de categories fournie "
                         "dans le contexte - ne jamais inventer une categorie qui n'existe pas."),
        "required": True, "filter_lookup": "categorie__slug__in",
    },
    {
        "field": "idees_produits", "type": "list[str]",
        "description": ("Idees de produits ou articles generiques pertinents pour la requete "
                         "(ex: 'bouquet de roses', 'chocolat', 'bijou'). Ce sont des pistes de "
                         "recherche, PAS une garantie qu'ils existent chez un commercant Yuumi - "
                         "elles seront verifiees ensuite. Laisser vide si la requete ne porte pas "
                         "sur un produit precis (ex: simple recherche de categorie de commerce)."),
        "required": False, "filter_lookup": None,
    },
    {
        "field": "ouvert_maintenant", "type": "bool",
        "description": ("True si la requete implique une urgence temporelle explicite ou "
                         "implicite (ex: 'maintenant', 'tout de suite', 'ce soir'). "
                         "False ou absent si rien ne l'indique."),
        "required": False, "filter_lookup": None,
    },
    {
        "field": "rayon_km", "type": "float",
        "description": ("Rayon de recherche en kilometres, UNIQUEMENT si l'utilisateur "
                         "donne une indication de distance ou de proximite explicite "
                         "(ex: 'pas loin', 'a 2km'). Ne jamais inventer une valeur par defaut."),
        "required": False, "filter_lookup": None,
    },
]


def build_json_schema():
    type_mapping = {
        "list[str]": {"type": "array", "items": {"type": "string"}},
        "bool": {"type": "boolean"},
        "float": {"type": "number"},
        "str": {"type": "string"},
    }
    properties = {}
    required_fields = []
    for param in PARAMETER_SCHEMA:
        json_type = type_mapping.get(param["type"], {"type": "string"})
        properties[param["field"]] = {**json_type, "description": param["description"]}
        if param["required"] and param["field"] != "categories":
            required_fields.append(param["field"])

    properties["hors_sujet"] = {"type": "boolean", "description": "True si hors sujet."}
    properties["categorie_absente"] = {"type": "boolean", "description": "True si categorie absente."}
    properties["besoin_clarification"] = {"type": "boolean", "description": "True si besoin de clarification."}
    properties["questions_clarification"] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question", "options"],
            "additionalProperties": False,
        },
        "description": "Questions de clarification eventuelles.",
    }
    required_fields += ["hors_sujet", "categorie_absente", "besoin_clarification", "questions_clarification"]

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "yuumi_search_intent",
            "schema": {
                "type": "object",
                "properties": properties,
                "required": required_fields,
                "additionalProperties": False,
            },
        },
    }


def build_recommendation_schema():
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "yuumi_recommendation",
            "schema": {
                "type": "object",
                "properties": {
                    "intention": {"type": "string"},
                    "message": {"type": "string"},
                    "pistes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "angle": {"type": "string"},
                                "resultats": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "confiance": {"type": "string"},
                                            "justification": {"type": "string"},
                                        },
                                        "required": ["id", "confiance", "justification"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["angle", "resultats"],
                            "additionalProperties": False,
                        },
                    },
                    "aucun_resultat": {"type": "boolean"},
                },
                "required": ["intention", "message", "pistes", "aucun_resultat"],
                "additionalProperties": False,
            },
        },
    }


def build_system_prompt_extract():
    parametres_block = "\n".join(
        f"- {p['field']} ({p['type']}) : {p['description']}" for p in PARAMETER_SCHEMA
    )
    return f"""Tu es l'assistant de recherche de Yuumi, un annuaire de commerces locaux en France.

Ta tache : analyser la requete de l'utilisateur et en extraire les parametres de recherche structures, selon le schema suivant :

{parametres_block}

Categories reellement disponibles sur Yuumi (tu ne peux choisir QUE parmi celles-ci, jamais en inventer une nouvelle) :

{CATEGORIES_FACTICES}

Regles strictes :
- Ne remplis un parametre optionnel QUE si l'utilisateur l'exprime clairement, explicitement ou implicitement. Ne jamais inventer une valeur par defaut.
- Le champ "categories" doit toujours contenir au moins une categorie pertinente parmi la liste ci-dessus, SAUF si hors_sujet=true (dans ce cas, laisse categories vide).
- Si la requete est ambigue et peut correspondre a plusieurs categories, inclus-les toutes plutot que d'en choisir une seule arbitrairement.
Hors-sujet et categorie absente (deux cas DIFFERENTS, ne jamais les confondre) :
- hors_sujet=true : UNIQUEMENT si la demande n'a AUCUN sens commercial.
- categorie_absente=true : si la demande decrit un VRAI type de commerce ou produit qui a du sens, mais qu'AUCUNE des categories listees ci-dessus ne correspond.
- REGLE ABSOLUE : que ce soit hors_sujet=true OU categorie_absente=true, categories DOIT TOUJOURS etre une liste vide [].
Clarification :
- Si la demande est trop generale, mets besoin_clarification=true et propose 1 a 2 questions courtes avec options cliquables (toujours avec une option de sortie en derniere position).
"""


def build_system_prompt_recommend(stores_fictifs, ouvert_maintenant=False):
    lignes = []
    for store in stores_fictifs:
        lignes.append(
            f"- ID {store['id']} : {store['nom']} ({store['categorie']}) - {store['description']}"
            + (" [CONFIRME : vend reellement un produit correspondant a la recherche]" if store.get("confirme") else "")
        )
    commerces_avec_id = "\n".join(lignes) if lignes else "(aucun candidat disponible pour cette recherche)"

    system_prompt = (
        "Tu es l'assistant de Yuumi. Tu aides l'utilisateur a trouver des "
        "produits et des commerces locaux.\n\n"
        "Tu ne peux citer QUE les commerces presents dans la liste candidats "
        "fournie ci-dessous. Tu n'inventes jamais un commerce, une adresse "
        "ou la disponibilite d'un produit.\n\n"
        f"Candidats (seuls commerces autorises) :\n{commerces_avec_id}\n\n"
        "Pour chaque demande :\n"
        "1. Classe l'intention : produit_precis, commerce_precis, besoin, ou hors_sujet.\n"
        "2. Organise ta reponse en PISTES (un angle/une approche distincte chacune).\n"
        "3. Pour chaque resultat : confiance='confirme' SEULEMENT si [CONFIRME] est present, "
        "sinon confiance='deduit'. Justifie en reliant la demande au commerce.\n"
        "4. UN COMMERCE NE PEUT JAMAIS APPARAITRE DANS PLUSIEURS PISTES.\n"
        "Ne jamais inventer un ID qui n'est pas dans la liste des candidats."
    )
    if ouvert_maintenant:
        system_prompt += "\n\nCONTEXTE 'OUVERT MAINTENANT' : tous les candidats sont ouverts actuellement."
    return system_prompt


# ---------------------------------------------------------------------------
# Scenarios de test
# ---------------------------------------------------------------------------

STORES_FICTIFS_FOIE_GRAS = [
    {"id": 1, "nom": "Charcuterie Dupont", "categorie": "Charcuterie",
     "description": "Charcuterie artisanale, specialiste du foie gras maison et des terrines.", "confirme": True},
    {"id": 2, "nom": "Epicerie Lefevre", "categorie": "Epicerie fine",
     "description": "Epicerie fine proposant foie gras, vins et fromages.", "confirme": False},
    {"id": 3, "nom": "Famille Mary", "categorie": "Epicerie fine",
     "description": "Specialiste des produits de la ruche, epicerie fine.", "confirme": False},
]

STORES_FICTIFS_CADEAU = [
    {"id": 10, "nom": "Fleurs & Co", "categorie": "Fleuriste",
     "description": "Fleuriste createur, bouquets et compositions sur mesure.", "confirme": False},
    {"id": 11, "nom": "Librairie du Coin", "categorie": "Librairie",
     "description": "Librairie generaliste, romans, BD et papeterie.", "confirme": False},
    {"id": 12, "nom": "Bijoux Lumiere", "categorie": "Bijouterie",
     "description": "Bijoux fantaisie et argent, createurs locaux.", "confirme": False},
    {"id": 13, "nom": "Chocolaterie Martin", "categorie": "Epicerie fine",
     "description": "Chocolats artisanaux, coffrets cadeaux.", "confirme": False},
]


def get_client():
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("ERREUR : variable d'environnement MISTRAL_API_KEY absente.")
        sys.exit(1)
    return Mistral(api_key=api_key)


def afficher_usage(label, usage):
    cout_input = (usage.prompt_tokens / 1_000_000) * PRIX_INPUT_PAR_MILLION
    cout_output = (usage.completion_tokens / 1_000_000) * PRIX_OUTPUT_PAR_MILLION
    cout_total = cout_input + cout_output
    print(f"\n--- {label} ---")
    print(f"  tokens input  : {usage.prompt_tokens}")
    print(f"  tokens output : {usage.completion_tokens}")
    print(f"  tokens total  : {usage.total_tokens}")
    print(f"  cout estime   : ${cout_total:.6f}  (input ${cout_input:.6f} + output ${cout_output:.6f})")
    return cout_total


def appel_extract(client, user_query):
    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=[
            {"role": "system", "content": build_system_prompt_extract()},
            {"role": "user", "content": user_query},
            {"role": "user", "content": "Analyse cette requete et produis le JSON structure selon le schema fourni."},
        ],
        response_format=build_json_schema(),
        temperature=0,
    )
    return response


def appel_recommend(client, user_query, stores_fictifs, ouvert_maintenant=False):
    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=[
            {"role": "system", "content": build_system_prompt_recommend(stores_fictifs, ouvert_maintenant)},
            {"role": "user", "content": user_query},
        ],
        response_format=build_recommendation_schema(),
        temperature=0.2,
    )
    return response


def scenario_simple(client):
    """Scenario 1 : requete produit precis, sans web_search (le cas le plus frequent)."""
    print("\n" + "=" * 70)
    print("SCENARIO 1 : requete simple 'je veux du foie gras a Annecy'")
    print("  (etapes : extract_search_params + recommend_stores, PAS de web_search)")
    print("=" * 70)

    total = 0
    r1 = appel_extract(client, "je veux du foie gras")
    total += afficher_usage("extract_search_params", r1.usage)
    print(f"  -> reponse JSON : {r1.choices[0].message.content[:200]}...")

    r2 = appel_recommend(client, "je veux du foie gras", STORES_FICTIFS_FOIE_GRAS)
    total += afficher_usage("recommend_stores", r2.usage)
    print(f"  -> reponse JSON : {r2.choices[0].message.content[:200]}...")

    print(f"\n  TOTAL SCENARIO 1 : ${total:.6f}")
    return total


def scenario_cadeau_ouvert(client):
    """Scenario 2 : demande ouverte type 'cadeau', plusieurs pistes generees."""
    print("\n" + "=" * 70)
    print("SCENARIO 2 : requete ouverte 'un cadeau pour ma mere qui aime le jardinage'")
    print("=" * 70)

    total = 0
    r1 = appel_extract(client, "un cadeau pour ma mere qui aime le jardinage")
    total += afficher_usage("extract_search_params", r1.usage)

    r2 = appel_recommend(client, "un cadeau pour ma mere qui aime le jardinage", STORES_FICTIFS_CADEAU)
    total += afficher_usage("recommend_stores", r2.usage)
    print(f"  -> reponse JSON : {r2.choices[0].message.content[:300]}...")

    print(f"\n  TOTAL SCENARIO 2 : ${total:.6f}")
    return total


def scenario_repete(client):
    """Scenario 3 : meme requete postee 2 fois -> simule ce qu'un cache efficace eviterait."""
    print("\n" + "=" * 70)
    print("SCENARIO 3 : meme requete postee 2 fois (cas 'cache zero')")
    print("  Avec un cache partage qui fonctionne, le 2e appel couterait $0.")
    print("  Sans cache partage (situation actuelle, 1 chance sur 3), il est")
    print("  facture une 2e fois la plupart du temps.")
    print("=" * 70)

    total = 0
    for i in (1, 2):
        r1 = appel_extract(client, "un fleuriste pas loin")
        total += afficher_usage(f"Appel #{i} - extract_search_params", r1.usage)
        r2 = appel_recommend(client, "un fleuriste pas loin", STORES_FICTIFS_CADEAU[:1])
        total += afficher_usage(f"Appel #{i} - recommend_stores", r2.usage)

    print(f"\n  TOTAL SCENARIO 3 (2 appels identiques) : ${total:.6f}")
    print(f"  -> Avec cache partage fonctionnel : ${total/2:.6f} (1 seul appel reellement facture)")
    return total


def main():
    client = get_client()

    grand_total = 0
    grand_total += scenario_simple(client)
    grand_total += scenario_cadeau_ouvert(client)
    grand_total += scenario_repete(client)

    print("\n" + "=" * 70)
    print(f"COUT TOTAL DE CE SCRIPT DE TEST : ${grand_total:.6f}")
    print("=" * 70)
    print("\nRappel quotas Yuumi : DAILY_AI_QUOTA = 10 requetes/jour/utilisateur premium.")
    print("Ces chiffres ne comptent PAS l'appel 'understand_intent' (agent web_search),")
    print("qui ne se declenche que sur des signaux meteo/tendance/evenement explicites.")


if __name__ == "__main__":
    main()
