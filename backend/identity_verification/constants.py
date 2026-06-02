"""Constants for identity verification.

Error codes, validation thresholds, and canonical reference data.
"""

# File validation error codes
MISSING_DOCUMENT = 'MISSING_DOCUMENT'
FILE_TYPE_NOT_ALLOWED = 'FILE_TYPE_NOT_ALLOWED'
FILE_TOO_LARGE = 'FILE_TOO_LARGE'
FILE_CORRUPT = 'FILE_CORRUPT'
FILE_TYPE_MISMATCH = 'FILE_TYPE_MISMATCH'

# Allowed file types
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
ALLOWED_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'application/pdf',
}

# Magic byte signatures for validation
MAGIC_SIGNATURES = {
    'image/png': b'\x89PNG\r\n\x1a\n',
    'image/jpeg': b'\xff\xd8\xff',
    'application/pdf': b'%PDF-',
}
