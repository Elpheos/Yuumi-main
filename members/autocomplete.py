from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Store


# 🔹 Autocomplétion département
# LoginRequiredMixin : seuls les utilisateurs connectés peuvent interroger ces endpoints.
# Sans ça, n'importe qui peut énumérer tous les départements/villes/catégories en base.
class DepartementAutocomplete(LoginRequiredMixin, autocomplete.Select2ListView):
    def get_list(self):
        return list(
            Store.objects.order_by('departement')
            .values_list('departement', flat=True)
            .distinct()
        )


# 🔹 Autocomplétion ville (filtrée par département)
class VilleAutocomplete(LoginRequiredMixin, autocomplete.Select2ListView):
    def get_list(self):
        qs = Store.objects.order_by('ville')
        departement = self.forwarded.get('departement', None)

        if departement:
            qs = qs.filter(departement__iexact=departement)

        return list(qs.values_list('ville', flat=True).distinct())


# 🔹 Autocomplétion catégorie
class CategorieAutocomplete(LoginRequiredMixin, autocomplete.Select2ListView):
    def get_list(self):
        return list(
            Store.objects.order_by('categorie')
            .values_list('categorie', flat=True)
            .distinct()
        )
