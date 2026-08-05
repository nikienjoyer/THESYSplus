"""Pluggable email backend for the Auth_Service.

Defines an ``EmailBackend`` Protocol with ``send(to, subject,
template_name, context)`` plus concrete ``ConsoleEmailBackend`` and
``SMTPEmailBackend`` implementations selected via the
``EMAIL_BACKEND_CHOICE`` setting (``console`` or ``smtp``) per
Requirement 5.2 / design §10.1.

Developer visibility:
- Console backend prints a clear banner with the actionable link.
- SMTP backend logs success/failure with recipient and template.
- ``default_email_backend()`` logs which backend is active on first call.
- If SMTP is selected but credentials are missing, falls back to console
  with a warning so development never breaks.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger('emails')

# Track whether we've logged the backend selection (once per process).
_backend_announced = False


class EmailBackend(Protocol):
    """Send a transactional email rendered from a template name + context."""

    def send(self, to: str, subject: str, template_name: str, context: dict[str, Any]) -> bool:
        ...


def _render_pair(template_name: str, context: dict[str, Any]) -> tuple[str, str | None]:
    """Render ``email/{template_name}.txt`` and (optionally) ``.html``."""
    text_body = render_to_string(f'email/{template_name}.txt', context)
    try:
        html_body = render_to_string(f'email/{template_name}.html', context)
    except Exception:
        html_body = None
    return text_body, html_body


def _extract_link(context: dict[str, Any]) -> str | None:
    """Pull the actionable URL from common email context keys."""
    for key in ('verify_url', 'reset_url', 'activation_url', 'link'):
        url = context.get(key)
        if url:
            return url
    return None


class ConsoleEmailBackend:
    """Write the rendered email to stdout via the standard logger.

    Used in dev when ``EMAIL_BACKEND_CHOICE='console'``. The template
    rendering still happens so authors can verify their templates.

    Prints a prominent banner with the actionable link so developers
    can click it directly from the terminal.
    """

    def send(self, to: str, subject: str, template_name: str, context: dict[str, Any]) -> bool:
        text_body, _ = _render_pair(template_name, context)
        link = _extract_link(context)

        # Prominent banner for developer visibility
        logger.info(
            '\n'
            '╔══════════════════════════════════════════════════════════════╗\n'
            '║  [EMAIL] Console backend — email printed to terminal       ║\n'
            '╠══════════════════════════════════════════════════════════════╣\n'
            '║  To:       %s\n'
            '║  Subject:  %s\n'
            '║  Template: %s\n'
            '%s'
            '╚══════════════════════════════════════════════════════════════╝\n'
            '%s\n'
            '--- end email ---',
            to, subject, template_name,
            f'║  🔗 Link:  {link}\n' if link else '',
            text_body,
        )
        return True


class SMTPEmailBackend:
    """Deliver via standard Django SMTP transport.

    Reads ``EMAIL_HOST`` / ``EMAIL_PORT`` / ``EMAIL_HOST_USER`` /
    ``EMAIL_HOST_PASSWORD`` / ``EMAIL_USE_TLS`` from settings.
    """

    def send(self, to: str, subject: str, template_name: str, context: dict[str, Any]) -> bool:
        text_body, html_body = _render_pair(template_name, context)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.EMAIL_FROM,
            to=[to],
        )
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        try:
            msg.send(fail_silently=False)
        except Exception as exc:  # pragma: no cover - exercised via logs
            logger.error(
                '[EMAIL] SMTP send FAILED to=%s template=%s error=%s',
                to, template_name, exc,
            )
            return False

        logger.info('[EMAIL] Sent via SMTP to=%s template=%s subject=%r', to, template_name, subject)
        return True


def default_email_backend() -> EmailBackend:
    """Return the configured backend instance.

    Selection logic:
    1. If ``EMAIL_BACKEND_CHOICE == 'smtp'`` AND credentials are present
       → ``SMTPEmailBackend``.
    2. If ``EMAIL_BACKEND_CHOICE == 'smtp'`` but credentials are MISSING
       → fall back to ``ConsoleEmailBackend`` with a warning.
    3. Otherwise (default) → ``ConsoleEmailBackend``.
    """
    global _backend_announced
    choice = (getattr(settings, 'EMAIL_BACKEND_CHOICE', None) or 'console').lower()

    if choice == 'smtp':
        host = getattr(settings, 'EMAIL_HOST', '')
        user = getattr(settings, 'EMAIL_HOST_USER', '')
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

        if not host or not user or not password:
            if not _backend_announced:
                logger.warning(
                    '[EMAIL] EMAIL_BACKEND=smtp but SMTP credentials are incomplete '
                    '(SMTP_HOST=%r, SMTP_USER=%r). Falling back to console backend. '
                    'Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in .env to enable real email delivery.',
                    host, user,
                )
                _backend_announced = True
            return ConsoleEmailBackend()

        if not _backend_announced:
            logger.info(
                '[EMAIL] SMTP backend active — sending via %s:%s as %s',
                host, getattr(settings, 'EMAIL_PORT', 587), user,
            )
            _backend_announced = True
        return SMTPEmailBackend()

    if not _backend_announced:
        logger.info('[EMAIL] Console backend active — emails will be printed to terminal only.')
        _backend_announced = True
    return ConsoleEmailBackend()
