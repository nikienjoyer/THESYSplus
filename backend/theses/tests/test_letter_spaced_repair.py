"""Tests for the letter-spaced PDF text repair in ``text_extractor``.

Canva-exported PDFs position every glyph individually, so pypdf emits a space
between every character — 'A B S T R A C T', never 'ABSTRACT'. Every heading
regex downstream is anchored on whole words, and a letter-spaced line's
alphabetic ratio (~0.47) sits below MIN_PROSE_ALPHA_RATIO, so title candidates
are disqualified outright. 17 of the 50 theses in this repository are affected.

THE DESIGN UNDER TEST IS PER-LINE, NOT PER-DOCUMENT
---------------------------------------------------
A document-wide ratio threshold was rejected because it misses partially
affected files (TASKGROVE sits at a document-wide ratio of 0.261, because Canva
letter-spaces only its display-font heading lines) and because it forces a
whole-text rewrite that collapses the 2-or-more space runs found in ordinary
prose. ``TestMixedDocument`` and ``TestNoOpOnRealCorpus`` are the two tests that
pin those properties, so neither regression can return unnoticed.
"""

from __future__ import annotations

import pytest

from theses.services.text_extractor import (
    _despace_line,
    _line_is_letter_spaced,
    despace_text,
)
from theses.services.thesis_document_check import check_thesis_document


# ---------------------------------------------------------------------------
# Fixtures — shaped after the real affected documents
# ---------------------------------------------------------------------------

# Every line letter-spaced, as DORMIFY / DHVCAT / COMPAWNION extract today.
SEVERE_LINES = [
    'D O R M I F Y :  D O R M  F I N D E R  A N D  M A N A G E M E N T  S Y S T E M',
    'B a l a o r o ,  D a v i d  J o s h u a  C .',
    'A B S T R A C T',
    'D o r m i f y ,  a n  i n n o v a t i v e  i n i t i a t i v e  a t  t h e  M a i n',
    'C a m p u s  i s  d e s i g n e d  t o  l o c a t e  a n d  m a n a g e  d o r m s .',
    'K e y w o r d s :  g e o f e n c i n g ,  d o r m i t o r y ,  m o b i l e',
    'I N T R O D U C T I O N',
    'T h e  r e s e a r c h e r s  o b s e r v e d  a  r e c u r r i n g  p r o b l e m .',
    'R E F E R E N C E S',
]

# TASKGROVE's shape: letter-spaced display-font HEADINGS above clean body prose.
# This is the case a document-wide ratio threshold cannot see.
MIXED_SPACED_HEADINGS = [
    'T A S K G R O V E :',
    'A  T R E E - B A S E D  P R O J E C T  M A N A G E M E N T  A P P L I C A T I O N',
    'A B S T R A C T',
]
MIXED_CLEAN_BODY = [
    "TaskGrove is an online platform that is essential in today's",
    'project management landscape. Its emergence has brought about a',
    'significant revolution in the way tasks are organized within',
    'project frameworks, leading to a remarkable increase in',
    'productivity levels. This innovative platform not only simplifies',
    'the complex process of achieving goals but also ensures the',
    'success of projects by providing a seamless and efficient workflow',
    'that minimizes errors, setting it apart from outdated manual',
    'methods or inadequately designed tools available on the market.',
    'In this study, the researchers employed a descriptive research',
    'design and used quantitative methodology to gauge the preferences',
    'of forty respondents working within the campus planning office of',
    'Don Honorio Ventura State University. The aim was to assess how',
    'well the respondents received the web application, considering its',
    'functional suitability, performance efficiency, compatibility,',
    'usability, reliability, security, maintainability and portability,',
    'across a range of devices and browser versions in common use.',
    'The results gained a total of 3.87 in the overall assessment,',
    'which the evaluators interpreted as a very satisfactory outcome',
    'for a first production release of the planning application.',
]

# Headings that sit INSIDE the body region, still letter-spaced. Kept separate
# from MIXED_CLEAN_BODY so the expected repair count stays explicit rather than
# being inferred from the detector the test is supposed to be checking.
MIXED_INTERLEAVED_HEADINGS = [
    'C H A P T E R  I',
    'R E F E R E N C E S',
]

