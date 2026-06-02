"""
Base Django settings for the THESYS+ project.

These settings are environment-agnostic and are imported by both ``dev`` and
``prod``. Environment-driven values are read with ``django-environ`` so the
same code path works whether configuration is supplied through a ``.env`` file
or the process environment.

The Foundation Phase wires only the bare minimum: the standard Django contrib
apps, DRF, ``corsheaders``, the PostgreSQL connection (via ``DATABASE_URL`` or
discrete ``POSTGRES_*`` fallbacks), and the four standard password validators.
No project-specific apps are registered yet; that lands in Task 3.1.
"""

from pathlib import Path

import environ


# ---------------------------------------------------------------------------
# Paths and environment
# ---------------------------------------------------------------------------

# ``BASE_DIR`` points at the ``backend/`` directory (the parent of ``thesys/``).
# ``__file__`` here is ``backend/thesys/settings/base.py`` so we walk up three
# levels to land on ``backend/``.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Read a ``.env`` file from the backend root if one exists. ``read_env`` is a
# safe no-op when the file is missing, which keeps CI and fresh checkouts
# functional without requiring an env file.
environ.Env.read_env(BASE_DIR / '.env')


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------

# ``DJANGO_SECRET_KEY`` MUST be set in production. In development we fall back
# to a clearly-marked insecure default so contributors can boot the project
# without first creating a ``.env`` file. The dev fallback is only honoured
# when ``DJANGO_ENV`` is ``development`` (or unset); ``prod.py`` re-validates
# this and refuses to boot with the placeholder value.
SECRET_KEY = env(
    'DJANGO_SECRET_KEY',
    default='django-insecure-foundation-dev-only-do-not-use-in-prod',
)

# ``DEBUG`` and ``ALLOWED_HOSTS`` are intentionally left to the per-environment
# modules (``dev.py`` / ``prod.py``) so the default in ``base`` is never used
# directly. We still define safe defaults here so partial imports don't crash.
DEBUG = False
ALLOWED_HOSTS: list[str] = []


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Django contrib
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party (placed after contrib, before any local apps)
    'corsheaders',
    'rest_framework',
    # Local apps. Order follows the dependency direction in design §2.2:
    # ``accounts`` is the leaf model holder, ``audit`` only FK-depends on
    # ``accounts``, and the three siblings (``auth_service``,
    # ``access_requests``, ``password_reset``) come last.
    'accounts',
    'audit',
    'auth_service',
    'access_requests',
    'identity_verification.apps.IdentityVerificationConfig',
    'password_reset',
    'theses.apps.ThesesConfig',
]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# ``corsheaders.middleware.CorsMiddleware`` MUST sit above
# ``django.middleware.common.CommonMiddleware`` so CORS headers are attached
# before Common applies its URL rewrites and response normalisation.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ---------------------------------------------------------------------------
# URL configuration / WSGI / ASGI
# ---------------------------------------------------------------------------

ROOT_URLCONF = 'thesys.urls'
WSGI_APPLICATION = 'thesys.wsgi.application'


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
#
# Primary mechanism: read a single ``DATABASE_URL`` (e.g.
# ``postgres://user:pass@host:5432/dbname``) via ``django-environ``'s
# ``db_url`` helper.
#
# Fallback: when ``DATABASE_URL`` is not set, build the same DATABASES dict
# from discrete ``POSTGRES_*`` variables. Both paths produce a record with
# ``ENGINE = 'django.db.backends.postgresql'`` so Django 5 auto-selects the
# psycopg 3 driver. ``psycopg2`` is NOT used anywhere.

if env('DATABASE_URL', default=None):
    DATABASES = {
        'default': env.db_url('DATABASE_URL'),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': env('POSTGRES_HOST', default='localhost'),
            'PORT': env('POSTGRES_PORT', default='5432'),
            'NAME': env('POSTGRES_DB', default='thesys'),
            'USER': env('POSTGRES_USER', default='thesys'),
            'PASSWORD': env('POSTGRES_PASSWORD', default='thesys'),
        }
    }


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Auth user model and password hashers
# ---------------------------------------------------------------------------
#
# The capstone uses a custom user model keyed on email (``accounts.User``)
# rather than Django's default ``auth.User`` so the schema can be UUID-keyed
# and citext-backed per design §3.3 / Requirement 1.5.
#
# Argon2id is the primary hasher per Requirement 8.1; the remaining entries
# are Django's default fallbacks so existing hashes from PBKDF2 / bcrypt /
# scrypt installations continue to verify and ``verify_password`` can request
# a re-hash on successful login (Requirement 8.3).

AUTH_USER_MODEL = 'accounts.User'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'

# ---------------------------------------------------------------------------
# Media files (user-uploaded content)
# ---------------------------------------------------------------------------
#
# MEDIA_ROOT must be an absolute path so uploaded verification documents are
# always stored at a predictable location regardless of the working directory
# the server process was started from.  The OCR pipeline reads files back by
# the stored absolute path, so a wrong MEDIA_ROOT causes FileNotFoundError.
#
# MEDIA_URL is defined for completeness; verification documents are served
# through an authenticated view, NOT via Django's static-file media serving.

MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'


# ---------------------------------------------------------------------------
# Private file storage (identity verification documents)
# ---------------------------------------------------------------------------
#
# Per Requirement 15.1 / design §1.5: uploaded verification documents are
# stored in private storage that is NOT publicly accessible. Files are served
# through an authenticated Django view (dev) or signed URLs (prod).

PRIVATE_STORAGE_ROOT = BASE_DIR / 'private_media'
VERIFICATION_DOCS_PATH = 'verification_docs'


# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# Django REST Framework (Foundation Phase minimum)
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'auth_service.authentication.JWTAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'common.errors.unified_exception_handler',
}


# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------
#
# ``FRONTEND_ORIGIN`` may be a single origin or a comma-separated list. Using
# ``env.list`` lets ops pass either ``http://localhost:5173`` or
# ``https://app.example.com,https://staging.example.com`` without code change.

CORS_ALLOWED_ORIGINS = env.list(
    'FRONTEND_ORIGIN',
    default=['http://localhost:5173'],
)
CORS_ALLOW_CREDENTIALS = True


# ---------------------------------------------------------------------------
# JWT (Auth_Service access tokens)
# ---------------------------------------------------------------------------
#
# Per Requirements 2.6 / 2.7 / design §5.1: HS256 access tokens with a
# ``kid`` JOSE header for future key rotation. The secret SHOULD be
# distinct from ``DJANGO_SECRET_KEY`` so rotating the JWT key doesn't
# invalidate Django sessions.

JWT_SECRET = env('JWT_SECRET', default=SECRET_KEY)
JWT_KID = env('JWT_KID', default='kid-2025-01')
JWT_ISSUER = 'thesys-auth'
JWT_ALGORITHM = 'HS256'
JWT_ACCESS_TTL_SECONDS = 900  # 15 minutes per Requirement 2.1


# ---------------------------------------------------------------------------
# Refresh token cookie / lifetime
# ---------------------------------------------------------------------------
#
# Per Requirements 2.1 / 4.1: 24h default, 30d when remember_me selected.

REFRESH_TOKEN_TTL_SECONDS = 24 * 60 * 60        # 24 hours
REFRESH_TOKEN_REMEMBER_ME_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
REFRESH_COOKIE_NAME = 'refresh_token'
REFRESH_COOKIE_PATH = '/api/v1/auth'


# ---------------------------------------------------------------------------
# Frontend base URL (used in email templates per design §10.1)
# ---------------------------------------------------------------------------

FRONTEND_BASE_URL = env('FRONTEND_BASE_URL', default='http://localhost:5173')


# ---------------------------------------------------------------------------
# Email backend
# ---------------------------------------------------------------------------
#
# Per Requirement 5.2 / design §10.1. ``console`` writes emails to stdout in
# dev; ``smtp`` is wired in prod. The pluggable backend lives in
# ``common.email_backend`` so swapping providers doesn't touch services.

EMAIL_BACKEND_CHOICE = env('EMAIL_BACKEND', default='console')
EMAIL_FROM = env('EMAIL_FROM', default='noreply@pampangastateu.edu.ph')

# Standard Django email backend wiring (used by common.email_backend's SMTP path).
EMAIL_HOST = env('SMTP_HOST', default='localhost')
EMAIL_PORT = env.int('SMTP_PORT', default=587)
EMAIL_HOST_USER = env('SMTP_USER', default='')
EMAIL_HOST_PASSWORD = env('SMTP_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('SMTP_USE_TLS', default=True)


# ---------------------------------------------------------------------------
# Cache (used by common.ratelimit)
# ---------------------------------------------------------------------------
#
# Per Requirement 10 + design §8.1: a backing cache holds the per-email
# and per-IP request budgets. LocMem is fine for dev and single-process
# deployments; production should swap in Redis via the env var.

CACHES = {
    'default': {
        'BACKEND': env(
            'RATE_LIMIT_BACKEND',
            default='django.core.cache.backends.locmem.LocMemCache',
        ),
        'LOCATION': env('RATE_LIMIT_LOCATION', default='thesys-rate-limit'),
    },
}


# ---------------------------------------------------------------------------
# Identity Verification (AI-Assisted Identity Verification MVP)
# ---------------------------------------------------------------------------
#
# Per design §4.7 / Requirements 7.2, 7.3, 7.4, 14.1: OCR-based document
# verification for Student ID and Certificate of Registration (COR) uploads.
# This MVP uses synchronous processing and rule-based validation only.
# SBERT, TF-IDF, Celery async processing, and retention purge are deferred
# to post-MVP.

IDENTITY_VERIFICATION = {
    # Processing mode: True = synchronous (dev), False = async via Celery (prod)
    'SYNC_MODE': env.bool('IDENTITY_VERIFICATION_SYNC', default=True),
    
    # Tesseract OCR configuration
    # Optional: Explicit path to tesseract executable
    # If not set, will auto-discover on Windows or use system PATH
    # Example: 'TESSERACT_CMD': r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    'TESSERACT_CMD': env.str('TESSERACT_CMD', default=None),
    
    # File validation settings
    'MAX_FILE_SIZE_MB': 10,
    'ALLOWED_EXTENSIONS': ['png', 'jpg', 'jpeg', 'pdf'],
    'ALLOWED_MIME_TYPES': [
        'image/png',
        'image/jpeg',
        'application/pdf',
    ],
    
    # OCR confidence thresholds (0-100 scale, per Tesseract)
    'OCR_CONFIDENCE_HIGH': 75,    # Auto-approve threshold
    'OCR_CONFIDENCE_MEDIUM': 60,  # Manual review threshold
    'OCR_CONFIDENCE_THRESHOLDS': {
        'HIGH': 75,    # Auto-approve threshold (legacy structure, kept for compatibility)
        'MEDIUM': 60,  # Manual review threshold (legacy structure, kept for compatibility)
    },
    'OCR_TIMEOUT_SECONDS': 10,
    
    # Canonical reference data for rule-based validation
    'INSTITUTIONS': (
        'Pampanga State University',
    ),
    'COLLEGES': (
        'College of Computing Studies',
        'CCS',
    ),
    'PROGRAMS_CANONICAL': (
        'BS Information System',
        'BS Information Technology',
        'BS Computer Science',
        'Associate in Computer Technology',
    ),
}
