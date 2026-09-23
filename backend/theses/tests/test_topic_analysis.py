"""Phase 3 — Topic Trend Analysis tests.

Covers:
  1. Cluster generation (TF-IDF + K-Means produces the expected number)
  2. TF-IDF keyword extraction surfaces meaningful tokens
  3. Pending / rejected theses are excluded from analysis
  4. Trend classification (SATURATED / EMERGING / UNDEREXPLORED)
  5. /api/v1/theses/topic-trends/ endpoint envelope shape
  6. Empty / single-doc edge cases
  7. Heuristic topic naming
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus
from theses.services.topic_analysis import (
    CLASS_EMERGING,
    CLASS_SATURATED,
    CLASS_UNDEREXPLORED,
    K_MAX,
    K_MIN,
    KEYWORDS_PER_CLUSTER,
    _EXTRA_STOP_WORDS,
    _TOPIC_RULES,
    _best_rule_label,
    _choose_k,
    _classify_trend,
    _compose_thesis_text,
    _label_cluster,
    _load_english_stopwords,
    analyze_topics,
    get_topic_trends_queryset,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='facultyt@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Topic',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, faculty_user):
    """Factory: creates a Thesis with arbitrary status (default APPROVED)."""
    counter = {'n': 0}

    def _make(title, abstract='', keywords=None, status=ThesisStatus.APPROVED):
        counter['n'] += 1
        n = counter['n']
        sha = (f'{n:x}' + 'a' * 64)[:64]
        from django.core.files.base import ContentFile

        thesis = Thesis(
            title=title,
            abstract=abstract or f'This thesis on {title} explores the topic in detail.',
            authors=['Tester, T.'],
            keywords=keywords or [],
            program=Program.BSIT.value,
            year=2024,
            adviser='',
            file_type=FileType.PDF,
            sha256=sha,
            extracted_text='',
            status=status,
            uploaded_by=faculty_user,
        )
        thesis.uploaded_file.save(
            f'thesis_{n}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        thesis.save()
        return thesis

    return _make


# ---------------------------------------------------------------------------
# Trend classification
# ---------------------------------------------------------------------------

class TestClassifyTrend:
    # Cold-start regime — total_theses < 15 preserves the original static rules.
    def test_saturated_at_5(self):
        assert _classify_trend(5, average_size=2.0, total_theses=10) == CLASS_SATURATED
        assert _classify_trend(10, average_size=2.0, total_theses=10) == CLASS_SATURATED

    def test_emerging_2_to_4(self):
        assert _classify_trend(2, average_size=2.0, total_theses=10) == CLASS_EMERGING
        assert _classify_trend(3, average_size=2.0, total_theses=10) == CLASS_EMERGING
        assert _classify_trend(4, average_size=2.0, total_theses=10) == CLASS_EMERGING

    def test_underexplored_0_or_1(self):
        assert _classify_trend(1, average_size=2.0, total_theses=10) == CLASS_UNDEREXPLORED
        assert _classify_trend(0, average_size=2.0, total_theses=10) == CLASS_UNDEREXPLORED

    def test_classify_trend_dynamic(self):
        # Large corpus (>= 15) switches to mean-relative scaling.
        # average_size = 20 → SATURATED >= 30, UNDEREXPLORED <= 10, else EMERGING.
        assert _classify_trend(35, average_size=20.0, total_theses=100) == CLASS_SATURATED
        assert _classify_trend(18, average_size=20.0, total_theses=100) == CLASS_EMERGING
        assert _classify_trend(8, average_size=20.0, total_theses=100) == CLASS_UNDEREXPLORED
        # Boundary checks: exactly 1.5x is SATURATED, exactly 0.5x is UNDEREXPLORED.
        assert _classify_trend(30, average_size=20.0, total_theses=100) == CLASS_SATURATED
        assert _classify_trend(10, average_size=20.0, total_theses=100) == CLASS_UNDEREXPLORED


# ---------------------------------------------------------------------------
# Heuristic topic naming
# ---------------------------------------------------------------------------

class TestRuleTokensAreReachable:
    """A rule token that is also a stop word is dead code.

    The vectoriser never emits it, so the rule entry can never fire, and the
    rule set silently means less than it appears to. ``_EXTRA_STOP_WORDS``
    grew over time for TF-IDF-ranking reasons without anyone re-checking
    ``_TOPIC_RULES`` against it, which left Educational Technology
    half-disarmed.
    """

    def test_no_rule_token_is_a_stop_word(self):
        stop_words = {*_EXTRA_STOP_WORDS, *_load_english_stopwords()}
        collisions = []

        for label, tokens in _TOPIC_RULES:
            for token in sorted(tokens):
                # Multi-word tokens are checked word by word. sklearn removes
                # stop words BEFORE assembling n-grams, so a bigram rule token
                # containing a stopped word can never be produced either —
                # "deep learning" is unreachable the moment "deep" is stopped.
                for word in token.split():
                    if word in stop_words:
                        collisions.append((label, token, word))

        assert not collisions, (
            'these _TOPIC_RULES tokens are stop words, so the vectoriser can '
            'never emit them and the rule entry is dead:\n'
            + '\n'.join(
                f'  {label!r}: token {token!r} (word {word!r} is a stop word)'
                for label, token, word in collisions
            )
        )


def _first_owner(token: str) -> str:
    """Label of the first rule in _TOPIC_RULES order that claims ``token``."""
    for label, tokens in _TOPIC_RULES:
        if token in tokens:
            return label
    raise AssertionError(f'{token!r} belongs to no rule')


# One (label, token) pair per token in the table, in declaration order.
_RULE_TOKEN_PAIRS = [
    (label, token)
    for label, tokens in _TOPIC_RULES
    for token in sorted(tokens)
]


class TestEveryRuleIsReachable:
    """Each rule must be able to win on its own vocabulary.

    Guards against a rule being added but shadowed into irrelevance, and
    against a careless reorder of ``_TOPIC_RULES`` silently changing which
    label a token resolves to.
    """

    @pytest.mark.parametrize('label, token', _RULE_TOKEN_PAIRS,
                             ids=[f'{lbl}:{tok}' for lbl, tok in _RULE_TOKEN_PAIRS])
    def test_token_resolves_to_its_own_rule(self, label, token):
        owner = _first_owner(token)
        if owner != label:
            # Not a failure: rule order is the documented tie-break, so an
            # earlier rule legitimately owns a shared token. Skipping rather
            # than silently tolerating keeps the overlap visible in the run
            # output, where it can be reviewed.
            pytest.skip(
                f'token {token!r} is shared — {owner!r} precedes {label!r} in '
                '_TOPIC_RULES and wins by documented priority'
            )

        assert _label_cluster([token]) == label

    def test_no_token_is_claimed_by_two_rules(self):
        """Currently ZERO tokens are shared, and that is worth locking.

        Removing ambiguous 'learning' from both AI Systems and Educational
        Technology left the table with no overlaps at all, so every token
        resolves to exactly one label and rule order never has to arbitrate.

        A future overlap is not automatically wrong — order is a documented
        tie-break — but it should be a deliberate decision, so make it fail
        here and be argued for rather than slip in unnoticed.
        """
        shared = [
            (label, token) for label, token in _RULE_TOKEN_PAIRS
            if _first_owner(token) != label
        ]
        assert shared == [], (
            'these tokens are claimed by more than one rule, so the later rule '
            'can never win on them:\n'
            + '\n'.join(
                f'  {label!r} declares {token!r}, but {_first_owner(token)!r} '
                'claims it first'
                for label, token in shared
            )
        )


class TestLabelCluster:
    def test_educational_game_cluster_is_not_labelled_ai_systems(self):
        """Regression: the bug this round exists to fix.

        'learning' used to sit in both AI Systems and Educational Technology.
        AI Systems comes first, so first-hit matching labelled every
        educational-game cluster 'AI Systems' — and because two separate
        clusters hit it, the chart showed 'AI Systems' twice while neither
        cluster was about machine learning.
        """
        assert _label_cluster([
            'game', 'educational', 'educational game',
            'interactive', 'learning', 'unity',
        ]) == 'Educational Technology'

    def test_ai_keywords_label(self):
        assert _label_cluster(['recognition', 'deep', 'cnn', 'learning']) == 'Computer Vision'

    def test_iot_keywords_label(self):
        assert _label_cluster(['iot', 'esp32', 'sensor']) == 'Internet of Things'

    def test_web_keywords_label(self):
        assert _label_cluster(['inventory', 'web', 'management']) == 'Web-Based Systems'

    def test_blockchain_keywords_label(self):
        assert _label_cluster(['blockchain', 'credential', 'verification']) == 'Blockchain Systems'

    def test_health_keywords_label(self):
        assert _label_cluster(['health', 'patient', 'diagnosis']) == 'Health Informatics'

    def test_mobile_keywords_label(self):
        assert _label_cluster(['mobile', 'flutter', 'android']) == 'Mobile Applications'

    def test_unknown_with_no_member_keywords_returns_other(self):
        """Inverted deliberately.

        This used to assert 'Robotics' — the raw top TF-IDF term promoted to a
        label. That mechanism is what produced "Support" and "Yielded Overall"
        on the live chart, so the term is no longer a label candidate at all.
        With no rule hit and no author keywords to fall back on, the honest
        answer is that the cluster is unnamed.
        """
        assert _label_cluster(['robotics', 'arm']) == 'Other / Mixed Topics'

    def test_member_keywords_supply_the_label(self):
        assert _label_cluster(
            ['robotics', 'arm'],
            member_keywords=[['swarm robotics'], ['swarm robotics'], ['gripper']],
        ) == 'Swarm Robotics'

    def test_member_keyword_counting_is_case_insensitive(self):
        """Two spellings of one phrase must be one topic, not two rivals."""
        assert _label_cluster(
            ['unmatched'],
            member_keywords=[['Swarm Robotics'], ['swarm robotics'], ['gripper']],
        ) == 'Swarm Robotics'

    def test_member_keyword_tie_break_is_alphabetical_and_stable(self):
        # 'gripper' and 'swarm robotics' both appear twice. Counter.most_common
        # would break the tie by insertion order, which follows cluster
        # membership and can differ between runs; alphabetical is stable.
        members = [['swarm robotics'], ['gripper'], ['swarm robotics'], ['gripper']]
        assert _label_cluster(['unmatched'], member_keywords=members) == 'Gripper'

        # Same input reversed — the winner must not move.
        reversed_members = list(reversed(members))
        assert _label_cluster(['unmatched'], member_keywords=reversed_members) == 'Gripper'

        # And repeated calls agree with each other.
        assert (
            _label_cluster(['unmatched'], member_keywords=members)
            == _label_cluster(['unmatched'], member_keywords=members)
        )

    def test_higher_ranked_keyword_wins_when_two_rules_match(self):
        """The point of weighting, proven directly.

        'recognition' belongs to Computer Vision, declared FIRST; 'iot'
        belongs to Internet of Things, declared fourth. Here 'iot' is the
        cluster's top term and 'recognition' its second, so IoT scores 2 to
        Computer Vision's 1.

        Under the old first-hit loop this returned 'Computer Vision' — rule
        order alone decided it and the centroid weighting was discarded.
        """
        assert _label_cluster(['iot', 'recognition']) == 'Internet of Things'

        # Reversing the ranking must flip the label. If it doesn't, the score
        # isn't actually reading position.
        assert _label_cluster(['recognition', 'iot']) == 'Computer Vision'

    def test_many_weak_matches_beat_one_strong_match(self):
        """A rule matching most of the list beats one matching only the top
        term, which is the behaviour that fixes the mislabelled clusters."""
        # 'neural' (rank 1, weight 6) is AI Systems' only hit.
        # Educational Technology hits ranks 2-6 → 5+4+3+2+1 = 15.
        assert _label_cluster([
            'neural', 'educational', 'game', 'quiz', 'tutorial', 'gamification',
        ]) == 'Educational Technology'

    def test_a_keyword_scores_a_rule_only_once(self):
        """'educational game' hits three Educational Technology tokens
        ('educational game', 'educational', 'game') but must count once, so a
        rule cannot inflate its score by listing synonyms.

        Educational Technology therefore scores 2 here, not 6 — and Computer
        Vision, scoring 1 on 'vision', still loses but only just.
        """
        assert _label_cluster(['educational game', 'vision']) == 'Educational Technology'
        # Give Computer Vision two ranked hits and it takes the label back,
        # which would be impossible if the bigram had triple-counted.
        assert _label_cluster(['vision', 'image', 'educational game']) == 'Computer Vision'

    def test_no_rule_match_returns_none_from_the_scorer(self):
        assert _best_rule_label(['robotics', 'arm']) is None
        assert _best_rule_label([]) is None

    def test_scorer_ignores_blank_keywords(self):
        assert _best_rule_label(['', None, 'iot']) == 'Internet of Things'

    def test_rules_outrank_member_keywords(self):
        """A rule hit must win even when authors supplied keywords."""
        assert _label_cluster(
            ['iot', 'esp32'],
            member_keywords=[['some custom phrase'], ['some custom phrase']],
        ) == 'Internet of Things'

    def test_empty_member_keyword_lists_fall_through_to_other(self):
        assert _label_cluster(['robotics'], member_keywords=[[], [], None]) == 'Other / Mixed Topics'

    def test_blank_member_keywords_are_ignored(self):
        assert _label_cluster(['robotics'], member_keywords=[['   '], ['']]) == 'Other / Mixed Topics'

    def test_empty_keywords_returns_general(self):
        assert _label_cluster([]) == 'General Research'

    def test_empty_keywords_with_member_keywords_uses_them(self):
        assert _label_cluster([], member_keywords=[['telemetry'], ['telemetry']]) == 'Telemetry'


# ---------------------------------------------------------------------------
# k auto-sizing
# ---------------------------------------------------------------------------

class TestChooseK:
    """Locks the k contract.

    The previous implementation was ``min(K_MAX, n_documents)``, which returns
    K_MAX for every corpus of 8 or more — k was effectively a constant while
    the docstring advertised corpus-sensitive sizing. The 10 and 30 rows below
    are the ones that would have failed then (both returned 8).
    """

    @pytest.mark.parametrize('n_documents, expected', [
        # Below K_MIN — one cluster per document, so the UI renders on a
        # freshly seeded repository.
        (1, 1),
        (2, 2),
        (4, 4),
        # At and above K_MIN, density sizing applies, floored at K_MIN.
        (5, 5),
        (10, 5),
        (30, 5),
        # 36 // 6 == 6 — the first corpus size where k actually moves.
        (36, 6),
        (42, 7),
        (48, 8),
        # Past the ceiling, K_MAX caps it — deliberately, not accidentally.
        (200, 8),
        (500, 8),
    ])
    def test_k_table(self, n_documents, expected):
        assert _choose_k(n_documents) == expected

    def test_k_never_leaves_the_documented_band(self):
        """Every corpus at or above K_MIN must land inside [K_MIN, K_MAX]."""
        for n in range(K_MIN, 600):
            k = _choose_k(n)
            assert K_MIN <= k <= K_MAX, f'k={k} out of band for n={n}'

    def test_k_never_exceeds_the_corpus_size(self):
        """K-Means cannot ask for more clusters than it has samples."""
        for n in range(1, 40):
            assert _choose_k(n) <= max(1, n)


# ---------------------------------------------------------------------------
# get_topic_trends_queryset — shared queryset helper
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetTopicTrendsQueryset:
    def test_returns_only_approved(self, make_thesis):
        approved = make_thesis('Approved Thesis On Recognition')
        make_thesis('Pending Thesis', status=ThesisStatus.PENDING_REVIEW)
        make_thesis('Rejected Thesis', status=ThesisStatus.REJECTED)

        ids = [str(t.id) for t in get_topic_trends_queryset()]
        assert ids == [str(approved.id)]

    def test_extracted_text_is_deferred_and_never_fetched(self, make_thesis):
        """The query win, guarded.

        ``extracted_text`` holds a whole manuscript per row, so it must stay
        out of ``.only()``. Asserting on ``get_deferred_fields()`` rather than
        query counts keeps this readable, and the second half proves nothing
        in the analysis path triggers the deferred-field reload.
        """
        make_thesis('Approved Thesis On Recognition')

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        row = get_topic_trends_queryset().first()
        assert 'extracted_text' in row.get_deferred_fields()

        # And running the full analysis must not quietly reload it per row.
        with CaptureQueriesContext(connection) as captured:
            analyze_topics(get_topic_trends_queryset())

        assert len(captured.captured_queries) == 1, (
            f'expected a single corpus query, got '
            f'{len(captured.captured_queries)} — a deferred field is '
            'probably being read per row'
        )

    def test_deterministic_ordering_across_calls(self, make_thesis):
        for i in range(5):
            make_thesis(f'Thesis Number {i}')

        first_call = [str(t.id) for t in get_topic_trends_queryset()]
        second_call = [str(t.id) for t in get_topic_trends_queryset()]
        assert first_call == second_call
        assert len(first_call) == 5


# ---------------------------------------------------------------------------
# analyze_topics — integration with TF-IDF + K-Means
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyzeTopics:
    def test_empty_corpus_returns_empty_envelope(self):
        result = analyze_topics([])
        assert result.total_theses == 0
        assert result.total_topics == 0
        assert result.clusters == []
        assert result.status == 'empty'

    def test_single_thesis_returns_one_cluster(self, make_thesis):
        t = make_thesis(
            'AI-Powered Attendance Monitoring Using Facial Recognition',
            abstract='A real-time deep learning system for recognising students.',
        )
        result = analyze_topics([t])
        assert result.total_theses == 1
        assert result.total_topics == 1
        assert len(result.clusters) == 1
        assert result.clusters[0].thesis_count == 1
        # Single-doc cluster is UNDEREXPLORED
        assert result.clusters[0].trend == CLASS_UNDEREXPLORED
        # Should have surfaced some keywords
        assert len(result.clusters[0].keywords) > 0

    def test_clustering_groups_attendance_theses_together(self, make_thesis):
        # Two clearly-attendance theses + two clearly-IoT theses
        ai_a = make_thesis(
            'AI-Powered Face Recognition Attendance System for Classrooms',
            abstract='Deep learning facial recognition for student attendance tracking.',
            keywords=['face recognition', 'attendance', 'deep learning'],
        )
        ai_b = make_thesis(
            'Smart Attendance Monitoring Using Facial Recognition CNN',
            abstract='CNN-based facial recognition for automated classroom attendance.',
            keywords=['CNN', 'attendance', 'face recognition'],
        )
        iot_a = make_thesis(
            'Internet of Things Greenhouse Monitoring with ESP32 Sensors',
            abstract='ESP32 sensors stream temperature and humidity over MQTT.',
            keywords=['IoT', 'ESP32', 'MQTT', 'sensors'],
        )
        iot_b = make_thesis(
            'IoT-Based Smart Parking System Using Magnetic Sensors',
            abstract='Magnetic sensors with IoT data exposes parking availability.',
            keywords=['IoT', 'sensors', 'parking'],
        )

        result = analyze_topics([ai_a, ai_b, iot_a, iot_b], k=2)
        assert result.total_theses == 4
        assert result.total_topics == 2

        # Each cluster's thesis_ids should not overlap
        all_ids = []
        for c in result.clusters:
            all_ids.extend(c.thesis_ids)
        assert len(set(all_ids)) == 4

        # The two attendance theses must end up in the same cluster
        clusters_by_id = {c.cluster_id: c for c in result.clusters}
        ai_a_cluster = next(c for c in result.clusters if str(ai_a.id) in c.thesis_ids)
        ai_b_cluster = next(c for c in result.clusters if str(ai_b.id) in c.thesis_ids)
        assert ai_a_cluster.cluster_id == ai_b_cluster.cluster_id

        iot_a_cluster = next(c for c in result.clusters if str(iot_a.id) in c.thesis_ids)
        iot_b_cluster = next(c for c in result.clusters if str(iot_b.id) in c.thesis_ids)
        assert iot_a_cluster.cluster_id == iot_b_cluster.cluster_id

        # And the attendance and IoT clusters must be different
        assert ai_a_cluster.cluster_id != iot_a_cluster.cluster_id

    def test_keywords_extracted_per_cluster(self, make_thesis):
        a = make_thesis(
            'Web-Based Inventory Management System',
            abstract='A web inventory management application with barcode tracking.',
            keywords=['web', 'inventory', 'management'],
        )
        b = make_thesis(
            'Cloud Inventory Tracking Web Platform',
            abstract='A cloud-hosted inventory tracking web application.',
            keywords=['cloud', 'inventory', 'web'],
        )
        result = analyze_topics([a, b], k=1)
        assert len(result.clusters) == 1
        kws = [k.lower() for k in result.clusters[0].keywords]
        # Every web/inventory cluster MUST surface at least one of these
        assert any(token in kws for token in ('web', 'inventory', 'tracking', 'cloud'))
        assert len(result.clusters[0].keywords) <= KEYWORDS_PER_CLUSTER


# ---------------------------------------------------------------------------
# Corpus hygiene — template boilerplate must never become a topic
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTemplateBoilerplateIsNotATopic:
    """The bug these guard: every manuscript shares the same front matter, so
    institution names and degree boilerplate ranked high enough in TF-IDF to
    become cluster labels. The chart then grouped theses by document template
    instead of research topic — "Capstone", "Honorio Ventura", "Dhvsu Edu".
    """

    BOILERPLATE = (
        'A capstone project presented to the faculty of the College of '
        'Computing Studies, Don Honorio Ventura State University, Bacolor, '
        'Pampanga, in partial fulfillment of the requirements for the degree '
        'of Bachelor of Science. Contact dhvsu edu for details.'
    )

    def _mixed_corpus(self, make_thesis):
        """Boilerplate on SOME rows, not all.

        This ratio matters. ``max_df=0.95`` already drops any term present in
        every document, so a corpus where all rows carry the front matter
        would pass this test with or without the stop-word list — the
        assertion would be vacuous. In the real repository, text extraction
        quality varies and only a fraction of rows carry a readable cover
        page, which is precisely why these terms survived max_df and became
        labels. 3 of 5 rows reproduces that: above ``min_df=2``, well below
        the max_df ceiling.
        """
        return [
            make_thesis(
                'Face Recognition Attendance Monitoring',
                abstract=f'{self.BOILERPLATE} Deep learning facial recognition '
                         'for classroom attendance.',
                keywords=['face recognition', 'attendance'],
            ),
            make_thesis(
                'IoT Greenhouse Sensor Network',
                abstract=f'{self.BOILERPLATE} ESP32 sensors stream humidity '
                         'readings over MQTT.',
                keywords=['iot', 'esp32', 'mqtt'],
            ),
            make_thesis(
                'Blockchain Credential Verification',
                abstract=f'{self.BOILERPLATE} A Hyperledger ledger verifies '
                         'academic credentials.',
                keywords=['blockchain', 'hyperledger'],
            ),
            make_thesis(
                'Sentiment Analysis of Tagalog Tweets',
                abstract='A BERT language model scores sentiment on Tagalog tweets.',
                keywords=['nlp', 'sentiment', 'tagalog'],
            ),
            make_thesis(
                'Mobile Flutter Campus Navigation',
                abstract='A cross-platform Flutter mobile app for campus routes.',
                keywords=['mobile', 'flutter'],
            ),
        ]

    def test_institution_and_degree_terms_never_surface_as_keywords(self, make_thesis):
        result = analyze_topics(self._mixed_corpus(make_thesis), k=2)

        surfaced = ' '.join(
            kw.lower() for c in result.clusters for kw in c.keywords
        )
        # Unigrams AND the bigrams they would have formed ("honorio ventura",
        # "capstone project"): sklearn strips stop words before assembling
        # n-grams, so killing the unigram kills every bigram containing it.
        for banned in (
            'capstone', 'dhvsu', 'honorio', 'ventura', 'bacolor',
            'bachelor', 'degree', 'fulfillment', 'college', 'faculty',
        ):
            assert banned not in surfaced, (
                f'template boilerplate {banned!r} surfaced as a TF-IDF keyword'
            )

    def test_extracted_text_is_not_part_of_the_corpus(self, make_thesis):
        """Direct proof the cover page cannot reach TF-IDF at all.

        Stronger than the stop-word tests above: those enumerate the noise
        terms seen so far, which is a blocklist and therefore always
        incomplete. This asserts the whole FIELD is excluded, so front matter
        nobody has thought of yet is excluded too.
        """
        theses = self._mixed_corpus(make_thesis)

        # A token that exists ONLY in extracted_text, on 3 of 5 rows — the
        # same ratio reasoning as _mixed_corpus: enough rows to clear
        # min_df=2, few enough to stay under the max_df ceiling, so neither
        # frequency filter can be credited for its absence.
        for t in theses[:3]:
            t.extracted_text = 'zzqqxx zzqqxx zzqqxx ' * 200
            t.save(update_fields=['extracted_text'])

        result = analyze_topics(theses, k=2)

        surfaced = ' '.join(
            kw.lower() for c in result.clusters for kw in c.keywords
        )
        assert 'zzqqxx' not in surfaced
        assert all('zzqqxx' not in c.topic.lower() for c in result.clusters)

    def test_compose_thesis_text_excludes_extracted_text(self, make_thesis):
        """Unit-level companion to the test above.

        The integration assertion has to reason about min_df/max_df to stay
        meaningful. This one does not: it reads the composed string directly,
        so it cannot pass for an unrelated reason.
        """
        t = make_thesis(
            'Sentiment Analysis of Tagalog Tweets',
            abstract='A BERT language model scores sentiment.',
            keywords=['nlp', 'sentiment'],
        )
        t.extracted_text = 'zzqqxx cover page boilerplate'
        t.save(update_fields=['extracted_text'])

        composed = _compose_thesis_text(t)

        assert 'zzqqxx' not in composed
        # And the three fields that SHOULD be there still are.
        assert 'Tagalog' in composed
        assert 'BERT' in composed
        assert 'sentiment' in composed

    def test_thesis_with_title_only_still_clusters(self, make_thesis):
        """Dropping a field narrows the per-document text, so the thin-input
        path needs to stay non-crashing: a row whose abstract and keywords are
        empty must still produce a well-formed result rather than an error
        envelope.
        """
        a = make_thesis('Blockchain Credential Verification Ledger', abstract='')
        b = make_thesis('Mobile Flutter Campus Navigation Routes', abstract='')
        for t in (a, b):
            t.abstract = ''
            t.keywords = []
            t.save(update_fields=['abstract', 'keywords'])

        result = analyze_topics([a, b], k=1)

        assert result.status == 'ok'
        assert result.total_theses == 2
        assert len(result.clusters) == 1
        assert result.clusters[0].thesis_count == 2

    def test_no_rule_matching_corpus_never_yields_a_raw_tfidf_label(self, make_thesis):
        """End-to-end guard on the label chain.

        Vocabulary chosen so no ``_TOPIC_RULES`` entry can fire, which forces
        every cluster down the fallback path. Each label must then be either
        an author keyword or the honest placeholder — never a bare corpus term
        like "Support" or "Yielded Overall".
        """
        prose = (
            'The findings yielded overall support for the approach, and '
            'respondents indicated substantial agreement throughout.'
        )
        for i in range(6):
            make_thesis(
                f'Ceramic Glaze Firing Schedules Volume {i}',
                abstract=f'{prose} Kiln atmosphere was varied across firings.',
                keywords=['kiln atmosphere'] if i % 2 == 0 else ['glaze chemistry'],
            )

        result = analyze_topics(get_topic_trends_queryset(), k=2)

        assert result.clusters
        permitted = {'Kiln Atmosphere', 'Glaze Chemistry', 'Other / Mixed Topics'}
        for cluster in result.clusters:
            assert cluster.topic in permitted, (
                f'label {cluster.topic!r} is neither an author keyword nor the '
                'honest placeholder — a raw TF-IDF term leaked into a label'
            )

    def test_real_shape_corpus_labels_each_cluster_honestly(self, make_thesis):
        """End-to-end, tokenizer included.

        Mirrors the shape of the actual repository: educational-game theses,
        web-based monitoring theses, and machine-learning theses. The
        educational-game cluster was the one being mislabelled 'AI Systems'.

        Boilerplate stays on 3 of 6 rows for the usual reason — a token present
        on every row is dropped by max_df=0.95, which would make the
        assertions pass for the wrong reason.
        """
        # 'learning' appears heavily in these two, which is what makes this
        # fixture a real reproduction rather than a clean-room one. An
        # educational-game thesis genuinely writes about learning outcomes and
        # learning objectives, so the ambiguous token ranks into the cluster's
        # top keywords — and under first-hit matching that single token sent
        # the whole cluster to 'AI Systems'.
        educational = [
            (
                'Interactive Educational Game for Elementary Mathematics Learning',
                'An interactive educational game built in Unity improves '
                'learning outcomes. Learning objectives are mapped to quiz '
                'rounds, and learning progress is tracked through flashcards '
                'so learning gaps in mathematics surface early.',
                ['educational game', 'gamification', 'unity'],
            ),
            (
                'Gamified Learning Module for Elementary Mathematics Drills',
                'A gamified tutorial module raises learning engagement. '
                'Learning outcomes improved across interactive quiz rounds, '
                'and learning retention in mathematics was measured after '
                'each learning session in Unity.',
                ['educational game', 'gamification', 'interactive'],
            ),
        ]
        web_based = [
            (
                'Web-Based Attendance Monitoring and Inventory Portal',
                'A web-based Laravel portal for monitoring attendance records '
                'and tracking supply inventory.',
                ['web-based', 'monitoring', 'inventory'],
            ),
            (
                'Web-Based Monitoring Dashboard for Supply Tracking',
                'A web-based Django dashboard for monitoring and tracking '
                'inventory across storerooms.',
                ['web-based', 'monitoring', 'tracking'],
            ),
        ]
        machine_learning = [
            (
                'Deep Learning Rainfall Prediction Using Neural Networks',
                'A deep learning neural classifier performs rainfall '
                'prediction from historical readings.',
                ['deep learning', 'neural', 'prediction'],
            ),
            (
                'Machine Learning Yield Prediction With Neural Classifiers',
                'A machine learning neural classifier performs yield '
                'prediction across seasons.',
                ['machine learning', 'neural', 'prediction'],
            ),
        ]

        rows = educational + web_based + machine_learning
        created = []
        for index, (title, abstract, keywords) in enumerate(rows):
            # Boilerplate on 3 of 6 rows only.
            prefix = f'{self.BOILERPLATE} ' if index % 2 == 0 else ''
            created.append(
                make_thesis(title, abstract=f'{prefix}{abstract}', keywords=keywords)
            )

        result = analyze_topics(get_topic_trends_queryset(), k=3)

        labels_by_thesis = {}
        for cluster in result.clusters:
            for thesis_id in cluster.thesis_ids:
                labels_by_thesis[thesis_id] = cluster

        # ── The bug: educational-game work must not read as machine learning
        edu_cluster = labels_by_thesis[str(created[0].id)]
        edu_keywords = [kw.lower() for kw in edu_cluster.keywords]

        # Self-check on the fixture. The whole point is that the ambiguous
        # token IS present and the label is STILL right. Without this, a
        # corpus where 'learning' happens not to rank would pass the assertion
        # below for the wrong reason, and the test would quietly stop guarding
        # the bug it was written for.
        assert any('learning' in kw for kw in edu_keywords), (
            "fixture no longer reproduces the bug: 'learning' is absent from "
            f'the educational cluster keywords {edu_cluster.keywords}, so '
            "'AI Systems' was never a candidate and this test proves nothing"
        )

        assert edu_cluster.topic == 'Educational Technology', (
            f'educational-game cluster labelled {edu_cluster.topic!r}; '
            f'keywords were {edu_cluster.keywords}'
        )
        assert edu_cluster.topic != 'AI Systems'

        # ── The hyphen: 'web-based' must survive the tokenizer AND match
        web_cluster = labels_by_thesis[str(created[2].id)]
        assert 'web-based' in [kw.lower() for kw in web_cluster.keywords], (
            "'web-based' did not survive tokenisation into the cluster's "
            f'keywords; got {web_cluster.keywords}'
        )
        assert web_cluster.topic == 'Web-Based Systems', (
            f'web-based cluster labelled {web_cluster.topic!r}; '
            f'keywords were {web_cluster.keywords}'
        )

        # ── No label may be a raw corpus artefact
        known_labels = {label for label, _ in _TOPIC_RULES}
        for cluster in result.clusters:
            assert cluster.topic in known_labels | {'Other / Mixed Topics'} | {
                kw.title() for row in rows for kw in row[2]
            }, (
                f'label {cluster.topic!r} is neither a rule label, an author '
                f'keyword, nor the honest placeholder; keywords {cluster.keywords}'
            )

    def test_boilerplate_terms_are_not_cluster_labels(self, make_thesis):
        """The user-visible half of the same bug: labels reach LandingPage."""
        for i in range(4):
            make_thesis(
                f'Inventory Tracking Platform {i}',
                abstract=f'{self.BOILERPLATE} A web inventory tracking tool.',
                keywords=['web', 'inventory'],
            )

        result = analyze_topics(get_topic_trends_queryset(), k=2)

        for cluster in result.clusters:
            lowered = cluster.topic.lower()
            for banned in ('capstone', 'dhvsu', 'honorio', 'ventura', 'bachelor'):
                assert banned not in lowered, (
                    f'cluster label {cluster.topic!r} is template boilerplate'
                )


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTopicTrendsEndpoint:
    @staticmethod
    def _bearer(user):
        from auth_service.services import issue_token_pair
        return issue_token_pair(user, request=None, remember_me=False).access_token

    def test_endpoint_requires_authentication(self, client):
        url = reverse('thesis-topic-trends')
        response = client.get(url)
        assert response.status_code == 401

    def test_endpoint_returns_envelope_shape(self, client, faculty_user, make_thesis):
        # Seed enough theses to produce real clusters.
        make_thesis(
            'AI-Powered Attendance Monitoring Using Facial Recognition',
            abstract='Deep learning facial recognition for student attendance.',
            keywords=['face recognition', 'attendance', 'deep learning'],
        )
        make_thesis(
            'IoT Greenhouse Monitoring with ESP32',
            abstract='Sensors over MQTT for greenhouse environment data.',
            keywords=['IoT', 'sensors', 'MQTT'],
        )
        make_thesis(
            'Web-Based Inventory Management System',
            abstract='A Laravel inventory system with barcode tracking.',
            keywords=['web', 'inventory', 'management'],
        )

        token = self._bearer(faculty_user)
        url = reverse('thesis-topic-trends')
        response = client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()

        # Envelope keys
        for key in (
            'total_theses', 'total_topics',
            'saturated_count', 'emerging_count', 'underexplored_count',
            'clusters', 'status',
        ):
            assert key in body, f'missing key: {key}'

        assert body['total_theses'] == 3
        assert body['total_topics'] >= 1
        assert body['status'] == 'ok'

        # Each cluster has the expected shape
        for c in body['clusters']:
            for k in ('cluster_id', 'topic', 'trend', 'thesis_count',
                      'keywords', 'sample_titles', 'thesis_ids'):
                assert k in c
            assert c['trend'] in (CLASS_SATURATED, CLASS_EMERGING, CLASS_UNDEREXPLORED)
            assert isinstance(c['keywords'], list)
            assert isinstance(c['thesis_ids'], list)
            assert c['thesis_count'] == len(c['thesis_ids'])

    def test_pending_and_rejected_excluded(self, client, faculty_user, make_thesis):
        approved = make_thesis(
            'Approved AI Thesis on Attendance',
            abstract='Real-time facial recognition.',
        )
        make_thesis(
            'Pending Thesis on Hidden Topic',
            abstract='This should not appear.',
            status=ThesisStatus.PENDING_REVIEW,
        )
        make_thesis(
            'Rejected Thesis on Other Topic',
            abstract='This should also not appear.',
            status=ThesisStatus.REJECTED,
        )

        token = self._bearer(faculty_user)
        url = reverse('thesis-topic-trends')
        response = client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()

        # Only the one APPROVED thesis should be analysed.
        assert body['total_theses'] == 1
        all_ids = [tid for c in body['clusters'] for tid in c['thesis_ids']]
        assert str(approved.id) in all_ids

    def test_empty_corpus_returns_status_empty(self, client, faculty_user):
        token = self._bearer(faculty_user)
        url = reverse('thesis-topic-trends')
        response = client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['total_theses'] == 0
        assert body['status'] == 'empty'
        assert body['clusters'] == []

    def test_endpoint_does_not_break_when_only_pending(self, client, faculty_user, make_thesis):
        make_thesis('Hidden', status=ThesisStatus.PENDING_REVIEW)
        make_thesis('Hidden 2', status=ThesisStatus.REJECTED)

        token = self._bearer(faculty_user)
        url = reverse('thesis-topic-trends')
        response = client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['total_theses'] == 0

    def test_invalid_k_param_rejected(self, client, faculty_user):
        token = self._bearer(faculty_user)
        url = reverse('thesis-topic-trends')
        response = client.get(f'{url}?k=abc', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'INVALID_K'


# ---------------------------------------------------------------------------
# Cross-endpoint consistency — /topic-trends/ vs /analytics/'s topic_summary
#
# Regression guard for the bug where each view built its own independent
# Thesis queryset (different .only() field sets, and critically no shared
# ordering), which let K-Means see the corpus in a different row order on
# each endpoint and silently produce different SATURATED / EMERGING /
# UNDEREXPLORED counts for identical underlying data. Both views must now
# route through the single get_topic_trends_queryset() helper.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsTrendConsistency:
    @staticmethod
    def _bearer(user):
        from auth_service.services import issue_token_pair
        return issue_token_pair(user, request=None, remember_me=False).access_token

    def _seed_dynamic_mode_corpus(self, make_thesis):
        """Seed >= 15 approved theses (the dynamic mean-relative threshold
        boundary) across varied keyword clusters, so K-Means has multiple
        non-trivial clusters and ordering-sensitivity has room to bite.
        """
        clusters = [
            (
                'Face Recognition Attendance System Using Deep Learning CNN',
                'A deep learning CNN facial recognition system for classroom attendance.',
                ['face recognition', 'deep learning', 'cnn', 'attendance'],
            ),
            (
                'IoT Greenhouse Monitoring with ESP32 Sensors over MQTT',
                'ESP32 sensors stream temperature and humidity data over MQTT.',
                ['iot', 'esp32', 'mqtt', 'sensors'],
            ),
            (
                'Web-Based Inventory Management System with Barcode Tracking',
                'A Laravel web inventory management application with barcode tracking.',
                ['web', 'inventory', 'management', 'laravel'],
            ),
            (
                'Blockchain-Based Academic Credential Verification Platform',
                'A Hyperledger blockchain platform for verifying academic credentials.',
                ['blockchain', 'hyperledger', 'credential', 'verification'],
            ),
            (
                'Mobile Flutter Application for Campus Navigation',
                'A cross-platform Flutter mobile app for navigating the campus.',
                ['mobile', 'flutter', 'android', 'ios'],
            ),
        ]
        # 15 theses: 3 rounds through the 5 topic clusters above so each
        # cluster has enough members to be meaningfully classified.
        titles = []
        for round_num in range(3):
            for title, abstract, keywords in clusters:
                titles.append(
                    make_thesis(f'{title} (v{round_num + 1})', abstract=abstract, keywords=keywords)
                )
        return titles

    def test_counts_match_between_endpoints(self, client, faculty_user, make_thesis):
        self._seed_dynamic_mode_corpus(make_thesis)

        token = self._bearer(faculty_user)
        trends_response = client.get(
            reverse('thesis-topic-trends'), HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        analytics_response = client.get(
            reverse('thesis-analytics'), HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        assert trends_response.status_code == 200
        assert analytics_response.status_code == 200

        trends_body = trends_response.json()
        analytics_body = analytics_response.json()
        topic_summary = analytics_body['topic_summary']

        assert trends_body['saturated_count'] == topic_summary['saturated_count']
        assert trends_body['emerging_count'] == topic_summary['emerging_count']
        assert trends_body['underexplored_count'] == topic_summary['underexplored_count']

        # Sanity check on scope: both endpoints must have analysed the same
        # number of theses, not just coincidentally agreeing counts.
        assert trends_body['total_theses'] == 15
        assert analytics_body['approved_theses'] == 15

    def test_counts_match_on_small_cold_start_corpus(self, client, faculty_user, make_thesis):
        # Below the 15-thesis dynamic-mode boundary — exercises the static
        # threshold branch instead.
        make_thesis(
            'AI-Powered Attendance Monitoring Using Facial Recognition',
            abstract='Deep learning facial recognition for student attendance.',
            keywords=['face recognition', 'attendance', 'deep learning'],
        )
        make_thesis(
            'IoT Greenhouse Monitoring with ESP32',
            abstract='Sensors over MQTT for greenhouse environment data.',
            keywords=['IoT', 'sensors', 'MQTT'],
        )
        make_thesis(
            'Web-Based Inventory Management System',
            abstract='A Laravel inventory system with barcode tracking.',
            keywords=['web', 'inventory', 'management'],
        )

        token = self._bearer(faculty_user)
        trends_body = client.get(
            reverse('thesis-topic-trends'), HTTP_AUTHORIZATION=f'Bearer {token}'
        ).json()
        analytics_body = client.get(
            reverse('thesis-analytics'), HTTP_AUTHORIZATION=f'Bearer {token}'
        ).json()
        topic_summary = analytics_body['topic_summary']

        assert trends_body['saturated_count'] == topic_summary['saturated_count']
        assert trends_body['emerging_count'] == topic_summary['emerging_count']
        assert trends_body['underexplored_count'] == topic_summary['underexplored_count']
        assert trends_body['total_theses'] == 3
        assert analytics_body['approved_theses'] == 3
