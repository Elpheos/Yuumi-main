from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
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


# ===========================================================
# 🔹 Widget jour : affiche le nom du jour en gras + champ caché
#    Lecture seule visuellement, mais soumet la valeur au POST.
# ===========================================================

class JourWidget(forms.Widget):
    JOURS_DISPLAY = {
        'lundi': 'Lundi',
        'mardi': 'Mardi',
        'mercredi': 'Mercredi',
        'jeudi': 'Jeudi',
        'vendredi': 'Vendredi',
        'samedi': 'Samedi',
        'dimanche': 'Dimanche',
    }

    def render(self, name, value, attrs=None, renderer=None):
        display = self.JOURS_DISPLAY.get(value, value or '—')
        return mark_safe(
            f'<strong style="line-height:2.4; white-space:nowrap;">{display}</strong>'
            f'<input type="hidden" name="{name}" value="{value or ""}">'
        )

    def value_from_datadict(self, data, files, name):
        return data.get(name)


class OpeningHourAdminForm(forms.ModelForm):
    class Meta:
        model = OpeningHour
        fields = [
            'jour',
            'matin_ouverture',
            'matin_fermeture',
            'apresmidi_ouverture',
            'apresmidi_fermeture',
        ]
        widgets = {
            'jour': JourWidget(),
        }


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


class OpeningHourInline(nested_admin.NestedTabularInline):
    model = OpeningHour
    form = OpeningHourAdminForm
    extra = 0
    max_num = 7
    can_delete = False
    fields = (
        "jour",
        "matin_ouverture",
        "matin_fermeture",
        "apresmidi_ouverture",
        "apresmidi_fermeture",
    )
    verbose_name = "Horaire d'ouverture"
    verbose_name_plural = "Horaires d'ouverture"

    JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

    def get_extra(self, request, obj=None, **kwargs):
        # Sur la page de création (obj=None) : 7 lignes pré-remplies.
        # Sur la page d'édition : 0 extra, on affiche les lignes existantes.
        return 7 if obj is None else 0

    def get_formset(self, request, obj=None, **kwargs):
        formset_class = super().get_formset(request, obj, **kwargs)
        if obj is None:
            formset_class.initial = [{'jour': jour} for jour in self.JOURS]
        return formset_class

class ProductFamilyInline(nested_admin.NestedStackedInline):
    model = ProductFamily
    extra = 1
    inlines = [ProductInline]


# ===========================================================
# 🔹 StoreAdmin
# ===========================================================

@admin.register(Store)
class StoreAdmin(nested_admin.NestedModelAdmin):
    form = StoreForm

    def save_model(self, request, obj, form, change):
        if not change:
            # À la création, l'inline horaires crée les 7 jours lui-même.
            # On désactive la création automatique de Store.save() pour éviter
            # un doublon qui provoquerait une IntegrityError (unique_together).
            obj._skip_opening_hours = True
        super().save_model(request, obj, form, change)

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
