"""Tests for title-embedding storage, the upload wiring, and the backfill flag.

SBERT is patched throughout — no model is loaded. What is under test is the
plumbing: which columns get written, which are left alone, and that a failure
in one embedding path never suppresses the other.
"""

from __future__ import annotations

import io

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from reportlab.pdfgen import canvas
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, User
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus
from theses.services import semantic_search
from theses.services.semantic_search import (
    EMBEDDING_DIM,
    generate_title_embedding,
)
from theses.views import ThesisUploadView

MINIMAL_PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'

# The upload endpoint gates on document shape (see thesis_document_check), so
# anything posted through the view needs real, thesis-shaped extractable text.
# The stored-file fixture below keeps using MINIMAL_PDF: those theses are built
# straight through the ORM and never pass the gate.
THESIS_LINES = [
    'PAMPANGA STATE UNIVERSITY',
    'College of Computing Studies',
    '',
    'A MOBILE HEALTH RECORDS SYSTEM FOR RURAL CLINICS',
    '',
    'A Capstone',
    'Presented to the Faculty of',
    'In Partial Fulfillment',
    'of the Requirements for the Degree',
    '',
    'by:',
    'Dela Cruz, Juan M.',
    '',
    'May 2025',
    '',
    'ABSTRACT',
    'This study developed and evaluated a mobile health records platform for',
    'rural clinics, applying an iterative development methodology across three',
    'pilot sites and measuring staff adoption over two academic terms.',
    '',
    'Keywords: mobile health, records management, rural clinics',
    '',
    'CHAPTER I',
    'THE PROBLEM AND ITS BACKGROUND',
    'The researchers observed that paper records were routinely mislaid.',
    '',
    'REFERENCES',
]


