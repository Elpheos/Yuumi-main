import unicodedata
from urllib.parse import unquote
from .models import Store, Category, SuperCategory

def menu_context(request):
    """
    Fournit :
    - menu_categories : catégories fines (compatibilité)
    - menu_supercategories : super catégories → sous-catégories
    - menu_departement / menu_ville : emplacement actuel

    Si l'URL ne contient pas de ville (pages neutres comme /notre-projet/,
    /mes-favoris/, etc.), on utilise les cookies yuumi_departement et
    yuumi_ville comme fallback pour maintenir le contexte de navigation.
    """
    # Découpe du chemin
    path_parts = [unquote(p) for p in request.path.strip("/").split("/") if p]

    departement = ""
    ville = ""
    categories = []

    # Départements existants — clé lowercase, valeur réelle en base
    deps_map = {
        d.lower(): d
        for d in Store.objects.values_list("departement", flat=True).distinct()
    }

    # Cas : /carte/<departement>/
    if len(path_parts) >= 2 and path_parts[0] == "carte" and path_parts[1] in deps_map:
        departement = deps_map[path_parts[1]]

    # Cas : /<departement>/<ville>/...
    elif len(path_parts) >= 2 and path_parts[0] in deps_map:
        departement = deps_map[path_parts[0]]
        villes_map = {
            v.lower(): v
            for v in Store.objects.filter(
                departement=departement
            ).values_list("ville", flat=True).distinct()
        }
        ville = villes_map.get(path_parts[1], path_parts[1])

    # -------------------------------------------------------
    # 🍪 Fallback cookie : si l'URL ne contient pas de ville,
    # on récupère la dernière ville visitée depuis le cookie.
    # -------------------------------------------------------
    if not ville:
        cookie_dep   = request.COOKIES.get("yuumi_departement", "")
        cookie_ville = request.COOKIES.get("yuumi_ville", "")
        if cookie_dep.lower() in deps_map and cookie_ville:
            departement = deps_map[cookie_dep.lower()]
            ville = cookie_ville

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
for super_cat in SuperCategory.objects.all():
    menu_supercategories[super_cat.name] = {
        "items": []
    }
for store in qs.select_related("categorie__super_categorie", "categorie__categorie_intermediaire"):
    if not store.categorie or not store.categorie.super_categorie:
        continue
    super_cat = store.categorie.super_categorie
    cat_inter = store.categorie.categorie_intermediaire
    
    if cat_inter:
        # Vérifier si l'intermédiaire est déjà dans la liste
        existing = next((i for i in menu_supercategories[super_cat.name]["items"] if i.get("type") == "inter" and i["obj"] == cat_inter), None)
        if not existing:
            menu_supercategories[super_cat.name]["items"].append({
                "type": "inter",
                "obj": cat_inter,
                "name": cat_inter.name,
                "cats": []
            })
            existing = menu_supercategories[super_cat.name]["items"][-1]
        if store.categorie not in existing["cats"]:
            existing["cats"].append(store.categorie)
    else:
        existing = next((i for i in menu_supercategories[super_cat.name]["items"] if i.get("type") == "direct" and i["obj"] == store.categorie), None)
        if not existing:
            menu_supercategories[super_cat.name]["items"].append({
                "type": "direct",
                "obj": store.categorie,
                "name": store.categorie.name,
            })

# Tri alphabétique
for super_cat_name in menu_supercategories:
    menu_supercategories[super_cat_name]["items"].sort(
        key=lambda x: unicodedata.normalize("NFD", x["name"].lower()).encode("ascii", "ignore").decode()
    )
