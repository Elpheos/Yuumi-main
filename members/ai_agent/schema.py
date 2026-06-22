# members/ai_agent/schema.py
#
# C'EST ICI, ET UNIQUEMENT ICI, QU'IL FAUT AJOUTER UN NOUVEAU PARAMETRE
# quand tu ajoutes une nouvelle metadonnee a Store plus tard.

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
        "filter_lookup": None,
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

    Utilise par extract_search_params() - etape de comprehension de
    l'intention generale (categories + parametres de filtre).
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


def build_recommendation_schema():
    """
    Schema JSON pour l'appel final de recommandation, conforme a la
    methode formalisee : classification d'intention (produit_precis /
    commerce_precis / besoin / hors_sujet), resultats avec confiance
    (confirme / deduit) et justification - ces deux derniers champs
    alimentent directement la bulle affichee a l'utilisateur cote
    frontend (texte = justification, couleur = confiance).

    Utilise par recommend_stores() - etape finale, apres que la recherche
    en base (search.py) a deja fourni les VRAIS candidats. Le modele ne
    choisit et justifie que parmi ce qu'on lui donne, il ne peut jamais
    citer un commerce absent de la liste de candidats.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "yuumi_recommandation",
            "schema": {
                "type": "object",
                "properties": {
                    "intention": {
                        "type": "string",
                        "enum": ["produit_precis", "commerce_precis", "besoin", "hors_sujet"],
                        "description": (
                            "Classification de la demande : produit_precis (objet "
                            "nomme), commerce_precis (type d'etablissement nomme), "
                            "besoin (demande ouverte type cadeau/occasion), "
                            "hors_sujet (sans rapport avec les commerces locaux)."
                        ),
                    },
                    "message": {
                        "type": "string",
                        "description": "Phrase d'introduction courte adressee a l'utilisateur.",
                    },
                    "resultats": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "description": "ID exact du commerce, recopie depuis la liste fournie.",
                                },
                                "confiance": {
                                    "type": "string",
                                    "enum": ["confirme", "deduit"],
                                    "description": (
                                        "confirme : ce commerce propose explicitement le produit/"
                                        "service demande (marque CONFIRME dans la liste, ou "
                                        "mentionne dans sa description). "
                                        "deduit : ce type de commerce en propose generalement, "
                                        "mais ce n'est pas confirme par les donnees fournies."
                                    ),
                                },
                                "justification": {
                                    "type": "string",
                                    "description": (
                                        "Courte explication affichee a l'utilisateur (la bulle). "
                                        "Si confiance=deduit, le dire explicitement "
                                        "(ex: 'a confirmer', 'generalement')."
                                    ),
                                },
                            },
                            "required": ["id", "confiance", "justification"],
                            "additionalProperties": False,
                        },
                    },
                    "aucun_resultat": {
                        "type": "boolean",
                        "description": "True si aucun candidat ne correspond a la demande.",
                    },
                },
                "required": ["intention", "message", "resultats", "aucun_resultat"],
                "additionalProperties": False,
            },
        },
    }
