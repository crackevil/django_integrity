"""Settings for the django_integrity test project."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# manage.py puts testprj_django_integrity on sys.path, the packages under test
# live next to it.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SECRET_KEY = 'django-insecure-change-me-in-production'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django_integrity',
    'testapp_django_integrity',
]

MIDDLEWARE = [
]

ROOT_URLCONF = None

TEMPLATES = [
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

LOGGING_CONFIG = None