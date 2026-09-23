"""HTTP views for the theses app — Phase 1.

Public surface (authenticated):
* ``GET    /api/v1/theses/``                    — list with filters/search
* ``GET    /api/v1/theses/{id}/``               — detail
* ``GET    /api/v1/theses/{id}/download/``      — file stream
* ``POST   /api/v1/theses/upload/``             — upload + extract text

Role visibility:
* student              → status='approved' only (or own uploads in any status)
* faculty/administrator → all statuses
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from common.errors import make_error_response

from .models import EmbeddingStatus, FileType, Thesis, ThesisStatus
from .serializers import (
    ThesisDetailSerializer,
    ThesisListItemSerializer,
    ThesisUploadSerializer,
)
from .services.preview_pdf import render_docx_to_pdf
from .services.text_extractor import ThesisTextExtractor
from .services.watermark_pdf import (
    DOWNLOAD_WATERMARK,
    PREVIEW_WATERMARK,
    WATERMARK_VERSION,
    EncryptedPdfError,
    WatermarkError,
    stamp_pdf,
)
from .validators import validate_thesis_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class _ThesisPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _visible_queryset(user) -> 'models.QuerySet[Thesis]':
    """Apply role-based visibility rules."""
    qs = Thesis.objects.all().select_related('uploaded_by')
    role = getattr(user, 'role', None)
    if role in (Role.FACULTY, Role.ADMINISTRATOR):
        return qs
    # Student: approved only, plus own uploads regardless of status
    return qs.filter(
        models.Q(status=ThesisStatus.APPROVED) | models.Q(uploaded_by=user)
    )


# Late import alias so _visible_queryset can use Q without polluting top-level
from django.db import models  # noqa: E402


# ---------------------------------------------------------------------------
# GET /theses/  — list with filters + simple search
# ---------------------------------------------------------------------------

class ThesisListView(APIView):
    """List theses with filters: ``q``, ``year``, ``program``, ``status``, ``mine``, ``ids``.

    When ``q`` is provided, the list is reranked by SBERT cosine similarity
    against the candidate set (filters are applied first to narrow the set,
    then semantic ranking sorts the survivors). When ``q`` is empty the
    standard chronological ordering is used.

    ``mine=true`` narrows the result to the requesting user's own uploads.
    It is applied on top of the role-based ``_visible_queryset``, never in
    place of it, so it cannot surface a thesis the caller couldn't already
    see — for a student that's just their own uploads regardless of status
    (which ``_visible_queryset`` already includes), and for faculty/admin
    it's the same filter over the full unrestricted set.

    ``ids`` accepts a comma-separated list of thesis UUIDs and narrows the
    result to exactly those theses — e.g. rendering a specific set of IDs
    obtained from another endpoint (such as a topic cluster's membership
    list). Applied on top of ``_visible_queryset`` like every other filter
    here: unknown or non-visible IDs simply don't match any row and are
    silently absent from the result, never an error. A malformed UUID in
    the list, or more IDs than ``MAX_IDS``, returns ``INVALID_FILTER``.
    """

    permission_classes = [IsAuthenticated]

    # A few hundred is enough to render any single cluster/collection in one
    # request (the largest cluster in the current corpus is ~47) while
    # keeping the query param from being abused as an unbounded batch load.
    MAX_IDS = 300

    def get(self, request, *args, **kwargs):
        qs = _visible_queryset(request.user)

        q = (request.query_params.get('q') or '').strip()

        # Similarity threshold: user-supplied float in [0.0, 1.0].
        # Defaults to the all-MiniLM-L6-v2 noise floor (0.10).
        # The frontend exposes this as a percentage slider (30–95 %).
        try:
            min_score = float(request.query_params.get('min_score', 0.10))
            min_score = max(0.0, min(1.0, min_score))
        except (ValueError, TypeError):
            min_score = 0.10

        year = request.query_params.get('year')
        if year:
            try:
                qs = qs.filter(year=int(year))
            except ValueError:
                return make_error_response(
                    code='INVALID_FILTER',
                    message='year must be an integer.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        program = request.query_params.get('program')
        if program:
            qs = qs.filter(program=program)

        status_filter = request.query_params.get('status')
        if status_filter:
            valid = {s.value for s in ThesisStatus}
            if status_filter not in valid:
                return make_error_response(
                    code='INVALID_FILTER',
                    message=f'status must be one of {sorted(valid)}.',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)

        mine = request.query_params.get('mine')
        if mine is not None:
            # Parsed explicitly rather than coerced (bool('false') is True) —
            # any value other than 'true'/'false' (case-insensitive) is a
            # caller mistake, not a silent false. Layered on top of the
            # already-role-scoped ``qs``, so this can only narrow further —
            # it can never surface a thesis outside the caller's visible set.
            mine_lower = mine.strip().lower()
            if mine_lower not in ('true', 'false'):
                return make_error_response(
                    code='INVALID_FILTER',
                    message="mine must be 'true' or 'false'.",
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if mine_lower == 'true':
                qs = qs.filter(uploaded_by=request.user)

        ids_param = request.query_params.get('ids')
        if ids_param is not None:
            raw_ids = [v.strip() for v in ids_param.split(',') if v.strip()]
            if len(raw_ids) > self.MAX_IDS:
                return make_error_response(
                    code='INVALID_FILTER',
                    message=f'ids accepts at most {self.MAX_IDS} values.',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            parsed_ids = []
            for raw_id in raw_ids:
                try:
                    parsed_ids.append(uuid.UUID(raw_id))
                except ValueError:
                    return make_error_response(
                        code='INVALID_FILTER',
                        message=f"ids contains an invalid UUID: '{raw_id}'.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # Layered on top of the role-scoped `qs` like every other filter
            # here — an ID for a thesis outside the caller's visible set
            # (e.g. another student's pending upload) simply matches no row,
            # rather than being an error or a visibility bypass.
            qs = qs.filter(id__in=parsed_ids)

        # ── No query → chronological listing ────────────────────────────
        if not q:
            qs = qs.order_by('-created_at')
            paginator = _ThesisPagination()
            page = paginator.paginate_queryset(qs, request, view=self)
            data = ThesisListItemSerializer(page, many=True).data
            return paginator.get_paginated_response(data)

        # ── Query → SBERT semantic ranking ──────────────────────────────
        # Filters have already been applied to ``qs``. We materialise the
        # candidate set, rank by cosine similarity, then paginate
        # manually so similarity_score is preserved on each result.
        from .services.semantic_search import rank_theses

        candidates = list(qs)
        try:
            scored = rank_theses(q, candidates)
        except Exception as exc:
            logger.warning('Semantic search failed (%s) — falling back to keyword search', exc)
            from django.db.models import Q
            qs_kw = qs.filter(
                Q(title__icontains=q)
                | Q(abstract__icontains=q)
                | Q(authors__icontains=q)
                | Q(keywords__icontains=q)
            ).order_by('-created_at')
            paginator = _ThesisPagination()
            page = paginator.paginate_queryset(qs_kw, request, view=self)
            data = ThesisListItemSerializer(page, many=True).data
            return paginator.get_paginated_response(data)

        # Drop results below the similarity threshold.
        # min_score defaults to 0.10 (noise floor for all-MiniLM-L6-v2);
        # the frontend exposes a 30–95 % slider that overrides this.
        #
        # Title-match boost (narrow):
        # When a query is a *specific identifier* — an acronym, a brand name
        # with punctuation, or a multi-word phrase — and that query appears
        # verbatim in a thesis title, we clamp the score to at least min_score
        # so it survives the threshold filter.
        #
        # This handles cases like "THESYS+", "RFID", "IPv4", or
        # "Face Recognition" where SBERT produces a low cosine score because
        # the query is a proper noun / acronym with no sentence-level semantics.
        #
        # Generic single words such as "computer", "system", or "web" are
        # intentionally excluded: they appear in almost every thesis title and
        # should not bypass the threshold.
        #
        # A query qualifies for the boost when ANY of:
        #   1. It contains non-alphanumeric punctuation ("+", "-", ".", "#", …)
        #   2. It is a single word that is fully UPPERCASE and ≥ 3 characters
        #      (all-caps acronym: "RFID", "NLP", "BERT", "BSIT")
        #   3. It has ≥ 2 space-separated tokens (multi-word exact phrase)

        import re as _re

        def _is_specific_identifier(query: str) -> bool:
            stripped = query.strip()
            # Rule 1: contains any non-alphanumeric, non-space character
            if _re.search(r'[^a-zA-Z0-9\s]', stripped):
                return True
            tokens = stripped.split()
            # Rule 2: single all-uppercase token of ≥ 3 characters
            if len(tokens) == 1 and stripped == stripped.upper() and len(stripped) >= 3:
                return True
            # Rule 3: multi-word phrase
            if len(tokens) >= 2:
                return True
            return False

        apply_boost = _is_specific_identifier(q)
        q_lower = q.lower()
        boosted = []
        for s in scored:
            effective_score = s.score
            if apply_boost and q_lower in s.thesis.title.lower():
                effective_score = max(effective_score, min_score)
            if effective_score >= min_score:
                boosted.append(s)
        scored = boosted

        # Manual pagination
        paginator = _ThesisPagination()
        total = len(scored)
        page_size = min(
            int(request.query_params.get('page_size', paginator.page_size)),
            paginator.max_page_size,
        )
        try:
            page_number = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page_number = 1
        start = (page_number - 1) * page_size
        end = start + page_size
        page_slice = scored[start:end]

        # Attach similarity_score onto each thesis instance for serializer
        results = []
        for s in page_slice:
            s.thesis.similarity_score = round(s.score, 4)
            results.append(s.thesis)

        data = ThesisListItemSerializer(results, many=True).data

        # Build a paginated response shape consistent with PageNumberPagination
        from django.utils.http import urlencode
        base_url = request.build_absolute_uri(request.path)
        qparams = dict(request.query_params)

        def _link(page_num):
            qparams_copy = {k: v for k, v in qparams.items() if k != 'page'}
            qparams_copy['page'] = str(page_num)
            return f'{base_url}?{urlencode(qparams_copy, doseq=True)}'

        next_link = _link(page_number + 1) if end < total else None
        prev_link = _link(page_number - 1) if page_number > 1 else None

        return Response({
            'count': total,
            'next': next_link,
            'previous': prev_link,
            'results': data,
        })


# ---------------------------------------------------------------------------
# GET /theses/{id}/ — detail
# ---------------------------------------------------------------------------

def _resolve_thesis(id_str: str, user) -> Thesis:
    try:
        uid = uuid.UUID(str(id_str))
    except (ValueError, TypeError):
        raise NotFound(detail='Thesis not found.')
    qs = _visible_queryset(user)
    try:
        return qs.get(pk=uid)
    except Thesis.DoesNotExist:
        raise NotFound(detail='Thesis not found.')


class ThesisDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id, *args, **kwargs):
        thesis = _resolve_thesis(id, request.user)
        return Response(ThesisDetailSerializer(thesis).data)


# ---------------------------------------------------------------------------
# GET /theses/{id}/download/ — inline PDF stream for the in-browser previewer
# ---------------------------------------------------------------------------

def _preview_filename(thesis: Thesis, *, preview: bool = True) -> str:
    """Build the stable, institution-branded served filename.

    Shape: ``THESYSplus_<YEAR>_<SLUG>_Preview.pdf`` for an inline preview, or
    ``THESYSplus_<YEAR>_<SLUG>.pdf`` for an attachment download. The slug is
    derived from the thesis title so the tab/save-as name is meaningful instead
    of exposing the raw stored upload name.

    Filename and watermark text are independent concerns: this helper knows
    nothing about which watermark was stamped, and the stamper knows nothing
    about the filename. Both happen to key off disposition, separately.
    """
    slug = slugify(thesis.title or '')[:60].strip('-') or 'thesis'
    year = thesis.year or 'undated'
    suffix = '_Preview' if preview else ''
    return f'THESYSplus_{year}_{slug}{suffix}.pdf'


# Cached stamped artifacts live under their own prefix so they are never
# confused with originals under ``theses/%Y/``. Written through the storage
# API rather than raw paths, because this project moves to object storage later.
WATERMARK_CACHE_PREFIX = 'theses/_watermarked'


def _watermark_cache_name(thesis: Thesis, disposition: str) -> str:
    """Storage name for a thesis's stamped artifact.

    Keyed on the source sha256 so replacing the underlying file invalidates
    automatically, on WATERMARK_VERSION so changing the stamp invalidates every
    existing artifact, and on disposition because the two watermark texts
    produce genuinely different bytes.
    """
    return (
        f'{WATERMARK_CACHE_PREFIX}/{thesis.id}/'
        f'{thesis.sha256}-v{WATERMARK_VERSION}-{disposition}.pdf'
    )


def _stamped_pdf_bytes(thesis: Thesis, disposition: str) -> bytes:
    """Return watermarked PDF bytes for ``thesis``, generating on cache miss.

    Stamping a 100-page thesis costs 1-2 seconds of CPU, and this endpoint is
    hit on every preview page load, so the result is cached. Django's cache
    framework is deliberately NOT used: the default backend is LocMemCache,
    which is per-process and would pin ~20 MB blobs in memory per worker.

    Raises:
        WatermarkError: source encrypted, unreadable, or stamping failed.
        Exception: DOCX conversion failed (propagated from render_docx_to_pdf).
    """
    cache_name = _watermark_cache_name(thesis, disposition)

    try:
        if default_storage.exists(cache_name):
            with default_storage.open(cache_name, 'rb') as cached:
                return cached.read()
    except (OSError, ValueError, NotImplementedError) as exc:
        # A broken cache must never break serving — fall through and regenerate.
        logger.warning('Thesis %s: watermark cache read failed (%s)', thesis.id, exc)

    if thesis.file_type == FileType.DOCX:
        source_bytes = render_docx_to_pdf(thesis.uploaded_file.path)
    else:
        with thesis.uploaded_file.open('rb') as handle:
            source_bytes = handle.read()

    text = DOWNLOAD_WATERMARK if disposition == 'attachment' else PREVIEW_WATERMARK
    stamped = stamp_pdf(source_bytes, text)

    try:
        # Racing requests would both generate identical bytes; the loser's
        # save() lands under a suffixed name that is never read again. Harmless
        # duplication, not corruption, so it isn't worth a lock.
        if not default_storage.exists(cache_name):
            default_storage.save(cache_name, ContentFile(stamped))
    except (OSError, ValueError, NotImplementedError) as exc:
        logger.warning('Thesis %s: watermark cache write failed (%s)', thesis.id, exc)

    return stamped


def _document_unavailable_response(thesis: Thesis, reason: str):
    """Structured 404 for a thesis whose source document can't be served.

    Returned instead of a metadata-only stand-in PDF: a stand-in is
    indistinguishable from the real document to the viewer, so a missing
    or unconvertible file silently rendered as "the preview". Callers get
    an explicit, machine-readable failure they can surface in the UI.
    """
    return make_error_response(
        code='DOCUMENT_NOT_AVAILABLE',
        message=(
            'The source document for this thesis is not available for preview. '
            'The record exists, but its uploaded file could not be read.'
        ),
        status=status.HTTP_404_NOT_FOUND,
        details={'thesis_id': str(thesis.id), 'reason': reason},
    )


class ThesisDownloadView(APIView):
    """Serve the thesis document as watermarked ``application/pdf``.

    * PDF uploads are stamped and served.
    * DOCX uploads are converted to PDF on the fly, then stamped identically —
      the conversion output is never persisted as the thesis file.
    * A record with no file, a file absent from storage, an encrypted source,
      or a DOCX that fails conversion yields a structured
      ``DOCUMENT_NOT_AVAILABLE`` 404 — never an unhandled 500, and never a
      silent stand-in document.

    ``?disposition=attachment`` serves a download; anything else (including
    omitting it) serves the inline preview, preserving existing behaviour for
    every current caller.

    THERE IS NO UNSTAMPED RESPONSE. Both dispositions go through the stamper,
    because a clean inline stream would make the watermarked download pointless
    — the original would still be one network-tab click away.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, id, *args, **kwargs):
        thesis = _resolve_thesis(id, request.user)

        # Unknown values fall back to inline rather than erroring: this
        # endpoint's existing contract is "give me the preview", and a typo in a
        # query string should not break a page load.
        disposition = (
            'attachment'
            if request.query_params.get('disposition') == 'attachment'
            else 'inline'
        )

        if not thesis.uploaded_file or not thesis.uploaded_file.name:
            logger.warning('Thesis %s: no uploaded file on record', thesis.id)
            return _document_unavailable_response(thesis, 'no_file_on_record')

        # Verify the bytes are actually retrievable before committing to a
        # 200. ``FieldFile.storage.exists`` covers the common case (record
        # kept, file pruned/never copied) without reading the whole file.
        try:
            file_present = thesis.uploaded_file.storage.exists(thesis.uploaded_file.name)
        except (NotImplementedError, ValueError, OSError) as exc:
            logger.warning('Thesis %s: storage existence check failed (%s)', thesis.id, exc)
            file_present = False

        if not file_present:
            logger.warning(
                'Thesis %s: file missing from storage (%s)',
                thesis.id, thesis.uploaded_file.name,
            )
            return _document_unavailable_response(thesis, 'file_missing_from_storage')

        filename = _preview_filename(thesis, preview=(disposition == 'inline'))

        try:
            pdf_bytes = _stamped_pdf_bytes(thesis, disposition)
        except EncryptedPdfError as exc:
            logger.warning('Thesis %s: source PDF is encrypted (%s)', thesis.id, exc)
            return _document_unavailable_response(thesis, 'source_encrypted')
        except WatermarkError as exc:
            logger.warning('Thesis %s: watermarking failed (%s)', thesis.id, exc)
            return _document_unavailable_response(thesis, 'watermark_failed')
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning('Thesis %s: source file could not be read (%s)', thesis.id, exc)
            return _document_unavailable_response(thesis, 'file_unreadable')
        except Exception as exc:
            # Only reachable via render_docx_to_pdf, which raises bare
            # exceptions for a corrupt or empty .docx.
            logger.warning('Thesis %s: DOCX-to-PDF conversion failed (%s)', thesis.id, exc)
            return _document_unavailable_response(thesis, 'docx_conversion_failed')

        # FileResponse's streaming is given up deliberately: stamping needs the
        # whole document in memory anyway, so there is nothing left to stream.
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response


