from pathlib import Path
import os
from dotenv import load_dotenv, find_dotenv
from django.urls import reverse_lazy
import logging
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration  # if you use Celery
from sentry_sdk.integrations.logging import LoggingIntegration

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent          # …/subdiaries_project
BASE_DIR    = PROJECT_DIR.parent                       # repo root (where manage.py lives)
REPO_ROOT   = BASE_DIR

# ── .env loading (next to manage.py unless ENV_FILE overrides) ─────────────────
ENV_FILE = os.getenv("ENV_FILE")
if ENV_FILE and Path(ENV_FILE).exists():
    env_path = ENV_FILE
else:
    candidate = REPO_ROOT / ".env"
    env_path = str(candidate) if candidate.exists() else find_dotenv(usecwd=True)

load_dotenv(env_path, override=True)

def get_bool(name: str, default=False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

# ── Core ───────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = get_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv(
        "DJANGO_ALLOWED_HOSTS",  # primary key
        os.getenv("ALLOWED_HOSTS", "journal.adamkaney.com,adamkaney.com,www.adamkaney.com,127.0.0.1,localhost")
    ).split(",") if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://journal.adamkaney.com,https://adamkaney.com,https://www.adamkaney.com,"
        "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "journal.apps.JournalConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "subdiaries_project.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "journal.context_processors.org_and_role",
    ]},
}]
WSGI_APPLICATION = "subdiaries_project.wsgi.application"

# ── Security (prod) ────────────────────────────────────────────────────────────
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

# ── Database ───────────────────────────────────────────────────────────────────
# Default to MySQL (prod); auto-switch to SQLite in dev unless overridden.
MYSQL_CFG_PRESENT = all(os.getenv(k) for k in ["MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"])
USE_SQLITE = get_bool("USE_SQLITE", False)

if DEBUG and (USE_SQLITE or not MYSQL_CFG_PRESENT):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DATABASE", "journal"),
            "USER": os.getenv("MYSQL_USER", "journal"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", "changeme"),
            "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"
            },
        }
    }

# ── Locale ─────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

# ── Static & media ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")     # <-- match Nginx alias
STATICFILES_DIRS = [BASE_DIR / "static"]   # source assets (only if this folder exists)

# ensure default finders are on
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media") if DEBUG else "/srv/subdiaries/media")

# ── Auth redirects ─────────────────────────────────────────────────────────────
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = reverse_lazy("journal:profile")
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ── Email ──────────────────────────────────────────────────────────────────────
if DEBUG and not os.getenv("EMAIL_BACKEND"):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "you@example.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "app-password")
EMAIL_USE_TLS = get_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Subdiaries <no-reply@yourdomain>")
SITE_NAME = os.getenv("SITE_NAME", "Subdiaries")

# ── Celery (optional) ──────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_TASK_ALWAYS_EAGER = get_bool("CELERY_TASK_ALWAYS_EAGER", False)

# ── Feature flags ──────────────────────────────────────────────────────────────
ALLOW_SELF_REGISTER = get_bool("ALLOW_SELF_REGISTER", False)
ENABLE_BILLING = get_bool("ENABLE_BILLING", False)
BILLING_MODE = os.getenv("BILLING_MODE", "per_moderator")
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "14"))
GRACE_DAYS = int(os.getenv("GRACE_DAYS", "7"))

# Sentry only if DSN is present
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),                      # remove if not using Celery
            LoggingIntegration(
                level=logging.INFO,                   # breadcrumbs: INFO+ logs
                event_level=logging.ERROR,            # send events for ERROR+
            ),
        ],
        # Perf monitoring (tune these!)
        traces_sample_rate=0.1,                        # 10% of requests
        profiles_sample_rate=0.1,                      # 10% profiling

        # Useful metadata
        environment=os.getenv("SENTRY_ENV", "development"),
        release=os.getenv("SENTRY_RELEASE"),

        # Privacy: send user info only if you’re comfortable
        send_default_pii=False,
    )

    # Optional: scrub/deny-list events
    # def before_send(event, hint):
    #     # e.g., drop noisy 404s
    #     if event.get("exception"):
    #         exc = event["exception"]["values"][-1]["type"]
    #         if exc in {"Http404"}:
    #             return None
    #     return event
    # sentry_sdk.Hub.current.client.options["before_send"] = before_send