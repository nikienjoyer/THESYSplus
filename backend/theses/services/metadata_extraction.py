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

1. **Score lines to find where the title STARTS** (unchanged scoring, so
   existing behaviour on single-line titles is preserved).
2. **Join forward from that line to find where the title ENDS.**

Stage 2's primary signal is the **blank line**. A title block on a title
page is always followed by a blank line before the next element ("A
Capstone", "Presented to the Faculty of", the author list, etc.). This is
the only signal that works universally — a continuation line may begin
with a lowercase connector ("for CCS Undergraduate Theses…"), an uppercase
connector ("WITH …"), or no connector at all (a bare "PROCESSING"), so
connector matching alone cannot terminate the block correctly.

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

# Words that can legitimately open a title CONTINUATION line. Compared
# case-insensitively — a continuation may be typeset in caps ("WITH …") in
# an all-caps title, so a case-sensitive list silently fails those.
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
    'NLP', 'OCR', 'PDF', 'PSU', 'QR', 'RFID', 'RPA', 'SBERT', 'SMS', 'SQL',
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
#      optional spacing or dashes between groups: 09397429130, +63 939 742
#      9130, 0939-742-9130.
#   2. Any bare run of 7 or more digits. This is the catch-all, and it also
#      covers student numbers (2018003310), which are PII in their own right.
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
    if _AUTHOR_MARKER.match(line):
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
    for token in title.split(' '):
        core = token.strip(_TOKEN_PUNCTUATION)
        if core and core.upper() in _KNOWN_ACRONYMS:
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
    parts = _COMPOUND_DELIMITERS.split(token)
    if len(parts) == 1:
        return token.title()

    out: list[str] = []
    for part in parts:
        # Delimiters come back from re.split as their own single-character
        # entries; pass them through untouched so the rejoin is exact.
        if part in ('-', '/'):
            out.append(part)
            continue
        core = part.strip(_TOKEN_PUNCTUATION)
        if core and core.upper() in _KNOWN_ACRONYMS:
            out.append(part)
        else:
            out.append(part.title())
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
    if n_words < 3 or n_words > MAX_TITLE_WORDS:
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
    if any(kw in lowered for kw in _TITLE_KEYWORDS):
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
      * a blank line (the primary signal — end of the title block)
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

    for nxt in lines[start_idx + 1:]:
        if not nxt:
            break
        # Terminators are checked FIRST, so a contact detail or author line is
        # cut even when the relaxed gate below would have admitted it.
        if _is_block_terminator(nxt):
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

    A bare author line like "Juan Miguel Santos" satisfies none of the four
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

    return False


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
    for raw_idx, line in enumerate(lines):
        if not line:
            continue
        nb_idx += 1
        if nb_idx >= MAX_CANDIDATE_LINES:
            break
        score = _score_candidate_line(line, nb_idx)
        if score is None:
            continue
        if score > best_score:
            best_score = score
            best_idx = raw_idx
            best_confidence = _confidence_for(score)

    if best_idx < 0:
        return '', 'low'

    title = _join_title_block(lines, best_idx, has_blank_structure)
    # Final scrub before casing. Every line-based defence above can be bypassed
    # by an extractor that emits the page as one line; this cannot.
    title = _strip_pii_tail(collapse_whitespace(title))
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
    r'^(keywords?|key\s*words?)\b\s*[:\-—]'
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
        if _ABSTRACT_STOP.match(line):
            break
        current.append(line)
        if sum(len(' '.join(p)) for p in paragraphs) + len(' '.join(current)) > MAX_ABSTRACT_CHARS:
            break

    if current:
        paragraphs.append(current)

    joined = '\n\n'.join(_join_wrapped_lines(p) for p in paragraphs if p).strip()
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
    r'^(keywords?|key\s*words?|index\s+terms?)\s*[:\-—]\s*(.*)$',
    re.IGNORECASE,
)

