"""Tests for access_requests serializers.

Tests RequestAccessSerializer with both legacy (justification) and new (document) flows.
"""

from io import BytesIO
from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .serializers import RequestAccessSerializer


class RequestAccessSerializerTests(TestCase):
    """Test RequestAccessSerializer validation logic."""

    def setUp(self):
        """Set up common test data."""
        self.base_data = {
            'email': 'student@pampangastateu.edu.ph',
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'requested_role': 'student',
        }

    def test_legacy_flow_with_justification(self):
        """Legacy flow: justification field is accepted."""
        data = {
            **self.base_data,
            'justification': 'I am a student at PSU CCS studying BSIS.',
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_new_flow_with_document(self):
        """New flow: document field is accepted."""
        # Create a mock image file
        image_content = b'fake image content'
        document = SimpleUploadedFile(
            'student_id.png',
            image_content,
            content_type='image/png'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_both_justification_and_document(self):
        """Validation fails when neither justification nor document is provided."""
        data = self.base_data.copy()
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
        self.assertEqual(
            serializer.errors['non_field_errors'][0].code,
            'MISSING_REQUIRED_FIELD'
        )

    def test_both_justification_and_document_provided(self):
        """Validation fails when both justification and document are provided."""
        document = SimpleUploadedFile(
            'student_id.png',
            b'fake image content',
            content_type='image/png'
        )
        
        data = {
            **self.base_data,
            'justification': 'I am a student at PSU CCS.',
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
        self.assertEqual(
            serializer.errors['non_field_errors'][0].code,
            'CONFLICTING_FIELDS'
        )

    def test_document_file_too_large(self):
        """Validation fails when document exceeds max file size."""
        # Create a file larger than 10MB
        large_content = b'x' * (11 * 1024 * 1024)  # 11MB
        document = SimpleUploadedFile(
            'student_id.png',
            large_content,
            content_type='image/png'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('document', serializer.errors)
        self.assertEqual(
            serializer.errors['document'][0].code,
            'FILE_TOO_LARGE'
        )

    def test_document_invalid_file_type(self):
        """Validation fails when document has invalid file extension."""
        document = SimpleUploadedFile(
            'document.txt',
            b'fake text content',
            content_type='text/plain'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('document', serializer.errors)
        self.assertEqual(
            serializer.errors['document'][0].code,
            'FILE_TYPE_NOT_ALLOWED'
        )

    def test_document_valid_png(self):
        """PNG files are accepted."""
        document = SimpleUploadedFile(
            'student_id.png',
            b'fake png content',
            content_type='image/png'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_document_valid_jpg(self):
        """JPG files are accepted."""
        document = SimpleUploadedFile(
            'student_id.jpg',
            b'fake jpg content',
            content_type='image/jpeg'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_document_valid_jpeg(self):
        """JPEG files are accepted."""
        document = SimpleUploadedFile(
            'student_id.jpeg',
            b'fake jpeg content',
            content_type='image/jpeg'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_document_valid_pdf(self):
        """PDF files are accepted."""
        document = SimpleUploadedFile(
            'cor.pdf',
            b'fake pdf content',
            content_type='application/pdf'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_email_validation_institutional_domain(self):
        """Email must be from institutional domain."""
        data = {
            **self.base_data,
            'email': 'student@gmail.com',
            'justification': 'I am a student at PSU CCS.',
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_requested_role_validation(self):
        """Requested role must be student or faculty."""
        data = {
            **self.base_data,
            'requested_role': 'administrator',
            'justification': 'I want to be an admin.',
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('requested_role', serializer.errors)
        self.assertEqual(
            serializer.errors['requested_role'][0].code,
            'INVALID_REQUESTED_ROLE'
        )

    def test_justification_too_short(self):
        """Justification must be at least 10 characters."""
        data = {
            **self.base_data,
            'justification': 'Short',
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('justification', serializer.errors)

    def test_justification_too_long(self):
        """Justification must not exceed 2000 characters."""
        data = {
            **self.base_data,
            'justification': 'x' * 2001,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('justification', serializer.errors)

    def test_document_case_insensitive_extension(self):
        """File extension validation is case-insensitive."""
        document = SimpleUploadedFile(
            'student_id.PNG',
            b'fake png content',
            content_type='image/png'
        )
        
        data = {
            **self.base_data,
            'document': document,
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_backward_compatibility_justification_optional(self):
        """Justification field is optional (for backward compatibility)."""
        # This test verifies that the field itself is optional
        # The cross-field validation will catch if neither justification nor document is provided
        data = {
            **self.base_data,
            'document': SimpleUploadedFile(
                'student_id.png',
                b'fake content',
                content_type='image/png'
            ),
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # Justification should not be in validated_data
        self.assertNotIn('justification', serializer.validated_data)

    def test_backward_compatibility_document_optional(self):
        """Document field is optional (for backward compatibility)."""
        data = {
            **self.base_data,
            'justification': 'I am a student at PSU CCS studying BSIS.',
        }
        serializer = RequestAccessSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # Document should not be in validated_data
        self.assertNotIn('document', serializer.validated_data)



class DocumentUploadIntegrationTests(TestCase):
    """Integration tests for document upload verification flow."""
    
    def setUp(self):
        """Set up test client and test data."""
        from rest_framework.test import APIClient
        self.client = APIClient(enforce_csrf_checks=False)
        self.url = '/api/v1/auth/request-access/'
        
        # Create a simple test image
        self.test_image = SimpleUploadedFile(
            name='test_student_id.png',
            content=b'PNG_IMAGE_DATA_HERE',
            content_type='image/png'
        )
    
    def tearDown(self):
        """Clear cache to prevent rate limiter interference between tests."""
        from django.core.cache import cache
        cache.clear()
    
    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_document_upload_creates_processing_request(self):
        """Document upload creates AccessRequest with status='processing'."""
        from unittest.mock import patch, MagicMock
        
        # Create a fresh test image for this test
        test_image = SimpleUploadedFile(
            name='test_student_id.png',
            content=b'PNG_IMAGE_DATA_HERE',
            content_type='image/png'
        )
        
        # Mock FileValidator to return valid result
        with patch('identity_verification.validators.file_validator.FileValidator') as mock_file_validator:
            mock_validator_instance = MagicMock()
            mock_validator_instance.validate.return_value = MagicMock(
                is_valid=True,
                detected_mime='image/png',
                errors=[],
            )
            mock_file_validator.return_value = mock_validator_instance
            
            # Mock VerificationOrchestrator to return pending result
            with patch('identity_verification.services.orchestrator.VerificationOrchestrator') as mock_orchestrator:
                mock_orchestrator_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.status = 'pending_manual_review'
                
                # Mock verify_request to also update the AccessRequest status
                def mock_verify_request(access_request_id):
                    from access_requests.models import AccessRequest
                    req = AccessRequest.objects.get(id=access_request_id)
                    req.status = 'pending'  # pending_manual_review maps to 'pending'
                    req.save()
                    return mock_result
                
                mock_orchestrator_instance.verify_request = mock_verify_request
                mock_orchestrator.return_value = mock_orchestrator_instance
                
                # Submit request with document
                response = self.client.post(
                    self.url,
                    {
                        'email': 'student@pampangastateu.edu.ph',
                        'first_name': 'Test',
                        'last_name': 'Student',
                        'requested_role': 'student',
                        'document': test_image,
                    },
                    format='multipart',
                    HTTP_ORIGIN='http://localhost:5173',
                )
                
                # Verify response
                self.assertEqual(response.status_code, 202)
                self.assertIn('access_request_id', response.data)
                self.assertIn('status', response.data)
                
                # Verify AccessRequest was created
                from access_requests.models import AccessRequest
                access_request = AccessRequest.objects.get(
                    email='student@pampangastateu.edu.ph'
                )
                self.assertEqual(access_request.status, 'pending')
                self.assertIsNone(access_request.justification)
                
                # Verify VerificationDocument was created
                from identity_verification.models import VerificationDocument
                self.assertTrue(
                    VerificationDocument.objects.filter(
                        access_request=access_request
                    ).exists()
                )
    
    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_auto_approved_calls_approve_request(self):
        """AUTO_APPROVED status triggers approve_request service."""
        from unittest.mock import patch, MagicMock
        
        # Create a fresh test image for this test
        test_image = SimpleUploadedFile(
            name='test_student_id.png',
            content=b'PNG_IMAGE_DATA_HERE',
            content_type='image/png'
        )
        
        # Mock FileValidator to return valid result
        with patch('identity_verification.validators.file_validator.FileValidator') as mock_file_validator:
            mock_validator_instance = MagicMock()
            mock_validator_instance.validate.return_value = MagicMock(
                is_valid=True,
                detected_mime='image/png',
                errors=[],
            )
            mock_file_validator.return_value = mock_validator_instance
            
            # Mock VerificationOrchestrator to return auto_approved result
            with patch('identity_verification.services.orchestrator.VerificationOrchestrator') as mock_orchestrator:
                mock_orchestrator_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.status = 'auto_approved'
                
                # Mock verify_request to also update the AccessRequest status
                def mock_verify_request(access_request_id):
                    from access_requests.models import AccessRequest
                    req = AccessRequest.objects.get(id=access_request_id)
                    req.status = 'processing'  # Keep as processing for AUTO_APPROVED
                    req.save()
                    return mock_result
                
                mock_orchestrator_instance.verify_request = mock_verify_request
                mock_orchestrator.return_value = mock_orchestrator_instance
                
                # Mock approve_request to succeed
                with patch('access_requests.services.approve_request') as mock_approve_request:
                    mock_approve_request.return_value = MagicMock()
                    
                    # Submit request with document
                    response = self.client.post(
                        self.url,
                        {
                            'email': 'student@pampangastateu.edu.ph',
                            'first_name': 'Test',
                            'last_name': 'Student',
                            'requested_role': 'student',
                            'document': test_image,
                        },
                        format='multipart',
                        HTTP_ORIGIN='http://localhost:5173',
                    )
                    
                    # Verify response
                    self.assertEqual(response.status_code, 202)
                    
                    # Verify approve_request was called
                    self.assertTrue(mock_approve_request.called)
                    call_args = mock_approve_request.call_args
                    self.assertIsNone(call_args.kwargs['reviewer'])  # System-initiated
                    self.assertEqual(
                        call_args.kwargs['note'],
                        'Automatically approved via identity verification'
                    )
    
    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_email_collision_changes_to_pending(self):
        """Email collision during AUTO_APPROVED changes status to pending."""
        from unittest.mock import patch, MagicMock
        from access_requests.services import AccessRequestEmailCollision
        
        # Create a fresh test image for this test
        test_image = SimpleUploadedFile(
            name='test_student_id.png',
            content=b'PNG_IMAGE_DATA_HERE',
            content_type='image/png'
        )
        
        # Mock FileValidator to return valid result
        with patch('identity_verification.validators.file_validator.FileValidator') as mock_file_validator:
            mock_validator_instance = MagicMock()
            mock_validator_instance.validate.return_value = MagicMock(
                is_valid=True,
                detected_mime='image/png',
                errors=[],
            )
            mock_file_validator.return_value = mock_validator_instance
            
            # Mock VerificationOrchestrator to return auto_approved result
            with patch('identity_verification.services.orchestrator.VerificationOrchestrator') as mock_orchestrator:
                mock_orchestrator_instance = MagicMock()
                mock_result = MagicMock()
                mock_result.status = 'auto_approved'
                
                # Mock verify_request to also update the AccessRequest status
                def mock_verify_request(access_request_id):
                    from access_requests.models import AccessRequest
                    from identity_verification.models import VerificationResult
                    req = AccessRequest.objects.get(id=access_request_id)
                    req.status = 'processing'  # Keep as processing for AUTO_APPROVED
                    req.save()
                    # Create and return a real VerificationResult so the view can update it
                    result = VerificationResult.objects.create(
                        access_request=req,
                        status='auto_approved',
                        processor_version='test-1.0',
                    )
                    return result
                
                mock_orchestrator_instance.verify_request = mock_verify_request
                mock_orchestrator.return_value = mock_orchestrator_instance
                
                # Mock approve_request to raise email collision
                with patch('access_requests.services.approve_request') as mock_approve_request:
                    mock_approve_request.side_effect = AccessRequestEmailCollision()
                    
                    # Submit request with document
                    response = self.client.post(
                        self.url,
                        {
                            'email': 'student@pampangastateu.edu.ph',
                            'first_name': 'Test',
                            'last_name': 'Student',
                            'requested_role': 'student',
                            'document': test_image,
                        },
                        format='multipart',
                        HTTP_ORIGIN='http://localhost:5173',
                    )
                    
                    # Verify response
                    self.assertEqual(response.status_code, 202)
                    
                    # Verify AccessRequest status changed to pending
                    from access_requests.models import AccessRequest
                    access_request = AccessRequest.objects.get(
                        email='student@pampangastateu.edu.ph'
                    )
                    self.assertEqual(access_request.status, 'pending')
                    
                    # Verify VerificationResult was updated
                    from identity_verification.models import VerificationResult
                    verification_result = VerificationResult.objects.get(
                        access_request=access_request
                    )
                    self.assertEqual(verification_result.status, 'pending_manual_review')
                    self.assertEqual(verification_result.decision_reason, 'email_collision')
                    self.assertIn('email_collision', verification_result.flagged_reasons)
    
    def test_legacy_justification_flow_still_works(self):
        """Legacy justification flow continues to work unchanged."""
        # Use APIClient which handles CSRF properly for tests
        response = self.client.post(
            self.url,
            {
                'email': 'student@pampangastateu.edu.ph',
                'first_name': 'Test',
                'last_name': 'Student',
                'requested_role': 'student',
                'justification': 'I am a student at PSU CCS.',
            },
            format='json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        
        # Verify response
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'pending')
        
        # Verify AccessRequest was created with justification
        from access_requests.models import AccessRequest
        access_request = AccessRequest.objects.get(
            email='student@pampangastateu.edu.ph'
        )
        self.assertEqual(access_request.status, 'pending')
        self.assertEqual(access_request.justification, 'I am a student at PSU CCS.')
        
        # Verify NO VerificationDocument was created
        from identity_verification.models import VerificationDocument
        self.assertFalse(
            VerificationDocument.objects.filter(
                access_request=access_request
            ).exists()
        )

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_document_upload_response_includes_verification_details(self):
        """Document upload response includes verification details for browser testing."""
        from unittest.mock import patch, MagicMock
        
        # Create a fresh test image for this test
        test_image = SimpleUploadedFile(
            name='test_student_id.png',
            content=b'PNG_IMAGE_DATA_HERE',
            content_type='image/png'
        )
        
        # Mock FileValidator to return valid result
        with patch('identity_verification.validators.file_validator.FileValidator') as mock_file_validator:
            mock_validator_instance = MagicMock()
            mock_validator_instance.validate.return_value = MagicMock(
                is_valid=True,
                detected_mime='image/png',
                errors=[],
            )
            mock_file_validator.return_value = mock_validator_instance
            
            # Mock VerificationOrchestrator to return pending_manual_review result
            with patch('identity_verification.services.orchestrator.VerificationOrchestrator') as mock_orchestrator:
                mock_orchestrator_instance = MagicMock()
                
                # Mock verify_request to create a real VerificationResult
                def mock_verify_request(access_request_id):
                    from access_requests.models import AccessRequest
                    from identity_verification.models import VerificationResult
                    req = AccessRequest.objects.get(id=access_request_id)
                    req.status = 'pending'
                    req.save()
                    
                    # Create VerificationResult with detailed information
                    result = VerificationResult.objects.create(
                        access_request=req,
                        status='pending_manual_review',
                        decision_reason='Low OCR confidence',
                        extracted_fields={
                            'full_name': 'Juan Dela Cruz',
                            'school_name': 'Pampanga State University',
                            'college': 'College of Computing Studies',
                            'program': 'BS Information Systems',
                        },
                        ocr_confidence=0.65,
                        flagged_reasons=['low_confidence'],
                        rule_failures=[],
                        processor_version='mvp-1.0',
                    )
                    return result
                
                mock_orchestrator_instance.verify_request = mock_verify_request
                mock_orchestrator.return_value = mock_orchestrator_instance
                
                # Submit request with document
                response = self.client.post(
                    self.url,
                    {
                        'email': 'test.verification@pampangastateu.edu.ph',
                        'first_name': 'Test',
                        'last_name': 'Verification',
                        'requested_role': 'student',
                        'document': test_image,
                    },
                    format='multipart',
                    HTTP_ORIGIN='http://localhost:5173',
                )
                
                # Verify response structure
                self.assertEqual(response.status_code, 202)
                self.assertIn('access_request_id', response.data)
                self.assertIn('status', response.data)
                self.assertIn('submitted_at', response.data)
                self.assertIn('verification', response.data)
                
                # Verify verification details are included
                verification = response.data['verification']
                self.assertEqual(verification['decision'], 'pending_manual_review')
                self.assertEqual(verification['decision_reason'], 'Low OCR confidence')
                self.assertEqual(verification['ocr_confidence'], 0.65)
                self.assertIn('low_confidence', verification['flagged_reasons'])
                
                # Verify extracted fields are included
                extracted = verification['extracted_fields']
                self.assertEqual(extracted['full_name'], 'Juan Dela Cruz')
                self.assertEqual(extracted['school_name'], 'Pampanga State University')
                self.assertEqual(extracted['college'], 'College of Computing Studies')
                self.assertEqual(extracted['program'], 'BS Information Systems')
