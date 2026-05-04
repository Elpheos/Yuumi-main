# members/check_adresses.py
# Lancer avec : python manage.py runscript check_adresses

import re
from members.models import Store

def run():
    stores = Store.objects.exclude(addressemaps="").exclude(addressemaps__isnull=True)

    sans_numero      = []
    avec_bis_b       = []
    avec_abreviation = []

    for store in stores:
        adresse = store.addressemaps.strip()

        # Pas de chiffre au début de l'adresse → probablement sans numéro de rue
        if not re.match(r"^\d", adresse):
            sans_numero.append(store)

        # Contient "bis" ou une lettre collée au numéro (ex: 12b, 12B)
        if re.search(r"\bbis\b", adresse, re.IGNORECASE) or re.search(r"\d+\s*[bB]\b", adresse):
            avec_bis_b.append(store)

        # Contient un point qui ressemble à une abréviation (ex: "Av.", "Bd.", "St.")
        if re.search(r"\b[A-Za-z]{1,4}\.", adresse):
            avec_abreviation.append(store)

    # --- Affichage ---

    print("\n" + "="*60)
    print(f"🔴 SANS NUMÉRO DE RUE ({len(sans_numero)} commerces)")
    print("="*60)
    for s in sans_numero:
        print(f"  {s.nom} ({s.ville}) → {s.addressemaps}")

    print("\n" + "="*60)
    print(f"🟡 AVEC BIS / B ({len(avec_bis_b)} commerces)")
    print("="*60)
    for s in avec_bis_b:
        print(f"  {s.nom} ({s.ville}) → {s.addressemaps}")

    print("\n" + "="*60)
    print(f"🟠 AVEC ABRÉVIATION ({len(avec_abreviation)} commerces)")
    print("="*60)
    for s in avec_abreviation:
        print(f"  {s.nom} ({s.ville}) → {s.addressemaps}")

    print("\n" + "="*60)
    print(f"✅ Total analysé : {stores.count()} commerces")
    print("="*60 + "\n")
