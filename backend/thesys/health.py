"""Foundation Phase health endpoint.

A tiny ``GET /api/v1/health`` view that returns ``{"status": "ok"}`` so the
runtime smoke check in Task 6.2 can confirm the Django process boots and
the URL conf is wired correctly. This view intentionally has no auth, no
rate limiting, and no CSRF requirement — it is a static probe, not an
auth-bearing endpoint.
"""

from django.http import HttpRequest, JsonResponse
from django.conf import settings
from django.db import connection


def health(_request: HttpRequest) -> JsonResponse:
    """Return a static 200 OK with a JSON ``{"status": "ok"}`` body."""
    return JsonResponse({"status": "ok"})


def ready(_request: HttpRequest) -> JsonResponse:
    """Only accept traffic when database and configured model are available."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        if settings.SBERT_PRELOAD:
            from theses.services.semantic_search import _model
            if _model is None:
                raise RuntimeError('model is not loaded')
    except Exception:
        return JsonResponse({'status': 'not_ready'}, status=503)
    return JsonResponse({'status': 'ready'})
