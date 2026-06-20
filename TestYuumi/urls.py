# TestYuumi/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
# ── Sitemap ────────────────────────────────────────────────
from django.contrib.sitemaps.views import sitemap
from members.sitemaps import (
    StaticSitemap,
    CitySitemap,
    CategorySitemap,
    SuperCategorySitemap,
    StoreSitemap,
    CategoriesVilleSitemap,
)
# ✅ NOUVEAU — API biométrie
from members.api_views import biometric_token_obtain, biometric_login
sitemaps = {
    "static":            StaticSitemap(),
    "villes":            CitySitemap(),
    "categories":        CategorySitemap(),
    "supercategories":   SuperCategorySitemap(),
    "commerces":         StoreSitemap(),
    "categories_ville":  CategoriesVilleSitemap(),
}
# ───────────────────────────────────────────────────────────
urlpatterns = [
    path("admin-yuumi-7896u/", admin.site.urls),
    path("aide-aux-commerces/", include("yuumi2.urls")),
    path("", include("members.urls")),
    path("login/",  auth_views.LoginView.as_view(template_name="members/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    # ✅ NOUVEAU — Endpoints API biométrie
    # Étape 1 : login classique → obtenir le refresh token JWT
    path("api/token/", biometric_token_obtain, name="api-token"),
    # Étape 2 : login biométrique → échanger le token contre une session
    path("api/biometric-login/", biometric_login, name="api-biometric-login"),
    # Sitemap Google
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
