
from .base import *
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1","localhost","10.6.83.234"]
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True

# Use SQLite for dev out-of-the-box
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
