"""File validation for thesis uploads — Phase 1.

Lightweight, separate from identity_verification's FileValidator (which
focuses on image sanitization). For theses we accept PDF and DOCX up to
25 MB and verify the magic bytes match the declared extension.
"""

from __future__ import annotations

from dataclasses import dataclass

# 25 MB per Phase 1 spec
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = ('pdf', 'docx')

# DOCX is a ZIP container ('PK\x03\x04'); PDFs start with '%PDF-'
_PDF_MAGIC = b'%PDF-'
_ZIP_MAGIC = b'PK\x03\x04'


@dataclass(frozen=True)
class FileValidationResult:
    is_valid: bool
    error_code: str | None = None
    error_message: str | None = None
    detected_type: str | None = None  # 'pdf' or 'docx'
    size_bytes: int = 0


def validate_thesis_file(uploaded_file) -> FileValidationResult:
    """Validate an uploaded thesis file (PDF or DOCX, ≤25 MB).

    Args:
        uploaded_file: A Django ``UploadedFile`` (from ``request.FILES``).

    Returns:
        FileValidationResult — ``is_valid`` flag + structured error code.
    """
    if uploaded_file is None:
        return FileValidationResult(
            is_valid=False,
            error_code='MISSING_FILE',
            error_message='No file was uploaded.',
        )

    name = (uploaded_file.name or '').lower()
    size = uploaded_file.size or 0

    # Size check first — cheapest
    if size > MAX_FILE_SIZE_BYTES:
        return FileValidationResult(
            is_valid=False,
            error_code='FILE_TOO_LARGE',
            error_message=f'File size must not exceed {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.',
            size_bytes=size,
        )

    # Extension check
    ext = name.rsplit('.', 1)[-1] if '.' in name else ''
    if ext not in ALLOWED_EXTENSIONS:
        return FileValidationResult(
            is_valid=False,
            error_code='FILE_TYPE_NOT_ALLOWED',
            error_message='Only PDF and DOCX files are allowed.',
            size_bytes=size,
        )

    # Magic-byte check
    try:
        uploaded_file.seek(0)
        head = uploaded_file.read(8)
        uploaded_file.seek(0)
    except Exception as exc:  # pragma: no cover - defensive
        return FileValidationResult(
            is_valid=False,
            error_code='FILE_CORRUPT',
            error_message=f'Could not read file: {exc}',
            size_bytes=size,
        )

    if ext == 'pdf':
        if not head.startswith(_PDF_MAGIC):
            return FileValidationResult(
                is_valid=False,
                error_code='FILE_TYPE_MISMATCH',
                error_message='File extension is .pdf but the file is not a valid PDF.',
                size_bytes=size,
            )
        return FileValidationResult(is_valid=True, detected_type='pdf', size_bytes=size)

    # ext == 'docx'
    if not head.startswith(_ZIP_MAGIC):
        return FileValidationResult(
            is_valid=False,
            error_code='FILE_TYPE_MISMATCH',
            error_message='File extension is .docx but the file is not a valid DOCX.',
            size_bytes=size,
        )
    return FileValidationResult(is_valid=True, detected_type='docx', size_bytes=size)
