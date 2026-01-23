from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views   # ✅ import
import os

def my_serve(request, path, document_root):
    from django.http import HttpResponse, Http404
    import mimetypes
    print(f"Document root: {document_root}")
    print(f"Path: {path}")
    path = path.lstrip('/')
    print(f"After lstrip: {path}")
    path = os.path.normpath(path)
    print(f"Normalized path: {path}")
    if path.startswith('/') or '..' in path:
        raise Http404
    fullpath = os.path.join(document_root, path)
    print(f"Fullpath: {fullpath}, exists: {os.path.exists(fullpath)}")
    if not os.path.exists(fullpath):
        raise Http404
    if not os.path.isfile(fullpath):
        raise Http404
    with open(fullpath, 'rb') as f:
        content = f.read()
    content_type, encoding = mimetypes.guess_type(fullpath)
    response = HttpResponse(content, content_type=content_type)
    if encoding:
        response['Content-Encoding'] = encoding
    return response

urlpatterns = static(settings.STATIC_URL, document_root=str(settings.STATIC_ROOT)) + [re_path(r'^media(?P<path>.*)$', my_serve, {'document_root': str(settings.MEDIA_ROOT)})] + [
    path('admin/', admin.site.urls),
    path('', include('members.urls')),

    # ✅ Authentification
    path("login/", auth_views.LoginView.as_view(template_name="members/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
]
