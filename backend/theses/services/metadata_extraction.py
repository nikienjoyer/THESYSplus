"""Front-matter metadata extraction for uploaded thesis documents.

Extracted out of ``ThesisExtractTitleView._detect_title`` so the heuristics
are unit-testable and reusable (the view keeps a thin delegating shim for
backwards compatibility). This module is pure text analysis — it performs
no file I/O and touches no models, so it can be exercised directly against
strings in tests.

TITLE DETECTION — why it works the way it does
----------------------------------------------
Thesis title pages wrap long titles across two or three physical lines.
The previous single-line heuristic returned only the highest-scoring line,
so every multi-line title silently truncated at the first line break.

The fix is a two-stage design:

1. **Score lines to find where the title STARTS.** When adjacent scored lines
   are continuations in the same title block, keep the earlier line as the
   start rather than selecting a higher-scoring fragment.
2. **Join forward from that line to find where the title ENDS.**

Stage 2 uses blank lines as a strong boundary, but bridges up to two blank
extractor lines when the next nonblank line still looks like a title
continuation. Some PDFs insert those gaps between words or wrapped title lines.
The continuation check accepts connector-led phrases, single-word tails, and
adjacent lines with the same all-caps or title-case style. It stops at author
markers, contact details, boilerplate, and sentence-like prose.

Because ``pypdf`` emits genuinely blank-looking lines as ``' '`` or
``'  '`` on justified text, "blank" here means *blank after stripping*.
Whitespace runs inside real lines are collapsed to single spaces for the
same reason.

The connector list is retained only as a **secondary** signal, used when a
document has no blank-line structure at all (some extractors drop blank
lines entirely). In that case a following line is joined only if it opens
with a connector.

OTHER FIELDS
------------
``extract_metadata`` adds abstract, keywords, year, program and authors on
top of the title. Each returns its own confidence, because the fields are
not equally reliable: a labelled "Keywords:" line is near-certain, while an
author block is genuinely ambiguous (a line of Title Case words could be a
name, an affiliation, or an adviser). Every extractor returns an EMPTY value
rather than a guess when it is not reasonably sure — an empty field leaves
the user to fill it in, whereas a wrong value either gets published or, for
``program``, fails server-side validation on submit.
"""

from __future__ import annotations

import logging
import re
from datetime import date

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Word cap for the JOINED title. Real multi-line titles in this corpus join
# to roughly 12-18 words; 40 leaves generous headroom while still refusing
# to swallow a runaway paragraph.
MAX_TITLE_WORDS = 40

# How many non-blank lines from the top of the document to consider as
# possible title starts.
MAX_CANDIDATE_LINES = 40

# Minimum share of characters that must be letters for text to count as prose.
#
# The discriminating power here is enormous and glyph-independent: English
# prose runs near 0.8, while a table-of-contents dot-leader row
# ("ABSTRACT ......... viii") scores about 0.08 — roughly four letters in fifty
# characters. That gap holds whether the leader is typeset with ASCII periods,
# an ellipsis, a middle dot, or a tab artifact, which is why this is a better
# test than enumerating leader characters.
#
# Shared by title-candidate scoring and abstract validation so the two cannot
# drift to different definitions of "looks like prose".
MIN_PROSE_ALPHA_RATIO = 0.6


# Section/boilerplate headings that are never themselves a title.
#
# Matched by EXACT equality (after lowercasing and stripping surrounding
# punctuation) — deliberately NOT by prefix and NOT by containment:
#   * prefix matching discarded any legitimate title starting with a noise
#     word (e.g. a title beginning "Thesis Repository …")
#   * containment matching would discard a legitimate title that merely
#     contains one (e.g. "… AND THESIS REPOSITORY …")
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

# Keyword headings may carry their values on the same line or the following
# lines. They are section labels, not title candidates.
_TITLE_KEYWORD_LABEL = re.compile(
    r'^\s*(?:key\s*words?|index\s+terms?)\s*'
    r'(?:(?:[:\-\u2013\u2014])\s*.*)?$',
    re.IGNORECASE,
)

# Words that can legitimately open a title CONTINUATION line. Compared
# case-insensitively — a continuation may be typeset in caps ("WITH …") in
# an all-caps title, so a case-sensitive list silently fails those.
_TITLE_OPENING_CONNECTORS = frozenset({'a', 'an', 'the'})

_CONNECTOR_WORDS = frozenset({
    'for', 'of', 'in', 'on', 'at', 'and', 'with', 'using',
    'toward', 'towards', 'to', 'a', 'an', 'the',
    # Added after auditing the real corpus: each of these opened a genuine
    # title continuation that was being truncated. 'through' alone accounted
    # for two ("… Scholarship Management In Pampanga / Through Centralized
    # Automation", "… Matching / Through Attachments Styles And Love
    # Languages"). None can open an author-list entry, so the strict gate is
    # not measurably weakened by them.
    'through', 'via', 'from', 'into', 'across', 'within',
    'among', 'between', 'under', 'over', 'during',
})

# Connectors that may NOT open a title START line. A line beginning with one of
# these is a continuation, and treating it as a start loses everything above it.
#
# Derived from _CONNECTOR_WORDS minus _TITLE_OPENING_CONNECTORS so the two can
# never drift: adding a connector above automatically blocks it here, and the
# 'a'/'an'/'the' carve-out is expressed once.
_TITLE_START_BLOCKED = _CONNECTOR_WORDS - _TITLE_OPENING_CONNECTORS

# Tokens preserved verbatim when normalising an ALL-CAPS title, instead of
# being title-cased into nonsense ("(NLP)" -> "(Nlp)").
#
# Known limitation: a *coined* all-caps product name inside an otherwise
# all-caps title is indistinguishable from an ordinary word without a
# dictionary, so it will be title-cased. Add it here if that matters.
_KNOWN_ACRONYMS = frozenset({
    'AI', 'API', 'AR', 'BERT', 'BI', 'BSCS', 'BSIS', 'BSIT', 'CCS', 'CNN',
    'CS', 'CSS', 'DHVSU', 'ERP', 'GAN', 'GIS', 'GPS', 'GPT', 'HTML', 'HTTP',
    'ICT', 'IDF', 'IOT', 'IP', 'IS', 'IT', 'KNN', 'LLM', 'LSTM', 'ML',
    'MEMOLOOP', 'NLP', 'OCR', 'PDF', 'PSU', 'QR', 'RFID', 'RPA', 'SBERT',
    'SMS', 'SQL',
    'SVM', 'TF', 'UI', 'UX', 'VR', 'X', 'XML', 'YOLO',
})

# Chapter/section headings, used both to disqualify a line as a title and to
# detect "this document has no title page" at the document level.
_CHAPTER_PATTERNS = re.compile(
    r'^(chapter\s+[ivxlcdm\d]+|the problem and its background|'
    r'review of related literature|related literature|introduction|'
    r'methodology|results and discussion|conclusion|recommendations|'
    r'references|bibliography|appendix|abstract)[\s\.\:\-]*$',
    re.IGNORECASE,
)

# "by", "by:", "submitted by" — the author block always terminates the title.
_AUTHOR_MARKER = re.compile(
    r'^(by|submitted\s+by|prepared\s+by|presented\s+by|researchers?)\b\s*:?',
    re.IGNORECASE,
)

# ── Contact details ────────────────────────────────────────────────────────
#
# Title pages in this corpus routinely print each author's institutional email
# and mobile number directly beneath the title, with no "by:" marker to
# separate them. Without these the contact block joins onto the title and is
# offered to the user as the thesis title — which then gets published.
#
# Both are used with ``.search()``, not ``.match()``: the contact detail sits
# at the END of a line ("GONZAGA, KURT ROSS E. kurt@dhvsu.edu.ph"), so
# anchoring at the start would miss every real case.

_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

# Two alternatives:
#   1. A Philippine mobile number, with or without country code and with
#      optional spacing or dashes between groups: 09170000001, +63 917 000
#      9130, 0939-742-9130.
#   2. Any bare run of 7 or more digits. This is the catch-all, and it also
#      covers student numbers (2018000001), which are PII in their own right.
#
# The floor is SEVEN deliberately. A year (2026), an ISO reference (9001), a
# section number and a page number are all four digits or fewer, so they
# cannot trip it. Every title fixture in this suite was checked for a 7+ digit
# run before this floor was chosen; the only hits in the whole test tree are
# raw PDF xref bytes and a Certificate of Registration student number, neither
# of which is a title.
_PHONE = re.compile(
    r'(?:\+?63|0)[\s\-]?9\d{2}[\s\-]?\d{3}[\s\-]?\d{4}'
    r'|\b\d{7,}\b'
)


def _has_contact_details(line: str) -> bool:
    """True when ``line`` contains an email address or a phone/ID number."""
    return bool(_EMAIL.search(line) or _PHONE.search(line))


def _remove_contact_details(line: str) -> str:
    """Delete every email and phone match from ``line``, keeping the rest.

    Distinct from :func:`_strip_pii_tail`, which CUTS at the first match and
    discards the remainder. That is the right behaviour for a title, where
    everything after the first contact detail is the author block. It is the
    wrong behaviour for an author name: cutting
    ``'GONZAGA, KURT ROSS E. kurt@dhvsu.edu.ph'`` at the email and then
    trimming name debris would also take the 'E.' initial off the name.

    Excising the matches in place instead preserves the full name. The removed
    text is discarded, never returned or stored.
    """
    cleaned = _EMAIL.sub(' ', line)
    cleaned = _PHONE.sub(' ', cleaned)
    return collapse_whitespace(cleaned).strip(' ,;:|-–—')


def _strip_pii_tail(title: str) -> str:
    """Cut ``title`` at the first email or phone number and tidy the stump.

    This is the last line of defence, and the only one that works when the
    extractor emits a whole page as a SINGLE line. With no newlines there are
    no lines to terminate, so ``_is_block_terminator`` can never fire — the
    assembled string has to be scrubbed directly.

    Cutting at the EARLIEST match of either pattern, rather than removing
    matches in place, is deliberate: everything after the first contact detail
    is the author block, and splicing individual matches out would leave the
    surnames behind welded into the title.

    The stump is then trimmed of trailing punctuation and of a dangling
    partial word — an all-caps surname immediately before an email
    ("... FARMERS GONZAGA, KURT ROSS E. kurt@...") leaves debris that a naive
    cut keeps.
    """
    if not title:
        return title

    earliest = len(title)
    for pattern in (_EMAIL, _PHONE):
        match = pattern.search(title)
        if match and match.start() < earliest:
            earliest = match.start()

    if earliest >= len(title):
        return title

    return _trim_title_stump(title[:earliest])


def _trim_title_stump(stump: str) -> str:
    """Tidy the remainder left behind by a mid-string cut.

    Drops trailing separators and, because a cut lands just after the author
    names that precede a contact detail, drops trailing tokens that look like
    name debris: a bare initial ("E.") or a token ending in a comma
    ("GONZAGA,"). A trailing comma is the giveaway that the line was still
    mid-list when it was cut.
    """
    stump = collapse_whitespace(stump)

    while stump:
        tokens = stump.split()
        if not tokens:
            break
        last = tokens[-1]
        # A bare initial, a comma-terminated token, or a lone separator is
        # debris from the author list rather than part of the title.
        if re.fullmatch(r"[A-Za-z]\.?,?", last) or last.endswith(',') \
                or re.fullmatch(r'[\-–—:;,.]+', last):
            stump = ' '.join(tokens[:-1])
            continue
        break

    stump = _strip_trailing_name_block(stump)
    return stump.strip(' ,;:-–—')


def _strip_trailing_name_block(stump: str) -> str:
    """Remove a trailing "SURNAME, Given Middle" run from ``stump``.

    Only reachable on the single-line path. When the page has newlines the
    author line is a line of its own and ``_is_block_terminator`` removes it;
    when it does not, the names sit inline immediately before the contact
    detail we just cut at, so they survive the cut and have to be found here.

    The comma is the anchor, matching this corpus' author convention. Two
    guards keep it off real titles:

      * the run after the comma must be SHORT (at most four tokens) — an
        author's given names, not a clause;
      * the run must contain no :data:`_TITLE_KEYWORDS`. This is what saves a
        title like "... TRAINING, MONITORING SYSTEM FOR SCHOOLS": 'MONITORING'
        and 'SYSTEM' are title vocabulary, so the comma is punctuation inside a
        title rather than a surname separator.
    """
    tokens = stump.split()
    # Scan from the right for the LAST comma-terminated token; anything after
    # it is the candidate given-name run.
    for index in range(len(tokens) - 1, -1, -1):
        if not tokens[index].endswith(','):
            continue

        trailing = tokens[index + 1:]
        if not trailing or len(trailing) > 4:
            return stump
        if any(
            keyword in token.lower()
            for token in trailing
            for keyword in _TITLE_KEYWORDS
        ):
            return stump
        # Every trailing token must look like a name part: a capitalised word
        # or an initial, nothing else.
        if not all(
            re.fullmatch(r"[A-Z][A-Za-z'\-]*\.?|[A-Z]\.", token)
            for token in trailing
        ):
            return stump
        return ' '.join(tokens[:index])

    return stump

# Degree/submission boilerplate that follows the title on a title page.
# Acts as a safety net for documents whose blank lines were lost.
_FRONTMATTER_STOP = re.compile(
    r'^(a|an)\s+(capstone|thesis|dissertation|research|project|'
    r'undergraduate\s+thesis)\b'
    r'|^(in\s+partial\s+fulfilment|in\s+partial\s+fulfillment|'
    r'in\s+fulfilment|in\s+fulfillment|presented\s+to|submitted\s+to)\b',
    re.IGNORECASE,
)

# Domain words that make a line more likely to be a real thesis title.
_TITLE_KEYWORDS = frozenset({
    'system', 'using', 'based', 'approach', 'study',
    'analysis', 'design', 'development', 'implementation',
    'monitoring', 'detection', 'recognition', 'learning',
    'classification', 'prediction', 'platform', 'application',
    'framework', 'model', 'management', 'technology',
})

