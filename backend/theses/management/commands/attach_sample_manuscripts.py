"""Management command — attach placeholder manuscripts to theses missing files.

Usage:
    python manage.py attach_sample_manuscripts              # backfill what is missing
    python manage.py attach_sample_manuscripts --dry-run    # report, change nothing
    python manage.py attach_sample_manuscripts --force      # regenerate every thesis
    python manage.py attach_sample_manuscripts --keep-hash  # leave sha256 untouched

Why this exists
---------------
``backend/media/`` is gitignored, so a checkout carries thesis *rows* but not
the uploaded bytes those rows point at. ``ThesisDownloadView`` verifies the
file is retrievable before committing to a 200 and returns a structured
``DOCUMENT_NOT_AVAILABLE`` 404 when it is not — which the previewer surfaces
as "this thesis record exists, but its source document is not available".

This command closes that gap by generating a valid, clearly-marked placeholder
PDF for every thesis whose file is blank or absent from storage.

Idempotence
-----------
A thesis whose file is present and non-empty is skipped. Running the command
repeatedly is safe and will not overwrite a real manuscript. ``--force``
deliberately opts out of that protection.

The generated document is a placeholder, not the original manuscript. Every
page carries an "ARCHIVAL EVALUATION COPY" stamp and a footer saying so, so a
reader can never mistake it for the real submission.
"""

from __future__ import annotations

import hashlib
import os
from xml.sax.saxutils import escape

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from theses.models import FileType, Thesis

STAMP_TEXT = 'ARCHIVAL EVALUATION COPY'
FOOTER_TEXT = 'Generated placeholder — not the original manuscript'


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def _build_pdf_reportlab(thesis) -> bytes:
    """Render a two-page placeholder manuscript with ReportLab."""
    import io

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    page_width, page_height = LETTER

    def decorate(canvas, doc):
        """Diagonal stamp plus a per-page footer."""
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 40)
        # Low alpha so the stamp never obscures the text underneath.
        canvas.setFillColor(colors.Color(0.80, 0.12, 0.12, alpha=0.13))
        canvas.translate(page_width / 2.0, page_height / 2.0)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, STAMP_TEXT)
        canvas.restoreState()

        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(
            page_width / 2.0, 0.55 * inch,
            f'{FOOTER_TEXT}  ·  page {doc.page}',
        )
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        title=thesis.title or 'Untitled Thesis',
        author='; '.join(_author_list(thesis)) or 'Unknown',
        subject='THESYS+ archival evaluation copy',
        leftMargin=1.0 * inch, rightMargin=1.0 * inch,
        topMargin=1.0 * inch, bottomMargin=1.0 * inch,
    )

    base = getSampleStyleSheet()
    institution = ParagraphStyle(
        'Institution', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=10.5, alignment=TA_CENTER, leading=14, textColor=colors.HexColor('#333333'),
    )
    sub = ParagraphStyle(
        'Sub', parent=base['Normal'], fontSize=9, alignment=TA_CENTER,
        leading=12, textColor=colors.HexColor('#666666'),
    )
    title_style = ParagraphStyle(
        'ThesisTitle', parent=base['Title'], fontName='Helvetica-Bold',
        fontSize=16, leading=21, alignment=TA_CENTER, spaceAfter=6,
    )
    meta = ParagraphStyle(
        'Meta', parent=base['Normal'], fontSize=10, leading=15,
    )
    heading = ParagraphStyle(
        'SectionHeading', parent=base['Normal'], fontName='Helvetica-Bold',
        fontSize=11, leading=15, spaceBefore=14, spaceAfter=5,
        textColor=colors.HexColor('#1a1a1a'),
    )
    body = ParagraphStyle(
        'Body', parent=base['Normal'], fontSize=10, leading=15, alignment=TA_JUSTIFY,
    )
    notice = ParagraphStyle(
        'Notice', parent=base['Normal'], fontSize=9.5, leading=14,
        alignment=TA_JUSTIFY, textColor=colors.HexColor('#8a1f1f'),
    )

    def esc(value) -> str:
        return escape(str(value or ''))

    story = [
        Paragraph('PAMPANGA STATE UNIVERSITY', institution),
        Paragraph('College of Computing Studies', sub),
        Spacer(1, 0.45 * inch),
        Paragraph(esc(thesis.title) or 'Untitled Thesis', title_style),
        Spacer(1, 0.30 * inch),
    ]

    authors = _author_list(thesis)
    story.append(Paragraph(
        f'<b>Author(s):</b> {esc("; ".join(authors)) or "Not recorded"}', meta,
    ))
    story.append(Paragraph(f'<b>Program:</b> {esc(thesis.program)}', meta))
    story.append(Paragraph(f'<b>Year:</b> {esc(thesis.year)}', meta))
    if thesis.adviser:
        story.append(Paragraph(f'<b>Adviser:</b> {esc(thesis.adviser)}', meta))
    story.append(Paragraph(f'<b>Status:</b> {esc(thesis.get_status_display())}', meta))

    story.append(Paragraph('ABSTRACT', heading))
    story.append(Paragraph(
        esc(thesis.abstract) or 'No abstract was recorded for this thesis.', body,
    ))

    keywords = _keyword_list(thesis)
    if keywords:
        story.append(Paragraph('KEYWORDS', heading))
        story.append(Paragraph(esc(', '.join(keywords)), body))

    story.append(PageBreak())

    story.append(Paragraph('ABOUT THIS DOCUMENT', heading))
    story.append(Paragraph(
        f'This is an <b>{esc(STAMP_TEXT).lower()}</b> generated by the THESYS+ '
        'repository for a record whose original uploaded manuscript is not '
        'present in storage. It reproduces the catalogued metadata only. It is '
        '<b>not</b> the original submission, contains none of the original '
        'body text, figures, or appendices, and must not be cited or evaluated '
        'as the authors&#8217; work.',
        notice,
    ))
    story.append(Spacer(1, 0.20 * inch))
    story.append(Paragraph(
        'To replace this placeholder, upload the original PDF or DOCX through '
        'the thesis record in the Django admin. Doing so overwrites this file, '
        'and re-running the backfill command will leave the real manuscript '
        'untouched.',
        body,
    ))
    story.append(Paragraph('RECORD REFERENCE', heading))
    story.append(Paragraph(f'<b>Repository ID:</b> {esc(thesis.id)}', meta))

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


