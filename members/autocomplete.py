from dal import autocomplete
from .models import Store


# 🔹 Autocomplétion département
class DepartementAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        return list(
            Store.objects.order_by('departement')
            .values_list('departement', flat=True)
            .distinct()
        )


# 🔹 Autocomplétion ville (filtrée par département)
class VilleAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        qs = Store.objects.order_by('ville')
        departement = self.forwarded.get('departement', None)  # 🔸 récupère le département choisi

        if departement:
            qs = qs.filter(departement__iexact=departement)

        return list(qs.values_list('ville', flat=True).distinct())


# 🔹 Autocomplétion catégorie
class CategorieAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        return list(
            Store.objects.order_by('categorie')
            .values_list('categorie', flat=True)
            .distinct()
        )
