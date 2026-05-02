import threading

from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from .utils import convert_to_webp, resize_and_convert
from simple_history.models import HistoricalRecords



# ===========================================================
# 🔹 Super catégories
# ===========================================================

class SuperCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    image = models.ImageField(
        upload_to="super_categories/",
        null=True,
        blank=True,
        help_text="Image affichée pour la super catégorie",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Super catégorie"
        verbose_name_plural = "Super catégories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.pk:
            ancien = SuperCategory.objects.filter(pk=self.pk).values("image").first()
            if ancien and self.image and ancien["image"] != self.image.name:
                self.image = convert_to_webp(self.image)
        elif self.image:
            self.image = convert_to_webp(self.image)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ===========================================================
# 🔹 Catégories
# ===========================================================

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)
    categorie_singulier = models.CharField(max_length=100, blank=True)
    super_categorie = models.ForeignKey(
        SuperCategory,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    icon_perso = models.ImageField(
        upload_to="categories/",
        null=True,
        blank=True,
        help_text="alternative à l'icône FA",
    )
    image = models.ImageField(
        upload_to="categories/",
        null=True,
        help_text="Image affichée sur la page ville",
    )
    history = HistoricalRecords()

    class Meta:
        unique_together = ("slug", "super_categorie")
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.pk:
            ancien = Category.objects.filter(pk=self.pk).values("image", "icon_perso").first()
            if ancien:
                if self.image and ancien["image"] != self.image.name:
                    self.image = convert_to_webp(self.image)
                if self.icon_perso and ancien["icon_perso"] != self.icon_perso.name:
                    self.icon_perso = convert_to_webp(self.icon_perso)
        elif self.image:
            self.image = convert_to_webp(self.image)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ===========================================================
# 🔹 Validateur URL réutilisable (http/https uniquement)
# ===========================================================

_url_validator = URLValidator(schemes=['http', 'https'])


# ===========================================================
# 🔹 Commerces
# ===========================================================

class Store(models.Model):
    # Infos principales
    nom = models.CharField(max_length=255)
    ville = models.CharField(max_length=255)
    departement = models.CharField(max_length=255)
    ville_precise = models.CharField(max_length=255)

    last_claim_request = models.DateTimeField(null=True, blank=True)
    horaires_updated_at = models.DateTimeField(null=True, blank=True)

    # Catégorie
    categorie = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores",
    )

    # Descriptions
    descriptionpetite = models.TextField()
    descriptiongrande = models.TextField(null=True, blank=True)

    # Contact & liens
    addressemaps = models.CharField(max_length=255)
    addresseitineraire = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=[_url_validator],
    )
    site = models.CharField(
        max_length=255,
        blank=True,
        validators=[_url_validator],
    )
    phone = models.CharField(max_length=20, null=True, blank=True)
    instagram = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=[_url_validator],
    )
    facebook = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=[_url_validator],
    )

    # Images
    photo = models.ImageField(upload_to="store_photos/", null=True, blank=True)
    photo_medium = models.ImageField(upload_to="store_photos/", null=True, blank=True, editable=False)
    photo_small = models.ImageField(upload_to="store_photos/", null=True, blank=True, editable=False)

    # Horaires
    lundi_matin_ouverture       = models.TimeField(null=True, blank=True)
    lundi_matin_fermeture       = models.TimeField(null=True, blank=True)
    lundi_apresmidi_ouverture   = models.TimeField(null=True, blank=True)
    lundi_apresmidi_fermeture   = models.TimeField(null=True, blank=True)

    mardi_matin_ouverture       = models.TimeField(null=True, blank=True)
    mardi_matin_fermeture       = models.TimeField(null=True, blank=True)
    mardi_apresmidi_ouverture   = models.TimeField(null=True, blank=True)
    mardi_apresmidi_fermeture   = models.TimeField(null=True, blank=True)

    mercredi_matin_ouverture    = models.TimeField(null=True, blank=True)
    mercredi_matin_fermeture    = models.TimeField(null=True, blank=True)
    mercredi_apresmidi_ouverture = models.TimeField(null=True, blank=True)
    mercredi_apresmidi_fermeture = models.TimeField(null=True, blank=True)

    jeudi_matin_ouverture       = models.TimeField(null=True, blank=True)
    jeudi_matin_fermeture       = models.TimeField(null=True, blank=True)
    jeudi_apresmidi_ouverture   = models.TimeField(null=True, blank=True)
    jeudi_apresmidi_fermeture   = models.TimeField(null=True, blank=True)

    vendredi_matin_ouverture    = models.TimeField(null=True, blank=True)
    vendredi_matin_fermeture    = models.TimeField(null=True, blank=True)
    vendredi_apresmidi_ouverture = models.TimeField(null=True, blank=True)
    vendredi_apresmidi_fermeture = models.TimeField(null=True, blank=True)

    samedi_matin_ouverture      = models.TimeField(null=True, blank=True)
    samedi_matin_fermeture      = models.TimeField(null=True, blank=True)
    samedi_apresmidi_ouverture  = models.TimeField(null=True, blank=True)
    samedi_apresmidi_fermeture  = models.TimeField(null=True, blank=True)

    dimanche_matin_ouverture    = models.TimeField(null=True, blank=True)
    dimanche_matin_fermeture    = models.TimeField(null=True, blank=True)
    dimanche_apresmidi_ouverture = models.TimeField(null=True, blank=True)
    dimanche_apresmidi_fermeture = models.TimeField(null=True, blank=True)

    # Slug & géolocalisation
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Propriétaire
    owner = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        related_name="store",
        null=True,
        blank=True,
        default=None,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Commerce"
        verbose_name_plural = "Commerces"
        ordering = ["nom"]

    def _generate_unique_slug(self):
        base = slugify(self.nom) or "commerce"
        slug = base
        counter = 1
        qs = Store.objects.exclude(pk=self.pk)
        while qs.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def _geocode(self):
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="yuumi_geocoder")
        try:
            location = geolocator.geocode(self.addressemaps, timeout=10)
            if location:
                Store.objects.filter(pk=self.pk).update(
                    latitude=location.latitude,
                    longitude=location.longitude,
                )
        except Exception:
            pass

    def _generate_photo_variants(self):
        ville = slugify(self.ville)
        nom = slugify(self.nom)
        categorie = slugify(self.categorie.name) if self.categorie else "commerce"

        self.photo_medium = resize_and_convert(
            self.photo,
            name=f"{categorie}-{nom}-a-{ville}",
            max_width=600,
        )
        self.photo_small = resize_and_convert(
            self.photo,
            name=f"{nom}-{ville}",
            max_width=300,
        )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()

        adresse_changee = False
        if self.pk:
            ancien = Store.objects.filter(pk=self.pk).values("addressemaps", "photo").first()
            if ancien and ancien["addressemaps"] != self.addressemaps:
                adresse_changee = True
                self.latitude = None
                self.longitude = None

            if self.photo and ancien and ancien["photo"] != self.photo.name:
                self._generate_photo_variants()
        elif self.photo:
            self._generate_photo_variants()

        super().save(*args, **kwargs)

        if self.addressemaps and (adresse_changee or self.latitude is None):
            t = threading.Thread(target=self._geocode)
            t.daemon = True
            t.start()

    def __str__(self):
        return f"{self.nom} ({self.ville}, {self.departement})"

    def get_absolute_url(self):
        return reverse(
            "store_details",
            args=[self.departement, self.ville, self.slug],
        )


