import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "accounts",
    "core",
    "complaints",
]

AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "cms"),
        "USER": os.environ.get("POSTGRES_USER", "cms"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "cms"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "media/"
ATTACHMENT_MAX_MB = int(os.environ.get("ATTACHMENT_MAX_MB", "5"))
ATTACHMENT_MAX_FILES = int(os.environ.get("ATTACHMENT_MAX_FILES", "5"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 40 * 1024 * 1024

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o
]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"public_submit": "10/hour", "track": "30/hour", "login": "10/minute", "captcha": "60/hour", "password_reset": "10/hour", "password_reset_verify": "40/hour", "cid_lookup": "20/hour"},
}

# --- Security ---
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", 8 * 3600))
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"

# BCRS (citizen registry) lookup used to fill the complainant's name from the CID. See core/bcrs.py.
BCRS_API_URL = os.environ.get("BCRS_API_URL", "")
BCRS_API_METHOD = os.environ.get("BCRS_API_METHOD", "GET")
BCRS_AUTH_HEADER = os.environ.get("BCRS_AUTH_HEADER", "Authorization")
BCRS_API_TOKEN = os.environ.get("BCRS_API_TOKEN", "")
# ZESt (employee directory): only reachability is checked until its API details are known.
ZEST_API_URL = os.environ.get("ZEST_API_URL", "")
ZEST_AUTH_HEADER = os.environ.get("ZEST_AUTH_HEADER", "Authorization")
ZEST_API_TOKEN = os.environ.get("ZEST_API_TOKEN", "")
BCRS_TOKEN_URL = os.environ.get("BCRS_TOKEN_URL", "")
BCRS_CLIENT_ID = os.environ.get("BCRS_CLIENT_ID", "")
BCRS_CLIENT_SECRET = os.environ.get("BCRS_CLIENT_SECRET", "")

# Account recovery and persistent sign-in.
REMEMBER_ME_AGE = 30 * 24 * 3600
PASSWORD_RESET_TIMEOUT = 3600
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "BICMA <noreply@example.org>")


# Bhutan NDI (National Digital Identity) staff sign-in: proof request + QR, result delivered over NATS. See core/ndi.py.
# The client id / secret and the NATS seed key are secrets: set them in .env, never in the code.
NDI = {
    "NATS_HOST": (os.environ.get("NDI_NATS_HOST") or "https://natsdemoclient.bhutanndi.com"),
    "NATS_PORT": int(os.environ.get("NDI_NATS_PORT") or "4222"),
    "NATS_SEED": (os.environ.get("NDI_NATS_SEED_KEY") or ""),
    "AUTH_ENDPOINT": (os.environ.get("NDI_API_AUTH_ENDPOINT") or "https://staging.bhutanndi.com/authentication/v1/authenticate"),
    "API_HOST": (os.environ.get("NDI_API_HOST") or "https://demo-client.bhutanndi.com"),
    "CLIENT_ID": (os.environ.get("NDI_API_CLIENT_ID") or ""),
    "CLIENT_SECRET": (os.environ.get("NDI_API_CLIENT_SECRET") or ""),
    "GRANT_TYPE": (os.environ.get("NDI_API_GRANT_TYPE") or "client_credentials"),
    "FOUNDATIONAL_ID_CRED_DEF_ID": (os.environ.get("NDI_FOUNDATIONAL_ID_CRED_DEF_ID")
                                    or "https://schema.ngotag.com/schemas/fb675203-b317-4675-a657-be7f5d1d57fb"),
    "LOGIN_ATTRIBUTES": ["ID Number", "Full Name"],
    "PROOF_TTL_SECONDS": int((os.environ.get("NDI_PROOF_TTL_SECONDS") or "300")),
}