# Positive content words that support a two-word title line. Keep these
# separate from general title scoring and author-line heuristics. "Parking" is
# present in the repository's existing title fixtures (for example, "Smart
# Parking System").
_SHORT_TITLE_KEYWORDS = _TITLE_KEYWORDS | {'parking'}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _alpha_ratio(value: str) -> float:
    """Share of characters in ``value`` that are letters, 0.0 for empty input."""
    if not value:
        return 0.0
    return sum(1 for char in value if char.isalpha()) / len(value)


def collapse_whitespace(value: str) -> str:
    """Collapse whitespace runs to single spaces and trim.

    ``pypdf`` emits double (sometimes triple) spaces on justified text, so
    without this the extracted title carries them through to the form field.
    """
    return re.sub(r'\s+', ' ', value or '').strip()


def _noise_key(line: str) -> str:
    """Lowercased line with surrounding punctuation stripped, for noise lookup."""
    return line.lower().strip(' .,;:!?-\'"“”()[]{}')


def _is_lone_acronym_start(line: str) -> bool:
    """True for a standalone acronym/product label ending in a colon."""
    words = line.split()
    return (
        len(words) == 1
        and line.rstrip().endswith(':')
        and len(re.sub(r'[^A-Za-z0-9]', '', line)) >= 4
    )


def _has_interior_blank(lines: list[str]) -> bool:
    """True when a blank line appears BETWEEN the first and last real lines.

    Only interior blanks count as structure. A leading or trailing blank —
    which every ``text.split('\\n')`` produces from a trailing newline — is
    an artifact, not a document boundary. Treating it as structure would
    disable the connector fallback on documents that genuinely have no
    blank-line structure, letting the title block run on into the author
    list.
    """
    first = next((i for i, line in enumerate(lines) if line), None)
    if first is None:
        return False
    last = next(i for i in range(len(lines) - 1, -1, -1) if lines[i])
    return any(lines[i] == '' for i in range(first, last + 1))


def _is_non_title_boilerplate(line: str) -> bool:
    """True when ``line`` is structural furniture rather than title text.

    Everything that ends a title block EXCEPT an author-list entry. Kept
    separate from :func:`_is_block_terminator` because the two have different
    meanings and one caller needs only this half:
    ``_looks_like_person_name`` must reject headings, markers and contact
    details, but obviously must NOT reject a line for looking like an author —
    that is the thing it exists to detect. Folding the author test in here
    would make every real author name fail the name test.
    """
    key = _noise_key(line)
    if key in _SECTION_NOISE:
        return True
    if _CHAPTER_PATTERNS.match(key):
        return True
    author_marker = _AUTHOR_MARKER.match(line)
    if author_marker:
        # ``BY`` is also a normal title word. In particular, the source PDF
        # for SINDALAN CONNECT wraps its title as ``... SYSTEM POWERED`` /
        # ``BY AI CHATBOT AND EMERGENCY RESPONSE``. Treat a leading ``by`` as
        # an author marker only when it is a standalone label, carries a
        # colon, or introduces a short inline name. Longer unmarked phrases
        # are not author labels; author names with initials or the corpus'
        # surname-comma convention are still caught by the name detector.
        if re.match(r'^by\b', line, re.IGNORECASE):
            remainder = re.sub(r'^by\b\s*:?', '', line, flags=re.IGNORECASE).strip()
            if remainder and not line.lstrip().lower().startswith('by:'):
                if len(remainder.split()) > 3 and not _looks_like_author_line(remainder):
                    author_marker = None
        if author_marker:
            return True
    if _FRONTMATTER_STOP.match(line):
        return True
    # Contact details mean the title is over, whether or not a "by:" marker
    # ever appeared. Many title pages in this corpus have no such marker.
    if _has_contact_details(line):
        return True
    return False


def _is_block_terminator(line: str) -> bool:
    """True when ``line`` cannot be part of a title block."""
    if _is_non_title_boilerplate(line):
        return True
    # An author-list entry ends the title.
    if _looks_like_author_line(line):
        return True
    return False


# Typographic quote characters, folded to ASCII so a title reads the same
# regardless of the source PDF's typography.
_QUOTE_FOLDING = {
    '\u2018': "'",   # left single quotation mark
    '\u2019': "'",   # right single quotation mark / curly apostrophe
    '\u201a': "'",   # single low-9 quotation mark
    '\u201b': "'",   # single high-reversed-9 quotation mark
    '\u201c': '"',   # left double quotation mark
    '\u201d': '"',   # right double quotation mark
    '\u201e': '"',   # double low-9 quotation mark
    '\u201f': '"',   # double high-reversed-9 quotation mark
    '\u2032': "'",   # prime
    '\u2033': '"',   # double prime
}


def fold_quotes(title: str) -> str:
    """Fold typographic quotes in a detected title to their ASCII forms.

    A document carrying NOAH\u2019S ARK produced a title that disagreed with a
    hand-typed NOAH'S ARK on nothing but the apostrophe glyph. Folding makes
    titles comparable across the corpus whatever the source PDF's typography.

    DELIBERATELY QUOTES ONLY. En dash and em dash are NOT folded: an en dash in
    'Main Campus \u2013 Bacolor' is correct typography and must survive. Folding it
    to a hyphen would corrupt a legitimate title.

    Applied separately from :func:`normalize_title_case`, and to EVERY title,
    because that function returns early for a mixed-case title — folding inside
    it would silently skip exactly the titles most likely to carry a curly
    apostrophe.
    """
    if not title:
        return title
    return ''.join(_QUOTE_FOLDING.get(ch, ch) for ch in title)


def _close_inline_hyphen_gap(value: str) -> str:
    """Repair PDF text that inserts a space before a joined hyphen.

    ``REAL -TIME`` is printed as ``REAL-TIME``. A space after the hyphen is
    deliberately left alone because it can reflect different source text.
    """
    return re.sub(r'(?<=\w)\s+-(?=\w)', '-', value)


def normalize_title_case(title: str) -> str:
    """Title-case an ALL-CAPS title while preserving known acronyms.

    A mixed-case title is returned untouched — the document's own casing is
    already meaningful and must not be flattened. Only a title that is
    entirely uppercase is normalised, and within it any token whose core
    (punctuation stripped) is a known acronym stays uppercase.

    Replaces a bare ``str.title()`` call, which mangled acronyms:
    ``"(NLP)" -> "(Nlp)"``.

    A token is checked as a WHOLE first, then split on hyphens and slashes so a
    compound like ``"AI-POWERED"`` keeps its acronym part. Whole-token first is
    what makes the existing behaviour byte-identical: a known acronym that
    happens to contain a delimiter is still matched intact before any splitting
    is attempted.
    """
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return title
    if not all(c.isupper() for c in letters):
        return title

    out: list[str] = []
    tokens = title.split(' ')
    first_prefix = tokens[0] if tokens else ''
    prefix_core = first_prefix[:-1] if first_prefix.endswith(':') else ''
    preserve_colon_prefix = (
        len(re.sub(r'[^A-Za-z]', '', prefix_core)) >= 4
        and bool(prefix_core)
        and all(char.isupper() for char in prefix_core if char.isalpha())
    )
    for index, token in enumerate(tokens):
        core = token.strip(_TOKEN_PUNCTUATION)
        if (
            core and core.upper() in _KNOWN_ACRONYMS
        ) or (index == 0 and preserve_colon_prefix):
            out.append(token)
        else:
            out.append(_titlecase_token(token))
    return ' '.join(out)


# Punctuation stripped from a token before looking it up in _KNOWN_ACRONYMS.
# Shared by the whole-token check and the per-part check so the two cannot
# drift to different ideas of what surrounds a word.
_TOKEN_PUNCTUATION = '()[]{}<>.,;:!?"\'“”'

# Delimiters inside a compound token. Captured in the split so the original
# character is preserved on rejoin — 'AI/ML-BASED' must come back with its
# slash and its hyphen exactly where they were, not normalised to one or the
# other.
#
# En and em dashes are deliberately NOT included. In this corpus they appear
# space-separated ("… State University – Main Campus"), so they already split
# into their own tokens and carry no acronym risk. Adding them would change
# behaviour for no benefit.
_COMPOUND_DELIMITERS = re.compile(r'([-/])')


def _titlecase_token(token: str) -> str:
    """Title-case ``token``, preserving known acronyms in hyphen/slash parts.

    ``str.title()`` on a whole compound gives ``'AI-POWERED' -> 'Ai-Powered'``
    because it only capitalises the first letter of each alphabetic run and
    lowercases the rest. Splitting on the delimiters lets each part be looked
    up on its own, so the acronym half survives:

        'AI-POWERED'  -> 'AI-Powered'
        'IOT-BASED'   -> 'IOT-Based'
        'AI/ML'       -> 'AI/ML'
        '(AI-POWERED)'-> '(AI-Powered)'

    Each part is stripped of its own surrounding punctuation before lookup,
    which is what makes the parenthesised form work — the leading '(' belongs
    to the first part, not to the token as a whole.

    Note this PRESERVES the document's casing for a known acronym rather than
    canonicalising it: 'IOT' stays 'IOT' and is not rewritten to 'IoT'. That
    matches the whole-token behaviour above and is a deliberate limit, not an
    oversight — rewriting an acronym's internal casing is a separate decision.
    """

    def titlecase_part(part: str) -> str:
        # str.title() uppercases the letter after an apostrophe, producing
        # "Noah'S" from an all-caps possessive. Folded quotes reach this path
        # as straight apostrophes; preserve acronym stems such as "NLP's".
        possessive = re.fullmatch(
            r"(?P<stem>.+)'S(?P<trailing>[^A-Za-z0-9]*)", part,
        )
        if possessive:
            stem = possessive.group('stem')
            core = stem.strip(_TOKEN_PUNCTUATION)
            titlecased_stem = (
                stem if core and core.upper() in _KNOWN_ACRONYMS
                else stem.title()
            )
            return f"{titlecased_stem}'s{possessive.group('trailing')}"

        core = part.strip(_TOKEN_PUNCTUATION)
        if core and core.upper() in _KNOWN_ACRONYMS:
            return part
        return part.title()

    parts = _COMPOUND_DELIMITERS.split(token)
    if len(parts) == 1:
        return titlecase_part(token)

    out: list[str] = []
    for part in parts:
        # Delimiters come back from re.split as their own single-character
        # entries; pass them through untouched so the rejoin is exact.
        if part in ('-', '/'):
            out.append(part)
            continue
        out.append(titlecase_part(part))
    return ''.join(out)


# ---------------------------------------------------------------------------
# Title detection
# ---------------------------------------------------------------------------

def _score_candidate_line(line: str, nb_idx: int) -> int | None:
    """Score ``line`` as a possible title START, or None if disqualified.

    ``nb_idx`` is the line's index among NON-BLANK lines, preserving the
    original position-based scoring exactly.
    """
    if _noise_key(line) in _SECTION_NOISE:
        return None
    if _TITLE_KEYWORD_LABEL.fullmatch(line):
        return None
    if _CHAPTER_PATTERNS.match(_noise_key(line)):
        return None

    # Judge the line by its PII-stripped form.
    #
    # A line that is ONLY contact details strips to nothing and is rejected, so
    # an email or phone line can never be a title start. But a line whose
    # contact details sit in the TAIL, after a real title, keeps its prefix —
    # which is what makes a single-line page recoverable instead of returning
    # an empty title. The word-count and prose checks below then run against
    # the clean text, so scoring is never influenced by the contact block.
    if _has_contact_details(line):
        line = _strip_pii_tail(line)
        if not line:
            return None

    words = line.split()
    n_words = len(words)

    # (a) A CONTINUATION LINE CANNOT BE A TITLE START.
    #
    # 'CAREER TRACK MOBILE APPLICATION' (4 words) scored 8 and lost to
    # 'USING FUZZY LOGIC FOR HIGH SCHOOL' (6 words) at 9, purely because the
    # longer line earns the 5..15-word bonus below. The join then began on the
    # continuation and the real first line was dropped. A line opening with a
    # connector is by definition a continuation.
    #
    # CARVE-OUT: 'a', 'an' and 'the' are in _CONNECTOR_WORDS but legitimately
    # open titles ('A Web-Based ...', 'An Android Application ...'), so they are
    # excluded from this rule. Verified against all 50 stored titles: none
    # starts with any of the remaining connectors, so nothing real is blocked.
    if words and words[0].lower().strip('.,;:') in _TITLE_START_BLOCKED:
        return None

    # (b) A LONE ACRONYM LINE ENDING IN A COLON IS A VALID TITLE START.
    #
    # Canva colloquium papers put the acronym on its own line:
    #   'MEMOLOOP:' / 'A CUSTOMIZABLE DIGITAL LEARNING' / 'FLASHCARDS FOR ...'
    # The n_words < 3 floor rejected the first line, so five titles lost their
    # acronym prefix — the part a reader notices missing first.
    #
    # Narrow on purpose: ONE token, ending in ':', with an alphanumeric core of
    # 4+ characters. Section labels are filtered first: 'ABSTRACT:' by the
    # chapter pattern and 'Keywords:' by _TITLE_KEYWORD_LABEL.
    is_acronym_start = _is_lone_acronym_start(line)
    short_title_signal = (
        n_words == 2
        and any(
            word.strip('.,;:!?-\'"()[]{}').lower() in _SHORT_TITLE_KEYWORDS
            for word in words
        )
    )

    if not is_acronym_start and not short_title_signal and (
        n_words < 3 or n_words > MAX_TITLE_WORDS
    ):
        return None
    if is_acronym_start and n_words > MAX_TITLE_WORDS:
        return None

    # An author-list entry is never the title.
    #
    # This replaces a guard that did almost nothing:
    #
    #     if n_words <= 3 and not any(c in line for c in (':', '-', 'A', 'An', 'The')):
    #
    # Two independent bugs. ``'A' in line`` is a SUBSTRING test for the single
    # letter A, so any line containing a capital A anywhere satisfied it —
    # 'GONZAGA, KURT ROSS E.' contains two, so the guard was skipped. And the
    # ``n_words <= 3`` ceiling meant that same four-word line never reached the
    # check at all. Between them the guard caught almost nothing.
    #
    # The replacement has no word-count ceiling, because author entries are
    # routinely four or more tokens once initials and suffixes are counted.
    if _looks_like_author_line(line):
        return None

    # The old guard's article clause is NOT revived, deliberately.
    #
    # Implemented correctly — "first word is not a/an/the, three words or
    # fewer, all capitalised, no colon or dash" — it rejects real titles in
    # this corpus: 'Alumni Portal Tracker', 'Web-Based Qualifying Examination'.
    # The broken substring form (``'A' in line``) had been shielding them by
    # accident, since both contain a capital A.
    #
    # Its stated purpose was catching author names, and _looks_like_author_line
    # above now does that with a purpose-built test instead of inferring it
    # from word count and capitalisation. A bare affiliation line could still
    # score, but affiliations in this corpus are covered by _SECTION_NOISE, and
    # the canary titles are authoritative: a wrong-title risk does not justify
    # truncating documented real titles.

    if re.fullmatch(r'[\d/\-,\s]+', line):
        return None

    if _alpha_ratio(line) < MIN_PROSE_ALPHA_RATIO:
        return None

    score = 0
    if nb_idx < 5:
        score += 3
    elif nb_idx < 10:
        score += 2
    elif nb_idx < 20:
        score += 1

    if line.isupper() and n_words >= 4:
        score += 3
    elif line.istitle():
        score += 2
    elif line[0].isupper():
        score += 1

    lowered = line.lower()
    if short_title_signal or any(kw in lowered for kw in _TITLE_KEYWORDS):
        score += 2

    if 5 <= n_words <= 15:
        score += 1

    return score


