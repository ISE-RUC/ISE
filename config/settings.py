"""
Django settings for ISE platform.
"""
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

SECRET_KEY = 'django-insecure-change-this-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # project apps
    'apps.users',
    'apps.qa',
    'apps.party',
    'apps.certificate',
    'apps.notification',
    'apps.profile',
    'apps.workflow',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.users.middleware.AuditLogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

def _build_postgresql_config():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme in {"postgres", "postgresql"}:
            if not parsed.path.lstrip("/"):
                raise ImproperlyConfigured("DATABASE_URL 缺少数据库名。")
            if not parsed.username:
                raise ImproperlyConfigured("DATABASE_URL 缺少数据库用户名。")
            config = {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": unquote(parsed.path.lstrip("/")),
                "USER": unquote(parsed.username),
                "PASSWORD": unquote(parsed.password or ""),
                "HOST": parsed.hostname or "127.0.0.1",
                "PORT": str(parsed.port or "5432"),
                "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            }
            sslmode = os.getenv("DB_SSLMODE", "").strip()
            if sslmode:
                config["OPTIONS"] = {"sslmode": sslmode}
            return config

    db_name = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB")
    db_user = os.getenv("DB_USER") or os.getenv("POSTGRES_USER")
    db_password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD")
    db_host = os.getenv("DB_HOST") or os.getenv("POSTGRES_HOST")
    db_port = os.getenv("DB_PORT") or os.getenv("POSTGRES_PORT")

    missing = []
    if not db_name:
        missing.append("DB_NAME/POSTGRES_DB")
    if not db_user:
        missing.append("DB_USER/POSTGRES_USER")
    if db_password is None:
        missing.append("DB_PASSWORD/POSTGRES_PASSWORD")
    if not db_host:
        missing.append("DB_HOST/POSTGRES_HOST")
    if not db_port:
        missing.append("DB_PORT/POSTGRES_PORT")
    if missing:
        raise ImproperlyConfigured(
            "PostgreSQL 配置不完整，缺少环境变量: " + ", ".join(missing)
        )

    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_password,
        "HOST": db_host,
        "PORT": str(db_port),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    if sslmode:
        config["OPTIONS"] = {"sslmode": sslmode}
    return config


DB_ENGINE = os.getenv("DB_ENGINE", "postgresql").strip().lower()

if DB_ENGINE in {"sqlite", "sqlite3"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": _build_postgresql_config()
    }

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Max upload size: 30MB (per SRS requirement)
DATA_UPLOAD_MAX_MEMORY_SIZE = 31457280
FILE_UPLOAD_MAX_MEMORY_SIZE = 31457280

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'
