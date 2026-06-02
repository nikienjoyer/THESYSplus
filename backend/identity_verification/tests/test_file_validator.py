"""Unit tests for FileValidator.

Tests magic byte validation, file size limits, EXIF stripping, and PDF sanitization.
Per Requirements 2.1, 2.2, 2.3, 2.4, 2.5.
"""

import io
import os
import tempfile
from pathlib import Path

import pikepdf
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from identity_verification.constants import (
    FILE_CORRUPT,
    FILE_TOO_LARGE,
    FILE_TYPE_MISMATCH,
    FILE_TYPE_NOT_ALLOWED,
)
from identity_verification.validators.file_validator import FileValidator


@pytest.fixture
def validator():
    """Create a FileValidator instance."""
    return FileValidator()


@pytest.fixture
def valid_png_bytes():
    """Create a valid PNG image with EXIF data."""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    # Add EXIF data
    exif_data = img.getexif()
    exif_data[0x010F] = "Test Camera"  # Make
    img.save(buffer, format='PNG', exif=exif_data)
    return buffer.getvalue()


@pytest.fixture
def valid_jpeg_bytes():
    """Create a valid JPEG image with EXIF data."""
    img = Image.new('RGB', (100, 100), color='blue')
    buffer = io.BytesIO()
    # Add EXIF data
    exif_data = img.getexif()
    exif_data[0x010F] = "Test Camera"  # Make
    exif_data[0x0110] = "Test Model"  # Model
    img.save(buffer, format='JPEG', exif=exif_data)
    return buffer.getvalue()


@pytest.fixture
def valid_pdf_bytes():
    """Create a valid PDF with JavaScript."""
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    
    # Add JavaScript action
    pdf.Root.Names = pikepdf.Dictionary({
        '/JavaScript': pikepdf.Dictionary({
            '/Names': pikepdf.Array([
                pikepdf.String('MyScript'),
                pikepdf.Dictionary({
                    '/S': pikepdf.Name('/JavaScript'),
                    '/JS': pikepdf.String('app.alert("Hello");'),
                }),
            ]),
        }),
    })
    
    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


