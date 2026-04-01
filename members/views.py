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
from django.utils import timezone
from datetime import timedelta
from .models import CityCategoryHighlight
from .models import SuperCategory



from .models import Store, ProductFamily, Product, Category, OpeningHour, StoreImage
from .forms import FamilyFormSet, ProductFormSet, RegisterForm, StoreForm, OpeningHourFormSet


# ---------------------------
# Pages principales
# ---------------------------

def main(request):
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

    import random
    stores_list = list(stores_qs)
    commerces_carousel = random.sample(stores_list, min(5, len(stores_list)))

    city_config = CityCategoryHighlight.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    ).first()

    city_category_items = city_config.items.all() if city_config else []

    return render(request, 'members/all_stores.html', {
        'stores': stores_qs,
        'departement': departement,
        'ville': ville,
        'derniers_arrivants': derniers_arrivants,
        'city_category_items': city_category_items,
        'commerces_carousel': commerces_carousel,
    })


def by_category(request, departement, ville, category):
    commerces_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    )

    commerces = [
        c for c in commerces_qs
        if c.categorie and c.categorie.slug == category
    ]

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
# Détails d'un commerce
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

    jours_ordre = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    opening_hours = sorted(
        store.opening_hours.all(),
        key=lambda h: jours_ordre.index(h.jour)
    )

    horaires_renseignes = any(
        h.matin_ouverture or h.matin_fermeture or h.apresmidi_ouverture or h.apresmidi_fermeture
        for h in opening_hours
    )

    return render(request, "members/store_details.html", {
        "store": store,
        "family_formset": family_formset,
        "product_formsets": product_formsets,
        "stores": store_data,
        "is_favorite": is_favorite,
        "opening_hours": opening_hours,
        "horaires_renseignes": horaires_renseignes,
    })


# ---------------------------
# Recherche produit
# ---------------------------

def search_product(request):
    q = request.GET.get("q", "").strip()
    ville = request.GET.get("ville", "").strip()
    results = []

    if q:
        try:
            qs = Product.objects.filter(
                nom__istartswith=q
            ).select_related('family', 'family__store')
            if ville:
                qs = qs.filter(family__store__ville__iexact=ville)
            products = qs

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
    stores_qs = (
        Store.objects
        .filter(departement__iexact=departement)
        .select_related("categorie__super_categorie")
    )

    store_data = []
    for store in stores_qs:
        if store.latitude is not None and store.longitude is not None and store.categorie:
            store_data.append({
                "nom": store.nom,
                "categorie": store.categorie.slug,
                "lat": store.latitude,
                "lng": store.longitude,
                "url": store.get_absolute_url(),
                "photo": store.photo.url if store.photo else "",
            })

    categories = (
        Category.objects
        .filter(stores__in=stores_qs)
        .select_related("super_categorie")
        .distinct()
        .values(
            "slug",
            "name",
            "super_categorie__slug",
            "super_categorie__name",
        )
        .order_by("super_categorie__name", "name")
    )

    return render(request, "members/map.html", {
        "stores": store_data,
        "categories": list(categories),
        "departement": departement,
    })


# ---------------------------
# Inscription utilisateur
# ---------------------------

def register(request):
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Bienvenue sur Yuumi ! Votre compte a été créé avec succès.")
            return redirect(next_url if next_url else 'main')
    else:
        form = RegisterForm()
    return render(request, "members/register.html", {"form": form, "next": next_url})


# ---------------------------
# Édition du commerce
# ---------------------------

from django.core.exceptions import PermissionDenied

