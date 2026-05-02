from PIL import Image
import io
from django.core.files.base import ContentFile


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