# Verbatim prose fragments from the REAL corpus, each containing a run of 2 or
# more spaces. These are the exact strings that broke the earlier
# whole-document design: it rejoined the entire text, collapsing these runs and
# so failing byte-identity on every clean thesis. They are embedded here
# because the pytest database is isolated and empty, so a DB-backed canary
# cannot run in-suite — see TestNoOpOnRealCorpus.
REAL_CORPUS_SPACE_RUNS = [
    'with much better assistance and immediate response, with the help and support from  the lo',
    'is the practice of planning and enforcing limits on how  much time is ',
    'different sources into a single user interface. It can serve as a  ',
    'In Partial Fulfillment  ',
    '11  1 ',
]


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class TestDetector:
    @pytest.mark.parametrize('line', [
        'A B S T R A C T',
        'R E F E R E N C E S',
        'I N T R O D U C T I O N',
        'D O R M I F Y :  D O R M  F I N D E R',
        'B a l a o r o ,  D a v i d  J o s h u a  C .',
    ])
    def test_letter_spaced_lines_are_detected(self, line):
        assert _line_is_letter_spaced(line)

    @pytest.mark.parametrize('line', [
        # Ordinary prose.
        'TaskGrove is an online platform that is essential today',
        'The researchers observed a recurring problem in the workflow.',
        'PAMPANGA STATE UNIVERSITY',
        'Presented to the Faculty of',
        # Prose containing a legitimate run of 2+ spaces.
        'with the help and support from  the local government unit',
        '',
        '   ',
    ])
    def test_normal_lines_are_not_detected(self, line):
        assert not _line_is_letter_spaced(line)

    @pytest.mark.parametrize('line', ['A B', 'A B C', 'A  B  C', 'x y z'])
    def test_short_lines_fail_the_token_count_condition(self, line):
        """Condition 2: fewer than 4 tokens can never qualify.

        'A B C' is 100% single-char and 3 of them are alphabetic, so only the
        token-count floor stops it.
        """
        assert not _line_is_letter_spaced(line)

    @pytest.mark.parametrize('line', [
        '1 2 3 4 5',
        '4 5 3 4 4 20',
        '1 2 3 4 5 6 7 8 9 10',
        '5 4 5 5 4',
    ])
    def test_numeric_rows_fail_the_alphabetic_condition(self, line):
        """Condition 3, and the reason it is not optional.

        A Likert-scale results row is 100% single-character tokens and would be
        welded into '12345' without this guard, silently corrupting table data.
        """
        assert not _line_is_letter_spaced(line)

    def test_mostly_numeric_row_with_few_letters_is_not_detected(self):
        """Three letters is below the floor of four."""
        assert not _line_is_letter_spaced('a 1 2 b 3 4 c 5')

    def test_ratio_floor_rejects_mixed_lines(self):
        """Condition 1: a line with mostly multi-char tokens is left alone."""
        assert not _line_is_letter_spaced('The a b c quick brown fox jumped over')


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

class TestDespaceLine:
    @pytest.mark.parametrize('raw, expected', [
        ('A B S T R A C T', 'ABSTRACT'),
        ('D O R M I F Y :  D O R M  F I N D E R', 'DORMIFY: DORM FINDER'),
        ('K e y w o r d s :  g e o f e n c i n g', 'Keywords: geofencing'),
        ('T A S K G R O V E :', 'TASKGROVE:'),
        ('C H A P T E R  I', 'CHAPTER I'),
        # Leading/trailing space runs must not leave stray separators.
        ('  A B S T R A C T  ', 'ABSTRACT'),
    ])
    def test_word_boundaries_land_on_double_spaces(self, raw, expected):
        assert _despace_line(raw) == expected

    def test_four_spaces_is_still_one_boundary(self):
        assert _despace_line('A B    C D') == 'AB CD'


class TestDespaceText:
    def test_returns_count_of_repaired_lines(self):
        text = '\n'.join(SEVERE_LINES)
        repaired, count = despace_text(text)

        assert count == len(SEVERE_LINES)
        assert 'ABSTRACT' in repaired
        assert 'REFERENCES' in repaired

    def test_nothing_to_repair_reports_zero_and_returns_input(self):
        text = 'A perfectly ordinary paragraph of text.\n\nAnd another one.'
        repaired, count = despace_text(text)

        assert count == 0
        assert repaired == text

    def test_blank_and_empty_input(self):
        assert despace_text('') == ('', 0)
        assert despace_text(None) == ('', 0)

    def test_line_count_and_blank_positions_are_preserved(self):
        """Blank lines are the gate's primary title-block boundary."""
        text = 'A B S T R A C T\n\n\nB o d y  t e x t  h e r e  n o w'
        repaired, _ = despace_text(text)

        assert len(repaired.split('\n')) == len(text.split('\n'))
        assert repaired.split('\n')[1] == ''
        assert repaired.split('\n')[2] == ''


