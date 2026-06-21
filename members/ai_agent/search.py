# members/ai_agent/search.py

def find_matching_stores(categories_slugs, departement, ville, limit=15):
    """
    Cherche les commerces reels qui correspondent aux categories extraites
    et a la ville de l'utilisateur.
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


def find_stores_by_product(idees_produits, departement, ville, limit=15):
    """
    Cherche les commerces qui vendent REELLEMENT un produit correspondant
    aux idees generiques extraites par l'IA (ex: "foie gras", "bouquet de
    roses"). Recherche textuelle simple (icontains), exactement comme
    search_product dans views.py.

    C'est cette etape qui garantit qu'on ne propose jamais un commerce
    sur la base d'un produit qu'il ne vend pas reellement - contrairement
    a avant, ou seule la categorie etait verifiee, jamais le produit
    precis mentionne par l'utilisateur.

    Renvoie un queryset Store (distinct, pas de doublons si plusieurs
    produits du meme commerce matchent).
    """
    from members.models import Store, Product
    from django.db.models import Q

    if not idees_produits:
        return Store.objects.none()

    q = Q()
    for idee in idees_produits:
        q |= Q(nom__icontains=idee)

    store_ids = (
        Product.objects
        .filter(q)
        .filter(
            family__store__departement__iexact=departement,
            family__store__ville__iexact=ville,
        )
        .values_list("family__store_id", flat=True)
        .distinct()
    )

    return (
        Store.objects
        .filter(id__in=store_ids)
        .select_related("categorie")
        .order_by("nom")
    )


def combine_store_querysets(*querysets):
    """
    Fusionne plusieurs querysets de Store (categories + produits) en une
    seule liste, sans doublons. Un commerce trouve par categorie ET par
    produit n'apparait qu'une fois.
    """
    seen_ids = set()
    combined = []

    for qs in querysets:
        for store in qs:
            if store.id not in seen_ids:
                seen_ids.add(store.id)
                combined.append(store)

    return combined


def apply_open_now_filter(stores_list, ouvert_maintenant, limit=15):
    """
    Applique le filtre "ouvert maintenant" sur une LISTE Python de Store
    (pas un queryset - voir combine_store_querysets qui renvoie une liste).

    Le filtrage se fait donc en Python via get_opening_status, pas en SQL
    via build_open_now_filter, puisqu'on n'a plus un seul queryset propre
    a filtrer apres la fusion categories + produits.
    """
    if not ouvert_maintenant:
        return stores_list[:limit]

    from members.views import get_opening_status

    ouverts = [
        store for store in stores_list
        if get_opening_status(store).get("is_open") is True
    ]
    return ouverts[:limit]