_KEYWORD_SPLIT = re.compile(r'[;,·•|]+')


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
    for idx, line in enumerate(lines):
        match = _KEYWORDS_LABEL.match(line)
        if not match:
            continue
        raw_value = match.group(2).strip()
        # Keyword lists wrap onto following lines; keep reading until the
        # blank line or the next heading.
        for nxt in lines[idx + 1:]:
            if not nxt or _ABSTRACT_STOP.match(nxt) or _is_block_terminator(nxt):
                break
            raw_value = f'{raw_value} {nxt}'
        break

    if not raw_value:
        return [], 'low'

    seen: set[str] = set()
    keywords: list[str] = []
    for chunk in _KEYWORD_SPLIT.split(raw_value):
        item = collapse_whitespace(chunk).strip(' .;:')
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
    confidence = 'high' if len(keywords) >= 3 else 'medium'
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
    window = '\n'.join(lines[:TITLE_PAGE_LINES])
    upper = max_year()

    def in_range(value: int) -> bool:
        return MIN_YEAR <= value <= upper

    month_years = [int(m.group(2)) for m in _MONTH_YEAR.finditer(window)]
    month_years = [y for y in month_years if in_range(y)]
    if month_years:
        return max(month_years), 'high'

    for line in lines[:TITLE_PAGE_LINES]:
        if re.fullmatch(r'(19\d{2}|20\d{2})', line) and in_range(int(line)):
            return int(line), 'high'

    candidates = [int(m.group(1)) for m in _BARE_YEAR.finditer(window)]
    candidates = [y for y in candidates if in_range(y)]
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
    'Associate in Computer Technology',
)

# A line must look like a degree statement before program matching runs.
# Without this gate, a title containing "Information Technology" would set
# the program from the title rather than from the degree line.
_DEGREE_LINE = re.compile(
    r'\b(bachelor|associate|degree|undergraduate\s+program|'
    r'bsis|bsit|bscs|bs\s?is|bs\s?it|bs\s?cs|act)\b',
    re.IGNORECASE,
)

# Deterministic discriminators, checked before any fuzzy matching. Ordered
# most-specific first: "computer technology" must be tested before the looser
# rules so an ACT degree line is not read as Computer Science.
_PROGRAM_TOKEN_RULES: tuple[tuple[str, str], ...] = (
    ('computer technology', 'Associate in Computer Technology'),
    ('information system', 'BS Information System'),
    ('information technology', 'BS Information Technology'),
    ('computer science', 'BS Computer Science'),
)

_PROGRAM_ACRONYMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'\bbs\s?is\b', re.IGNORECASE), 'BS Information System'),
    (re.compile(r'\bbs\s?it\b', re.IGNORECASE), 'BS Information Technology'),
    (re.compile(r'\bbs\s?cs\b', re.IGNORECASE), 'BS Computer Science'),
    (re.compile(r'\bact\b'), 'Associate in Computer Technology'),
)

# Fuzzy fallback, used ONLY when the deterministic rules find nothing — it
# exists for OCR damage ("Informaton Systerns"), not for normal documents.
_PROGRAM_FUZZY_ALIASES: tuple[tuple[str, str], ...] = (
    ('bachelor of science in information systems', 'BS Information System'),
    ('bachelor of science in information technology', 'BS Information Technology'),
    ('bachelor of science in computer science', 'BS Computer Science'),
    ('associate in computer technology', 'Associate in Computer Technology'),
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

# A standalone middle initial: "E." or "S.".
#
# The trailing period is MANDATORY. Making it optional matches the bare article
# 'A', which classified every title opening "A …" as an author line — 'A
# SEMANTIC RETRIEVAL ENGINE' was cut to nothing. The period is what
# distinguishes an initial from a one-letter word.
_STANDALONE_INITIAL = re.compile(r'^[A-Z]\.$')


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
            if _STANDALONE_INITIAL.match(token):
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


def detect_authors(text: str) -> tuple[list[str], str]:
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
    first_inline = ''
    for idx, line in enumerate(lines[:TITLE_PAGE_LINES * 2]):
        if not line:
            continue
        match = _AUTHOR_MARKER.match(line)
        if not match:
            continue
        marker_idx = idx
        remainder = _remove_contact_details(line[match.end():].strip(' :,'))
        if remainder and _looks_like_person_name(remainder):
            first_inline = remainder
        break

    if marker_idx < 0:
        return [], 'low'

    authors: list[str] = []
    if first_inline:
        authors.append(first_inline)

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


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

#: Field order used in the API response. Mirrors the upload form's layout so
#: the frontend can iterate it directly.
METADATA_FIELDS = ('title', 'abstract', 'authors', 'keywords', 'program', 'year')


def extract_metadata(text: str) -> dict[str, dict]:
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
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Metadata extraction failed for field %s: %s', field, exc)
            value, confidence = empties[field], 'low'
        result[field] = {'value': value, 'confidence': confidence}
    return result
