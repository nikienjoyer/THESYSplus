"""Integration tests for OCR pipeline with real Tesseract.

Tests full OCR extraction with real Tesseract installation.
Skips if Tesseract is not installed (CI environment).
Per Requirements 3.1, 3.2, 4.1, 4.2, 4.3, 4.4.
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from identity_verification.services.ocr_extractor import OCRExtractor
from identity_verification.services.field_extractor import FieldExtractor


# Check if Tesseract is installed
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not TESSERACT_AVAILABLE,
    reason="Tesseract OCR not installed"
)


@pytest.fixture
def ocr_extractor():
    """Create an OCRExtractor instance."""
    return OCRExtractor(timeout_seconds=10)


@pytest.fixture
def field_extractor():
    """Create a FieldExtractor instance."""
    return FieldExtractor()


@pytest.fixture
def sample_student_id_image():
    """Create a synthetic Student ID image for testing.
    
    This creates a simple text-based image that Tesseract can read.
    In production, you would use real anonymized Student ID samples.
    """
    # Create a white image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Use default font (PIL's built-in font)
    # In production, use a proper font file for better OCR accuracy
    
    # Draw text content (simulating a Student ID)
    y_offset = 50
    line_height = 40
    
    lines = [
        "Pampanga State University",
        "College of Computing Studies",
        "",
        "STUDENT ID CARD",
        "",
        "Name: Juan Dela Cruz",
        "Student No: 2021-12345",
        "Program: BS Information Technology",
        "Valid Until: 2025",
    ]
    
    for line in lines:
        draw.text((50, y_offset), line, fill='black')
        y_offset += line_height
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file.name)
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    Path(temp_file.name).unlink(missing_ok=True)


@pytest.fixture
def sample_cor_image():
    """Create a synthetic COR (Certificate of Registration) image for testing."""
    # Create a white image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw text content (simulating a COR)
    y_offset = 50
    line_height = 40
    
    lines = [
        "PAMPANGA STATE UNIVERSITY",
        "Certificate of Registration",
        "",
        "Student Name: Maria Santos",
        "College: CCS",
        "Course: BSCS",
        "Student Number: 2022-54321",
        "Semester: 1st Semester 2024-2025",
    ]
    
    for line in lines:
        draw.text((50, y_offset), line, fill='black')
        y_offset += line_height
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file.name)
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    Path(temp_file.name).unlink(missing_ok=True)


class TestOCRIntegrationStudentID:
    """Test full OCR pipeline with Student ID image."""
    
    def test_extract_text_from_student_id(self, ocr_extractor, sample_student_id_image):
        """Extract text from Student ID image using real Tesseract."""
        result = ocr_extractor.extract(sample_student_id_image)
        
        assert result.success
        assert result.error is None
        assert len(result.raw_text) > 0
        
        # Check that key text is present (case-insensitive, flexible matching)
        text_lower = result.raw_text.lower()
        assert "pampanga" in text_lower or "state" in text_lower
        assert "juan" in text_lower or "dela" in text_lower or "cruz" in text_lower
    
    def test_extract_fields_from_student_id(self, ocr_extractor, field_extractor, sample_student_id_image):
        """Extract structured fields from Student ID using full pipeline."""
        # Step 1: OCR extraction
        ocr_result = ocr_extractor.extract(sample_student_id_image)
        assert ocr_result.success
        
        # Step 2: Field extraction
        fields = field_extractor.extract(ocr_result.raw_text)
        
        # Verify extracted fields (flexible matching due to OCR variability)
        # Note: OCR may not be 100% accurate on synthetic images
        # In production, use real document samples for better accuracy
        
        # At least some fields should be extracted
        assert (
            fields.full_name is not None or
            fields.school_name is not None or
            fields.college is not None or
            fields.program is not None or
            fields.student_number is not None
        ), "At least one field should be extracted"
    
    def test_ocr_confidence_score(self, ocr_extractor, sample_student_id_image):
        """Verify OCR confidence score is calculated."""
        result = ocr_extractor.extract(sample_student_id_image)
        
        assert result.success
        assert result.overall_confidence >= 0.0
        assert result.overall_confidence <= 100.0


class TestOCRIntegrationCOR:
    """Test full OCR pipeline with COR image."""
    
    def test_extract_text_from_cor(self, ocr_extractor, sample_cor_image):
        """Extract text from COR image using real Tesseract."""
        result = ocr_extractor.extract(sample_cor_image)
        
        assert result.success
        assert result.error is None
        assert len(result.raw_text) > 0
        
        # Check that key text is present
        text_lower = result.raw_text.lower()
        assert "pampanga" in text_lower or "state" in text_lower
        assert "maria" in text_lower or "santos" in text_lower
    
    def test_extract_fields_from_cor(self, ocr_extractor, field_extractor, sample_cor_image):
        """Extract structured fields from COR using full pipeline."""
        # Step 1: OCR extraction
        ocr_result = ocr_extractor.extract(sample_cor_image)
        assert ocr_result.success
        
        # Step 2: Field extraction
        fields = field_extractor.extract(ocr_result.raw_text)
        
        # At least some fields should be extracted
        assert (
            fields.full_name is not None or
            fields.school_name is not None or
            fields.college is not None or
            fields.program is not None or
            fields.student_number is not None
        ), "At least one field should be extracted"


class TestOCRIntegrationProgramNormalization:
    """Test program normalization in full pipeline."""
    
    def test_program_normalization_bsit(self, ocr_extractor, field_extractor, sample_student_id_image):
        """Verify program normalization works in full pipeline."""
        ocr_result = ocr_extractor.extract(sample_student_id_image)
        fields = field_extractor.extract(ocr_result.raw_text)
        
        # If program was extracted, verify normalization
        if fields.program_raw:
            # program should be normalized (or same as raw if already canonical)
            assert fields.program is not None
            
            # If raw program contains "IT" or "Information Technology",
            # normalized should be "BS Information Technology"
            if fields.program_raw and ("IT" in fields.program_raw.upper() or "INFORMATION TECHNOLOGY" in fields.program_raw.upper()):
                assert fields.program == "BS Information Technology"


class TestOCRIntegrationErrorHandling:
    """Test error handling in integration scenarios."""
    
    def test_extract_from_nonexistent_file(self, ocr_extractor):
        """Handle nonexistent file gracefully."""
        result = ocr_extractor.extract("/nonexistent/file.png")
        
        assert not result.success
        assert result.error is not None
        assert result.raw_text == ""
        assert result.overall_confidence == 0.0
    
    def test_extract_from_corrupt_image(self, ocr_extractor):
        """Handle corrupt image file gracefully."""
        # Create a file with invalid image data
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_file.write(b'not a valid image')
        temp_file.close()
        
        result = ocr_extractor.extract(temp_file.name)
        
        assert not result.success
        assert result.error is not None
        
        # Cleanup
        Path(temp_file.name).unlink(missing_ok=True)


class TestOCRIntegrationPerformance:
    """Test OCR performance characteristics."""
    
    def test_ocr_completes_within_timeout(self, ocr_extractor, sample_student_id_image):
        """Verify OCR completes within configured timeout."""
        import time
        
        start_time = time.time()
        result = ocr_extractor.extract(sample_student_id_image)
        elapsed_time = time.time() - start_time
        
        # Should complete within timeout (10 seconds)
        assert elapsed_time < 10.0
        assert result.success or result.error is not None  # Either success or graceful failure
