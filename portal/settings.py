import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ["RELAY_PORTAL_STATE"]).resolve()
if STATE == ROOT.parent or ROOT.parent in STATE.parents:
    raise RuntimeError("Keep portal state outside the checkout")
CONFIG = json.loads((STATE / "settings.json").read_text(encoding="utf-8"))
SECRET_KEY = CONFIG["secret"]
BASE = CONFIG["origin"].rstrip("/")
ORIGIN = urlsplit(BASE)
LOCAL = ORIGIN.hostname in ("127.0.0.1", "localhost")
if (
    not ORIGIN.hostname
    or ORIGIN.username
    or ORIGIN.password
    or ORIGIN.path
    or ORIGIN.query
    or ORIGIN.fragment
    or (ORIGIN.scheme != "https" and not (LOCAL and ORIGIN.scheme == "http"))
):
    raise RuntimeError("A dedicated HTTPS origin or a loopback development origin is required")
ALLOWED_HOSTS = [ORIGIN.hostname, "127.0.0.1", "localhost"]
DEBUG = False
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "portal",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "portal.views"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
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
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": STATE / "portal.sqlite3",
        "OPTIONS": {"timeout": 8, "transaction_mode": "IMMEDIATE"},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation." + name}
    for name in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]
STATIC_URL = "/static/"
STATIC_ROOT = STATE / "static"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not LOCAL
SESSION_COOKIE_SAMESITE = "Strict"
SECURE_REFERRER_POLICY = "no-referrer"
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 32
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"discard": {"class": "logging.NullHandler"}},
    "loggers": {
        "django.request": {"handlers": ["discard"], "propagate": False},
        "django.security": {"handlers": ["discard"], "propagate": False},
    },
}
