"""File validator for uploaded verification documents.

Validates file type, size, magic bytes, and sanitizes images/PDFs.
Per Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 16.1.
"""

from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pikepdf
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from PIL import Image

from ..constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    FILE_CORRUPT,
    FILE_TOO_LARGE,
    FILE_TYPE_MISMATCH,
    FILE_TYPE_NOT_ALLOWED,
    MAGIC_SIGNATURES,
)


@dataclass
class FileValidationResult:
    """Result of file validation.
    
    Attributes:
        is_valid: Whether the file passed all validation checks
        detected_mime: MIME type detected by magic bytes
        magic_bytes_ok: Whether magic bytes match declared MIME
        size_bytes: File size in bytes
        errors: List of error codes if validation failed
        sanitized_path: Path to sanitized file (if applicable)
    """
    is_valid: bool
    detected_mime: str | None
    magic_bytes_ok: bool
    size_bytes: int
    errors: list[str]
    sanitized_path: str | None = None


class FileValidator:
    """Validates and sanitizes uploaded verification documents.
    
    Performs:
    - File extension validation
    - File size validation
    - Magic byte validation (MIME type verification)
    - Image sanitization (EXIF stripping via Pillow re-encoding)
    - PDF sanitization (JavaScript/embedded file removal via pikepdf)
    """
    
    def __init__(self):
        """Initialize validator with settings from Django config."""
        self.max_size_bytes = (
            settings.IDENTITY_VERIFICATION['MAX_FILE_SIZE_MB'] * 1024 * 1024
        )
        self.allowed_extensions = ALLOWED_EXTENSIONS
        self.allowed_mime_types = ALLOWED_MIME_TYPES
    
    def validate(self, uploaded_file: UploadedFile) -> FileValidationResult:
        """Validate and sanitize an uploaded file.
        
        Args:
            uploaded_file: Django UploadedFile instance
            
        Returns:
            FileValidationResult with validation outcome and sanitized path
        """
        errors = []
        detected_mime = None
        magic_bytes_ok = False
        sanitized_path = None
        
        # Get file size
        size_bytes = uploaded_file.size
        
        # Validate file size
        if size_bytes > self.max_size_bytes:
            errors.append(FILE_TOO_LARGE)
            return FileValidationResult(
                is_valid=False,
                detected_mime=None,
                magic_bytes_ok=False,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # Validate file extension
        file_ext = self._get_extension(uploaded_file.name)
        if file_ext not in self.allowed_extensions:
            errors.append(FILE_TYPE_NOT_ALLOWED)
            return FileValidationResult(
                is_valid=False,
                detected_mime=None,
                magic_bytes_ok=False,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # Read file content for magic byte validation
        try:
            uploaded_file.seek(0)
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset for later use
        except Exception:
            errors.append(FILE_CORRUPT)
            return FileValidationResult(
                is_valid=False,
                detected_mime=None,
                magic_bytes_ok=False,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # Detect MIME type from magic bytes
        detected_mime = self._detect_mime_from_magic_bytes(file_content)
        
        if not detected_mime:
            errors.append(FILE_CORRUPT)
            return FileValidationResult(
                is_valid=False,
                detected_mime=None,
                magic_bytes_ok=False,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # Check if detected MIME is allowed
        if detected_mime not in self.allowed_mime_types:
            errors.append(FILE_TYPE_MISMATCH)
            return FileValidationResult(
                is_valid=False,
                detected_mime=detected_mime,
                magic_bytes_ok=False,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # Verify magic bytes match expected signature
        magic_bytes_ok = self._verify_magic_bytes(file_content, detected_mime)
        if not magic_bytes_ok:
            errors.append(FILE_TYPE_MISMATCH)
            return FileValidationResult(
                is_valid=False,
                detected_mime=detected_mime,
                magic_bytes_ok=False,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # Sanitize file based on type
        try:
            if detected_mime in ('image/png', 'image/jpeg'):
                sanitized_path = self._sanitize_image(file_content, detected_mime)
            elif detected_mime == 'application/pdf':
                sanitized_path = self._sanitize_pdf(file_content)
        except Exception:
            errors.append(FILE_CORRUPT)
            return FileValidationResult(
                is_valid=False,
                detected_mime=detected_mime,
                magic_bytes_ok=True,
                size_bytes=size_bytes,
                errors=errors,
            )
        
        # All validations passed
        return FileValidationResult(
            is_valid=True,
            detected_mime=detected_mime,
            magic_bytes_ok=True,
            size_bytes=size_bytes,
            errors=[],
            sanitized_path=sanitized_path,
        )
    
    def _get_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        return Path(filename).suffix.lstrip('.').lower()
    
    def _detect_mime_from_magic_bytes(self, content: bytes) -> str | None:
        """Detect MIME type from magic bytes.
        
        Uses manual signature matching for cross-platform compatibility.
        """
        # Check PNG
        if content.startswith(MAGIC_SIGNATURES['image/png']):
            return 'image/png'
        
        # Check JPEG
        if content.startswith(MAGIC_SIGNATURES['image/jpeg']):
            return 'image/jpeg'
        
        # Check PDF
        if content.startswith(MAGIC_SIGNATURES['application/pdf']):
            return 'application/pdf'
        
        return None
    
    def _verify_magic_bytes(self, content: bytes, mime_type: str) -> bool:
        """Verify file content starts with expected magic bytes."""
        expected_signature = MAGIC_SIGNATURES.get(mime_type)
        if not expected_signature:
            return False
        return content.startswith(expected_signature)
    
    def _sanitize_image(self, content: bytes, mime_type: str) -> str:
        """Sanitize image by re-encoding through Pillow to strip EXIF.
        
        Args:
            content: Raw image bytes
            mime_type: Detected MIME type
            
        Returns:
            Path to sanitized temporary file
        """
        # Load image
        image = Image.open(io.BytesIO(content))
        
        # Determine format
        if mime_type == 'image/png':
            format_name = 'PNG'
            ext = '.png'
        else:  # image/jpeg
            format_name = 'JPEG'
            ext = '.jpg'
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ext,
            prefix='sanitized_',
        )
        temp_file.close()  # Close immediately so Pillow can write to it
        
        # Re-encode image without EXIF
        # Pillow strips EXIF by default when saving without exif parameter
        image.save(temp_file.name, format=format_name)
        image.close()  # Close the image to release resources
        
        return temp_file.name
    
    def _sanitize_pdf(self, content: bytes) -> str:
        """Sanitize PDF by removing JavaScript and embedded files.
        
        Args:
            content: Raw PDF bytes
            
        Returns:
            Path to sanitized temporary file
        """
        # Load PDF
        pdf = pikepdf.open(io.BytesIO(content))
        
        # Remove JavaScript (if present)
        try:
            if '/Names' in pdf.Root:
                names = pdf.Root.Names
                if '/JavaScript' in names:
                    del names['/JavaScript']
        except Exception:
            pass  # Ignore errors in JavaScript removal
        
        # Remove embedded files (if present)
        try:
            if '/Names' in pdf.Root:
                names = pdf.Root.Names
                if '/EmbeddedFiles' in names:
                    del names['/EmbeddedFiles']
        except Exception:
            pass  # Ignore errors in embedded file removal
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.pdf',
            prefix='sanitized_',
        )
        temp_file.close()  # Close immediately so pikepdf can write to it
        
        # Save sanitized PDF
        pdf.save(temp_file.name)
        pdf.close()
        
        return temp_file.name
