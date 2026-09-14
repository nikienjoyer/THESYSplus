"""Tests for the thesis review surface in the Django admin.

Three things are under test:

1. Bulk mutation is gone. No status actions, and no ``delete_selected``.
2. Every real status transition stamps provenance and writes exactly one
   audit row. A no-op save writes neither.
3. The redundancy signal is advisory: it renders, it escapes user-supplied
   titles, and it never takes the page down with it.
"""

from __future__ import annotations

import math

import pytest
from django.contrib import admin as django_admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.base import ContentFile
from django.test import RequestFactory
from django.urls import reverse

from accounts.models import Role, User
from audit.models import AuditLog
from theses.admin import ThesisAdmin, _format_percent
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus
from theses.services.redundancy import EMBEDDING_DIM, invalidate_cache

REVIEW_EVENT_PREFIX = 'thesis.review.'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def basis(index: int = 0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[index] = 1.0
    return vector


def at_cosine(c: float, *, axis: int = 1) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[0] = c
    vector[axis] = math.sqrt(max(0.0, 1.0 - c * c))
    return vector


def review_rows():
    return AuditLog.objects.filter(event_type__startswith=REVIEW_EVENT_PREFIX)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def isolate_media(settings, tmp_path):
    """Keep test uploads out of the real MEDIA_ROOT.

    Not autouse: a setting override fires ``setting_changed`` receivers that
    reach for the database connection.
    """
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email='reviewer.admin@pampangastateu.edu.ph',
        first_name='Review',
        last_name='Admin',
        password='Test12345!Test',
    )


