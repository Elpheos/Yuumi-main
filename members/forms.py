from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from dal import autocomplete
from .models import Store, ProductFamily, Product, OpeningHour

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
            'photo',
            'galerie_title',
            'galerie_description',
            'galerie_image',
        ]
        widgets = {
            'departement': forms.TextInput(attrs={'placeholder': 'Tapez un département...'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Tapez une ville...'}),
        }

# ============================================================
# À intégrer dans members/forms.py
# Remplace le bloc OpeningHourFormSet existant
# ============================================================

from django import forms
from django.forms import inlineformset_factory
from .models import Store, OpeningHour


class OpeningHourForm(forms.ModelForm):
    """
    Formulaire pour un jour d'ouverture.
    - Les 4 champs TimeField restent nullable (null/blank=True côté modèle).
    - Le clean() vérifie la cohérence de chaque période :
        · Si ouverture renseignée → fermeture obligatoire (et vice-versa)
        · La fermeture doit être APRÈS l'ouverture
    - Le template gère l'affichage "Fermé" via des checkboxes JS côté client
      qui vident les inputs avant soumission → les champs arrivent à "" → None.
    """

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
            'matin_ouverture':     forms.TimeInput(attrs={'type': 'time'}),
            'matin_fermeture':     forms.TimeInput(attrs={'type': 'time'}),
            'apresmidi_ouverture': forms.TimeInput(attrs={'type': 'time'}),
            'apresmidi_fermeture': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned = super().clean()

        mo = cleaned.get('matin_ouverture')
        mf = cleaned.get('matin_fermeture')
        ao = cleaned.get('apresmidi_ouverture')
        af = cleaned.get('apresmidi_fermeture')

        # ── Matin ──────────────────────────────────────────────
        if mo and not mf:
            self.add_error('matin_fermeture',
                           "Indiquez l'heure de fermeture du matin.")
        if mf and not mo:
            self.add_error('matin_ouverture',
                           "Indiquez l'heure d'ouverture du matin.")
        if mo and mf and mo >= mf:
            self.add_error('matin_fermeture',
                           "La fermeture doit être après l'ouverture.")

        # ── Après-midi ─────────────────────────────────────────
        if ao and not af:
            self.add_error('apresmidi_fermeture',
                           "Indiquez l'heure de fermeture de l'après-midi.")
        if af and not ao:
            self.add_error('apresmidi_ouverture',
                           "Indiquez l'heure d'ouverture de l'après-midi.")
        if ao and af and ao >= af:
            self.add_error('apresmidi_fermeture',
                           "La fermeture doit être après l'ouverture.")

        # ── Cohérence inter-périodes ────────────────────────────
        # Si les deux périodes sont renseignées, l'après-midi doit commencer
        # après la fin du matin (évite les chevauchements absurdes).
        if mf and ao and ao <= mf:
            self.add_error('apresmidi_ouverture',
                           "L'après-midi doit commencer après la fin du matin.")

        return cleaned


# Remplace l'ancien OpeningHourFormSet = inlineformset_factory(...)
OpeningHourFormSet = inlineformset_factory(
    Store,
    OpeningHour,
    form=OpeningHourForm,
    extra=0,
    can_delete=False,
)

