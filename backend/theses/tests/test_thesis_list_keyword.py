"""Tests for the ``keyword`` filter on GET /api/v1/theses/.

Covers the clickable-keyword data path: a keyword badge in the repository or
on a thesis detail page links to ``/repository?keyword=<tag>``, and the
frontend forwards that value straight to this endpoint.

  1. ``keyword=IoT`` matches tags stored as 'iot' and 'IOT' — case-blind.
  2. ``keyword=Internet of Things`` matches 'internet  of  things' —
     whitespace-blind, including doubled inner spaces.
  3. ``keyword=ai`` does NOT match 'domain' or 'training'. This is the
     substring trap: ``keywords`` is a JSONField list, so
     ``keywords__icontains`` would match the serialised JSON text and return
     every thesis whose tags merely CONTAIN the letters. Test 3 fails loudly
     if anyone reaches for icontains later.
  4. Absent param → response identical to no filtering at all.
  5. Composes with ``year`` and ``program``.
  6. Composes with ``q`` (keyword narrows the candidate set, then semantic
     ranking sorts the survivors).
  7. Respects ``_visible_queryset`` — a student never sees another user's
     pending or rejected thesis through a keyword link.
  8. No match → 200 with an empty page, never 404.
  9. A keyword over ``MAX_KEYWORD_LENGTH`` → 200 with an empty page.

MODULE NAMING: this follows the one-module-per-list-filter convention already
established by ``test_thesis_list_ids.py`` and ``test_thesis_list_mine.py``.
There is no generic thesis-list module to extend; each of those files is
scoped to a single filter by its own docstring.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus
from theses.views import _normalise_keyword


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='faculty.kw@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Keyword',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def student_a(db):
    return User.objects.create_user(
        email='student.a.kw@pampangastateu.edu.ph',
        first_name='Student',
        last_name='A',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def student_b(db):
    return User.objects.create_user(
        email='student.b.kw@pampangastateu.edu.ph',
        first_name='Student',
        last_name='B',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db):
    """Factory: creates a Thesis uploaded by an arbitrary user."""
    counter = {'n': 0}

    def _make(uploaded_by, title='Test Thesis', program=Program.BSIT.value,
              year=2024, status=ThesisStatus.APPROVED, keywords=None):
        counter['n'] += 1
        n = counter['n']
        sha = (f'{n:x}' + 'c' * 64)[:64]
        from django.core.files.base import ContentFile

        thesis = Thesis(
            title=title,
            abstract=f'Abstract for {title}.',
            authors=['Tester, T.'],
            keywords=keywords or [],
            program=program,
            year=year,
            adviser='',
            file_type=FileType.PDF,
            sha256=sha,
            extracted_text='',
            status=status,
            uploaded_by=uploaded_by,
        )
        thesis.uploaded_file.save(
            f'thesis_kw_{n}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        thesis.save()
        return thesis

    return _make


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _get(client, user, query=''):
    url = reverse('thesis-list')
    return client.get(
        f'{url}{query}',
        HTTP_AUTHORIZATION=f'Bearer {_bearer(user)}',
    )


def _ids(response):
    return {r['id'] for r in response.json()['results']}


# ---------------------------------------------------------------------------
# _normalise_keyword — the comparison key
# ---------------------------------------------------------------------------

class TestNormaliseKeyword:
    """Both axes matter, and both come from real stored data."""

    @pytest.mark.parametrize('raw, expected', [
        ('IoT', 'iot'),
        ('IOT', 'iot'),
        ('iot', 'iot'),
        # Whitespace: doubled inner spaces and stray leading/trailing space.
        ('internet  of  things', 'internet of things'),
        ('  Internet Of Things  ', 'internet of things'),
        # The real corpus value, with its stray space before the hyphen.
        ('Solar -Powered Water Pump', 'solar -powered water pump'),
        ('\tMachine\nLearning ', 'machine learning'),
        ('', ''),
        (None, ''),
    ])
    def test_folds_case_and_whitespace(self, raw, expected):
        assert _normalise_keyword(raw) == expected

    def test_distinct_keywords_stay_distinct(self):
        """Folding must not collapse genuinely different tags."""
        assert _normalise_keyword('AI') != _normalise_keyword('AI Ethics')
        assert _normalise_keyword('web') != _normalise_keyword('web-based')


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestKeywordFilter:
    def test_case_insensitive_match(self, client, faculty_user, make_thesis):
        """Students enter 'IoT', 'IOT' and 'iot' as three spellings of one tag."""
        lower = make_thesis(faculty_user, title='Lower', keywords=['iot', 'sensors'])
        upper = make_thesis(faculty_user, title='Upper', keywords=['IOT'])
        camel = make_thesis(faculty_user, title='Camel', keywords=['IoT'])
        other = make_thesis(faculty_user, title='Other', keywords=['blockchain'])

        response = _get(client, faculty_user, '?keyword=IoT')

        assert response.status_code == 200
        assert _ids(response) == {str(lower.id), str(upper.id), str(camel.id)}
        assert str(other.id) not in _ids(response)
        assert response.json()['count'] == 3

    def test_whitespace_insensitive_match(self, client, faculty_user, make_thesis):
        """Tags pasted out of a PDF carry doubled and stray spaces."""
        doubled = make_thesis(
            faculty_user, title='Doubled', keywords=['internet  of  things'],
        )
        padded = make_thesis(
            faculty_user, title='Padded', keywords=['  Internet Of Things  '],
        )

        response = _get(client, faculty_user, '?keyword=Internet of Things')

        assert response.status_code == 200
        assert _ids(response) == {str(doubled.id), str(padded.id)}

    def test_stray_space_corpus_value_matches(self, client, faculty_user, make_thesis):
        """'Solar -Powered Water Pump' is a real stored tag, stray space included."""
        thesis = make_thesis(
            faculty_user, title='Solar', keywords=['Solar -Powered Water Pump'],
        )

        response = _get(
            client, faculty_user, '?keyword=Solar%20-Powered%20%20Water%20Pump',
        )

        assert _ids(response) == {str(thesis.id)}

    # ── THE SUBSTRING TRAP ────────────────────────────────────────────────

    def test_does_not_substring_match_other_keywords(
        self, client, faculty_user, make_thesis,
    ):
        """LOCK: ``keywords__icontains`` must never be used here.

        ``keywords`` is a JSONField holding a list, so icontains matches
        against the serialised JSON text. ``keyword=ai`` would then return
        theses tagged 'domain', 'training' and 'email', because each contains
        the letters 'ai'. That is the single most likely wrong turn in this
        feature, so it gets its own test.

        If this fails, someone swapped the element-wise comparison for a
        substring query. Do not relax the assertion.
        """
        tagged_ai = make_thesis(faculty_user, title='Real AI', keywords=['ai'])
        domain = make_thesis(faculty_user, title='Domain', keywords=['domain'])
        training = make_thesis(faculty_user, title='Training', keywords=['training'])
        email = make_thesis(faculty_user, title='Email', keywords=['email'])
        captain = make_thesis(faculty_user, title='Captain', keywords=['captain'])

        response = _get(client, faculty_user, '?keyword=ai')

        assert response.status_code == 200
        assert _ids(response) == {str(tagged_ai.id)}, (
            'keyword matching is substring-based; it must compare whole tags'
        )
        for substring_victim in (domain, training, email, captain):
            assert str(substring_victim.id) not in _ids(response)
        assert response.json()['count'] == 1

    def test_partial_prefix_does_not_match(self, client, faculty_user, make_thesis):
        """The reverse direction: a shorter stored tag must not match a longer query."""
        make_thesis(faculty_user, title='Web', keywords=['web'])

        response = _get(client, faculty_user, '?keyword=web-based systems')

        assert response.json()['count'] == 0

    # ── Absent / empty param ──────────────────────────────────────────────

    def test_absent_param_is_identical_to_no_filter(
        self, client, faculty_user, make_thesis,
    ):
        make_thesis(faculty_user, title='One', keywords=['iot'])
        make_thesis(faculty_user, title='Two', keywords=['ai'])
        make_thesis(faculty_user, title='Three', keywords=[])

        baseline = _get(client, faculty_user, '')
        with_empty_param = _get(client, faculty_user, '?keyword=')

        assert baseline.status_code == with_empty_param.status_code == 200
        assert baseline.json()['count'] == 3
        assert with_empty_param.json() == baseline.json()

    def test_whitespace_only_param_is_ignored(
        self, client, faculty_user, make_thesis,
    ):
        make_thesis(faculty_user, title='One', keywords=['iot'])
        make_thesis(faculty_user, title='Two', keywords=['ai'])

        response = _get(client, faculty_user, '?keyword=%20%20')

        assert response.json()['count'] == 2

    # ── Composition with the other filters ────────────────────────────────

    def test_composes_with_year(self, client, faculty_user, make_thesis):
        match = make_thesis(
            faculty_user, title='2024 IoT', year=2024, keywords=['iot'],
        )
        make_thesis(faculty_user, title='2023 IoT', year=2023, keywords=['iot'])

        response = _get(client, faculty_user, '?keyword=iot&year=2024')

        assert _ids(response) == {str(match.id)}

    def test_composes_with_program(self, client, faculty_user, make_thesis):
        match = make_thesis(
            faculty_user, title='BSIT IoT',
            program=Program.BSIT.value, keywords=['iot'],
        )
        make_thesis(
            faculty_user, title='BSCS IoT',
            program=Program.BSCS.value, keywords=['iot'],
        )

        response = _get(
            client, faculty_user, f'?keyword=iot&program={Program.BSIT.value}',
        )

        assert _ids(response) == {str(match.id)}

    def test_composes_with_semantic_query(self, client, faculty_user, make_thesis):
        """keyword narrows the candidate set, then ``q`` ranks the survivors.

        The assertion is about SCOPE, not ranking order: a thesis excluded by
        the keyword filter must not reappear because it scored well, and the
        semantic branch must still produce a well-formed 200.
        """
        in_scope = make_thesis(
            faculty_user,
            title='Greenhouse Monitoring With Sensors',
            keywords=['iot'],
        )
        out_of_scope = make_thesis(
            faculty_user,
            title='Greenhouse Monitoring With Sensors And Automation',
            keywords=['agriculture'],
        )

        response = _get(
            client, faculty_user, '?keyword=iot&q=greenhouse%20monitoring&min_score=0.0',
        )

        assert response.status_code == 200
        returned = _ids(response)
        assert str(out_of_scope.id) not in returned
        assert returned <= {str(in_scope.id)}

    # ── Visibility ────────────────────────────────────────────────────────

    def test_student_cannot_see_another_users_pending_thesis(
        self, client, student_a, student_b, make_thesis,
    ):
        """Layered on _visible_queryset, never a bypass."""
        visible = make_thesis(
            student_a, title='Approved IoT',
            status=ThesisStatus.APPROVED, keywords=['iot'],
        )
        hidden_pending = make_thesis(
            student_b, title='Pending IoT',
            status=ThesisStatus.PENDING_REVIEW, keywords=['iot'],
        )
        hidden_rejected = make_thesis(
            student_b, title='Rejected IoT',
            status=ThesisStatus.REJECTED, keywords=['iot'],
        )

        response = _get(client, student_a, '?keyword=iot')

        returned = _ids(response)
        assert str(visible.id) in returned
        assert str(hidden_pending.id) not in returned
        assert str(hidden_rejected.id) not in returned

    def test_student_still_sees_their_own_pending_thesis(
        self, client, student_a, make_thesis,
    ):
        """The own-upload carve-out in _visible_queryset must survive."""
        own_pending = make_thesis(
            student_a, title='My Pending IoT',
            status=ThesisStatus.PENDING_REVIEW, keywords=['iot'],
        )

        response = _get(client, student_a, '?keyword=iot')

        assert str(own_pending.id) in _ids(response)

    def test_faculty_sees_pending_theses(self, client, faculty_user, student_b, make_thesis):
        pending = make_thesis(
            student_b, title='Pending IoT',
            status=ThesisStatus.PENDING_REVIEW, keywords=['iot'],
        )

        response = _get(client, faculty_user, '?keyword=iot')

        assert str(pending.id) in _ids(response)

    # ── Degenerate input ──────────────────────────────────────────────────

    def test_no_match_returns_empty_page_not_404(
        self, client, faculty_user, make_thesis,
    ):
        make_thesis(faculty_user, title='One', keywords=['iot'])

        response = _get(client, faculty_user, '?keyword=nonexistent-tag')

        assert response.status_code == 200
        assert response.json()['count'] == 0
        assert response.json()['results'] == []

    def test_overlong_keyword_returns_empty_page(
        self, client, faculty_user, make_thesis,
    ):
        """150 characters cannot be a real tag; an empty page, not an error."""
        make_thesis(faculty_user, title='One', keywords=['iot'])

        response = _get(client, faculty_user, f'?keyword={"x" * 150}')

        assert response.status_code == 200
        assert response.json()['count'] == 0

    def test_length_boundary_is_still_searched(
        self, client, faculty_user, make_thesis,
    ):
        """Exactly MAX_KEYWORD_LENGTH is searched, not rejected."""
        from theses.views import ThesisListView

        tag = 'y' * ThesisListView.MAX_KEYWORD_LENGTH
        thesis = make_thesis(faculty_user, title='Long tag', keywords=[tag])

        response = _get(client, faculty_user, f'?keyword={tag}')

        assert _ids(response) == {str(thesis.id)}

    def test_thesis_with_no_keywords_is_never_matched(
        self, client, faculty_user, make_thesis,
    ):
        """``keywords`` may be an empty list or null; neither may crash or match."""
        make_thesis(faculty_user, title='No tags', keywords=[])
        tagged = make_thesis(faculty_user, title='Tagged', keywords=['iot'])

        response = _get(client, faculty_user, '?keyword=iot')

        assert _ids(response) == {str(tagged.id)}

    def test_requires_authentication(self, client):
        url = reverse('thesis-list')
        response = client.get(f'{url}?keyword=iot')

        assert response.status_code == 401

    def test_response_envelope_is_unchanged(
        self, client, faculty_user, make_thesis,
    ):
        """The frontend already knows the keyword it clicked; no new fields."""
        make_thesis(faculty_user, title='One', keywords=['iot'])

        response = _get(client, faculty_user, '?keyword=iot')

        body = response.json()
        assert set(body) == {'count', 'next', 'previous', 'results'}