def thesis_shaped_pdf() -> bytes:
    """A real multi-line PDF that clears the document-type gate."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 740
    for line in THESIS_LINES:
        if y < 60:
            pdf.showPage()
            y = 740
        pdf.drawString(54, y, line)
        y -= 16
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def unit_vector(seed: float = 1.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[0] = seed
    return vector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_media(settings, tmp_path):
    """Keep test uploads out of the real MEDIA_ROOT.

    Autouse is safe in this module: every test here touches the database
    anyway, so the ``setting_changed`` receivers have a connection available.
    """
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email='embed.student@pampangastateu.edu.ph',
        first_name='Embed',
        last_name='Student',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def fake_embed(monkeypatch):
    """Replace embed_text with a deterministic stub. No SBERT load."""
    calls = []

    def _stub(text: str):
        calls.append(text)
        return unit_vector()

    monkeypatch.setattr(semantic_search, 'embed_text', _stub)
    return calls


@pytest.fixture
def make_thesis(db, student):
    counter = {'n': 0}

    def _make(title: str = 'A Thesis', **kwargs) -> Thesis:
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
            sha256=(f'{n:x}' + 'd' * 64)[:64],
            status=kwargs.pop('status', ThesisStatus.APPROVED),
            uploaded_by=student,
            **kwargs,
        )
        thesis.uploaded_file.save(
            f'embed_{n}.pdf', ContentFile(MINIMAL_PDF), save=False,
        )
        thesis.save()
        return thesis

    return _make


# ---------------------------------------------------------------------------
# Model / column shape
# ---------------------------------------------------------------------------

class TestColumns:
    def test_both_columns_default_to_null(self, make_thesis):
        thesis = make_thesis('Fresh')
        thesis.refresh_from_db()

        assert thesis.title_embedding is None
        assert thesis.title_embedding_generated_at is None

    def test_columns_are_nullable_and_blankable(self):
        for name in ('title_embedding', 'title_embedding_generated_at'):
            field = Thesis._meta.get_field(name)
            assert field.null is True
            assert field.blank is True


# ---------------------------------------------------------------------------
# generate_title_embedding
# ---------------------------------------------------------------------------

class TestGenerateTitleEmbedding:
    def test_writes_vector_and_timestamp(self, make_thesis, fake_embed):
        thesis = make_thesis('Needs A Vector')
        generate_title_embedding(thesis)
        thesis.refresh_from_db()

        assert len(thesis.title_embedding) == EMBEDDING_DIM
        assert thesis.title_embedding_generated_at is not None

    def test_embeds_the_title_alone_not_the_composite(self, make_thesis, fake_embed):
        thesis = make_thesis('Just The Title')
        generate_title_embedding(thesis)

        # The abstract must not leak into the title vector's input.
        assert fake_embed == ['Just The Title']

    def test_leaves_composite_embedding_columns_untouched(self, make_thesis, fake_embed):
        thesis = make_thesis(
            'Has Composite',
            embedding_vector=[0.5] * EMBEDDING_DIM,
            embedding_status=EmbeddingStatus.READY,
            embedding_model='sentinel-model',
        )
        generate_title_embedding(thesis)
        thesis.refresh_from_db()

        assert thesis.embedding_vector == [0.5] * EMBEDDING_DIM
        assert thesis.embedding_status == EmbeddingStatus.READY
        assert thesis.embedding_model == 'sentinel-model'

    def test_write_advances_updated_at(self, make_thesis, fake_embed):
        """The redundancy corpus cache key depends on this.

        The sleep crosses a clock tick: on Windows the create and the update
        can otherwise land on the same ``timezone.now()`` value, which would
        make this assert flaky for reasons unrelated to the behaviour.
        """
        import time

        thesis = make_thesis('Touches updated_at')
        before = thesis.updated_at
        time.sleep(0.05)

        generate_title_embedding(thesis)
        thesis.refresh_from_db()

        assert thesis.updated_at > before
        assert 'updated_at' in [
            f.name for f in Thesis._meta.get_fields() if f.name == 'updated_at'
        ]

    def test_save_false_does_not_persist(self, make_thesis, fake_embed):
        thesis = make_thesis('In Memory Only')
        generate_title_embedding(thesis, save=False)

        assert thesis.title_embedding is not None
        thesis.refresh_from_db()
        assert thesis.title_embedding is None

    def test_whitespace_title_yields_a_zero_vector(self, make_thesis, monkeypatch):
        """embed_text's real contract for empty input, exercised end to end."""
        thesis = make_thesis('   ')
        generate_title_embedding(thesis)
        thesis.refresh_from_db()

        assert thesis.title_embedding == [0.0] * EMBEDDING_DIM
        # And a zero vector is treated as absent by the analyzer, so such a
        # thesis never enters the approved corpus.
        from theses.services.redundancy import analyze_titles
        result = analyze_titles([thesis])[thesis.id]
        assert result.computed is False

    def test_failure_propagates_to_the_caller(self, make_thesis, monkeypatch):
        def boom(text):
            raise RuntimeError('model unavailable')

        monkeypatch.setattr(semantic_search, 'embed_text', boom)
        thesis = make_thesis('Will Fail')

        with pytest.raises(RuntimeError):
            generate_title_embedding(thesis)

        thesis.refresh_from_db()
        assert thesis.title_embedding is None


# ---------------------------------------------------------------------------
# Upload path — step 7
# ---------------------------------------------------------------------------

def upload(student, *, title='Uploaded Thesis'):
    factory = APIRequestFactory()
    payload = {
        'title': title,
        'abstract': 'A sufficiently long abstract for the serializer to accept.',
        'authors': '["Tester, T."]',
        'keywords': '["test"]',
        'program': Program.BSIT.value,
        'year': '2024',
        'file': SimpleUploadedFile(
            'upload.pdf', thesis_shaped_pdf(), content_type='application/pdf',
        ),
    }
    request = factory.post('/api/v1/theses/upload/', payload, format='multipart')
    force_authenticate(request, user=student)
    return ThesisUploadView.as_view()(request)


