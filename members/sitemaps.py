# members/sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Store, Category, SuperCategory


# ============================================================
# 1. Pages statiques (accueil, contact, CGU…)
# ============================================================

class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return [
            "main",
            "notre_projet",
            "contact",
            "cgu",
            "cookies_policy",
            "mentions_legales",
            "changer_ville",
        ]

    def location(self, item):
        return reverse(item)


# ============================================================
# 2. Pages ville  →  /<dep>/<ville>/tous-les-commerces/
# ============================================================

class CitySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        # Retourne des tuples (departement, ville) distincts
        combos = (
            Store.objects
            .values_list("departement", "ville")
            .distinct()
            .order_by("departement", "ville")
        )
        return list(combos)

    def location(self, item):
        departement, ville = item
        return reverse("stores", args=[departement, ville])


# ============================================================
# 3. Pages catégorie  →  /<dep>/<ville>/categorie/<slug>/
# ============================================================

class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        # Toutes les combinaisons (departement, ville, categorie.slug) existantes
        combos = set()
        qs = (
            Store.objects
            .select_related("categorie")
            .exclude(categorie=None)
            .values_list("departement", "ville", "categorie__slug")
        )
        for dep, ville, cat_slug in qs:
            if cat_slug:
                combos.add((dep, ville, cat_slug))
        return sorted(combos)

    def location(self, item):
        departement, ville, cat_slug = item
        return reverse("by_category", args=[departement, ville, cat_slug])


# ============================================================
# 4. Pages super-catégorie  →  /<dep>/<ville>/super/<slug>/
# ============================================================

class SuperCategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        # Toutes les combinaisons (departement, ville, super_categorie.slug)
        combos = set()
        qs = (
            Store.objects
            .select_related("categorie__super_categorie")
            .exclude(categorie=None)
            .exclude(categorie__super_categorie=None)
            .values_list("departement", "ville", "categorie__super_categorie__slug")
        )
        for dep, ville, super_slug in qs:
            if super_slug:
                combos.add((dep, ville, super_slug))
        return sorted(combos)

    def location(self, item):
        departement, ville, super_slug = item
        return reverse("by_super_category", args=[departement, ville, super_slug])


# ============================================================
# 5. Pages de détail des commerces  →  /<dep>/<ville>/<slug>/
# ============================================================

class StoreSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Store.objects.all().order_by("departement", "ville", "slug")

    def location(self, obj):
        # Utilise get_absolute_url() défini sur le modèle Store
        return obj.get_absolute_url()
