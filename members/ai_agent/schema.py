# members/ai_agent/schema.py
#
# C'EST ICI, ET UNIQUEMENT ICI, QU'IL FAUT AJOUTER UN NOUVEAU PARAMÈTRE
# quand tu ajoutes une nouvelle métadonnée à Store plus tard.

PARAMETER_SCHEMA = [
    {
        "field": "categories",
        "type": "list[str]",
        "description": (
            "Liste des slugs de categories Yuumi pertinentes pour la requete. "
            "Doit etre choisie UNIQUEMENT parmi la liste de categories fournie "
            "dans le contexte - ne jamais inventer une categorie qui n'existe pas."
        ),
        "required": True,
        "filter_lookup": "categorie__slug__in",
    },
    {
        "field": "idees_produits",
        "type": "list[str]",
        "description": (
            "Idees de produits ou articles generiques pertinents pour la requete "
            "(ex: 'bouquet de roses', 'chocolat', 'bijou'). Ce sont des pistes de "
            "recherche, PAS une garantie qu'ils existent chez un commercant Yuumi - "
            "elles seront verifiees ensuite. Laisser vide si la requete ne porte pas "
            "sur un produit precis (ex: simple recherche de categorie de commerce)."
        ),
        "required": False,
        "filter_lookup": None,  # vérifié en base à part, pas un filtre direct sur Store
    },
    {
        "field": "ouvert_maintenant",
        "type": "bool",
        "description": (
            "True si la requete implique une urgence temporelle explicite ou "
            "implicite (ex: 'maintenant', 'tout de suite', 'ce soir'). "
            "False ou absent si rien ne l'indique."
        ),
        "required": False,
        "filter_lookup": None,
    },
    {
        "field": "rayon_km",
        "type": "float",
        "description": (
            "Rayon de recherche en kilometres, UNIQUEMENT si l'utilisateur "
            "donne une indication de distance ou de proximite explicite "
            "(ex: 'pas loin', 'a 2km'). Ne jamais inventer une valeur par defaut."
        ),
        "required": False,
        "filter_lookup": None,
    },
]


def build_json_schema():
    """
    Construit le schema JSON (format attendu par l'API Mistral en mode
    Custom Structured Outputs) a partir de PARAMETER_SCHEMA.
    """
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
        properties[param["field"]] = {
            **json_type,
            "description": param["description"],
        }
        if param["required"]:
            required_fields.append(param["field"])

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

# A ajouter dans members/ai_agent/schema.py, a la suite du fichier existant.
# Ce schema est different de build_json_schema() : il sert pour l'ETAPE FINALE
# (choisir des commerces reels parmi une liste fournie), pas pour l'extraction
# d'intention initiale.

def build_recommendation_schema():
    """
    Schema de la reponse finale de recommandation.

    message_intro : petit texte d'introduction (la "bulle") affiche AVANT
        la liste des commerces. Contextualise la recherche, et signale
        honnetement quand un critere demande (haut de gamme, pas cher,
        romantique...) ne peut pas etre verifie depuis nos donnees.
    commerces_recommandes : la liste des commerces choisis, par ID exact.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "yuumi_recommandation",
            "schema": {
                "type": "object",
                "properties": {
                    "message_intro": {
                        "type": "string",
                        "description": (
                            "Court texte d'introduction (1 a 3 phrases) affiche "
                            "avant la liste. Accueillant, puis factuel. Si la "
                            "requete contient un critere NON verifiable depuis "
                            "les descriptions (haut de gamme, pas cher, "
                            "romantique, etc.), le signaler honnetement ici "
                            "plutot que de l'affirmer. Si la requete est neutre, "
                            "rester simplement accueillant et direct, sans "
                            "reserve inutile."
                        ),
                    },
                    "commerces_recommandes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "raison": {"type": "string"},
                            },
                            "required": ["id", "raison"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["message_intro", "commerces_recommandes"],
                "additionalProperties": False,
            },
        },
    }
