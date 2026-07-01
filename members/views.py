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
    Wishlist, WishlistStore, StoreNote,
)
from .forms import FamilyFormSet, ProductFormSet, RegisterForm, StoreForm, NewStoreForm, ModifStoreForm

from .ai_agent.access import can_use_ai_agent, register_ai_usage, is_premium_user, can_use_web_search
from .ai_agent.client import understand_intent, extract_search_params, recommend_stores
from .ai_agent.search import find_matching_stores, apply_open_now_filter
from django.http import HttpResponse
from django.shortcuts import redirect
from .utils import web_only, app_only, is_native_request, activer_premium, yuumi_plus_required, YUUMI_PLUS_WISHLIST_LIMIT, YUUMI_PLUS_UNFAVORIS_LIMIT, verify_google_purchase

AI_AGENT_PUBLIC = False

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
        if request.user.is_authenticated and is_premium_user(request.user):
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


def haversine_km(lat1, lng1, lat2, lng2):
    """
    Distance à vol d'oiseau entre deux points GPS, en km (formule haversine,
    approximation sphérique de la Terre — largement suffisante à l'échelle
    d'une ville). Calcul en Python pur, pas de SQL : utilisé pour filtrer une
    liste de Store déjà chargée depuis la base.
    """
    import math
    R = 6371.0
    lat1_r, lng1_r, lat2_r, lng2_r = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_r - lat1_r
    dlng = lng2_r - lng1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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

    # Filtre distance : nécessite la position utilisateur (lat/lng), transmise par
    # le JS une fois la géolocalisation obtenue (voir le script de la page catégorie).
    # Calcul en Python pur (haversine_km) sur les commerces déjà filtrés par catégorie
    # et "ouvert maintenant" — pas de SQL exotique, le nombre de commerces par
    # catégorie/ville reste assez restreint pour que ça reste rapide.
    user_lat = request.GET.get("lat")
    user_lng = request.GET.get("lng")
    distance_km = request.GET.get("distance")
    distance_active = False

    if user_lat and user_lng and distance_km:
        try:
            user_lat = float(user_lat)
            user_lng = float(user_lng)
            max_km = float(distance_km)
            if max_km < 15:  # 15 = valeur par défaut du slider = "pas de filtre"
                distance_active = True
                kept_ids = []
                for store in commerces_qs:
                    if store.latitude is None or store.longitude is None:
                        continue
                    km = haversine_km(user_lat, user_lng, store.latitude, store.longitude)
                    if km <= max_km:
                        kept_ids.append(store.id)
                commerces_qs = commerces_qs.filter(id__in=kept_ids)
        except (TypeError, ValueError):
            pass  # paramètres invalides : on ignore le filtre distance plutôt que de planter

    paginator = Paginator(commerces_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    message = None
    if not commerces_qs.exists():
        if open_now and distance_active:
            message = "Aucun commerce ouvert en ce moment dans ce rayon pour cette catégorie."
        elif open_now:
            message = "Aucun commerce ouvert en ce moment pour cette catégorie."
        elif distance_active:
            message = "Aucun commerce dans ce rayon pour cette catégorie."
        else:
            message = "Aucun commerce trouvé pour cette catégorie."

    readable_category = category.replace("-", " ").capitalize()

    # Construit le suffixe de query string à ajouter à tous les liens de pagination
    # (ouvert + lat/lng/distance si actifs), pour ne pas répéter cette logique
    # dans le template à chaque lien.
    extra_params = ""
    if open_now:
        extra_params += "&ouvert=1"
    if distance_active:
        extra_params += f"&lat={user_lat}&lng={user_lng}&distance={distance_km}"

    return render(request, "members/by_category.html", {
        "ville": ville,
        "departement": departement,
        "category": readable_category,
        "commerces": page_obj,
        "page_obj": page_obj,
        "message": message,
        "open_now": open_now,
        "distance_active": distance_active,
        "current_distance": distance_km if distance_active else None,
        "user_lat": user_lat if distance_active else None,
        "user_lng": user_lng if distance_active else None,
        "extra_params": extra_params,
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
        
    user_wishlists = []
    if request.user.is_authenticated and is_premium_user(request.user):
        wishlist_ids_with_store = set(
            WishlistStore.objects.filter(
                wishlist__user=request.user, store=store
            ).values_list("wishlist_id", flat=True)
        )
        user_wishlists = [
            {"id": w.id, "name": w.name, "has_store": w.id in wishlist_ids_with_store}
            for w in request.user.wishlists.all()
        ]

    store_note_text = ""
    if request.user.is_authenticated and is_premium_user(request.user):
        note = StoreNote.objects.filter(user=request.user, store=store).first()
        if note:
            store_note_text = note.text
        
    est_ouvert = is_open_now(store)
    opening_status = get_opening_status(store)

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
        "user_wishlists": user_wishlists,
        "est_ouvert": est_ouvert,
        "opening_status": opening_status,  # ← NOUVEAU
        "families_with_rows": families_with_rows,
        "opening_hours": opening_hours,
        "store_note_text": store_note_text,
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
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
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
    unfavoris = request.user.unfavoris.all() if is_premium_user(request.user) else []
    wishlists = (
        request.user.wishlists.all().prefetch_related("stores")
        if is_premium_user(request.user) else []
    )
    return render(request, "members/my_favorites.html", {
        "favoris": favoris,
        "unfavoris": unfavoris,
        "wishlists": wishlists,
    })


@login_required
def toggle_unfavoris(request, store_id):
    if not is_premium_user(request.user):
        return JsonResponse(
            {"error": "Cette fonctionnalité est réservée aux comptes Premium."},
            status=403,
        )

    store = get_object_or_404(Store, id=store_id)
    user = request.user
    if store in user.unfavoris.all():
        user.unfavoris.remove(store)
        is_unfavorite = False
    else:
        if request.user.unfavoris.count() >= YUUMI_PLUS_UNFAVORIS_LIMIT:
            return JsonResponse(
                {"error": f"Vous avez atteint la limite de {YUUMI_PLUS_UNFAVORIS_LIMIT} commerces masqués."},
                status=400,
            )
        user.unfavoris.add(store)
        is_unfavorite = True
        user.favoris.remove(store)
    return JsonResponse({"is_unfavorite": is_unfavorite})


@login_required
@yuumi_plus_required
def my_unfavorites(request):
    favoris = request.user.unfavoris.all()
    return render(request, "members/my_unfavorites.html", {"unfavoris": favoris})


# ===========================================================
# 🔹 Wishlists nommées (Premium)
# ===========================================================

@login_required
@yuumi_plus_required
def create_wishlist(request):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    if not is_premium_user(request.user):
        return JsonResponse(
            {"error": "Cette fonctionnalité est réservée aux comptes Premium."},
            status=403,
        )

    if request.user.wishlists.count() >= YUUMI_PLUS_WISHLIST_LIMIT:
        return JsonResponse(
            {"error": f"Vous avez atteint la limite de {YUUMI_PLUS_WISHLIST_LIMIT} catégories."},
            status=400,
        )

    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Le nom de la wishlist est requis."}, status=400)

    if request.user.wishlists.filter(name__iexact=name).exists():
        return JsonResponse({"error": "Vous avez déjà une wishlist avec ce nom."}, status=400)

    wishlist = Wishlist.objects.create(user=request.user, name=name)
    return JsonResponse({"id": wishlist.id, "name": wishlist.name})

@login_required
@yuumi_plus_required
def toggle_wishlist_store(request, wishlist_id, store_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    wishlist = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    store = get_object_or_404(Store, id=store_id)

    link = WishlistStore.objects.filter(wishlist=wishlist, store=store).first()
    if link:
        link.delete()
        return JsonResponse({"in_wishlist": False})

    if not is_premium_user(request.user):
        return JsonResponse(
            {"error": "Cette fonctionnalité est réservée aux comptes Premium."},
            status=403,
        )

    WishlistStore.objects.create(wishlist=wishlist, store=store)
    return JsonResponse({"in_wishlist": True})
    
@login_required
@yuumi_plus_required
def delete_wishlist(request, wishlist_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    wishlist = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    wishlist.delete()
    return JsonResponse({"deleted": True})

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
    
@login_required
def testyuumi2(request):
    response = render(request, 'members/recherche-intelligente.html', {
        "departement_cookie": request.COOKIES.get("yuumi_departement", ""),
        "ville_cookie": request.COOKIES.get("yuumi_ville", ""),
    })
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

# Extrait de members/views.py — fonction ai_search_agent patchee (memoire conversationnelle).
# Dependances supposees deja importees en haut de views.py : JsonResponse, json,
# can_use_ai_agent, is_premium_user, understand_intent, extract_search_params,
# recommend_stores, register_ai_usage, find_matching_stores.

@yuumi_plus_required
@login_required
def ai_search_agent(request):
    """
    Point d'entree complet de l'agent IA premium.

    La ville/departement sont TOUJOURS envoyes explicitement par le
    frontend (confirmes par l'utilisateur avant l'envoi, pre-remplis
    depuis le cookie cote frontend mais jamais devines cote serveur).

    Enchaine : verification acces -> cache -> (option) comprehension web ->
    extraction parametres -> recherche en base par tiers de preuve (catalogue
    / description / categorie) -> recommandation finale (intention, confiance
    confirme/deduit, justification par resultat).

    MEMOIRE CONVERSATIONNELLE : le frontend peut envoyer un champ "history"
    (JSON, liste de tours {role, content}). Il est transmis a l'extraction
    pour resoudre les questions de suivi ("et ce soir ?") par rapport au fil,
    et sert a reconstruire le besoin complet pour la recommandation. Une
    requete avec historique n'est ni lue ni ecrite dans le cache (elle depend
    du contexte conversationnel, pas seulement de (query, ville, departement)).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    if not can_use_ai_agent(request.user):
        if not is_premium_user(request.user):
            return JsonResponse(
                {"error": "Cette fonctionnalité est réservée aux comptes Premium."},
                status=403,
            )
        return JsonResponse({
            "fallback_to_tree": True,
            "message": (
                "Vous avez atteint votre quota de recherches IA pour aujourd'hui. "
                "Utilisez le guide par questions pour continuer votre recherche."
            ),
        })

    user_query = request.POST.get("query", "").strip()
    departement = request.POST.get("departement", "").strip()
    ville = request.POST.get("ville", "").strip()

    if not user_query:
        return JsonResponse({"error": "Requête vide."}, status=400)

    if not departement or not ville:
        return JsonResponse({
            "error": "Ville non précisée. Veuillez confirmer une ville avant de rechercher.",
        }, status=400)

    # -----------------------------------------------------------------
    # HISTORIQUE CONVERSATIONNEL envoye par le frontend (liste de tours
    # {role, content}). Valide strictement : on n'injecte que des tours bien
    # formes dans l'appel LLM, et on borne leur nombre pour limiter le cout.
    # -----------------------------------------------------------------
    history = []
    history_raw = request.POST.get("history", "")
    if history_raw:
        try:
            parsed = json.loads(history_raw)
            if isinstance(parsed, list):
                for tour in parsed:
                    if (isinstance(tour, dict)
                            and tour.get("role") in ("user", "assistant")
                            and isinstance(tour.get("content"), str)
                            and tour["content"].strip()):
                        history.append({
                            "role": tour["role"],
                            "content": tour["content"][:2000],
                        })
        except (ValueError, TypeError):
            history = []
    history = history[-16:]  # 8 echanges max (user + assistant)

    # -----------------------------------------------------------------
    # CACHE : meme (query, ville, departement) -> meme reponse, sans relancer
    # les 2-3 appels LLM. Un hit ne consomme PAS de quota (reponse gratuite a
    # servir). On ne met en cache que les reponses NON temporelles : une
    # recherche "ouvert maintenant" depend de l'heure et n'est jamais cachee
    # (voir cache.set plus bas). Une requete AVEC historique n'est ni lue ni
    # ecrite dans le cache : elle depend du fil de conversation, pas seulement
    # de (query, ville, departement). NB : un backend de cache PARTAGE entre
    # les workers Gunicorn est necessaire pour que ce soit efficace (voir
    # reglage CACHES dans settings).
    # -----------------------------------------------------------------
    import hashlib
    from django.core.cache import cache

    cache_key = "yuumi_ai:" + hashlib.sha256(
        f"{user_query.lower()}|{departement.lower()}|{ville.lower()}".encode("utf-8")
    ).hexdigest()

    reponse_cache = cache.get(cache_key)
    if reponse_cache is not None and not history:
        return JsonResponse(reponse_cache)

    # -----------------------------------------------------------------
    # ETAPE 1 : comprehension d'intention.
    # On ne paie l'agent web (understand_intent) QUE si la requete depend d'une
    # info externe et changeante (meteo, tendance, evenement). Sinon on saute
    # cet appel et extract_search_params analyse la requete brute : un appel LLM
    # de moins, moins de latence, moins de quota Mistral consomme.
    # -----------------------------------------------------------------
    from .ai_agent.client import needs_web_search

    web_search_a_ete_utilise = needs_web_search(user_query)

    # Quota mensuel de recherches web atteint : mode dégradé (pas de blocage total)
    if web_search_a_ete_utilise and not can_use_web_search(request.user):
        web_search_a_ete_utilise = False

    if web_search_a_ete_utilise:
        intent_text = understand_intent(user_query)
        if intent_text is None:
            return JsonResponse({
                "fallback_to_tree": True,
                "message": "La recherche intelligente est temporairement indisponible.",
            })
    else:
        intent_text = None  # extract_search_params gere le cas None.

    params = extract_search_params(user_query, intent_text, history=history)
    if params is None:
        return JsonResponse({
            "fallback_to_tree": True,
            "message": "La recherche intelligente est temporairement indisponible.",
        })

    # Hors-sujet detecte des l'extraction - on s'arrete ici.
    if params.get("hors_sujet"):
        register_ai_usage(request.user, web_search_used=web_search_a_ete_utilise)
        return JsonResponse({
            "fallback_to_tree": False,
            "besoin_clarification": False,
            "hors_sujet": True,
            "message": (
                "Je suis l'assistant de recherche de Yuumi, dedie a vous aider "
                "a trouver des commerces et produits locaux. Pouvez-vous "
                "reformuler votre demande dans ce sens ?"
            ),
            "pistes": [],
            "aucun_resultat": True,
        })

    # Categorie absente : la demande a un vrai sens commercial mais aucune
    # categorie Yuumi ne la couvre.
    if params.get("categorie_absente"):
        register_ai_usage(request.user, web_search_used=web_search_a_ete_utilise)
        return JsonResponse({
            "fallback_to_tree": False,
            "besoin_clarification": False,
            "categorie_absente": True,
            "message": (
                "Ce type de commerce n'est pas encore référencé sur Yuumi "
                "pour le moment. N'hésitez pas à nous suggérer son ajout !"
            ),
            "pistes": [],
            "aucun_resultat": True,
        })

    # Demande trop vague : on renvoie des questions de clarification.
    if params.get("besoin_clarification"):
        return JsonResponse({
            "fallback_to_tree": False,
            "besoin_clarification": True,
            "questions_clarification": params.get("questions_clarification", []),
            "message": "Pouvez-vous préciser votre demande ?",
        })

    # -----------------------------------------------------------------
    # ETAPE 2 : recherche en base, par TIERS DE PREUVE.
    #   - catalogue (Product/ProductFamily) -> preuve forte  -> [CONFIRME]
    #   - description (fiche du commerce)    -> preuve directe -> deduit
    #   - categorie                          -> filet large    -> deduit
    # Le filtre "ouvert maintenant" est applique EN SQL dans chaque recherche,
    # AVANT le plafond de candidats (sinon on plafonnait a 30 puis filtrait,
    # d'ou des "aucun resultat" a tort).
    # -----------------------------------------------------------------
    from .ai_agent.search import (
        find_stores_by_product,
        find_stores_by_description,
        combine_store_querysets,
    )

    ouvert = bool(params.get("ouvert_maintenant", False))
    categories = params.get("categories", [])
    idees_produits = params.get("idees_produits", [])

    commerces_par_categorie = find_matching_stores(
        categories, departement, ville, ouvert_maintenant=ouvert
    )
    commerces_par_produit = find_stores_by_product(
        idees_produits, departement, ville, ouvert_maintenant=ouvert
    )
    commerces_par_desc = find_stores_by_description(
        idees_produits, departement, ville, ouvert_maintenant=ouvert
    )

    # Seul le catalogue donne le marqueur [CONFIRME].
    ids_par_produit = set(commerces_par_produit.values_list("id", flat=True))

    demande_produit_precis = bool(idees_produits)

    if demande_produit_precis:
        # Preuve directe = au moins un commerce trouve par catalogue OU par
        # description. Dans ce cas on n'utilise PAS le filet "categorie", qui
        # ferait remonter des commerces vaguement lies (bug Famille Mary).
        preuve_directe = bool(ids_par_produit) or commerces_par_desc.exists()
        if preuve_directe:
            commerces_filtres = combine_store_querysets(
                commerces_par_produit, commerces_par_desc
            )
            # Il existe une preuve directe (catalogue et/ou description) : le
            # flux normal confirme/deduit suffit. Les commerces "description
            # seule" ne sont pas [CONFIRME] -> l'IA les presentera en deduit,
            # en s'appuyant sur la fiche. Pas besoin du message "aucune
            # correspondance exacte".
            produit_sans_match_confirme = False
        else:
            # Aucune preuve directe -> on retombe sur le filet categorie, mais
            # l'IA devra l'annoncer honnetement et ne garder que le plausible.
            commerces_filtres = combine_store_querysets(commerces_par_categorie)
            produit_sans_match_confirme = True
    else:
        # Demande de type categorie / besoin : produit (confirme) d'abord,
        # puis categorie, pour ne jamais tronquer un match confirme.
        commerces_filtres = combine_store_querysets(
            commerces_par_produit, commerces_par_categorie
        )
        produit_sans_match_confirme = False

    # -----------------------------------------------------------------
    # COURT-CIRCUIT LISTE VIDE : si aucun candidat ne ressort, NE PAS
    # appeler recommend_stores. Sur une liste vide, le modele improvise un
    # message de recadrage type "ça ne correspond pas à la mission de Yuumi",
    # ce qui est absurde pour une vraie categorie (ex: un restaurant a 11h,
    # simplement pas encore ouvert). On renvoie ici un message honnete et
    # adapte, sans appel LLM (gratuit, instantane).
    # -----------------------------------------------------------------
    if not commerces_filtres:
        register_ai_usage(request.user, web_search_used=web_search_a_ete_utilise)

        if ouvert:
            # Distinguer "rien d'OUVERT maintenant" de "rien du tout dans
            # cette ville" : on relance la meme recherche categorie SANS le
            # filtre horaire. Si ca renvoie des commerces, c'est juste une
            # question d'horaire, pas d'absence de commerce.
            existe_hors_horaire = find_matching_stores(
                categories, departement, ville, ouvert_maintenant=False
            ).exists()
            if existe_hors_horaire:
                message = (
                    "Aucun commerce correspondant n'est ouvert à cet instant. "
                    "Réessayez plus tard, ou relancez la recherche sans le critère "
                    "« ouvert maintenant »."
                )
            else:
                message = (
                    "Je n'ai trouvé aucun commerce correspondant à votre recherche "
                    "dans votre ville pour le moment."
                )
        else:
            message = (
                "Je n'ai trouvé aucun commerce correspondant à votre recherche "
                "dans votre ville pour le moment."
            )

        payload = {
            "fallback_to_tree": False,
            "besoin_clarification": False,
            "intention": "",
            "message": message,
            "pistes": [],
            "aucun_resultat": True,
        }
        # Pas de mise en cache : une reponse "rien d'ouvert" depend de l'heure,
        # et une reponse "rien dans la ville" peut changer des qu'un commerce
        # est ajoute -> on prefere ne pas figer ces cas vides.
        return JsonResponse(payload)

    # -----------------------------------------------------------------
    # REQUETE EFFECTIVE pour la recommandation : on reconstruit le besoin
    # complet a partir de TOUS les tours utilisateur (cote serveur uniquement,
    # jamais affiche ni place dans la barre de recherche). Sans ca,
    # recommend_stores ne verrait que le dernier message ("et ce soir ?") et
    # perdrait le "restaurant gastronomique" du depart. Hors conversation,
    # requete_effective == user_query (comportement inchange).
    # -----------------------------------------------------------------
    tours_user = [t["content"] for t in history if t["role"] == "user"]
    tours_user.append(user_query)
    requete_effective = " ; ".join(tours_user)

    resultat_ia = recommend_stores(
        requete_effective,
        commerces_filtres,
        ids_par_produit,
        produit_sans_match_confirme=produit_sans_match_confirme,
        ouvert_maintenant=ouvert,
    )

    if resultat_ia is None:
        return JsonResponse({
            "fallback_to_tree": True,
            "message": "La recherche intelligente est temporairement indisponible.",
        })

    # Verification de securite : on ne fait JAMAIS confiance aveuglement
    # aux ID renvoyes par l'IA. Le JSON Schema garantit le FORMAT, pas le
    # CONTENU. Applique a chaque resultat, quelle que soit la piste.
    #
    # ids_deja_cites : garde-fou cote code contre la duplication d'un meme
    # commerce dans plusieurs pistes. Observe en prod : sur une demande
    # avec tres peu de candidats reels (ex: 2 commerces pour un "cadeau
    # d'anniversaire sous 20 euros"), le modele a invente 3 pistes
    # ("creatif", "educatif", "gourmand") en reutilisant les 2 MEMES
    # commerces dans chacune, avec des justifications de plus en plus
    # forcees pour justifier la repetition. Le prompt interdit maintenant
    # explicitement cette duplication (voir client.py, regle 5), mais on
    # ne peut pas compter uniquement sur l'instruction textuelle - ce
    # garde-fou cote code garantit le resultat meme si le modele l'ignore.
    # Premiere piste ou un ID apparait = piste retenue, les occurrences
    # suivantes du meme ID dans d'autres pistes sont silencieusement
    # ignorees.
    ids_valides = {store.id for store in commerces_filtres}
    ids_deja_cites = set()
    pistes_valides = []
    for piste in resultat_ia.get("pistes", []):
        resultats_valides = []
        for reco in piste.get("resultats", []):
            reco_id = reco.get("id")
            if reco_id in ids_valides and reco_id not in ids_deja_cites:
                ids_deja_cites.add(reco_id)
                store = next(s for s in commerces_filtres if s.id == reco_id)
                resultats_valides.append({
                    "id": store.id,
                    "nom": store.nom,
                    "slug": store.slug,
                    "ville": store.ville,
                    "departement": store.departement,
                    "url": store.get_absolute_url(),
                    "confiance": reco.get("confiance", "deduit"),
                    "justification": reco.get("justification", ""),
                })
        if resultats_valides:
            pistes_valides.append({
                "angle": piste.get("angle", ""),
                "resultats": resultats_valides,
            })

    register_ai_usage(request.user, web_search_used=web_search_a_ete_utilise)

    payload = {
        "fallback_to_tree": False,
        "besoin_clarification": False,
        "intention": resultat_ia.get("intention", ""),
        "message": resultat_ia.get("message", ""),
        "pistes": pistes_valides,
        "aucun_resultat": len(pistes_valides) == 0,
    }

    # Mise en cache : uniquement les reponses NON temporelles ET hors
    # conversation. Une recherche "ouvert maintenant" depend de l'heure, une
    # requete avec historique depend du fil -> jamais mises en cache. TTL 6h,
    # a ajuster selon la frequence de mise a jour de ton catalogue.
    if not ouvert and not history:
        cache.set(cache_key, payload, 60 * 60 * 6)

    return JsonResponse(payload)
    
@yuumi_plus_required
@login_required
def save_store_note(request, store_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    if not is_premium_user(request.user):
        return JsonResponse(
            {"error": "Cette fonctionnalité est réservée aux comptes Premium."},
            status=403,
        )

    store = get_object_or_404(Store, id=store_id)
    text = request.POST.get("text", "").strip()[:1000]

    StoreNote.objects.update_or_create(
        user=request.user,
        store=store,
        defaults={"text": text},
    )
    return JsonResponse({"text": text})

# ============================================================
#  PREMIUM — vues
#  (is_native_request, web_only, app_only, activer_premium sont
#   deja importes en haut du fichier — pas de re-import ici.)
# ============================================================
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt


# ---------- Pages affichées ----------

def premium_home(request):
    if is_native_request(request):
        return redirect("premium_app")
    return render(request, "members/premium_home.html", {
        "premium_price": None,  # TODO : fixer le vrai prix
    })


@web_only
def premium_web_checkout(request):
    return render(request, "members/premium_checkout.html", {"premium_price": None})


@web_only
def premium_web_success(request):
    return render(request, "members/premium_success.html")


@web_only
def premium_web_cancel(request):
    return render(request, "members/premium_cancel.html")


@app_only
def premium_app(request):
    # APP UNIQUEMENT — 404 si la requete vient du web.
    return HttpResponse("Premium — page dediee APP (placeholder IAP)")


# ---------- Déclenchement du paiement ----------

@web_only
@login_required
def premium_checkout_stripe(request):
    plan = request.GET.get("plan", "monthly")
    if plan == "annual":
        price_id = settings.STRIPE_PRICE_YUUMI_PLUS_ANNUEL
    else:
        price_id = settings.STRIPE_PRICE_YUUMI_PLUS_MENSUEL

    if not (settings.STRIPE_SECRET_KEY and price_id):
        return render(request, "members/premium_checkout.html", {
            "config_error": "Le paiement par carte n'est pas encore activé.",
        })

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=request.build_absolute_uri(reverse("premium_web_success")),
        cancel_url=request.build_absolute_uri(reverse("premium_web_cancel")),
        client_reference_id=str(request.user.id),
    )
    return redirect(session.url)


@web_only
def premium_checkout_paypal(request):
    if not (settings.PAYPAL_CLIENT_ID and settings.PAYPAL_PLAN_ID):
        return render(request, "members/premium_checkout.html", {
            "premium_price": None,
            "config_error": "Le paiement PayPal n'est pas encore activé.",
        })

    # TODO : POST /v1/billing/subscriptions, récupérer le lien "approve", y rediriger.
    return HttpResponse("TODO PayPal", status=501)


# ---------- Webhooks (appelés par les serveurs des prestataires) ----------

@csrf_exempt
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=503)
    import stripe
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        return HttpResponse(status=400)

    # ----------------------------------------------------------------
    # Activation initiale après paiement réussi
    # ----------------------------------------------------------------
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = getattr(session, "client_reference_id", None)
        sub_id = getattr(session, "subscription", None)
        price_id = None

        line_items = getattr(session, "line_items", None)
        if line_items is None:
            try:
                expanded = stripe.checkout.Session.retrieve(
                    session.id,
                    expand=["line_items"],
                )
                line_items = getattr(expanded, "line_items", None)
            except Exception:
                pass

        if line_items:
            try:
                price_id = line_items.data[0].price.id
            except Exception:
                pass

        PRICE_MAP = {
            settings.STRIPE_PRICE_YUUMI_PLUS_MENSUEL: ("yuumi_plus", "monthly"),
            settings.STRIPE_PRICE_YUUMI_PLUS_ANNUEL:  ("yuumi_plus", "annual"),
            settings.STRIPE_PRICE_PREMIUM_MENSUEL:    ("premium",    "monthly"),
            settings.STRIPE_PRICE_PREMIUM_ANNUEL:     ("premium",    "annual"),
        }
        tier, billing_period = PRICE_MAP.get(price_id, ("yuumi_plus", "monthly"))

        if user_id:
            from django.contrib.auth.models import User
            try:
                activer_premium(
                    User.objects.get(id=user_id),
                    source="stripe",
                    tier=tier,
                    billing_period=billing_period,
                    external_subscription_id=sub_id,
                )
            except User.DoesNotExist:
                pass

    # ----------------------------------------------------------------
    # Renouvellement mensuel/annuel automatique
    # ----------------------------------------------------------------
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        sub_id = getattr(invoice, "subscription", None)
        # On ne traite que les renouvellements (billing_reason == "subscription_cycle")
        # pas la première facture (déjà gérée par checkout.session.completed)
        billing_reason = getattr(invoice, "billing_reason", None)
        if sub_id and billing_reason == "subscription_cycle":
            from members.models import UserPremium
            try:
                premium = UserPremium.objects.get(external_subscription_id=sub_id)
                # Prolonge selon la périodicité déjà enregistrée
                duree = 365 if premium.billing_period == "annual" else 30
                activer_premium(
                    premium.user,
                    source="stripe",
                    tier=premium.tier,
                    billing_period=premium.billing_period,
                    duree_jours=duree,
                    external_subscription_id=sub_id,
                )
            except UserPremium.DoesNotExist:
                pass

    # ----------------------------------------------------------------
    # Résiliation : l'abonné a annulé ou le paiement a définitivement échoué
    # ----------------------------------------------------------------
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        sub_id = getattr(subscription, "id", None)
        if sub_id:
            from members.models import UserPremium
            try:
                premium = UserPremium.objects.get(external_subscription_id=sub_id)
                premium.is_active = False
                premium.save(update_fields=["is_active"])
            except UserPremium.DoesNotExist:
                pass

    return HttpResponse(status=200)
@csrf_exempt
def paypal_webhook(request):
    if not settings.PAYPAL_CLIENT_ID:
        return HttpResponse(status=503)

    try:
        event = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    # TODO : verifier l'evenement avant d'appeler activer_premium(..., source="paypal").
    return HttpResponse(status=200)

# ---------- Google Play : vérification d'achat côté app ----------

@app_only
@login_required
@csrf_exempt
def google_play_verify(request):
    """
    Reçoit le purchase_token envoyé par l'app après un achat Google Play
    (via @capgo/native-purchases), le vérifie auprès de l'API Google Play
    Developer, puis active le premium si l'achat est valide.

    csrf_exempt : l'app mobile appelle cet endpoint hors contexte
    navigateur classique, sans token CSRF disponible facilement.
    Ne fait JAMAIS confiance au token sans verify_google_purchase.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    purchase_token = request.POST.get("purchase_token", "").strip()
    product_id = request.POST.get("product_id", "").strip()

    if not purchase_token or not product_id:
        return JsonResponse({"error": "purchase_token et product_id requis"}, status=400)

    is_valid = verify_google_purchase(purchase_token, product_id)
    if not is_valid:
        return JsonResponse({"error": "Achat invalide"}, status=400)

    PRODUCT_MAP = {
        "yuumi_plus_monthly": ("yuumi_plus", "monthly"),
        "yuumi_plus_annual": ("yuumi_plus", "annual"),
    }
    tier, billing_period = PRODUCT_MAP.get(product_id, ("yuumi_plus", "monthly"))

    activer_premium(
        request.user,
        source="google_play",
        tier=tier,
        billing_period=billing_period,
        external_subscription_id=purchase_token,
    )

    return JsonResponse({"success": True})

@csrf_exempt
def google_play_rtdn(request):
    """
    Recoit les Real-Time Developer Notifications de Google Play via Pub/Sub
    (push). Le message contient un evenement d'abonnement (renouvellement,
    resiliation, remboursement, etc.) encode en base64 dans request.body.

    Format du payload Pub/Sub push :
    {
      "message": {
        "data": "<base64 JSON>",
        "messageId": "...",
        "publishTime": "..."
      },
      "subscription": "..."
    }

    Le JSON decode contient notamment subscriptionNotification avec
    purchaseToken et notificationType (cf. doc Google RTDN).
    """
    import base64
    import logging
    from members.models import UserPremium
    from members.utils import verify_pubsub_token

    logger = logging.getLogger(__name__)

    if request.method != "POST":
        return HttpResponse(status=405)

    logger.error(f"DEBUG headers RTDN : {dict(request.headers)}")

    if not verify_pubsub_token(request):
        return HttpResponse(status=401)

    try:
        envelope = json.loads(request.body)
        message_data = envelope["message"]["data"]
        decoded = base64.b64decode(message_data).decode("utf-8")
        notification = json.loads(decoded)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"RTDN Google Play : payload invalide - {e}")
        return HttpResponse(status=200)

    sub_notif = notification.get("subscriptionNotification")
    if not sub_notif:
        return HttpResponse(status=200)

    purchase_token = sub_notif.get("purchaseToken")
    notification_type = sub_notif.get("notificationType")

    TYPES_DESACTIVATION = {3, 13, 12}
    TYPES_RENOUVELLEMENT = {2, 4}

    try:
        premium = UserPremium.objects.get(external_subscription_id=purchase_token)
    except UserPremium.DoesNotExist:
        logger.warning(f"RTDN Google Play : token inconnu - {purchase_token}")
        return HttpResponse(status=200)

    if notification_type in TYPES_DESACTIVATION:
        premium.is_active = False
        premium.save(update_fields=["is_active"])
    elif notification_type in TYPES_RENOUVELLEMENT:
        from members.utils import activer_premium
        duree = 365 if premium.billing_period == "annual" else 30
        activer_premium(
            premium.user,
            source="google_play",
            tier=premium.tier,
            billing_period=premium.billing_period,
            duree_jours=duree,
            external_subscription_id=purchase_token,
        )

    return HttpResponse(status=200)
