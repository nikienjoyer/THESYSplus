"""Foundation Phase health endpoint.

A tiny ``GET /api/v1/health`` view that returns ``{"status": "ok"}`` so the
runtime smoke check in Task 6.2 can confirm the Django process boots and
the URL conf is wired correctly. This view intentionally has no auth, no
rate limiting, and no CSRF requirement — it is a static probe, not an
auth-bearing endpoint.
"""

from django.http import HttpRequest, JsonResponse


def health(_request: HttpRequest) -> JsonResponse:
    """Return a static 200 OK with a JSON ``{"status": "ok"}`` body."""
    return JsonResponse({"status": "ok"})
