# members/ai_agent/search.py
#
# Cette etape n'utilise AUCUNE IA - c'est de la recherche Django classique,
# exactement comme search_product ou by_category dans views.py. Elle prend
# les categories/produits extraits par l'IA (etape precedente) et la ville
# de l'utilisateur, et renvoie les VRAIS commerces qui correspondent.

MAX_CANDIDATES_TO_LLM = 30
# Plafond raisonnable de candidats envoyes au modele, pour limiter le cout
# en tokens. Au-dela de ce nombre, on tronque - mais l'IA elle-meme n'a
# AUCUNE limite sur le nombre de resultats qu'elle peut recommander parmi
# ces candidats : si les 30 sont pertinents, elle peut les recommander
# tous. Le plafond porte sur l'ENTREE (cout), jamais sur la SORTIE
# (pertinence pour l'utilisateur).


def _ordonner_par_pertinence(queryset):
    """
    Trie un queryset Store par signal d'engagement (nombre de clics) puis par
    nom. AVANT, le tri etait purement alphabetique : dans une categorie dense,
    seuls les commerces en "A-B-C" remontaient sous le plafond de 30, et les
    plus pertinents pouvaient etre tronques avant meme d'atteindre l'IA.

    On utilise les clics (intention reelle : itineraire, appel, site...) comme
    proxy de qualite/popularite. distinct=True evite la multiplication de
    lignes due a la jointure.
    """
    from django.db.models import Count

    return (
        queryset
        .annotate(nb_clics=Count("clicks", distinct=True))
        .order_by("-nb_clics", "nom")
    )


def _filtrer_ouvert_maintenant(queryset, ouvert_maintenant):
    """
    Applique le filtre "ouvert maintenant" EN SQL, sur le queryset, AVANT tout
    plafonnement. C'est le correctif du bug "filtrage apres plafond" : avant,
    on plafonnait a 30 candidats (alphabetiques) PUIS on filtrait en Python via
    apply_open_now_filter - donc si les 30 premiers etaient fermes, l'utilisateur
    obtenait "aucun resultat" alors qu'un commerce ouvert existait en 31e
    position. Ici, on filtre d'abord, on plafonne ensuite.

    Import tardif de build_open_now_filter pour eviter l'import circulaire
    (views.py importe deja ce module au niveau module).
    """
    if not ouvert_maintenant:
        return queryset

    from members.views import build_open_now_filter

    return queryset.filter(build_open_now_filter())


def find_matching_stores(categories_slugs, departement, ville,
                         ouvert_maintenant=False, limit=MAX_CANDIDATES_TO_LLM):
    """
    Cherche les commerces reels qui correspondent aux categories extraites
    et a la ville de l'utilisateur.

    IMPORTANT : ne decoupe PAS le queryset ici (pas de [:limit]) - le
    decoupage se fait uniquement dans combine_store_querysets, a la toute
    fin de la chaine. Le filtre "ouvert maintenant" est applique ICI, en SQL,
    AVANT ce decoupage.
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
    )

    queryset = _filtrer_ouvert_maintenant(queryset, ouvert_maintenant)
    return _ordonner_par_pertinence(queryset)


def find_stores_by_product(idees_produits, departement, ville,
                           ouvert_maintenant=False):
    """
    Cherche les commerces qui vendent REELLEMENT un produit correspondant
    aux idees generiques extraites par l'IA (ex: "foie gras", "bouquet de
    roses"). C'est le tier CONFIRME : ces commerces seront marques [CONFIRME]
    dans le prompt de recommandation.

    Match elargi (correctif "plafond de qualite") : on matche desormais sur
    le nom du produit ET sur le nom de sa famille de produits (ProductFamily),
    pas seulement Product.nom. Un commerce ayant une famille "Foies gras &
    terrines" ressort donc, meme si aucun produit unitaire ne s'appelle
    exactement "foie gras". Les deux sont des declarations de catalogue du
    commercant, donc un signal fort (= confirme).

    Renvoie un queryset Store (distinct, pas de doublons si plusieurs
    produits/familles du meme commerce matchent).
    """
    from members.models import Store, Product
    from django.db.models import Q

    if not idees_produits:
        return Store.objects.none()

    q = Q()
    for idee in idees_produits:
        q |= Q(nom__icontains=idee) | Q(family__nom__icontains=idee)

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

    queryset = (
        Store.objects
        .filter(id__in=store_ids)
        .select_related("categorie")
    )

    queryset = _filtrer_ouvert_maintenant(queryset, ouvert_maintenant)
    return _ordonner_par_pertinence(queryset)


def find_stores_by_description(idees_produits, departement, ville,
                               ouvert_maintenant=False):
    """
    Tier intermediaire (correctif "elargir le match") : commerces dont la
    DESCRIPTION (petite ou grande) mentionne explicitement le produit demande,
    sans qu'il existe forcement une entree catalogue dediee.

    Un commerce dont la fiche dit "epicerie fine proposant foie gras, vins et
    fromages" est un candidat legitime, meme sans Product "foie gras" en base.
    C'est un signal plus faible que le catalogue (Product/ProductFamily), donc
    ces commerces NE sont PAS marques [CONFIRME] : l'IA les presentera en
    "deduit", en s'appuyant sur la description.

    Renvoie un queryset Store.
    """
    from members.models import Store
    from django.db.models import Q

    if not idees_produits:
        return Store.objects.none()

    q = Q()
    for idee in idees_produits:
        q |= Q(descriptionpetite__icontains=idee) | Q(descriptiongrande__icontains=idee)

    queryset = (
        Store.objects
        .filter(q, departement__iexact=departement, ville__iexact=ville)
        .select_related("categorie")
    )

    queryset = _filtrer_ouvert_maintenant(queryset, ouvert_maintenant)
    return _ordonner_par_pertinence(queryset)


def combine_store_querysets(*querysets, limit=MAX_CANDIDATES_TO_LLM):
    """
    Fusionne plusieurs querysets de Store en une seule liste, sans doublons.
    Un commerce trouve par plusieurs voies (catalogue + description, par ex.)
    n'apparait qu'une fois, et garde la position de sa PREMIERE apparition -
    d'ou l'importance de l'ordre des arguments (passer les querysets les plus
    fiables en premier).

    Le plafond limit s'applique ICI, sur le nombre de candidats envoyes a
    l'IA (cout en tokens) - jamais sur le nombre de resultats que l'IA peut
    recommander parmi eux.
    """
    seen_ids = set()
    combined = []

    for qs in querysets:
        for store in qs:
            if store.id not in seen_ids:
                seen_ids.add(store.id)
                combined.append(store)
            if len(combined) >= limit:
                return combined

    return combined


def apply_open_now_filter(stores_list, ouvert_maintenant):
    """
    OBSOLETE depuis le passage du filtrage "ouvert maintenant" en SQL
    (_filtrer_ouvert_maintenant, applique AVANT le plafonnement dans chaque
    fonction de recherche). Conservee uniquement pour compatibilite si elle
    est encore appelee ailleurs. Ne plus l'utiliser dans le pipeline de l'agent
    IA : filtrer une liste DEJA plafonnee a 30 reintroduit le bug d'origine.
    """
    if not ouvert_maintenant:
        return stores_list

    from members.views import get_opening_status

    return [
        store for store in stores_list
        if get_opening_status(store).get("is_open") is True
    ]
