from django.contrib import admin
from django.utils.html import format_html
from .models import CityCategoryHighlight, CityCategoryItem, PageView

import nested_admin

from .models import (
    Store,
    StoreImage,
    ProductFamily,
    Product,
    Category,
    SuperCategory,
    StoreGalerieImage,
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
# 🔹 StoreAdmin
# ===========================================================

@admin.register(Store)
class StoreAdmin(nested_admin.NestedModelAdmin):
    form = StoreForm

    list_display = (
        "nom",
        "ville",
        "ville_precise",
        "departement",
        "phone",
        "photo_preview",
        "owner",
    )
    search_fields = ("nom", "ville", "departement")
    list_filter = ("ville", "departement")
    fieldsets = (
        ("Informations générales", {
            "fields": (
                "nom", "ville","ville_precise", "departement", "categorie",
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
    
@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ("page", "store", "ip_address", "timestamp")
    list_filter = ("store",)
