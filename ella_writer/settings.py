"""
Django settings for ella_writer project.

Generated by 'django-admin startproject' using Django 4.2.15.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
from datetime import timedelta
from django.conf.global_settings import CSRF_COOKIE_SECURE, SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE
from dotenv import load_dotenv
import os
import dj_database_url
import base64


load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Secret Key Configuration

def get_secret_key():
    import base64
    # First, try to get the base64 encoded secret key
    encoded_secret_key = os.environ.get('DJANGO_SECRET_KEY', '')
    
    try:
        # Try to decode the base64 encoded key
        if encoded_secret_key:
            return base64.b64decode(encoded_secret_key).decode('utf-8')
    except Exception:
        pass
    
    # Fallback to the original secret key or generate a new one
    return encoded_secret_key or "django-insecure-fallback-key-please-replace"

# Set the secret key using the function
SECRET_KEY = get_secret_key()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Sites Framework
SITE_ID = 1


CURRENT_LLM_CONFIG = {
    'provider': 'mistral',
    'mistral_api_key': os.getenv('MISTRAL_API_KEY'),
    'groq_api_key': os.getenv('GROQ_API_KEY'),
    'huggingface_api_key': os.getenv('HUGGINGFACE_API_KEY'),
    'model_path': '/path/to/local/llama/model.gguf'
}

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # "allauth.socialaccount.providers.linkedin",
    # "allauth.socialaccount.providers.facebook",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_auth",
    "rest_auth.registration",
    "corsheaders",
    "api",
    "home",
    "cv_parser",
    "cv_writer",
    "models_trainer",
    "linkedin_parser",
    "jobstract",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# SOCIALACCOUNT_PROVIDERS = {
#     'google': {
#         # For each OAuth based provider, either add a ``SocialApp``
#         # (``socialaccount`` app) containing the required client
#         # credentials, or list them here:
#         'APP': {
#             'client_id': '123',
#             'secret': '456',
#             'key': ''
#         }
#     },

# }

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://www.ellacv.com",
    "https://ellacv.com",
    "https://www.ellacvwriter.com",
    "https://ellacvwriter.com",
    "http://localhost:5173",
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://www.ellacv.com",
    "https://ellacv.com",
    "https://www.ellacvwriter.com",
    "https://ellacvwriter.com",
]

# Production-specific settings
if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production'):
    # Security settings
    DEBUG = False
    
    # Enforce HTTPS and secure cookies
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Add your production domains to allowed hosts
    ALLOWED_HOSTS = [
        'project3-backend-7ck4.onrender.com', 
        'www.ellacv.com', 
        'ellacv.com',
        'www.ellacvwriter.com',
        'ellacvwriter.com'
    ]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": "access_token",
    "JWT_AUTH_REFRESH_COOKIE": "refresh_token",
    "JWT_AUTH_HTTPONLY": False,
}

# Frontend URL (without trailing slash)
FRONTEND_URL = "http://localhost:5173"

# Email settings
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@ella.com"
SITE_NAME = "Ella"
SITE_DOMAIN = FRONTEND_URL.replace("http://", "").replace("https://", "")

ROOT_URLCONF = "ella_writer.urls"

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "cv_writer.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "cv_writer": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Create logs directory if it doesn't exist
if not os.path.exists(os.path.join(BASE_DIR, "logs")):
    os.makedirs(os.path.join(BASE_DIR, "logs"))

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Email verification settings
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = "/"
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

WSGI_APPLICATION = "ella_writer.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.parse(
        url=os.getenv("DATABASE_URL", ""),
        conn_max_age=600, conn_health_checks=True
    )
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# Add STATIC configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

# Email settings (console backend for development)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

EMAIL_USE_TLS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Ella Writer] "

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# Form setting
ACCOUNT_FORMS = {
    "signup": "allauth.account.forms.SignupForm",
    "login": "allauth.account.forms.LoginForm",
    "reset_password": "allauth.account.forms.ResetPasswordForm",
    "reset_password_from_key": "allauth.account.forms.ResetPasswordKeyForm",
    "change_password": "allauth.account.forms.ChangePasswordForm",
    "add_email": "allauth.account.forms.AddEmailForm",
}

ACCOUNT_PASSWORD_MIN_LENGTH = 8
ACCOUNT_PASSWORD_REQUIRED = True


# Environment Configuration
ENVIRONMENT = os.getenv('DJANGO_ENVIRONMENT', 'development')

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

LLM_PROVIDERS = {
    'development': {
        'provider': 'local',
        'model_path': os.path.join(BASE_DIR, "models/llama-2-7b-chat.gguf"),
        'fallback_provider': 'local'
    },
    'production': {
        'provider': 'mistral',
        'api_key': MISTRAL_API_KEY,
        'fallback_provider': 'groq_llama',
        'fallback_api_key': GROQ_API_KEY
    }
}

# Get current environment configuration
CURRENT_LLM_CONFIG = LLM_PROVIDERS.get(ENVIRONMENT, LLM_PROVIDERS['development'])

# LinkedIn OAuth Configuration
LINKEDIN_CONFIG = {
    "CLIENT_ID": os.getenv("LINKEDIN_CLIENT_ID", ""),
    "CLIENT_SECRET": os.getenv("LINKEDIN_CLIENT_SECRET", ""),
    "SCOPE": "r_liteprofile r_emailaddress",
    "AUTH_URL": "https://www.linkedin.com/oauth/v2/authorization",
    "TOKEN_URL": "https://www.linkedin.com/oauth/v2/accessToken",
    "REDIRECT_URI": "http://localhost:5173/linkedin/callback",
}

# Add to existing settings.py
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Production-specific settings
if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production'):
    # Security settings
    DEBUG = False
    
    # Use environment variable for secret key in production
    # SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)
    
    # Enforce HTTPS and secure cookies
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Database configuration for Render
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            ssl_require=True
        )
    }
    
    # Allowed hosts from environment variable
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',') if os.environ.get('ALLOWED_HOSTS') else []
    
    # CORS settings for production
    CORS_ALLOWED_ORIGINS = [
        "https://www.ellacv.com",
        "https://ellacv.com",
        "https://www.ellacvwriter.com",
        "https://ellacvwriter.com",
    ]
    
    CSRF_TRUSTED_ORIGINS = [
        "https://www.ellacv.com",
        "https://ellacv.com",
        "https://www.ellacvwriter.com",
        "https://ellacvwriter.com",
    ]
    
    # Logging for production
    LOGGING['handlers']['file']['filename'] = '/var/log/ella/cv_writer.log'
    LOGGING['loggers']['cv_writer']['level'] = 'INFO'

# Ensure environment-specific LLM configuration
ENVIRONMENT = 'production' if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('production') else 'development'
CURRENT_LLM_CONFIG = LLM_PROVIDERS.get(ENVIRONMENT, LLM_PROVIDERS['development'])
