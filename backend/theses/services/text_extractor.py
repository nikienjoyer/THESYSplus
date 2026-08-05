"""Thesis text extraction pipeline — Phase 1.

Per the approved THESYS+ architecture:

* PDF: extract text directly with ``pypdf`` (fast, accurate when the PDF
  has a real text layer). If the extracted result is short or empty,
  fall back to Tesseract OCR via ``pdf2image`` for scanned PDFs.
* DOCX: extract text with ``python-docx`` (paragraphs + table cells).

The extracted text is stored verbatim in ``Thesis.extracted_text`` and
will feed Phase 2 (SBERT, TF-IDF, K-Means).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Heuristic threshold: if direct PDF text extraction yields fewer than
# this many printable characters, treat the PDF as scanned and fall back
# to OCR. 200 chars is roughly two short paragraphs — generous enough to
# avoid OCR for typed theses with sparse first pages.
PDF_TEXT_FALLBACK_THRESHOLD = 200


@dataclass(frozen=True)
class ExtractionResult:
    """Result of a thesis text extraction.

    Attributes
    ----------
    text:
        The extracted plain text (UTF-8 string). Empty if extraction
        failed entirely.
    method:
        How the text was obtained — one of ``pypdf``, ``ocr_tesseract``,
        ``python_docx``, or ``failed``.
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

    def extract(self, file_path: str | Path) -> ExtractionResult:
        """Dispatch on file extension.

        Args:
            file_path: Absolute path to the uploaded thesis file.

        Returns:
            ExtractionResult with extracted text + method used.
        """
        path = Path(file_path)
        ext = path.suffix.lower().lstrip('.')

        if ext == 'pdf':
            return self._extract_pdf(path)
        if ext == 'docx':
            return self._extract_docx(path)

        return ExtractionResult(
            text='',
            method='failed',
            success=False,
            error=f'Unsupported file extension: .{ext}',
        )

    # ── PDF ─────────────────────────────────────────────────────────────

    def _extract_pdf(self, path: Path) -> ExtractionResult:
        """Try direct text extraction; fall back to OCR for scanned PDFs."""
        # Step 1: try pypdf for machine-readable PDFs
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages_text = []
            for page in reader.pages:
                try:
                    pages_text.append(page.extract_text() or '')
                except Exception as page_err:  # pragma: no cover - defensive
                    logger.warning('pypdf page failed for %s: %s', path, page_err)
            direct_text = '\n\n'.join(pages_text).strip()

            if len(direct_text) >= PDF_TEXT_FALLBACK_THRESHOLD:
                return ExtractionResult(
                    text=direct_text,
                    method='pypdf',
                    success=True,
                )
            # Else: proceed to OCR fallback
        except Exception as exc:
            logger.warning('pypdf extraction failed for %s: %s', path, exc)
            direct_text = ''

        # Step 2: OCR fallback for scanned PDFs
        try:
            ocr_text = self._ocr_pdf(path)
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
                    method='pypdf',
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
                    method='pypdf',
                    success=True,
                )
            return ExtractionResult(
                text='',
                method='failed',
                success=False,
                error=f'PDF extraction failed: {exc}',
            )

    def _ocr_pdf(self, path: Path) -> str:
        """OCR every page of a scanned PDF using Tesseract.

        Reuses the existing identity-verification OCR setup so Tesseract
        path discovery (Windows + Linux) is identical. We process up to 50
        pages; theses longer than that are atypical and capping protects
        against runaway OCR jobs.
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

        max_pages = 50
        images = convert_from_path(str(path), dpi=200, first_page=1, last_page=max_pages)
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
