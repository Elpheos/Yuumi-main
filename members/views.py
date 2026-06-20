import random
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from datetime import timedelta
from django.utils.safestring import mark_safe
from .utils import convert_to_webp
import logging

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
from django.db.models import Q
from .models import PageView
import json

from .models import (
    Store, ProductFamily, Product, Category,
    StoreImage, CityCategoryHighlight, SuperCategory, StoreGalerieImage, Click, PageView, StoreSuggestion,
)
from .forms import FamilyFormSet, ProductFormSet, RegisterForm, StoreForm, NewStoreForm, ModifStoreForm


def is_open_now(store):
    now = datetime.now(tz=ZoneInfo('Europe/Paris'))
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    today = jours[now.weekday()]
    yesterday = jours[(now.weekday() - 1) % 7]
    current_time = now.time().replace(second=0, microsecond=0)

    def check_jour(jour):
        mo = getattr(store, f'{jour}_matin_ouverture', None)
        mf = getattr(store, f'{jour}_matin_fermeture', None)
        ao = getattr(store, f'{jour}_apresmidi_ouverture', None)
        af = getattr(store, f'{jour}_apresmidi_fermeture', None)
        return mo, mf, ao, af

    mo, mf, ao, af = check_jour(today)

    if mo is not None and mf is not None:
        if mf > mo:
            if mo <= current_time <= mf:
                return True
        else:
            if current_time >= mo:
                return True

    if ao is not None and af is not None:
        if af > ao:
            if ao <= current_time <= af:
                return True
        else:
            if current_time >= ao:
                return True

    mo_hier, mf_hier, ao_hier, af_hier = check_jour(yesterday)
    if mo_hier is not None and mf_hier is not None and mf_hier <= mo_hier:
        if current_time <= mf_hier:
            return True
    if ao_hier is not None and af_hier is not None and af_hier <= ao_hier:
        if current_time <= af_hier:
            return True

    if mo is not None or mf is not None or ao is not None or af is not None:
        return False
    return None


def get_opening_status(store):
    """
    Version enrichie de is_open_now, pensée pour le badge "Ouvert / Fermé"
    de la fiche commerce.

    Contrairement à is_open_now (qui renvoie juste True / False / None),
    celle-ci renvoie un dict avec le libellé prêt à afficher et la
    prochaine transition ("ferme à 19h", "ouvre demain à 9h", etc.).

    Ne remplace pas is_open_now : les deux coexistent pour ne rien casser
    si is_open_now est utilisée ailleurs dans le projet (ex: by_category,
    map_view, etc.). Si ce n'est pas le cas, is_open_now pourra être
    supprimée plus tard au profit de celle-ci.

    Retourne :
        {
            "is_open": True / False / None,   # None = horaires non communiqués
            "label": "Ouvert en ce moment" / "Fermé en ce moment" / "Horaires non communiqués",
            "next_change": "ferme à 19h" / "ouvre à 14h" / "ouvre demain à 9h" / None,
        }
    """
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    now = datetime.now(tz=ZoneInfo('Europe/Paris'))
    today_idx = now.weekday()
    current_time = now.time().replace(second=0, microsecond=0)

    def format_heure(t):
        return t.strftime('%Hh%M').replace('h00', 'h')

    def get_creneaux(jour_idx):
        """Renvoie les créneaux (ouverture, fermeture) du jour donné (matin + après-midi)."""
        jour = jours[jour_idx % 7]
        mo = getattr(store, f'{jour}_matin_ouverture', None)
        mf = getattr(store, f'{jour}_matin_fermeture', None)
        ao = getattr(store, f'{jour}_apresmidi_ouverture', None)
        af = getattr(store, f'{jour}_apresmidi_fermeture', None)

        creneaux = []
        if mo and mf:
            creneaux.append((mo, mf))
        if ao and af:
            creneaux.append((ao, af))
        return creneaux

    # 1. Aucune donnée d'horaires sur toute la semaine -> on ne dit pas "Fermé",
    #    on dit que l'info n'a jamais été renseignée.
    has_any_data = any(get_creneaux(i) for i in range(7))
    if not has_any_data:
        return {
            "is_open": None,
            "label": "Horaires non communiqués",
            "next_change": None,
        }

    creneaux_today = get_creneaux(today_idx)
    creneaux_yesterday = get_creneaux(today_idx - 1)

    is_open = False
    closing_time = None

    # Créneau d'aujourd'hui en cours
    for (o, f) in creneaux_today:
        if f > o:
            if o <= current_time <= f:
                is_open = True
                closing_time = f
                break
        else:
            # créneau qui chevauche minuit (rare, ex: bar ouvert 22h-2h)
            if current_time >= o:
                is_open = True
                closing_time = f
                break

    # Créneau d'hier qui chevauche minuit et court encore
    if not is_open:
        for (o, f) in creneaux_yesterday:
            if f <= o and current_time <= f:
                is_open = True
                closing_time = f
                break

    if is_open:
        next_change = f"ferme à {format_heure(closing_time)}" if closing_time else None
        return {
            "is_open": True,
            "label": "Ouvert en ce moment",
            "next_change": next_change,
        }

    # Fermé : chercher la prochaine ouverture (reste de la journée, puis jours suivants)
    next_opening = None
    next_opening_day_offset = None

    for (o, f) in creneaux_today:
        if o > current_time:
            next_opening = o
            next_opening_day_offset = 0
            break

    if next_opening is None:
        for offset in range(1, 8):
            creneaux = get_creneaux(today_idx + offset)
            if creneaux:
                next_opening = creneaux[0][0]
                next_opening_day_offset = offset
                break

    next_change = None
    if next_opening is not None:
        heure = format_heure(next_opening)
        if next_opening_day_offset == 0:
            next_change = f"ouvre à {heure}"
        elif next_opening_day_offset == 1:
            next_change = f"ouvre demain à {heure}"
        else:
            jour_label = jours[(today_idx + next_opening_day_offset) % 7]
            next_change = f"ouvre {jour_label} à {heure}"

    return {
        "is_open": False,
        "label": "Fermé en ce moment",
        "next_change": next_change,
    }


