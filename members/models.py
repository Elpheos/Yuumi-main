from django.db import models 
from django.utils.text import slugify
from django.urls import reverse
from geopy.geocoders import Nominatim
from django.contrib.auth.models import User   # ✅ import User


class Store(models.Model):
    nom = models.CharField(max_length=255)
    ville = models.CharField(max_length=255)
    departement = models.CharField(max_length=255)
    
    # 🔸 Catégorie “fine” (épicerie fine, primeur, etc.)
    categorie = models.CharField(max_length=100, null=True, blank=True)
    slugcategorie = models.SlugField(max_length=255, blank=True)

    # 🔸 Super-catégorie (Alimentation / Restauration / Autres)
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

    descriptiongrande = models.TextField(null=True, blank=True)
    descriptionpetite = models.CharField(max_length=255)
    addressemaps = models.CharField(max_length=255, null=True, blank=True)
    addresseitineraire = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    instagram = models.CharField(max_length=255, null=True, blank=True)
    facebook = models.CharField(max_length=255, null=True, blank=True)
    photo = models.ImageField(upload_to='store_photos/', null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # 🔑 Ajout de l’utilisateur propriétaire
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="store",
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        # Slug automatique
        if not self.slug:
            self.slug = slugify(self.nom)
        if self.categorie and not self.slugcategorie:
            self.slugcategorie = slugify(self.categorie)

        # ⚡ Géocodage automatique
        if self.addressemaps and (self.latitude is None or self.longitude is None):
            geolocator = Nominatim(user_agent="yuumi_geocoder")
            try:
                location = geolocator.geocode(self.addressemaps)
                if location:
                    self.latitude = location.latitude
                    self.longitude = location.longitude
                    print(f"{self.nom} | {self.ville} géocodé : {self.latitude}, {self.longitude}")
                else:
                    print(f"Géocodage impossible pour {self.nom} | {self.ville}")
            except Exception as e:
                print(f"Erreur de géocodage pour {self.nom} : {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nom} ({self.ville}, {self.departement})"
    
    def get_absolute_url(self):
        return reverse('store_details', args=[self.departement, self.ville, self.slug])


# 🖼️ Nouveau modèle : plusieurs images par commerce
class StoreImage(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="store_photos/")

    def __str__(self):
        return f"Image de {self.store.nom}"


class ProductFamily(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="families")
    nom = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.nom} - {self.store.nom}"


class Product(models.Model):
    family = models.ForeignKey(ProductFamily, on_delete=models.CASCADE, related_name="products")
    nom = models.CharField(max_length=255)

    @property
    def store(self):
        return self.family.store

    def __str__(self):
        return f"{self.nom} ({self.family.nom})"


User.add_to_class(
    'favoris',
    models.ManyToManyField(Store, blank=True, related_name='favorited_by')
)
