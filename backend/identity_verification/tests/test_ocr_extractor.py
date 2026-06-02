"""Unit tests for OCRExtractor with mocked Tesseract output.

Tests OCR extraction logic without requiring Tesseract installation.
Per Requirements 3.1, 3.2, 3.3, 3.4, 3.5.
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from identity_verification.services.ocr_extractor import OCRExtractor, OCRResult


@pytest.fixture
def ocr_extractor():
    """Create an OCRExtractor instance."""
    return OCRExtractor(timeout_seconds=10)


@pytest.fixture
def sample_image_file():
    """Create a temporary image file for testing."""
    img = Image.new('RGB', (100, 100), color='white')
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file.name)
    temp_file.close()
    yield temp_file.name
    # Cleanup
    Path(temp_file.name).unlink(missing_ok=True)


class TestOCRExtractorBasic:
    """Test basic OCR extraction functionality."""
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_from_image_success(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """Successful image OCR extraction."""
        # Mock Tesseract output
        mock_pytesseract.image_to_string.return_value = "Sample OCR Text\nLine 2"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [95, 90, 85, 92],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.success
        assert result.raw_text == "Sample OCR Text\nLine 2"
        assert result.overall_confidence == 90.5  # Average of [95, 90, 85, 92]
        assert result.error is None
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_handles_no_text(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """OCR extraction with no text detected."""
        # Mock Tesseract output with no text
        mock_pytesseract.image_to_string.return_value = ""
        mock_pytesseract.image_to_data.return_value = {
            'conf': [-1, -1, -1],  # -1 means no text
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.success
        assert result.raw_text == ""
        assert result.overall_confidence == 0.0
        assert result.error is None
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_handles_low_confidence(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """OCR extraction with low confidence scores."""
        # Mock Tesseract output with low confidence
        mock_pytesseract.image_to_string.return_value = "Blurry text"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [30, 25, 35, 28],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.success
        assert result.raw_text == "Blurry text"
        assert result.overall_confidence == 29.5  # Average of [30, 25, 35, 28]
        assert result.error is None
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_handles_mixed_confidence(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """OCR extraction with mixed confidence scores (some -1)."""
        # Mock Tesseract output with mixed confidence
        mock_pytesseract.image_to_string.return_value = "Some text"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [90, -1, 85, -1, 88],  # -1 values should be ignored
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.success
        # Average of [90, 85, 88] = 87.666... (use approximate comparison)
        assert abs(result.overall_confidence - 87.67) < 0.01
        assert result.error is None
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_handles_ocr_failure(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """OCR extraction handles Tesseract failure gracefully."""
        # Mock Tesseract failure
        mock_pytesseract.image_to_string.side_effect = Exception("Tesseract error")
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert not result.success
        assert result.raw_text == ""
        assert result.overall_confidence == 0.0
        assert "Tesseract error" in result.error


class TestOCRExtractorPDF:
    """Test PDF to image conversion and OCR."""
    
    @patch('identity_verification.services.ocr_extractor.convert_from_path')
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_from_pdf_success(self, mock_pytesseract, mock_convert, ocr_extractor):
        """Successful PDF OCR extraction."""
        # Create a mock PDF file path
        pdf_path = 'test.pdf'
        
        # Mock PDF to image conversion
        mock_image = MagicMock()
        mock_convert.return_value = [mock_image]
        
        # Mock Tesseract output
        mock_pytesseract.image_to_string.return_value = "PDF Text Content"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [92, 88, 90],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor._extract_from_pdf(pdf_path)
        
        assert result.success
        assert result.raw_text == "PDF Text Content"
        assert result.overall_confidence == 90.0  # Average of [92, 88, 90]
        assert result.error is None
        
        # Verify PDF conversion was called correctly
        mock_convert.assert_called_once_with(
            pdf_path,
            first_page=1,
            last_page=1,
            dpi=300,
        )
    
    @patch('identity_verification.services.ocr_extractor.convert_from_path')
    def test_extract_from_pdf_no_pages(self, mock_convert, ocr_extractor):
        """PDF extraction handles empty PDF."""
        pdf_path = 'empty.pdf'
        
        # Mock empty PDF
        mock_convert.return_value = []
        
        result = ocr_extractor._extract_from_pdf(pdf_path)
        
        assert not result.success
        assert result.raw_text == ""
        assert result.overall_confidence == 0.0
        assert "No pages found" in result.error
    
    @patch('identity_verification.services.ocr_extractor.convert_from_path')
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_extract_from_pdf_only_first_page(self, mock_pytesseract, mock_convert, ocr_extractor):
        """PDF extraction processes only first page."""
        pdf_path = 'multipage.pdf'
        
        # Mock multi-page PDF (but only first page should be used)
        mock_image1 = MagicMock()
        mock_image2 = MagicMock()
        mock_convert.return_value = [mock_image1, mock_image2]
        
        # Mock Tesseract output
        mock_pytesseract.image_to_string.return_value = "First Page"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [95],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor._extract_from_pdf(pdf_path)
        
        assert result.success
        assert result.raw_text == "First Page"
        
        # Verify only first page was processed
        mock_pytesseract.image_to_string.assert_called_once_with(
            mock_image1,
            timeout=10,
        )


class TestOCRExtractorConfidenceCalculation:
    """Test confidence score calculation logic."""
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_confidence_calculation_all_valid(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """Confidence calculation with all valid scores."""
        mock_pytesseract.image_to_string.return_value = "Text"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [100, 90, 80, 70],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.overall_confidence == 85.0  # (100+90+80+70)/4
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_confidence_calculation_ignores_negative_one(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """Confidence calculation ignores -1 values."""
        mock_pytesseract.image_to_string.return_value = "Text"
        mock_pytesseract.image_to_data.return_value = {
            'conf': [100, -1, 80, -1, 60],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.overall_confidence == 80.0  # (100+80+60)/3
    
    @patch('identity_verification.services.ocr_extractor.pytesseract')
    def test_confidence_calculation_all_negative_one(self, mock_pytesseract, ocr_extractor, sample_image_file):
        """Confidence calculation with all -1 values."""
        mock_pytesseract.image_to_string.return_value = ""
        mock_pytesseract.image_to_data.return_value = {
            'conf': [-1, -1, -1],
        }
        mock_pytesseract.Output.DICT = 'dict'
        
        result = ocr_extractor.extract(sample_image_file)
        
        assert result.overall_confidence == 0.0
