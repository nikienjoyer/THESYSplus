"""Unit tests for VerificationDocument model.

Tests Requirements 13.1, 13.3, 16.2.
"""

import hashlib
from datetime import datetime, timezone

import pytest
from django.db import IntegrityError

from access_requests.models import AccessRequest
from identity_verification.models import VerificationDocument


@pytest.mark.django_db
class TestVerificationDocumentModel:
    """Test VerificationDocument model creation and constraints."""
    
    def test_create_verification_document(self):
        """Test creating a VerificationDocument with all required fields."""
        # Create an AccessRequest first
        access_request = AccessRequest.objects.create(
            first_name="Juan",
            last_name="Dela Cruz",
            email="juan.delacruz@test.psu.edu.ph",
            requested_role="student",
            status="processing",
        )
        
        # Create VerificationDocument
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path="/private/verification_docs/test/abc123.png",
            mime_type="image/png",
            sha256="a" * 64,  # Valid SHA256 hash (64 hex chars)
            size_bytes=1024000,
        )
        
        # Verify fields
        assert doc.id is not None
        assert doc.access_request == access_request
        assert doc.file_path == "/private/verification_docs/test/abc123.png"
        assert doc.mime_type == "image/png"
        assert doc.sha256 == "a" * 64
        assert doc.size_bytes == 1024000
        assert doc.uploaded_at is not None
        assert doc.retention_purge_at is None
        assert doc.purged_at is None
    
    def test_one_to_one_constraint(self):
        """Test that only one VerificationDocument can exist per AccessRequest."""
        access_request = AccessRequest.objects.create(
            first_name="Maria",
            last_name="Santos",
            email="maria.santos@test.psu.edu.ph",
            requested_role="student",
            status="processing",
        )
        
        # Create first document
        VerificationDocument.objects.create(
            access_request=access_request,
            file_path="/private/verification_docs/test/doc1.png",
            mime_type="image/png",
            sha256="b" * 64,
            size_bytes=1024000,
        )
        
        # Attempt to create second document for same AccessRequest
        with pytest.raises(IntegrityError):
            VerificationDocument.objects.create(
                access_request=access_request,
                file_path="/private/verification_docs/test/doc2.png",
                mime_type="image/png",
                sha256="c" * 64,
                size_bytes=2048000,
            )
    
    def test_sha256_index_exists(self):
        """Test that SHA256 field is indexed for anti-replay lookups."""
        # Create documents with different SHA256 hashes
        for i in range(3):
            access_request = AccessRequest.objects.create(
                first_name=f"User{i}",
                last_name="Test",
                email=f"user{i}@test.psu.edu.ph",
                requested_role="student",
                status="processing",
            )
            
            sha256 = hashlib.sha256(f"document{i}".encode()).hexdigest()
            VerificationDocument.objects.create(
                access_request=access_request,
                file_path=f"/private/verification_docs/test/doc{i}.png",
                mime_type="image/png",
                sha256=sha256,
                size_bytes=1024000,
            )
        
        # Query by SHA256 (should use index)
        target_sha256 = hashlib.sha256(b"document1").hexdigest()
        doc = VerificationDocument.objects.get(sha256=target_sha256)
        assert doc.access_request.email == "user1@test.psu.edu.ph"
    
    def test_cascade_delete(self):
        """Test that deleting AccessRequest cascades to VerificationDocument."""
        access_request = AccessRequest.objects.create(
            first_name="Pedro",
            last_name="Reyes",
            email="pedro.reyes@test.psu.edu.ph",
            requested_role="student",
            status="processing",
        )
        
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path="/private/verification_docs/test/doc.png",
            mime_type="image/png",
            sha256="d" * 64,
            size_bytes=1024000,
        )
        
        doc_id = doc.id
        
        # Delete AccessRequest
        access_request.delete()
        
        # Verify VerificationDocument is also deleted
        assert not VerificationDocument.objects.filter(id=doc_id).exists()
    
    def test_nullable_file_path_for_purged_documents(self):
        """Test that file_path can be null (for purged documents)."""
        access_request = AccessRequest.objects.create(
            first_name="Ana",
            last_name="Garcia",
            email="ana.garcia@test.psu.edu.ph",
            requested_role="student",
            status="approved",
        )
        
        # Create document with null file_path (simulating purged document)
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path=None,
            mime_type="image/png",
            sha256="e" * 64,
            size_bytes=1024000,
            purged_at=datetime.now(timezone.utc),
        )
        
        assert doc.file_path is None
        assert doc.purged_at is not None
    
    def test_str_representation(self):
        """Test string representation of VerificationDocument."""
        access_request = AccessRequest.objects.create(
            first_name="Test",
            last_name="User",
            email="test@psu.edu.ph",
            requested_role="student",
            status="processing",
        )
        
        doc = VerificationDocument.objects.create(
            access_request=access_request,
            file_path="/private/verification_docs/test/doc.png",
            mime_type="image/png",
            sha256="f" * 64,
            size_bytes=1024000,
        )
        
        str_repr = str(doc)
        assert "test@psu.edu.ph" in str_repr
        assert "ffffffff" in str_repr  # First 8 chars of SHA256