def _confidence_for(score: int) -> str:
    if score >= 7:
        return 'high'
    if score >= 4:
        return 'medium'
    return 'low'


def _join_title_block(
    lines: list[str],
    start_idx: int,
    has_blank_structure: bool,
) -> str:
    """Join the title block starting at ``lines[start_idx]``.

    Walks forward and stops at the first of:
      * a long blank gap, or a short gap followed by a non-continuation
      * a section heading / chapter heading
      * an author marker ("by", "by:", "submitted by")
      * degree/submission boilerplate ("A Capstone", "Presented to …")
      * MAX_TITLE_WORDS words accumulated

    A continuation gate ALWAYS applies, in one of two strengths:

    * **No blank-line structure** — the strict gate: the line must open with a
      connector word. This is the tighter of the two and is unchanged.
    * **Blank-line structure present** — the relaxed gate: the line must show
      at least one positive sign of being a continuation (see
      :func:`_continues_title`).

    Previously the gate ran ONLY in the no-blank-structure case, so a page
    that had blank lines anywhere joined every non-terminator line
    unconditionally. That is how author names ended up inside titles: the
    blank line separating the title block from the degree boilerplate lower
    down was enough to switch the gate off entirely for the lines in between.
    """
    parts = [lines[start_idx]]
    n_words = len(lines[start_idx].split())
    blank_run = 0

    for nxt in lines[start_idx + 1:]:
        if not nxt:
            blank_run += 1
            # Some PDFs place a blank extractor line between title lines,
            # even though the printed title is visually continuous. Bridge a
            # small gap only; a longer blank run remains a strong block end.
            if blank_run > 2:
                break
            continue
        blank_run = 0
        # Terminators are checked FIRST, so a contact detail or author line is
        # cut even when the relaxed gate below would have admitted it.
        if _TITLE_KEYWORD_LABEL.fullmatch(nxt) or _is_block_terminator(nxt):
            break

        # A summary sentence may repeat the final title line immediately
        # before describing the work. It is not another title fragment.
        if (
            _looks_like_prose_continuation(nxt)
            or _repeats_title_as_prose(nxt, parts[-1])
        ):
            break

        if has_blank_structure:
            if not _continues_title(nxt, parts[-1]):
                break
        else:
            first_word = nxt.split()[0].lower().strip('.,;:')
            if first_word not in _CONNECTOR_WORDS:
                break

        added = len(nxt.split())
        if n_words + added > MAX_TITLE_WORDS:
            break

        # A few PDFs repeat the title in adjacent extracted lines. Compare
        # alphanumeric text without whitespace so small pypdf word-splitting
        # artifacts (for example ``SISTEM A``) still match the clean copy.
        # Keep the version with fewer extracted word fragments.
        previous_key = re.sub(r'[^A-Za-z0-9]', '', parts[-1]).casefold()
        next_key = re.sub(r'[^A-Za-z0-9]', '', nxt).casefold()
        if len(previous_key) >= 12 and previous_key == next_key:
            if len(nxt.split()) < len(parts[-1].split()):
                parts[-1] = nxt
            continue

        parts.append(nxt)
        n_words += added

    return ' '.join(parts)


def _continues_title(line: str, previous: str) -> bool:
    """Relaxed continuation test, used when the page has blank-line structure.

    Any ONE of four signals is enough:

    1. The line opens with a connector word ("FOR RURAL CLINICS").
    2. The line contains title vocabulary ("… MONITORING SYSTEM"). Substring
       matching, consistent with :func:`_score_candidate_line`, so 'SYSTEMS'
       satisfies 'system'.
    3. The PREVIOUS line ends on a connector word. A title line ending in
       "FOR" or "USING" obviously continues, and the next line may carry
       neither a leading connector nor title vocabulary — "… MONITORING
       SYSTEM FOR" / "PUBLIC SENIOR HIGH SCHOOLS" is a real example that
       signals 1 and 2 both miss. A dangling connector is a high-precision
       signal, so this costs almost nothing and prevents a whole class of
       false truncation.
    4. The line is a SINGLE word. An author-list entry cannot be one word —
       :func:`_has_name_shape` requires two to six — so a lone token is never
       a name, while a title's final wrapped line frequently is ("… NATURAL
       LANGUAGE" / "PROCESSING"). A token ending in a comma is excluded, since
       that is a list entry mid-flow rather than a title tail.
    5. The line contains a connector elsewhere, or has the same all-caps or
       title-case style as the preceding fragment.

    A bare author line like "Juan Miguel Santos" satisfies none of these
    and is therefore cut. That pairing is the point: the author-line
    terminator needs a positive personhood marker and so misses a bare
    three-word name, and this gate is what catches it.

    Note on ordering: this runs AFTER ``_is_block_terminator`` in the caller,
    so a contact detail or a marked author line is already gone. Nothing here
    can readmit PII.
    """
    words = line.split()
    if not words:
        return False

    # Do not let a sentence from an abstract/body run-on join merely because
    # it begins with ``The`` or contains a connector. A comma followed by a
    # subject and finite-verb-shaped clause is strong prose evidence, while
    # title fragments in this corpus are noun phrases.
    if (
        _looks_like_prose_continuation(line)
        or _repeats_title_as_prose(line, previous)
    ):
        return False

    if words[0].lower().strip('.,;:') in _CONNECTOR_WORDS:
        return True

    lowered = line.lower()
    if any(keyword in lowered for keyword in _TITLE_KEYWORDS):
        return True

    previous_words = previous.split()
    if previous_words and previous_words[-1].lower().strip('.,;:') in _CONNECTOR_WORDS:
        return True

    if len(words) == 1 and not words[0].endswith(','):
        return True

    # 5. The line contains a connector word somewhere OTHER than the start —
    #    "CENTERS IN MUNICIPALITY", "Crop Recommendations and IoT-Enabled
    #    Solar-Powered Water". A mid-line preposition or conjunction means the
    #    line is a sentence fragment, and a title is the only sentence on a
    #    title page.
    #
    #    Author lines do not satisfy this: 'GONZAGA, KURT ROSS E.',
    #    'Dela Cruz, Juan M.' and 'CRISTOPHER B. AMPA, Don Honorio Ventura
    #    State University' contain no connector. Name PARTICLES ('de', 'la',
    #    'van') are in _NAME_PARTICLES, deliberately not in _CONNECTOR_WORDS,
    #    so a particle cannot admit a name here.
    #
    #    A middle initial 'A.' does normalise to the connector 'a', but such a
    #    line is an author line by the standalone-initial rule and the
    #    terminator removes it before this function is ever reached.
    if any(word.lower().strip('.,;:') in _CONNECTOR_WORDS for word in words):
        return True

    if _same_title_line_style(line, previous):
        return True

    return False


def _same_title_line_style(line: str, previous: str) -> bool:
    """Whether adjacent lines share an all-caps or title-case presentation."""
    def style(value: str) -> str | None:
        letters = [char for char in value if char.isalpha()]
        if letters and all(char.isupper() for char in letters):
            return 'upper'

        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?", value)
        if not words:
            return None
        capitalized = sum(word[0].isupper() for word in words)
        if capitalized / len(words) >= 0.6:
            return 'title'
        return None

    current_style = style(line)
    if current_style is None or current_style != style(previous):
        return False
    # A title-case line made only of ordinary name-shaped words is still more
    # likely an author than a continuation. All-caps title blocks and
    # connector/title-vocabulary signals are handled separately.
    if current_style == 'title' and _has_name_shape(line):
        return False
    return True


def _looks_like_prose_continuation(line: str) -> bool:
    """Recognise a wrapped prose sentence that should end a title block.

    It is intentionally narrow: a long line must start with a sentence
    subject, contain a comma, then continue with a subject/finite-verb clause.
    This avoids rejecting ordinary title phrases while stopping abstract text
    that begins with ``The ...``.
    """
    if len(line.split()) < 7:
        return False
    if not re.match(r'^(?:the|this|these|it|they|we)\b', line, re.IGNORECASE):
        return False
    return bool(re.search(
        r',\s+[A-Za-z][A-Za-z\-]*\s+(?:[A-Za-z]+ed|is|are|was|were|'
        r'has|have|had|does|do|did|can|could|will|would|should)\b',
        line,
        re.IGNORECASE,
    ))


def _repeats_title_as_prose(line: str, previous: str) -> bool:
    """Stop when a summary restates the prior title fragment as a sentence."""
    if len(line.split()) < 16 or len(previous.split()) < 4:
        return False
    if not re.match(r'^(?:the|this|these|it)\b', line, re.IGNORECASE):
        return False
    copula = re.search(
        r'\b(?:is|are|was|were)\s+(?:a|an|the)\b', line, re.IGNORECASE
    )
    if not copula:
        return False
    earlier = re.sub(r'\W+', ' ', line[:copula.start()]).strip().casefold()
    fragment = re.sub(r'\W+', ' ', previous).strip().casefold()
    return bool(fragment and fragment in earlier)


def detect_title(text: str) -> tuple[str, str]:
    """Detect the thesis title from raw extracted document text.

    Returns ``(title, confidence)`` where confidence is ``'high'``,
    ``'medium'`` or ``'low'``. This is the exact return contract the
    ``/theses/extract-title/`` endpoint already relies on.
    """
    if not text:
        return '', 'low'

    # Normalise whitespace WITHIN lines but preserve blank-line POSITIONS —
    # blank lines are the primary title-block boundary and must survive.
    lines = [collapse_whitespace(raw) for raw in text.split('\n')]
    non_blank = [line for line in lines if line]
    if not non_blank:
        return '', 'low'

    # A document whose front matter opens with a chapter heading has no title
    # page; cap confidence regardless of how well a line scores. Evaluated on
    # non-blank lines so blank-line preservation doesn't shift the window.
    document_is_chapter_only = any(
        _CHAPTER_PATTERNS.match(line) for line in non_blank[:6]
    )

    has_blank_structure = _has_interior_blank(lines)

    best_idx = -1
    best_score = -1
    best_confidence = 'low'

    nb_idx = -1
    in_keyword_section = False
    keyword_section_value_seen = False
    previous_line = ''
    previous_chain_start_idx = -1
    blank_gap = 0
    for raw_idx, line in enumerate(lines):
        if not line:
            blank_gap += 1
            if blank_gap > 2:
                previous_line = ''
                previous_chain_start_idx = -1
            if keyword_section_value_seen:
                in_keyword_section = False
                keyword_section_value_seen = False
            continue
        blank_gap = 0
        nb_idx += 1
        if nb_idx >= MAX_CANDIDATE_LINES:
            break
        if _TITLE_KEYWORD_LABEL.fullmatch(line):
            in_keyword_section = True
            keyword_section_value_seen = bool(
                re.search(r'[:\-\u2013\u2014]\s*\S', line)
            )
            previous_line = ''
            previous_chain_start_idx = -1
            continue
        if in_keyword_section:
            keyword_section_value_seen = True
            previous_line = ''
            previous_chain_start_idx = -1
            continue
        score = _score_candidate_line(line, nb_idx)
        continues_previous = bool(
            previous_line
            and previous_chain_start_idx >= 0
            and not _is_block_terminator(line)
            and not _looks_like_prose_continuation(line)
            and not _repeats_title_as_prose(line, previous_line)
            and (
                _continues_title(line, previous_line)
                or _same_title_line_style(line, previous_line)
            )
        )

        if score is not None:
            if continues_previous:
                # A stronger continuation line must not replace the actual
                # start of a title. It may still support the confidence of
                # the same block, and the join below will include it.
                if previous_chain_start_idx == best_idx and score > best_score:
                    best_score = score
                    best_confidence = _confidence_for(score)
            elif score > best_score:
                best_score = score
                best_idx = raw_idx
                best_confidence = _confidence_for(score)

        if not continues_previous:
            previous_chain_start_idx = raw_idx if score is not None else -1
        previous_line = line

    if best_idx < 0:
        return '', 'low'

    # A one-token brand/acronym immediately above a title body is often part
    # of the title even when the longer body line scores higher. Walk backward
    # only across a short, uninterrupted continuation chain so labels and
    # unrelated front matter cannot be pulled into the title.
    title_start_idx = best_idx
    cursor = best_idx - 1
    steps = 0
    while cursor >= 0 and lines[cursor] and steps < 3:
        if (
            _is_lone_acronym_start(lines[cursor])
            and _score_candidate_line(lines[cursor], 0) is not None
        ):
            title_start_idx = cursor
            break
        if not _continues_title(lines[cursor + 1], lines[cursor]):
            break
        cursor -= 1
        steps += 1

    title = _join_title_block(lines, title_start_idx, has_blank_structure)
    # Final scrub before casing. Every line-based defence above can be bypassed
    # by an extractor that emits the page as one line; this cannot.
    title = _strip_pii_tail(collapse_whitespace(title))
    title = _close_inline_hyphen_gap(fold_quotes(title))
    title = normalize_title_case(title)

    if document_is_chapter_only and best_confidence in ('high', 'medium'):
        best_confidence = 'low'

    return title, best_confidence


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------