@pytest.mark.django_db
class TestUploadWiring:
    def test_upload_populates_both_embeddings(self, student, fake_embed):
        response = upload(student)
        assert response.status_code == 201

        thesis = Thesis.objects.get(title='Uploaded Thesis')
        assert thesis.embedding_vector is not None
        assert thesis.title_embedding is not None
        assert thesis.title_embedding_generated_at is not None

    def test_composite_failure_still_writes_the_title_vector(
        self, student, monkeypatch,
    ):
        """The two calls are independent — one failing must not skip the other."""
        monkeypatch.setattr(semantic_search, 'embed_text', lambda t: unit_vector())
        monkeypatch.setattr(
            semantic_search, 'generate_thesis_embedding',
            lambda t, **k: (_ for _ in ()).throw(RuntimeError('composite down')),
        )

        response = upload(student, title='Composite Failed')
        assert response.status_code == 201

        thesis = Thesis.objects.get(title='Composite Failed')
        assert thesis.embedding_vector is None
        assert thesis.title_embedding is not None

    def test_title_failure_still_returns_201(self, student, monkeypatch):
        monkeypatch.setattr(semantic_search, 'embed_text', lambda t: unit_vector())
        monkeypatch.setattr(
            semantic_search, 'generate_title_embedding',
            lambda t, **k: (_ for _ in ()).throw(RuntimeError('title down')),
        )

        response = upload(student, title='Title Failed')
        assert response.status_code == 201

        thesis = Thesis.objects.get(title='Title Failed')
        assert thesis.title_embedding is None
        assert thesis.title_embedding_generated_at is None
        # The composite path is unaffected.
        assert thesis.embedding_vector is not None

    def test_both_failing_still_returns_201(self, student, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('all embeddings down')

        monkeypatch.setattr(semantic_search, 'generate_thesis_embedding', boom)
        monkeypatch.setattr(semantic_search, 'generate_title_embedding', boom)

        response = upload(student, title='Both Failed')
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# embed_theses --titles-only
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBackfillCommand:
    def test_titles_only_selects_rows_with_no_title_vector(
        self, make_thesis, fake_embed,
    ):
        missing = make_thesis('Missing Title Vector')
        already = make_thesis(
            'Already Has One', title_embedding=unit_vector(0.25),
        )

        call_command('embed_theses', '--titles-only')

        missing.refresh_from_db()
        already.refresh_from_db()

        assert missing.title_embedding is not None
        # Untouched — the stub would have overwritten it with unit_vector(1.0).
        assert already.title_embedding == unit_vector(0.25)

    def test_titles_only_with_regenerate_overwrites_everything(
        self, make_thesis, fake_embed,
    ):
        already = make_thesis('Already Has One', title_embedding=unit_vector(0.25))

        call_command('embed_theses', '--titles-only', '--regenerate')

        already.refresh_from_db()
        assert already.title_embedding == unit_vector(1.0)

    def test_titles_only_leaves_composite_columns_alone(
        self, make_thesis, fake_embed,
    ):
        thesis = make_thesis('Composite Preserved')
        thesis.refresh_from_db()

        call_command('embed_theses', '--titles-only', '--regenerate')

        thesis.refresh_from_db()
        assert thesis.embedding_vector is None
        assert thesis.embedding_status == EmbeddingStatus.NOT_STARTED

    def test_default_run_leaves_title_columns_alone(self, make_thesis, fake_embed):
        thesis = make_thesis('Title Preserved')

        call_command('embed_theses')

        thesis.refresh_from_db()
        assert thesis.embedding_vector is not None
        assert thesis.title_embedding is None
        assert thesis.title_embedding_generated_at is None

    def test_per_row_failure_does_not_abort_the_run(
        self, make_thesis, monkeypatch, capsys,
    ):
        good = make_thesis('Good Row')
        bad = make_thesis('Bad Row')

        def selective(text):
            if 'Bad' in text:
                raise RuntimeError('cannot embed this one')
            return unit_vector()

        monkeypatch.setattr(semantic_search, 'embed_text', selective)

        call_command('embed_theses', '--titles-only')

        good.refresh_from_db()
        bad.refresh_from_db()
        assert good.title_embedding is not None
        assert bad.title_embedding is None

        out = capsys.readouterr().out
        assert '1 embedded, 1 failed' in out


# ---------------------------------------------------------------------------
# Migration state
# ---------------------------------------------------------------------------

class TestMigrationState:
    def test_no_model_changes_are_outstanding(self):
        """The model and the migration graph agree."""
        from django.apps import apps
        from django.db.migrations.autodetector import MigrationAutodetector
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
        from django.db.migrations.state import ProjectState

        loader = MigrationLoader(None, ignore_no_migrations=True)
        autodetector = MigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            NonInteractiveMigrationQuestioner(specified_apps=set(), dry_run=True),
        )
        changes = autodetector.changes(graph=loader.graph)
        assert 'theses' not in changes, (
            'theses has unmigrated model changes: '
            f'{[op for m in changes["theses"] for op in m.operations]}'
        )
