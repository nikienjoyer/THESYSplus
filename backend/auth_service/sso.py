"""SSO stub views (Requirement 6).

These views deliberately return ``501 SSO_NOT_CONFIGURED`` so a future
SAML / OAuth provider can be dropped in without touching login or token
issuance. The dedicated module isolates the swap surface.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import make_error_response


def _stub_response() -> Response:
    response = make_error_response(
        code='SSO_NOT_CONFIGURED',
        message='Institutional SSO is not yet configured.',
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )
    response.data['provider'] = None
    return response


class InitiateSsoView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return _stub_response()


class SsoCallbackView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        return _stub_response()