# The modal's textarea enforces minLength={20}; anything shorter would be
# auto-filled only to be rejected on submit, so treat it as "not found".
MIN_ABSTRACT_CHARS = 20

# Abstracts run ~150-300 words. 6000 characters is well past that, and caps
# the damage if a stop heading is missing and the walk runs into Chapter I.
MAX_ABSTRACT_CHARS = 6000

# A real abstract is 150-300 words, so a 20-word floor has ample headroom
# while rejecting a table-of-contents remainder — "viii" is one word.
#
# This is strictly stricter than MIN_ABSTRACT_CHARS, so the character floor
# stops binding in practice. Both are kept: the character floor documents the
# form's own minLength={20} contract, this one documents "is it prose".
MIN_ABSTRACT_WORDS = 20

# "ABSTRACT" as its own line, optionally followed by the abstract's first
# sentence on the same line (some templates typeset it as a run-in heading).
_ABSTRACT_HEADING = re.compile(r'^abstract\b\s*[:\.\-—]?\s*(.*)$', re.IGNORECASE)

# A run of three or more of the SAME punctuation character. This is how dot
# leaders are recognised without enumerating glyphs: "....", "………", "···",
# "---" and anything else a PDF extractor invents all collapse to this one
# shape. Enumerating leader characters is unbounded — the previous guard only
# knew about ASCII periods and let an ellipsis row through into the form.
_LEADER_RUN = re.compile(r'([^\w\s])\1{2,}')

# A strict roman numeral, so ordinary words are not mistaken for page numbers.
# Loose "[ivxlcdm]+" matches "did" and "mill"; this pattern does not.
_ROMAN_NUMERAL = (
    r'(?=[ivxlcdm])m*(?:c[md]|d?c{0,3})(?:x[cl]|l?x{0,3})(?:i[xv]|v?i{0,3})'
)

# A trailing page number, arabic or roman, as its own token: the tail of every
# table-of-contents row.
_TRAILING_PAGE_NUMBER = re.compile(
    rf'(?:^|\s)(?:\d{{1,4}}|{_ROMAN_NUMERAL})\s*\.?\s*$',
    re.IGNORECASE,
)

# The "TABLE OF CONTENTS" heading that opens the contents listing.
_TOC_HEADING = re.compile(
    r'^(table\s+of\s+contents|contents)\s*[:\.\-—]?\s*$',
    re.IGNORECASE,
)


def _looks_like_toc_row(value: str) -> bool:
    """True when ``value`` looks like a table-of-contents entry, not prose.

    Three independent signals, any of which is sufficient:

      1. a run of repeated punctuation (a dot leader, whatever glyph it uses)
      2. a trailing page number, arabic or roman
      3. an alphabetic ratio below :data:`MIN_PROSE_ALPHA_RATIO`

    Deliberately character-agnostic. (2) can in principle fire on prose that
    ends on a word which happens to be a valid roman numeral ("…in the mix"),
    but this only ever runs against a heading line's trailing remainder, and
    the prose test applied to the assembled abstract body is the real
    safeguard — the cost of a false positive here is a blank field the user
    fills in, not a wrong value that gets published.
    """
    if not value:
        return False
    if _LEADER_RUN.search(value):
        return True
    if _TRAILING_PAGE_NUMBER.search(value):
        return True
    return _alpha_ratio(value) < MIN_PROSE_ALPHA_RATIO

# Headings that always come after an abstract and therefore end it.
_ABSTRACT_STOP = re.compile(
    r'^(?:keyword\s*/\s*s|keywords?|key\s*words?|index\s+terms?)'
    r'(?:\s*[:\-—]\s*|\s*$)'
    r'|^(table\s+of\s+contents|list\s+of\s+(figures|tables|appendices)|'
    r'acknowledge?ments?|acknowledgment|dedication|preface|'
    r'chapter\s+[ivxlcdm\d]+|introduction|references|bibliography|'
    r'appendix|the\s+problem\s+and\s+its\s+background)\b',
    re.IGNORECASE,
)


def detect_abstract(text: str) -> tuple[str, str]:
    """Extract the abstract body that follows an "ABSTRACT" heading.

    Returns ``(abstract, confidence)``, or ``('', 'low')`` when the document
    has no abstract heading. Not every thesis does — the real THESYS+ document
    in this repository has none — and inventing one from the first paragraph of
    Chapter I would be worse than leaving the field for the user to fill.

    Line wrapping is undone (``pypdf`` breaks every ~80 characters) while
    paragraph breaks are preserved as blank lines, and end-of-line hyphenation
    is rejoined.

    Table-of-contents rows are rejected on three independent layers, because a
    row like "ABSTRACT ......... viii" otherwise reads as a run-in heading and
    its dot leaders land in the form:

      1. the contents region itself is skipped (see below),
      2. any candidate heading whose remainder looks like a contents row is
         passed over rather than accepted,
      3. the assembled body must look like prose before it is returned.

    Layer 1 is what makes a document that BOTH lists ABSTRACT in its contents
    AND has a real abstract section resolve to the real one; without it the
    contents row is found first and the search stops there.
    """
    if not text:
        return '', 'low'

    lines = [collapse_whitespace(raw) for raw in text.split('\n')]

    start = -1
    inline_remainder = ''
    in_toc = False
    for idx, line in enumerate(lines):
        if not line:
            continue

        # Skip the contents listing wholesale. It opens at the "TABLE OF
        # CONTENTS" heading and ends at the first line that is not itself a
        # contents row — which is exactly where a real "ABSTRACT" section
        # heading would sit, so the real heading still terminates the region
        # and gets evaluated normally.
        if _TOC_HEADING.match(line):
            in_toc = True
            continue
        if in_toc:
            if _looks_like_toc_row(line):
                continue
            in_toc = False

        match = _ABSTRACT_HEADING.match(line)
        if not match:
            continue
        # A line merely *containing* the word (e.g. "Abstract screening was
        # performed…") is excluded by requiring the line to START with it.
        remainder = match.group(1).strip()
        if _looks_like_toc_row(remainder):
            continue
        start = idx
        inline_remainder = remainder
        break

    if start < 0:
        return '', 'low'

    paragraphs: list[list[str]] = []
    current: list[str] = [inline_remainder] if inline_remainder else []
    blank_run = 0

    for line in lines[start + 1:]:
        if not line:
            blank_run += 1
            # A single blank is a paragraph break inside the abstract; three
            # in a row means the block is over (end of page / section gap).
            if blank_run >= 3 and (current or paragraphs):
                break
            if current:
                paragraphs.append(current)
                current = []
            continue
        blank_run = 0
        # Numbered headings such as "1.INTRODUCTION" are not covered by the
        # unnumbered stop pattern. Require the whole line to be a heading so
        # citations and ordinary prose mentioning a section stay in the body.
        if _ABSTRACT_STOP.match(line) or _NUMBERED_BODY_HEADING.fullmatch(line):
            break
        current.append(line)
        if sum(len(' '.join(p)) for p in paragraphs) + len(' '.join(current)) > MAX_ABSTRACT_CHARS:
            break

    if current:
        paragraphs.append(current)

    joined = '\n\n'.join(_join_wrapped_lines(p) for p in paragraphs if p).strip()
    joined = _close_inline_hyphen_gap(joined)
    joined = joined[:MAX_ABSTRACT_CHARS].strip()

    if len(joined) < MIN_ABSTRACT_CHARS:
        return '', 'low'

    # Positive prose test — the layer that does not care which glyph a dot
    # leader used. A leader row scores ~0.08 alphabetic and one word; prose
    # scores ~0.8 and well over twenty. Anything failing this is not an
    # abstract, so return the not-found result rather than a wrong value.
    if _alpha_ratio(joined) < MIN_PROSE_ALPHA_RATIO:
        return '', 'low'
    if len(joined.split()) < MIN_ABSTRACT_WORDS:
        return '', 'low'

    # A real abstract is a substantial block of prose. A short one is more
    # likely a stray heading match, so hand it over with less certainty.
    confidence = 'high' if len(joined) >= 200 else 'medium'
    return joined, confidence


def _join_wrapped_lines(lines: list[str]) -> str:
    """Rejoin PDF-wrapped lines into a single paragraph.

    Reverses end-of-line hyphenation ("develop-\\nment" -> "development")
    only when the next line starts lowercase, so a genuine trailing hyphen in
    "Web-\\nBased" style headings is not silently welded together wrongly.
    """
    out = ''
    for line in lines:
        if not out:
            out = line
            continue
        if out.endswith('-') and line[:1].islower():
            out = out[:-1] + line
        else:
            out = f'{out} {line}'
    return collapse_whitespace(out)


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

MAX_KEYWORDS = 15
MAX_KEYWORD_CHARS = 64

# Requires an explicit label AND a separator. "keywords, contextual meanings"
# — a real sentence fragment inside this corpus' body text — must NOT match,
# which is why ',' is deliberately absent from the separator class.
_KEYWORDS_LABEL = re.compile(
    # 'keyword/s' is listed FIRST: alternation is first-match-wins, so
    # 'keywords?' would otherwise consume 'Keyword' and leave '/s:' behind as
    # the value.
    r'^(keyword\s*/\s*s|keywords?|key\s*words?|index\s+terms?)\s*[:\-—]\s*(.*)$',
    re.IGNORECASE,
)

# The separator-OPTIONAL form, used ONLY by detect_keywords.
#
# WHY THIS IS SEPARATE FROM _KEYWORDS_LABEL.
# Two reasons, both about blast radius:
#
#   * _KEYWORDS_LABEL is imported read-only by thesis_document_check (the
#     keywords gate marker) and consulted by detect_abstract's stop pattern.
#     Making the separator optional THERE would change which documents clear
#     the upload gate, which is not this round's business.
#   * A comma must never be accepted as the separator. The corpus contains real
#     body sentences that open with the word:
#         'keywords, contextual meanings, and topic, improving efficiency ...'
#         'keywords, authors, advisors, and academic year. The system must ...'
#     Neither branch below can match those: ',' is not in the separator class,
#     is not whitespace, and is not end-of-line.
#
# CAPITALISATION IS REQUIRED, and it is the load-bearing guard. Measured on the
# corpus: 12 separator-less label lines are Capitalised or ALL CAPS and every
# one is a genuine keyword label; 18 are lowercase and every one is wrapped body
# prose ('keywords' alone on a line, continuing a sentence). Without the case
# requirement the optional separator would read those 18 as labels.
_KEYWORDS_LABEL_LOOSE = re.compile(
    r'^(?:Keyword\s*/\s*s|KEYWORD\s*/\s*S|Keywords?|Key\s*Words?|'
    r'KEYWORDS?|KEY\s*WORDS?|'
    r'Index\s+Terms?|INDEX\s+TERMS?)'
    r'(?:\s*[:\-—]\s*|\s+|\s*$)'
    r'(.*)$',
)

_KEYWORD_SPLIT = re.compile(r'[;,·•|]+')
_KEYWORD_NUMBERED_SECTION = re.compile(
    r'^\s*\d+(?:\.\d+)*\.?\s*'
    r'(?:introduction|references|bibliography|appendix)\b',
    re.IGNORECASE,
)

# A loose label has less evidence than an explicit ``Keywords:`` label, and a
# continuation line must look like another list fragment. These cues prevent
# sentence clauses from being folded into the final keyword while still
# accepting wrapped lists (including a keyword moved after a trailing comma).
_KEYWORD_PROSE_SUBJECT = re.compile(
    r'^(?:the|this|these|those|it|they|we|our|their|study|research|'
    r'results?|findings?|students?|researchers?|participants?|respondents?)\b',
    re.IGNORECASE,
)
_KEYWORD_PROSE_VERB = re.compile(
    r'\b(?:am|is|are|was|were|be|been|being|has|have|had|do|does|did|'
    r'can|could|will|would|should|must|may|might|shall|supports|supported|'
    r'tracks|tracked|reports|reported|improves|improved|provides|provided|'
    r'uses|used|includes|included|focuses|focused|examines|examined|'
    r'investigates|investigated|develops|developed|presents|presented|'
    r'describes|described|discusses|discussed|suggests|suggested)\b',
    re.IGNORECASE,
)
_KEYWORD_PROSE_OPENING = re.compile(
    r'^(?:are|is|was|were|has|have|had|do|does|did|can|could|will|'
    r'would|should|must|may|might|shall)\b',
    re.IGNORECASE,
)


