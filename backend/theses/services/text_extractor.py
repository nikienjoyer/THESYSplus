"""Thesis text extraction pipeline — Phase 1.

Per the approved THESYS+ architecture:

* PDF: extract text directly with ``pypdf`` (fast, accurate when the PDF
  has a real text layer). If the extracted result is short or empty,
  fall back to Tesseract OCR via ``pdf2image`` for scanned PDFs.
* DOCX: extract text with ``python-docx`` (paragraphs + table cells).

The extracted text is stored verbatim in ``Thesis.extracted_text`` and
will feed Phase 2 (SBERT, TF-IDF, K-Means).

PAGE LIMITING
-------------
``extract()`` accepts an optional ``max_pages`` keyword. It defaults to
``None``, meaning *unlimited* — the full-document behaviour the upload
pipeline depends on is therefore unchanged.

Front-matter callers (title/metadata detection) pass a small limit so they
read only the title page and abstract instead of a whole 93-page thesis.
The saving is largest in the OCR path: a scanned PDF rasterised at 200 dpi
costs roughly 12 MB per page in memory, so the previous 50-page OCR ceiling
could allocate hundreds of megabytes to find a title printed on page one.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

logger = logging.getLogger(__name__)

# Heuristic threshold: if direct PDF text extraction yields fewer than
# this many printable characters, treat the PDF as scanned and fall back
# to OCR. 200 chars is roughly two short paragraphs — generous enough to
# avoid OCR for typed theses with sparse first pages.
PDF_TEXT_FALLBACK_THRESHOLD = 200

# Hard ceiling on pages sent to Tesseract, regardless of ``max_pages``.
# Rasterising at 200 dpi is memory-hungry, so this stays a runaway guard
# even when a caller asks for more.
OCR_MAX_PAGES = 50

# Pages that reliably contain a thesis' title page and its immediate
# surroundings. Enough for title / authors / program / year, all of which sit
# on page one. Callers doing title-only detection pass this as ``max_pages``.
FRONT_MATTER_PAGES = 5

# Wider window for full metadata extraction. The abstract is the one field
# that is not on the title page — depending on the template it follows the
# approval sheet, acknowledgements and dedication, so it can land as late as
# page 8. Still a ~9x reduction against a typical 93-page thesis.
METADATA_PAGES = 10


# ---------------------------------------------------------------------------
# Letter-spaced text repair (Canva-exported PDFs)
# ---------------------------------------------------------------------------
#
# Canva positions every glyph individually, so pypdf emits a space between
# every character: the text layer yields 'A B S T R A C T', never 'ABSTRACT'.
# Every heading regex downstream is anchored on whole words, so all of them
# fail, and a letter-spaced line's alphabetic ratio sits near 0.47 — below
# MIN_PROSE_ALPHA_RATIO — so title candidates are disqualified outright.
#
# 17 of the 50 theses in this repository are affected; /Producer is 'Canva' for
# every one of them and for no unaffected file.
#
# WHY PER LINE, NOT PER DOCUMENT
# ------------------------------
# A document-wide ratio threshold was considered and rejected on two grounds:
#
#   * It misses partially-affected files. Canva letter-spaces its display-font
#     HEADING lines while leaving body prose clean, so one real thesis
#     (TASKGROVE) sits at a document-wide ratio of only 0.261 — under any
#     workable threshold — despite its title being unreadable.
#   * It forces a whole-text rewrite, which collapses the 2-or-more space runs
#     that occur naturally in clean prose.
#
# Deciding per line makes the no-op property STRUCTURAL rather than
# threshold-dependent: a line that does not trip the detector is returned
# byte-identical, so a clean document cannot be altered at all.

# A line must be at least this proportion single-character tokens.
_SPACED_SINGLE_TOKEN_RATIO = 0.6

# ...and carry at least this many tokens, so a short fragment like 'A B' cannot
# qualify.
_SPACED_MIN_TOKENS = 4

# ...and at least this many of its single-character tokens must be LETTERS.
#
# This condition is not optional. A numeric table row such as '1 2 3 4 5' is
# 100% single-character tokens and would otherwise be joined into '12345',
# silently corrupting table content — Likert-scale rows in a results chapter
# look exactly like that. Letter-spaced prose always carries many single
# letters; a numeric row carries none.
_SPACED_MIN_ALPHA_SINGLES = 4

# Canva marks a word boundary with a DOUBLE space and an intra-word glyph gap
# with a single space, so runs of 2+ spaces are the word separators.
_WORD_GROUP_SEPARATOR = re.compile(r' {2,}')


def _line_is_letter_spaced(line: str) -> bool:
    """True when ``line`` looks like per-glyph-positioned text.

    All three conditions must hold — see the constants above for why each
    exists. Conservative by design: a false positive rewrites real content,
    while a false negative merely leaves a line as it is today.
    """
    tokens = line.split()
    if len(tokens) < _SPACED_MIN_TOKENS:
        return False

    singles = [t for t in tokens if len(t) == 1]
    if len(singles) / len(tokens) < _SPACED_SINGLE_TOKEN_RATIO:
        return False

    alpha_singles = sum(1 for t in singles if t.isalpha())
    return alpha_singles >= _SPACED_MIN_ALPHA_SINGLES


def _despace_line(line: str) -> str:
    """Rejoin a letter-spaced line into ordinary words.

    'A B S T R A C T' -> 'ABSTRACT'
    'D O R M I F Y :  D O R M  F I N D E R' -> 'DORMIFY: DORM FINDER'

    Empty groups are dropped so leading or trailing space runs do not leave
    stray separators. Interior runs never produce an empty group, so word
    boundaries are unaffected.
    """
    groups = _WORD_GROUP_SEPARATOR.split(line)
    words = [''.join(group.split()) for group in groups]
    return ' '.join(w for w in words if w)


def despace_text(text: str) -> tuple[str, int]:
    """Repair every letter-spaced line in ``text``.

    Returns ``(repaired_text, lines_repaired)``. Lines that do not trip the
    detector are passed through BYTE-IDENTICAL — no stripping, no whitespace
    normalisation — so a document with no affected lines round-trips exactly.
    """
    lines = (text or '').split('\n')
    repaired = 0
    out = []
    for line in lines:
        if _line_is_letter_spaced(line):
            out.append(_despace_line(line))
            repaired += 1
        else:
            out.append(line)
    return '\n'.join(out), repaired


@dataclass(frozen=True)
class ExtractionResult:
    """Result of a thesis text extraction.

    Attributes
    ----------
    text:
        The extracted plain text (UTF-8 string). Empty if extraction
        failed entirely.
    method:
        How the text was obtained — one of ``pypdf``, ``pypdf+despaced``,
        ``ocr_tesseract``, ``python_docx``, or ``failed``.

        ``pypdf+despaced`` means the text layer was letter-spaced (see
        ``despace_text``) and at least one line was rejoined. It is reported
        separately from plain ``pypdf`` so a rewrite is never silent.
    success:
        True when at least one character was extracted.
    error:
        Human-readable error message when ``success`` is False.
    """

    text: str
    method: str
    success: bool
    error: str | None = None


class ThesisTextExtractor:
    """Extracts plain text from PDF or DOCX thesis files."""

    def extract(
        self,
        file_path: str | Path,
        *,
        max_pages: int | None = None,
    ) -> ExtractionResult:
        """Dispatch on file extension.

        Args:
            file_path: Absolute path to the uploaded thesis file.
            max_pages: Read at most this many leading pages. ``None`` (the
                default) means read the whole document, which is what the
                upload pipeline requires — ``Thesis.extracted_text`` feeds
                semantic search and must cover the full text. Pass
                ``FRONT_MATTER_PAGES`` for title/metadata detection.
                Values ``<= 0`` are treated as ``None``.

        Returns:
            ExtractionResult with extracted text + method used.

        Note:
            ``max_pages`` is ignored for DOCX. A .docx file stores a flat
            paragraph stream with no page boundaries — pagination is
            computed by the renderer at layout time and simply is not
            present in the file — so there is nothing to slice. Front
            matter still lands at the top of the returned text, so
            detection heuristics that scan the first lines are unaffected.
        """
        path = Path(file_path)
        ext = path.suffix.lower().lstrip('.')

        if max_pages is not None and max_pages <= 0:
            max_pages = None

        if ext == 'pdf':
            return self._extract_pdf(path, max_pages=max_pages)
        if ext == 'docx':
            return self._extract_docx(path)

        return ExtractionResult(
            text='',
            method='failed',
            success=False,
            error=f'Unsupported file extension: .{ext}',
        )

    # ── PDF ─────────────────────────────────────────────────────────────

    def _extract_pdf(
        self,
        path: Path,
        *,
        max_pages: int | None = None,
    ) -> ExtractionResult:
        """Try direct text extraction; fall back to OCR for scanned PDFs."""
        # Step 1: try pypdf for machine-readable PDFs
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            # islice rather than reader.pages[:n] — it works on any iterable
            # and does not depend on pypdf's virtual list supporting slices.
            pages = (
                reader.pages if max_pages is None
                else islice(reader.pages, max_pages)
            )
            pages_text = []
            for page in pages:
                try:
                    pages_text.append(page.extract_text() or '')
                except Exception as page_err:  # pragma: no cover - defensive
                    logger.warning('pypdf page failed for %s: %s', path, page_err)
            direct_text = '\n\n'.join(pages_text).strip()

            # Repair letter-spaced lines HERE, at assembly, rather than at each
            # return site. Three separate returns below hand back pypdf text
            # (the normal path plus two last-resort paths when OCR yields
            # nothing), and repairing once means they cannot drift apart.
            #
            # The OCR path is deliberately NOT repaired: its text comes from
            # Tesseract, whose failure modes are different, and it is out of
            # scope here.
            direct_text, despaced_lines = despace_text(direct_text)
            if despaced_lines:
                # 'pypdf+despaced' rather than a silent repair — a rewrite of
                # stored text has to be auditable from the result object.
                pypdf_method = 'pypdf+despaced'
                logger.info(
                    'Repaired %d letter-spaced line(s) in %s', despaced_lines, path,
                )
            else:
                pypdf_method = 'pypdf'

            if len(direct_text) >= PDF_TEXT_FALLBACK_THRESHOLD:
                return ExtractionResult(
                    text=direct_text,
                    method=pypdf_method,
                    success=True,
                )
            # Else: proceed to OCR fallback
        except Exception as exc:
            logger.warning('pypdf extraction failed for %s: %s', path, exc)
            direct_text = ''
            pypdf_method = 'pypdf'

        # Step 2: OCR fallback for scanned PDFs
        try:
            ocr_text = self._ocr_pdf(path, max_pages=max_pages)
            if ocr_text.strip():
                return ExtractionResult(
                    text=ocr_text,
                    method='ocr_tesseract',
                    success=True,
                )
            # Last resort — return whatever pypdf gave us, even if short
            if direct_text:
                return ExtractionResult(
                    text=direct_text,
                    method=pypdf_method,
                    success=True,
                )
            return ExtractionResult(
                text='',
                method='failed',
                success=False,
                error='Both pypdf and Tesseract OCR yielded no text',
            )
        except Exception as exc:
            # OCR failed but we may still have partial pypdf text — keep it
            if direct_text:
                return ExtractionResult(
                    text=direct_text,
                    method=pypdf_method,
                    success=True,
                )
            return ExtractionResult(
                text='',
                method='failed',
                success=False,
                error=f'PDF extraction failed: {exc}',
            )

    def _ocr_pdf(self, path: Path, *, max_pages: int | None = None) -> str:
        """OCR the leading pages of a scanned PDF using Tesseract.

        Reuses the existing identity-verification OCR setup so Tesseract
        path discovery (Windows + Linux) is identical.

        ``OCR_MAX_PAGES`` remains a hard ceiling: theses longer than that are
        atypical and capping protects against runaway OCR jobs. A caller's
        ``max_pages`` can only lower it, never raise it — so passing
        ``max_pages=None`` reproduces the previous behaviour exactly.
        """
        # Late imports keep this module lightweight when OCR isn't needed.
        import pytesseract
        from pdf2image import convert_from_path
        from identity_verification.services.ocr_extractor import (
            _configure_tesseract_path,
            OCRExtractor,
        )

        # Trigger Tesseract path discovery exactly once.
        if not OCRExtractor._tesseract_configured:
            _configure_tesseract_path()
            OCRExtractor._tesseract_configured = True

        last_page = (
            OCR_MAX_PAGES if max_pages is None
            else min(max_pages, OCR_MAX_PAGES)
        )
        images = convert_from_path(str(path), dpi=200, first_page=1, last_page=last_page)
        page_texts: list[str] = []
        for img in images:
            try:
                page_texts.append(pytesseract.image_to_string(img, timeout=30))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning('Tesseract failed on PDF page: %s', exc)
        return '\n\n'.join(t.strip() for t in page_texts if t and t.strip())

    # ── DOCX ────────────────────────────────────────────────────────────

    def _extract_docx(self, path: Path) -> ExtractionResult:
        try:
            from docx import Document

            doc = Document(str(path))
            chunks: list[str] = []

            # Body paragraphs
            for para in doc.paragraphs:
                txt = para.text.strip()
                if txt:
                    chunks.append(txt)

            # Table cells (abstracts often live in a 1-cell table)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            chunks.append(cell_text)

            text = '\n\n'.join(chunks)
            if not text:
                return ExtractionResult(
                    text='',
                    method='failed',
                    success=False,
                    error='DOCX contains no extractable text',
                )
            return ExtractionResult(
                text=text,
                method='python_docx',
                success=True,
            )
        except Exception as exc:
            return ExtractionResult(
                text='',
                method='failed',
                success=False,
                error=f'DOCX extraction failed: {exc}',
            )
