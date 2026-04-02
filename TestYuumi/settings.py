"""
Django settings for Yuumi project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------
# Chargement du fichier .env (sans dépendance externe)
# -------------------------------------------------------------------
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


# -------------------------------------------------------------------
# SÉCURITÉ
# -------------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY manquante — vérifiez votre fichier .env")

DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost"
    ).split(",")
    if h.strip()
]


# -------------------------------------------------------------------
# Applications
# -------------------------------------------------------------------

INSTALLED_APPS = [
    # Django Autocomplete Light — doit être avant contrib.admin
    "dal",
    "dal_select2",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Projet
    "members",

    # Third-party
    "nested_admin",
    "django_extensions",
]


# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise doit être juste après SecurityMiddleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # No-cache sur les pages HTML (évite le cache navigateur mobile)
    "members.cache_middleware.NoCacheHTMLMiddleware",
]


# -------------------------------------------------------------------
# URLs & Templates
# -------------------------------------------------------------------

ROOT_URLCONF = "TestYuumi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "members.context_processors.menu_context",
            ],
        },
    },
]

WSGI_APPLICATION = "TestYuumi.wsgi.application"


# -------------------------------------------------------------------
# Base de données
# -------------------------------------------------------------------

_db_engine = os.environ.get("DB_ENGINE", "sqlite3")

if _db_engine == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "yuumi"),
            "USER": os.environ.get("DB_USER", "yuumi"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# -------------------------------------------------------------------
# Validation des mots de passe
# -------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# -------------------------------------------------------------------
# Internationalisation
# -------------------------------------------------------------------

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True


# -------------------------------------------------------------------
# Fichiers statiques & médias
# -------------------------------------------------------------------

STATIC_URL = "/static/"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

STATICFILES_DIRS = [
    BASE_DIR / "static",
    BASE_DIR / "members" / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -------------------------------------------------------------------
# Email
# -------------------------------------------------------------------

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "mail.infomaniak.com")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "contact@yuumi-shop.com")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@yuumi-shop.com")


# -------------------------------------------------------------------
# Sécurité CSRF / cookies
# -------------------------------------------------------------------

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]

CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# En production : HSTS
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True


# -------------------------------------------------------------------
# Authentification
# -------------------------------------------------------------------

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