def _looks_like_keyword_prose(line: str) -> bool:
    """True when a candidate list fragment has a sentence-like clause."""
    if _KEYWORD_PROSE_OPENING.match(line):
        return True
    if (
        _KEYWORD_PROSE_SUBJECT.match(line)
        and _KEYWORD_PROSE_VERB.search(line)
    ):
        return True
    # A short complete sentence can start with an ordinary noun ("Technology
    # improves access, and supports students.") rather than one of the common
    # pronouns above. Do not mistake its comma for a keyword delimiter.
    if (
        len(line.split()) >= 6
        and _KEYWORD_PROSE_VERB.search(line)
        and line.rstrip().endswith(('.', '?', '!'))
    ):
        return True
    # A longer, punctuated sentence can begin with a transition ("Moreover,"
    # or "In addition,") and evade the subject-at-start cues above. When it
    # carries a recognised verb, the preceding branch catches it. Do not use
    # this broad length-only fallback on delimiter-separated lists: a valid
    # list such as the iSecure DOCX line has 13 words and a final period.
    return (
        len(line.split()) >= 8
        and line.rstrip().endswith(('.', '?', '!'))
        and not _KEYWORD_SPLIT.search(line)
    )


def _looks_like_keyword_continuation(line: str, previous_line: str) -> bool:
    """Only continue a keyword list across list-shaped or visibly wrapped text."""
    if _looks_like_keyword_prose(line):
        return False
    if _KEYWORD_SPLIT.search(line):
        return True
    return bool(re.search(r'[;,·•|]\s*$', previous_line))


def _looks_like_wrapped_keyword_tail(
    line: str,
    previous_line: str = '',
) -> bool:
    """Recognize a short final keyword phrase split across a physical line.

    Some PDFs wrap the final item without carrying a comma to the next line:
    ``Geofencing`` / ``Technology`` and ``Learning`` / ``and Memorizing
    Information``. This intentionally accepts only a single-word tail or a
    short conjunction-led phrase. A sentence-like line is rejected first so
    ordinary body prose cannot be appended to the list.
    """
    if not line or _looks_like_keyword_prose(line) or _KEYWORD_SPLIT.search(line):
        return False

    words = line.split()
    if len(words) == 1:
        token = words[0].strip('.,;:!?()[]{}')
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9'’\-]*", token))

    if (
        2 <= len(words) <= 4
        and words[0].lower() in {'and', 'or'}
        and not _KEYWORD_PROSE_VERB.search(line)
        and not line.rstrip().endswith(('.', '?', '!'))
    ):
        return True

    # A final phrase can wrap without carrying a comma onto the next physical
    # line: ``Water`` / ``Level Monitoring.``. Accept only a short, title-like
    # continuation of the final one-word item in an already delimited list.
    if (
        not previous_line
        or not _KEYWORD_SPLIT.search(previous_line)
        or not 2 <= len(words) <= 3
    ):
        return False
    previous_tail = _KEYWORD_SPLIT.split(previous_line)[-1].strip()
    if len(previous_tail.split()) != 1:
        return False
    if words[0].lower().strip('.,;:!?()[]{}') in {
        'a', 'an', 'the', 'this', 'that', 'these', 'those', 'it', 'we',
        'our', 'in', 'on', 'at', 'for', 'with',
    }:
        return False
    return all(
        (core := word.strip('.,;:!?()[]{}'))
        and (core[0].isupper() or core.isupper() or any(ch.isdigit() for ch in core))
        for word in words
    )


def _is_keyword_block_terminator(line: str) -> bool:
    """Stop at structural text or a real author line without rejecting lists.

    The title detector's broader block terminator treats comma-rich lines as
    possible surname/given-name entries. Keyword phrases also use commas, so
    exempt clearly list-shaped lines unless a standalone initial still marks
    the line as an author entry.
    """
    if _is_non_title_boilerplate(line):
        return True
    if not _looks_like_author_line(line):
        return False

    separator_count = len(_KEYWORD_SPLIT.findall(line))
    has_standalone_initial = any(
        _STANDALONE_INITIAL.fullmatch(token) for token in line.split()
    )
    first_fragment = _KEYWORD_SPLIT.split(line, maxsplit=1)[0]
    first_words = first_fragment.split()
    first_word = (
        first_words[0].strip('.,;:!?()[]{}').lower() if first_words else ''
    )
    if (
        not has_standalone_initial
        and (
            separator_count >= 2
            or first_word in _TITLE_KEYWORDS
        )
    ):
        return False
    return True


def _keyword_continuation_overrides_weak_author(
    line: str,
    previous_line: str,
) -> bool:
    """Prefer a clearly continued labeled list over a weak surname-comma hit.

    A few real lists wrap as ``... Dogs,`` / ``Cats, Mabalacat City`` or
    ``... Agile`` / ``Software Development Methodology, Web-based Approach``.
    Those fragments resemble surname-comma-given names to the title helper.
    Strong author markers (initials, honorifics, suffixes) still stop the list.
    """
    if (
        not _KEYWORD_SPLIT.search(line)
        or _looks_like_keyword_prose(line)
    ):
        return False

    tokens = line.split()
    has_strong_author_marker = any(
        _STANDALONE_INITIAL.fullmatch(token.rstrip(','))
        or token.rstrip(',.').lower() in _GENERATIONAL_SUFFIXES
        or token.rstrip(',.').lower() in _HONORIFICS
        for token in tokens
    )
    if has_strong_author_marker:
        return False

    if re.search(r'[;,·•|]\s*$', previous_line) and len(tokens) >= 3:
        return True

    previous_delimiters = len(_KEYWORD_SPLIT.findall(previous_line))
    fragments = _KEYWORD_SPLIT.split(line)
    return (
        previous_delimiters >= 2
        and len(fragments) >= 2
        and all(len(fragment.split()) >= 2 for fragment in fragments[:2])
    )


def _looks_like_single_keyword_token(line: str) -> bool:
    """Recognize a one-token item beneath a bare label, without prose guesses."""
    token = line.strip(' .;:!?()[]{}')
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9'’\-]*", token):
        return False
    # A bare label followed by ordinary title-case prose like "The study..."
    # is ambiguous. A single all-caps/mixed-case token (e.g. CyberEscape) is
    # sufficiently label-like to retain as one medium-confidence item.
    return token.isupper() or any(char.isupper() for char in token[1:])


def _is_keyword_section_stop(line: str) -> bool:
    """Recognize abstract stops plus numbered headings seen in the PDFs."""
    return bool(
        _ABSTRACT_STOP.match(line)
        or _CHAPTER_PATTERNS.match(_noise_key(line))
        or _KEYWORD_NUMBERED_SECTION.match(line)
    )


def detect_keywords(text: str) -> tuple[list[str], str]:
    """Extract the keyword list from a labelled "Keywords:" line.

    Returns ``(keywords, confidence)``. Only an explicit label is trusted;
    there is no fallback to term-frequency guessing, because a plausible-looking
    but wrong keyword set is harder for a user to notice than an empty field.
    """
    if not text:
        return [], 'low'

    lines = [collapse_whitespace(raw) for raw in text.split('\n')]

    raw_value = ''
    value_line_idx: int | None = None
    for idx, line in enumerate(lines):
        # STRICT first, so explicit labels retain priority, including
        # case-insensitive 'Key words:'. The capitalisation-gated LOOSE pattern
        # only gets a say on separator-less shapes.
        strict_match = _KEYWORDS_LABEL.match(line)
        match = strict_match or _KEYWORDS_LABEL_LOOSE.match(line)
        if not match:
            continue
        raw_value = match.group(2 if strict_match else 1).strip()
        value_line_idx = idx

        # Separator-less inline forms are inherently ambiguous. The corpus'
        # ACM-style forms carry a real list delimiter; require one and reject
        # clear sentence clauses so ordinary prose cannot become a keyword set.
        if raw_value and (
            (not strict_match and not _KEYWORD_SPLIT.search(raw_value))
            or _looks_like_keyword_prose(raw_value)
        ):
            raw_value = ''
            break

        # ACM house style puts the label on a line of its own and the list on
        # the NEXT line. This is the largest failing group in the corpus — 9 of
        # the 12 label-shape failures — so an empty remainder is not "no
        # keywords", it is "look one line down".
        #
        # Bounded deliberately: ONE line, it must not be a heading or block
        # terminator, and it must actually look like a list (carry a separator).
        # The separator requirement is what stops a bare label in body prose
        # from swallowing the sentence that follows it.
        if not raw_value:
            for nxt_idx in range(idx + 1, len(lines)):
                nxt = lines[nxt_idx]
                if not nxt:
                    continue
                if (
                    _is_keyword_section_stop(nxt)
                    or _is_keyword_block_terminator(nxt)
                ):
                    break
                if _noise_key(nxt) in _SECTION_NOISE:
                    break
                if _looks_like_keyword_prose(nxt):
                    break
                if not _KEYWORD_SPLIT.search(nxt):
                    if not _looks_like_single_keyword_token(nxt):
                        break
                raw_value = nxt
                value_line_idx = nxt_idx
                break

        if not raw_value:
            break

        # Keyword lists wrap onto following lines. Continue only while the
        # next line carries a list delimiter, or the previous line ends with a
        # delimiter that visibly moved the next keyword onto its own line.
        previous_line = lines[value_line_idx] if value_line_idx is not None else line
        first_continuation_idx = (
            value_line_idx if value_line_idx is not None else idx
        ) + 1
        cursor = first_continuation_idx
        blank_wrap_pending = False
        partial_tail = False
        while cursor < len(lines):
            nxt = lines[cursor]
            if not nxt:
                # Some two-column PDF text layers insert a blank between a
                # delimiter-led wrapped fragment ("Social") and its final
                # word ("Media"). Bridge at most one such blank and only when
                # the next line has the shape of a wrapped keyword tail.
                if (
                    not blank_wrap_pending
                    or cursor + 1 >= len(lines)
                    or not _looks_like_wrapped_keyword_tail(
                        lines[cursor + 1], previous_line,
                    )
                ):
                    break
                cursor += 1
                nxt = lines[cursor]
            if _is_keyword_section_stop(nxt):
                break
            if _noise_key(nxt) in _SECTION_NOISE:
                break

            is_continuation = _looks_like_keyword_continuation(nxt, previous_line)
            is_wrapped_tail = _looks_like_wrapped_keyword_tail(nxt, previous_line)
            if (
                _is_keyword_block_terminator(nxt)
                and not _keyword_continuation_overrides_weak_author(
                    nxt, previous_line,
                )
            ):
                break
            if not is_continuation and not is_wrapped_tail:
                break

            prior_ends_with_delimiter = bool(
                re.search(r'[;,·•|]\s*$', previous_line)
            )
            if is_wrapped_tail and len(nxt.split()) == 1:
                fragment = nxt.strip(' .;:!?()[]{}')
                if re.fullmatch(r'[A-Z][a-z]?', fragment):
                    partial_tail = True
            raw_value = f'{raw_value} {nxt}'
            blank_wrap_pending = (
                prior_ends_with_delimiter and not _KEYWORD_SPLIT.search(nxt)
            )
            previous_line = nxt
            cursor += 1
        break

    if not raw_value:
        return [], 'low'

    seen: set[str] = set()
    keywords: list[str] = []
    for chunk in _KEYWORD_SPLIT.split(raw_value):
        item = _close_inline_hyphen_gap(collapse_whitespace(chunk).strip(' .;:'))
        if not item or len(item) > MAX_KEYWORD_CHARS:
            continue
        if not any(ch.isalpha() for ch in item):
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(item)
        if len(keywords) >= MAX_KEYWORDS:
            break

    if not keywords:
        return [], 'low'

    # A single item usually means the separators were lost in extraction, so
    # the split is suspect even though the label was explicit.
    visibly_truncated = bool(
        re.search(r'(?:[;,·•|]\s*|\.{2,}\s*|…\s*)$', raw_value)
    )
    confidence = (
        'high'
        if len(keywords) >= 3 and not visibly_truncated and not partial_tail
        else 'medium'
    )
    return keywords, confidence


# ---------------------------------------------------------------------------
# Year
# ---------------------------------------------------------------------------

# Matches the DB CheckConstraint's lower bound (theses_year_range_check).
MIN_YEAR = 1980

# Lines from the top of the document treated as "title page region". The
# submission date lives here; years mentioned in body text must not compete
# with it. 60 lines covers a title page plus its overflow comfortably.
TITLE_PAGE_LINES = 60

_MONTH_YEAR = re.compile(
    r'\b(january|february|march|april|may|june|july|august|september|'
    r'october|november|december)\s+(\d{4})\b',
    re.IGNORECASE,
)
_BARE_YEAR = re.compile(r'\b(19\d{2}|20\d{2})\b')
_CITATION_YEAR_INTRODUCER = re.compile(r'\baccording\s+to\b', re.IGNORECASE)
_ABSTRACT_SECTION_HEADING = re.compile(r'^\s*abstract\b', re.IGNORECASE)
_NUMBERED_BODY_HEADING = re.compile(
    r'^\s*\d+(?:\.\d+)*\.?\s*'
    r'(?:abstract|introduction|chapter\s+[ivxlcdm\d]+|methodology|'
    r'results\s+and\s+discussion|conclusion|references|bibliography|appendix)\b',
    re.IGNORECASE,
)

# Legislation references — "Act of 2000", "Act No. 10175". The year names the
# statute, not the thesis.
_STATUTE_BEFORE_YEAR = re.compile(r'\bact\s+(?:of|no\.?)\s*$', re.IGNORECASE)

# Words that explicitly introduce a date, so the year following one is a date
# even mid-sentence: 'academic year 2021', 'S.Y. 2024-2025', 'Batch 2021'.
_DATE_WORD_BEFORE_YEAR = re.compile(
    r'\b(?:academic\s+year|school\s+year|year|s\.?\s*y\.?|a\.?\s*y\.?|'
    r'batch|class\s+of|copyright|\u00a9)\s*[:\-]?\s*$',
    re.IGNORECASE,
)

# A submission year sits at the END of its line on a title page ("Bacolor,
# Pampanga  May 2025", "S.Y. 2024-2025"). Trailing punctuation is allowed.
_YEAR_AT_LINE_END = re.compile(r'^[\s\.,;:\)\]\-–—]*$')