@pytest.fixture
def other_admin(db):
    return User.objects.create_superuser(
        email='second.admin@pampangastateu.edu.ph',
        first_name='Second',
        last_name='Admin',
        password='Test12345!Test',
    )


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email='uploader.student@pampangastateu.edu.ph',
        first_name='Up',
        last_name='Loader',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, student, isolate_media):
    counter = {'n': 0}

    def _make(
        title: str = 'A Thesis',
        *,
        status: str = ThesisStatus.PENDING_REVIEW,
        title_embedding=None,
        embedding_status: str = EmbeddingStatus.READY,
        reviewed_by=None,
        reviewed_at=None,
        rejection_reason: str = '',
    ) -> Thesis:
        counter['n'] += 1
        n = counter['n']
        thesis = Thesis(
            title=title,
            abstract=f'Abstract for {title}',
            authors=['Tester, T.'],
            keywords=['test'],
            program=Program.BSIT.value,
            year=2024,
            file_type=FileType.PDF,
            sha256=(f'{n:x}' + 'c' * 64)[:64],
            status=status,
            uploaded_by=student,
            title_embedding=title_embedding,
            embedding_status=embedding_status,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            rejection_reason=rejection_reason,
        )
        thesis.uploaded_file.save(
            f'admin_review_{n}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        thesis.save()
        return thesis

    return _make


@pytest.fixture
def model_admin():
    return ThesisAdmin(Thesis, django_admin.site)


@pytest.fixture
def rf_request(admin_user):
    """A POST request with the messages framework wired up.

    ``message_user`` needs a storage backend; RequestFactory does not run
    middleware, so it is attached explicitly.
    """
    def _make(user=None):
        request = RequestFactory().post('/admin/theses/thesis/1/change/')
        request.user = user or admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    return _make


def save_via_admin(model_admin, request, thesis, *, change=True):
    """Invoke the real save_model path."""
    model_admin.save_model(request, thesis, form=None, change=change)


# ---------------------------------------------------------------------------
# 1. No bulk mutation
# ---------------------------------------------------------------------------

class TestBulkActionsRemoved:
    def test_actions_is_none_not_empty_list(self, model_admin):
        """`actions = []` would let Django re-add delete_selected."""
        assert ThesisAdmin.actions is None

    def test_get_actions_is_empty_for_superuser(self, model_admin, rf_request):
        assert model_admin.get_actions(rf_request()) == {}

    def test_delete_selected_is_absent(self, model_admin, rf_request):
        assert 'delete_selected' not in model_admin.get_actions(rf_request())

    @pytest.mark.parametrize('name', [
        'approve_theses', 'reject_theses', 'mark_pending_review',
    ])
    def test_former_action_attributes_are_gone(self, name):
        assert not hasattr(ThesisAdmin, name)

    def test_changelist_renders_no_action_controls(self, client, admin_user, make_thesis):
        make_thesis('Something Pending')
        client.force_login(admin_user)
        response = client.get(reverse('admin:theses_thesis_changelist'))
        body = response.content.decode()

        assert response.status_code == 200
        assert 'name="action"' not in body
        assert 'delete_selected' not in body


# ---------------------------------------------------------------------------
# 2. Transition matrix — provenance and audit
# ---------------------------------------------------------------------------

class TestTransitionMatrix:
    @pytest.mark.parametrize('previous,new,event', [
        (ThesisStatus.PENDING_REVIEW, ThesisStatus.APPROVED, 'thesis.review.approved'),
        (ThesisStatus.PENDING_REVIEW, ThesisStatus.REJECTED, 'thesis.review.rejected'),
        (ThesisStatus.APPROVED, ThesisStatus.REJECTED, 'thesis.review.rejected'),
        (ThesisStatus.REJECTED, ThesisStatus.APPROVED, 'thesis.review.approved'),
    ])
    def test_terminal_transition_stamps_and_audits(
        self, model_admin, rf_request, make_thesis, admin_user, previous, new, event,
    ):
        thesis = make_thesis('Under Review', status=previous)
        request = rf_request()

        thesis.status = new
        save_via_admin(model_admin, request, thesis)

        thesis.refresh_from_db()
        assert thesis.status == new
        assert thesis.reviewed_by == admin_user
        assert thesis.reviewed_at is not None

        rows = review_rows()
        assert rows.count() == 1
        row = rows.first()
        assert row.event_type == event
        assert row.actor_user == admin_user
        assert row.target_user == thesis.uploaded_by
        assert row.success is True
        assert row.metadata['previous_status'] == previous
        assert row.metadata['new_status'] == new
        assert row.metadata['thesis_id'] == str(thesis.id)

    @pytest.mark.parametrize('previous', [
        ThesisStatus.APPROVED, ThesisStatus.REJECTED,
    ])
    def test_reopening_clears_provenance(
        self, model_admin, rf_request, make_thesis, admin_user, previous,
    ):
        from django.utils import timezone

        thesis = make_thesis(
            'Decided', status=previous,
            reviewed_by=admin_user, reviewed_at=timezone.now(),
        )
        request = rf_request()

        thesis.status = ThesisStatus.PENDING_REVIEW
        save_via_admin(model_admin, request, thesis)

        thesis.refresh_from_db()
        assert thesis.reviewed_by is None
        assert thesis.reviewed_at is None

        rows = review_rows()
        assert rows.count() == 1
        assert rows.first().event_type == 'thesis.review.reopened'

    @pytest.mark.parametrize('status', [
        ThesisStatus.PENDING_REVIEW, ThesisStatus.APPROVED, ThesisStatus.REJECTED,
    ])
    def test_no_op_save_writes_no_audit_row_and_leaves_provenance(
        self, model_admin, rf_request, make_thesis, other_admin, status,
    ):
        from django.utils import timezone

        stamped_at = timezone.now()
        thesis = make_thesis(
            'Unchanged', status=status,
            reviewed_by=other_admin, reviewed_at=stamped_at,
        )
        request = rf_request()

        # Edit an unrelated field; status stays put.
        thesis.title = 'Unchanged but retitled'
        save_via_admin(model_admin, request, thesis)

        thesis.refresh_from_db()
        assert thesis.title == 'Unchanged but retitled'
        assert thesis.reviewed_by == other_admin
        assert thesis.reviewed_at == stamped_at
        assert review_rows().count() == 0

    def test_rejection_reason_edit_at_same_status_is_a_no_op(
        self, model_admin, rf_request, make_thesis, other_admin,
    ):
        from django.utils import timezone

        stamped_at = timezone.now()
        thesis = make_thesis(
            'Rejected', status=ThesisStatus.REJECTED,
            reviewed_by=other_admin, reviewed_at=stamped_at,
            rejection_reason='Original reason',
        )
        request = rf_request()

        thesis.rejection_reason = 'Revised reason'
        save_via_admin(model_admin, request, thesis)

        thesis.refresh_from_db()
        assert thesis.rejection_reason == 'Revised reason'
        assert thesis.reviewed_by == other_admin
        assert thesis.reviewed_at == stamped_at
        assert review_rows().count() == 0

    def test_rejection_reason_is_recorded_on_a_rejection(
        self, model_admin, rf_request, make_thesis,
    ):
        thesis = make_thesis('To Reject', status=ThesisStatus.PENDING_REVIEW)
        thesis.status = ThesisStatus.REJECTED
        thesis.rejection_reason = 'Scope overlaps an approved study.'
        save_via_admin(model_admin, rf_request(), thesis)

        row = review_rows().first()
        assert row.metadata['rejection_reason'] == 'Scope overlaps an approved study.'

    def test_approval_metadata_omits_rejection_reason(
        self, model_admin, rf_request, make_thesis,
    ):
        thesis = make_thesis('To Approve')
        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(), thesis)

        assert 'rejection_reason' not in review_rows().first().metadata

    def test_provenance_is_overwritten_by_the_later_reviewer(
        self, model_admin, rf_request, make_thesis, admin_user, other_admin,
    ):
        """Deliberate change: the old code kept whoever got there first."""
        from django.utils import timezone

        thesis = make_thesis(
            'Twice Reviewed', status=ThesisStatus.APPROVED,
            reviewed_by=other_admin, reviewed_at=timezone.now(),
        )

        thesis.status = ThesisStatus.REJECTED
        save_via_admin(model_admin, rf_request(admin_user), thesis)

        thesis.refresh_from_db()
        assert thesis.reviewed_by == admin_user

    def test_sequential_reviewers_each_get_their_own_previous_status(
        self, model_admin, rf_request, make_thesis, admin_user, other_admin,
    ):
        thesis = make_thesis('Contested')

        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(admin_user), thesis)

        thesis.refresh_from_db()
        thesis.status = ThesisStatus.REJECTED
        save_via_admin(model_admin, rf_request(other_admin), thesis)

        rows = list(review_rows().order_by('created_at'))
        assert len(rows) == 2
        assert rows[0].metadata['previous_status'] == ThesisStatus.PENDING_REVIEW
        assert rows[0].metadata['new_status'] == ThesisStatus.APPROVED
        assert rows[1].metadata['previous_status'] == ThesisStatus.APPROVED
        assert rows[1].metadata['new_status'] == ThesisStatus.REJECTED

    def test_audit_row_count_equals_transition_count(
        self, model_admin, rf_request, make_thesis,
    ):
        thesis = make_thesis('Churn')
        request = rf_request()

        sequence = [
            ThesisStatus.APPROVED,       # transition
            ThesisStatus.APPROVED,       # no-op
            ThesisStatus.PENDING_REVIEW,  # transition
            ThesisStatus.PENDING_REVIEW,  # no-op
            ThesisStatus.REJECTED,       # transition
        ]
        for status in sequence:
            thesis.refresh_from_db()
            thesis.status = status
            save_via_admin(model_admin, request, thesis)

        assert review_rows().count() == 3

    def test_event_types_fit_the_column(self):
        from theses.admin import _EVENT_FOR_STATUS
        max_length = AuditLog._meta.get_field('event_type').max_length
        for event in _EVENT_FOR_STATUS.values():
            assert len(event) <= max_length


