"""Test audit logging for identity verification events.

Per Requirement 17 (Auditability), this test suite verifies that all
verification activities produce the expected audit log entries.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from django.test import TestCase

from access_requests.models import AccessRequest
from audit.models import AuditLog
from identity_verification.models import VerificationDocument, VerificationResult
from identity_verification.services.orchestrator import VerificationOrchestrator
from identity_verification.services import audit
from identity_verification.services.ocr_extractor import OCRResult
from identity_verification.services.field_extractor import ExtractedFields
from identity_verification.services.decision_engine import Decision
from identity_verification.validators.rule_validator import RuleResult, RuleFailure


@pytest.mark.django_db
class TestVerificationAuditEvents:
    """Test audit logging for verification pipeline events."""
    
    def test_verification_started_event(self):
        """WHEN verification starts, THEN access_request.verification.started event is created."""
        AuditLog.objects.all().delete()
        
        # Call audit function directly
        audit.log_verification_started(
            access_request_id='test-request-id',
            document_sha256='abc123def456',
        )
        
        # Verify audit log entry
        logs = AuditLog.objects.filter(event_type='access_request.verification.started')
        assert logs.count() == 1
        
        log = logs.first()
        assert log.success is True
        assert log.actor_user is None  # System-initiated
        assert log.target_user is None
        assert log.metadata['access_request_id'] == 'test-request-id'
        assert log.metadata['document_sha256'] == 'abc123def456'
    
    def test_verification_completed_event(self):
        """WHEN verification completes, THEN access_request.verification.completed event is created."""
        AuditLog.objects.all().delete()
        
        # Call audit function directly
        audit.log_verification_completed(
            access_request_id='test-request-id',
            decision='auto_approved',
            processor_version='mvp-1.0',
        )
        
        # Verify audit log entry
        logs = AuditLog.objects.filter(event_type='access_request.verification.completed')
        assert logs.count() == 1
        
        log = logs.first()
        assert log.success is True
        assert log.metadata['access_request_id'] == 'test-request-id'
        assert log.metadata['decision'] == 'auto_approved'
        assert log.metadata['processor_version'] == 'mvp-1.0'
    
    def test_verification_auto_approved_event(self):
        """WHEN request is AUTO_APPROVED, THEN access_request.verification.auto_approved event is created."""
        AuditLog.objects.all().delete()
        
        # Call audit function directly
        audit.log_verification_auto_approved(
            access_request_id='test-request-id',
            confidence_summary={
                'ocr_confidence': 85.5,
                'rule_validation': 'passed',
            },
        )
        
        # Verify audit log entry
        logs = AuditLog.objects.filter(event_type='access_request.verification.auto_approved')
        assert logs.count() == 1
        
        log = logs.first()
        assert log.success is True
        assert log.metadata['access_request_id'] == 'test-request-id'
        assert log.metadata['confidence_summary']['ocr_confidence'] == 85.5
        assert log.metadata['confidence_summary']['rule_validation'] == 'passed'
    
    def test_verification_pending_review_event(self):
        """WHEN request is PENDING_MANUAL_REVIEW, THEN access_request.verification.pending_review event is created."""
        AuditLog.objects.all().delete()
        
        # Call audit function directly
        audit.log_verification_pending_review(
            access_request_id='test-request-id',
            flagged_reasons=['ocr_medium_confidence', 'duplicate_document'],
        )
        
        # Verify audit log entry
        logs = AuditLog.objects.filter(event_type='access_request.verification.pending_review')
        assert logs.count() == 1
        
        log = logs.first()
        assert log.success is True
        assert log.metadata['access_request_id'] == 'test-request-id'
        assert log.metadata['flagged_reasons'] == ['ocr_medium_confidence', 'duplicate_document']
    
    def test_verification_rejected_event(self):
        """WHEN request is REJECTED, THEN access_request.verification.rejected event is created."""
        AuditLog.objects.all().delete()
        
        # Call audit function directly
        audit.log_verification_rejected(
            access_request_id='test-request-id',
            decision_reason='rule_validation_failed',
            rule_failures=[
                {
                    'field': 'institution',
                    'reason': 'wrong_institution',
                    'expected': 'Pampanga State University',
                    'actual': 'Other University',
                }
            ],
        )
        
        # Verify audit log entry
        logs = AuditLog.objects.filter(event_type='access_request.verification.rejected')
        assert logs.count() == 1
        
        log = logs.first()
        assert log.success is False  # Rejection is a failure outcome
        assert log.metadata['access_request_id'] == 'test-request-id'
        assert log.metadata['decision_reason'] == 'rule_validation_failed'
        assert len(log.metadata['rule_failures']) == 1
        assert log.metadata['rule_failures'][0]['field'] == 'institution'
    
    def test_verification_error_event(self):
        """WHEN verification error occurs, THEN access_request.verification.error event is created."""
        AuditLog.objects.all().delete()
        
        # Call audit function directly
        audit.log_verification_error(
            access_request_id='test-request-id',
            error_type='OCRExtractionError',
            error_message='Tesseract not found',
        )
        
        # Verify audit log entry
        logs = AuditLog.objects.filter(event_type='access_request.verification.error')
        assert logs.count() == 1
        
        log = logs.first()
        assert log.success is False  # Error is a failure outcome
        assert log.metadata['access_request_id'] == 'test-request-id'
        assert log.metadata['error_type'] == 'OCRExtractionError'
        assert log.metadata['error_message'] == 'Tesseract not found'


@pytest.mark.django_db
class TestOrchestratorAuditIntegration:
    """Test that orchestrator writes audit events at correct points."""
    
    @patch('identity_verification.services.orchestrator.OCRExtractor')
    @patch('identity_verification.services.orchestrator.FieldExtractor')
    @patch('identity_verification.services.orchestrator.RuleValidator')
    @patch('identity_verification.services.orchestrator.DecisionEngine')
    def test_orchestrator_writes_audit_events_on_success(
        self,
        mock_decision_engine_class,
        mock_rule_validator_class,
        mock_field_extractor_class,
        mock_ocr_extractor_class,
    ):
        """WHEN orchestrator runs successfully, THEN all audit events are written."""
        AuditLog.objects.all().delete()
        
        # Create test data
        access_request = AccessRequest.objects.create(
            first_name='Juan',
            last_name='Dela Cruz',
            email='juan.delacruz@test.edu',
            requested_role='student',
            status='processing',
        )
        
        verification_doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/tmp/test.jpg',
            mime_type='image/jpeg',
            sha256='abc123def456',
            size_bytes=1024,
        )
        
        # Mock OCR extraction
        mock_ocr_extractor = MagicMock()
        mock_ocr_result = OCRResult(
            success=True,
            raw_text='Pampanga State University\nCollege of Computing Studies\nBS Information System',
            overall_confidence=85.0,
            error=None,
        )
        mock_ocr_extractor.extract.return_value = mock_ocr_result
        mock_ocr_extractor_class.return_value = mock_ocr_extractor
        
        # Mock field extraction
        mock_field_extractor = MagicMock()
        mock_extracted_fields = ExtractedFields(
            full_name='Juan Dela Cruz',
            school_name='Pampanga State University',
            college='College of Computing Studies',
            program='BS Information System',
            program_raw='BSIS',
            student_number='2021-12345',
        )
        mock_field_extractor.extract.return_value = mock_extracted_fields
        mock_field_extractor_class.return_value = mock_field_extractor
        
        # Mock rule validation (passed)
        mock_rule_validator = MagicMock()
        mock_rule_result = RuleResult(passed=True, failures=[])
        mock_rule_validator.validate.return_value = mock_rule_result
        mock_rule_validator_class.return_value = mock_rule_validator
        
        # Mock decision engine (auto-approved)
        mock_decision_engine = MagicMock()
        mock_decision = Decision(
            status='auto_approved',
            reason='high_confidence',
            confidence_summary={'ocr_confidence': 85.0},
            flagged_reasons=[],
        )
        mock_decision_engine.decide_mvp.return_value = mock_decision
        mock_decision_engine_class.return_value = mock_decision_engine
        
        # Run orchestrator
        orchestrator = VerificationOrchestrator()
        result = orchestrator.verify_request(str(access_request.id))
        
        # Verify audit events were written
        # 1. verification.started
        started_logs = AuditLog.objects.filter(
            event_type='access_request.verification.started'
        )
        assert started_logs.count() == 1
        assert started_logs.first().metadata['document_sha256'] == 'abc123def456'
        
        # 2. verification.auto_approved
        auto_approved_logs = AuditLog.objects.filter(
            event_type='access_request.verification.auto_approved'
        )
        assert auto_approved_logs.count() == 1
        assert auto_approved_logs.first().metadata['confidence_summary']['ocr_confidence'] == 85.0
        
        # 3. verification.completed
        completed_logs = AuditLog.objects.filter(
            event_type='access_request.verification.completed'
        )
        assert completed_logs.count() == 1
        assert completed_logs.first().metadata['decision'] == 'auto_approved'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor')
    @patch('identity_verification.services.orchestrator.FieldExtractor')
    @patch('identity_verification.services.orchestrator.RuleValidator')
    @patch('identity_verification.services.orchestrator.DecisionEngine')
    def test_orchestrator_writes_audit_events_on_rejection(
        self,
        mock_decision_engine_class,
        mock_rule_validator_class,
        mock_field_extractor_class,
        mock_ocr_extractor_class,
    ):
        """WHEN orchestrator rejects request, THEN rejection audit events are written."""
        AuditLog.objects.all().delete()
        
        # Create test data
        access_request = AccessRequest.objects.create(
            first_name='Juan',
            last_name='Dela Cruz',
            email='juan.delacruz@test.edu',
            requested_role='student',
            status='processing',
        )
        
        verification_doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/tmp/test.jpg',
            mime_type='image/jpeg',
            sha256='abc123def456',
            size_bytes=1024,
        )
        
        # Mock OCR extraction
        mock_ocr_extractor = MagicMock()
        mock_ocr_result = OCRResult(
            success=True,
            raw_text='Other University\nCollege of Computing Studies\nBS Information System',
            overall_confidence=85.0,
            error=None,
        )
        mock_ocr_extractor.extract.return_value = mock_ocr_result
        mock_ocr_extractor_class.return_value = mock_ocr_extractor
        
        # Mock field extraction
        mock_field_extractor = MagicMock()
        mock_extracted_fields = ExtractedFields(
            full_name='Juan Dela Cruz',
            school_name='Other University',
            college='College of Computing Studies',
            program='BS Information System',
            program_raw='BSIS',
            student_number='2021-12345',
        )
        mock_field_extractor.extract.return_value = mock_extracted_fields
        mock_field_extractor_class.return_value = mock_field_extractor
        
        # Mock rule validation (failed)
        mock_rule_validator = MagicMock()
        mock_rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Institution not allowed',
                    expected='Pampanga State University',
                    actual='Other University',
                )
            ]
        )
        mock_rule_validator.validate.return_value = mock_rule_result
        mock_rule_validator_class.return_value = mock_rule_validator
        
        # Mock decision engine (rejected)
        mock_decision_engine = MagicMock()
        mock_decision = Decision(
            status='rejected',
            reason='rule_validation_failed',
            confidence_summary={},
            flagged_reasons=['wrong_institution'],
        )
        mock_decision_engine.decide_mvp.return_value = mock_decision
        mock_decision_engine_class.return_value = mock_decision_engine
        
        # Run orchestrator
        orchestrator = VerificationOrchestrator()
        result = orchestrator.verify_request(str(access_request.id))
        
        # Verify audit events were written
        # 1. verification.started
        started_logs = AuditLog.objects.filter(
            event_type='access_request.verification.started'
        )
        assert started_logs.count() == 1
        
        # 2. verification.rejected
        rejected_logs = AuditLog.objects.filter(
            event_type='access_request.verification.rejected'
        )
        assert rejected_logs.count() == 1
        assert rejected_logs.first().metadata['decision_reason'] == 'rule_validation_failed'
        assert len(rejected_logs.first().metadata['rule_failures']) == 1
        
        # 3. verification.completed
        completed_logs = AuditLog.objects.filter(
            event_type='access_request.verification.completed'
        )
        assert completed_logs.count() == 1
        assert completed_logs.first().metadata['decision'] == 'rejected'
    
    @patch('identity_verification.services.orchestrator.OCRExtractor')
    def test_orchestrator_writes_audit_events_on_error(
        self,
        mock_ocr_extractor_class,
    ):
        """WHEN orchestrator encounters error, THEN error audit event is written."""
        AuditLog.objects.all().delete()
        
        # Create test data
        access_request = AccessRequest.objects.create(
            first_name='Juan',
            last_name='Dela Cruz',
            email='juan.delacruz@test.edu',
            requested_role='student',
            status='processing',
        )
        
        verification_doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path='/tmp/test.jpg',
            mime_type='image/jpeg',
            sha256='abc123def456',
            size_bytes=1024,
        )
        
        # Mock OCR extraction failure
        mock_ocr_extractor = MagicMock()
        mock_ocr_result = OCRResult(
            success=False,
            raw_text='',
            overall_confidence=0.0,
            error='Tesseract not found',
        )
        mock_ocr_extractor.extract.return_value = mock_ocr_result
        mock_ocr_extractor_class.return_value = mock_ocr_extractor
        
        # Run orchestrator
        orchestrator = VerificationOrchestrator()
        result = orchestrator.verify_request(str(access_request.id))
        
        # Verify audit events were written
        # 1. verification.started
        started_logs = AuditLog.objects.filter(
            event_type='access_request.verification.started'
        )
        assert started_logs.count() == 1
        
        # 2. verification.error
        error_logs = AuditLog.objects.filter(
            event_type='access_request.verification.error'
        )
        assert error_logs.count() == 1
        assert error_logs.first().metadata['error_type'] == 'OCRExtractionError'
        assert 'Tesseract not found' in error_logs.first().metadata['error_message']
