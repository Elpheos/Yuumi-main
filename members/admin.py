from django.contrib import admin
from django.utils.html import format_html
from .models import CityCategoryHighlight, CityCategoryItem

import nested_admin

from .models import (
    Store,
    StoreImage,
    ProductFamily,
    Product,
    OpeningHour,
    Category,
    SuperCategory,
)
from .forms import StoreForm


# 🔹 Images supplémentaires
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


# 🔹 Produits
class ProductInline(nested_admin.NestedTabularInline):
    model = Product
    extra = 1

class OpeningHourInline(nested_admin.NestedTabularInline):
    model = OpeningHour
    extra = 7
    max_num = 7
    fields = ("jour", "matin_ouverture", "matin_fermeture", "apresmidi_ouverture", "apresmidi_fermeture")
    verbose_name = "Horaire d'ouverture"
    verbose_name_plural = "Horaires d'ouverture"

class ProductFamilyInline(nested_admin.NestedStackedInline):
    model = ProductFamily
    extra = 1
    inlines = [ProductInline]


@admin.register(Store)

class StoreAdmin(nested_admin.NestedModelAdmin):
    form = StoreForm
    list_display = (
        "nom",
        "ville",
        "departement",
        "phone",
        "photo_preview",
        "owner",
    )
    search_fields = ("nom", "ville", "departement")
    list_filter = ("ville", "departement")
    fields = (
        "nom",
        "ville",
        "departement",
        "categorie",    
        "descriptionpetite",
        "descriptiongrande",
        "addressemaps",
        "addresseitineraire",
        "site",
        "phone",
        "instagram",
        "facebook",
        "photo",
        "galerie_title",
        "galerie_description",
        "galerie_image",
        "slug",
        "owner",
    )
    inlines = [
        StoreImageInline,
        ProductFamilyInline,
        OpeningHourInline,
    ]
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius:5px;" />',
                obj.photo.url
            )
        return ""
    photo_preview.short_description = "Photo principale"


@admin.register(ProductFamily)
class ProductFamilyAdmin(admin.ModelAdmin):
    list_display = ("nom", "store")
    search_fields = ("nom", "store__nom")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("nom", "family")
    search_fields = ("nom",)
    list_filter = ("family",)

# 🔹 Super catégories
@admin.register(SuperCategory)
class SuperCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


# 🔹 Catégories
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