def _is_incidental_year_context(line: str, start: int, end: int) -> bool:
    """True when a year span in this line is not a submission date.

    Measured against the real corpus: every wrong year the bare-year fallback
    produced came from one of these shapes, and none came from a title-page
    date. The four shapes actually observed were

      * an inline citation — '(BLS, 2021)', 'Ranada (2020)', 'Prevention, 2021)'
      * a statute — 'E-Commerce Act of 2000'
      * a POSTAL CODE — 'Bacolor, Pampanga 2001 Philippines'
      * a student-number fragment — '2020@dhvsu.edu.ph'

    so this rejects all four rather than citations alone.
    """
    before, after = line[:start], line[end:]

    # POSITIVE EXEMPTION, checked first: an explicit date word immediately
    # before the year makes it a date however deep in the sentence it sits —
    # 'academic year 2021 requirements', 'S.Y. 2024', 'Batch 2021'. None of the
    # corpus' wrong years carry one of these, so this costs no precision.
    if _DATE_WORD_BEFORE_YEAR.search(before):
        return False

    # Line-wrapped citations can leave a statistic's year at the very end of
    # the extracted line (for example, "According to the PSA 2017"), making it
    # look like a date despite the following line continuing the citation.
    if _CITATION_YEAR_INTRODUCER.search(before):
        return True

    # Part of a longer identifier: '20201017', '2020@dhvsu.edu.ph'.
    if before[-1:].isalnum() or after[:1].isalnum() or after[:1] == '@':
        return True
    # Inside parentheses, or closing one: '(… 2021)' / '2021)'.
    if before.rfind('(') > before.rfind(')') or after[:1] == ')':
        return True
    # Citation comma directly before the year: ', 2021'.
    if re.search(r',\s*$', before):
        return True
    # Statute reference.
    if _STATUTE_BEFORE_YEAR.search(before):
        return True
    # Anything still mid-sentence is not a date line. A postal code followed by
    # a country name ('Pampanga 2001 Philippines') is caught here, and so is
    # every remaining prose mention.
    if not _YEAR_AT_LINE_END.match(after):
        return True
    return False


def _is_incidental_year(line: str, match: 're.Match[str]') -> bool:
    """True when this bare-year occurrence is not a submission date."""
    return _is_incidental_year_context(line, *match.span(1))


def max_year() -> int:
    """Upper bound for an acceptable year: next calendar year.

    Theses are dated by defence year, and a document submitted in December
    is routinely dated the following year, so ``+1`` is legitimate. Anything
    beyond that is a page number, a phone fragment, or an OCR artifact.
    """
    return date.today().year + 1


def detect_year(text: str) -> tuple[int | None, str]:
    """Detect the submission year from the title page region.

    Returns ``(year, confidence)`` with ``None`` when nothing plausible is
    found. A "May 2026" style date is the strongest signal; a bare year on
    its own line is next; any other in-range 4-digit number is weakest and
    the largest such value wins, since front matter cites earlier years
    (curriculum dates, prior work) but is dated by the latest one.
    """
    if not text:
        return None, 'low'

    lines = [collapse_whitespace(raw) for raw in text.split('\n') if collapse_whitespace(raw)]
    title_page_lines = lines[:TITLE_PAGE_LINES]
    for index, line in enumerate(title_page_lines):
        if (
            _CHAPTER_PATTERNS.match(_noise_key(line))
            or _ABSTRACT_STOP.match(line)
            or _ABSTRACT_SECTION_HEADING.match(line)
            or _NUMBERED_BODY_HEADING.match(line)
        ):
            title_page_lines = title_page_lines[:index]
            break

    # Abstract and section text can occur on the same extracted PDF page as
    # the title and authors. Stop at its heading so body dates cannot compete
    # with a genuine date printed in the title block.
    window = '\n'.join(title_page_lines)
    upper = max_year()

    def in_range(value: int) -> bool:
        return MIN_YEAR <= value <= upper

    month_years: list[int] = []
    for match in _MONTH_YEAR.finditer(window):
        value = int(match.group(2))
        if not in_range(value):
            continue

        # A month/year is strong evidence only when its surrounding line also
        # looks date-shaped. This removes parenthesized citations and inline
        # prose while retaining standalone dates and title-page address/date
        # lines. Context is evaluated within the existing bounded scan.
        line_start = window.rfind('\n', 0, match.start())
        line_start = 0 if line_start < 0 else line_start + 1
        line_end = window.find('\n', match.end())
        line_end = len(window) if line_end < 0 else line_end
        line = window[line_start:line_end]
        year_start = match.start(2) - line_start
        year_end = match.end(2) - line_start
        if _is_incidental_year_context(line, year_start, year_end):
            continue
        month_years.append(value)

    if month_years:
        return max(month_years), 'high'

    for line in title_page_lines:
        if re.fullmatch(r'(19\d{2}|20\d{2})', line) and in_range(int(line)):
            return int(line), 'high'

    # Weakest tier. Scanned PER LINE rather than over the joined window so each
    # occurrence can be judged in context, and every occurrence that is
    # incidental — a citation, a statute, a postal code, a student number — is
    # discarded before the maximum is taken.
    #
    # WHY THIS TIER NOW RETURNS EMPTY MORE OFTEN, DELIBERATELY.
    # A full-corpus audit found this tier answered 16 times: 12 WRONG and 4
    # right. All 16 came from citation-shaped context, and the 4 right ones were
    # right only because a cited year happened to equal the submission year.
    # That is a coin flip, not a signal. Returning EMPTY at 'low' is strictly
    # better than a value at 'medium': the upload modal pre-fills year with the
    # current year, which a user notices and corrects, whereas a confident
    # '2000' reads as deliberate. The 'medium' label was also the least accurate
    # band in the whole extractor, and these years were most of it.
    candidates: list[int] = []
    for line in title_page_lines:
        for match in _BARE_YEAR.finditer(line):
            value = int(match.group(1))
            if not in_range(value):
                continue
            if _is_incidental_year(line, match):
                continue
            candidates.append(value)

    if candidates:
        return max(candidates), 'medium'

    return None, 'low'


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------

# The EXACT strings accepted by theses.models.Program. Duplicated here on
# purpose so this module stays importable without Django's app registry;
# test_metadata_fields.py asserts this set equals ``Program.values``, so the
# duplication cannot drift silently.
CANONICAL_PROGRAMS = (
    'BS Information System',
    'BS Information Technology',
    'BS Computer Science',
)

# A line must look like a degree statement before program matching runs.
# Without this gate, a title containing "Information Technology" would set
# the program from the title rather than from the degree line.
_DEGREE_LINE = re.compile(
    r'\b(bachelor|associate|degree|undergraduate\s+program|'
    r'bsis|bsit|bscs|bs\s?is|bs\s?it|bs\s?cs)\b',
    re.IGNORECASE,
)

# Deterministic discriminators, checked before any fuzzy matching.
_PROGRAM_TOKEN_RULES: tuple[tuple[str, str], ...] = (
    ('information system', 'BS Information System'),
    ('information technology', 'BS Information Technology'),
    ('computer science', 'BS Computer Science'),
)

_PROGRAM_ACRONYMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'\bbs\s?is\b', re.IGNORECASE), 'BS Information System'),
    (re.compile(r'\bbs\s?it\b', re.IGNORECASE), 'BS Information Technology'),
    (re.compile(r'\bbs\s?cs\b', re.IGNORECASE), 'BS Computer Science'),
)

# Fuzzy fallback, used ONLY when the deterministic rules find nothing — it
# exists for OCR damage ("Informaton Systerns"), not for normal documents.
_PROGRAM_FUZZY_ALIASES: tuple[tuple[str, str], ...] = (
    ('bachelor of science in information systems', 'BS Information System'),
    ('bachelor of science in information technology', 'BS Information Technology'),
    ('bachelor of science in computer science', 'BS Computer Science'),
)

# Empirically the gap between a real OCR-damaged degree line and the wrong
# program is wide; 88 keeps "…in Information Technology" from matching the
# Information System alias, which scores in the low 80s.
_PROGRAM_FUZZY_THRESHOLD = 88


def detect_program(text: str) -> tuple[str, str]:
    """Detect the degree program, constrained to ``CANONICAL_PROGRAMS``.

    Returns ``(program, confidence)`` where ``program`` is either one of the
    exact enum strings or ``''``. It is never anything else: an out-of-enum
    value would pass silently into the form and then fail submit with a
    VALIDATION_ERROR, which is a worse outcome than an unfilled dropdown that
    the user sets themselves.
    """
    if not text:
        return '', 'low'

    lines = [collapse_whitespace(raw) for raw in text.split('\n') if collapse_whitespace(raw)]

    degree_lines = [line for line in lines[:TITLE_PAGE_LINES] if _DEGREE_LINE.search(line)]
    if not degree_lines:
        return '', 'low'

    # Stage 1 — deterministic. Handles every well-formed document.
    for line in degree_lines:
        lowered = line.lower()
        for token, canonical in _PROGRAM_TOKEN_RULES:
            if token in lowered:
                return _validated_program(canonical), 'high'

    # Stage 2 — acronyms ("BSIT", "BS IT").
    for line in degree_lines:
        for pattern, canonical in _PROGRAM_ACRONYMS:
            if pattern.search(line):
                return _validated_program(canonical), 'high'

    # Stage 3 — fuzzy, for OCR-damaged degree lines only.
    try:
        from rapidfuzz import fuzz, process
    except ImportError:  # pragma: no cover - rapidfuzz is a pinned dependency
        logger.warning('rapidfuzz unavailable; skipping fuzzy program matching')
        return '', 'low'

    best_canonical = ''
    best_score = 0.0
    aliases = [alias for alias, _ in _PROGRAM_FUZZY_ALIASES]
    alias_to_canonical = dict(_PROGRAM_FUZZY_ALIASES)
    for line in degree_lines:
        match = process.extractOne(
            line.lower(),
            aliases,
            scorer=fuzz.token_set_ratio,
            score_cutoff=_PROGRAM_FUZZY_THRESHOLD,
        )
        if match and match[1] > best_score:
            best_score = match[1]
            best_canonical = alias_to_canonical[match[0]]

    if not best_canonical:
        return '', 'low'
    return _validated_program(best_canonical), 'medium'


def _validated_program(value: str) -> str:
    """Final gate — return ``value`` only if it is an exact enum member."""
    if value in CANONICAL_PROGRAMS:
        return value
    logger.warning('Program extraction produced non-enum value %r; discarding', value)
    return ''


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

MAX_AUTHORS = 12

# Lowercase name particles and generational suffixes that legitimately break
# the "every word is capitalised" rule.
_NAME_PARTICLES = frozenset({
    'de', 'del', 'dela', 'delos', 'delas', 'da', 'di', 'du', 'van', 'von',
    'der', 'la', 'le', 'y', 'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv',
})

# Characters allowed in a person's name. Anything else (digits, slashes,
# parentheses) means the line is not a name.
_NAME_DISALLOWED = re.compile(r"[^A-Za-z.,\-'\u00C0-\u024F\s]")

# ── Positive name markers ──────────────────────────────────────────────────
#
# Used only by ``_looks_like_author_line``, which needs to be STRICTER than
# ``_looks_like_person_name``. That function answers "could this be a name?"
# and correctly returns True for real titles in this corpus — 'Alumni Portal
# Tracker', 'Web-Based Qualifying Examination', 'Scholarship Management In
# Pampanga' are all indistinguishable from a name by capitalisation alone.
# Using it raw as a title terminator would chop those titles in half.
#
# So a line must ALSO carry at least one affirmative signal that it is a
# person. Name PARTICLES are deliberately excluded from these markers:
# 'SISTEMA de OBRA: TRAINING MONITORING SYSTEM' contains 'de', and while the
# colon already disqualifies it via _NAME_DISALLOWED, relying on that
# coincidence would make the rule fragile.

# Generational suffixes. Distinct from _NAME_PARTICLES on purpose: every
# entry here is affirmative evidence of a person, whereas that set also
# contains particles like 'de' and 'van' which are not.
_GENERATIONAL_SUFFIXES = frozenset({'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'})

_HONORIFICS = frozenset({
    'dr', 'dr.', 'engr', 'engr.', 'prof', 'prof.',
    'mr', 'mr.', 'ms', 'ms.', 'mrs', 'mrs.',
})

# "SURNAME, Given" — the author-list convention throughout this corpus.
_SURNAME_COMMA_GIVEN = re.compile(r',\s+[A-Z]')
_INLINE_SURNAME_START = re.compile(
    r"(?<![A-Za-z])(?P<surname>(?:(?:de|del|dela|delos|delas|da|di|du|"
    r"van|von|der|la|le)\s+)?[A-Z][A-Za-z'’\-]{1,}),\s+",
    re.IGNORECASE,
)

# A standalone middle initial: "E." or "S.".
#
# The trailing period is MANDATORY. Making it optional matches the bare article
# 'A', which classified every title opening "A …" as an author line — 'A
# SEMANTIC RETRIEVAL ENGINE' was cut to nothing. The period is what
# distinguishes an initial from a one-letter word.
_STANDALONE_INITIAL = re.compile(r'^[A-Z]\.$')
_INITIAL_CLUSTER = re.compile(r'^(?:[A-Z]\.){2,}$')


def _is_name_initial(token: str) -> bool:
    cleaned = token.rstrip(',')
    return bool(
        _STANDALONE_INITIAL.fullmatch(cleaned)
        or _INITIAL_CLUSTER.fullmatch(cleaned)
    )

