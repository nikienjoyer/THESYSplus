"""Abstract recovery must be isolated from successful metadata extraction."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from theses.services.text_extractor import ExtractionResult, ThesisTextExtractor
from theses.views import ThesisExtractMetadataView
from theses.services.abstract_recovery import recover_text_abstract
from theses.services.abstract_recovery import _column_texts, recover_layout_abstract
from theses.services.abstract_recovery import recover_ocr_abstract


BODY = ('This study developed a system to improve access to information. '
        'The researchers evaluated the system with users and found that it '
        'supported their daily work and improved the quality of service.')


@pytest.fixture
def endpoint(monkeypatch):
    fields = {
        'title': {'value': 'Original title', 'confidence': 'high'},
        'authors': {'value': ['A', 'B', 'C', 'D', 'E'], 'confidence': 'medium'},
        'keywords': {'value': [], 'confidence': 'low'},
        'abstract': {'value': '', 'confidence': 'low'},
        'year': {'value': 2024, 'confidence': 'medium'},
        'program': {'value': 'BSIS', 'confidence': 'high'},
    }
    monkeypatch.setattr('theses.views._gate_document', lambda *a, **k: SimpleNamespace(passed=True))
    monkeypatch.setattr('theses.services.metadata_extraction.extract_metadata',
                        lambda *a, **k: deepcopy(fields))
    extract = Mock(side_effect=[
        ExtractionResult('Original text', 'pypdf', True),
        ExtractionResult('ABSTRACT\n' + BODY + '\nKeywords: testing', 'pypdf', True),
    ])
    monkeypatch.setattr(ThesisTextExtractor, 'extract', extract)
    return fields, extract


def test_missing_abstract_reuses_keyword_window_and_preserves_other_fields(endpoint):
    fields, extract = endpoint
    data = ThesisExtractMetadataView()._extract_and_respond('example.pdf').data
    assert [c.kwargs['max_pages'] for c in extract.call_args_list] == [10, 15]
    assert data['fields']['abstract']['value'] == BODY
    for key in ('title', 'authors', 'year', 'program'):
        assert data['fields'][key] == fields[key]
    assert set(data) == {'fields', 'filled_fields', 'method', 'message'}
    assert set(data['fields']) == set(fields)
    assert 'abstract' in data['filled_fields']
    assert data['method'] == 'pypdf'


def test_existing_abstract_and_keywords_never_retry(endpoint):
    fields, extract = endpoint
    fields['abstract'] = {'value': BODY, 'confidence': 'high'}
    fields['keywords']['value'] = ['testing']
    data = ThesisExtractMetadataView()._extract_and_respond('example.pdf').data
    assert extract.call_count == 1
    assert data['fields'] == fields


def test_abstract_only_retry_preserves_existing_keywords(endpoint):
    fields, extract = endpoint
    fields['keywords']['value'] = ['original']
    data = ThesisExtractMetadataView()._extract_and_respond('example.pdf').data
    assert extract.call_count == 2
    assert data['fields']['keywords'] == fields['keywords']


def test_docx_never_uses_pdf_recovery(endpoint):
    fields, extract = endpoint
    data = ThesisExtractMetadataView()._extract_and_respond('example.docx').data
    assert extract.call_count == 1
    assert data['fields'] == fields


def test_continuation_removes_page_numbers_and_repeated_margins():
    start, end = BODY.split('The researchers')
    pages = (
        'UNIVERSITY\n13\nABSTRACT\n' + start + 'The researchers\nCOLLEGE OF COMPUTING STUDIES',
        'UNIVERSITY\n1414 14\n' + end + '\nKeywords: testing\nCOLLEGE OF COMPUTING STUDIES',
    )
    abstract, confidence = recover_text_abstract(pages)
    assert abstract == BODY
    assert confidence == 'medium'


def test_fragmented_words_and_blank_lines_are_readable():
    body = BODY + ' The software development methodology produced useful results.'
    text = 'ABSTRACT\n' + '\n\n'.join(body.split()) + '\nKeywords: testing'
    assert recover_text_abstract((text,)) == (body, 'medium')


@pytest.mark.parametrize('text', [
    'TABLE OF CONTENTS\nAbstract ........ viii\nIntroduction 1\n' + BODY,
    'TABLE OF CONTENTS\nAbstract\nviii\n' + BODY + '\nKeywords: testing',
    'INTRODUCTION\n' + BODY + '\nKeywords: testing',
    BODY,
    'ABSTRACT\n' + BODY,  # No reliable end boundary.
    'ABSTRACT\n' + BODY[:-1] + '\nKeywords: testing',  # Truncated sentence.
    'ABSTRACT\n' + BODY + '\nUNRELATED SECTION\nOther prose.\nKeywords: testing',
    'ABSTRACT\n' + ('word ' * 1500) + '\nKeywords: testing',
])
def test_uncertain_or_negative_candidates_stay_blank(text):
    assert recover_text_abstract((text,)) == ('', 'low')


@pytest.mark.parametrize('heading', ['1. Introduction', '1.INTRODUCTION', 'I. INTRODUCTION'])
def test_stops_at_numbered_section_and_does_not_include_introduction(heading):
    assert recover_text_abstract(('ABSTRACT\n' + BODY + '\n' + heading + '\nUnrelated prose.',))[0] == BODY


def test_does_not_scan_beyond_page_fifteen_or_continue_for_three_pages():
    valid = 'ABSTRACT\n' + BODY + '\nKeywords: testing'
    assert recover_text_abstract(tuple([''] * 15 + [valid])) == ('', 'low')
    assert recover_text_abstract(('ABSTRACT\n' + BODY, 'More prose.', '\nKeywords: testing')) == ('', 'low')


def test_column_coordinates_exclude_parallel_introduction():
    from xml.sax.saxutils import escape

    def line(x, y, right, text):
        return (f'<line xMin="{x}" yMin="{y}" xMax="{right}">'
                f'<word>{escape(text)}</word></line>')

    # Deliberately store the right column first, just as an unordered PDF can.
    rows = [line(330, 110 + i * 15, 550, 'Unrelated introduction in the right column.')
            for i in range(8)]
    rows += [line(50, 100, 100, 'ABSTRACT'), line(50, 130, 300, BODY),
             line(50, 180, 290, 'Keywords: testing'),
             line(50, 210, 290, '1. Introduction'), line(50, 230, 300, 'Other prose.')]
    xml = '<doc><page width="600">' + ''.join(rows) + '</page></doc>'
    candidates = _column_texts(xml)
    assert len(candidates) == 1
    assert 'right column' not in candidates[0]
    assert recover_text_abstract((candidates[0],))[0] == BODY


def test_layout_only_reads_two_explicit_heading_pages(monkeypatch):
    monkeypatch.setattr('theses.services.abstract_recovery.shutil.which', lambda _: 'pdftotext')
    run = Mock(return_value=SimpleNamespace(stdout=b'<doc/>'))
    monkeypatch.setattr('theses.services.abstract_recovery.subprocess.run', run)
    pages = ('INTRODUCTION', 'ABSTRACT', 'ABSTRACT', 'ABSTRACT')
    assert recover_layout_abstract('example.pdf', pages) == ('', 'low')
    assert [c.args[0][2] for c in run.call_args_list] == ['2', '3']
    assert all(c.kwargs['timeout'] == 10 for c in run.call_args_list)


def test_layout_tool_unavailable_is_safe(monkeypatch):
    monkeypatch.setattr('theses.services.abstract_recovery.shutil.which', lambda _: None)
    assert recover_layout_abstract('example.pdf', ('ABSTRACT',)) == ('', 'low')


def test_successful_normal_abstract_never_uses_layout(endpoint, monkeypatch):
    fields, _ = endpoint
    fields['abstract'] = {'value': BODY, 'confidence': 'high'}
    layout = Mock(side_effect=AssertionError('Successful abstracts must stay untouched'))
    monkeypatch.setattr('theses.services.abstract_recovery.recover_layout_abstract', layout)
    data = ThesisExtractMetadataView()._extract_and_respond('example.pdf').data
    assert data['fields']['abstract'] == fields['abstract']
    layout.assert_not_called()


@pytest.fixture
def image_pages(monkeypatch):
    image = Mock()
    image.get_object.return_value = {'/Subtype': '/Image'}
    page = {'/Resources': {'/XObject': {'/Image1': image}}}
    monkeypatch.setattr('pypdf.PdfReader', lambda _: SimpleNamespace(pages=[page] * 20))


def test_targeted_ocr_ignores_document_text_threshold(image_pages):
    extractor = Mock()
    extractor.ocr_abstract_page.return_value = 'ABSTRACT\n' + BODY + '\nKeywords: testing'
    text, confidence = recover_ocr_abstract('example.pdf', ('Sparse cover', BODY * 10), extractor)
    assert (text, confidence) == (BODY, 'medium')
    assert extractor.ocr_abstract_page.call_args.args[1] == 1
    assert extractor.ocr_abstract_page.call_count == 1


def test_reuses_existing_cover_ocr_without_repeating_it():
    extractor = Mock()
    cover = ExtractionResult('ABSTRACT\n' + BODY + '\nKeywords: testing', 'ocr_tesseract', True)
    assert recover_ocr_abstract('example.pdf', ('',), extractor, cover_result=cover) == (BODY, 'medium')
    extractor.ocr_abstract_page.assert_not_called()


def test_failed_cover_ocr_is_not_repeated():
    extractor = Mock()
    cover = ExtractionResult('Sparse cover', 'pypdf', True)
    assert recover_ocr_abstract('example.pdf', ('',), extractor, cover_result=cover) == ('', 'low')
    extractor.ocr_abstract_page.assert_not_called()


@pytest.mark.parametrize('result', ['', 'INTRODUCTION\n' + BODY, 'ABSTRACT\n' + BODY[:-1] + '\nKeywords: testing'])
def test_ocr_bad_output_stays_blank(image_pages, result):
    extractor = Mock()
    extractor.ocr_abstract_page.return_value = result
    assert recover_ocr_abstract('example.pdf', ('',), extractor) == ('', 'low')


def test_ocr_failure_and_page_budget(image_pages):
    extractor = Mock()
    extractor.ocr_abstract_page.side_effect = RuntimeError('OCR unavailable')
    assert recover_ocr_abstract('example.pdf', tuple(['ABSTRACT'] * 20), extractor) == ('', 'low')
    assert [call.args[1] for call in extractor.ocr_abstract_page.call_args_list] == [1, 2]


def test_ocr_does_not_scan_sparse_unlabelled_interior_pages(image_pages):
    extractor = Mock()
    assert recover_ocr_abstract('example.pdf', (BODY * 10, '', '', ''), extractor) == ('', 'low')
    extractor.ocr_abstract_page.assert_not_called()


def test_ocr_renders_exactly_one_selected_page(monkeypatch):
    import pdf2image
    import pytesseract
    image = Mock()
    render = Mock(return_value=[image])
    recognize = Mock(return_value='OCR text')
    monkeypatch.setattr(pdf2image, 'convert_from_path', render)
    monkeypatch.setattr(pytesseract, 'image_to_string', recognize)
    assert ThesisTextExtractor().ocr_abstract_page('example.pdf', 12) == 'OCR text'
    assert render.call_args.kwargs['first_page'] == 12
    assert render.call_args.kwargs['last_page'] == 12
    assert render.call_args.kwargs['timeout'] == 15
    assert recognize.call_args.kwargs['timeout'] == 20
    image.close.assert_called_once()
    assert ThesisTextExtractor().ocr_abstract_page('example.pdf', 16) == ''
    assert render.call_count == 1


def test_preview_post_returns_same_schema_without_saving(endpoint, settings):
    # The inline path; the processing worker returns this same response body.
    settings.DOCUMENT_PROCESSING_ASYNC = False
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIRequestFactory, force_authenticate
    request = APIRequestFactory().post('/theses/extract-metadata/',
        {'file': SimpleUploadedFile('example.pdf', b'%PDF-1.4 test'), 'abstract': 'User-entered text'},
        format='multipart')
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
    response = ThesisExtractMetadataView.as_view()(request)
    assert response.status_code == 200
    assert set(response.data) == {'fields', 'filled_fields', 'method', 'message'}
    assert response.data['fields']['abstract']['value'] == BODY


def test_failed_extended_pass_preserves_primary_metadata(endpoint):
    fields, extract = endpoint
    fields['keywords']['value'] = ['original']
    extract.side_effect = [ExtractionResult('Original text', 'pypdf', True), RuntimeError('Unreadable PDF')]
    data = ThesisExtractMetadataView()._extract_and_respond('example.pdf').data
    assert data['fields'] == fields
    assert extract.call_count == 2


def test_rejection_gate_runs_before_any_recovery(endpoint, monkeypatch):
    from rest_framework.response import Response
    _, extract = endpoint
    monkeypatch.setattr('theses.views._gate_document', lambda *a, **k: SimpleNamespace(passed=False, reason='test', markers=[]))
    monkeypatch.setattr('theses.views._not_a_thesis_response', lambda gate: Response({'error': 'NOT_A_THESIS'}, status=400))
    response = ThesisExtractMetadataView()._extract_and_respond('example.pdf')
    assert response.status_code == 400
    assert extract.call_count == 1


def test_page_cache_preserves_primary_text_when_a_page_fails(monkeypatch):
    from pathlib import Path
    first = Mock()
    first.extract_text.return_value = BODY
    broken = Mock()
    broken.extract_text.side_effect = RuntimeError('Bad page')
    last = Mock()
    last.extract_text.return_value = BODY
    monkeypatch.setattr('pypdf.PdfReader', lambda _: SimpleNamespace(pages=[first, broken, last]))
    result = ThesisTextExtractor().extract(Path('example.pdf'), max_pages=15)
    assert result.text == BODY + '\n\n' + BODY
    assert result.page_texts == (BODY, '', BODY)


def test_cover_retry_skips_author_ocr_without_changing_cover_text(monkeypatch):
    from pathlib import Path
    import pypdf

    page = Mock()
    page.extract_text.return_value = 'Sparse cover'
    monkeypatch.setattr(pypdf, 'PdfReader', lambda _: SimpleNamespace(pages=[page]))
    cover_ocr = Mock(return_value='ABSTRACT\n' + BODY + '\nKeywords: testing')
    author_ocr = Mock(return_value=('Existing author hint',))
    monkeypatch.setattr(ThesisTextExtractor, '_ocr_pdf', lambda self, *a, **k: cover_ocr())
    monkeypatch.setattr(ThesisTextExtractor, '_ocr_first_page_author_lines',
                        lambda self, *a, **k: author_ocr())
    extractor = ThesisTextExtractor()
    preview = extractor.extract_cover_text(Path('example.pdf'))
    normal = extractor.extract(Path('example.pdf'), max_pages=1)
    assert preview.text == normal.text
    assert preview.method == normal.method == 'ocr_tesseract'
    assert preview.author_lines == ()
    assert normal.author_lines == ('Existing author hint',)
    assert cover_ocr.call_count == 2
    assert author_ocr.call_count == 1
