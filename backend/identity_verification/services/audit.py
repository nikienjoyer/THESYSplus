"""Audit logging for identity verification events.

Per Requirement 17 (Auditability), this module provides structured audit
logging for all verification activities. All audit events are written to
the common audit log via common.audit_logger.write().

Event Types:
- access_request.verification.started: Verification pipeline begins
- access_request.verification.completed: Verification pipeline completes
- access_request.verification.auto_approved: Request auto-approved
- access_request.verification.pending_review: Request flagged for manual review
- access_request.verification.rejected: Request rejected due to rule failures
- access_request.verification.error: Pipeline error occurred
"""

from __future__ import annotations

from typing import Any, Optional

from common.audit_logger import write as audit_write


def log_verification_started(
    access_request_id: str,
    document_sha256: str,
    request=None,
) -> None:
    """Log verification pipeline start.
    
    Per Requirement 17.1: WHERE verification starts, THE Verification_System
    SHALL write audit event access_request.verification.started with document SHA256.
    
    Args:
        access_request_id: UUID of AccessRequest being verified
        document_sha256: SHA256 hash of uploaded document
        request: Optional HTTP request for IP/user-agent capture
    """
    audit_write(
        event_type='access_request.verification.started',
        actor=None,  # System-initiated
        target=None,
        success=True,
        metadata={
            'access_request_id': str(access_request_id),
            'document_sha256': document_sha256,
        },
        request=request,
    )


def log_verification_completed(
    access_request_id: str,
    decision: str,
    processor_version: str,
    request=None,
) -> None:
    """Log verification pipeline completion.
    
    Per Requirement 17.2: WHERE verification completes, THE Verification_System
    SHALL write audit event access_request.verification.completed with decision
    and processor version.
    
    Args:
        access_request_id: UUID of AccessRequest verified
        decision: Final decision status (auto_approved, pending_manual_review, rejected)
        processor_version: Version identifier of verification processor
        request: Optional HTTP request for IP/user-agent capture
    """
    audit_write(
        event_type='access_request.verification.completed',
        actor=None,  # System-initiated
        target=None,
        success=True,
        metadata={
            'access_request_id': str(access_request_id),
            'decision': decision,
            'processor_version': processor_version,
        },
        request=request,
    )


def log_verification_auto_approved(
    access_request_id: str,
    confidence_summary: dict[str, Any],
    request=None,
) -> None:
    """Log auto-approval decision.
    
    Per Requirement 17.3: WHERE a request is AUTO_APPROVED, THE Verification_System
    SHALL write audit event access_request.verification.auto_approved with
    confidence summary.
    
    Args:
        access_request_id: UUID of AccessRequest auto-approved
        confidence_summary: Dict with OCR confidence and other scores
        request: Optional HTTP request for IP/user-agent capture
    """
    audit_write(
        event_type='access_request.verification.auto_approved',
        actor=None,  # System-initiated
        target=None,
        success=True,
        metadata={
            'access_request_id': str(access_request_id),
            'confidence_summary': confidence_summary,
        },
        request=request,
    )


def log_verification_pending_review(
    access_request_id: str,
    flagged_reasons: list[str],
    request=None,
) -> None:
    """Log pending manual review decision.
    
    Per Requirement 17.4: WHERE a request is PENDING_MANUAL_REVIEW, THE
    Verification_System SHALL write audit event
    access_request.verification.pending_review with flagged reasons.
    
    Args:
        access_request_id: UUID of AccessRequest flagged for review
        flagged_reasons: List of reasons why manual review is required
        request: Optional HTTP request for IP/user-agent capture
    """
    audit_write(
        event_type='access_request.verification.pending_review',
        actor=None,  # System-initiated
        target=None,
        success=True,
        metadata={
            'access_request_id': str(access_request_id),
            'flagged_reasons': flagged_reasons,
        },
        request=request,
    )


def log_verification_rejected(
    access_request_id: str,
    decision_reason: str,
    rule_failures: list[dict[str, Any]],
    request=None,
) -> None:
    """Log rejection decision.
    
    Per Requirement 17.5: WHERE a request is REJECTED, THE Verification_System
    SHALL write audit event access_request.verification.rejected with decision
    reason and rule failures.
    
    Args:
        access_request_id: UUID of AccessRequest rejected
        decision_reason: Machine-readable rejection reason code
        rule_failures: List of rule validation failures
        request: Optional HTTP request for IP/user-agent capture
    """
    audit_write(
        event_type='access_request.verification.rejected',
        actor=None,  # System-initiated
        target=None,
        success=False,  # Rejection is a failure outcome
        metadata={
            'access_request_id': str(access_request_id),
            'decision_reason': decision_reason,
            'rule_failures': rule_failures,
        },
        request=request,
    )


def log_verification_error(
    access_request_id: str,
    error_type: str,
    error_message: str,
    request=None,
) -> None:
    """Log verification pipeline error.
    
    Per Requirement 18.6: WHERE an error occurs, THE Verification_System SHALL
    write audit event access_request.verification.error with exception class.
    
    Args:
        access_request_id: UUID of AccessRequest that encountered error
        error_type: Exception class name or error type
        error_message: Error message or description
        request: Optional HTTP request for IP/user-agent capture
    """
    audit_write(
        event_type='access_request.verification.error',
        actor=None,  # System-initiated
        target=None,
        success=False,  # Error is a failure outcome
        metadata={
            'access_request_id': str(access_request_id),
            'error_type': error_type,
            'error_message': error_message,
        },
        request=request,
    )