@login_required
def edit_store(request, departement, ville, slug):
    store = get_object_or_404(
        Store,
        departement__iexact=departement,
        ville__iexact=ville,
        slug=slug
    )

    if request.user != store.owner and not request.user.is_superuser:
        raise PermissionDenied("Accès interdit à ce commerce.")

    # Pré-remplir les 7 jours si pas encore créés
    jours_semaine = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    jours_existants = set(store.opening_hours.values_list('jour', flat=True))
    for jour in jours_semaine:
        if jour not in jours_existants:
            OpeningHour.objects.create(store=store, jour=jour)

    if request.method == "POST":
        form = StoreForm(request.POST, request.FILES, instance=store)
        opening_formset = OpeningHourFormSet(request.POST, instance=store, prefix="horaires")
        if form.is_valid() and opening_formset.is_valid():
            form.save()
            opening_formset.save()

            # Supprimer les images marquées via les checkboxes du template
            for key in request.POST:
                if key.startswith('delete_image_'):
                    img_id = key.split('_')[-1]
                    StoreImage.objects.filter(id=img_id, store=store).delete()

            # Ajouter les nouvelles images supplémentaires
            for image in request.FILES.getlist('extra_images'):
                StoreImage.objects.create(store=store, image=image)

            Store.objects.filter(pk=store.pk).update(horaires_updated_at=timezone.now())
            messages.success(request, "Le commerce a été mis à jour avec succès.")
            return redirect(store.get_absolute_url())
        else:
            # ── DEBUG : à supprimer une fois le bug résolu ──
            print("\n=== FORM ERRORS ===")
            print(form.errors)
            print("\n=== FORMSET ERRORS ===")
            for i, form_errors in enumerate(opening_formset.errors):
                if form_errors:
                    print(f"  Jour {i} : {form_errors}")
            print("\n=== FORMSET NON-FORM ERRORS ===")
            print(opening_formset.non_form_errors())
            print("\n=== POST DATA (horaires) ===")
            for key, val in request.POST.items():
                if 'horaires' in key:
                    print(f"  {key} = '{val}'")
            print("===================\n")
    else:
        form = StoreForm(instance=store)
        opening_formset = OpeningHourFormSet(instance=store, prefix="horaires")

    return render(request, "members/edit_store.html", {
        "form": form,
        "opening_formset": opening_formset,
        "store": store,
    })


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
    now = timezone.now()

    if store.owner:
        return JsonResponse(
            {"error": "Ce commerce a déjà un propriétaire."},
            status=400
        )

    if store.last_claim_request:
        delta = now - store.last_claim_request
        if delta < timedelta(hours=1):
            remaining = int(3600 - delta.total_seconds())
            return JsonResponse(
                {
                    "error": "cooldown",
                    "remaining": remaining
                },
                status=429
            )

    subject = f"Demande de revendication – {store.nom}"

    message = (
        f"Une demande de revendication a été effectuée.\n\n"
        f"Commerce : {store.nom}\n"
        f"Ville : {store.ville}\n"
        f"Département : {store.departement}\n\n"
        f"Compte utilisateur : {user.username}\n"
        f"Email utilisateur : {user.email}\n\n"
        f"Aucune attribution n'a encore été faite.\n"
        f"Vous pouvez contacter l'utilisateur pour vérification."
    )

    send_mail(
        subject,
        message,
        'noreply@yuumi-shop.com',
        ['contact@yuumi-shop.com'],
        fail_silently=False
    )

    store.last_claim_request = now
    store.save(update_fields=["last_claim_request"])

    return JsonResponse({
        "message": (
            "Votre demande de revendication a bien été envoyée. "
            "Nous vous contacterons après vérification."
        )
    })


# ---------------------------
# Autres pages
# ---------------------------

def categories_ville(request, departement, ville):
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    ).select_related("categorie__super_categorie")

    categories_qs = (
        Category.objects
        .filter(stores__in=stores_qs)
        .distinct()
        .select_related("super_categorie")
    )

    categories_by_super = {}

    for cat in categories_qs:
        commerces_cat = stores_qs.filter(categorie=cat)
        commerces_with_photo = commerces_cat.filter(photo__isnull=False)

        if commerces_with_photo.exists():
            random_store = choice(list(commerces_with_photo))
            image_url = random_store.photo.url
        else:
            image_url = static("placeholder.png")

        super_cat = cat.super_categorie

        if not super_cat:
            continue

        if super_cat not in categories_by_super:
            categories_by_super[super_cat] = []

        categories_by_super[super_cat].append({
            "name": cat.name,
            "slug": cat.slug,
            "image": image_url,
        })

    return render(request, 'members/categories_villes.html', {
        'categories_by_super': categories_by_super,
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
    store = None

    if hasattr(request.user, "store"):
        store = request.user.store

    return render(
        request,
        "members/account.html",
        {
            "store": store
        }
    )

def by_super_category(request, departement, ville, super_slug):
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville
    ).select_related("categorie__super_categorie")

    super_cat = get_object_or_404(
        SuperCategory,
        slug=super_slug
    )

    categories_qs = (
        Category.objects
        .filter(
            super_categorie=super_cat,
            stores__in=stores_qs
        )
        .distinct()
    )

    categories = []

    for cat in categories_qs:
        commerces_cat = stores_qs.filter(categorie=cat)
        commerces_with_photo = commerces_cat.filter(photo__isnull=False)

        if commerces_with_photo.exists():
            random_store = choice(list(commerces_with_photo))
            image_url = random_store.photo.url
        else:
            image_url = static("placeholder.png")

        categories.append({
            "name": cat.name,
            "slug": cat.slug,
            "image": image_url,
        })

    return render(request, "members/by_supercategory.html", {
        "super_cat": super_cat,
        "categories": categories,
        "departement": departement,
        "ville": ville,
    })

def changer_ville(request):
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

    return render(request, 'members/changer_ville.html', {
        'departements_villes': sorted_data,
        'next': request.GET.get('next', request.META.get('HTTP_REFERER', '')),
    })