def build_open_now_filter():
    """
    Construit un objet Q() Django qui filtre les Store ouverts à l'instant présent,
    en se basant sur le jour de la semaine réel et l'heure courante (fuseau Europe/Paris).

    Gère le cas des commerces dont les horaires chevauchent minuit (ex: bar ouvert
    22h-2h) : un tel commerce est considéré "ouvert" soit parce qu'on est dans son
    créneau d'aujourd'hui qui déborde sur demain, soit parce qu'on est encore dans
    son créneau d'hier qui a débordé jusqu'à maintenant.

    IMPORTANT : chaque condition exige explicitement que les deux champs comparés
    soient non-NULL (isnull=False). Sans ça, un commerce qui n'a renseigné AUCUN
    horaire peut remonter par erreur dans certains cas limites où une comparaison
    impliquant NULL ne se comporte pas comme on l'attend sur tous les moteurs SQL.
    Un commerce sans horaires ne doit JAMAIS apparaître comme "ouvert".

    Doit rester cohérent avec get_opening_status (vue détail), même si l'implémentation
    diffère par nécessité : ici on compare des champs entre eux via F() pour que tout
    se passe en SQL, alors que get_opening_status travaille en Python sur un store
    déjà chargé.
    """
    from django.db.models import F

    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    now = datetime.now(tz=ZoneInfo('Europe/Paris'))
    today_idx = now.weekday()
    yesterday_idx = (today_idx - 1) % 7
    current_time = now.time().replace(second=0, microsecond=0)

    today = jours[today_idx]
    yesterday = jours[yesterday_idx]

    q = Q()

    for periode in ["matin", "apresmidi"]:
        o_field = f"{today}_{periode}_ouverture"
        f_field = f"{today}_{periode}_fermeture"

        # Créneau normal d'aujourd'hui : ouverture <= maintenant <= fermeture,
        # et fermeture après ouverture (pas de chevauchement de minuit).
        # isnull=False sur les deux champs : un créneau partiellement vide
        # (ex: ouverture renseignée mais pas fermeture) ne doit pas matcher.
        q |= Q(**{
            f"{o_field}__isnull": False,
            f"{f_field}__isnull": False,
            f"{o_field}__lte": current_time,
            f"{f_field}__gte": current_time,
            f"{f_field}__gt": F(o_field),
        })

        # Créneau d'aujourd'hui qui chevauche minuit (fermeture <= ouverture, ex: 22h-2h)
        # et on est déjà dans ce créneau (après l'heure d'ouverture)
        q |= Q(**{
            f"{o_field}__isnull": False,
            f"{f_field}__isnull": False,
            f"{f_field}__lte": F(o_field),
            f"{o_field}__lte": current_time,
        })

    for periode in ["matin", "apresmidi"]:
        o_field = f"{yesterday}_{periode}_ouverture"
        f_field = f"{yesterday}_{periode}_fermeture"

        # Créneau d'hier qui chevauchait minuit et court encore ce matin
        # (ex: ouvert hier 22h, ferme aujourd'hui 2h, et il est 1h du matin)
        q |= Q(**{
            f"{o_field}__isnull": False,
            f"{f_field}__isnull": False,
            f"{f_field}__lte": F(o_field),
            f"{f_field}__gte": current_time,
        })

    return q


