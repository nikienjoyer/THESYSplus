"""Type definitions for identity verification.

Dataclasses and TypedDicts for structured data passing between components.
"""

from dataclasses import dataclass
from typing import Optional

# Re-export FileValidationResult from validators
from .validators.file_validator import FileValidationResult

# Re-export OCR types from services
from .services.ocr_extractor import OCRResult
from .services.field_extractor import ExtractedFields

__all__ = ['FileValidationResult', 'OCRResult', 'ExtractedFields']
