"""
Django settings for Yuumi project.
"""

from pathlib import Path
from datetime import timedelta
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
GOOGLE_PLAY_SERVICE_ACCOUNT_PATH = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_PATH")
GOOGLE_PLAY_PACKAGE_NAME = os.environ.get("GOOGLE_PLAY_PACKAGE_NAME", "com.yuumi.app")

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
    "axes",

    # Projet
    "members",

    # Third-party
    "nested_admin",
    "django_extensions",
    "django.contrib.sitemaps",
    'simple_history',

    # ✅ NOUVEAU — API biométrie
    'rest_framework',
    'corsheaders',

    "yuumi2",
]


# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------

MIDDLEWARE = [
    # ✅ NOUVEAU — CorsMiddleware doit être en premier
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "cache_middleware.LowercaseURLMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "members.cache_middleware.NoCacheHTMLMiddleware",
    "axes.middleware.AxesMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
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
                'members.context_processors.ai_agent_visible', 
                'members.context_processors.premium_context',
                'members.context_processors.native_context',
            ],
        },
    },
]

WSGI_APPLICATION = "TestYuumi.wsgi.application"

# -------------------------------------------------------------------
# Cache (partagé entre les workers Gunicorn via Redis)
# -------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
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
# Limite uploads : 1 Mo max par fichier
DATA_UPLOAD_MAX_MEMORY_SIZE = 1 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

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
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'django_errors.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

# -------------------------------------------------------------------
# Authentification
# -------------------------------------------------------------------

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = 'https://yuumi-shop.com/'
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# -------------------------------------------------------------------
# django-axes (protection brute force)
# -------------------------------------------------------------------
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_CALLABLE = None


# -------------------------------------------------------------------
# ✅ NOUVEAU — Django REST Framework
# -------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}


# -------------------------------------------------------------------
# ✅ NOUVEAU — JWT (tokens biométrie)
# -------------------------------------------------------------------

SIMPLE_JWT = {
    # Access token court (utilisé pour valider la biométrie)
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10),
    # Refresh token long — stocké dans le Keychain natif de l'app
    # 90 jours : l'utilisateur n'a pas à retaper son mot de passe pendant 3 mois
    'REFRESH_TOKEN_LIFETIME': timedelta(days=90),
    'ROTATE_REFRESH_TOKENS': True,       # Nouveau refresh token à chaque usage
    'BLACKLIST_AFTER_ROTATION': False,   # Pas de blacklist (pas de BDD extra)
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# -------------------------------------------------------------------
# ✅ NOUVEAU — CORS (autorise l'app Capacitor à appeler l'API)
# -------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = [
    "https://yuumi-shop.com",
    "capacitor://localhost",   # Android Capacitor
    "http://localhost",        # iOS Capacitor
]

# L'app Capacitor n'envoie pas de cookies cross-origin, c'est OK
CORS_ALLOW_CREDENTIALS = False

import firebase_admin
from firebase_admin import credentials


_firebase_creds_path = BASE_DIR / 'firebase-credentials.json'
if _firebase_creds_path.exists() and not firebase_admin._apps:
    _cred = credentials.Certificate(str(_firebase_creds_path))
    firebase_admin.initialize_app(_cred)

# ===== PAIEMENT PREMIUM =====
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Yuumi+
STRIPE_PRICE_YUUMI_PLUS_MENSUEL = os.environ.get("STRIPE_PRICE_YUUMI_PLUS_MENSUEL", "")
STRIPE_PRICE_YUUMI_PLUS_ANNUEL = os.environ.get("STRIPE_PRICE_YUUMI_PLUS_ANNUEL", "")

# Yuumi Premium (à venir)
STRIPE_PRICE_PREMIUM_MENSUEL = os.environ.get("STRIPE_PRICE_PREMIUM_MENSUEL", "")
STRIPE_PRICE_PREMIUM_ANNUEL = os.environ.get("STRIPE_PRICE_PREMIUM_ANNUEL", "")

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_PLAN_ID = os.environ.get("PAYPAL_PLAN_ID", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
