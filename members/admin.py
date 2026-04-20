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
# 🔹 Statistiques (ONGLET DÉDIÉ)
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
