from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.contrib.auth.models import User
from geopy.geocoders import Nominatim


# ===========================================================
# 🔹 Catégories (avec icônes)
# ===========================================================

class Category(models.Model):
    SUPER_CATEGORIES = [
        ("alimentation", "Alimentation"),
        ("restauration", "Restauration"),
        ("autres", "Autres catégories"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icône Font Awesome, ex : fa-store, fa-utensils"
    )

    super_categorie = models.CharField(
        max_length=50,
        choices=SUPER_CATEGORIES,
        default="autres",
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# ===========================================================
# 🔹 Commerces
# ===========================================================

class Store(models.Model):
    # 🔹 Infos principales
    nom = models.CharField(max_length=255)
    ville = models.CharField(max_length=255)
    departement = models.CharField(max_length=255)

    # 🔹 Catégorie (relation propre)
    categorie = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores"
    )

    SUPER_CATEGORIES = [
        ("alimentation", "Alimentation"),
        ("restauration", "Restauration"),
        ("autres", "Autres catégories"),
    ]
    super_categorie = models.CharField(
        max_length=50,
        choices=SUPER_CATEGORIES,
        default="autres",
    )

    # 🔹 Descriptions
    descriptionpetite = models.CharField(max_length=255)
    descriptiongrande = models.TextField(null=True, blank=True)

    # 🔹 Contact & liens
    addressemaps = models.CharField(max_length=255, null=True, blank=True)
    addresseitineraire = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    instagram = models.CharField(max_length=255, null=True, blank=True)
    facebook = models.CharField(max_length=255, null=True, blank=True)

    # 🔹 Images
    photo = models.ImageField(upload_to='store_photos/', null=True, blank=True)

    # 🔹 Galerie
    galerie_title = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Titre facultatif pour la galerie du commerce"
    )
    galerie_description = models.TextField(
        blank=True, null=True,
        help_text="Description facultative pour la galerie"
    )
    galerie_image = models.ImageField(
        upload_to='store_galerie/', blank=True, null=True,
        help_text="Image principale pour la galerie"
    )

    # 🔹 Slug & géolocalisation
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # 🔹 Propriétaire
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="store",
        null=True,
        blank=True,
        default=None,
    )

    def save(self, *args, **kwargs):
        # Slug du commerce
        if not self.slug:
            self.slug = slugify(self.nom)

        # Géocodage
        if self.addressemaps and (self.latitude is None or self.longitude is None):
            geolocator = Nominatim(user_agent="yuumi_geocoder")
            try:
                location = geolocator.geocode(self.addressemaps)
                if location:
                    self.latitude = location.latitude
                    self.longitude = location.longitude
            except Exception:
                pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nom} ({self.ville}, {self.departement})"

    def get_absolute_url(self):
        return reverse(
            "store_details",
            args=[self.departement, self.ville, self.slug]
        )


# ===========================================================
# 🔹 Images supplémentaires
# ===========================================================

class StoreImage(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(upload_to="store_photos/")

    def __str__(self):
        return f"Image de {self.store.nom}"


# ===========================================================
# 🔹 Familles de produits
# ===========================================================

class ProductFamily(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="families"
    )
    nom = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.nom} - {self.store.nom}"


# ===========================================================
# 🔹 Produits
# ===========================================================

class Product(models.Model):
    family = models.ForeignKey(
        ProductFamily,
        on_delete=models.CASCADE,
        related_name="products"
    )
    nom = models.CharField(max_length=255)

    @property
    def store(self):
        return self.family.store

    def __str__(self):
        return f"{self.nom} ({self.family.nom})"


# ===========================================================
# 🔹 Horaires d'ouverture
# ===========================================================

class OpeningHour(models.Model):
    JOURS_SEMAINE = [
        ("lundi", "Lundi"),
        ("mardi", "Mardi"),
        ("mercredi", "Mercredi"),
        ("jeudi", "Jeudi"),
        ("vendredi", "Vendredi"),
        ("samedi", "Samedi"),
        ("dimanche", "Dimanche"),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="opening_hours"
    )
    jour = models.CharField(max_length=10, choices=JOURS_SEMAINE)
    matin_ouverture = models.TimeField(null=True, blank=True)
    matin_fermeture = models.TimeField(null=True, blank=True)
    apresmidi_ouverture = models.TimeField(null=True, blank=True)
    apresmidi_fermeture = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ("store", "jour")
        ordering = ["store", "jour"]

    def __str__(self):
        return (
            f"{self.get_jour_display()} : "
            f"{self.matin_ouverture} - {self.matin_fermeture}, "
            f"{self.apresmidi_ouverture} - {self.apresmidi_fermeture}"
        )


# ===========================================================
# 🔹 Favoris utilisateurs
# ===========================================================

User.add_to_class(
    "favoris",
    models.ManyToManyField(Store, blank=True, related_name="favorited_by")
)