class TestPreSaveStatusRead:
    def test_database_wins_over_a_stale_form(
        self, model_admin, rf_request, make_thesis,
    ):
        """A concurrent reviewer makes form.initial unreliable in both directions."""
        thesis = make_thesis('Raced', status=ThesisStatus.PENDING_REVIEW)

        # Another reviewer approves it behind our back.
        Thesis.objects.filter(pk=thesis.pk).update(status=ThesisStatus.APPROVED)

        # Our in-memory copy still says pending; we submit "approved".
        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(), thesis)

        # Stored status was already approved, so this is a no-op, not a
        # transition — even though our stale copy would have suggested one.
        assert review_rows().count() == 0

    def test_create_is_a_transition_from_null(
        self, model_admin, rf_request, make_thesis, admin_user,
    ):
        thesis = make_thesis('Freshly Made', status=ThesisStatus.APPROVED)
        # Simulate the add form: change=False.
        save_via_admin(model_admin, rf_request(), thesis, change=False)

        rows = review_rows()
        assert rows.count() == 1
        row = rows.first()
        assert row.metadata['previous_status'] is None
        assert row.metadata['created'] is True

        thesis.refresh_from_db()
        assert thesis.reviewed_by == admin_user


# ---------------------------------------------------------------------------
# Embedding repair on approval
# ---------------------------------------------------------------------------

