from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from . import autocomplete 

urlpatterns = [
    path('', views.main, name='main'),

    # Favoris / actions
    path('store/<int:store_id>/favoris/', views.toggle_favoris, name='toggle-favoris'),
    path('store/<int:store_id>/claim/', views.claim_store, name='claim-store'),
    path('mes-favoris/', views.my_favorites, name='my-favorites'),

    # Recherche / carte
    path('search-product/', views.search_product, name='search-product'),
    path('carte/<str:departement>/', views.map_view, name='map-view'),

    # Auth
    path("login/", auth_views.LoginView.as_view(template_name="members/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="main"), name="logout"),
    path("register/", views.register, name='register'),
    path("mon-compte/", views.account, name="account"),

    # Pages informatives
    path("a-propos/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("notre-projet/", views.notre_projet, name="notre_projet"),
    path("cgu/", views.cgu, name="cgu"),
    path("cookies/", views.cookies_policy, name="cookies_policy"),
    path("mentions-legales/", views.mentions_legales, name="mentions_legales"),

    # Autocomplete
    path('departement-autocomplete/', autocomplete.DepartementAutocomplete.as_view(), name='departement-autocomplete'),
    path('ville-autocomplete/', autocomplete.VilleAutocomplete.as_view(), name='ville-autocomplete'),
    path('categorie-autocomplete/', autocomplete.CategorieAutocomplete.as_view(), name='categorie-autocomplete'),

    # 🚨 EDIT DOIT ÊTRE AVANT store_details
    path(
        "<str:departement>/<str:ville>/<slug:slug>/edit/",
        views.edit_store,
        name="edit_store"
    ),

    # Pages commerce
    path('<str:departement>/<str:ville>/tous-les-commerces/', views.stores, name='stores'),
    path('<str:departement>/<str:ville>/categorie/<str:category>/', views.by_category, name='by_category'),
    path('<str:departement>/<str:ville>/categories/', views.categories_ville, name='categories_ville'),
    path('<str:departement>/<str:ville>/<slug:slug>/', views.store_details, name='store_details'),
]

