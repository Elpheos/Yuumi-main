from django.contrib import admin
from django.utils.html import format_html
import nested_admin
from .models import Store, ProductFamily, Product, StoreImage
from .forms import StoreForm  # formulaire DAL


# 🔹 Inline pour les images supplémentaires du commerce
class StoreImageInline(nested_admin.NestedTabularInline):
    model = StoreImage
    extra = 1
    fields = ("image", "image_preview")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="70" height="70" style="object-fit: cover; border-radius: 5px;" />',
                obj.image.url
            )
        return ""
    image_preview.short_description = "Aperçu"


# 🔹 Inline pour les produits
class ProductInline(nested_admin.NestedTabularInline):
    model = Product
    extra = 1
    show_change_link = True


# 🔹 Inline pour les familles de produits
class ProductFamilyInline(nested_admin.NestedStackedInline):
    model = ProductFamily
    extra = 1
    show_change_link = True
    inlines = [ProductInline]


# 🔹 Admin du Store avec tout intégré + autocomplétion
@admin.register(Store)
class StoreAdmin(nested_admin.NestedModelAdmin):
    form = StoreForm  # DAL autocomplete

    list_display = ("nom", "ville", "departement", "phone", "photo_preview", "owner")
    search_fields = ("nom", "ville", "departement")
    list_filter = ("ville", "departement")

    # ⭐⭐ CHAMP SUPER_CATÉGORIE AJOUTÉ ICI ⭐⭐
    fields = (
        "nom",
        "ville",
        "departement",
        "categorie",
        "super_categorie",   # ⭐ AJOUT ESSENTIEL
        "descriptiongrande",
        "descriptionpetite",
        "addressemaps",
        "addresseitineraire",
        "site",
        "phone",
        "instagram",
        "facebook",
        "photo",
        "slug",
        "owner",
    )

    inlines = [StoreImageInline, ProductFamilyInline]

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                obj.photo.url
            )
        return ""
    photo_preview.short_description = 'Photo principale'


# 🔹 Admin ProductFamily
@admin.register(ProductFamily)
class ProductFamilyAdmin(admin.ModelAdmin):
    list_display = ("nom", "store")
    search_fields = ("nom", "store__nom")


# 🔹 Admin Product
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("nom", "family")
    list_filter = ("family",)
    search_fields = ("nom",)
