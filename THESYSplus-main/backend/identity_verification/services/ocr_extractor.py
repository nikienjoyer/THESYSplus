"""OCR extraction service using Tesseract.

Extracts text from images and PDFs with confidence scoring.
Per Requirements 3.1, 3.2, 3.3, 3.4, 3.5.
"""

from __future__ import annotations

import io
import os
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pytesseract
from pdf2image import convert_from_path
from PIL import Image


def _configure_tesseract_path():
    """Configure Tesseract path for pytesseract.
    
    Priority:
    1. Use IDENTITY_VERIFICATION['TESSERACT_CMD'] if set in settings
    2. Auto-discover on Windows in common installation paths
    3. Fall back to system PATH (default pytesseract behavior)
    
    This fixes Windows PATH issues where Tesseract is installed but not
    in the current process PATH.
    """
    # Import Django settings here to avoid module-level import issues
    from django.conf import settings
    
    # Check if already configured via settings
    tesseract_cmd = getattr(settings, 'IDENTITY_VERIFICATION', {}).get('TESSERACT_CMD')
    
    if tesseract_cmd:
        # Use explicitly configured path
        if os.path.isfile(tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            return
        else:
            # Configured path doesn't exist - log warning but continue to auto-discovery
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f'Configured TESSERACT_CMD does not exist: {tesseract_cmd}. '
                f'Attempting auto-discovery.'
            )
    
    # Auto-discovery for Windows
    if platform.system() == 'Windows':
        # Common Tesseract installation paths on Windows
        common_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Tesseract-OCR\tesseract.exe',
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return
    
    # If we reach here, rely on system PATH (default pytesseract behavior)
    # pytesseract will raise TesseractNotFoundError if not found


@dataclass
class OCRResult:
    """Result of OCR extraction.
    
    Attributes:
        raw_text: Full extracted text from document
        overall_confidence: Average confidence score (0-100)
        success: Whether OCR extraction succeeded
        error: Error message if extraction failed
    """
    raw_text: str
    overall_confidence: float
    success: bool
    error: str | None = None


class OCRExtractor:
    """Extracts text from images and PDFs using Tesseract OCR.
    
    Supports:
    - Direct image OCR (PNG, JPEG)
    - PDF to image conversion then OCR (first page only)
    - Confidence score calculation
    - Graceful error handling
    """
    
    # Class-level flag to track if Tesseract path has been configured
    _tesseract_configured = False
    
    def __init__(self, timeout_seconds: int = 10):
        """Initialize OCR extractor.
        
        Args:
            timeout_seconds: Maximum time to wait for OCR (default: 10s)
        """
        self.timeout_seconds = timeout_seconds
        
        # Configure Tesseract path on first instantiation
        if not OCRExtractor._tesseract_configured:
            _configure_tesseract_path()
            OCRExtractor._tesseract_configured = True
    
    def extract(self, file_path: str) -> OCRResult:
        """Extract text from image or PDF file.
        
        Args:
            file_path: Path to image or PDF file
            
        Returns:
            OCRResult with extracted text and confidence
        """
        try:
            # Determine file type
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.pdf':
                return self._extract_from_pdf(file_path)
            else:
                return self._extract_from_image(file_path)
                
        except Exception as e:
            # Graceful failure - return empty result with error
            return OCRResult(
                raw_text='',
                overall_confidence=0.0,
                success=False,
                error=str(e),
            )
    
    def _extract_from_image(self, image_path: str) -> OCRResult:
        """Extract text from image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            OCRResult with extracted text and confidence
        """
        # Load image
        image = Image.open(image_path)
        
        # Extract text
        raw_text = pytesseract.image_to_string(
            image,
            timeout=self.timeout_seconds,
        )
        
        # Get confidence data
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            timeout=self.timeout_seconds,
        )
        
        # Calculate overall confidence
        confidences = [
            float(conf)
            for conf in data['conf']
            if conf != -1  # -1 means no text detected
        ]
        
        if confidences:
            overall_confidence = sum(confidences) / len(confidences)
        else:
            overall_confidence = 0.0
        
        image.close()
        
        return OCRResult(
            raw_text=raw_text.strip(),
            overall_confidence=overall_confidence,
            success=True,
            error=None,
        )
    
    def _extract_from_pdf(self, pdf_path: str) -> OCRResult:
        """Extract text from PDF file (first page only).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            OCRResult with extracted text and confidence
        """
        # Convert first page of PDF to image
        images = convert_from_path(
            pdf_path,
            first_page=1,
            last_page=1,  # Only process first page
            dpi=300,  # High DPI for better OCR accuracy
        )
        
        if not images:
            return OCRResult(
                raw_text='',
                overall_confidence=0.0,
                success=False,
                error='No pages found in PDF',
            )
        
        # Extract text from first page
        first_page = images[0]
        
        # Extract text
        raw_text = pytesseract.image_to_string(
            first_page,
            timeout=self.timeout_seconds,
        )
        
        # Get confidence data
        data = pytesseract.image_to_data(
            first_page,
            output_type=pytesseract.Output.DICT,
            timeout=self.timeout_seconds,
        )
        
        # Calculate overall confidence
        confidences = [
            float(conf)
            for conf in data['conf']
            if conf != -1  # -1 means no text detected
        ]
        
        if confidences:
            overall_confidence = sum(confidences) / len(confidences)
        else:
            overall_confidence = 0.0
        
        return OCRResult(
            raw_text=raw_text.strip(),
            overall_confidence=overall_confidence,
            success=True,
            error=None,
        )
