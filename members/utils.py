# members/utils.py

from PIL import Image
import io
from django.core.files.base import ContentFile


def convert_to_webp(image_file):
    """
    Prend un fichier image uploadé et le convertit en WebP.
    Retourne un ContentFile prêt à être sauvegardé par Django.
    """
    img = Image.open(image_file)

    # Convertir en RGB si nécessaire (ex: PNG avec transparence)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format='WEBP', quality=80)
    output.seek(0)

    # Nouveau nom avec extension .webp
    original_name = image_file.name.rsplit('.', 1)[0]
    new_name = f"{original_name}.webp"

    return ContentFile(output.read(), name=new_name)
