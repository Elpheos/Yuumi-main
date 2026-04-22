from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q

import nested_admin

from .models import (
    Store,
    StoreImage,
    ProductFamily,
    Product,
    Category,
    SuperCategory,
    StoreGalerieImage,
    CityCategoryHighlight,
    CityCategoryItem,
    PageView,
    StoreStats,
    StoreClickStats,
    Click,
    StoreSuggestion,
)

from .forms import StoreForm


# ===========================================================
# 🔹 Inlines
# ===========================================================

class StoreImageInline(nested_admin.NestedTabularInline):
    model = StoreImage
    extra = 1
    readonly_fields = ("image_preview",)
    fields = ("image", "image_preview")

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="70" height="70" style="object-fit: cover; border-radius:5px;" />',
                obj.image.url
            )
        return ""


class ProductInline(nested_admin.NestedTabularInline):
    model = Product
    extra = 1


class ProductFamilyInline(nested_admin.NestedStackedInline):
    model = ProductFamily
    extra = 1
    inlines = [ProductInline]


class StoreGalerieImageInline(nested_admin.NestedTabularInline):
    model = StoreGalerieImage
    extra = 1
    readonly_fields = ("image_preview",)
    fields = ("image", "image_preview")

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="70" height="70" style="object-fit: cover; border-radius:5px;" />',
                obj.image.url
            )
        return ""


# ===========================================================
# 🔹 StoreAdmin (édition classique)
# ===========================================================

@admin.register(Store)
class StoreAdmin(nested_admin.NestedModelAdmin):
    form = StoreForm

    list_display = (
        "nom",
        "ville",
        "categorie",
        "photo_preview",
        "owner",
    )

    search_fields = ("nom", "ville", "departement")

    list_filter = (
        "categorie",
        "categorie__super_categorie",
        "ville",
        "departement",
    )

    fieldsets = (
        ("Informations générales", {
            "fields": (
                "nom", "ville", "ville_precise", "departement", "categorie",
                "descriptionpetite", "descriptiongrande",
                "addressemaps", "addresseitineraire",
                "site", "phone", "instagram", "facebook",
                "photo", "slug", "owner",
            )
        }),
        ("Lundi", {"fields": (("lundi_matin_ouverture", "lundi_matin_fermeture", "lundi_apresmidi_ouverture", "lundi_apresmidi_fermeture"),)}),
        ("Mardi", {"fields": (("mardi_matin_ouverture", "mardi_matin_fermeture", "mardi_apresmidi_ouverture", "mardi_apresmidi_fermeture"),)}),
        ("Mercredi", {"fields": (("mercredi_matin_ouverture", "mercredi_matin_fermeture", "mercredi_apresmidi_ouverture", "mercredi_apresmidi_fermeture"),)}),
        ("Jeudi", {"fields": (("jeudi_matin_ouverture", "jeudi_matin_fermeture", "jeudi_apresmidi_ouverture", "jeudi_apresmidi_fermeture"),)}),
        ("Vendredi", {"fields": (("vendredi_matin_ouverture", "vendredi_matin_fermeture", "vendredi_apresmidi_ouverture", "vendredi_apresmidi_fermeture"),)}),
        ("Samedi", {"fields": (("samedi_matin_ouverture", "samedi_matin_fermeture", "samedi_apresmidi_ouverture", "samedi_apresmidi_fermeture"),)}),
        ("Dimanche", {"fields": (("dimanche_matin_ouverture", "dimanche_matin_fermeture", "dimanche_apresmidi_ouverture", "dimanche_apresmidi_fermeture"),)}),
    )

    inlines = [
        StoreImageInline,
        ProductFamilyInline,
        StoreGalerieImageInline,
    ]

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius:5px;" />',
                obj.photo.url
            )
        return ""
    photo_preview.short_description = "Photo principale"

    class Media:
        js = ("copy_horaires.js",)


# ===========================================================
# 🔹 Statistiques vues (ONGLET DÉDIÉ)
# ===========================================================

@admin.register(StoreStats)
class StoreStatsAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "ville",
        "categorie",
        "total_views",
        "views_last_24h",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_views_count=Count("pageviews"),
            views_24h_count=Count(
                "pageviews",
                filter=Q(
                    pageviews__timestamp__gte=timezone.now() - timedelta(hours=24)
                )
            )
        )

    def total_views(self, obj):
        return obj.total_views_count
    total_views.admin_order_field = "total_views_count"

    def views_last_24h(self, obj):
        return obj.views_24h_count
    views_last_24h.admin_order_field = "views_24h_count"


# ===========================================================
# 🔹 Statistiques clics (ONGLET DÉDIÉ)
# ===========================================================

@admin.register(StoreClickStats)
class StoreClickStatsAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "ville",
        "categorie",
        "clicks_itineraire",
        "clicks_site",
        "clicks_instagram",
        "clicks_facebook",
    )

    search_fields = ("nom", "ville")
    list_filter = ("categorie__super_categorie", "categorie")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            c_itineraire=Count("clicks", filter=Q(clicks__type_click="itineraire")),
            c_site=Count("clicks", filter=Q(clicks__type_click="site")),
            c_instagram=Count("clicks", filter=Q(clicks__type_click="instagram")),
            c_facebook=Count("clicks", filter=Q(clicks__type_click="facebook")),
        )

    def clicks_itineraire(self, obj):
        return obj.c_itineraire
    clicks_itineraire.short_description = "Itinéraire"
    clicks_itineraire.admin_order_field = "c_itineraire"

    def clicks_site(self, obj):
        return obj.c_site
    clicks_site.short_description = "Site web"
    clicks_site.admin_order_field = "c_site"

    def clicks_instagram(self, obj):
        return obj.c_instagram
    clicks_instagram.short_description = "Instagram"
    clicks_instagram.admin_order_field = "c_instagram"

    def clicks_facebook(self, obj):
        return obj.c_facebook
    clicks_facebook.short_description = "Facebook"
    clicks_facebook.admin_order_field = "c_facebook"


# ===========================================================
# 🔹 Autres admins
# ===========================================================

@admin.register(ProductFamily)
class ProductFamilyAdmin(admin.ModelAdmin):
    list_display = ("nom", "store")
    search_fields = ("nom", "store__nom")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("nom", "family")
    search_fields = ("nom",)
    list_filter = ("family",)


@admin.register(SuperCategory)
class SuperCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "super_categorie")
    list_filter = ("super_categorie",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class CityCategoryItemInline(admin.TabularInline):
    model = CityCategoryItem
    extra = 1


@admin.register(CityCategoryHighlight)
class CityCategoryHighlightAdmin(admin.ModelAdmin):
    list_display = ("ville", "departement")
    search_fields = ("ville", "departement")
    inlines = [CityCategoryItemInline]


@admin.register(StoreSuggestion)
class StoreSuggestionAdmin(admin.ModelAdmin):
    list_display = ("type_suggestion", "nom", "ville", "statut", "created_at", "store")
    list_filter = ("statut", "type_suggestion")

