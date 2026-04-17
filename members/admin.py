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
    extra = 0          # Pas de lignes vides — on pré-remplit via get_queryset
    max_num = 7
    can_delete = False # On ne supprime pas un jour, on laisse les horaires vides
    fields = ("jour_display", "matin_ouverture", "matin_fermeture", "apresmidi_ouverture", "apresmidi_fermeture")
    readonly_fields = ("jour_display",)  # Le jour est affiché en lecture seule
    verbose_name = "Horaire d'ouverture"
    verbose_name_plural = "Horaires d'ouverture"

    def jour_display(self, obj):
        """Affiche le jour en toutes lettres, non modifiable."""
        return obj.get_jour_display() if obj.pk else ""
    jour_display.short_description = "Jour"

class ProductFamilyInline(nested_admin.NestedStackedInline):
    model = ProductFamily
    extra = 1
    inlines = [ProductInline]


@admin.register(Store)

class StoreAdmin(nested_admin.NestedModelAdmin):
    form = StoreForm

    def get_object(self, request, object_id, from_field=None):
        """Pré-remplit les 7 jours d'horaires si le commerce n'en a pas encore."""
        obj = super().get_object(request, object_id, from_field)
        if obj:
            jours_existants = set(
                OpeningHour.objects.filter(store=obj).values_list('jour', flat=True)
            )
            jours_semaine = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
            for jour in jours_semaine:
                if jour not in jours_existants:
                    OpeningHour.objects.create(store=obj, jour=jour)
        return obj
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
