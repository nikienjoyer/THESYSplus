"""Persist the default Topic Trend result until its approved corpus changes."""

import hashlib
import json
import logging
from pathlib import Path

from django.core.cache import caches

from .topic_analysis import analyze_topics, get_topic_trends_queryset, to_dict


logger = logging.getLogger(__name__)
_CACHE_SCHEMA_VERSION = '1'
_ALGORITHM_FINGERPRINT = hashlib.sha256(
    Path(__file__).with_name('topic_analysis.py').read_bytes()
).hexdigest()


def _cache_key(theses):
    digest = hashlib.sha256()
    digest.update(_CACHE_SCHEMA_VERSION.encode('ascii'))
    digest.update(_ALGORITHM_FINGERPRINT.encode('ascii'))
    for thesis in theses:
        # Include every field the analysis reads or returns. The queryset's
        # stable order is significant to K-Means and is preserved here.
        row = (
            str(thesis.id), thesis.title, thesis.abstract, thesis.keywords,
            thesis.program, thesis.year, thesis.status,
        )
        encoded = json.dumps(row, ensure_ascii=False, default=str, separators=(',', ':')).encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
    return f'topic-trends:{digest.hexdigest()}'


def get_topic_trends_data(*, k=None):
    """Return the API payload, sharing the default result across web workers.

    Custom ``k`` requests are uncommon and run directly. The default result
    is keyed by the exact approved rows, so edits, approvals and removals
    automatically yield a new result without serving outdated clusters.
    """
    theses = list(get_topic_trends_queryset())
    if k is not None:
        return to_dict(analyze_topics(theses, k=k))

    cache = caches['topic_trends']
    key = _cache_key(theses)
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.warning('Topic trends cache read failed: %s', exc)

    result = to_dict(analyze_topics(theses))
    try:
        cache.set(key, result, timeout=None)
    except Exception as exc:
        logger.warning('Topic trends cache write failed: %s', exc)
    return result
