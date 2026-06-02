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
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404
from django.utils import timezone
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
from .services.text_extractor import ThesisTextExtractor
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
    """List theses with filters: ``q``, ``year``, ``program``, ``status``.

    When ``q`` is provided, the list is reranked by SBERT cosine similarity
    against the candidate set (filters are applied first to narrow the set,
    then semantic ranking sorts the survivors). When ``q`` is empty the
    standard chronological ordering is used.
    """

    permission_classes = [IsAuthenticated]

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
        scored = [s for s in scored if s.score >= min_score]

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
# GET /theses/{id}/download/ — stream the file
# ---------------------------------------------------------------------------

class ThesisDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id, *args, **kwargs):
        thesis = _resolve_thesis(id, request.user)
        if not thesis.uploaded_file:
            raise NotFound(detail='File no longer available.')
        try:
            f = thesis.uploaded_file.open('rb')
        except FileNotFoundError:
            raise NotFound(detail='File no longer available.')
        filename = Path(thesis.uploaded_file.name).name
        return FileResponse(f, as_attachment=True, filename=filename)


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

        # Step 7: generate SBERT embedding (best-effort — does not block upload)
        try:
            from .services.semantic_search import generate_thesis_embedding
            generate_thesis_embedding(thesis)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Thesis %s embedding generation failed: %s', thesis.id, exc)

        # Step 8: respond with the detail shape
        return Response(
            ThesisDetailSerializer(thesis).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _coerce_list_fields(raw):
        """Multipart fields arrive as strings — decode JSON for list-shaped fields."""
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
        
        # Now coerce authors and keywords from JSON strings to lists
        for key in ('authors', 'keywords'):
            value = out.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value.startswith('['):
                    try:
                        out[key] = _json.loads(value)
                    except _json.JSONDecodeError:
                        # Comma-separated fallback: "Foo, Bar, Baz"
                        out[key] = [v.strip() for v in value.split(',') if v.strip()]
                else:
                    out[key] = [v.strip() for v in value.split(',') if v.strip()]
        
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
      2. TF-IDF vectorise (title + abstract + extracted_text + keywords).
      3. K-Means cluster the vectors (auto-k in [5, 8]).
      4. Surface top-K TF-IDF keywords per cluster.
      5. Map cluster size → trend (SATURATED / EMERGING / UNDEREXPLORED).
      6. Apply heuristic naming so each cluster gets a human-readable label.

    Read-only — never mutates Thesis rows.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        approved = (
            Thesis.objects
            .filter(status=ThesisStatus.APPROVED)
            .only(
                'id', 'title', 'abstract', 'extracted_text',
                'keywords', 'program', 'year', 'status',
            )
            .order_by('created_at')
        )

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

        from .services.topic_analysis import analyze_topics, to_dict

        try:
            result = analyze_topics(approved, k=k)
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

    # Noise words that appear as section headings — never the actual title.
    _SECTION_NOISE = frozenset({
        'abstract', 'introduction', 'table of contents', 'chapter',
        'acknowledgements', 'acknowledgment', 'dedication', 'preface',
        'references', 'bibliography', 'appendix', 'index',
        'list of figures', 'list of tables', 'methodology',
        'review of related literature', 'related literature',
        'background of the study', 'statement of the problem',
        'scope and limitations', 'significance of the study',
        'definition of terms', 'theoretical framework',
        'conceptual framework', 'college of computing studies',
        'pampanga state university', 'psu', 'ccs', 'dhvsu',
        'thesis', 'dissertation', 'capstone project',
        'submitted', 'presented', 'partial fulfillment', 'degree',
        'bachelor', 'master', 'doctor',
    })

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
            from .services.text_extractor import ThesisTextExtractor
            extractor = ThesisTextExtractor()
            result = extractor.extract(tmp_path)
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
        """Heuristic title detection from raw extracted text.

        Returns (detected_title, confidence) where confidence is one of
        'high', 'medium', 'low'.

        Strategy
        --------
        1. Scan the first 40 lines, score each candidate line, pick best.
        2. Apply a document-level chapter-heading penalty: if the first
           meaningful lines of the document are section/chapter headings,
           the document likely has no title page → cap confidence at 'low'.
        3. A line scores well when it:
           - is not a noise section heading
           - is 3–22 words
           - appears near the top of the document (first 30 lines)
           - starts with uppercase or is ALL-CAPS
           - contains thesis-domain keywords
        """
        import re

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        candidates = lines[:40]
        noise = self._SECTION_NOISE

        # ── Document-level chapter-heading detection ─────────────────
        # Check if the first 1–6 non-trivial lines look like chapter headings.
        # If so, the document almost certainly has no title page; cap at 'low'.
        _CHAPTER_PATTERNS = re.compile(
            r'^(chapter\s+[ivxlcdm\d]+|the problem and its background|'
            r'review of related literature|related literature|introduction|'
            r'methodology|results and discussion|conclusion|recommendations|'
            r'references|bibliography|appendix|abstract)[\s\.\:\-]*$',
            re.IGNORECASE,
        )
        _chapter_heading_count = 0
        for line in lines[:6]:
            if _CHAPTER_PATTERNS.match(line.strip()):
                _chapter_heading_count += 1
        document_is_chapter_only = _chapter_heading_count >= 1

        # ── Per-line scoring ──────────────────────────────────────────
        best: str | None = None
        best_score = -1
        best_confidence = 'low'

        for idx, line in enumerate(candidates):
            line_lower = line.lower().strip(' .,;:!?-')

            # Skip noise headings
            if any(line_lower == n or line_lower.startswith(n) for n in noise):
                continue
            # Skip chapter pattern even if it passed noise filter
            if _CHAPTER_PATTERNS.match(line_lower):
                continue

            words = line.split()
            n_words = len(words)
            if n_words < 3 or n_words > 22:
                continue
            # Skip short lines that look like author names
            if n_words <= 3 and not any(c in line for c in (':', '-', 'A', 'An', 'The')):
                if all(w[0].isupper() for w in words if w):
                    continue
            if re.fullmatch(r'[\d/\-,\s]+', line):
                continue
            alpha_ratio = sum(1 for c in line if c.isalpha()) / max(len(line), 1)
            if alpha_ratio < 0.6:
                continue

            score = 0
            if idx < 5:
                score += 3
            elif idx < 10:
                score += 2
            elif idx < 20:
                score += 1

            if line.isupper() and n_words >= 4:
                score += 3
            elif line.istitle():
                score += 2
            elif line[0].isupper():
                score += 1

            title_kws = {'system', 'using', 'based', 'approach', 'study',
                         'analysis', 'design', 'development', 'implementation',
                         'monitoring', 'detection', 'recognition', 'learning',
                         'classification', 'prediction', 'platform', 'application',
                         'framework', 'model', 'management', 'technology'}
            if any(kw in line.lower() for kw in title_kws):
                score += 2

            if 5 <= n_words <= 15:
                score += 1

            if score > best_score:
                best_score = score
                best = line
                if score >= 7:
                    best_confidence = 'high'
                elif score >= 4:
                    best_confidence = 'medium'
                else:
                    best_confidence = 'low'

        # Normalise capitalisation
        if best and best.isupper():
            best = best.title()

        # ── Apply document-level chapter penalty ──────────────────────
        # If the document appears to start with chapter headings (no title
        # page), cap the confidence at 'low' regardless of per-line score.
        if document_is_chapter_only and best_confidence in ('high', 'medium'):
            best_confidence = 'low'

        return best or '', best_confidence


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
            from .services.topic_analysis import analyze_topics
            trend_result = analyze_topics(approved.only(
                'title', 'abstract', 'extracted_text', 'keywords', 'status',
            ))
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
