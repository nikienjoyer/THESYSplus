"""
Production settings for the THESYS+ project.

Imports everything from ``base`` and tightens the values that must NOT use
their development defaults:

- ``DEBUG`` is forced off.
- ``ALLOWED_HOSTS`` MUST be supplied via the ``DJANGO_ALLOWED_HOSTS`` env var
  (comma-separated). An empty list will cause Django to reject every request
  with a 400, which is the safe default until the operator configures hosts.

Security headers are intentionally minimal in the Foundation Phase. HSTS and
SSL redirection are deliberately *not* enabled here because the Foundation
Phase does not yet stand up a TLS terminator; turning them on now would brick
local production-mode smoke tests. They will be enabled once a real
load balancer / reverse proxy with TLS lands in a later phase.
"""

from .base import *  # noqa: F401,F403
from .base import env


DEBUG = False

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])


# ---------------------------------------------------------------------------
# Security headers (phase-1 placeholders)
# ---------------------------------------------------------------------------
#
# These flags harden cookies and content-type sniffing without requiring a
# TLS terminator. HSTS and SECURE_SSL_REDIRECT are intentionally deferred to
# the phase that introduces the real reverse proxy / load balancer; enabling
# them now would break HTTP-only smoke tests.

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# HSTS — DEFERRED (phase-1): no TLS terminator wired yet.
# SECURE_HSTS_SECONDS, SECURE_HSTS_INCLUDE_SUBDOMAINS, SECURE_HSTS_PRELOAD,
# and SECURE_SSL_REDIRECT will be enabled once HTTPS is terminated upstream.

# ---------------------------------------------------------------------------
# DEPLOYMENT CONSTRAINT — /media/theses/ MUST NOT be served statically
# ---------------------------------------------------------------------------
#
# Do NOT add an nginx `alias`/`location` for MEDIA_ROOT, and do NOT point a CDN
# or object-storage public bucket policy at it. Thesis documents must be served
# exclusively through `ThesisDownloadView` (GET /api/v1/theses/<id>/download/).
#
# WHY, specifically:
#
#   1. The institutional watermark is burned into the PDF bytes at serve time by
#      `theses/services/watermark_pdf.py`. The file on disk is intentionally
#      NEVER modified — the stored original stays pristine so the watermark can
#      be reworded or removed later without having damaged any archive copy.
#      A static route therefore serves the CLEAN, UNWATERMARKED original.
#
#   2. The view is the only place `IsAuthenticated` and the role-scoped
#      `_visible_queryset` are enforced. A static route serves any document to
#      anyone who can guess or scrape a filename.
#
# Both failures are SILENT: nothing errors, no log line appears, and the preview
# page keeps working normally. The only symptom is that the feature has quietly
# stopped doing anything. Treat a static media route for theses/ as a
# security regression, not a performance optimisation.
#
# The cached stamped artifacts under `theses/_watermarked/` are equally
# non-public: they are an internal serve-time cache, addressed by content hash,
# and must not be exposed either.
