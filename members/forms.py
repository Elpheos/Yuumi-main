from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
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
            'addresseitineraire',
            'photo',
            'galerie_title',
            'galerie_description',
            'galerie_image',
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


# -------------------------------
# Formulaire horaires avec validation
class OpeningHourForm(forms.ModelForm):
    """
    Formulaire pour un jour d'ouverture.
    Les checkboxes "Fermé" côté JS vident les inputs avant soumission,
    donc les champs arrivent à "" → None (null=True, blank=True sur le modèle).
    Le clean() vérifie la cohérence de chaque période.
    """

    class Meta:
        model = OpeningHour
        # 'jour' est exclu : il est déjà en base et ne change jamais.
        # L'inclure dans le POST le rend obligatoire et tout plante.
        fields = [
            'matin_ouverture',
            'matin_fermeture',
            'apresmidi_ouverture',
            'apresmidi_fermeture',
        ]
        widgets = {
            'matin_ouverture':     forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'matin_fermeture':     forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'apresmidi_ouverture': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'apresmidi_fermeture': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['matin_ouverture', 'matin_fermeture',
                           'apresmidi_ouverture', 'apresmidi_fermeture']:
            self.fields[field_name].required = False

    def clean(self):
        cleaned = super().clean()

        # .get() retourne None si le champ est absent de cleaned_data
        # (ce qui arrive quand le champ est vide et required=False)
        mo = cleaned.get('matin_ouverture') or None
        mf = cleaned.get('matin_fermeture') or None
        ao = cleaned.get('apresmidi_ouverture') or None
        af = cleaned.get('apresmidi_fermeture') or None

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
        if mf and ao and ao <= mf:
            self.add_error('apresmidi_ouverture',
                           "L'après-midi doit commencer après la fin du matin.")

        return cleaned


OpeningHourFormSet = inlineformset_factory(
    Store,
    OpeningHour,
    form=OpeningHourForm,
    extra=0,
    can_delete=False,
    # 'jour' n'est pas dans les fields du form, Django le laisse intact en base
)
