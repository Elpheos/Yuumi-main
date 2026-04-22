from django.urls import path
from django.views.generic import TemplateView
from . import views
from . import autocomplete

urlpatterns = [
    path("", views.main, name="main"),

    # robots.txt
    path("robots.txt", TemplateView.as_view(
        template_name="robots.txt",
        content_type="text/plain"
    ), name="robots"),

    # Suggestions de modification et de nouveaux commerces
    path("suggestion/nouveau/", views.suggest_new_store, name="suggest-new-store"),
    path("store/<int:store_id>/suggestion/", views.suggest_modif_store, name="suggest-modif-store"),

    # Favoris / actions
    path("store/<int:store_id>/favoris/", views.toggle_favoris, name="toggle-favoris"),
    path("store/<int:store_id>/claim/", views.claim_store, name="claim-store"),
    path("store/<int:store_id>/click/", views.track_click, name="track-click"),
    path("mes-favoris/", views.my_favorites, name="my-favorites"),
    path("changer-de-ville/", views.changer_ville, name="changer_ville"),

    # Recherche / carte
    path("search-product/", views.search_product, name="search-product"),
    path("carte/<str:departement>/", views.map_view, name="map-view"),

    # Auth — login/logout définis dans TestYuumi/urls.py uniquement
    path("register/", views.register, name="register"),
    path("mon-compte/", views.account, name="account"),

    # Pages informatives
    path("contact/", views.contact, name="contact"),
    path("notre-projet/", views.notre_projet, name="notre_projet"),
    path("cgu/", views.cgu, name="cgu"),
    path("cookies/", views.cookies_policy, name="cookies_policy"),
    path("mentions-legales/", views.mentions_legales, name="mentions_legales"),

    # Autocomplete
    path("departement-autocomplete/", autocomplete.DepartementAutocomplete.as_view(), name="departement-autocomplete"),
    path("ville-autocomplete/", autocomplete.VilleAutocomplete.as_view(), name="ville-autocomplete"),
    path("categorie-autocomplete/", autocomplete.CategorieAutocomplete.as_view(), name="categorie-autocomplete"),

    # EDIT doit être avant store_details pour éviter les conflits de pattern
    path("<str:departement>/<str:ville>/<slug:slug>/edit/", views.edit_store, name="edit_store"),

    # Pages commerce
    path("<str:departement>/<str:ville>/tous-les-commerces/", views.stores, name="stores"),
    path("<str:departement>/<str:ville>/categorie/<str:category>/", views.by_category, name="by_category"),
    path("<str:departement>/<str:ville>/categories/", views.categories_ville, name="categories_ville"),
    path("<str:departement>/<str:ville>/super/<slug:super_slug>/", views.by_super_category, name="by_super_category"),

    # store_details en dernier — pattern le plus générique
    path("<str:departement>/<str:ville>/<slug:slug>/", views.store_details, name="store_details"),


    
]
