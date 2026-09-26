"""
Django settings for config project (PMS Purchasing).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import ldap
from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-t&+0125la*hgf5ufl_ysg)f@go!r5*b4kc%%_z9*oh#x4jtl_@')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.EmployeeAccessMiddleware',
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
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', 'pms_purchasing'),
        'USER': os.environ.get('DB_USER', 'pms_purchasing'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'pms_purchasing'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        # MySQL/MariaDB-only options (not valid for PostgreSQL)
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        } if os.environ.get('DB_ENGINE', 'django.db.backends.postgresql') == 'django.db.backends.mysql' else {},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', 'English'),
    ('ar', 'العربية'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

LANGUAGE_COOKIE_NAME = 'django_language'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'

CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost,http://127.0.0.1',
).split(',')

# ── Active Directory / LDAP (matches Laravel config) ──
AUTHENTICATION_BACKENDS = [
    'core.backends.ActiveDirectoryBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_LDAP_SERVER_URI = "ldap://10.51.0.20:389"
AUTH_LDAP_BIND_DN = "2669@pms.local"
# Never hard-code the AD bind password: it must come from the environment
# (see .env.example -> AUTH_LDAP_BIND_PASSWORD). Empty means "cannot bind",
# which only affects LDAP logins; the local admin user still works.
AUTH_LDAP_BIND_PASSWORD = os.environ.get('AUTH_LDAP_BIND_PASSWORD', '')
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    "DC=PMS,DC=LOCAL",
    ldap.SCOPE_SUBTREE,
    "(sAMAccountName=%(user)s)",
)
AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
    "CN=Users,DC=PMS,DC=LOCAL",
    ldap.SCOPE_SUBTREE,
    "(objectClass=group)",
)
AUTH_LDAP_GROUP_TYPE = GroupOfNamesType()
AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": "givenName",
    "last_name": "sn",
    "email": "mail",
}
AUTH_LDAP_ALWAYS_UPDATE_USER = True
AUTH_LDAP_CACHE_TIMEOUT = 300
AUTH_LDAP_CONNECTION_TIMEOUT = 5