# An unmarked title-page author still needs name-specific evidence. Affiliations
# and addresses are capitalised just like names, so exclude their common
# vocabulary before applying the stricter author-line shape below.
_UNMARKED_AUTHOR_AFFILIATION = re.compile(
    r'\b(?:university|college|school|institute|campus|faculty|department|'
    r'computing\s+studies|'
    r'state|dhvsu|don\s+honorio(?:\s+ventura)?|pampanga|philippines|'
    r'province|city|municipality|barangay|barrio|purok|sitio|street|avenue|'
    r'road|highway|village|subdivision)\b',
    re.IGNORECASE,
)
_UNMARKED_AUTHOR_INSTITUTION = re.compile(
    r'\b(?:university|college|school|institute|campus|faculty|department|'
    r'computing\s+studies|'
    r'state|dhvsu|don\s+honorio(?:\s+ventura)?)\b',
    re.IGNORECASE,
)
_UNMARKED_AUTHOR_LOCALITY = re.compile(
    r'\b(?:pampanga|philippines|province|city|municipality|barangay|barrio|'
    r'brgy|purok|sitio|street|avenue|road|highway|village|subdivision|'
    r'resettlement)\b',
    re.IGNORECASE,
)
_UNMARKED_AUTHOR_ROLE = re.compile(
    r'^\s*(?:thesis\s+)?(?:adviser|advisor|panel(?:ist|ists|\s+members?)?|'
    r'chair(?:person)?|committee|approved\s+by|reviewed\s+by|examined\s+by)\b',
    re.IGNORECASE,
)


def _looks_like_author_line(line: str) -> bool:
    """True when ``line`` is an author-list entry rather than a title line.

    Strictly narrower than :func:`_looks_like_person_name`: that must be true
    first, and then the line must carry at least one positive marker of
    personhood. See the comment block above for why the extra requirement
    exists — without it, legitimate titles in this corpus are read as names.
    """
    # ── Strong personhood markers, valid at ANY line length ────────────────
    #
    # This corpus prints author entries as "NAME, Affiliation" on one line:
    #   'CRISTOPHER B. AMPA, Don Honorio Ventura State University'   (8 words)
    #   'JOHN PAUL B. ARNAIZ, Don Honorio Ventura State University'  (9 words)
    #
    # _has_name_shape caps a name at six words, so those were NOT recognised
    # and the full student names were eligible to join a title. The markers
    # below are checked without any length limit because they are strong enough
    # to stand alone: an initial, an honorific or a generational suffix does
    # not occur in a thesis title.
    #
    # The "SURNAME, Given" comma rule is NOT applied at unlimited length. It is
    # much weaker — a real title line like 'Monitoring for the Office of
    # Municipal Treasury of the Municipality of Bacolor, Pampanga' matches it,
    # and treating that as an author line would disqualify the title itself.
    # Title vocabulary vetoes the unlimited-length path. Without it a title
    # like 'A SYSTEM FOR DR. JOSE RIZAL MEMORIAL HOSPITAL' would be read as an
    # author line on the strength of its honorific and disqualified outright.
    # An author entry does not contain title vocabulary, so this costs nothing.
    lowered_line = line.lower()
    carries_title_vocabulary = any(
        keyword in lowered_line for keyword in _TITLE_KEYWORDS
    )

    if not carries_title_vocabulary and not _NAME_DISALLOWED.search(line):
        for token in line.split():
            # pypdf can attach the comma introducing an affiliation to a
            # middle initial ("... IVAN A., Don Honorio Ventura State
            # University"). Strip only that delimiter before checking the
            # existing standalone-initial signal.
            if _STANDALONE_INITIAL.fullmatch(token.rstrip(',')):
                return True
            lowered = token.lower()
            if lowered in _GENERATIONAL_SUFFIXES or lowered in _HONORIFICS:
                return True

    # ── Weaker markers, only on a line already shaped like a bare name ─────
    if not _has_name_shape(line):
        return False

    return bool(_SURNAME_COMMA_GIVEN.search(line))


def _has_name_shape(line: str) -> bool:
    """Character and capitalisation shape of a name, with NO terminator check.

    Split out of :func:`_looks_like_person_name` to break a cycle:
    ``_looks_like_person_name`` consults the boilerplate screen, and
    ``_is_block_terminator`` consults ``_looks_like_author_line``. Routing the
    author test through the public function would recurse, so both share this
    screen-free core instead.
    """
    if not line:
        return False
    if _NAME_DISALLOWED.search(line):
        return False

    words = line.split()
    if not 2 <= len(words) <= 6:
        return False
    if sum(1 for ch in line if ch.isalpha()) < 4:
        return False

    for word in words:
        core = word.strip(".,-'")
        if not core or core.lower() in _NAME_PARTICLES:
            continue
        if not core[0].isupper():
            return False
    return True


def _looks_like_person_name(line: str) -> bool:
    """Heuristic test for "this line is a person's name".

    Screens against ``_is_non_title_boilerplate`` rather than the full
    ``_is_block_terminator``: the latter now counts an author-list entry as a
    terminator, which would make this reject exactly the lines it is meant to
    accept.
    """
    if not line or _is_non_title_boilerplate(line):
        return False
    return _has_name_shape(line)


def _title_boundary_key(value: str) -> str:
    """Compact title text for locating its exact span in extracted lines."""
    return re.sub(r'[^A-Za-z0-9]', '', fold_quotes(value)).casefold()


def _find_detected_title_end(lines: list[str]) -> int | None:
    """Return the line after the detected title, or None if it cannot be mapped.

    Markerless author inference is safe only when it can anchor the candidate
    block after a title already recognised by the existing title detector.
    The punctuation-insensitive key handles wrapped hyphens and quote folding
    without moving or re-scoring the title boundary.
    """
    title, _ = detect_title('\n'.join(lines))
    return _find_title_end_for_title(lines, title)


def _find_title_end_for_title(lines: list[str], title: str) -> int | None:
    """Map an already detected title back to the equivalent extracted rows."""
    target = _title_boundary_key(title)
    if not target:
        return None

    limit = min(len(lines), TITLE_PAGE_LINES)
    for start in range(limit):
        if not lines[start]:
            continue
        accumulated = ''
        for end in range(start, min(limit, start + 12)):
            accumulated += _title_boundary_key(lines[end])
            if accumulated == target:
                return end + 1
            if len(accumulated) > len(target):
                break
    return None


def _is_author_marker_candidate(line: str, match: re.Match) -> bool:
    """Reject body prose that happens to begin with a marker word.

    In particular, ``Researchers used ...`` is ordinary abstract prose, not an
    author heading. Marker labels may stand alone (``by:`` / ``Researchers:``)
    or introduce a name on the same line.
    """
    marker = match.group(1).casefold()
    remainder = _remove_contact_details(line[match.end():].strip(' :,'))
    if remainder:
        if marker == 'by':
            # ``by`` can open a title continuation. An inline author marker
            # needs either surname/initial structure or a short name; a long
            # all-caps phrase such as ``BY AI CHATBOT AND EMERGENCY RESPONSE``
            # is not a person block.
            return (
                _looks_like_author_line(remainder)
                or (
                    len(remainder.split()) <= 3
                    and _looks_like_person_name(remainder)
                )
            )
        return (
            len(_split_inline_author_names(remainder)) >= 2
            or _looks_like_person_name(remainder)
            or _looks_like_author_line(remainder)
        )

    if marker.startswith('researcher'):
        return bool(re.fullmatch(r'researchers?\s*:?\s*', line, re.IGNORECASE))
    return True


def _split_inline_author_names(line: str) -> list[str]:
    """Split a row containing multiple ``Surname, Given`` author entries.

    DOCX extraction can keep several authors in one paragraph, and PDF
    extraction can place a whole column of names on one visual row. A new
    surname-comma boundary is strong evidence of the next entry. Only return
    the split when at least two resulting spans independently look like
    surname-first names, so ordinary comma-containing title or affiliation
    lines stay intact.
    """
    cleaned = line or ''
    if re.search(r'\d', cleaned):
        return []
    # A locality row such as "San Basilio, Sta Rita, Pampanga" can look like
    # two short surname-first names after comma splitting. A name row carrying
    # an affiliation can also look like two names when the given name ends in
    # a word such as "Gerald" ("Oliva, Edmar Gerald, ... University"). Defer
    # those multi-comma rows to the affiliation-aware parser below.
    if (
        cleaned.count(',') >= 2
        and _UNMARKED_AUTHOR_AFFILIATION.search(cleaned)
    ):
        return []

    matches = list(_INLINE_SURNAME_START.finditer(cleaned))
    if len(matches) < 2:
        return []

    names: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        candidate = collapse_whitespace(cleaned[match.start():end]).strip(' ,;')
        if (
            _looks_like_person_name(candidate)
            and _SURNAME_COMMA_GIVEN.search(candidate)
        ):
            names.append(candidate)

    return names if len(names) == len(matches) else []


def _looks_like_unmarked_author_name(line: str) -> bool:
    """Require a surname/given-name or middle-initial structure without a label."""
    cleaned = _remove_contact_details(line)
    if not cleaned:
        return False
    lowered = cleaned.casefold()
    if _UNMARKED_AUTHOR_AFFILIATION.search(cleaned):
        return False
    if any(keyword in lowered for keyword in _TITLE_KEYWORDS):
        return False

    words = cleaned.split()
    comma_count = cleaned.count(',')
    if not _looks_like_person_name(cleaned):
        # A title-page surname can be printed in lower case (as in the
        # source's ``ingat, Randy Jr. M..``). Accept that only in the
        # surname-first form, and only when the given-name side still carries
        # a middle initial or generational suffix.
        if comma_count != 1:
            return False
        surname, given = cleaned.split(',', maxsplit=1)
        given_words = given.split()
        titlecase_shape = _has_name_shape(f'{surname.title()}, {given}')
        has_given_marker = (
            any(_STANDALONE_INITIAL.fullmatch(word.rstrip('.,')) for word in given_words)
            or any(word.rstrip('.,').casefold() in _GENERATIONAL_SUFFIXES for word in given_words)
        )
        if not titlecase_shape or not has_given_marker:
            return False

    if comma_count == 1:
        surname, given = cleaned.split(',', maxsplit=1)
        given_words = given.split()
        # A single given-name token after a comma is a common address shape
        # ("Villa de Bacolor, Pampanga"). Requiring at least two keeps that
        # shape out while allowing names such as "Bonifacio, Ralph Christian".
        return 1 <= len(surname.split()) <= 2 and 2 <= len(given_words) <= 4

    if comma_count == 0 and 3 <= len(words) <= 5:
        return (
            any(_is_name_initial(word) for word in words[1:-1])
            or any(word.rstrip('.,').lower() in _GENERATIONAL_SUFFIXES for word in words)
        )
    return False


def _unmarked_author_name_from_line(line: str) -> str:
    """Return a verified name prefix when an author shares a line with an affiliation."""
    cleaned = _remove_contact_details(line)
    if re.search(r'\d', cleaned):
        return ''

    # An uppercase degree abbreviation may follow a printed middle initial
    # without a delimiter (for example, ``Mallari, Christian S. MIT``). Keep
    # the name only when the prefix already satisfies the full name rule.
    trailing_abbreviation = re.fullmatch(
        r'(?P<name>.+\b[A-Z]\.)\s+[A-Z]{2,5}', cleaned,
    )
    if (
        trailing_abbreviation
        and _looks_like_unmarked_author_name(trailing_abbreviation.group('name'))
    ):
        return trailing_abbreviation.group('name')

    # Two or more commas plus a locality term indicate an address row, not an
    # author followed by an institution. This blocks fragments such as
    # "San Basilio, Sta Rita, Pampanga" before suffix splitting can read them
    # as surname/given pairs.
    if (
        cleaned.count(',') >= 2
        and _UNMARKED_AUTHOR_LOCALITY.search(cleaned)
    ):
        return ''

    # PDF text can wrap the end of the previous affiliation onto the same row
    # as the next surname-first author (for example, "University BENITEZ,
    # CHRISTIAN M."). Discard only that leading affiliation fragment; the
    # author still has to pass the name and affiliation boundary checks below.
    cleaned = _strip_leading_affiliation_continuation(cleaned)

    if _looks_like_unmarked_author_name(cleaned):
        return cleaned

    # Some title pages print ``Given Middle Surname, University`` on one line.
    # Split only at a comma whose right side contains known affiliation
    # vocabulary; a surname-first author comma is otherwise left untouched.
    comma_matches = list(re.finditer(r',\s*', cleaned))
    for comma_index, match in enumerate(comma_matches):
        name = collapse_whitespace(cleaned[:match.start()]).strip(' ,;')
        affiliation = cleaned[match.end():]
        words = name.split()
        has_initial = any(
            _is_name_initial(word)
            for word in words
        )
        has_title_word = any(
            keyword in name.casefold() for keyword in _TITLE_KEYWORDS
        )
        # With two commas, the first may separate surname from given names,
        # while the next one separates the complete name from its affiliation
        # (``DELA CRUZ, CHARLES IVAN A., University``). Do not truncate that
        # layout to its two-word surname prefix.
        leading_surname_only = (
            comma_index == 0
            and len(comma_matches) > 1
            and len(words) <= 2
            and not has_initial
        )
        # The affiliation delimiter is strong context for common given-first
        # layouts, including two-word names and initials placed before the
        # surname. Without that delimiter, those shapes remain too ambiguous.
        name_before_affiliation = (
            _looks_like_unmarked_author_name(name)
            or (
                _looks_like_person_name(name)
                and not _UNMARKED_AUTHOR_AFFILIATION.search(name)
                and not has_title_word
                and (2 <= len(words) <= 5 or has_initial)
            )
        )
        locality_only_suffix = (
            _UNMARKED_AUTHOR_LOCALITY.search(affiliation)
            and not _UNMARKED_AUTHOR_INSTITUTION.search(affiliation)
        )
        if (
            not leading_surname_only
            and
            _UNMARKED_AUTHOR_AFFILIATION.search(affiliation)
            and name_before_affiliation
            and not locality_only_suffix
        ):
            return name
    return ''


def _strip_leading_affiliation_continuation(line: str) -> str:
    """Remove a wrapped affiliation prefix before the next surname-first name."""
    for surname_match in _INLINE_SURNAME_START.finditer(line):
        leading_fragment = line[:surname_match.start()]
        if (
            leading_fragment
            and _UNMARKED_AUTHOR_INSTITUTION.search(leading_fragment)
        ):
            return line[surname_match.start():].lstrip(' ,;')
    return line


