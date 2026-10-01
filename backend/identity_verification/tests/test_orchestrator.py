"""Integration tests for VerificationOrchestrator.

Tests the full verification pipeline from AccessRequest to VerificationResult.
Per Requirements 7.1, 13.2, 13.6, 17.1, 17.2.
"""

import pytest
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model

from access_requests.models import AccessRequest
from identity_verification.models import VerificationDocument, VerificationResult
from identity_verification.services.orchestrator import VerificationOrchestrator
from identity_verification.services.ocr_extractor import OCRResult
from identity_verification.types import ExtractedFields


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
        email='202112345@pampangastateu.edu.ph',
        first_name='Juan',
        last_name='Dela Cruz',
        requested_role='student',
        status='pending',
    )


@pytest.fixture
def verification_document(db, access_request):
    """Create a test VerificationDocument."""
    return VerificationDocument.objects.create(
        access_request=access_request,
        file_path='/path/to/student_id.jpg',
        mime_type='image/jpeg',
        sha256='a' * 64,
        size_bytes=1024,
    )


@pytest.fixture
def orchestrator():
    """Create a VerificationOrchestrator instance."""
    return VerificationOrchestrator()


@pytest.mark.django_db
class TestVerificationOrchestratorAutoApproved:
    """Test cases that should result in AUTO_APPROVED."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_auto_approved_high_confidence_valid_fields(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """High OCR confidence + valid fields → AUTO_APPROVED."""
        # Mock OCR extraction with realistic Student ID format
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
COLLEGE OF COMPUTING STUDIES
Name: DELA CRUZ, JUAN MIGUEL
Program: BS INFORMATION TECHNOLOGY
Student No: 2021-12345""",
            overall_confidence=92.5,
            success=True,
            error=None,
        )
        
        # Run verification
        result = orchestrator.verify_request(str(access_request.id))
        
        # Verify VerificationResult
        assert result.status == 'auto_approved'
        assert result.decision_reason == 'high_confidence'
        assert result.ocr_confidence == 92.5
        assert result.extracted_fields['full_name'] == 'DELA CRUZ, JUAN MIGUEL'
        assert result.extracted_fields['school_name'] == 'Pampanga State University'  # Normalized to title case
        assert result.extracted_fields['college'] == 'College of Computing Studies'
        assert result.extracted_fields['program'] == 'BS Information Technology'
        assert result.extracted_fields['student_number'] == '2021-12345'  # Keeps dash format
        assert len(result.flagged_reasons) == 0
        
        # Verify AccessRequest status updated
        access_request.refresh_from_db()
        # Orchestrator sets 'processing' for auto_approved; the view layer
        # calls approve_request() which transitions to 'approved'.
        assert access_request.status == 'processing'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_auto_approved_exactly_75_percent(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Exactly 75% confidence → AUTO_APPROVED."""
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
CCS
Name: DELA CRUZ, JUAN
Student No: 2021-12345
Program: BS COMPUTER SCIENCE""",
            overall_confidence=75.0,
            success=True,
            error=None,
        )
        
        result = orchestrator.verify_request(str(access_request.id))
        
        assert result.status == 'auto_approved'
        assert result.ocr_confidence == 75.0

        access_request.refresh_from_db()
        # Orchestrator sets 'processing' for auto_approved; view layer transitions to 'approved'.
        assert access_request.status == 'processing'


