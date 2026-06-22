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
    Custom Structured Outputs) a partir de PARAMETER_SCHEMA, plus les
    champs fixes (hors_sujet, categorie_absente, besoin_clarification,
    questions_clarification) qui permettent a l'IA de signaler elle-meme
    soit une demande hors-sujet, soit une demande dont le type de
    commerce/produit n'est tout simplement pas reference sur Yuumi, soit
    une demande trop vague pour produire des idees_produits utiles (ex:
    "un cadeau" sans precision de destinataire/occasion/budget).

    Quand besoin_clarification=true, le frontend affiche des boutons de
    reponse rapide (pas de saisie texte) bases sur questions_clarification,
    plutot que de lancer une recherche avec des criteres trop pauvres.

    IMPORTANT : categorie_absente doit etre declare ICI explicitement.
    Le prompt systeme (voir build_system_prompt dans client.py) explique
    a l'IA comment distinguer hors_sujet de categorie_absente, mais cette
    distinction ne peut JAMAIS remonter dans la reponse si la cle n'existe
    pas dans le JSON Schema envoye a l'API - en mode structured outputs
    strict, un champ absent du schema ne peut pas etre renvoye par le
    modele, peu importe ce que dit le prompt. (Bug reel observe : le
    garde-fou cote code dans extract_search_params() teste
    result.get("categorie_absente"), qui restait toujours None avant cet
    ajout - la distinction ne fonctionnait donc qu'a moitie en prod.)
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
        # categories n'est PAS ajoute aux champs requis ici - voir plus bas,
        # ou il est rendu requis sauf en cas de hors_sujet/categorie_absente.
        # Les autres parametres optionnels (idees_produits, ouvert_maintenant,
        # rayon_km) restent vraiment optionnels dans tous les cas.
        if param["required"] and param["field"] != "categories":
            required_fields.append(param["field"])

    properties["hors_sujet"] = {
        "type": "boolean",
        "description": (
            "True si la requete n'a AUCUN rapport avec la recherche de "
            "commerces ou produits locaux (ex: mots isoles sans sens "
            "commercial, insultes, questions techniques sans rapport, "
            "demandes absurdes). False pour toute demande qui a un sens "
            "commercial meme tres vague (ex: 'un truc', 'j'ai besoin "
            "d'aide' restent False si une interpretation commerciale est "
            "plausible - seul un contenu clairement sans rapport est True). "
            "Voir categorie_absente pour le cas different d'un commerce "
            "qui a un sens commercial reel mais n'est pas reference sur Yuumi."
        ),
    }
    properties["categorie_absente"] = {
        "type": "boolean",
        "description": (
            "True si la demande decrit un VRAI type de commerce ou de "
            "produit qui a un sens commercial reel, mais qu'AUCUNE des "
            "categories Yuumi fournies dans le contexte ne correspond "
            "(ex: 'armurerie', 'magasin de drones' alors qu'aucune "
            "categorie Yuumi ne couvre cela). Dans ce cas, hors_sujet doit "
            "etre False et categories doit etre une liste vide. "
            "False dans tous les autres cas, y compris quand hors_sujet=true."
        ),
    }
    properties["besoin_clarification"] = {
        "type": "boolean",
        "description": (
            "True UNIQUEMENT si la demande est trop generale pour produire "
            "des idees_produits utiles (ex: 'un cadeau' sans destinataire, "
            "occasion ou budget). False si la demande est deja assez "
            "precise pour chercher directement (ex: 'foie gras', 'un "
            "restaurant ouvert maintenant', 'un cadeau pour ma mere qui "
            "aime le jardinage')."
        ),
    }
    properties["questions_clarification"] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question courte affichee a l'utilisateur (ex: 'Pour qui ?').",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2 a 4 options courtes cliquables (ex: ['Conjoint(e)', 'Ami(e)', 'Parent', 'Collegue']).",
                },
            },
            "required": ["question", "options"],
            "additionalProperties": False,
        },
        "description": (
            "1 a 2 questions de clarification avec options, UNIQUEMENT si "
            "besoin_clarification=true. Liste vide sinon."
        ),
    }
    required_fields.append("hors_sujet")
    required_fields.append("categorie_absente")
    required_fields.append("besoin_clarification")
    required_fields.append("questions_clarification")

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
    commerce_precis / besoin / hors_sujet), resultats organises en
    PISTES (un angle/une approche chacune) plutot qu'une liste plate.

    POURQUOI DES PISTES, PAS UNE LISTE PLATE (changement important) :
    Pour une demande ouverte type "cadeau de Noel pour un parent, surprenez-
    moi", il n'existe PAS une seule bonne reponse - le modele etait avant
    force par le schema lui-meme a presenter ses choix comme un consensus
    unique ("voici LA selection"), alors que la nature de la demande
    appelle plusieurs angles distincts (deco / gourmand / experience /
    artisanal...). Forcer le modele a nommer chaque piste l'empeche de
    noyer des suggestions tres differentes dans un seul bloc indifferencie,
    et donne au frontend une structure naturelle pour les afficher
    separement (ex: en sections) plutot qu'en une seule liste plate.

    Chaque piste contient son propre groupe de commerces avec confiance/
    justification - le modele ne choisit et justifie que parmi ce qu'on
    lui donne, il ne peut jamais citer un commerce absent de la liste de
    candidats, peu importe la piste.
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
                    "pistes": {
                        "type": "array",
                        "description": (
                            "Groupes de resultats par angle/approche distincte. Pour "
                            "une demande precise (produit_precis, commerce_precis), "
                            "UNE SEULE piste suffit generalement (pas besoin de "
                            "fragmenter artificiellement). Pour une demande ouverte "
                            "(besoin), proposer 2 a 4 pistes RELLEMENT distinctes "
                            "(ex: 'Cote gourmand', 'Cote deco', 'Une experience a "
                            "vivre') plutot qu'une seule liste qui mélange tout - "
                            "ne jamais inventer une piste qui n'a pas de candidat "
                            "reel a y mettre."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "angle": {
                                    "type": "string",
                                    "description": (
                                        "Nom court de l'angle/approche (ex: 'Cote "
                                        "gourmand', 'Une experience a vivre', 'Le "
                                        "choix le plus sur'). Pour une demande "
                                        "precise avec une seule piste, peut etre "
                                        "neutre (ex: 'Notre selection')."
                                    ),
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
                                                    "confirme : UNIQUEMENT si ce commerce est "
                                                    "marque [CONFIRME] dans la liste fournie - "
                                                    "jamais sur la seule base d'une description "
                                                    "qui semble explicite. "
                                                    "deduit : tous les autres cas, y compris "
                                                    "quand la description semble tres pertinente."
                                                ),
                                            },
                                            "justification": {
                                                "type": "string",
                                                "description": (
                                                    "Explication affichee a l'utilisateur (la "
                                                    "bulle), qui relie la demande precise de "
                                                    "l'utilisateur au commerce - jamais une "
                                                    "simple reformulation de sa fiche "
                                                    "descriptive. Si confiance=deduit, le dire "
                                                    "explicitement (ex: 'a confirmer', "
                                                    "'generalement')."
                                                ),
                                            },
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
                    "aucun_resultat": {
                        "type": "boolean",
                        "description": "True si aucun candidat ne correspond a la demande, dans aucune piste.",
                    },
                },
                "required": ["intention", "message", "pistes", "aucun_resultat"],
                "additionalProperties": False,
            },
        },
    }
