from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

# Project root (manage.py turgan papka)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# .env ni yuklaymiz
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "rest_framework_simplejwt",

    # CORS (frontend domenlardan API'ga ruxsat berish uchun)
    "corsheaders",

    "users",
    "catalog",
    "cart",
    "orders",
    "payments",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -----------------
# CORS CONFIG
# -----------------
# Agar frontend alohida domen/portda bo'lsa (masalan: http://localhost:3000),
# shu yerda ruxsat beriladi.

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_origin(origin: str) -> str:
    o = origin.strip()
    if not o:
        return ""
    # Agar scheme yo'q bo'lsa, http:// qo'shamiz
    if "://" not in o:
        o = f"http://{o}"
    return o


# Default: DEBUG bo'lsa allow-all (dev uchun qulay)
CORS_ALLOW_ALL_ORIGINS = _env_bool("CORS_ORIGIN_ALLOW_ALL", default=DEBUG)

_whitelist = os.getenv("CORS_ORIGIN_WHITELIST", "")
_origins = [_normalize_origin(x) for x in _whitelist.split(",")]
CORS_ALLOWED_ORIGINS = [x for x in _origins if x]

# Cookie/JWT refresh kabi credential ishlatsangiz kerak bo'lishi mumkin
CORS_ALLOW_CREDENTIALS = _env_bool("CORS_ALLOW_CREDENTIALS", default=True)

ROOT_URLCONF = "karzina.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "karzina.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}"),
        conn_max_age=60,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tashkent"
USE_TZ = True
USE_I18N = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema"}

REST_FRAMEWORK.update({
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
})

REST_FRAMEWORK.update({
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # xohlasangiz admin session ham qolsin:
        "rest_framework.authentication.SessionAuthentication",
    ),
})

SPECTACULAR_SETTINGS = {
    "TITLE": "Karzinka API",
    "DESCRIPTION": "Karzinka backend API documentation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


 # Basic auth decoded string (login:password)
PAYME_BASIC_AUTH = "Paycom:YOUR_KEY"

# -----------------
# CLICK (SHOP API)
# -----------------
# Click'ni ulash uchun kerak bo'ladigan qiymatlar.
# Hozircha sizda kalitlar yo'q bo'lsa ham, Click endpointlar DEBUG=True rejimida
# "mock" tarzda ishlashi mumkin (signature tekshiruvi o'chiriladi).

CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")

# Prod'da (DEBUG=False) signature tekshiruvni majburiy qilamiz.
CLICK_REQUIRE_SIGNATURE = _env_bool("CLICK_REQUIRE_SIGNATURE", default=not DEBUG)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}