# ===========================================================
# 🔹 Images supplémentaires
# ===========================================================

class StoreImage(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="store_photos/")

    history = HistoricalRecords()

    def __str__(self):
        return f"Image de {self.store.nom}"

    def save(self, *args, **kwargs):
        if self.image and not self.image.name.endswith('.webp'):
            self.image = convert_to_webp(self.image)
        super().save(*args, **kwargs)


# ===========================================================
# 🔹 Familles de produits
# ===========================================================

class ProductFamily(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="families",
    )
    nom = models.CharField(max_length=255)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Famille de produits"
        verbose_name_plural = "Familles de produits"

    def __str__(self):
        return f"{self.nom} — {self.store.nom}"


# ===========================================================
# 🔹 Produits
# ===========================================================

class Product(models.Model):
    family = models.ForeignKey(
        ProductFamily,
        on_delete=models.CASCADE,
        related_name="products",
    )
    nom = models.CharField(max_length=255)

    history = HistoricalRecords()

    @property
    def store(self):
        return self.family.store

    def __str__(self):
        return f"{self.nom} ({self.family.nom})"


# ===========================================================
# 🔹 Favoris utilisateurs
# ===========================================================

User.add_to_class(
    "favoris",
    models.ManyToManyField(Store, blank=True, related_name="favorited_by"),
)


