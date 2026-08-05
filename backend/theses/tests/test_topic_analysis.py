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
    KEYWORDS_PER_CLUSTER,
    _classify_trend,
    _label_cluster,
    analyze_topics,
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

class TestLabelCluster:
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

    def test_unknown_falls_back_to_top_keyword(self):
        # No rule matches "robotics" → fallback uses the top keyword.
        assert _label_cluster(['robotics', 'arm']) == 'Robotics'

    def test_empty_keywords_returns_general(self):
        assert _label_cluster([]) == 'General Research'


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
