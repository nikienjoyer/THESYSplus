"""Conservative, preview-only recovery after the normal abstract is absent.

Never invent an abstract from surrounding prose. A candidate needs an explicit
heading, an explicit ending, readable prose, and at most one continuation page.
The normal metadata detector and global PDF reading order are untouched.
"""
from __future__ import annotations

import re
import logging
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from .metadata_extraction import (
    MAX_ABSTRACT_CHARS,
    MIN_ABSTRACT_WORDS,
    _ABSTRACT_STOP,
    _LEADER_RUN,
    _ROMAN_NUMERAL,
    _TOC_HEADING,
    _alpha_ratio,
    _join_wrapped_lines,
)

ABSTRACT_RECOVERY_PAGES = 15
logger = logging.getLogger(__name__)
_HEADING = re.compile(r'^abstract\s*(?:[:.\-—]\s*(.*))?$', re.I)
_NUMBER = re.compile(rf'^(?:[\d\s]+|{_ROMAN_NUMERAL})$', re.I)
_INSTITUTION = re.compile(
    r'^(?:.{0,90}\b(?:university|college)|college of .{1,80}|(?:main|\w+) campus)$', re.I,
)
_SECTION = re.compile(
    r'^(?:(?:\d+(?:\.\d+)*|[IVX]+)(?:[.)]\s*|\s+))?'
    r'(?:introduction|background(?: of the study)?|methodology|methods?|'
    r'materials and methods|results(?: and discussion)?|discussion|conclusions?|'
    r'recommendations?|literature review|review of related literature)\s*[:.]?$', re.I,
)
_KEYWORDS = re.compile(r'\b(?:keywords?|key\s+words?|index\s+terms)\s*:', re.I)


def _clean_pages(pages: tuple[str, ...]) -> list[list[str]]:
    rows = [[re.sub(r'\s+', ' ', line).strip() for line in p.splitlines()]
            for p in pages[:ABSTRACT_RECOVERY_PAGES]]
    edges = Counter()
    for lines in rows:
        nonempty = [line for line in lines if line]
        edges.update(set(nonempty[:3] + nonempty[-3:]))
    cleaned = []
    for lines in rows:
        nonempty = [line for line in lines if line]
        margins = set(nonempty[:3] + nonempty[-3:])
        cleaned.append([
            line for line in lines
            if not _NUMBER.fullmatch(line)
            and not _INSTITUTION.fullmatch(line)
            and not (line in margins and edges[line] > 1 and len(line) < 120
                     and not _HEADING.match(line) and not _ABSTRACT_STOP.match(line)
                     and not re.search(r'[.!?]$', line))
        ])
    return cleaned


def recover_text_abstract(pages: tuple[str, ...], *, ocr: bool = False) -> tuple[str, str]:
    """Return only a bounded, complete candidate; uncertain text stays blank."""
    cleaned = _clean_pages(pages)
    for page_index, lines in enumerate(cleaned):
        # A contents page is never evidence of an abstract body.
        if any(_TOC_HEADING.match(line) for line in lines):
            continue
        for index, line in enumerate(lines):
            heading = _HEADING.fullmatch(line)
            if not heading:
                continue
            body = [heading.group(1)] if heading.group(1) else []
            following = lines[index + 1:]
            if page_index + 1 < len(cleaned):
                following = following + cleaned[page_index + 1]
            ended = False
            for row in following:
                if not row:
                    continue
                keyword = _KEYWORDS.search(row)
                if keyword:
                    if row[:keyword.start()].strip():
                        body.append(row[:keyword.start()].strip())
                    ended = True
                    break
                section = _SECTION.fullmatch(row)
                if _ABSTRACT_STOP.match(row) or (section and (
                    row[:1].isupper() or row[:1].isdigit()
                    or (body and re.search(r'[.!?]$', body[-1]))
                )):
                    ended = True
                    break
                if _HEADING.fullmatch(row) or _LEADER_RUN.search(row):
                    break
                # Unknown display headings inside a candidate are ambiguous;
                # never silently concatenate another section's prose.
                if row.isupper() and len(row.split()) >= 2:
                    break
                body.append(row)
                if sum(map(len, body)) > MAX_ABSTRACT_CHARS:
                    break
            if not ended or not body:
                continue
            text = _join_wrapped_lines(body)
            words = text.split()
            if (len(text) > MAX_ABSTRACT_CHARS or len(words) < MIN_ABSTRACT_WORDS
                    or _alpha_ratio(text) < 0.7
                    or not re.search(r'[.!?][\u201d\u2019\"\')]*$', text)
                    or sum(len(w) == 1 and w.isalpha() for w in words) / len(words) > 0.12
                    or '\ufffd' in text):
                continue
            fragmented = sum(len(row.split()) <= 2 for row in body) > len(body) / 3
            # Confidence reflects boundaries and quality, not character count.
            confidence = 'medium' if ocr or fragmented or len(words) < 80 else 'high'
            return text, confidence
    return '', 'low'


