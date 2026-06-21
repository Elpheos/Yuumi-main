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
    Schema JSON pour l'appel final : l'IA recoit une liste de vrais commerces
    (avec leur ID Django exact) et doit choisir parmi eux, en renvoyant
    uniquement des ID - jamais un nom ou un slug retape a la main, qui
    pourrait etre legerement deforme.

    L'ID etant un entier recopie depuis la liste fournie, il ne peut pas
    etre "approximativement juste" comme un texte libre - soit c'est le bon
    ID, soit la recherche en base ne trouvera rien, ce qui est detectable
    et filtrable cote code.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "yuumi_recommandation",
            "schema": {
                "type": "object",
                "properties": {
                    "commerces_recommandes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "description": (
                                        "ID exact du commerce, recopie depuis "
                                        "la liste fournie - jamais invente."
                                    ),
                                },
                                "raison": {
                                    "type": "string",
                                    "description": (
                                        "Courte explication de pourquoi ce "
                                        "commerce correspond a la demande."
                                    ),
                                },
                            },
                            "required": ["id", "raison"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["commerces_recommandes"],
                "additionalProperties": False,
            },
        },
    }
