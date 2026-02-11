# members/context_processors.py

from urllib.parse import unquote
from .models import Store, Category, SuperCategory


def menu_context(request):
    """
    Fournit :
    - menu_categories : catégories fines (compatibilité)
    - menu_supercategories : super catégories → sous-catégories
    - menu_departement / menu_ville : emplacement actuel
    """

    # Découpe du chemin
    path_parts = [unquote(p) for p in request.path.strip("/").split("/") if p]

    departement = ""
    ville = ""
    categories = []

    # Départements existants
    deps = set(Store.objects.values_list("departement", flat=True).distinct())

    # Cas : /carte/<departement>/
    if len(path_parts) >= 2 and path_parts[0] == "carte" and path_parts[1] in deps:
        departement = path_parts[1]

    # Cas : /<departement>/<ville>/...
    elif len(path_parts) >= 2 and path_parts[0] in deps:
        departement = path_parts[0]
        ville = path_parts[1]

    # -----------------------------------------
    # 📌 Récupération des commerces concernés
    # -----------------------------------------
    qs = Store.objects.none()

    if departement and ville:
        qs = Store.objects.filter(
            departement__iexact=departement,
            ville__iexact=ville
        )
    elif departement:
        qs = Store.objects.filter(
            departement__iexact=departement
        )

    # -----------------------------------------
    # 📌 menu_categories (compatibilité)
    # -----------------------------------------
    if qs.exists():
        categories = list(
            qs.values_list("categorie__name", flat=True).distinct()
        )
        categories = [c for c in categories if c]

    # -----------------------------------------
    # 📌 menu_supercategories (100% dynamique)
    # -----------------------------------------
    menu_supercategories = {}

    # On initialise toutes les super catégories existantes
    for super_cat in SuperCategory.objects.all():
        menu_supercategories[super_cat.name] = []

    # On remplit avec les catégories réellement présentes
    for store in qs.select_related("categorie__super_categorie"):
        if not store.categorie or not store.categorie.super_categorie:
            continue

        super_cat = store.categorie.super_categorie

        if store.categorie not in menu_supercategories[super_cat.name]:
            menu_supercategories[super_cat.name].append(store.categorie)

    return {
        "menu_categories": categories,
        "menu_supercategories": menu_supercategories,
        "menu_departement": departement,
        "menu_ville": ville,
    }
