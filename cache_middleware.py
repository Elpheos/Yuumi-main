# members/cache_middleware.py


class NoCacheHTMLMiddleware:
    """
    Force le navigateur à ne jamais mettre en cache les pages HTML.
    Les fichiers statiques (CSS, JS) restent cachés longtemps via
    WhiteNoise (leurs URLs contiennent un hash qui change à chaque
    collectstatic).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        content_type = response.get("Content-Type", "")
        if "text/html" in content_type:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