def _column_texts(xml: str) -> list[str]:
    """Isolate the heading's column from Poppler's positioned text rows."""
    root = ElementTree.fromstring(xml)
    candidates = []
    for page in root.findall('.//{*}page'):
        width = float(page.attrib['width'])
        rows = []
        for line in page.findall('.//{*}line'):
            text = ' '.join(word.text or '' for word in line.findall('{*}word'))
            rows.append((float(line.attrib['xMin']), float(line.attrib['yMin']),
                         float(line.attrib['xMax']), text.strip()))
        if any(_TOC_HEADING.fullmatch(row[3]) for row in rows):
            continue
        for left, top, right, heading in rows:
            if not _HEADING.fullmatch(heading):
                continue
            below = [row for row in rows if row[1] > top]
            # A second column must have several rows. A stray indented line
            # or page number is not sufficient evidence for a column split.
            neighbours = [row for row in below if row[0] > left + width * 0.25
                          and len(row[3].split()) >= 4]
            boundary = min(row[0] for row in neighbours) if len(neighbours) >= 4 else width
            column = [row for row in below
                      if left - width * 0.04 <= row[0] < left + width * 0.12
                      and row[2] <= boundary]
            if not column:
                continue
            column.sort(key=lambda row: (row[1], row[0]))
            candidates.append(heading + '\n' + '\n'.join(row[3] for row in column))
    return candidates


def recover_layout_abstract(path: str | Path, pages: tuple[str, ...]) -> tuple[str, str]:
    """Inspect at most two heading-bearing pages within the fifteen-page window."""
    executable = shutil.which('pdftotext')
    if not executable:
        return '', 'low'
    likely = [i + 1 for i, page in enumerate(pages[:ABSTRACT_RECOVERY_PAGES])
              if any(_HEADING.fullmatch(line.strip()) for line in page.splitlines())
              and not any(_TOC_HEADING.fullmatch(line.strip()) for line in page.splitlines())]
    for number in likely[:2]:
        try:
            result = subprocess.run(
                [executable, '-f', str(number), '-l', str(number), '-bbox-layout', str(path), '-'],
                capture_output=True, timeout=10, check=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            if len(result.stdout) > 2_000_000:
                continue
            for text in _column_texts(result.stdout.decode('utf-8')):
                abstract = recover_text_abstract((text,))
                if abstract[0]:
                    return abstract
        except Exception as exc:
            logger.info('Abstract column recovery unavailable on page %s: %s', number, exc)
    return '', 'low'


def _has_image(resources, depth=0) -> bool:
    """Inspect image references without decoding full-resolution image data."""
    if not resources or depth > 3:
        return False
    if hasattr(resources, 'get_object'):
        resources = resources.get_object()
    objects = resources.get('/XObject', {})
    if hasattr(objects, 'get_object'):
        objects = objects.get_object()
    for reference in list(objects.values())[:30]:
        obj = reference.get_object()
        if obj.get('/Subtype') == '/Image':
            return True
        if obj.get('/Subtype') == '/Form' and _has_image(obj.get('/Resources'), depth + 1):
            return True
    return False


def recover_ocr_abstract(path, pages, extractor, *, cover_result=None) -> tuple[str, str]:
    """Reuse cover OCR, else OCR at most two likely image-backed abstract pages.

    Page one is common for article-style theses. Later pages qualify only with
    an explicit Abstract heading in their sparse text layer. No document-level
    text threshold can suppress these page-level checks.
    """
    attempted = set()
    if cover_result is not None:
        attempted.add(1)  # Includes a cover OCR attempt that failed.
        if cover_result.method == 'ocr_tesseract':
            result = recover_text_abstract((cover_result.text,), ocr=True)
            if result[0]:
                return result
    likely = [i + 1 for i, text in enumerate(pages[:ABSTRACT_RECOVERY_PAGES])
              if i + 1 not in attempted
              and sum(c.isalpha() for c in text) < 200
              and (i == 0 or any(_HEADING.fullmatch(line.strip()) for line in text.splitlines()))]
    if not likely:
        return '', 'low'
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        for number in likely:
            if len(attempted) >= 2:
                break
            if number > len(reader.pages) or not _has_image(reader.pages[number - 1].get('/Resources')):
                continue
            attempted.add(number)
            try:
                text = extractor.ocr_abstract_page(Path(path), number)
                result = recover_text_abstract((text,), ocr=True)
                if result[0]:
                    return result
            except Exception as exc:
                logger.info('Abstract OCR unavailable on page %s: %s', number, exc)
    except Exception as exc:
        logger.info('Abstract OCR page selection unavailable: %s', exc)
    return '', 'low'
