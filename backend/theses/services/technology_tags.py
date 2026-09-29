"""Technology tags: which technologies a thesis is actually about.

A thesis can be about several technologies at once (the fuzzy-logic farming
app is an IoT project that also uses fuzzy logic), and a technology is not a
research subject (the IoT theses are about agriculture, accessibility,
commerce and security). So tags are a list per thesis, never a group.

Evidence uses the Repository term-rescue rule (services/acronyms.py
``is_about_term``): one mention in the title, keywords or abstract, or at
least three full-text mentions at a density of one per 10,000 characters.
Tags are computed when the search vector is generated and stored on
``Thesis.technology_tags``, so reading them never loads the full text.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from .acronyms import is_about_term

TECHNOLOGY_TAGS = (
    'IoT', 'AI', 'ML', 'DL', 'NLP', 'OCR', 'CNN', 'LLM',
    'AR', 'VR', 'GPS', 'GIS', 'RFID', 'QR', 'SMS',
)


def detect_technology_tags(
    *,
    title: str = '',
    abstract: str = '',
    keywords: Optional[Iterable] = None,
    full_text: Optional[str] = '',
) -> List[str]:
    """The technologies this thesis is about, in ``TECHNOLOGY_TAGS`` order."""
    keyword_text = ' ; '.join(str(k) for k in (keywords or []) if isinstance(k, str))
    head = '\n'.join([title or '', keyword_text, abstract or ''])
    return [
        tag for tag in TECHNOLOGY_TAGS
        if is_about_term(tag, head=head, full_text=full_text or '')
    ]
