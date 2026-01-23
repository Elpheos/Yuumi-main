from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from random import choice
from django.templatetags.static import static
from django.utils.text import slugify

from .models import Store, ProductFamily, Product
from .forms import FamilyFormSet, ProductFormSet, RegisterForm, StoreForm


# ---------------------------
# Pages principales
# ---------------------------

def main(request):
    """
    Page d’accueil : affiche tous les départements et les villes où des commerces existent.
    """
    stores = Store.objects.all().values('departement', 'ville').distinct()

    departements_villes = {}
    for s in stores:
        dep = s['departement'].strip().title() if s['departement'] else ""
        ville = s['ville'].strip().title() if s['ville'] else ""
        if dep and ville:
            departements_villes.setdefault(dep, set()).add(ville)

    sorted_data = {
        dep: sorted(villes, key=str.casefold)
        for dep, villes in sorted(departements_villes.items(), key=lambda x: x[0].casefold())
    }

    return render(request, "members/main.html", {
        "departements_villes": sorted_data,
    })


def stores(request, departement, ville):
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    )
    derniers_arrivants = stores_qs.order_by('-id')[:10]

    return render(request, 'members/all_stores.html', {
        'stores': stores_qs,
        'departement': departement,
        'ville': ville,
        'derniers_arrivants': derniers_arrivants,
    })


def by_category(request, departement, ville, category):
    commerces_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    )

    commerces = [c for c in commerces_qs if slugify(c.categorie or "") == category]

    message = None
    if not commerces:
        message = "Aucun commerce trouvé pour cette catégorie."

    readable_category = category.replace('-', ' ').capitalize()

    return render(request, "members/by_category.html", {
        "ville": ville,
        "departement": departement,
        "category": readable_category,
        "commerces": commerces,
        "message": message,
    })


# ---------------------------
# Détails d’un commerce
# ---------------------------

def store_details(request, departement, ville, slug):
    store = get_object_or_404(Store, slug=slug, departement=departement, ville=ville)

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("login")
        if request.user != store.owner and not request.user.is_superuser:
            raise PermissionDenied("Vous n'avez pas l'autorisation de modifier ce commerce.")

    family_formset = FamilyFormSet(request.POST or None, instance=store, prefix="families")
    product_formsets = {}

    if request.method == "POST":
        if family_formset.is_valid():
            families = family_formset.save()
            for family in families:
                formset_key = f"products_{family.id}"
                product_formsets[family.id] = ProductFormSet(
                    request.POST,
                    instance=family,
                    prefix=formset_key
                )
                if product_formsets[family.id].is_valid():
                    product_formsets[family.id].save()
            messages.success(request, "Les informations ont bien été enregistrées.")
            return redirect('store_details', departement=departement, ville=ville, slug=slug)
    else:
        for family in store.families.all():
            formset_key = f"products_{family.id}"
            product_formsets[family.id] = ProductFormSet(instance=family, prefix=formset_key)

    store_data = []
    if store.latitude and store.longitude:
        store_data.append({
            "nom": store.nom,
            "lat": store.latitude,
            "lng": store.longitude,
            "url": store.get_absolute_url()
        })

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = store in request.user.favoris.all()

    # Horaires d'ouverture, ordonnés selon la semaine française
    jours_ordre = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    opening_hours = sorted(
        store.opening_hours.all(),
        key=lambda h: jours_ordre.index(h.jour)
    )
    return render(request, "members/store_details.html", {
        "store": store,
        "family_formset": family_formset,
        "product_formsets": product_formsets,
        "stores": store_data,
        "is_favorite": is_favorite,
        "opening_hours": opening_hours,
    })


# ---------------------------
# Page de test
# ---------------------------

def testing(request):
    fruits = ['Apple', 'Banana', 'Cherry']
    return render(request, 'template.html', {'fruits': fruits})


# ---------------------------
# Recherche produit
# ---------------------------

def search_product(request):
    q = request.GET.get("q", "").strip()
    results = []

    if q:
        try:
            products = Product.objects.filter(
                nom__istartswith=q
            ).select_related('family', 'family__store')

            for p in products:
                store = p.family.store
                results.append({
                    "product": p.nom,
                    "store": store.nom,
                    "url": store.get_absolute_url(),
                    "photo": store.photo.url if store.photo else None,
                })
        except Exception as e:
            import traceback
            print("Erreur dans search_product :", e)
            traceback.print_exc()

    return JsonResponse(results, safe=False)


# ---------------------------
# Carte des commerces
# ---------------------------