class TestEmbeddingRetry:
    def test_ready_embedding_is_left_alone(
        self, model_admin, rf_request, make_thesis, monkeypatch,
    ):
        calls = []
        monkeypatch.setattr(
            'theses.services.semantic_search.generate_thesis_embedding',
            lambda *a, **k: calls.append('composite'),
        )

        thesis = make_thesis('Already Embedded', embedding_status=EmbeddingStatus.READY)
        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(), thesis)

        assert calls == []

    @pytest.mark.parametrize('embedding_status', [
        EmbeddingStatus.NOT_STARTED,
        EmbeddingStatus.PROCESSING,
        EmbeddingStatus.FAILED,
    ])
    def test_retry_runs_for_every_non_ready_state(
        self, model_admin, rf_request, make_thesis, monkeypatch, embedding_status,
    ):
        calls = []
        monkeypatch.setattr(
            'theses.services.semantic_search.generate_thesis_embedding',
            lambda t, **k: calls.append('composite'),
        )
        monkeypatch.setattr(
            'theses.services.semantic_search.generate_title_embedding',
            lambda t, **k: calls.append('title'),
        )

        thesis = make_thesis('Needs Embedding', embedding_status=embedding_status)
        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(), thesis)

        assert calls == ['composite', 'title']

    def test_retry_is_skipped_for_rejection_and_reopening(
        self, model_admin, rf_request, make_thesis, monkeypatch,
    ):
        calls = []
        monkeypatch.setattr(
            'theses.services.semantic_search.generate_thesis_embedding',
            lambda t, **k: calls.append('composite'),
        )

        rejected = make_thesis('To Reject', embedding_status=EmbeddingStatus.FAILED)
        rejected.status = ThesisStatus.REJECTED
        save_via_admin(model_admin, rf_request(), rejected)

        reopened = make_thesis(
            'To Reopen', status=ThesisStatus.APPROVED,
            embedding_status=EmbeddingStatus.FAILED,
        )
        reopened.status = ThesisStatus.PENDING_REVIEW
        save_via_admin(model_admin, rf_request(), reopened)

        assert calls == []

    def test_failed_retry_leaves_the_approval_standing(
        self, model_admin, rf_request, make_thesis, admin_user, monkeypatch,
    ):
        def boom(*args, **kwargs):
            raise RuntimeError('SBERT unavailable')

        monkeypatch.setattr(
            'theses.services.semantic_search.generate_thesis_embedding', boom,
        )

        thesis = make_thesis('Unembeddable', embedding_status=EmbeddingStatus.FAILED)
        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(), thesis)

        thesis.refresh_from_db()
        assert thesis.status == ThesisStatus.APPROVED
        assert thesis.reviewed_by == admin_user
        assert thesis.reviewed_at is not None
        # The decision is still audited even though the repair failed.
        assert review_rows().count() == 1


# ---------------------------------------------------------------------------
# Audit durability
# ---------------------------------------------------------------------------

class TestAuditDurability:
    def test_review_survives_a_failing_audit_insert(
        self, model_admin, rf_request, make_thesis, admin_user, monkeypatch,
    ):
        """audit_logger.write swallows its own failures by contract."""
        def boom(*args, **kwargs):
            raise RuntimeError('audit table is unavailable')

        monkeypatch.setattr(AuditLog.objects, 'create', boom)

        thesis = make_thesis('Audit Outage')
        thesis.status = ThesisStatus.APPROVED
        save_via_admin(model_admin, rf_request(), thesis)

        thesis.refresh_from_db()
        assert thesis.status == ThesisStatus.APPROVED
        assert thesis.reviewed_by == admin_user


# ---------------------------------------------------------------------------
# 3. Redundancy display surfaces
# ---------------------------------------------------------------------------

class TestPercentFormat:
    @pytest.mark.parametrize('score,expected', [
        (0.8543, '85.4%'),
        (-0.0321, '-3.2%'),
        (0.5999, '60.0%'),
        (0.8499, '85.0%'),
        (1.0, '100.0%'),
        (0.0, '0.0%'),
    ])
    def test_half_away_from_zero_to_one_decimal(self, score, expected):
        assert _format_percent(score) == expected


