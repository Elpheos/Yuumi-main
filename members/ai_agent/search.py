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

    IMPORTANT : ne decoupe PAS le queryset ici (pas de [:limit]) - le
    decoupage se fait uniquement dans apply_open_now_filter, a la toute
    fin de la chaine, car Django interdit d'ajouter un .filter() sur un
    queryset deja decoupe.
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
        .order_by("nom")
    )

    return queryset


def apply_open_now_filter(queryset, ouvert_maintenant, limit=15):
    """
    Applique le filtre "ouvert maintenant" si l'IA l'a detecte, PUIS
    decoupe le resultat a limit elements - toujours dans cet ordre.
    """
    if ouvert_maintenant:
        from members.views import build_open_now_filter
        queryset = queryset.filter(build_open_now_filter())

    return queryset[:limit]