# ===========================================================
# 🔹 Catégories mises en avant par ville
# ===========================================================

class CityCategoryHighlight(models.Model):
    departement = models.CharField(max_length=100)
    ville = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Mise en avant ville/catégorie"
        verbose_name_plural = "Mises en avant ville/catégorie"

    def __str__(self):
        return f"{self.ville} ({self.departement})"


class CityCategoryItem(models.Model):
    highlight = models.ForeignKey(
        CityCategoryHighlight,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = "Catégorie mise en avant"
        verbose_name_plural = "Catégories mises en avant"

    def __str__(self):
        return f"{self.highlight} — {self.category}"


# ===========================================================
# 🔹 Images de galerie
# ===========================================================

class StoreGalerieImage(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="galerie_images",
    )
    image = models.ImageField(upload_to="store_galerie/")

    history = HistoricalRecords()

    def __str__(self):
        return f"Galerie image de {self.store.nom}"

    def save(self, *args, **kwargs):
        if self.image and not self.image.name.endswith('.webp'):
            self.image = convert_to_webp(self.image)
        super().save(*args, **kwargs)


# ===========================================================
# 🔹 Trackers
# ===========================================================

class PageView(models.Model):
    store = models.ForeignKey(
        "Store",
        on_delete=models.CASCADE,
        related_name="pageviews",
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class StoreStats(Store):
    class Meta:
        proxy = True
        verbose_name = "Statistique"
        verbose_name_plural = "Statistiques"


class StoreClickStats(Store):
    class Meta:
        proxy = True
        verbose_name = "Statistique des clics"
        verbose_name_plural = "Statistiques des clics"


class Click(models.Model):

    TYPE_CHOICES = [
        ("itineraire", "Itinéraire"),
        ("site",       "Site web"),
        ("instagram",  "Instagram"),
        ("facebook",   "Facebook"),
        ("telephone",  "Téléphone"),
    ]

    store = models.ForeignKey("Store", on_delete=models.CASCADE, related_name="clicks")
    type_click = models.CharField(max_length=20, choices=TYPE_CHOICES, default="site")
    created_at = models.DateTimeField(auto_now_add=True)


class StoreSuggestion(models.Model):

    TYPE_CHOICES = [
        ("new.store", "Suggestion de nouveau commerce"),
        ("modif.store","Suggestion de modification"),
    ]

    STATUT_CHOICES = [
        ("en_attente", "En attente"),
        ("acceptee","Acceptée"),
        ("refusee","Refusée"),
    ]

    nom = models.CharField(max_length=255, null=True, blank=True)
    ville = models.CharField(max_length=255, null=True, blank=True)
    departement = models.CharField(max_length=255, null=True, blank=True)
    ville_precise = models.CharField(max_length=255, null=True, blank=True)

    descriptionpetite = models.TextField(null=True, blank=True)
    descriptiongrande = models.TextField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)

    addressemaps = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(
        max_length=255,
        blank=True,
        validators=[_url_validator],
    )
    phone = models.CharField(max_length=20, null=True, blank=True)
    instagram = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=[_url_validator],
    )
    facebook = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=[_url_validator],
    )

    photo = models.ImageField(upload_to="store_photos/", null=True, blank=True)

    type_suggestion = models.CharField(max_length=20, choices=TYPE_CHOICES)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="en_attente")

    store = models.ForeignKey("Store", on_delete=models.SET_NULL, null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    lundi = models.TextField(null=True, blank=True)
    mardi = models.TextField(null=True, blank=True)
    mercredi = models.TextField(null=True, blank=True)
    jeudi = models.TextField(null=True, blank=True)
    vendredi = models.TextField(null=True, blank=True)
    samedi = models.TextField(null=True, blank=True)
    dimanche = models.TextField(null=True, blank=True)

    produits_suggeres = models.TextField(null=True, blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.get_type_suggestion_display()} — {self.nom or self.store}"

    class Meta:
        verbose_name = "Suggestion"
        verbose_name_plural = "Suggestions"
        ordering = ["-created_at"]
