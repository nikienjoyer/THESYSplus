# THESYS+ Backend

Django REST API backend for the THESYS+ authentication and identity verification system.

## Features

- User authentication (login, logout, token refresh)
- Access request management with AI-assisted identity verification
- Role-based access control (Student, Faculty, Administrator)
- Audit logging for security events
- OCR-based document verification for Student IDs and CORs

## Requirements

### Python Dependencies

Install Python dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### System Dependencies

#### Tesseract OCR

The identity verification feature requires Tesseract OCR for text extraction from uploaded documents.

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
1. Download the installer from [GitHub Releases](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer and follow the setup wizard
3. Add Tesseract to your PATH environment variable
4. Verify installation: `tesseract --version`

**Docker:**
```dockerfile
RUN apt-get update && apt-get install -y tesseract-ocr
```

#### Poppler (for PDF processing)

Required for converting PDF documents to images before OCR.

**Ubuntu/Debian:**
```bash
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

**Windows:**
1. Download from [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
2. Extract and add `bin/` directory to PATH

## Configuration

### Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/thesys

# Email (for activation emails)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Identity Verification
IDENTITY_VERIFICATION_SYNC=True
```

### Tesseract Configuration

If Tesseract is installed in a non-standard location, set the `TESSDATA_PREFIX` environment variable:

```bash
export TESSDATA_PREFIX=/usr/local/share/tessdata/
```

## Running the Server

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Run migrations
python manage.py migrate --settings=thesys.settings.dev

# Start development server
python manage.py runserver --settings=thesys.settings.dev
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test module
pytest identity_verification/tests/test_ocr_extractor.py

# Run with coverage
pytest --cov=identity_verification --cov-report=html
```

**Note:** Integration tests that require Tesseract will be skipped if Tesseract is not installed.

## Troubleshooting

### Tesseract Not Found

If you see `TesseractNotFoundError`:

1. Verify Tesseract is installed: `tesseract --version`
2. Check PATH includes Tesseract binary directory
3. Set `TESSDATA_PREFIX` if using custom installation path

### OCR Low Confidence

If OCR confidence scores are consistently low:

1. Ensure uploaded documents are high-resolution (300 DPI recommended)
2. Check document image quality (clear text, good contrast)
3. Verify Tesseract language data is installed: `tesseract --list-langs`

### PDF Conversion Fails

If PDF to image conversion fails:

1. Verify Poppler is installed: `pdftoppm -v`
2. Check PDF is not encrypted or password-protected
3. Ensure sufficient disk space for temporary image files

## MVP Limitations

This is a **capstone-safe MVP** implementation with the following limitations:

- **NO SBERT semantic validation** (deferred to post-MVP)
- **NO TF-IDF keyword validation** (deferred to post-MVP)
- **NO Celery async processing** (synchronous only)
- **NO Redis broker** (not required for synchronous processing)
- **NO retention purge jobs** (manual cleanup only)
- **NO anti-replay enforcement** (deferred to post-MVP)
- **NO advanced admin review endpoints** with signed document URLs (basic review only)

These features can be added in future iterations after the capstone project is complete.

## Architecture

### Apps

- **accounts**: User model and authentication
- **access_requests**: Access request management
- **identity_verification**: OCR and document verification (MVP)
- **audit**: Audit logging for security events

### Identity Verification Pipeline (MVP)

1. **File Upload**: User uploads Student ID or COR (PNG, JPEG, PDF)
2. **File Validation**: Magic byte check, size limit, sanitization
3. **OCR Extraction**: Tesseract extracts text from document
4. **Field Extraction**: Regex patterns extract structured fields
5. **Program Normalization**: Normalize program aliases (BSIS → BS Information System)
6. **Rule Validation**: Check institution, college, program against whitelist
7. **Decision Engine**: OCR confidence + rule validation → AUTO_APPROVED, PENDING_MANUAL_REVIEW, or REJECTED
8. **Auto-Approval**: If AUTO_APPROVED, trigger activation email

## License

Proprietary - THESYS+ Capstone Project