def _build_pdf_fallback(thesis) -> bytes:
    """Minimal hand-built PDF, used only if ReportLab is unavailable."""
    from theses.management.commands.seed_theses import _build_minimal_pdf

    header = f'[{STAMP_TEXT}] {thesis.title or "Untitled Thesis"}'
    detail = (
        f'Program: {thesis.program} | Year: {thesis.year} | '
        f'Authors: {"; ".join(_author_list(thesis)) or "Not recorded"} | '
        f'{FOOTER_TEXT}. Abstract: {thesis.abstract or "None recorded."}'
    )
    return _build_minimal_pdf(header, detail)


def build_manuscript_pdf(thesis) -> bytes:
    """Return placeholder PDF bytes for ``thesis``.

    Prefers ReportLab (pinned in requirements.txt) and degrades to the minimal
    builder the seed commands already use, so a missing optional dependency
    cannot stop a repository from being made previewable.
    """
    try:
        return _build_pdf_reportlab(thesis)
    except ImportError:
        return _build_pdf_fallback(thesis)


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def _author_list(thesis) -> list[str]:
    raw = getattr(thesis, 'authors', None)
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if a and str(a).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _keyword_list(thesis) -> list[str]:
    raw = getattr(thesis, 'keywords', None)
    if isinstance(raw, list):
        return [str(k).strip() for k in raw if k and str(k).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _slug_filename(thesis) -> str:
    slug = ''.join(c if c.isalnum() else '_' for c in (thesis.title or ''))[:60]
    return f'{slug or "thesis"}.pdf'


def file_state(thesis) -> str:
    """Classify a thesis as ``'blank'``, ``'missing'``, ``'empty'`` or ``'present'``."""
    name = thesis.uploaded_file.name if thesis.uploaded_file else ''
    if not name:
        return 'blank'
    storage = thesis.uploaded_file.storage
    try:
        if not storage.exists(name):
            return 'missing'
    except (NotImplementedError, ValueError, OSError):
        return 'missing'
    # A zero-byte file passes an existence check but cannot be rendered.
    try:
        if storage.size(name) == 0:
            return 'empty'
    except (NotImplementedError, ValueError, OSError):
        return 'missing'
    return 'present'


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        'Generate placeholder manuscript PDFs for theses whose uploaded file '
        'is blank or missing from storage, so the preview endpoint can serve them.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help=(
                'Regenerate a placeholder for EVERY thesis, replacing files that '
                'are already present. Not idempotent — use deliberately.'
            ),
        )
        parser.add_argument(
            '--keep-hash',
            action='store_true',
            help=(
                'Leave Thesis.sha256 untouched. By default the hash is recomputed '
                'so it describes the bytes actually on disk.'
            ),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        keep_hash = options['keep_hash']

        theses = list(Thesis.objects.all().order_by('year', 'created_at'))
        if not theses:
            self.stdout.write(self.style.WARNING('No theses in the repository.'))
            return

        # ── Audit first, so the operator sees the scope before any write ──
        buckets: dict[str, list] = {'blank': [], 'missing': [], 'empty': [], 'present': []}
        for thesis in theses:
            buckets[file_state(thesis)].append(thesis)

        self.stdout.write('Repository audit')
        self.stdout.write(f'  total theses          : {len(theses)}')
        self.stdout.write(f'  file present          : {len(buckets["present"])}')
        self.stdout.write(f'  file field blank      : {len(buckets["blank"])}')
        self.stdout.write(f'  file missing on disk  : {len(buckets["missing"])}')
        self.stdout.write(f'  file present but empty: {len(buckets["empty"])}')

        if force:
            targets = theses
            self.stdout.write(self.style.WARNING(
                f'\n--force: regenerating all {len(targets)} theses, '
                'including ones with existing files.'
            ))
        else:
            targets = buckets['blank'] + buckets['missing'] + buckets['empty']

        if not targets:
            self.stdout.write(self.style.SUCCESS(
                '\nEvery thesis already has a readable file. Nothing to do.'
            ))
            return

        self.stdout.write(f'\n{len(targets)} thesis(es) need a manuscript.')

        if dry_run:
            for thesis in targets[:20]:
                name = thesis.uploaded_file.name or '(blank)'
                self.stdout.write(f'  would write  {name}  <-  {thesis.title[:52]}')
            if len(targets) > 20:
                self.stdout.write(f'  ... and {len(targets) - 20} more')
            self.stdout.write(self.style.WARNING(
                '\n--dry-run: no files written, no rows changed.'
            ))
            return

        written = 0
        failed = 0
        for thesis in targets:
            try:
                self._attach(thesis, keep_hash=keep_hash)
                written += 1
                self.stdout.write(f'  [OK] {thesis.uploaded_file.name}')
            except Exception as exc:
                failed += 1
                self.stderr.write(f'  [FAIL] {thesis.title[:52]} -- {exc}')

        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(
            f'\nDone -- {written} manuscript(s) attached, {failed} failed.'
        ))

        remaining = sum(
            1 for thesis in Thesis.objects.all() if file_state(thesis) != 'present'
        )
        if remaining:
            self.stdout.write(self.style.WARNING(
                f'{remaining} thesis(es) still have no readable file.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Every thesis in the repository now has a readable file.'
            ))

    # ------------------------------------------------------------------
    def _attach(self, thesis, *, keep_hash: bool) -> None:
        """Generate and persist a placeholder manuscript for one thesis."""
        pdf_bytes = build_manuscript_pdf(thesis)

        # Reuse the recorded basename so an existing DB path is honoured
        # rather than a second file appearing alongside it.
        existing = thesis.uploaded_file.name or ''
        basename = os.path.basename(existing) or _slug_filename(thesis)

        update_fields = ['uploaded_file', 'file_type', 'updated_at']

        with transaction.atomic():
            thesis.file_type = FileType.PDF
            if not keep_hash:
                thesis.sha256 = hashlib.sha256(pdf_bytes).hexdigest()
                update_fields.append('sha256')

            # save=False: write the bytes and set the field name, then persist
            # the row once with an explicit field list.
            thesis.uploaded_file.save(basename, ContentFile(pdf_bytes), save=False)
            try:
                thesis.save(update_fields=update_fields)
            except IntegrityError:
                # sha256 is UNIQUE. Two placeholders can only collide if two
                # theses carry identical metadata; keep the original hash
                # rather than failing the whole run.
                thesis.refresh_from_db(fields=['sha256'])
                thesis.uploaded_file.save(basename, ContentFile(pdf_bytes), save=False)
                thesis.save(update_fields=['uploaded_file', 'file_type', 'updated_at'])