def map_view(request, departement):
    stores_qs = Store.objects.filter(departement__iexact=departement)
    store_data = []
    categories = set()

    for store in stores_qs:
        if store.latitude and store.longitude:
            categorie = store.categorie or ""
            categories.add(categorie)
            store_data.append({
                "nom": store.nom,
                "categorie": categorie,
                "lat": store.latitude,
                "lng": store.longitude,
                "url": store.get_absolute_url(),
                "photo": store.photo.url if store.photo else "",
            })

    return render(request, "members/map.html", {
        "stores": store_data,
        "departement": departement,
        "categories": sorted(categories),
    })


# ---------------------------
# Inscription utilisateur
# ---------------------------

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Bienvenue sur Yuumi ! Votre compte a été créé avec succès.")
            return redirect('main')
    else:
        form = RegisterForm()
    return render(request, "members/register.html", {"form": form})


# ---------------------------
# Édition du commerce
# ---------------------------

@login_required
def edit_store(request):
    store = Store.objects.filter(owner=request.user).first()

    if not store and not request.user.is_superuser:
        messages.error(request, "Vous n'avez pas de commerce associé.")
        return redirect('main')

    if not store and request.user.is_superuser:
        store = Store(
            nom="Nom du commerce",
            ville="Ville",
            departement="Département",
            descriptionpetite="Description courte",
            site="Site web"
        )

    if request.method == "POST":
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            new_store = form.save(commit=False)
            if not store.owner:
                new_store.owner = request.user
            new_store.save()
            messages.success(request, "Le commerce a été mis à jour avec succès.")

            # Redirection vers la page précédente si possible
            next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or new_store.get_absolute_url()
            return redirect(next_url)
    else:
        form = StoreForm(instance=store)

    # On peut passer l'URL actuelle dans le formulaire pour le POST
    return render(request, "members/edit_store.html", {"form": form, "store": store, "next": request.META.get('HTTP_REFERER')})



# ---------------------------
# Gestion des favoris
# ---------------------------

@login_required
def toggle_favoris(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    user = request.user

    if store in user.favoris.all():
        user.favoris.remove(store)
        action = "removed"
    else:
        user.favoris.add(store)
        action = "added"

    return JsonResponse({"action": action})


@login_required
def my_favorites(request):
    favoris = request.user.favoris.all()
    return render(request, 'members/my_favorites.html', {'favoris': favoris})


@login_required
def claim_store(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    user = request.user

    if store.owner:
        return JsonResponse({"error": "Ce commerce a déjà un propriétaire."}, status=400)

    store.owner = user
    store.save()

    # Send email notification
    subject = f"Nouveau commerce revendiqué : {store.nom}"
    message = f"L'utilisateur {user.username} ({user.email}) a revendiqué le commerce '{store.nom}' situé à {store.ville}, {store.departement}."
    send_mail(subject, message, 'noreply@yuumi-shop.com', ['contact@yuumi-shop.com'], fail_silently=True)

    return JsonResponse({"message": "Commerce revendiqué avec succès. Un email de notification a été envoyé."})


# ---------------------------
# Autres pages
# ---------------------------

def about(request):
    return render(request, "members/about.html")


def categories_ville(request, departement, ville):
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    )

    raw_categories = (
        stores_qs.exclude(categorie__isnull=True)
        .exclude(categorie__exact="")
        .values_list('categorie', flat=True)
        .distinct()
    )

    categories = []

    for cat in raw_categories:
        commerces_cat = stores_qs.filter(categorie=cat)

        if not commerces_cat.exists():
            continue

        super_cat = commerces_cat.first().super_categorie

        commerces_with_photo = commerces_cat.filter(photo__isnull=False)

        if commerces_with_photo.exists():
            random_store = choice(list(commerces_with_photo))
            image_url = random_store.photo.url
        else:
            image_url = static("placeholder.png")

        categories.append({
            "name": cat,
            "slug": slugify(cat),
            "image": image_url,
            "super": super_cat,
        })

    alimentation = [c for c in categories if c["super"] == "alimentation"]
    restauration = [c for c in categories if c["super"] == "restauration"]
    autres = [c for c in categories if c["super"] == "autres"]

    return render(request, 'members/categories_villes.html', {
        'alimentation': alimentation,
        'restauration': restauration,
        'autres': autres,
        'departement': departement,
        'ville': ville,
    })


def notre_projet(request):
    return render(request, 'members/notre_projet.html')


def contact(request):
    return render(request, 'members/contact.html')


def cgu(request):
    return render(request, 'members/cgu.html')


def cookies_policy(request):
    return render(request, 'members/cookies.html')


def mentions_legales(request):
    return render(request, 'members/mentions_legales.html')


@login_required
def account(request):
    return render(request, "members/account.html")
    