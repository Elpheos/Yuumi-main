from PIL import Image
import io
from functools import wraps
from django.core.files.base import ContentFile
from django.http import Http404

# Limites Yuumi+
YUUMI_PLUS_WISHLIST_LIMIT = 10
YUUMI_PLUS_UNFAVORIS_LIMIT = 10

def resize_and_convert(image_file, name, max_width=None):
    """
    Convertit une image en WebP, la redimensionne si nécessaire
    en conservant les proportions, et lui donne un nom personnalisé.
    """
    img = Image.open(image_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    # Redimensionner si max_width est défini et que l'image est plus large
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)
    output = io.BytesIO()
    img.save(output, format='WEBP', quality=80)
    output.seek(0)
    return ContentFile(output.read(), name=f"{name}.webp")


def convert_to_webp(image_file):
    """Compatibilité avec l'ancien code — conserve le nom original."""
    original_name = image_file.name.rsplit('.', 1)[0]
    return resize_and_convert(image_file, name=original_name)


def is_native_request(request):
    """
    True si la requete vient de l'app mobile Capacitor (et non du web).
    L'app ajoute 'YuumiNativeApp' a son User-Agent via appendUserAgent.
    """
    ua = request.META.get("HTTP_USER_AGENT", "")
    return "YuumiNativeApp" in ua


def web_only(view_func):
    """
    Decorateur : 404 si la requete vient de l'app mobile Capacitor.
    Reserve les pages de paiement WEB (Stripe) au navigateur. C'est le
    verrou cote serveur : meme en tapant l'URL a la main dans l'app,
    l'acces est refuse.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if is_native_request(request):
            raise Http404()
        return view_func(request, *args, **kwargs)
    return _wrapped


def app_only(view_func):
    """
    Decorateur : 404 si la requete vient du web. Reserve la page premium
    dediee a l'app (IAP). Le web ne peut jamais l'ouvrir.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_native_request(request):
            raise Http404()
        return view_func(request, *args, **kwargs)
    return _wrapped

from datetime import timedelta
from django.utils import timezone


def activer_premium(user, source, billing_period="monthly", tier="yuumi_plus",
                    duree_jours=None, external_subscription_id=None):
    """
    Active (ou prolonge) le premium d'un utilisateur. Point d'entree UNIQUE
    appele apres un paiement verifie — quel que soit le prestataire. Ne fait
    JAMAIS confiance au client : a appeler uniquement cote serveur, apres
    validation reelle du paiement.
    """
    from members.models import UserPremium

    # Durée selon la périodicité, sauf si forcée manuellement via duree_jours
    if duree_jours is None:
        duree_jours = 365 if billing_period == "annual" else 30

    premium, _ = UserPremium.objects.get_or_create(user=user)
    premium.is_active = True
    premium.payment_provider = source
    premium.tier = tier
    premium.billing_period = billing_period

    if external_subscription_id:
        premium.external_subscription_id = external_subscription_id

    if duree_jours is None:
        premium.expires_at = None
    else:
        base = premium.expires_at
        if base is None or base < timezone.now():
            base = timezone.now()
        premium.expires_at = base + timedelta(days=duree_jours)

    premium.save()
    return premium

from functools import wraps

def yuumi_plus_required(view_func):
    """
    Restreint l'acces aux abonnes Yuumi+.
    - Vue HTML  → redirige vers la page premium
    - Vue JSON  → retourne 403 avec message
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not is_premium_user(request.user):
            is_json = (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if is_json:
                from django.http import JsonResponse
                return JsonResponse(
                    {"error": "Fonctionnalité réservée aux abonnés Yuumi+",
                     "premium_required": True},
                    status=403,
                )
            from django.shortcuts import redirect
            return redirect("premium_home")
        return view_func(request, *args, **kwargs)
    return wrapper
