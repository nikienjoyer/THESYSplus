"""Verification orchestrator for identity verification pipeline.

Coordinates the full verification workflow from file validation to decision.
Per Requirements 7.1, 13.2, 13.6, 17.1, 17.2.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from django.db import transaction

from access_requests.models import AccessRequest
from ..models import VerificationDocument, VerificationResult
from ..services.ocr_extractor import OCRExtractor
from ..services.field_extractor import FieldExtractor
from ..services.decision_engine import DecisionEngine
from ..services import audit
from ..validators.rule_validator import RuleValidator


class VerificationOrchestrator:
    """Orchestrates the identity verification pipeline.
    
    Pipeline:
    1. Load AccessRequest and VerificationDocument
    2. Run OCR extraction
    3. Extract structured fields
    4. Validate against rules
    5. Make decision
    6. Write VerificationResult
    7. Update AccessRequest status
    
    MVP scope: Synchronous processing only (no Celery/Redis).
    """
    
    def __init__(self):
        """Initialize orchestrator with service dependencies."""
        self.ocr_extractor = OCRExtractor(timeout_seconds=10)
        self.field_extractor = FieldExtractor()
        self.rule_validator = RuleValidator()
        self.decision_engine = DecisionEngine()
    
    @transaction.atomic
    def verify_request(self, access_request_id: str) -> VerificationResult:
        """Run full verification pipeline for an access request.
        
        Args:
            access_request_id: UUID of AccessRequest to verify
            
        Returns:
            VerificationResult with decision and metadata
            
        Raises:
            AccessRequest.DoesNotExist: If request not found
            VerificationDocument.DoesNotExist: If document not found
        """
        # Step 1: Load AccessRequest and VerificationDocument
        access_request = AccessRequest.objects.get(id=access_request_id)
        verification_doc = VerificationDocument.objects.get(
            access_request=access_request
        )
        
        # Audit: Log verification started
        audit.log_verification_started(
            access_request_id=str(access_request.id),
            document_sha256=verification_doc.sha256,
        )
        
        # Step 2: Create initial VerificationResult (processing status)
        verification_result, created = VerificationResult.objects.get_or_create(
            access_request=access_request,
            defaults={
                'status': 'processing',
                'processor_version': 'mvp-1.0',
            }
        )
        
        try:
            # Step 3: Run OCR extraction
            ocr_result = self.ocr_extractor.extract(verification_doc.file_path)
            
            if not ocr_result.success:
                # OCR failed - mark as error
                verification_result.status = 'error'
                verification_result.decision_reason = f'OCR extraction failed: {ocr_result.error}'
                verification_result.ocr_confidence = 0.0
                verification_result.save()
                
                # Update AccessRequest to pending for manual review
                access_request.status = 'pending'
                access_request.save()
                
                # Audit: Log error
                audit.log_verification_error(
                    access_request_id=str(access_request.id),
                    error_type='OCRExtractionError',
                    error_message=ocr_result.error or 'OCR extraction failed',
                )
                
                return verification_result
            
            # Step 4: Extract structured fields
            extracted_fields = self.field_extractor.extract(ocr_result.raw_text)
            
            # Step 5: Validate against rules
            rule_result = self.rule_validator.validate(extracted_fields)
            
            # Step 6: Make decision
            decision = self.decision_engine.decide_mvp(
                ocr_result=ocr_result,
                rule_result=rule_result,
            )
            
            # Step 7: Write VerificationResult
            verification_result.status = decision.status
            verification_result.extracted_fields = self._serialize_extracted_fields(extracted_fields)
            verification_result.ocr_raw_text = ocr_result.raw_text
            verification_result.ocr_confidence = ocr_result.overall_confidence
            verification_result.decision_reason = decision.reason
            verification_result.flagged_reasons = decision.flagged_reasons
            
            # Store rule failures if any
            rule_failures_list = []
            if not rule_result.passed:
                rule_failures_list = [
                    {
                        'field': f.field,
                        'reason': f.reason,
                        'expected': f.expected if isinstance(f.expected, str) else list(f.expected),
                        'actual': f.actual,
                    }
                    for f in rule_result.failures
                ]
                verification_result.rule_failures = rule_failures_list
            
            verification_result.save()
            
            # Step 8: Update AccessRequest status based on decision
            self._update_access_request_status(access_request, decision.status)
            
            # Step 9: Write decision-specific audit events
            if decision.status == 'auto_approved':
                audit.log_verification_auto_approved(
                    access_request_id=str(access_request.id),
                    confidence_summary={
                        'ocr_confidence': ocr_result.overall_confidence,
                        'rule_validation': 'passed',
                    },
                )
            elif decision.status == 'pending_manual_review':
                audit.log_verification_pending_review(
                    access_request_id=str(access_request.id),
                    flagged_reasons=decision.flagged_reasons,
                )
            elif decision.status == 'rejected':
                audit.log_verification_rejected(
                    access_request_id=str(access_request.id),
                    decision_reason=decision.reason,
                    rule_failures=rule_failures_list,
                )
            
            # Audit: Log verification completed
            audit.log_verification_completed(
                access_request_id=str(access_request.id),
                decision=decision.status,
                processor_version='mvp-1.0',
            )
            
            return verification_result
            
        except Exception as e:
            # Unexpected error - mark as error
            verification_result.status = 'error'
            verification_result.decision_reason = f'Verification pipeline error: {str(e)}'
            verification_result.save()
            
            # Update AccessRequest to pending for manual review
            access_request.status = 'pending'
            access_request.save()
            
            # Audit: Log error
            audit.log_verification_error(
                access_request_id=str(access_request.id),
                error_type=type(e).__name__,
                error_message=str(e),
            )
            
            raise
    
    def _serialize_extracted_fields(self, fields) -> dict:
        """Serialize ExtractedFields to JSON-compatible dict.
        
        Args:
            fields: ExtractedFields dataclass
            
        Returns:
            Dict with field values
        """
        return {
            'full_name': fields.full_name,
            'school_name': fields.school_name,
            'college': fields.college,
            'program': fields.program,
            'program_raw': fields.program_raw,
            'student_number': fields.student_number,
        }
    
    def _update_access_request_status(
        self,
        access_request: AccessRequest,
        decision_status: str,
    ) -> None:
        """Update AccessRequest status based on verification decision.
        
        Maps VerificationResult.status → AccessRequest.status:
        - auto_approved → Keep as 'processing' (will be updated by approve_request in view)
        - pending_manual_review → pending
        - rejected → denied
        - error → pending
        
        Args:
            access_request: AccessRequest to update
            decision_status: VerificationResult status
        """
        if decision_status == 'auto_approved':
            # AUTO_APPROVED: Keep as 'processing' for now
            # The view layer will call approve_request() which updates to 'approved'
            # and sends activation email
            access_request.status = 'processing'
        
        elif decision_status == 'pending_manual_review':
            # PENDING_MANUAL_REVIEW: Keep as pending for admin review
            access_request.status = 'pending'
        
        elif decision_status == 'rejected':
            # REJECTED: Set to denied
            access_request.status = 'denied'
        
        elif decision_status == 'error':
            # ERROR: Keep as pending for manual review
            access_request.status = 'pending'
        
        else:
            # Unknown status - keep as pending
            access_request.status = 'pending'
        
        access_request.save()
