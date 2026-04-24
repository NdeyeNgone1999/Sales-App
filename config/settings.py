"""
Django settings for the Service Commercial project.
"""

import os
from pathlib import Path

try:
    import dj_database_url
except ImportError:
    dj_database_url = None

try:
    import whitenoise  # noqa: F401
except ImportError:
    HAS_WHITENOISE = False
else:
    HAS_WHITENOISE = True


def config(name, default=None, cast=None):
    value = os.environ.get(name, default)
    if cast is not None and value is not None:
        return cast(value)
    return value

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-@3k9m#x$p2w!8y4v6n7b5t1q0z-change-this-in-production',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG_VALUE = str(config('DEBUG', default='true')).strip().lower()
DEBUG = DEBUG_VALUE not in {'0', 'false', 'no', 'off', 'release', 'prod', 'production'}

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,pmi-analysis-4b5b508408b2.herokuapp.com',
).split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'service_commercial.client_analytics.apps.ClientAnalyticsConfig',
    'service_commercial.common.accounts.apps.AccountsConfig',
    'service_commercial.fiches_techniques.pages.apps.PagesConfig',
    'service_commercial.fiches_techniques.main_page.apps.MainPageConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if HAS_WHITENOISE and not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'service_commercial' / 'client_analytics' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'service_commercial.common.accounts.context_processors.user_role_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
database_url = config('DATABASE_URL', default=None)
if database_url:
    if dj_database_url is None:
        raise RuntimeError(
            "DATABASE_URL is defined but `dj_database_url` is not installed. "
            "Install it or unset DATABASE_URL to use SQLite locally."
        )
    DATABASES = {
        'default': dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    databases_dir = BASE_DIR / 'databases'
    databases_dir.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'config.sqlite3_backend',
            'NAME': databases_dir / os.environ.get('SQLITE_COMMON_DB_NAME', 'common_service.sqlite3'),
        },
        'client_analytics': {
            'ENGINE': 'config.sqlite3_backend',
            'NAME': databases_dir / os.environ.get(
                'SQLITE_CLIENT_ANALYTICS_DB_NAME',
                'client_analytics.sqlite3',
            ),
        },
        'fiches_techniques': {
            'ENGINE': 'config.sqlite3_backend',
            'NAME': databases_dir / os.environ.get(
                'SQLITE_FICHES_TECHNIQUES_DB_NAME',
                'fiches_techniques.sqlite3',
            ),
        },
    }
    DATABASE_ROUTERS = ['config.db_routers.ServiceCommercialRouter']

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'service-commercial-portal',
        'TIMEOUT': 3600,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
static_manifest_path = STATIC_ROOT / 'staticfiles.json'
staticfiles_backend = 'django.contrib.staticfiles.storage.StaticFilesStorage'

if HAS_WHITENOISE and not DEBUG:
    staticfiles_backend = (
        'whitenoise.storage.CompressedManifestStaticFilesStorage'
        if static_manifest_path.exists()
        else 'whitenoise.storage.CompressedStaticFilesStorage'
    )

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': staticfiles_backend,
    }
}

# Media files (uploads)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/fiches-techniques/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'noreply@service-commercial.local',
)
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', EMAIL_HOST_USER or DEFAULT_FROM_EMAIL)

RECIPE_DEBUG_MODE = os.environ.get('RECIPE_DEBUG_MODE', 'True').lower() == 'true'
RECIPE_DETAILED_ERRORS = (
    os.environ.get('RECIPE_DETAILED_ERRORS', 'True').lower() == 'true'
)
ENABLE_HTTPS_REDIRECT = (
    str(os.environ.get('ENABLE_HTTPS_REDIRECT', 'false')).strip().lower()
    in {'1', 'true', 'yes', 'on'}
)

MIGRATION_MODULES = {
    'accounts': 'service_commercial.common.accounts.stable_migrations_pkg',
}

# Security Settings for Production
if not DEBUG:
    SECURE_SSL_REDIRECT = ENABLE_HTTPS_REDIRECT
    SESSION_COOKIE_SECURE = ENABLE_HTTPS_REDIRECT
    CSRF_COOKIE_SECURE = ENABLE_HTTPS_REDIRECT
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# Logging (visible dans heroku logs)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '[{levelname}] {asctime} {name} {funcName}:{lineno} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'client_analytics': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'service_commercial.common.accounts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'service_commercial.fiches_techniques.pages.services': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'service_commercial.fiches_techniques.pages.views': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
