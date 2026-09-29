"""
WSGI config for thesys project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')

application = get_wsgi_application()

if settings.SBERT_PRELOAD:
    from theses.services.semantic_search import _get_model, embed_text

    _get_model()
    # Torch's first encode can be much slower than model construction alone.
    # Warm it before the web process accepts search traffic.
    embed_text('THESYS+ model warmup')