def _name_before_wrapped_affiliation(line: str, following_line: str) -> str:
    """Recover a surname-first name when its final affiliation word wrapped."""
    if (
        _is_unmarked_author_contact(following_line)
        or not _UNMARKED_AUTHOR_INSTITUTION.search(following_line)
    ):
        return ''

    cleaned = _strip_leading_affiliation_continuation(
        _remove_contact_details(line)
    )
    separators = list(re.finditer(r',\s*', cleaned))
    if len(separators) < 2:
        return ''

    name = collapse_whitespace(cleaned[:separators[1].start()]).strip(' ,;')
    partial_affiliation = cleaned[separators[1].end():].strip(' ,;')
    if (
        not re.fullmatch(r"[A-Z][A-Za-z'’\-]{1,}", partial_affiliation)
        or not _looks_like_unmarked_author_name(name)
    ):
        return ''
    return name


def _trailing_name_fragment_after_affiliation(line: str) -> str:
    """Return a single name token accidentally left after a wrapped affiliation."""
    cleaned = _remove_contact_details(line)
    matches = list(_UNMARKED_AUTHOR_AFFILIATION.finditer(cleaned))
    if not matches:
        return ''
    trailing = cleaned[matches[-1].end():].strip(' ,;')
    return trailing if re.fullmatch(r"[A-Z][A-Za-z'’\-]{1,}", trailing) else ''


def _is_unmarked_author_block_stop(line: str) -> bool:
    """Stop before sections, submission details, and labelled reviewers."""
    return bool(
        _UNMARKED_AUTHOR_ROLE.match(line)
        or _AUTHOR_MARKER.match(line)
        or _ABSTRACT_HEADING.match(line)
        or _ABSTRACT_STOP.match(line)
        or _CHAPTER_PATTERNS.match(_noise_key(line))
        or _FRONTMATTER_STOP.match(line)
        or _TITLE_KEYWORD_LABEL.fullmatch(line)
        or _DEGREE_LINE.search(line)
        or _MONTH_YEAR.search(line)
        or re.fullmatch(r'(?:19|20)\d{2}', line)
    )


def _is_unmarked_author_affiliation_or_contact(line: str) -> bool:
    """Recognise intervening title-page details without returning them as names."""
    return bool(
        _is_unmarked_author_contact(line)
        or _UNMARKED_AUTHOR_AFFILIATION.search(line)
        or _UNMARKED_AUTHOR_LOCALITY.search(line)
        or line.count(',') >= 2
        or _looks_like_wrapped_address_fragment(line)
    )


def _looks_like_wrapped_address_fragment(line: str) -> bool:
    """Recognise a capitalised place fragment whose comma wrapped to the next row."""
    if not line.rstrip().endswith(','):
        return False
    words = line.rstrip(' ,').split()
    return (
        len(words) >= 3
        and all(re.fullmatch(r'[A-Z][A-Za-z.\-]*', word) for word in words)
    )


def _is_unmarked_author_contact(line: str) -> bool:
    """Recognise contacts even when PDF extraction spaces digits or splits email."""
    digits = sum(char.isdigit() for char in line)
    return _has_contact_details(line) or '@' in line or digits >= 6


def _detect_unmarked_title_page_authors(
    lines: list[str], *, title_end: int | None = None,
) -> list[str]:
    """Infer a names-only block immediately after a confidently located title.

    The fallback intentionally requires multiple structured names on the
    title page. A lone capitalised line, a name elsewhere in the document, or
    a block that cannot be bounded remains unknown for manual entry.
    """
    cursor = title_end if title_end is not None else _find_detected_title_end(lines)
    if cursor is None:
        return []

    page_limit = min(len(lines), TITLE_PAGE_LINES)
    while cursor < page_limit and not lines[cursor]:
        cursor += 1
    if cursor >= page_limit or _is_unmarked_author_block_stop(lines[cursor]):
        return []

    first_inline_names = _split_inline_author_names(
        _remove_contact_details(lines[cursor])
    )
    first_name = _unmarked_author_name_from_line(lines[cursor])
    if first_inline_names:
        authors = first_inline_names
    elif first_name:
        authors = [first_name]
    else:
        return []
    pending_name_fragment = _trailing_name_fragment_after_affiliation(lines[cursor])
    cursor += 1
    non_name_lines = 0
    max_non_name_lines = 48
    blank_run = 0
    previous_contact_line = False
    previous_affiliation_line = False
    while cursor < page_limit and len(authors) < MAX_AUTHORS:
        line = lines[cursor]
        cursor += 1
        if not line:
            blank_run += 1
            if blank_run > 3:
                break
            continue
        if _is_unmarked_author_block_stop(line):
            break

        inline_names = _split_inline_author_names(_remove_contact_details(line))
        if inline_names:
            authors.extend(inline_names)
            non_name_lines = 0
            blank_run = 0
            previous_contact_line = False
            previous_affiliation_line = False
            continue
        candidate = _unmarked_author_name_from_line(line)
        if not candidate and cursor < page_limit:
            candidate = _name_before_wrapped_affiliation(line, lines[cursor])
        if candidate:
            if (
                pending_name_fragment
                and re.match(r'^[A-Z]\.(?:\s|$)', candidate)
            ):
                candidate = f'{pending_name_fragment} {candidate}'
            authors.append(candidate)
            pending_name_fragment = _trailing_name_fragment_after_affiliation(line)
            non_name_lines = 0
            blank_run = 0
            previous_contact_line = False
            previous_affiliation_line = False
            continue

        if _is_unmarked_author_affiliation_or_contact(line):
            pending_name_fragment = ''
            non_name_lines += 1
            blank_run = 0
            previous_contact_line = _is_unmarked_author_contact(line)
            previous_affiliation_line = bool(
                _UNMARKED_AUTHOR_AFFILIATION.search(line)
            ) and not previous_contact_line
            if non_name_lines > max_non_name_lines:
                break
            continue

        # pypdf sometimes wraps the final few letters of a long email onto a
        # separate line (for example ``...@gmail.c`` / ``om``). Skip only a
        # short fragment immediately following a contact line; this is not a
        # general licence to bridge arbitrary text between names.
        if previous_contact_line and re.fullmatch(r'[A-Za-z0-9]{1,4}', line):
            non_name_lines += 1
            previous_contact_line = False
            previous_affiliation_line = False
            if non_name_lines > max_non_name_lines:
                break
            continue

        # Address blocks can wrap a locality onto its own short line after a
        # street/highway line (for example, ``114 MacArthur Highway Sampaloc``
        # followed by ``Apalit``). A one- or two-word place fragment cannot
        # satisfy the author-name rule above, so bridge it only immediately
        # after a recognised affiliation/address line.
        if previous_affiliation_line and re.fullmatch(
            r'[A-Z][A-Za-z.,-]*(?:\s+[A-Z][A-Za-z.,-]*)?', line,
        ):
            non_name_lines += 1
            previous_affiliation_line = False
            if non_name_lines > max_non_name_lines:
                break
            continue

        previous_contact_line = False
        previous_affiliation_line = False

        break

    # One unmarked candidate is too ambiguous: it could be a reviewer, a
    # caption, or another title-page line. Leave it for manual entry.
    return authors if len(authors) >= 2 else []


def detect_authors(
    text: str, *, title_override: str | None = None,
) -> tuple[list[str], str]:
    """Extract the author block that follows a "by" / "Submitted by" marker.

    Returns ``(authors, confidence)``.

    Confidence is capped at ``'low'`` by design — never ``'high'`` — because
    this is the least determinable of the six fields. A line of capitalised
    words after "by:" is just as likely to be an adviser, a panel member, or a
    department name as it is an author, and unlike the other fields there is no
    label to anchor on. The UI should always prompt a review here.
    """
    if not text:
        return [], 'low'

    lines = [collapse_whitespace(raw) for raw in text.split('\n')]

    marker_idx = -1
    first_inline: list[str] = []
    title_end = (
        _find_title_end_for_title(lines, title_override)
        if title_override else _find_detected_title_end(lines)
    )
    for idx, line in enumerate(lines[:TITLE_PAGE_LINES * 2]):
        if not line:
            continue
        if (
            _ABSTRACT_HEADING.match(line)
            or _CHAPTER_PATTERNS.match(_noise_key(line))
        ):
            break
        match = _AUTHOR_MARKER.match(line)
        if not match or not _is_author_marker_candidate(line, match):
            continue
        marker_idx = idx
        remainder = _remove_contact_details(line[match.end():].strip(' :,'))
        if remainder:
            first_inline = _split_inline_author_names(remainder)
            if not first_inline and _looks_like_person_name(remainder):
                first_inline = [remainder]
        break

    if marker_idx < 0:
        authors = _detect_unmarked_title_page_authors(lines, title_end=title_end)
    else:
        authors: list[str] = []
        if first_inline:
            authors.extend(first_inline)

        # Blanks cannot terminate the author block, only bound it. Two different
        # real layouts require tolerating them:
        #   * the THESYS+ PDF puts a blank line between "by:" and the first name,
        #     then lists the names contiguously;
        #   * DOCX extraction makes every paragraph its own block, so a blank sits
        #     between EVERY name.
        # Termination is therefore driven by "this line is no longer a name",
        # with a small blank budget to bridge the gaps.
        MAX_CONSECUTIVE_BLANKS = 2
        blank_run = 0

        for line in lines[marker_idx + 1:]:
            if not line:
                blank_run += 1
                if blank_run > MAX_CONSECUTIVE_BLANKS:
                    break
                continue

            # Contact details are removed BEFORE the name test, then the remainder
            # is judged. Previously any line carrying an email or a phone number
            # failed _looks_like_person_name — '@' and digits are outside
            # _NAME_DISALLOWED's character class — which broke the walk and
            # silently dropped that author AND every author after it. Title pages
            # in this corpus commonly print contacts beside or beneath each name,
            # so that was the normal case, not an edge one.
            cleaned = _remove_contact_details(line)

            if not cleaned:
                # A line that is ONLY contact details. Skip it rather than
                # terminate — the names often continue after it — but spend the
                # blank budget so a long contact block cannot run away.
                blank_run += 1
                if blank_run > MAX_CONSECUTIVE_BLANKS:
                    break
                continue

            inline_names = _split_inline_author_names(cleaned)
            if inline_names:
                blank_run = 0
                authors.extend(inline_names)
                if len(authors) >= MAX_AUTHORS:
                    break
                continue

            if not _looks_like_person_name(cleaned):
                break
            blank_run = 0
            authors.append(cleaned)
            if len(authors) >= MAX_AUTHORS:
                break

    seen: set[str] = set()
    deduped: list[str] = []
    for name in authors:
        cleaned = collapse_whitespace(name).rstrip(',;')
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)

    if not deduped:
        return [], 'low'
    return deduped, 'low'


def _order_authors_by_visual_rows(
    authors: list[str], author_lines: tuple[str, ...] | list[str],
) -> list[str]:
    """Reorder recognized authors by their positions in first-page visual rows.

    The row hints come from the PDF text layer and are never used to invent
    names. If any extracted name cannot be mapped back to a row, keep the
    detector's original order rather than returning a partial ordering.
    """
    if len(authors) < 2 or not author_lines:
        return authors

    def key(value: str) -> str:
        return ''.join(char.casefold() for char in value if char.isalnum())

    row_keys = [key(line) for line in author_lines]
    positions: list[tuple[int, int]] = []
    for author in authors:
        author_key = key(author)
        matches = [
            (row_index, row_key.find(author_key))
            for row_index, row_key in enumerate(row_keys)
            if author_key and row_key.find(author_key) >= 0
        ]
        if not matches:
            return authors
        positions.append(matches[0])

    if len(set(positions)) != len(authors):
        return authors
    return [
        author for _position, author in sorted(zip(positions, authors))
    ]


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

#: Field order used in the API response. Mirrors the upload form's layout so
#: the frontend can iterate it directly.
METADATA_FIELDS = ('title', 'abstract', 'authors', 'keywords', 'program', 'year')


def extract_metadata(
    text: str, *, author_lines: tuple[str, ...] | list[str] = (),
) -> dict[str, dict]:
    """Run every field extractor over ``text``.

    Returns a mapping of field name to ``{'value': ..., 'confidence': ...}``
    for each name in :data:`METADATA_FIELDS`. Values are already in the shape
    the upload form needs: ``authors`` and ``keywords`` are lists, ``year`` is
    an ``int`` or ``None``, everything else is a string.

    An extractor that finds nothing yields an empty value with ``'low'``
    confidence; no field is ever guessed. One extractor raising must not lose
    the other five, so each is isolated.
    """
    extractors = {
        'title': detect_title,
        'abstract': detect_abstract,
        'authors': detect_authors,
        'keywords': detect_keywords,
        'program': detect_program,
        'year': detect_year,
    }
    empties: dict[str, object] = {
        'title': '', 'abstract': '', 'authors': [],
        'keywords': [], 'program': '', 'year': None,
    }

    result: dict[str, dict] = {}
    for field in METADATA_FIELDS:
        try:
            value, confidence = extractors[field](text)
            if field == 'authors':
                # Some scanned pages have several author columns. The primary
                # OCR pass can read only one column even though the source
                # page clearly contains more names. A second author-only pass
                # over positioned first-page rows may supply a more complete
                # block; all names still pass the same title-page checks and
                # confidence remains low.
                if author_lines:
                    visual_title, _ = detect_title(text)
                    visual_value, visual_confidence = detect_authors(
                        '\n'.join(author_lines),
                        title_override=visual_title or None,
                    )
                    if len(visual_value) > len(value):
                        value, confidence = visual_value, visual_confidence
                value = _order_authors_by_visual_rows(value, author_lines)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Metadata extraction failed for field %s: %s', field, exc)
            value, confidence = empties[field], 'low'
        result[field] = {'value': value, 'confidence': confidence}
    return result