class TestOverlapBadge:
    def test_not_computed_when_no_embedding(self, model_admin, make_thesis):
        thesis = make_thesis('No Vector', title_embedding=None)
        markup = model_admin.overlap_badge(thesis)

        assert 'Not computed' in markup
        assert '#6C757D' in markup

    @pytest.mark.parametrize('cosine,label,color', [
        (0.95, 'High Overlap', '#DC3545'),
        (0.70, 'Moderate', '#FFA500'),
        (0.20, 'Clean', '#28A745'),
    ])
    def test_palette_matches_label(
        self, model_admin, make_thesis, cosine, label, color,
    ):
        make_thesis('Approved', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(cosine))
        probe = make_thesis('Probe', title_embedding=basis(0))

        markup = model_admin.overlap_badge(probe)
        assert label in markup
        assert color in markup

    def test_label_uses_the_unrounded_score(self, model_admin, make_thesis):
        """0.5999 displays as 60.0% but is still Clean."""
        make_thesis('Approved', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(0.5999))
        probe = make_thesis('Probe', title_embedding=basis(0))

        markup = model_admin.overlap_badge(probe)
        assert 'Clean' in markup
        assert '60.0%' in markup

    def test_no_sort_link_offered(self, model_admin):
        assert not hasattr(model_admin.overlap_badge, 'admin_order_field')

    def test_title_with_markup_cannot_inject(self, model_admin, make_thesis):
        nasty = '<script>alert(1)</script>'
        make_thesis('Approved', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(0.9))
        probe = make_thesis(nasty, title_embedding=basis(0))

        markup = str(model_admin.overlap_badge(probe))
        assert '<script>' not in markup


class TestPreviewLink:
    def test_opens_in_a_new_tab_without_leaking_the_opener(
        self, model_admin, make_thesis,
    ):
        thesis = make_thesis('Previewable')
        markup = str(model_admin.preview_link(thesis))

        assert 'target="_blank"' in markup
        assert 'rel="noopener noreferrer"' in markup
        assert f'/theses/{thesis.id}/preview' in markup

    def test_uses_frontend_url_when_set(self, model_admin, make_thesis, settings):
        settings.FRONTEND_URL = 'https://thesys.example.edu/'
        thesis = make_thesis('Previewable')

        markup = str(model_admin.preview_link(thesis))
        assert f'https://thesys.example.edu/theses/{thesis.id}/preview' in markup

    def test_falls_back_to_cors_origin(self, model_admin, make_thesis, settings):
        if hasattr(settings, 'FRONTEND_URL'):
            del settings.FRONTEND_URL
        settings.CORS_ALLOWED_ORIGINS = ['https://cors.example.edu']
        thesis = make_thesis('Previewable')

        markup = str(model_admin.preview_link(thesis))
        assert 'https://cors.example.edu/theses/' in markup

    def test_trailing_slashes_do_not_double_up(self, model_admin, make_thesis, settings):
        settings.FRONTEND_URL = 'https://thesys.example.edu///'
        thesis = make_thesis('Previewable')

        markup = str(model_admin.preview_link(thesis))
        assert '.edu/theses/' in markup
        assert '.edu//' not in markup


class TestRedundancyAnalysisPanel:
    def test_unsaved_object_is_not_analysed(self, model_admin):
        markup = str(model_admin.redundancy_analysis(None))
        assert 'after the thesis is saved' in markup

    def test_missing_embedding_names_the_backfill_command(
        self, model_admin, make_thesis,
    ):
        thesis = make_thesis('No Vector', title_embedding=None)
        markup = str(model_admin.redundancy_analysis(thesis))

        assert 'Not computed' in markup
        assert 'embed_theses --titles-only' in markup

    def test_empty_corpus_says_so_explicitly(self, model_admin, make_thesis):
        """A green badge over an empty corpus must not read as 'verified'."""
        thesis = make_thesis('Alone', title_embedding=basis(0))
        markup = str(model_admin.redundancy_analysis(thesis))

        assert 'No other approved thesis' in markup

    def test_match_is_linked_and_corpus_size_stated(self, model_admin, make_thesis):
        match = make_thesis('The Match', status=ThesisStatus.APPROVED,
                            title_embedding=at_cosine(0.92))
        make_thesis('Another', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(0.1))
        probe = make_thesis('Probe', title_embedding=basis(0))

        markup = str(model_admin.redundancy_analysis(probe))
        expected_url = reverse('admin:theses_thesis_change', args=[match.id])

        assert expected_url in markup
        assert 'The Match' in markup
        assert 'High Overlap' in markup
        assert '2 approved theses' in markup

    def test_singular_noun_at_corpus_size_one(self, model_admin, make_thesis):
        make_thesis('Only One', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(0.5))
        probe = make_thesis('Probe', title_embedding=basis(0))

        markup = str(model_admin.redundancy_analysis(probe))
        assert '1 approved thesis.' in markup

    def test_matched_title_is_escaped(self, model_admin, make_thesis):
        """The panel renders a title the current reviewer never typed."""
        make_thesis('<script>alert(1)</script>', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0))

        markup = str(model_admin.redundancy_analysis(probe))
        assert '<script>' not in markup
        assert '&lt;script&gt;' in markup

    def test_brace_sequences_in_a_title_do_not_break_formatting(
        self, model_admin, make_thesis,
    ):
        make_thesis('Study of {0} and {advisory} Braces',
                    status=ThesisStatus.APPROVED, title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0))

        markup = str(model_admin.redundancy_analysis(probe))
        assert '{0}' in markup
        assert '{advisory}' in markup


