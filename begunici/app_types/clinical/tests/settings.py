"""Isolated tests and preview: no .env and no connection to the farm database."""
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parents[4]
SECRET_KEY = "clinical-disposable-tests-only"
DEBUG = True
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
ROOT_URLCONF = "begunici.urls"
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "begunici.app_types.animals", "begunici.app_types.veterinary", "begunici.app_types.inventory",
    "begunici.app_types.feed_inventory", "begunici.app_types.vet_inventory", "begunici.app_types.clinical",
    "begunici.app_types.public_site", "rest_framework",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "HOST": "clinical-db", "NAME": "clinical_sandbox", "USER": "clinical_test", "PASSWORD": "", "PORT": "5432"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "Europe/Moscow"
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "begunici" / "static"]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "begunici.app_types.vet_inventory.middleware.VetInventoryActorMiddleware",
    "begunici.app_types.public_site.middleware.LoginRequiredExceptPublicMiddleware",
    "begunici.app_types.animals.middleware.UserActionLogMiddleware",
]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "begunici" / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": [
    "django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "begunici.app_types.animals.context_processors.user_permissions",
]}}]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"]}
LOGIN_URL = "/login/"
TEST_RUNNER = "begunici.app_types.clinical.tests.runner.IsolatedRunner"
