from django.contrib.sitemaps import Sitemap
from .models import Commerce

class CommerceSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Commerce.objects.all()
