"""
Development settings for the THESYS+ project.

Imports everything from ``base`` and overrides only the values that differ in
local development:

- ``DEBUG = True`` enables the Django error pages and template auto-reload.
- ``ALLOWED_HOSTS = ['*']`` lets the dev server respond to any Host header so
  devices on the LAN (and tunnels like ngrok) can reach the dev backend
  without per-machine configuration.
- ``LOGGING`` is configured to output email, audit, and access_request logs
  to the console so developers can see password reset links and other
  transactional emails during local testing.
"""

from .base import *  # noqa: F401,F403


DEBUG = True

ALLOWED_HOSTS = ['*']


# ---------------------------------------------------------------------------
# Logging configuration for development
# ---------------------------------------------------------------------------
#
# Route the 'emails', 'audit', and 'access_requests' loggers to the console
# so developers can see password reset links, audit events, and access
# request notifications during local testing. The ConsoleEmailBackend uses
# logger.info() to output the full email body including the reset URL.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'emails': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'audit': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'access_requests': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