# ---------------------------------------------------------------------------
# POST /theses/upload/  — upload PDF/DOCX, run extraction
# ---------------------------------------------------------------------------

class ThesisUploadView(APIView):
    """Upload a thesis. Students → pending_review; faculty/admin → approved."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
        # Step 1: validate the uploaded file (size, ext, magic bytes)
        uploaded_file = request.FILES.get('file')
        file_check = validate_thesis_file(uploaded_file)
        if not file_check.is_valid:
            return make_error_response(
                code=file_check.error_code or 'FILE_VALIDATION_FAILED',
                message=file_check.error_message or 'File validation failed.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Step 2: validate metadata payload
        # Authors and keywords arrive as JSON-encoded strings in multipart
        # form-data. Accept both a list (JSON body) and a JSON string.
        data = self._coerce_list_fields(request.data)
        serializer = ThesisUploadSerializer(data=data)
        if not serializer.is_valid():
            return make_error_response(
                code='VALIDATION_ERROR',
                message='Thesis metadata is invalid.',
                status=status.HTTP_400_BAD_REQUEST,
                details=dict(serializer.errors),
            )
        payload = serializer.validated_data

        # Step 3: hash file contents (duplicate detection)
        uploaded_file.seek(0)
        contents = uploaded_file.read()
        sha256 = hashlib.sha256(contents).hexdigest()
        uploaded_file.seek(0)

        if Thesis.objects.filter(sha256=sha256).exists():
            return make_error_response(
                code='DUPLICATE_FILE',
                message='This file has already been uploaded.',
                status=status.HTTP_409_CONFLICT,
            )

        # Step 4: determine workflow status from uploader's role
        role = getattr(request.user, 'role', None)
        if role in (Role.FACULTY, Role.ADMINISTRATOR):
            initial_status = ThesisStatus.APPROVED
            reviewed_by = request.user
            reviewed_at = timezone.now()
        else:
            initial_status = ThesisStatus.PENDING_REVIEW
            reviewed_by = None
            reviewed_at = None

        # Step 5: persist in a transaction
        try:
            with transaction.atomic():
                thesis = Thesis.objects.create(
                    title=payload['title'].strip(),
                    abstract=payload['abstract'].strip(),
                    authors=payload['authors'],
                    keywords=payload['keywords'],
                    program=payload['program'],
                    year=payload['year'],
                    adviser=payload.get('adviser', '').strip(),
                    uploaded_file=uploaded_file,
                    file_type=file_check.detected_type or FileType.PDF,
                    sha256=sha256,
                    status=initial_status,
                    uploaded_by=request.user,
                    reviewed_by=reviewed_by,
                    reviewed_at=reviewed_at,
                    embedding_status=EmbeddingStatus.NOT_STARTED,
                )
        except IntegrityError:
            return make_error_response(
                code='DUPLICATE_FILE',
                message='This file has already been uploaded.',
                status=status.HTTP_409_CONFLICT,
            )

        # Step 6: extract text (best-effort — never blocks upload success)
        try:
            extractor = ThesisTextExtractor()
            result = extractor.extract(thesis.uploaded_file.path)
            if result.success:
                thesis.extracted_text = result.text
                thesis.save(update_fields=['extracted_text', 'updated_at'])
            else:
                logger.warning(
                    'Thesis %s text extraction failed: %s',
                    thesis.id, result.error,
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Thesis %s text extraction crashed: %s', thesis.id, exc)

        # Step 7: generate SBERT embeddings (best-effort — does not block upload)
        #
        # The composite and title-only embeddings are generated in SEPARATE
        # try/except blocks on purpose. They serve different features
        # (semantic search vs review-time redundancy analysis) and one
        # failing must not skip the other. Neither blocks the 201.
        from .services.semantic_search import (
            generate_thesis_embedding,
            generate_title_embedding,
        )

        try:
            generate_thesis_embedding(thesis)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Thesis %s embedding generation failed: %s', thesis.id, exc)

        try:
            generate_title_embedding(thesis)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Thesis %s title embedding generation failed: %s', thesis.id, exc)

        # Step 8: respond with the detail shape
        return Response(
            ThesisDetailSerializer(thesis).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _parse_author_input(value: str) -> list[str]:
        """Split a legacy raw author field without corrupting inverted names.

        Semicolons are unambiguous author separators when names use an
        internal comma (``Lastname, Firstname``). For comma-only values we
        accept the natural-order form and split only before a capitalized
        next name (``Juan Dela Cruz, Maria Santos``).
        """
        import re

        value = (value or '').strip()
        if not value:
            return []
        delimiter = r';' if ';' in value else r',\s*(?=[A-Z])'
        return [' '.join(part.split()) for part in re.split(delimiter, value) if part.strip()]

    @staticmethod
    def _coerce_list_fields(raw):
        """Decode multipart list fields and normalize legacy raw input."""
        import json as _json

        # Handle QueryDict properly - get single values for scalar fields
        out = {}
        for key in raw.keys():
            # For scalar fields, get the single value (not a list)
            if key in ('title', 'abstract', 'program', 'year', 'adviser'):
                out[key] = raw.get(key)  # get() returns single value, not list
            else:
                # For other fields (authors, keywords), get as-is
                out[key] = raw.get(key)

        # Frontend multipart submissions use JSON arrays. For legacy raw
        # strings, author names need their own parser so `Lastname, Firstname`
        # remains a single contributor; keywords retain comma separation.
        for key in ('authors', 'keywords'):
            value = out.get(key)
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value.startswith('['):
                try:
                    out[key] = _json.loads(value)
                    continue
                except _json.JSONDecodeError:
                    pass
            out[key] = (
                ThesisUploadView._parse_author_input(value)
                if key == 'authors'
                else [part.strip() for part in value.split(',') if part.strip()]
            )

        # year arrives as string in multipart - convert to int
        if isinstance(out.get('year'), str) and out['year'].isdigit():
            out['year'] = int(out['year'])

        return out


# ---------------------------------------------------------------------------
# GET /theses/search/  — dedicated semantic search endpoint
# ---------------------------------------------------------------------------

class ThesisSearchView(APIView):
    """Semantic search over the visible thesis corpus.

    Returns ranked results with a ``similarity_score`` per item. Filters
    (``year``, ``program``, ``status``) narrow the candidate set before
    ranking. Pagination follows the same shape as ``ThesisListView``.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        q = (request.query_params.get('q') or '').strip()
        if not q:
            return make_error_response(
                code='MISSING_QUERY',
                message='Query parameter `q` is required.',
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(q) < 3:
            return make_error_response(
                code='QUERY_TOO_SHORT',
                message='Query must be at least 3 characters.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Similarity threshold: user-supplied float in [0.0, 1.0].
        # Defaults to the all-MiniLM-L6-v2 noise floor (0.10).
        try:
            min_score = float(request.query_params.get('min_score', 0.10))
            min_score = max(0.0, min(1.0, min_score))
        except (ValueError, TypeError):
            min_score = 0.10

        qs = _visible_queryset(request.user)

        year = request.query_params.get('year')
        if year:
            try:
                qs = qs.filter(year=int(year))
            except ValueError:
                return make_error_response(
                    code='INVALID_FILTER',
                    message='year must be an integer.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        program = request.query_params.get('program')
        if program:
            qs = qs.filter(program=program)

        status_filter = request.query_params.get('status')
        if status_filter:
            valid = {s.value for s in ThesisStatus}
            if status_filter not in valid:
                return make_error_response(
                    code='INVALID_FILTER',
                    message=f'status must be one of {sorted(valid)}.',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)

        from .services.semantic_search import rank_theses

        candidates = list(qs)
        scored = rank_theses(q, candidates)

        # Apply similarity threshold filter (user-controlled or default noise floor)
        scored = [s for s in scored if s.score >= min_score]

        # Read pagination params
        try:
            page_size = min(
                int(request.query_params.get('page_size', _ThesisPagination.page_size)),
                _ThesisPagination.max_page_size,
            )
        except ValueError:
            page_size = _ThesisPagination.page_size
        try:
            page_number = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page_number = 1

        total = len(scored)
        start = (page_number - 1) * page_size
        end = start + page_size
        page_slice = scored[start:end]

        results = []
        for s in page_slice:
            s.thesis.similarity_score = round(s.score, 4)
            results.append(s.thesis)

        data = ThesisListItemSerializer(results, many=True).data

        from django.utils.http import urlencode
        base_url = request.build_absolute_uri(request.path)
        qparams = dict(request.query_params)

        def _link(page_num):
            qparams_copy = {k: v for k, v in qparams.items() if k != 'page'}
            qparams_copy['page'] = str(page_num)
            return f'{base_url}?{urlencode(qparams_copy, doseq=True)}'

        next_link = _link(page_number + 1) if end < total else None
        prev_link = _link(page_number - 1) if page_number > 1 else None

        return Response({
            'count': total,
            'next': next_link,
            'previous': prev_link,
            'query': q,
            'results': data,
        })


# ---------------------------------------------------------------------------
# POST /theses/validate-title/  — Phase 2B title similarity validation
# ---------------------------------------------------------------------------

class ThesisValidateTitleView(APIView):
    """Validate a proposed thesis title against the existing corpus.

    Reuses the SBERT model loaded by Phase 2A and the cosine-similarity
    primitives. Returns a classification (HIGHLY_SIMILAR / MODERATELY_SIMILAR
    / LOW_SIMILARITY), a recommendation message per the Chapter 1–3
    thresholds, and the top-K most similar approved theses.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    MIN_LEN = 5
    MAX_LEN = 500

    def post(self, request, *args, **kwargs):
        title = (request.data.get('title') or '').strip()
        if len(title) < self.MIN_LEN:
            return make_error_response(
                code='TITLE_TOO_SHORT',
                message=f'Title must be at least {self.MIN_LEN} characters.',
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(title) > self.MAX_LEN:
            return make_error_response(
                code='TITLE_TOO_LONG',
                message=f'Title must not exceed {self.MAX_LEN} characters.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate against APPROVED theses only — pending/rejected records
        # should not influence duplicate detection.
        approved = (
            Thesis.objects
            .filter(status=ThesisStatus.APPROVED)
            .only('id', 'title', 'program', 'year', 'authors', 'status')
        )

        from .services.title_similarity import classify_title

        result = classify_title(title, approved, top_k=5)

        return Response({
            'query': result.query,
            'classification': result.classification,
            'similarity_score': round(result.similarity_score, 4),
            'recommendation': result.recommendation,
            'matches': [
                {
                    'id': str(s.thesis.id),
                    'title': s.thesis.title,
                    'authors': s.thesis.authors,
                    'program': s.thesis.program,
                    'year': s.thesis.year,
                    'similarity': round(s.score, 4),
                }
                for s in result.matches
            ],
        })


# ---------------------------------------------------------------------------
# GET /theses/topic-trends/  — Phase 3 TF-IDF + K-Means topic analysis
# ---------------------------------------------------------------------------

class ThesisTopicTrendsView(APIView):
    """Topic trend analysis over the approved thesis corpus.

    Pipeline (Chapter 1–3):
      1. Materialise approved theses.
      2. TF-IDF vectorise (title + abstract + keywords). The stored
         extracted_text is excluded — it is dominated by cover-page and
         approval-sheet boilerplate that every manuscript shares.
      3. K-Means cluster the vectors (auto-k in [5, 8], targeting ~6
         theses per cluster).
      4. Surface top-K TF-IDF keywords per cluster.
      5. Map cluster size → trend (SATURATED / EMERGING / UNDEREXPLORED).
      6. Apply heuristic naming so each cluster gets a human-readable label.

    Read-only — never mutates Thesis rows.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Optional override of k via ?k=N (clamped server-side in service)
        k = None
        k_param = request.query_params.get('k')
        if k_param:
            try:
                k = int(k_param)
            except ValueError:
                return make_error_response(
                    code='INVALID_K',
                    message='k must be an integer.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from .services.topic_analysis import analyze_topics, get_topic_trends_queryset, to_dict

        try:
            result = analyze_topics(get_topic_trends_queryset(), k=k)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning('Topic analysis failed: %s', exc)
            return make_error_response(
                code='TOPIC_ANALYSIS_FAILED',
                message='Topic analysis could not complete. Please try again.',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(to_dict(result))


# ---------------------------------------------------------------------------
# POST /theses/extract-title/  — title detection from uploaded proposal document
# ---------------------------------------------------------------------------

class ThesisExtractTitleView(APIView):
    """Extract the likely thesis title from an uploaded PDF or DOCX proposal.

    Uses the existing ThesisTextExtractor pipeline (pypdf → Tesseract OCR
    fallback for PDFs; python-docx for DOCX). The extracted text is then
    analysed by a lightweight heuristic to detect the most likely thesis
    title so the user can validate it with the existing
    ``/theses/validate-title/`` endpoint.

    This endpoint does NOT persist anything to the database. It is a
    stateless text-extraction-and-title-detection helper.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024   # 25 MB
    ALLOWED_EXTS = ('pdf', 'docx')

    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return make_error_response(
                code='MISSING_FILE',
                message='No file was uploaded.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = (uploaded.name or '').lower()
        ext = name.rsplit('.', 1)[-1] if '.' in name else ''
        if ext not in self.ALLOWED_EXTS:
            return make_error_response(
                code='FILE_TYPE_NOT_ALLOWED',
                message='Only PDF and DOCX files are accepted for title extraction.',
                status=status.HTTP_400_BAD_REQUEST,
            )
        if uploaded.size > self.MAX_FILE_SIZE_BYTES:
            return make_error_response(
                code='FILE_TOO_LARGE',
                message='File size must not exceed 25 MB.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Write to a temporary file so ThesisTextExtractor can read it
        import tempfile, os as _os
        suffix = f'.{ext}'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from .services.text_extractor import (
                FRONT_MATTER_PAGES,
                ThesisTextExtractor,
            )
            extractor = ThesisTextExtractor()
            # Read front matter only. A title lives on page one, so parsing all
            # 93 pages of a thesis to find it is wasted work — and on the OCR
            # path it was wasted memory too (up to 50 pages rasterised at
            # 200 dpi). The response contract is unchanged.
            result = extractor.extract(tmp_path, max_pages=FRONT_MATTER_PAGES)
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass

        if not result.success or not result.text.strip():
            return Response({
                'detected_title': '',
                'confidence': 'low',
                'method': result.method,
                'message': (
                    'Could not extract readable text from the document. '
                    'If this is a scanned image, ensure Tesseract OCR is installed. '
                    'Please type the title manually.'
                ),
            })

        detected, confidence = self._detect_title(result.text)

        if not detected:
            return Response({
                'detected_title': '',
                'confidence': 'low',
                'method': result.method,
                'message': (
                    'Could not confidently detect a title. '
                    'Please type or edit the title manually.'
                ),
            })

        # Per-confidence messages — distinct copy for each state
        if confidence == 'high':
            message = 'Title detected successfully. The thesis title was automatically extracted.'
        elif confidence == 'medium':
            message = (
                'Possible title detected. '
                'Please review and edit the detected title if needed.'
            )
        else:  # low
            message = (
                'Low confidence title detection. '
                'This file may not contain a title page — the detected text may be a '
                'chapter heading or section title. Please review and edit manually.'
            )

        return Response({
            'detected_title': detected,
            'confidence': confidence,
            'method': result.method,
            'message': message,
        })

    def _detect_title(self, text: str) -> tuple[str, str]:
        """Delegate to the shared metadata-extraction service.

        All title-detection logic now lives in
        ``theses/services/metadata_extraction.py`` so it can be unit-tested
        and reused by the metadata endpoint. This thin shim is kept so any
        caller (including existing tests) that reaches for the view method
        keeps working, and so this view's response contract is unchanged.
        """
        from .services.metadata_extraction import detect_title
        return detect_title(text)


# ---------------------------------------------------------------------------
# POST /theses/extract-metadata/  — all six upload fields from the document
# ---------------------------------------------------------------------------

class ThesisExtractMetadataView(APIView):
    """Extract title, abstract, authors, keywords, program and year at once.

    Exists so the upload modal can pre-fill itself from the attached document
    instead of asking the user to retype metadata that is already printed on
    the title page.

    Deliberate duplication: ``ThesisUploadView.post`` Step 6 re-extracts the
    document server-side on submit and stores the result in
    ``Thesis.extracted_text``. That is kept as the authoritative extraction.
    This endpoint is a *convenience* pass whose output the user can edit
    freely, so the two are not expected to agree and neither depends on the
    other. Collapsing them would either make the upload trust unvalidated
    client input or force the user to wait for a full-document parse twice.

    Nothing is persisted. Same auth, same 25 MB cap and same accepted
    extensions as ``/theses/extract-title/``.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    MAX_FILE_SIZE_BYTES = ThesisExtractTitleView.MAX_FILE_SIZE_BYTES
    ALLOWED_EXTS = ThesisExtractTitleView.ALLOWED_EXTS

    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return make_error_response(
                code='MISSING_FILE',
                message='No file was uploaded.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = (uploaded.name or '').lower()
        ext = name.rsplit('.', 1)[-1] if '.' in name else ''
        if ext not in self.ALLOWED_EXTS:
            return make_error_response(
                code='FILE_TYPE_NOT_ALLOWED',
                message='Only PDF and DOCX files are accepted for metadata extraction.',
                status=status.HTTP_400_BAD_REQUEST,
            )
        if uploaded.size > self.MAX_FILE_SIZE_BYTES:
            return make_error_response(
                code='FILE_TOO_LARGE',
                message='File size must not exceed 25 MB.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        import os as _os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from .services.text_extractor import METADATA_PAGES, ThesisTextExtractor
            extractor = ThesisTextExtractor()
            result = extractor.extract(tmp_path, max_pages=METADATA_PAGES)
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass

        from .services.metadata_extraction import METADATA_FIELDS, extract_metadata

        if not result.success or not result.text.strip():
            return Response({
                'fields': {
                    field: {
                        'value': [] if field in ('authors', 'keywords')
                        else (None if field == 'year' else ''),
                        'confidence': 'low',
                    }
                    for field in METADATA_FIELDS
                },
                'filled_fields': [],
                'method': result.method,
                'message': (
                    'Could not extract readable text from the document. '
                    'If this is a scanned image, ensure Tesseract OCR is installed. '
                    'Please fill in the fields manually.'
                ),
            })

        fields = extract_metadata(result.text)

        # Which fields actually produced something — lets the frontend show a
        # precise note without re-implementing emptiness rules per type.
        filled = [
            field for field in METADATA_FIELDS
            if fields[field]['value'] not in ('', None, [])
        ]

        if not filled:
            message = (
                'No metadata could be detected in this document. '
                'Please fill in the fields manually.'
            )
        elif len(filled) == len(METADATA_FIELDS):
            message = 'All fields were detected. Please review them before uploading.'
        else:
            missing = [f for f in METADATA_FIELDS if f not in filled]
            message = (
                f'Detected {len(filled)} of {len(METADATA_FIELDS)} fields. '
                f'Please fill in and review the rest ({", ".join(missing)}).'
            )

        return Response({
            'fields': fields,
            'filled_fields': filled,
            'method': result.method,
            'message': message,
        })


# ---------------------------------------------------------------------------
# GET /theses/analytics/  — Phase 3B repository intelligence dashboard
# ---------------------------------------------------------------------------

class ThesisAnalyticsView(APIView):
    """Repository intelligence metrics for the analytics dashboard.

    Returns pure ORM aggregations over the Thesis table — no ML,
    no AI inference. Designed to complement (not duplicate) the
    TF-IDF + K-Means topic trend analysis endpoint.

    Role visibility:
    - All authenticated users: thesis counts + distributions
    - Faculty / Administrator: pending_review count
    """

    permission_classes = [IsAuthenticated]

    # Number of recent days for "recent uploads" card
    RECENT_DAYS = 30
    # Top-N keywords to surface
    TOP_KEYWORDS = 10

    def get(self, request, *args, **kwargs):
        from django.db.models import Count
        from django.utils import timezone as tz
        from datetime import timedelta
        from collections import Counter

        approved = Thesis.objects.filter(status=ThesisStatus.APPROVED)
        all_theses = Thesis.objects.all()

        # ── 1. Repository overview ──────────────────────────────────
        total_theses = all_theses.count()
        approved_count = approved.count()

        # Semantic ready = approved theses with a stored embedding vector
        semantic_ready = approved.exclude(embedding_vector__isnull=True).count()

        # Recent uploads (all statuses, last RECENT_DAYS days)
        since = tz.now() - timedelta(days=self.RECENT_DAYS)
        recent_uploads = all_theses.filter(created_at__gte=since).count()

        # Most active program by approved thesis count
        most_active_program = ''
        prog_counts = (
            approved
            .values('program')
            .annotate(n=Count('id'))
            .order_by('-n')
        )
        if prog_counts:
            # Shorten the program name for the card (e.g. "BS IT" from long label)
            raw = prog_counts[0]['program'] or ''
            most_active_program = raw

        # ── 2. Program distribution (approved) ─────────────────────
        program_distribution = [
            {'program': row['program'], 'count': row['n']}
            for row in prog_counts
        ]

        # ── 3. Thesis growth by year (approved, up to last 10 years) ─
        current_year = tz.now().year
        growth_qs = (
            approved
            .filter(year__gte=current_year - 9)
            .values('year')
            .annotate(count=Count('id'))
            .order_by('year')
        )
        thesis_growth = [{'year': r['year'], 'count': r['count']} for r in growth_qs]

        # ── 4. Top keywords ─────────────────────────────────────────
        # keywords is a JSONB array; we flatten it in Python (corpus is small)
        keyword_counter: Counter = Counter()
        for kw_list in approved.values_list('keywords', flat=True):
            if isinstance(kw_list, list):
                for kw in kw_list:
                    if kw and isinstance(kw, str):
                        keyword_counter[kw.strip().lower()] += 1
        top_keywords = [
            {'keyword': kw, 'count': cnt}
            for kw, cnt in keyword_counter.most_common(self.TOP_KEYWORDS)
        ]

        # ── 5. Topic saturation summary — reuse trend analysis ───────
        # Call the existing analyze_topics service to get cluster stats
        # without hitting the network; silently degrade if it fails.
        topic_summary = {'emerging_count': 0, 'saturated_count': 0, 'underexplored_count': 0}
        try:
            from .services.topic_analysis import analyze_topics, get_topic_trends_queryset
            # Use the shared queryset helper (same scope/fields/order as the
            # /topic-trends/ endpoint) so both pages cluster identical input
            # and never drift apart on SATURATED/EMERGING/UNDEREXPLORED counts.
            trend_result = analyze_topics(get_topic_trends_queryset())
            topic_summary = {
                'emerging_count': trend_result.emerging_count,
                'saturated_count': trend_result.saturated_count,
                'underexplored_count': trend_result.underexplored_count,
            }
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning('Analytics: topic summary failed: %s', exc)

        # ── 6. Role-gated extras ─────────────────────────────────────
        role = getattr(request.user, 'role', None)
        pending_review_count = None
        if role in ('faculty', 'administrator'):
            pending_review_count = Thesis.objects.filter(
                status=ThesisStatus.PENDING_REVIEW
            ).count()

        return Response({
            # Overview
            'total_theses': total_theses,
            'approved_theses': approved_count,
            'semantic_ready': semantic_ready,
            'recent_uploads_count': recent_uploads,
            'recent_uploads_days': self.RECENT_DAYS,
            'most_active_program': most_active_program,

            # Distributions
            'program_distribution': program_distribution,
            'thesis_growth': thesis_growth,
            'top_keywords': top_keywords,

            # Topic summary (from existing trend analysis)
            'topic_summary': topic_summary,

            # Role-gated
            'pending_review_count': pending_review_count,
        })


# ---------------------------------------------------------------------------
# GET /theses/public-stats/  — unauthenticated public summary statistics
# ---------------------------------------------------------------------------

class ThesisPublicStatsView(APIView):
    """Return a minimal public summary for the LandingPage stats row.

    This endpoint requires NO authentication by design.

    What it exposes:
        indexed_theses_count — number of approved theses (integer)

    What it does NOT expose:
        thesis titles, abstracts, authors, keywords, documents, file paths,
        user accounts, pending/rejected records, admin-only analytics, or
        any PII.

    The thesis count is treated as public marketing information — it
    signals the size of the repository without revealing any private content.
    """

    permission_classes = []   # No authentication required
    authentication_classes = []  # Skip auth middleware entirely for speed

    def get(self, request, *args, **kwargs):
        count = Thesis.objects.filter(status=ThesisStatus.APPROVED).count()
        return Response({'indexed_theses_count': count})
