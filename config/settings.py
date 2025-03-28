"""
Django settings for config project.

Generated by 'django-admin startproject' using Django 5.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
from pathlib import Path

import dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
env_file = BASE_DIR / '.env'
if env_file.exists():
    dotenv.load_dotenv(env_file)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# The SECRET_KEY must be provided via environment variable
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# Debug mode should be False in production
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Get domain name from environment
DOMAIN_NAME = os.environ.get('DOMAIN_NAME', 'localhost')

# Allow the domain name, www subdomain, localhost, and internal docker IPs
ALLOWED_HOSTS = [DOMAIN_NAME, f'www.{DOMAIN_NAME}', 'localhost', '127.0.0.1', '[::1]']

# CSRF trusted origins - generated dynamically based on DOMAIN_NAME
CSRF_TRUSTED_ORIGINS = [
    f'https://{DOMAIN_NAME}',
    f'https://*.{DOMAIN_NAME}',
    f'http://{DOMAIN_NAME}',
    f'http://*.{DOMAIN_NAME}',
    'http://localhost',
    'http://127.0.0.1'
]

# Security settings for HTTPS - temporarily disabled until HTTPS is fully set up
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Disabled until HTTPS is fully set up
SESSION_COOKIE_SECURE = False  # Disabled until HTTPS is fully set up
CSRF_COOKIE_SECURE = False  # Disabled until HTTPS is fully set up
SECURE_HSTS_SECONDS = 31536000  # Commented out until HTTPS is fully configured
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'battycoda_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add whitenoise for static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Add standard authentication middleware
    'battycoda_app.middleware.authentication_middleware.AuthenticationMiddleware',
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


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Whitenoise configuration for serving static files
# Check if static file caching should be disabled using environment variable
DISABLE_STATIC_CACHING = os.environ.get('DISABLE_STATIC_CACHING', 'False').lower() == 'true'

# Choose appropriate storage backend based on caching settings
if DISABLE_STATIC_CACHING:
    # Use basic storage with no caching for development
    STATICFILES_STORAGE = 'whitenoise.storage.StaticFilesStorage'
    WHITENOISE_MAX_AGE = 0  # No caching
else:
    # Use compressed storage with long caching for production
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
    WHITENOISE_MAX_AGE = 31536000  # 1 year in seconds

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Make sure the media directory exists
os.makedirs(MEDIA_ROOT / 'audio_cache', exist_ok=True)
os.makedirs(MEDIA_ROOT / 'home', exist_ok=True)

# File upload settings - read from same environment variable as Nginx
MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', 100))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert MB to bytes
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

# Celery configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'battycoda.auth': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'battycoda.audio': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'battycoda.tasks': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'battycoda.email': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'battycoda.views_species': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# AWS SES Email Configuration
EMAIL_BACKEND = 'django_ses.SESBackend'
AWS_SES_REGION_NAME = os.environ.get('AWS_SES_REGION_NAME', 'us-east-1')
AWS_SES_ACCESS_KEY_ID = os.environ.get('AWS_SES_ACCESS_KEY_ID')
AWS_SES_SECRET_ACCESS_KEY = os.environ.get('AWS_SES_SECRET_ACCESS_KEY')
AWS_SES_CONFIGURATION_SET = os.environ.get('AWS_SES_CONFIGURATION_SET', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', f'noreply@{DOMAIN_NAME}')
