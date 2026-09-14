"""Root URL configuration for the THESYS+ project.

Mounts every cookie-bearing auth endpoint (login, logout, refresh,
forgot-password, reset-password, public request-access) under
``/api/v1/auth/``. Mounts every administrator-only admin endpoint under
``/api/v1/admin/``. The ``accounts`` app intentionally has no HTTP
surface — per design §2.2 it is a model-holder.

Also wires the ``GET /api/v1/health`` smoke endpoint so Task 6.2 can
verify end-to-end boot against a real PostgreSQL connection.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from thesys.health import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health', health, name='health'),

    # Cookie-bearing public auth surface.
    path('api/v1/auth/', include('auth_service.urls')),
    path('api/v1/auth/', include('password_reset.urls')),
    path('api/v1/auth/', include('access_requests.urls_public')),

    # Authenticated thesis repository (Phase 1).
    path('api/v1/theses/', include('theses.urls')),

    # Administrator-only surface (JWT bearer + IsAdministrator).
    path('api/v1/admin/', include('access_requests.urls_admin')),
    path('api/v1/admin/', include('audit.urls')),
]

# ---------------------------------------------------------------------------
# Media files (development only)
# ---------------------------------------------------------------------------
#
# Serves MEDIA_ROOT under MEDIA_URL when DEBUG is on. Django's ``static``
# helper is a deliberate no-op when DEBUG is False, so this is safe to leave
# unconditional — but the explicit guard documents the intent.
#
# NOTE: the thesis previewer does NOT depend on this. ``ThesisDownloadView``
# streams bytes through an authenticated view because the frontend must send
# an Authorization header, which a plain <iframe src="/media/..."> cannot do.
# This route exists for direct media inspection during development, not for
# the preview path. Thesis documents remain reachable only through the
# authenticated endpoint in production, where this block is inert.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