# ---------------------------------------------------------------------------
# Page batching
# ---------------------------------------------------------------------------

class TestPageBatching:
    def test_changelist_analyses_the_page_once(
        self, client, admin_user, make_thesis, monkeypatch,
    ):
        make_thesis('Approved Corpus', status=ThesisStatus.APPROVED,
                    title_embedding=at_cosine(0.8))
        for i in range(20):
            make_thesis(f'Row {i}', title_embedding=basis(i % 5))

        calls = []
        import theses.admin as admin_module
        real = admin_module.analyze_titles

        def counting(theses):
            probes = list(theses)
            calls.append(len(probes))
            return real(probes)

        monkeypatch.setattr(admin_module, 'analyze_titles', counting)

        client.force_login(admin_user)
        response = client.get(reverse('admin:theses_thesis_changelist'))

        assert response.status_code == 200
        # Exactly one batch call for the whole page — not one per row.
        assert len(calls) == 1
        assert calls[0] == 21

    def test_changelist_survives_a_failing_analysis(
        self, client, admin_user, make_thesis, monkeypatch,
    ):
        make_thesis('Row', title_embedding=basis(0))

        import theses.admin as admin_module
        monkeypatch.setattr(
            admin_module, 'analyze_titles',
            lambda theses: (_ for _ in ()).throw(RuntimeError('analyzer down')),
        )

        client.force_login(admin_user)
        response = client.get(reverse('admin:theses_thesis_changelist'))

        assert response.status_code == 200
        assert 'Not computed' in response.content.decode()


# ---------------------------------------------------------------------------
# Change form rendering
# ---------------------------------------------------------------------------

class TestChangeFormRendering:
    def test_provenance_fields_render_read_only(
        self, client, admin_user, make_thesis,
    ):
        thesis = make_thesis('Editable', title_embedding=basis(0))
        client.force_login(admin_user)

        response = client.get(
            reverse('admin:theses_thesis_change', args=[thesis.id])
        )
        body = response.content.decode()

        assert response.status_code == 200
        assert 'name="reviewed_by"' not in body
        assert 'name="reviewed_at"' not in body
        # rejection_reason stays editable.
        assert 'name="rejection_reason"' in body

    def test_review_fieldset_order_is_pinned(self, model_admin):
        review = dict(ThesisAdmin.fieldsets)['Review Status']
        assert review['fields'] == (
            'status',
            'rejection_reason',
            'redundancy_analysis',
            'reviewed_by',
            'reviewed_at',
        )

    def test_provenance_is_read_only(self):
        for field in ('reviewed_by', 'reviewed_at', 'redundancy_analysis'):
            assert field in ThesisAdmin.readonly_fields

    def test_change_form_renders_with_a_missing_embedding(
        self, client, admin_user, make_thesis,
    ):
        thesis = make_thesis('No Vector', title_embedding=None)
        client.force_login(admin_user)

        response = client.get(
            reverse('admin:theses_thesis_change', args=[thesis.id])
        )
        assert response.status_code == 200
        assert 'Not computed' in response.content.decode()

    def test_add_form_renders(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get(reverse('admin:theses_thesis_add'))

        assert response.status_code == 200
        assert 'after the thesis is saved' in response.content.decode()

    def test_admin_uses_the_theses_plural(self, client, admin_user, make_thesis):
        make_thesis('Anything')
        client.force_login(admin_user)

        response = client.get(reverse('admin:theses_thesis_changelist'))
        body = response.content.decode()

        assert 'Theses' in body
        assert 'Thesiss' not in body
