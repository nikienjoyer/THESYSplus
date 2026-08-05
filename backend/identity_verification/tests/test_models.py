"""Unit tests for identity_verification models.

Tests VerificationDocument and VerificationResult model behavior.
Per Requirements 13.1, 13.2, 13.3, 13.6, 16.2.
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from access_requests.models import AccessRequest
from identity_verification.models import VerificationDocument, VerificationResult


User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email='admin@pampangastateu.edu.ph',
        password='testpass123',
        first_name='Admin',
        last_name='User',
        role='administrator',
        is_active=True,
    )


@pytest.fixture
def access_request(db, user):
    """Create a test AccessRequest."""
    return AccessRequest.objects.create(
        email='student@pampangastateu.edu.ph',
        first_name='Juan',
        last_name='Dela Cruz',
        requested_role='student',
        status='pending',
    )


@pytest.mark.django_db
class TestVerificationResultModel:
    """Test VerificationResult model."""
    
    def test_create_verification_result_minimal(self, access_request):
        """Create VerificationResult with minimal required fields."""
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='processing',
        )
        
        assert result.id is not None
        assert result.access_request == access_request
        assert result.status == 'processing'
        assert result.extracted_fields == {}
        assert result.ocr_raw_text == ''
        assert result.ocr_confidence is None
        assert result.decision_reason == ''
        assert result.flagged_reasons == []
        assert result.rule_failures == []
        assert result.processor_version == 'mvp-1.0'
        assert result.processed_at is not None
    
    def test_create_verification_result_full(self, access_request):
        """Create VerificationResult with all fields populated."""
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='auto_approved',
            extracted_fields={
                'full_name': 'DELA CRUZ, JUAN',
                'school_name': 'Pampanga State University',
                'college': 'College of Computing Studies',
                'program': 'BS Information Technology',
                'program_raw': 'BSIT',
                'student_number': '2021-12345',
            },
            ocr_raw_text='PAMPANGA STATE UNIVERSITY\nCCS\nName: DELA CRUZ, JUAN\nProgram: BSIT',
            ocr_confidence=92.5,
            decision_reason='high_confidence',
            flagged_reasons=[],
            rule_failures=[],
            processor_version='mvp-1.0',
        )
        
        assert result.status == 'auto_approved'
        assert result.extracted_fields['full_name'] == 'DELA CRUZ, JUAN'
        assert result.extracted_fields['program'] == 'BS Information Technology'
        assert result.ocr_confidence == 92.5
        assert result.decision_reason == 'high_confidence'
    
    def test_verification_result_status_choices(self, access_request):
        """Test all valid status choices."""
        valid_statuses = [
            'processing',
            'auto_approved',
            'pending_manual_review',
            'rejected',
            'error',
        ]
        
        for status in valid_statuses:
            result = VerificationResult.objects.create(
                access_request=access_request,
                status=status,
            )
            assert result.status == status
            result.delete()
    
    def test_verification_result_one_to_one_constraint(self, access_request):
        """Test that only one VerificationResult can exist per AccessRequest."""
        VerificationResult.objects.create(
            access_request=access_request,
            status='processing',
        )
        
        # Attempting to create another VerificationResult for the same AccessRequest should fail
        with pytest.raises(IntegrityError):
            VerificationResult.objects.create(
                access_request=access_request,
                status='auto_approved',
            )
    
    def test_verification_result_update_existing(self, access_request):
        """Test updating an existing VerificationResult."""
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='processing',
            ocr_confidence=0.0,
        )
        
        # Update the result
        result.status = 'auto_approved'
        result.ocr_confidence = 92.5
        result.decision_reason = 'high_confidence'
        result.save()
        
        # Verify update
        result.refresh_from_db()
        assert result.status == 'auto_approved'
        assert result.ocr_confidence == 92.5
        assert result.decision_reason == 'high_confidence'
    
    def test_verification_result_jsonb_fields(self, access_request):
        """Test JSONB fields can store complex data."""
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='rejected',
            extracted_fields={
                'full_name': 'SANTOS, MARIA',
                'school_name': 'Pampanga State University',
                'college': 'College of Computing Studies',
                'program': 'BS Computer Science',
            },
            flagged_reasons=[
                'OCR confidence low',
                'Missing student number',
            ],
            rule_failures=[
                {
                    'field': 'program',
                    'expected': 'BS Information Technology',
                    'got': 'BS Computer Science',
                    'reason': 'Invalid program',
                }
            ],
        )
        
        # Verify JSONB fields are correctly stored and retrieved
        result.refresh_from_db()
        assert isinstance(result.extracted_fields, dict)
        assert result.extracted_fields['full_name'] == 'SANTOS, MARIA'
        assert isinstance(result.flagged_reasons, list)
        assert len(result.flagged_reasons) == 2
        assert isinstance(result.rule_failures, list)
        assert result.rule_failures[0]['field'] == 'program'
    
    def test_verification_result_str_representation(self, access_request):
        """Test string representation of VerificationResult."""
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='auto_approved',
        )
        
        str_repr = str(result)
        assert 'student@pampangastateu.edu.ph' in str_repr
        assert 'auto_approved' in str_repr
    
    def test_verification_result_cascade_delete(self, access_request):
        """Test that VerificationResult is deleted when AccessRequest is deleted."""
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='processing',
        )
        result_id = result.id
        
        # Delete the AccessRequest
        access_request.delete()
        
        # Verify VerificationResult is also deleted (cascade)
        assert not VerificationResult.objects.filter(id=result_id).exists()


@pytest.mark.django_db
class TestVerificationDocumentModel:
    """Test VerificationDocument model."""
    
    def test_create_verification_document(self, access_request):
        """Create VerificationDocument with required fields."""
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/path/to/student_id.jpg',
            mime_type='image/jpeg',
            sha256='a' * 64,
            size_bytes=1024,
        )
        
        assert doc.id is not None
        assert doc.access_request == access_request
        assert doc.file_path == '/path/to/student_id.jpg'
        assert doc.mime_type == 'image/jpeg'
        assert doc.sha256 == 'a' * 64
        assert doc.size_bytes == 1024
        assert doc.uploaded_at is not None
        assert doc.retention_purge_at is None
        assert doc.purged_at is None
    
    def test_verification_document_one_to_one_constraint(self, access_request):
        """Test that only one VerificationDocument can exist per AccessRequest."""
        VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/path/to/student_id.jpg',
            mime_type='image/jpeg',
            sha256='a' * 64,
            size_bytes=1024,
        )
        
        # Attempting to create another VerificationDocument for the same AccessRequest should fail
        with pytest.raises(IntegrityError):
            VerificationDocument.objects.create(
                access_request=access_request,
                file_path='/path/to/another_id.jpg',
                mime_type='image/jpeg',
                sha256='b' * 64,
                size_bytes=2048,
            )
    
    def test_verification_document_sha256_index(self, access_request):
        """Test that sha256 field is indexed for anti-replay detection."""
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/path/to/student_id.jpg',
            mime_type='image/jpeg',
            sha256='c' * 64,
            size_bytes=1024,
        )
        
        # Query by sha256 should be efficient (uses index)
        found_doc = VerificationDocument.objects.get(sha256='c' * 64)
        assert found_doc.id == doc.id
    
    def test_verification_document_str_representation(self, access_request):
        """Test string representation of VerificationDocument."""
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/path/to/student_id.jpg',
            mime_type='image/jpeg',
            sha256='d' * 64,
            size_bytes=1024,
        )
        
        str_repr = str(doc)
        assert 'student@pampangastateu.edu.ph' in str_repr
        assert 'dddddddd' in str_repr  # First 8 chars of sha256
    
    def test_verification_document_cascade_delete(self, access_request):
        """Test that VerificationDocument is deleted when AccessRequest is deleted."""
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/path/to/student_id.jpg',
            mime_type='image/jpeg',
            sha256='e' * 64,
            size_bytes=1024,
        )
        doc_id = doc.id
        
        # Delete the AccessRequest
        access_request.delete()
        
        # Verify VerificationDocument is also deleted (cascade)
        assert not VerificationDocument.objects.filter(id=doc_id).exists()
    
    def test_verification_document_nullable_file_path(self, access_request):
        """Test that file_path can be null (after purge)."""
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path=None,  # Simulating purged file
            mime_type='image/jpeg',
            sha256='f' * 64,
            size_bytes=1024,
        )
        
        assert doc.file_path is None
        assert doc.sha256 == 'f' * 64  # SHA256 is preserved even after purge


@pytest.mark.django_db
class TestVerificationModelsRelationship:
    """Test relationship between VerificationDocument and VerificationResult."""
    
    def test_both_models_linked_to_same_access_request(self, access_request):
        """Test that both models can be linked to the same AccessRequest."""
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/path/to/student_id.jpg',
            mime_type='image/jpeg',
            sha256='g' * 64,
            size_bytes=1024,
        )
        
        result = VerificationResult.objects.create(
            access_request=access_request,
            status='auto_approved',
            ocr_confidence=92.5,
        )
        
        # Verify both are linked to the same AccessRequest
        assert doc.access_request == result.access_request
        
        # Verify reverse relationships
        assert access_request.verification_document == doc
        assert access_request.verification_result == result
    
    def test_access_request_without_verification_data(self, access_request):
        """Test AccessRequest without verification data (legacy flow)."""
        # No VerificationDocument or VerificationResult created
        
        # Verify reverse relationships return None
        with pytest.raises(VerificationDocument.DoesNotExist):
            _ = access_request.verification_document
        
        with pytest.raises(VerificationResult.DoesNotExist):
            _ = access_request.verification_result
