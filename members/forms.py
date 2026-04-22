from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from dal import autocomplete
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
            'nom',
            'categorie',
            'descriptionpetite',
            'descriptiongrande',
            'site',
            'phone',
            'instagram',
            'facebook',
            'addresseitineraire',
            'photo',
            # Horaires
            'lundi_matin_ouverture', 'lundi_matin_fermeture', 'lundi_apresmidi_ouverture', 'lundi_apresmidi_fermeture',
            'mardi_matin_ouverture', 'mardi_matin_fermeture', 'mardi_apresmidi_ouverture', 'mardi_apresmidi_fermeture',
            'mercredi_matin_ouverture', 'mercredi_matin_fermeture', 'mercredi_apresmidi_ouverture', 'mercredi_apresmidi_fermeture',
            'jeudi_matin_ouverture', 'jeudi_matin_fermeture', 'jeudi_apresmidi_ouverture', 'jeudi_apresmidi_fermeture',
            'vendredi_matin_ouverture', 'vendredi_matin_fermeture', 'vendredi_apresmidi_ouverture', 'vendredi_apresmidi_fermeture',
            'samedi_matin_ouverture', 'samedi_matin_fermeture', 'samedi_apresmidi_ouverture', 'samedi_apresmidi_fermeture',
            'dimanche_matin_ouverture', 'dimanche_matin_fermeture', 'dimanche_apresmidi_ouverture', 'dimanche_apresmidi_fermeture',
        ]
        widgets = {
            'departement': forms.TextInput(attrs={'placeholder': 'Tapez un département...'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Tapez une ville...'}),
        }

    # ------------------------------------------------------------------
    # Validation d'URL mutualisée
    # Seuls les schémas http:// et https:// sont acceptés.
    # Cela bloque javascript:, data:, ftp:, etc.
    # ------------------------------------------------------------------
    _url_validator = URLValidator(schemes=['http', 'https'])

    def _validate_url(self, field_name, label):
        value = self.cleaned_data.get(field_name, '')
        if not value:
            # Champ facultatif vide → on laisse passer
            return value
        value = value.strip()
        try:
            self._url_validator(value)
        except ValidationError:
            raise ValidationError(
                f"L'adresse « {label} » n'est pas une URL valide "
                f"(elle doit commencer par https:// ou http://)."
            )
        return value

    def clean_site(self):
        return self._validate_url('site', 'Site web')

    def clean_instagram(self):
        return self._validate_url('instagram', 'Instagram')

    def clean_facebook(self):
        return self._validate_url('facebook', 'Facebook')

    def clean_addresseitineraire(self):
        return self._validate_url('addresseitineraire', 'Lien itinéraire')

class NewStoreForm(forms.ModelForm):
    class Meta:
        model = StoreSuggestion
        fields = [
            'nom',
            'ville',
            'departement',
            'ville_precise',
            'descriptionpetite',
            'descriptiongrande',
            'site',
            'phone',
            'instagram',
            'facebook',
            'addressemaps',
            'photo',
            # Horaires
            'lundi',
            'mardi',
            'mercredi',
            'jeudi',
            'vendredi',
            'samedi',
            'dimanche',
        ]
        widgets = {
            'departement': forms.TextInput(attrs={'placeholder': 'Tapez un département...'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Tapez une ville...'}),
        }

class ModifStoreForm(forms.ModelForm):
    class Meta:
        model = StoreSuggestion
        fields = [
            'message',
            'descriptionpetite',
            'descriptiongrande',
            'site',
            'phone',
            'instagram',
            'facebook',
            'addressemaps',
            'photo',
            # Horaires
            'lundi',
            'mardi',
            'mercredi',
            'jeudi',
            'vendredi',
            'samedi',
            'dimanche',
        ]
        widgets = {
        'message': forms.Textarea(attrs={
            'placeholder': 'Expliquez ce que vous souhaitez modifier...',
            'rows': 4,
        }),
    }