class TestFileValidatorBasic:
    """Test basic file validation (size, extension, MIME)."""
    
    def test_valid_png_passes(self, validator, valid_png_bytes):
        """Valid PNG file should pass validation."""
        uploaded_file = SimpleUploadedFile(
            'test.png',
            valid_png_bytes,
            content_type='image/png',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.detected_mime == 'image/png'
        assert result.magic_bytes_ok
        assert result.size_bytes == len(valid_png_bytes)
        assert result.errors == []
        assert result.sanitized_path is not None
    
    def test_valid_jpeg_passes(self, validator, valid_jpeg_bytes):
        """Valid JPEG file should pass validation."""
        uploaded_file = SimpleUploadedFile(
            'test.jpg',
            valid_jpeg_bytes,
            content_type='image/jpeg',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.detected_mime == 'image/jpeg'
        assert result.magic_bytes_ok
        assert result.size_bytes == len(valid_jpeg_bytes)
        assert result.errors == []
        assert result.sanitized_path is not None
    
    def test_valid_pdf_passes(self, validator, valid_pdf_bytes):
        """Valid PDF file should pass validation."""
        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            valid_pdf_bytes,
            content_type='application/pdf',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.detected_mime == 'application/pdf'
        assert result.magic_bytes_ok
        assert result.size_bytes == len(valid_pdf_bytes)
        assert result.errors == []
        assert result.sanitized_path is not None
    
    def test_file_too_large_rejected(self, validator):
        """File exceeding max size should be rejected."""
        # Create a file larger than 10MB
        large_content = b'x' * (11 * 1024 * 1024)
        uploaded_file = SimpleUploadedFile(
            'large.png',
            large_content,
            content_type='image/png',
        )
        
        result = validator.validate(uploaded_file)
        
        assert not result.is_valid
        assert FILE_TOO_LARGE in result.errors
    
    def test_invalid_extension_rejected(self, validator):
        """File with invalid extension should be rejected."""
        uploaded_file = SimpleUploadedFile(
            'test.txt',
            b'Hello world',
            content_type='text/plain',
        )
        
        result = validator.validate(uploaded_file)
        
        assert not result.is_valid
        assert FILE_TYPE_NOT_ALLOWED in result.errors
    
    def test_mime_mismatch_rejected(self, validator):
        """File with mismatched MIME type should be rejected."""
        # PNG magic bytes but .jpg extension
        png_bytes = b'\x89PNG\r\n\x1a\n' + b'fake png data'
        uploaded_file = SimpleUploadedFile(
            'fake.jpg',
            png_bytes,
            content_type='image/jpeg',
        )
        
        result = validator.validate(uploaded_file)
        
        assert not result.is_valid
        # Should detect as PNG but expect JPEG
        assert result.detected_mime == 'image/png'
    
    def test_corrupt_file_rejected(self, validator):
        """Corrupt file should be rejected."""
        # Invalid PNG (missing proper structure)
        corrupt_bytes = b'\x89PNG\r\n\x1a\n' + b'corrupt'
        uploaded_file = SimpleUploadedFile(
            'corrupt.png',
            corrupt_bytes,
            content_type='image/png',
        )
        
        result = validator.validate(uploaded_file)
        
        assert not result.is_valid
        assert FILE_CORRUPT in result.errors


class TestImageSanitization:
    """Test EXIF stripping from images."""
    
    def test_png_exif_stripped(self, validator, valid_png_bytes):
        """PNG EXIF data should be stripped."""
        uploaded_file = SimpleUploadedFile(
            'test.png',
            valid_png_bytes,
            content_type='image/png',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.sanitized_path is not None
        
        # Load sanitized image and check EXIF is gone
        sanitized_img = Image.open(result.sanitized_path)
        exif = sanitized_img.getexif()
        
        # EXIF should be empty or minimal
        assert len(exif) == 0 or 0x010F not in exif
        
        # Cleanup
        os.unlink(result.sanitized_path)
    
    def test_jpeg_exif_stripped(self, validator, valid_jpeg_bytes):
        """JPEG EXIF data should be stripped."""
        uploaded_file = SimpleUploadedFile(
            'test.jpg',
            valid_jpeg_bytes,
            content_type='image/jpeg',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.sanitized_path is not None
        
        # Load sanitized image and check EXIF is gone
        sanitized_img = Image.open(result.sanitized_path)
        exif = sanitized_img.getexif()
        
        # EXIF should be empty or minimal
        assert len(exif) == 0 or 0x010F not in exif
        
        # Close image before cleanup
        sanitized_img.close()
        
        # Cleanup
        try:
            os.unlink(result.sanitized_path)
        except PermissionError:
            # Windows file locking - file will be cleaned up later
            pass


class TestPDFSanitization:
    """Test JavaScript and embedded file removal from PDFs."""
    
    def test_pdf_javascript_stripped(self, validator, valid_pdf_bytes):
        """PDF JavaScript should be removed."""
        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            valid_pdf_bytes,
            content_type='application/pdf',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.sanitized_path is not None
        
        # Load sanitized PDF and check JavaScript is gone
        sanitized_pdf = pikepdf.open(result.sanitized_path)
        
        # JavaScript should be removed
        if '/Names' in sanitized_pdf.Root:
            assert '/JavaScript' not in sanitized_pdf.Root.Names
        
        sanitized_pdf.close()
        
        # Cleanup
        os.unlink(result.sanitized_path)
    
    def test_pdf_without_javascript_unchanged(self, validator):
        """PDF without JavaScript should still be sanitized."""
        # Create clean PDF
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        buffer = io.BytesIO()
        pdf.save(buffer)
        pdf_bytes = buffer.getvalue()
        
        uploaded_file = SimpleUploadedFile(
            'clean.pdf',
            pdf_bytes,
            content_type='application/pdf',
        )
        
        result = validator.validate(uploaded_file)
        
        assert result.is_valid
        assert result.sanitized_path is not None
        
        # Cleanup
        os.unlink(result.sanitized_path)


class TestMagicByteValidation:
    """Test magic byte signature validation."""
    
    def test_png_magic_bytes_verified(self, validator):
        """PNG magic bytes should be verified."""
        # Valid PNG magic bytes
        png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        uploaded_file = SimpleUploadedFile(
            'test.png',
            png_bytes,
            content_type='image/png',
        )
        
        result = validator.validate(uploaded_file)
        
        # Should detect as PNG
        assert result.detected_mime == 'image/png'
    
    def test_jpeg_magic_bytes_verified(self, validator):
        """JPEG magic bytes should be verified."""
        # Valid JPEG magic bytes
        jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        uploaded_file = SimpleUploadedFile(
            'test.jpg',
            jpeg_bytes,
            content_type='image/jpeg',
        )
        
        result = validator.validate(uploaded_file)
        
        # Should detect as JPEG
        assert result.detected_mime == 'image/jpeg'
    
    def test_pdf_magic_bytes_verified(self, validator):
        """PDF magic bytes should be verified."""
        # Valid PDF magic bytes
        pdf_bytes = b'%PDF-1.4\n' + b'\x00' * 100
        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            pdf_bytes,
            content_type='application/pdf',
        )
        
        result = validator.validate(uploaded_file)
        
        # Should detect as PDF
        assert result.detected_mime == 'application/pdf'
    
    def test_fake_extension_detected(self, validator):
        """File with fake extension should be detected."""
        # Text file with .png extension
        text_bytes = b'This is not an image'
        uploaded_file = SimpleUploadedFile(
            'fake.png',
            text_bytes,
            content_type='image/png',
        )
        
        result = validator.validate(uploaded_file)
        
        assert not result.is_valid
        # Text file won't match any magic signature, so detected_mime will be None
        # This triggers FILE_CORRUPT error
        assert FILE_CORRUPT in result.errors or FILE_TYPE_MISMATCH in result.errors