@pytest.mark.django_db
class TestVerificationOrchestratorPendingManualReview:
    """Test cases that should result in PENDING_MANUAL_REVIEW."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_pending_medium_confidence(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Medium OCR confidence (60-75%) → PENDING_MANUAL_REVIEW."""
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
CCS
Name: GARCIA, ANA
Program: BS INFORMATION SYSTEM""",
            overall_confidence=65.0,
            success=True,
            error=None,
        )
        
        result = orchestrator.verify_request(str(access_request.id))
        
        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'ocr_medium_confidence'
        assert result.ocr_confidence == 65.0
        assert 'OCR confidence medium' in result.flagged_reasons[0]
        
        access_request.refresh_from_db()
        assert access_request.status == 'pending'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_pending_low_confidence(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Low OCR confidence (<60%) → PENDING_MANUAL_REVIEW."""
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
COLLEGE OF COMPUTING STUDIES
Name: REYES, PEDRO
Program: BS INFORMATION TECHNOLOGY""",
            overall_confidence=45.0,
            success=True,
            error=None,
        )
        
        result = orchestrator.verify_request(str(access_request.id))
        
        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'ocr_low_confidence'
        assert result.ocr_confidence == 45.0
        assert 'OCR confidence low' in result.flagged_reasons[0]
        
        access_request.refresh_from_db()
        assert access_request.status == 'pending'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_pending_missing_fields(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Blurry PSU ID — school_name and college missing but PSU signal present
        → PENDING_MANUAL_REVIEW (incomplete_extraction)."""
        mock_extract.return_value = OCRResult(
            raw_text="PAMPANGA STATE\nLOPEZ, CARLOS\nBS INFORMATION SYSTEM",
            overall_confidence=85.0,  # High confidence
            success=True,
            error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'incomplete_extraction'
        assert 'Missing required field: school_name' in result.flagged_reasons

        access_request.refresh_from_db()
        assert access_request.status == 'pending'


@pytest.mark.django_db
class TestVerificationOrchestratorRejected:
    """Test cases that should result in REJECTED."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_rejected_wrong_institution(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Wrong institution with no PSU signals → REJECTED (invalid_institution)."""
        mock_extract.return_value = OCRResult(
            raw_text="""UNIVERSITY OF THE PHILIPPINES
COLLEGE OF COMPUTING STUDIES
Name: TAN, MIGUEL
Program: BS COMPUTER SCIENCE""",
            overall_confidence=90.0,
            success=True,
            error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        # FieldExtractor can't match "University of the Philippines" to PSU,
        # school_name is None.  OCR text has no PSU/DHVSU signals → REJECTED.
        assert result.status == 'rejected'
        assert result.decision_reason == 'invalid_institution'
        assert 'No PSU/DHVSU institution signals detected in document' in result.flagged_reasons

        access_request.refresh_from_db()
        assert access_request.status == 'denied'
        # No review stamp: request-access gives an ID-check rejection its try back.
        assert access_request.reviewed_at is None

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_rejected_wrong_college(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """PSU institution + unknown college + valid CCS program → AUTO_APPROVED.

        'COLLEGE OF ENGINEERING' is not extracted as a valid CCS college (college=None).
        However, 'PAMPANGA STATE UNIVERSITY' IS present, program='BS Information Technology'
        is valid, and the college can be inferred from the CCS program.
        Result: rules pass → AUTO_APPROVED (at high OCR confidence).
        """
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
COLLEGE OF ENGINEERING
Name: DELA CRUZ, JUAN
Student No: 2021-12345
Program: BS INFORMATION TECHNOLOGY""",
            overall_confidence=88.0,
            success=True,
            error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        # College is inferred from valid CCS program → rules pass → auto_approved
        assert result.status == 'auto_approved'
        assert result.decision_reason == 'high_confidence'

        access_request.refresh_from_db()
        # Note: orchestrator sets 'processing' for auto_approved; the view
        # layer is responsible for calling approve_request() → 'approved'.
        assert access_request.status == 'processing'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_rejected_wrong_program(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Wrong program → REJECTED."""
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
CCS
Name: CRUZ, ANTONIO
Program: BS BIOLOGY""",
            overall_confidence=92.0,
            success=True,
            error=None,
        )
        
        result = orchestrator.verify_request(str(access_request.id))
        
        assert result.status == 'rejected'
        assert result.decision_reason == 'rule_validation_failed'
        assert 'Invalid program' in result.flagged_reasons[0]
        
        access_request.refresh_from_db()
        assert access_request.status == 'denied'


@pytest.mark.django_db
class TestVerificationOrchestratorError:
    """Test error handling."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_ocr_extraction_failed(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """OCR extraction failure → ERROR."""
        mock_extract.return_value = OCRResult(
            raw_text="",
            overall_confidence=0.0,
            success=False,
            error="Tesseract not installed",
        )
        
        result = orchestrator.verify_request(str(access_request.id))
        
        assert result.status == 'error'
        assert 'OCR extraction failed' in result.decision_reason
        assert result.ocr_confidence == 0.0
        
        access_request.refresh_from_db()
        assert access_request.status == 'pending'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_unexpected_exception(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Unexpected exception → ERROR and re-raised."""
        # Exception happens during OCR extraction
        mock_extract.side_effect = Exception("Unexpected error")
        
        # The exception is caught, error status is saved, then re-raised
        with pytest.raises(Exception, match="Unexpected error"):
            orchestrator.verify_request(str(access_request.id))
        
        # Note: Due to transaction rollback on exception, the VerificationResult
        # with error status may not be persisted. This is acceptable behavior
        # as the exception will be logged and handled by the caller.


@pytest.mark.django_db
class TestVerificationOrchestratorIdempotency:
    """Test idempotent behavior."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_rerun_verification_updates_existing_result(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Re-running verification updates existing VerificationResult."""
        # First run
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
CCS
Name: DELA CRUZ, JUAN
Program: BS INFORMATION TECHNOLOGY""",
            overall_confidence=92.0,
            success=True,
            error=None,
        )
        
        result1 = orchestrator.verify_request(str(access_request.id))
        result1_id = result1.id
        
        # Second run (same request)
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
CCS
Name: DELA CRUZ, JUAN
Program: BS INFORMATION TECHNOLOGY""",
            overall_confidence=95.0,  # Different confidence
            success=True,
            error=None,
        )
        
        result2 = orchestrator.verify_request(str(access_request.id))
        
        # Should update existing result, not create new one
        assert result2.id == result1_id
        assert result2.ocr_confidence == 95.0
        
        # Verify only one VerificationResult exists
        assert VerificationResult.objects.filter(access_request=access_request).count() == 1


@pytest.mark.django_db
class TestVerificationOrchestratorExtractedFields:
    """Test extracted fields serialization."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_extracted_fields_serialization(
        self,
        mock_extract,
        orchestrator,
        access_request,
        verification_document,
    ):
        """Extracted fields are correctly serialized to JSON."""
        mock_extract.return_value = OCRResult(
            raw_text="""PAMPANGA STATE UNIVERSITY
COLLEGE OF COMPUTING STUDIES
Name: SANTOS, MARIA CLARA
Program: BSIT
Student No: 2022-67890""",
            overall_confidence=88.0,
            success=True,
            error=None,
        )
        
        result = orchestrator.verify_request(str(access_request.id))
        
        # Verify all fields are present
        assert result.extracted_fields['full_name'] == 'SANTOS, MARIA CLARA'
        assert result.extracted_fields['school_name'] == 'Pampanga State University'  # Normalized
        assert result.extracted_fields['college'] == 'College of Computing Studies'
        assert result.extracted_fields['program'] == 'BS Information Technology'  # Normalized
        assert result.extracted_fields['program_raw'] == 'BSIT'  # Original
        assert result.extracted_fields['student_number'] == '2022-67890'  # Keeps dash format
        
        # Verify JSON serialization works
        result.refresh_from_db()
        assert isinstance(result.extracted_fields, dict)
        assert result.extracted_fields['program'] == 'BS Information Technology'


VALID_PSU_DOCUMENT = """PAMPANGA STATE UNIVERSITY
Name: {name}
Student No: 2021-12345
BACHELOR OF SCIENCE IN INFORMATION SYSTEMS"""


@pytest.mark.django_db
class TestVerificationOrchestratorNameMatch:
    """The registered name must appear on the document (applicant: Juan Dela Cruz)."""

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_someone_elses_document_goes_to_manual_review(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        """The reported case: a valid COR, but it belongs to someone else."""
        mock_extract.return_value = OCRResult(
            raw_text=VALID_PSU_DOCUMENT.format(name='AQUINO, LIZA MARIE PEREZ'),
            overall_confidence=89.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'name_mismatch'
        assert result.flagged_reasons == [
            'Name on document does not match the registered name (Juan Dela Cruz)',
        ]
        access_request.refresh_from_db()
        assert access_request.status == 'pending'

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_own_document_is_still_auto_approved(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        mock_extract.return_value = OCRResult(
            raw_text=VALID_PSU_DOCUMENT.format(name='DELA CRUZ, JUAN MIGUEL'),
            overall_confidence=89.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'auto_approved'
        assert result.decision_reason == 'high_confidence'

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_mismatch_is_flagged_on_an_existing_manual_review(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        mock_extract.return_value = OCRResult(
            raw_text=VALID_PSU_DOCUMENT.format(name='AQUINO, LIZA'),
            overall_confidence=65.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'ocr_medium_confidence'
        assert result.flagged_reasons[-1] == (
            'Name on document does not match the registered name (Juan Dela Cruz)'
        )

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_rejection_is_not_softened_by_a_name_mismatch(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        mock_extract.return_value = OCRResult(
            raw_text='UNIVERSITY OF THE PHILIPPINES\nName: TAN, MIGUEL\nProgram: BS COMPUTER SCIENCE',
            overall_confidence=90.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'rejected'
        access_request.refresh_from_db()
        assert access_request.status == 'denied'


@pytest.mark.django_db
class TestVerificationOrchestratorStudentNumber:
    """The student number in the email must appear on the document."""

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_another_students_email_goes_to_manual_review(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        """The reported case: the applicant's own ID, another student's email."""
        access_request.email = '202199999@pampangastateu.edu.ph'
        access_request.save(update_fields=['email'])
        mock_extract.return_value = OCRResult(
            raw_text=VALID_PSU_DOCUMENT.format(name='DELA CRUZ, JUAN MIGUEL'),
            overall_confidence=89.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'student_number_mismatch'
        assert result.flagged_reasons == [
            'Student number in the email (202199999) was not found on the document',
        ]
        access_request.refresh_from_db()
        assert access_request.status == 'pending'

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_name_and_number_mismatch_are_both_flagged(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        access_request.email = '202199999@pampangastateu.edu.ph'
        access_request.save(update_fields=['email'])
        mock_extract.return_value = OCRResult(
            raw_text=VALID_PSU_DOCUMENT.format(name='REYES, MARIA'),
            overall_confidence=89.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'pending_manual_review'
        assert result.decision_reason == 'name_mismatch'
        assert result.flagged_reasons == [
            'Name on document does not match the registered name (Juan Dela Cruz)',
            'Student number in the email (202199999) was not found on the document',
        ]

    @patch('identity_verification.services.orchestrator.OCRExtractor.extract')
    def test_ten_digit_number_is_read_from_the_full_text(
        self, mock_extract, orchestrator, access_request, verification_document,
    ):
        """PSU numbers have ten digits, and the check reads them from the OCR
        text itself, not from the label-based extracted field."""
        access_request.email = '2023123456@pampangastateu.edu.ph'
        access_request.save(update_fields=['email'])
        mock_extract.return_value = OCRResult(
            raw_text=(
                'PAMPANGA STATE UNIVERSITY\nName: DELA CRUZ, JUAN\n'
                'Student No: 2023123456\nBACHELOR OF SCIENCE IN INFORMATION SYSTEMS'
            ),
            overall_confidence=89.0, success=True, error=None,
        )

        result = orchestrator.verify_request(str(access_request.id))

        assert result.status == 'auto_approved'
