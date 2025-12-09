# members/geocode_stores.py

from members.models import Store
from geopy.geocoders import Nominatim
import time

def run():
    geolocator = Nominatim(user_agent="yuumi_geocoder")
    stores = Store.objects.all()

    for store in stores:
        # Ne géocode que si addressemaps existe et que lat/lon sont vides
        if store.addressemaps and (store.latitude is None or store.longitude is None):
            try:
                location = geolocator.geocode(store.addressemaps)
                if location:
                    store.latitude = location.latitude
                    store.longitude = location.longitude
                    store.save()
                    print(f"{store.nom} géocodé : {store.latitude}, {store.longitude}")
                else:
                    print(f"{store.nom} : géocodage impossible")
            except Exception as e:
                print(f"Erreur pour {store.nom} : {e}")
            # Pause 1 seconde pour ne pas saturer le service
            time.sleep(1)

if __name__ == "__main__":
    run()
