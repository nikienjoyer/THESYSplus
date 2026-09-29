"""Suggest a primary research subject from the most similar reviewed theses.

Nearest subject centroid over Sentence-BERT document vectors: each subject's
reviewed theses are averaged into one direction, and the subjects closest to
the thesis being reviewed are suggested. On the initial 52 reviewed theses
(leave-one-out) the right subject was first 65% of the time and within two
suggestions 77% of the time, so a suggestion only pre-selects a choice;
faculty or an administrator always confirms the subject.
"""

from __future__ import annotations

from typing import List

SUGGESTION_LIMIT = 2


def _unit(raw):
    """Unit-length float vector, or ``None`` when unusable."""
    import numpy as np
    from .semantic_search import EMBEDDING_DIM

    if raw is None:
        return None
    try:
        vector = np.asarray(raw, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if vector.shape != (EMBEDDING_DIM,) or not np.isfinite(vector).all():
        return None
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-6 else None


def suggest_subjects(thesis, *, limit: int = SUGGESTION_LIMIT) -> List[dict]:
    """Up to ``limit`` subjects as ``{'code', 'name', 'score'}``, best first.

    The thesis itself never counts toward a centroid, so a reviewed thesis is
    only compared with the others. Subjects without usable reviewed vectors
    are never suggested.
    """
    from theses.models import Thesis, ThesisStatus

    target = _unit(getattr(thesis, 'embedding_vector', None))
    if target is None:
        return []

    reviewed = (
        Thesis.objects
        .filter(status=ThesisStatus.APPROVED, primary_subject__isnull=False,
                subject_reviewed_at__isnull=False)
        .exclude(pk=thesis.pk)
        .select_related('primary_subject')
        .only('id', 'embedding_vector', 'primary_subject', 'primary_subject__name')
    )
    totals: dict = {}
    names: dict = {}
    for row in reviewed:
        vector = _unit(row.embedding_vector)
        if vector is None:
            continue
        code = row.primary_subject_id
        totals[code] = totals[code] + vector if code in totals else vector
        names[code] = row.primary_subject.name

    suggestions = []
    for code, total in totals.items():
        centroid = _unit(total)
        if centroid is None:
            continue
        suggestions.append({'code': code, 'name': names[code], 'score': round(float(centroid @ target), 4)})
    suggestions.sort(key=lambda item: (-item['score'], item['code']))
    return suggestions[:limit]