# ---------------------------------------------------------------------------
# Gate recovery
# ---------------------------------------------------------------------------

class TestGateRecovery:
    def test_severe_document_goes_from_zero_markers_to_passing(self):
        text = '\n'.join(SEVERE_LINES)

        before = check_thesis_document(text)
        assert before.marker_count == 0, 'fixture does not reproduce the bug'
        assert not before.passed

        repaired, count = despace_text(text)
        after = check_thesis_document(repaired)

        assert count > 0
        assert after.marker_count >= 2
        assert after.passed

    def test_cor_still_scores_zero_markers(self):
        """The gate must not be loosened as a side effect of the repair.

        A Certificate of Registration has no structural markers before OR after
        the repair — there is nothing letter-spaced about it to fix.
        """
        from theses.tests.test_thesis_gate_integration import COR_LINES

        text = '\n'.join(COR_LINES)
        before = check_thesis_document(text)
        repaired, count = despace_text(text)
        after = check_thesis_document(repaired)

        assert before.marker_count == 0
        assert after.marker_count == 0
        assert not after.passed
        assert count == 0, 'no COR line should have been rewritten'
        assert repaired == text


# ---------------------------------------------------------------------------
# The mixed case a document-wide threshold could not see
# ---------------------------------------------------------------------------

class TestMixedDocument:
    """TASKGROVE's shape: spaced headings, clean body.

    Its document-wide single-char ratio is 0.261 — far below any workable
    global threshold — yet its title is unreadable. This test is the reason the
    detector is per line.
    """

    @staticmethod
    def _text():
        # Headings first, then body with the two interleaved headings placed
        # inside it, as a real paper lays out.
        body = MIXED_CLEAN_BODY[:10] + [MIXED_INTERLEAVED_HEADINGS[0]] \
            + MIXED_CLEAN_BODY[10:] + [MIXED_INTERLEAVED_HEADINGS[1]]
        return '\n'.join(MIXED_SPACED_HEADINGS + body)

    def test_headings_are_repaired(self):
        repaired, count = despace_text(self._text())

        lines = repaired.split('\n')
        assert lines[0] == 'TASKGROVE:'
        assert lines[1] == 'A TREE-BASED PROJECT MANAGEMENT APPLICATION'
        assert lines[2] == 'ABSTRACT'
        assert 'CHAPTER I' in lines
        assert 'REFERENCES' in lines
        assert count == len(MIXED_SPACED_HEADINGS) + len(MIXED_INTERLEAVED_HEADINGS)

    def test_clean_body_lines_are_byte_identical(self):
        repaired, _ = despace_text(self._text())
        out = repaired.split('\n')

        for original in MIXED_CLEAN_BODY:
            assert original in out, (
                f'clean body line was altered: {original!r}'
            )

    def test_document_wide_ratio_would_have_missed_this(self):
        """Documents the rejected design's failure, so it is not re-proposed."""
        text = self._text()
        tokens = text.split()
        ratio = sum(1 for t in tokens if len(t) == 1) / len(tokens)

        assert ratio < 0.40, (
            f'fixture ratio {ratio:.3f} is not below the rejected 0.40 '
            'threshold, so it no longer models TASKGROVE'
        )
        # ...and yet the per-line detector still finds and fixes the headings.
        _, count = despace_text(text)
        assert count >= len(MIXED_SPACED_HEADINGS)


# ---------------------------------------------------------------------------
# NO-OP CANARY — the most important test in this module
# ---------------------------------------------------------------------------

class TestNoOpOnRealCorpusFragments:
    """The no-op canary, using verbatim REAL corpus fragments.

    This is the version that actually runs in CI. The pytest database is
    isolated and empty, so a query-the-corpus canary cannot assert anything
    in-suite (see TestNoOpOnRealCorpus below, which skips for that reason).
    Embedding the exact strings keeps the regression covered without a DB.

    Every fragment below contains a run of 2 or more spaces, which is precisely
    what the rejected whole-document design destroyed: it rewrote the entire
    text, collapsing these runs and failing byte-identity on all 33 clean
    theses. A hand-written fixture of tidy prose would not have caught it,
    because tidy prose has no double spaces.
    """

    @pytest.mark.parametrize('fragment', REAL_CORPUS_SPACE_RUNS)
    def test_real_prose_with_multi_space_runs_is_untouched(self, fragment):
        assert not _line_is_letter_spaced(fragment)
        repaired, count = despace_text(fragment)
        assert count == 0
        assert repaired == fragment, (
            'a run of 2+ spaces in real prose was collapsed'
        )

    def test_all_fragments_together_round_trip_exactly(self):
        text = '\n'.join(REAL_CORPUS_SPACE_RUNS)
        repaired, count = despace_text(text)

        assert count == 0
        assert repaired == text

    def test_fragments_really_do_contain_multi_space_runs(self):
        """Guards the fixture: if these lose their double spaces in editing,
        the tests above would pass while testing nothing."""
        import re as _re

        for fragment in REAL_CORPUS_SPACE_RUNS:
            assert _re.search(r' {2,}', fragment), (
                f'fixture no longer contains a 2+ space run: {fragment!r}'
            )


