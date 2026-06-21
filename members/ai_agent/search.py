# members/ai_agent/search.py
#
# Cette etape n'utilise AUCUNE IA - c'est de la recherche Django classique,
# exactement comme search_product ou by_category dans views.py. Elle prend
# les categories extraites par l'IA (etape precedente) et la ville de
# l'utilisateur, et renvoie les VRAIS commerces qui correspondent.


def find_matching_stores(categories_slugs, departement, ville, limit=15):
    """
    Cherche les commerces reels qui correspondent aux categories extraites
    et a la ville de l'utilisateur.

    categories_slugs : liste de slugs de categories (ex: ["restaurants-francais", "cafes"])
    departement, ville : contexte de navigation de l'utilisateur, jamais
        fourni par l'IA elle-meme (voir la discussion sur ce point - la
        ville vient toujours du cookie/URL, pas d'une devinette de l'IA).
    limit : nombre maximum de commerces renvoyes, pour ne pas surcharger
        le prompt du prochain appel IA si jamais une categorie tres large
        remonte des centaines de resultats.

    Renvoie un queryset Store, avec categorie deja prechargee
    (select_related) pour eviter les requetes SQL en cascade dans une
    boucle d'affichage.
    """
    from members.models import Store

    if not categories_slugs:
        return Store.objects.none()

    queryset = (
        Store.objects
        .filter(
            categorie__slug__in=categories_slugs,
            departement__iexact=departement,
            ville__iexact=ville,
        )
        .select_related("categorie")
        .order_by("nom")[:limit]
    )

    return queryset


def apply_open_now_filter(queryset, ouvert_maintenant):
    """
    Applique le filtre "ouvert maintenant" si l'IA l'a detecte dans la
    requete utilisateur. Reutilise build_open_now_filter deja existante
    dans views.py, pour ne pas dupliquer cette logique.
    """
    if not ouvert_maintenant:
        return queryset

    from members.views import build_open_now_filter
    return queryset.filter(build_open_now_filter())
