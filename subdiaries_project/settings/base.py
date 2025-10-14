
from pathlib import Path
import os
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = "127.0.0.1,localhost,10.6.83.234,10.6.83.235".split(",")


CSRF_TRUSTED_ORIGINS = [u.strip() for u in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if u.strip()]
INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "journal",
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
    "BACKEND":"django.template.backends.django.DjangoTemplates",
    "DIRS":[BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS":{"context_processors":[
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "journal.context_processors.org_and_role",
    ]},
}]
WSGI_APPLICATION = "subdiaries_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE","journal"),
        "USER": os.environ.get("MYSQL_USER","journal"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD","changeme"),
        "HOST": os.environ.get("MYSQL_HOST","127.0.0.1"),
        "PORT": os.environ.get("MYSQL_PORT","3306"),
        "OPTIONS": {"charset":"utf8mb4","init_command":"SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator","OPTIONS":{"min_length":8}},
    {"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = STATIC_ROOT = "/srv/subdiaries/static" 
STATICFILES_DIRS = [p for p in [BASE_DIR / "static"] if p.exists()]
MEDIA_URL = "/media/"
MEDIA_ROOT = "/srv/subdiaries/media"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND","django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST","smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT","587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER","you@example.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD","app-password")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL","Tabbed Journal <no-reply@yourdomain>")
SITE_NAME = os.environ.get("SITE_NAME","Tabbed Journal")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL","redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND","redis://127.0.0.1:6379/1")
CELERY_TASK_ALWAYS_EAGER = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO","https")
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Feature flags
ALLOW_SELF_REGISTER = os.environ.get("ALLOW_SELF_REGISTER","0") in ("1","true","True")
ENABLE_BILLING = os.environ.get("ENABLE_BILLING","0") in ("1","true","True")
BILLING_MODE = os.environ.get("BILLING_MODE","per_moderator")
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS","14"))
GRACE_DAYS = int(os.environ.get("GRACE_DAYS","7"))
