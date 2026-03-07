from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.contrib.auth.models import User
from geopy.geocoders import Nominatim

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
        help_text="Image affichée pour la super catégorie"
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ===========================================================
# 🔹 Catégories (avec icônes)
# ===========================================================

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)

    super_categorie = models.ForeignKey(
        SuperCategory,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,
    )

    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icône Font Awesome, ex : fa-store, fa-utensils"
    )

    image = models.ImageField(
        upload_to="categories/",
        null=True,
        blank=True,
        help_text="Image affichée sur la page ville"
    )

    class Meta:
        unique_together = ("slug", "super_categorie")

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
    last_claim_request = models.DateTimeField(null=True, blank=True)
    horaires_updated_at = models.DateTimeField(null=True, blank=True)

    # 🔹 Catégorie (relation propre)
    categorie = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores"
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

    def _geocode(self):
        """Géocodage en arrière-plan — appelé depuis un thread séparé."""
        geolocator = Nominatim(user_agent="yuumi_geocoder")
        try:
            location = geolocator.geocode(self.addressemaps)
            if location:
                # update() au lieu de save() pour éviter une boucle infinie
                Store.objects.filter(pk=self.pk).update(
                    latitude=location.latitude,
                    longitude=location.longitude
                )
        except Exception:
            pass

    def save(self, *args, **kwargs):
        import threading

        # Slug du commerce
        if not self.slug:
            self.slug = slugify(self.nom)

        # Détecter si l'adresse a changé sur un commerce existant
        adresse_changee = False
        if self.pk:
            ancien = Store.objects.filter(pk=self.pk).values('addressemaps').first()
            if ancien and ancien['addressemaps'] != self.addressemaps:
                adresse_changee = True
                self.latitude = None   # forcer un nouveau géocodage
                self.longitude = None

        super().save(*args, **kwargs)

        # Lancer le géocodage en arrière-plan si nécessaire
        if self.addressemaps and (adresse_changee or self.latitude is None):
            thread = threading.Thread(target=self._geocode)
            thread.daemon = True
            thread.start()

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

# ===========================================================
# 🔹 catégories mises en avant par ville
# ===========================================================

class CityCategoryHighlight(models.Model):
    departement = models.CharField(max_length=100)
    ville = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.ville} ({self.departement})"

# ===========================================================
# 🔹 catégories mises en avant par ville
# ===========================================================

class CityCategoryItem(models.Model):
    city = models.ForeignKey(
        CityCategoryHighlight,
        on_delete=models.CASCADE,
        related_name="items"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    super_category = models.ForeignKey(
        SuperCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        if self.category:
            return f"{self.category.name} - {self.city.ville}"
        if self.super_category:
            return f"{self.super_category.name} - {self.city.ville}"
        return "Item vide"
