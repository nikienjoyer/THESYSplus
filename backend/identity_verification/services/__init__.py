"""Services for identity verification processing.

Contains:
- OCRExtractor: Tesseract OCR wrapper
- FieldExtractor: Regex-based field extraction
- VerificationOrchestrator: Main verification pipeline
- DecisionEngine: Auto-approval decision logic
- audit: Audit logging functions for verification events
"""

from . import audit

__all__ = ['audit']
