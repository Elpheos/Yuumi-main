from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from dal import autocomplete  # ✅ Ajout important
from .models import Store, ProductFamily, Product


# -------------------------------
# Formulaire famille
class ProductFamilyForm(forms.ModelForm):
    class Meta:
        model = ProductFamily
        fields = ['nom']


# Formulaire produit
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['nom']


# Formset pour gérer les produits d'une famille
ProductFormSet = inlineformset_factory(
    ProductFamily, Product, form=ProductForm, extra=1, can_delete=True
)

# Formset pour gérer les familles d'un store
FamilyFormSet = inlineformset_factory(
    Store, ProductFamily, form=ProductFamilyForm, extra=1, can_delete=True
)


# -------------------------------
# Formulaire d'inscription commerçant
class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


# -------------------------------
# Formulaire principal de commerce avec autocomplétion
class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = [
            "nom", "ville", "departement", "categorie", "descriptiongrande",
            "descriptionpetite", "addressemaps", "addresseitineraire",
            "site", "phone", "instagram", "facebook", "photo"
        ]
        widgets = {
            'departement': autocomplete.ListSelect2(
                url='departement-autocomplete',
                attrs={
                    'data-placeholder': 'Commencez à taper un département...',
                    'data-tags': 'true',  # ✅ création libre
                }
            ),
            'ville': autocomplete.ListSelect2(
                url='ville-autocomplete',
                forward=['departement'],  # ✅ filtre dynamique selon le département choisi
                attrs={
                    'data-placeholder': 'Tapez ou choisissez une ville...',
                    'data-tags': 'true',  # ✅ création libre
                }
            ),
            'categorie': autocomplete.ListSelect2(
                url='categorie-autocomplete',
                attrs={
                    'data-placeholder': 'Type de commerce (nouveau ou existant)...',
                    'data-tags': 'true',  # ✅ création libre
                }
            ),
        }

