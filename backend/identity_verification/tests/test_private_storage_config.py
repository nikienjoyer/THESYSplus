"""
Tests for private file storage configuration.

Validates that private storage settings are correctly configured per
Requirements 15.1, 15.3 (secure storage, not publicly accessible).
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase


class PrivateStorageConfigTest(TestCase):
    """Test private file storage configuration."""

    def test_private_storage_root_is_configured(self):
        """PRIVATE_STORAGE_ROOT setting exists and points to private_media directory."""
        self.assertTrue(hasattr(settings, 'PRIVATE_STORAGE_ROOT'))
        self.assertIsInstance(settings.PRIVATE_STORAGE_ROOT, Path)
        self.assertEqual(settings.PRIVATE_STORAGE_ROOT.name, 'private_media')

    def test_verification_docs_path_is_configured(self):
        """VERIFICATION_DOCS_PATH setting exists and is set to 'verification_docs'."""
        self.assertTrue(hasattr(settings, 'VERIFICATION_DOCS_PATH'))
        self.assertEqual(settings.VERIFICATION_DOCS_PATH, 'verification_docs')

    def test_private_storage_is_under_base_dir(self):
        """Private storage is located under BASE_DIR (backend directory)."""
        self.assertTrue(settings.PRIVATE_STORAGE_ROOT.is_relative_to(settings.BASE_DIR))

    def test_private_storage_is_not_media_root(self):
        """Private storage is separate from MEDIA_ROOT (if MEDIA_ROOT exists)."""
        # MEDIA_ROOT should not be configured to avoid accidental public exposure
        # If it exists, it should be different from PRIVATE_STORAGE_ROOT
        if hasattr(settings, 'MEDIA_ROOT'):
            self.assertNotEqual(settings.MEDIA_ROOT, settings.PRIVATE_STORAGE_ROOT)

    def test_private_storage_directory_exists(self):
        """Private storage directory exists on filesystem."""
        self.assertTrue(settings.PRIVATE_STORAGE_ROOT.exists())
        self.assertTrue(settings.PRIVATE_STORAGE_ROOT.is_dir())

    def test_verification_docs_subdirectory_exists(self):
        """verification_docs subdirectory exists under private storage."""
        verification_docs_dir = settings.PRIVATE_STORAGE_ROOT / settings.VERIFICATION_DOCS_PATH
        self.assertTrue(verification_docs_dir.exists())
        self.assertTrue(verification_docs_dir.is_dir())

    def test_identity_verification_settings_exist(self):
        """IDENTITY_VERIFICATION settings dict is configured."""
        self.assertTrue(hasattr(settings, 'IDENTITY_VERIFICATION'))
        self.assertIsInstance(settings.IDENTITY_VERIFICATION, dict)

    def test_identity_verification_has_required_keys(self):
        """IDENTITY_VERIFICATION dict contains all required configuration keys."""
        required_keys = [
            'SYNC_MODE',
            'MAX_FILE_SIZE_MB',
            'ALLOWED_EXTENSIONS',
            'ALLOWED_MIME_TYPES',
            'OCR_CONFIDENCE_THRESHOLDS',
            'OCR_TIMEOUT_SECONDS',
            'INSTITUTIONS',
            'COLLEGES',
            'PROGRAMS_CANONICAL',
        ]
        for key in required_keys:
            with self.subTest(key=key):
                self.assertIn(key, settings.IDENTITY_VERIFICATION)

    def test_ocr_confidence_thresholds_are_valid(self):
        """OCR confidence thresholds are properly configured."""
        thresholds = settings.IDENTITY_VERIFICATION['OCR_CONFIDENCE_THRESHOLDS']
        self.assertIn('HIGH', thresholds)
        self.assertIn('MEDIUM', thresholds)
        self.assertEqual(thresholds['HIGH'], 75)
        self.assertEqual(thresholds['MEDIUM'], 60)
        # HIGH threshold should be greater than MEDIUM
        self.assertGreater(thresholds['HIGH'], thresholds['MEDIUM'])

    def test_canonical_reference_data_is_configured(self):
        """Canonical institutions, colleges, and programs are configured."""
        config = settings.IDENTITY_VERIFICATION
        
        # Institutions
        self.assertIn('Pampanga State University', config['INSTITUTIONS'])
        
        # Colleges
        self.assertIn('College of Computing Studies', config['COLLEGES'])
        self.assertIn('CCS', config['COLLEGES'])
        
        # Programs
        expected_programs = [
            'BS Information System',
            'BS Information Technology',
            'BS Computer Science',
            'Associate in Computer Technology',
        ]
        for program in expected_programs:
            with self.subTest(program=program):
                self.assertIn(program, config['PROGRAMS_CANONICAL'])

    def test_file_validation_settings_are_configured(self):
        """File validation settings (size, extensions, MIME types) are configured."""
        config = settings.IDENTITY_VERIFICATION
        
        # Max file size
        self.assertEqual(config['MAX_FILE_SIZE_MB'], 10)
        
        # Allowed extensions
        expected_extensions = ['png', 'jpg', 'jpeg', 'pdf']
        for ext in expected_extensions:
            with self.subTest(extension=ext):
                self.assertIn(ext, config['ALLOWED_EXTENSIONS'])
        
        # Allowed MIME types
        expected_mime_types = [
            'image/png',
            'image/jpeg',
            'application/pdf',
        ]
        for mime_type in expected_mime_types:
            with self.subTest(mime_type=mime_type):
                self.assertIn(mime_type, config['ALLOWED_MIME_TYPES'])
