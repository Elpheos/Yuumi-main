import random
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.templatetags.static import static
from django.utils import timezone
from datetime import timedelta
from .models import PageView
import json

from .models import (
    Store, ProductFamily, Product, Category,
    StoreImage, CityCategoryHighlight, SuperCategory,StoreGalerieImage,Click, PageView, StoreSuggestion,
)
from .forms import FamilyFormSet, ProductFormSet, RegisterForm, StoreForm, NewStoreForm, ModifStoreForm


# ---------------------------
# Helper : commerce ouvert ?
# À réécrire à l'étape suivante avec les nouveaux champs plats.
# ---------------------------

def is_open_now(store):
    now = datetime.now(tz=ZoneInfo('Europe/Paris'))
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    today = jours[now.weekday()]
    current_time = now.time().replace(second=0, microsecond=0)

    mo = getattr(store, f'{today}_matin_ouverture', None)
    mf = getattr(store, f'{today}_matin_fermeture', None)
    ao = getattr(store, f'{today}_apresmidi_ouverture', None)
    af = getattr(store, f'{today}_apresmidi_fermeture', None)

    if mo and mf and mo <= current_time <= mf:
        return True
    if ao and af and ao <= current_time <= af:
        return True
    if mo or mf or ao or af:
        return False
    return None


# ---------------------------
# Helper : tri alphabétique sans accents
# ---------------------------

def sort_key(text):
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()

# ---------------------------
# Helper : récupérer IP client
# ---------------------------
def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")
    
# ---------------------------
# Pages principales
# ---------------------------

def main(request):
    dep = request.COOKIES.get("yuumi_departement")
    ville = request.COOKIES.get("yuumi_ville")
    if dep and ville:
        return redirect("stores", departement=dep, ville=ville)

    stores = Store.objects.all().values("departement", "ville").distinct()

    departements_villes = {}
    for s in stores:
        dep = s["departement"].strip().title() if s["departement"] else ""
        ville = s["ville"].strip().title() if s["ville"] else ""
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
        ville__iexact=ville,
    )

    derniers_arrivants = stores_qs.order_by("-id")[:10]

    stores_with_photo = stores_qs.filter(
        photo__isnull=False
    ).exclude(photo='')

    stores_with_photo_list = list(stores_with_photo)
    commerces_carousel = random.sample(
        stores_with_photo_list,
        min(5, len(stores_with_photo_list))
    )

    city_config = CityCategoryHighlight.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville,
    ).first()

    city_category_items = city_config.items.all() if city_config else []

    return render(request, "members/all_stores.html", {
        "stores": stores_qs,
        "departement": departement,
        "ville": ville,
        "derniers_arrivants": derniers_arrivants,
        "city_category_items": city_category_items,
        "commerces_carousel": commerces_carousel,
    })


def by_category(request, departement, ville, category):
    commerces_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville,
        categorie__slug=category,
    ).select_related("categorie")

    paginator = Paginator(commerces_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    message = None
    if not commerces_qs.exists():
        message = "Aucun commerce trouvé pour cette catégorie."

    readable_category = category.replace("-", " ").capitalize()

    return render(request, "members/by_category.html", {
        "ville": ville,
        "departement": departement,
        "category": readable_category,
        "commerces": page_obj,
        "page_obj": page_obj,
        "message": message,
    })


# ---------------------------
# Détails d'un commerce
# ---------------------------

def store_details(request, departement, ville, slug):
    store = get_object_or_404(Store, slug=slug, departement=departement, ville=ville)

    # --- TRACKING VUE ---
    session_id = request.session.session_key
    if not session_id:
        request.session.save()
        session_id = request.session.session_key

    ip = get_client_ip(request)

    recent_view = PageView.objects.filter(
        store=store,
        session_id=session_id,
        timestamp__gte=timezone.now() - timedelta(seconds=20)
    ).exists()

    if not recent_view and not request.user.is_superuser:
        PageView.objects.create(
            store=store,
            session_id=session_id,
            ip_address=ip
        )

    # --- LOGIQUE EXISTANTE ---
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
                    prefix=formset_key,
                )
                if product_formsets[family.id].is_valid():
                    product_formsets[family.id].save()
            messages.success(request, "Les informations ont bien été enregistrées.")
            return redirect("store_details", departement=departement, ville=ville, slug=slug)
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
            "url": store.get_absolute_url(),
        })

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = store in request.user.favoris.all()

    est_ouvert = is_open_now(store)
    
    # Préparer les produits par lignes de 4
    families_with_rows = []
    for family in store.families.all():
        products = list(family.products.all())
        rows = [products[i:i+4] for i in range(0, len(products), 4)]
        if rows:
            while len(rows[-1]) < 4:
                rows[-1].append(None)
        families_with_rows.append({"family": family, "rows": rows})
    
    return render(request, "members/store_details.html", {
        "store": store,
        "family_formset": family_formset,
        "product_formsets": product_formsets,
        "stores": store_data,
        "is_favorite": is_favorite,
        "est_ouvert": est_ouvert,
        "families_with_rows": families_with_rows,
    })