def sort_key(text):
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")

# ---------------------------
# Helper : unfavoris
# ---------------------------

logger = logging.getLogger(__name__)

def get_unfavori_ids(request):
    try:
        if request.user.is_authenticated:
            return list(
                request.user.unfavoris.values_list('id', flat=True)
            )
    except Exception as e:
        logger.error(f"get_unfavori_ids a échoué : {e}", exc_info=True)
    return []

# ---------------------------
# Pages principales
# ---------------------------

def main(request):
    dep = request.COOKIES.get("yuumi_departement")
    ville = request.COOKIES.get("yuumi_ville")
    if dep and ville:
        return redirect("stores", departement=dep.lower(), ville=ville.lower())

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
    unfavori_ids = get_unfavori_ids(request)  # ← NOUVEAU
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville,
    ).exclude(id__in=unfavori_ids)  # ← NOUVEAU

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
    unfavori_ids = get_unfavori_ids(request)  # ← NOUVEAU
    commerces_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville,
        categorie__slug=category,
    ).exclude(id__in=unfavori_ids).select_related("categorie")  # ← NOUVEAU

    open_now = request.GET.get("ouvert") == "1"
    if open_now:
        commerces_qs = commerces_qs.filter(build_open_now_filter())

    paginator = Paginator(commerces_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    message = None
    if not commerces_qs.exists():
        if open_now:
            message = "Aucun commerce ouvert en ce moment pour cette catégorie."
        else:
            message = "Aucun commerce trouvé pour cette catégorie."

    readable_category = category.replace("-", " ").capitalize()

    return render(request, "members/by_category.html", {
        "ville": ville,
        "departement": departement,
        "category": readable_category,
        "commerces": page_obj,
        "page_obj": page_obj,
        "message": message,
        "open_now": open_now,
    })


def store_details(request, departement, ville, slug):
    store = get_object_or_404(Store, slug=slug, departement__iexact=departement, ville__iexact=ville)

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

    is_unfavorite = False
    if request.user.is_authenticated:
        is_unfavorite = store in request.user.unfavoris.all()

    est_ouvert = is_open_now(store)
    opening_status = get_opening_status(store)  # ← NOUVEAU : badge enrichi (label + prochaine transition)

    families_with_rows = []
    for family in store.families.all():
        products = list(family.products.all())
        rows = [products[i:i+4] for i in range(0, len(products), 4)]
        if rows:
            while len(rows[-1]) < 4:
                rows[-1].append(None)
        families_with_rows.append({"family": family, "rows": rows})

    jours = [
        ("lundi", "Mo"), ("mardi", "Tu"), ("mercredi", "We"),
        ("jeudi", "Th"), ("vendredi", "Fr"), ("samedi", "Sa"), ("dimanche", "Su"),
    ]
    opening_hours = []
    for jour_fr, jour_en in jours:
        for periode in ["matin", "apresmidi"]:
            ouverture = getattr(store, f"{jour_fr}_{periode}_ouverture", None)
            fermeture = getattr(store, f"{jour_fr}_{periode}_fermeture", None)
            if ouverture and fermeture:
                opening_hours.append(f"{jour_en} {ouverture.strftime('%H:%M')}-{fermeture.strftime('%H:%M')}")

    return render(request, "members/store_details.html", {
        "store": store,
        "family_formset": family_formset,
        "product_formsets": product_formsets,
        "stores": store_data,
        "is_favorite": is_favorite,
        "is_unfavorite": is_unfavorite,
        "est_ouvert": est_ouvert,
        "opening_status": opening_status,  # ← NOUVEAU
        "families_with_rows": families_with_rows,
        "opening_hours": opening_hours
    })


def search_product(request):
    q = request.GET.get("q", "").strip()
    ville = request.GET.get("ville", "").strip()
    unfavori_ids = get_unfavori_ids(request)  # ← NOUVEAU
    results = []

    if q:
        qs = Product.objects.filter(
            nom__icontains=q,
        ).select_related("family", "family__store").exclude(
            family__store__id__in=unfavori_ids  # ← NOUVEAU
        )

        if ville:
            qs = qs.filter(family__store__ville__iexact=ville)

        for p in qs:
            store = p.family.store
            results.append({
                "product": p.nom,
                "store": store.nom,
                "url": store.get_absolute_url(),
                "photo": store.photo_small.url if store.photo_small else (store.photo.url if store.photo else ""),
                "address": store.addressemaps or "",
                "lat": store.latitude or "",
                "lng": store.longitude or "",
            })

    return JsonResponse({"results": results})


def map_view(request, departement):
    unfavori_ids = get_unfavori_ids(request)
    stores_qs = (
        Store.objects
        .filter(departement__iexact=departement)
        .exclude(id__in=unfavori_ids)
        .select_related("categorie__super_categorie")
    )

    if request.user.is_authenticated:
        favorite_ids = list(request.user.favoris.values_list('id', flat=True))
    else:
        favorite_ids = []

    store_data = []
    for store in stores_qs:
        if store.latitude is not None and store.longitude is not None and store.categorie:
            store_data.append({
                "nom": store.nom,
                "categorie": store.categorie.slug,
                "lat": store.latitude,
                "lng": store.longitude,
                "url": store.get_absolute_url(),
                "photo": store.photo_small.url if store.photo_small else (store.photo.url if store.photo else ""),
                "is_favorite": store.id in favorite_ids, 
            })

   # Dans views.py, remplace la requête categories dans map_view par ceci :

    categories = (
        Category.objects
        .filter(stores__in=stores_qs)
        .select_related("super_categorie", "categorie_intermediaire")
        .distinct()
        .values(
            "slug",
            "name",
            "super_categorie__slug",
            "super_categorie__name",
            "icon_perso",
            "categorie_intermediaire__name",
            "categorie_intermediaire__slug",
        )
        .order_by("super_categorie__name", "categorie_intermediaire__name", "name")
    )

    return render(request, "members/map.html", {
        "stores": store_data,
        "categories": list(categories),
        "departement": departement,
        "favorite_ids": favorite_ids,
    })

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

            for key in request.POST:
                if key.startswith("delete_image_"):
                    img_id = key.split("_")[-1]
                    StoreImage.objects.filter(id=img_id, store=store).delete()

            for image in request.FILES.getlist("extra_images"):
                if image.size > 2 * 1024 * 1024:
                    messages.warning(request, mark_safe(
                        'Une image dépasse 2 Mo. Compressez-la sur '
                        '<a href="https://squoosh.app" target="_blank">squoosh.app</a> puis réessayez.'
                    ))
                else:
                    webp_image = convert_to_webp(image)
                    StoreImage.objects.create(store=store, image=webp_image)

            for key in request.POST:
                if key.startswith("delete_galerie_image_"):
                    img_id = key.split("_")[-1]
                    StoreGalerieImage.objects.filter(id=img_id, store=store).delete()

            for image in request.FILES.getlist("extra_galerie_images"):
                if image.size > 2 * 1024 * 1024:
                    messages.warning(request, mark_safe(
                        'Une image dépasse 2 Mo. Compressez-la sur '
                        '<a href="https://squoosh.app" target="_blank">squoosh.app</a> puis réessayez.'
                    ))
                else:
                    webp_image = convert_to_webp(image)
                    StoreGalerieImage.objects.create(store=store, image=webp_image)

            Store.objects.filter(pk=store.pk).update(horaires_updated_at=timezone.now())
            messages.success(request, "Le commerce a été mis à jour avec succès.")
            return redirect(store.get_absolute_url())
    else:
        form = StoreForm(instance=store)

    return render(request, "members/edit_store.html", {
        "form": form,
        "store": store,
    })


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
        is_unfavorite = False

    return JsonResponse({"is_favorite": is_favorite})


@login_required
def my_favorites(request):
    favoris = request.user.favoris.all()
    unfavoris = request.user.unfavoris.all()
    return render(request, "members/my_favorites.html", {
        "favoris": favoris,
        "unfavoris": unfavoris,
    })


@login_required
def toggle_unfavoris(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    user = request.user

    if store in user.unfavoris.all():
        user.unfavoris.remove(store)
        is_unfavorite = False
    else:
        user.unfavoris.add(store)
        is_unfavorite = True
        user.favoris.remove(store)

    return JsonResponse({"is_unfavorite": is_unfavorite})


@login_required
def my_unfavorites(request):
    favoris = request.user.unfavoris.all()
    return render(request, "members/my_unfavorites.html", {"unfavoris": favoris})


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


def categories_ville(request, departement, ville):
    stores_qs = Store.objects.filter(
        departement__iexact=departement,
        ville__iexact=ville,
    ).select_related("categorie__super_categorie", "categorie__categorie_intermediaire")

    categories_qs = (
        Category.objects
        .filter(stores__in=stores_qs)
        .distinct()
        .select_related("super_categorie", "categorie_intermediaire")
    )

    categories_by_super = {}

    for cat in categories_qs:
        image_url = cat.image.url if cat.image else static("placeholder.png")
        super_cat = cat.super_categorie
        cat_inter = cat.categorie_intermediaire

        if not super_cat:
            continue

        if super_cat not in categories_by_super:
            categories_by_super[super_cat] = {
                "directes": [],
                "intermediaires": {},
            }

        if cat_inter:
            if cat_inter not in categories_by_super[super_cat]["intermediaires"]:
                categories_by_super[super_cat]["intermediaires"][cat_inter] = []
            categories_by_super[super_cat]["intermediaires"][cat_inter].append({
                "name": cat.name,
                "slug": cat.slug,
                "image": image_url,
            })
        else:
            categories_by_super[super_cat]["directes"].append({
                "name": cat.name,
                "slug": cat.slug,
                "image": image_url,
            })

    for super_cat in categories_by_super:
        categories_by_super[super_cat]["directes"].sort(key=lambda c: sort_key(c["name"]))
        for inter in categories_by_super[super_cat]["intermediaires"]:
            categories_by_super[super_cat]["intermediaires"][inter].sort(key=lambda c: sort_key(c["name"]))

    categories_by_super = dict(
        sorted(
            categories_by_super.items(),
            key=lambda x: (x[0].name.lower() == "autres commerces", x[0].name.lower())
        )
    )

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

    ip = get_client_ip(request)

    if not request.user.is_superuser:
        recent = StoreSuggestion.objects.filter(
            ip_address=ip,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).exists()
        if recent:
            return JsonResponse({"error": "cooldown"}, status=429)

    form = NewStoreForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": "Formulaire invalide"}, status=400)

    suggestion = form.save(commit=False)
    suggestion.type_suggestion = "new.store"
    suggestion.ip_address = ip
    suggestion.save()

    send_mail(
        subject=f"Nouvelle suggestion de commerce — {suggestion.nom}",
        message=f"Nom : {suggestion.nom}\nVille : {suggestion.ville}\nDépartement : {suggestion.departement}\nTél : {suggestion.phone}\nSite : {suggestion.site}",
        from_email="noreply@yuumi-shop.com",
        recipient_list=["contact@yuumi-shop.com"],
        fail_silently=False,
    )

    return JsonResponse({"message": "Merci pour votre suggestion !"})


def suggest_modif_store(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    ip = get_client_ip(request)

    if not request.user.is_superuser:
        recent = StoreSuggestion.objects.filter(
            ip_address=ip,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).exists()
        if recent:
            return JsonResponse({"error": "cooldown"}, status=429)

    form = ModifStoreForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": "Formulaire invalide"}, status=400)

    suggestion = form.save(commit=False)
    suggestion.type_suggestion = "modif.store"
    suggestion.ip_address = ip
    suggestion.store = store
    suggestion.save()

    send_mail(
        subject=f"Suggestion de modification — {store.nom}",
        message=f"Commerce : {store.nom}\nVille : {store.ville}\nMessage : {suggestion.message}\nTél : {suggestion.phone}\nSite : {suggestion.site}",
        from_email="noreply@yuumi-shop.com",
        recipient_list=["contact@yuumi-shop.com"],
        fail_silently=False,
    )

    return JsonResponse({"message": "Merci pour votre suggestion !"})


def confidentialite(request):
    return render(request, "members/confidentialite.html")

def apropos(request):
    return render(request, 'members/apropos.html')

def support(request):
    return render(request, 'members/support.html')

def supprimer_compte_public(request):
    return render(request, 'members/supprimer_compte.html')
    
def testyuumi2(request):
    response = render(request, 'members/test-yuumi2.html')
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        from django.contrib.auth import logout
        logout(request)
        user.delete()
        return redirect('main')
    return redirect('account')
