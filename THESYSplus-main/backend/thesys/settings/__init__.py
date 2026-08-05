"""
Settings package entry point for the THESYS+ project.

This module re-exports either the development or production settings based on
the value of the ``DJANGO_ENV`` environment variable so that existing references
to ``DJANGO_SETTINGS_MODULE='thesys.settings'`` continue to work without change.

- ``DJANGO_ENV=development`` (default) -> ``thesys.settings.dev``
- ``DJANGO_ENV=production``           -> ``thesys.settings.prod``

Any other value falls back to ``development`` to keep local tooling forgiving.
The ``base`` module holds the shared definitions both environments build on.
"""
import os

_DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').lower()

if _DJANGO_ENV == 'production':
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