# ---------------------------
# Recherche produit
# ---------------------------

def search_product(request):
    q = request.GET.get("q", "").strip()
    ville = request.GET.get("ville", "").strip()
    results = []

    if q:
        qs = Product.objects.filter(
            nom__icontains=q,
        ).select_related("family", "family__store")

        if ville:
            qs = qs.filter(family__store__ville__iexact=ville)

        for p in qs:
            store = p.family.store
            results.append({
                "product": p.nom,
                "store": store.nom,
                "url": store.get_absolute_url(),
                "photo": store.photo.url if store.photo else None,
            })

    return JsonResponse({"results": results})


# ---------------------------
# Carte des commerces
# ---------------------------

def map_view(request, departement):
    stores_qs = (              # ← 4 espaces ✅
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
            "icon",
            "super_categorie__slug",
            "super_categorie__name",
            "icon_perso",
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
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if next_url and not next_url.startswith("/"):
        next_url = ""
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Bienvenue sur Yuumi ! Votre compte a été créé avec succès.")
            return redirect(next_url if next_url else "main")
    else:
        form = RegisterForm()
    return render(request, "members/register.html", {"form": form, "next": next_url})


# ---------------------------
# Édition du commerce
# ---------------------------

@login_required
def edit_store(request, departement, ville, slug):
    store = get_object_or_404(
        Store,
        departement__iexact=departement,
        ville__iexact=ville,
        slug=slug,
    )

    if request.user != store.owner and not request.user.is_superuser:
        raise PermissionDenied("Accès interdit à ce commerce.")

    if request.method == "POST":
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()

            # Suppression images carrousel
            for key in request.POST:
                if key.startswith("delete_image_"):
                    img_id = key.split("_")[-1]
                    StoreImage.objects.filter(id=img_id, store=store).delete()

            # Upload images carrousel
            for image in request.FILES.getlist("extra_images"):
                StoreImage.objects.create(store=store, image=image)

            # Suppression images galerie
            for key in request.POST:
                if key.startswith("delete_galerie_image_"):
                    img_id = key.split("_")[-1]
                    StoreGalerieImage.objects.filter(id=img_id, store=store).delete()

            # Upload images galerie
            for image in request.FILES.getlist("extra_galerie_images"):
                StoreGalerieImage.objects.create(store=store, image=image)

            Store.objects.filter(pk=store.pk).update(horaires_updated_at=timezone.now())
            messages.success(request, "Le commerce a été mis à jour avec succès.")
            return redirect(store.get_absolute_url())
    else:
        form = StoreForm(instance=store)

    return render(request, "members/edit_store.html", {
        "form": form,
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
        is_favorite = False
    else:
        user.favoris.add(store)
        is_favorite = True

    return JsonResponse({"is_favorite": is_favorite})


@login_required
def my_favorites(request):
    favoris = request.user.favoris.all()
    return render(request, "members/my_favorites.html", {"favoris": favoris})


@login_required
def claim_store(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    user = request.user
    now = timezone.now()

    if store.owner:
        return JsonResponse(
            {"error": "Ce commerce a déjà un propriétaire."},
            status=400,
        )

    if store.last_claim_request:
        delta = now - store.last_claim_request
        if delta < timedelta(hours=1):
            remaining = int(3600 - delta.total_seconds())
            return JsonResponse(
                {"error": "cooldown", "remaining": remaining},
                status=429,
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
        "noreply@yuumi-shop.com",
        ["contact@yuumi-shop.com"],
        fail_silently=False,
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
        ville__iexact=ville,
    ).select_related("categorie__super_categorie")

    categories_qs = (
        Category.objects
        .filter(stores__in=stores_qs)
        .distinct()
        .select_related("super_categorie")
    )

    categories_by_super = {}

    for cat in categories_qs:
        image_url = cat.image.url if cat.image else static("placeholder.png")

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

    # Tri alphabétique sans accents dans chaque groupe
    for super_cat in categories_by_super:
        categories_by_super[super_cat].sort(key=lambda cat: sort_key(cat["name"]))

    return render(request, "members/categories_villes.html", {
        "categories_by_super": categories_by_super,
        "departement": departement,
        "ville": ville,
    })


def notre_projet(request):
    return render(request, "members/notre_projet.html")


def contact(request):
    return render(request, "members/contact.html")


def cgu(request):
    return render(request, "members/cgu.html")


def cookies_policy(request):
    return render(request, "members/cookies.html")


def mentions_legales(request):
    return render(request, "members/mentions_legales.html")


@login_required
def account(request):
    store = None
    if hasattr(request.user, "store"):
        store = request.user.store
    return render(request, "members/account.html", {"store": store})


def by_super_category(request, departement, ville, super_slug):
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville,
    ).select_related("categorie__super_categorie")

    super_cat = get_object_or_404(SuperCategory, slug=super_slug)

    categories_qs = (
        Category.objects
        .filter(super_categorie=super_cat, stores__in=stores_qs)
        .distinct()
    )

    categories = []
    for cat in categories_qs:
        image_url = cat.image.url if cat.image else static("placeholder.png")

        categories.append({
            "name": cat.name,
            "slug": cat.slug,
            "image": image_url,
        })

    # Tri alphabétique sans accents
    categories.sort(key=lambda cat: sort_key(cat["name"]))

    return render(request, "members/by_supercategory.html", {
        "super_cat": super_cat,
        "categories": categories,
        "departement": departement,
        "ville": ville,
    })


def changer_ville(request):
    stores = Store.objects.all().values("departement", "ville").distinct()

    departements_villes = {}
    for s in stores:
        dep = s["departement"].strip().title() if s["departement"] else ""
        ville = s["ville"].strip().title() if s["ville"] else ""
        if dep and ville:
            departements_villes.setdefault(dep, set()).add(ville)

    sorted_data = {
        dep: sorted(villes, key=str.casefold)
        for dep, villes in sorted(departements_villes.items(), key=lambda x: x[0].casefold())
    }

    next_url = request.GET.get("next", "")
    if next_url and not next_url.startswith("/"):
        next_url = ""

    return render(request, "members/changer_ville.html", {
        "departements_villes": sorted_data,
        "next": next_url,
    })


def track_click(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    data = json.loads(request.body)
    type_click = data["type_click"]
    if request.user.is_superuser:
        return JsonResponse({"ok": True})
    else:
        Click.objects.create(store=store, type_click=type_click)
        return JsonResponse({"ok": True})

def suggest_new_store(request):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    # 1. Récupérer l'IP
    ip = get_client_ip(request)

    # 2. Vérifier le cooldown par IP
    if not request.user.is_superuser:    # 4 espaces
        recent = StoreSuggestion.objects.filter(  # 8 espaces ← pas 12
            ip_address=ip,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).exists()
        if recent:                        # 8 espaces ← pas 12
            return JsonResponse(
                {"error": "cooldown"},
                status=429,
            )


    # 3. Valider le formulaire
    form = NewStoreForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": "Formulaire invalide"}, status=400)

    # 4. Sauvegarder en BDD
    suggestion = form.save(commit=False)
    suggestion.type_suggestion = "new.store"
    suggestion.ip_address = ip
    suggestion.save()

    # 5. Envoyer le mail
    send_mail(
        subject=f"Nouvelle suggestion de commerce — {suggestion.nom}",
        message=f"Nom : {suggestion.nom}\nVille : {suggestion.ville}\nDépartement : {suggestion.departement}\nTél : {suggestion.phone}\nSite : {suggestion.site}",
        from_email="noreply@yuumi-shop.com",
        recipient_list=["contact@yuumi-shop.com"],
        fail_silently=False,
    )

    # 6. Confirmer
    return JsonResponse({"message": "Merci pour votre suggestion !"})


def suggest_modif_store(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    # 1. Récupérer l'IP
    ip = get_client_ip(request)


    # 2. Vérifier le cooldown par IP
    if not request.user.is_superuser:    # 4 espaces
        recent = StoreSuggestion.objects.filter(  # 8 espaces ← pas 12
            ip_address=ip,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).exists()
        if recent:                        # 8 espaces ← pas 12
            return JsonResponse(
                {"error": "cooldown"},
                status=429,
            )


    # 3. Valider le formulaire
    form = ModifStoreForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": "Formulaire invalide"}, status=400)

    # 4. Sauvegarder en BDD
    suggestion = form.save(commit=False)
    suggestion.type_suggestion = "modif.store"
    suggestion.ip_address = ip
    suggestion.store = store
    suggestion.save()

    # 5. Envoyer le mail
    send_mail(
        subject=f"Suggestion de modification — {store.nom}",
        message=f"Commerce : {store.nom}\nVille : {store.ville}\nMessage : {suggestion.message}\nTél : {suggestion.phone}\nSite : {suggestion.site}",
        from_email="noreply@yuumi-shop.com",
        recipient_list=["contact@yuumi-shop.com"],
        fail_silently=False,
    )

    # 6. Confirmer
    return JsonResponse({"message": "Merci pour votre suggestion !"})
