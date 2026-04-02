"""
Tests Yuumi — membres

Lancer avec : python manage.py test members
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Store, Category, SuperCategory, OpeningHour, ProductFamily, Product


# ===========================================================
# Factories helpers
# ===========================================================

def make_supercategory(name="Alimentation"):
    return SuperCategory.objects.create(name=name, slug=name.lower())


def make_category(name="Boulangerie", super_cat=None):
    if super_cat is None:
        super_cat = make_supercategory()
    return Category.objects.create(name=name, super_categorie=super_cat)


def make_store(nom="Le Pain Doré", ville="Annecy", departement="Haute-Savoie", categorie=None):
    if categorie is None:
        categorie = make_category()
    return Store.objects.create(
        nom=nom,
        ville=ville,
        departement=departement,
        categorie=categorie,
        descriptionpetite="Un pain délicieux",
    )


def make_user(username="testuser", password="testpass123"):
    return User.objects.create_user(username=username, password=password)


# ===========================================================
# Tests des modèles
# ===========================================================

class SuperCategoryModelTest(TestCase):
    def test_creation(self):
        sc = make_supercategory("Restauration")
        self.assertEqual(str(sc), "Restauration")

    def test_slug_auto_genere(self):
        sc = SuperCategory.objects.create(name="Bien-être")
        self.assertTrue(sc.slug)
        self.assertNotIn(" ", sc.slug)


class CategoryModelTest(TestCase):
    def test_creation(self):
        cat = make_category("Fromagerie")
        self.assertEqual(str(cat), "Fromagerie")

    def test_slug_auto_genere(self):
        sc = make_supercategory()
        cat = Category.objects.create(name="Épicerie fine", super_categorie=sc)
        self.assertTrue(cat.slug)


class StoreModelTest(TestCase):
    def test_creation_et_str(self):
        store = make_store()
        self.assertIn("Le Pain Doré", str(store))
        self.assertIn("Annecy", str(store))

    def test_slug_auto_genere(self):
        store = make_store()
        self.assertTrue(store.slug)
        self.assertNotIn(" ", store.slug)

    def test_slug_unique(self):
        """Deux commerces avec le même nom doivent avoir des slugs différents."""
        s1 = make_store(nom="La Bonne Adresse")
        s2 = Store.objects.create(
            nom="La Bonne Adresse",
            ville="Chambéry",
            departement="Savoie",
            categorie=s1.categorie,
            descriptionpetite="Une autre bonne adresse",
        )
        self.assertNotEqual(s1.slug, s2.slug)

    def test_get_absolute_url(self):
        store = make_store()
        url = store.get_absolute_url()
        self.assertIn(store.slug, url)
        self.assertIn(store.ville, url)

    def test_owner_null_ne_supprime_pas_store(self):
        """Supprimer le propriétaire ne doit pas supprimer le commerce (SET_NULL)."""
        user = make_user()
        store = make_store()
        store.owner = user
        store.save()
        user.delete()
        store.refresh_from_db()
        self.assertIsNone(store.owner)


class OpeningHourModelTest(TestCase):
    def test_creation(self):
        store = make_store()
        oh = OpeningHour.objects.create(store=store, jour="lundi")
        self.assertIn("Lundi", str(oh))

    def test_unicite_store_jour(self):
        from django.db import IntegrityError
        store = make_store()
        OpeningHour.objects.create(store=store, jour="mardi")
        with self.assertRaises(IntegrityError):
            OpeningHour.objects.create(store=store, jour="mardi")


class ProductModelTest(TestCase):
    def test_creation(self):
        store = make_store()
        family = ProductFamily.objects.create(store=store, nom="Pains")
        product = Product.objects.create(family=family, nom="Baguette")
        self.assertEqual(product.store, store)
        self.assertIn("Baguette", str(product))


class FavorisTest(TestCase):
    def test_ajout_favori(self):
        user = make_user()
        store = make_store()
        user.favoris.add(store)
        self.assertIn(store, user.favoris.all())

    def test_suppression_favori(self):
        user = make_user()
        store = make_store()
        user.favoris.add(store)
        user.favoris.remove(store)
        self.assertNotIn(store, user.favoris.all())


# ===========================================================
# Tests des vues
# ===========================================================

class ViewsPubliquesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.store = make_store()
        # Créer les 7 jours d'horaires
        for jour in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]:
            OpeningHour.objects.create(store=self.store, jour=jour)

    def test_main_page(self):
        response = self.client.get(reverse("main"))
        self.assertEqual(response.status_code, 200)

    def test_store_details(self):
        url = reverse(
            "store_details",
            args=[self.store.departement, self.store.ville, self.store.slug],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.store.nom)

    def test_all_stores(self):
        url = reverse("all_stores", args=[self.store.departement, self.store.ville])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_notre_projet(self):
        response = self.client.get(reverse("notre_projet"))
        self.assertEqual(response.status_code, 200)

    def test_contact(self):
        response = self.client.get(reverse("contact"))
        self.assertEqual(response.status_code, 200)

    def test_changer_ville(self):
        response = self.client.get(reverse("changer_ville"))
        self.assertEqual(response.status_code, 200)


class ViewsAuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.store = make_store()

    def test_my_favorites_redirige_si_non_connecte(self):
        response = self.client.get(reverse("my-favorites"))
        self.assertRedirects(response, f"/login/?next={reverse('my-favorites')}")

    def test_my_favorites_connecte(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("my-favorites"))
        self.assertEqual(response.status_code, 200)

    def test_account_redirige_si_non_connecte(self):
        response = self.client.get(reverse("account"))
        self.assertRedirects(response, f"/login/?next={reverse('account')}")

    def test_account_connecte(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 200)

    def test_toggle_favoris(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            reverse("toggle-favoris"),
            {"store_id": self.store.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_favorite", data)


class SearchProductTest(TestCase):
    def setUp(self):
        self.client = Client()
        store = make_store()
        family = ProductFamily.objects.create(store=store, nom="Pains")
        Product.objects.create(family=family, nom="Baguette tradition")
        Product.objects.create(family=family, nom="Pain de campagne")

    def test_search_product(self):
        response = self.client.get(
            reverse("search-product"),
            {"q": "Baguette", "ville": "Annecy"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