@pytest.mark.django_db
class TestNoOpOnRealCorpus:
    """Byte-identity across the whole stored corpus, when one is present.

    Skips on the isolated pytest database, which is empty. Kept because it is
    the assertion that matters on a populated database, and because it is the
    exact check run manually against the dev corpus after this change.
    ``TestNoOpOnRealCorpusFragments`` is the CI-effective counterpart.
    """

    CLEAN_RATIO_CEILING = 0.1

    @staticmethod
    def _single_char_ratio(text):
        tokens = (text or '').split()
        return (sum(1 for t in tokens if len(t) == 1) / len(tokens)) if tokens else 0.0

    def test_clean_corpus_text_is_byte_identical_after_repair(self):
        from theses.models import Thesis

        clean = [
            t for t in Thesis.objects.all()
            if (t.extracted_text or '').strip()
            and self._single_char_ratio(t.extracted_text) < self.CLEAN_RATIO_CEILING
        ]
        if not clean:
            pytest.skip('no clean theses with stored text in this database')

        altered = []
        for thesis in clean:
            original = thesis.extracted_text
            repaired, count = despace_text(original)
            if repaired != original or count:
                altered.append((thesis, original, repaired, count))

        assert not altered, (
            'the repair altered clean corpus text:\n' + '\n'.join(
                f'  {t.title[:60]!r} lines_repaired={c}'
                for t, _, _, c in altered
            )
        )

    def test_clean_corpus_gate_verdicts_are_unchanged(self):
        """Byte-identity implies this, but assert it directly.

        If the repair ever becomes lossy, this names the behavioural cost
        rather than only reporting a byte diff.
        """
        from theses.models import Thesis

        clean = [
            t for t in Thesis.objects.all()
            if (t.extracted_text or '').strip()
            and self._single_char_ratio(t.extracted_text) < self.CLEAN_RATIO_CEILING
        ]
        if not clean:
            pytest.skip('no clean theses with stored text in this database')

        for thesis in clean:
            before = check_thesis_document(thesis.extracted_text)
            after = check_thesis_document(despace_text(thesis.extracted_text)[0])
            assert before.markers == after.markers, (
                f'{thesis.title[:60]!r}: markers moved '
                f'{before.markers} -> {after.markers}'
            )
            assert before.passed == after.passed


# ---------------------------------------------------------------------------
# method reporting
# ---------------------------------------------------------------------------

class TestMethodReporting:
    """``method`` must distinguish a repaired extraction from a clean one.

    Built with reportlab so the PDF has a real text layer, then the letter
    spacing is drawn literally — this exercises the actual extractor, not just
    the helper.
    """

    @staticmethod
    def _pdf(lines):
        import io

        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=(612, 792))
        y = 740
        for line in lines:
            if y < 60:
                pdf.showPage()
                y = 740
            pdf.drawString(40, y, line)
            y -= 16
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    def test_method_is_pypdf_when_nothing_was_repaired(self, tmp_path):
        from theses.services.text_extractor import ThesisTextExtractor

        target = tmp_path / 'clean.pdf'
        target.write_bytes(self._pdf([
            'PAMPANGA STATE UNIVERSITY',
            'A MOBILE HEALTH RECORDS SYSTEM FOR RURAL CLINICS',
            'ABSTRACT',
            'This study developed and evaluated a records platform for clinics,',
            'applying an iterative methodology across three pilot sites and',
            'measuring staff adoption over two full academic terms in total.',
            'REFERENCES',
        ]))

        result = ThesisTextExtractor().extract(str(target))

        assert result.success
        assert result.method == 'pypdf'

    def test_method_is_pypdf_despaced_when_something_was_repaired(self, tmp_path):
        from theses.services.text_extractor import ThesisTextExtractor

        target = tmp_path / 'spaced.pdf'
        target.write_bytes(self._pdf(SEVERE_LINES * 3))

        result = ThesisTextExtractor().extract(str(target))

        assert result.success
        assert result.method == 'pypdf+despaced'
        assert 'ABSTRACT' in result.text
