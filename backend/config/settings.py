from pathlib import Path
from urllib.parse import urlparse, unquote
import os

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only-change-before-deploy")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
if not DEBUG and SECRET_KEY == "local-development-only-change-before-deploy":
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a long random value when DJANGO_DEBUG is false.")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "air_quality",
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

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def database_config():
    raw = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/atmoiq"
    )

    parsed = urlparse(raw)

    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError(
            "DATABASE_URL must be a PostgreSQL URL"
        )

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "localhost",
            "PORT": parsed.port or 5432,
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "connect_timeout": 10,
                "sslmode": os.getenv("DB_SSLMODE", "require"),
            },
        }
    }


DATABASES = database_config()
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATA_GOV_IN_API_KEY = os.getenv("DATA_GOV_IN_API_KEY", "").strip()
DATA_GOV_IN_RESOURCE_ID = os.getenv("DATA_GOV_IN_RESOURCE_ID", "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69").strip()
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "").strip()
def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (ROOT_DIR / path).resolve()


ML_ARTIFACT_PATH = project_path(os.getenv("ML_ARTIFACT_PATH", "ml/artifacts/atmoiq_models.joblib"))
ML_METRICS_PATH = project_path(os.getenv("ML_METRICS_PATH", "ml/artifacts/metrics.json"))
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
