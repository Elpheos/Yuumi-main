from PIL import Image
import io
from functools import wraps
from django.core.files.base import ContentFile
from django.http import Http404


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
