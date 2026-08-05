#!/usr/bin/env python
"""Inspect OCR raw text for a specific access request."""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from identity_verification.models import VerificationResult
from identity_verification.services.field_extractor import FieldExtractor


def inspect_request(access_request_id: str):
    """Inspect OCR text and extraction for a specific request."""
    
    print("=" * 80)
    print(f"Access Request ID: {access_request_id}")
    print("=" * 80)
    
    # Retrieve VerificationResult
    try:
        result = VerificationResult.objects.get(access_request_id=access_request_id)
    except VerificationResult.DoesNotExist:
        print(f"ERROR: No VerificationResult found")
        return
    
    print(f"\nOCR Confidence: {result.ocr_confidence}%")
    print(f"Status: {result.status}")
    
    print("\n" + "=" * 80)
    print("RAW OCR TEXT")
    print("=" * 80)
    print(result.ocr_raw_text)
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print("CURRENT EXTRACTED FIELDS (from database)")
    print("=" * 80)
    
    extracted_fields = result.extracted_fields or {}
    print(f"full_name:       {extracted_fields.get('full_name')}")
    print(f"school_name:     {extracted_fields.get('school_name')}")
    print(f"college:         {extracted_fields.get('college')}")
    print(f"program:         {extracted_fields.get('program')}")
    print(f"program_raw:     {extracted_fields.get('program_raw')}")
    print(f"student_number:  {extracted_fields.get('student_number')}")
    
    print("\n" + "=" * 80)
    print("DIRECT FIELD EXTRACTOR TEST (current implementation)")
    print("=" * 80)
    
    extractor = FieldExtractor()
    extracted = extractor.extract(result.ocr_raw_text)
    
    print(f"full_name:       {extracted.full_name}")
    print(f"school_name:     {extracted.school_name}")
    print(f"college:         {extracted.college}")
    print(f"program:         {extracted.program}")
    print(f"program_raw:     {extracted.program_raw}")
    print(f"student_number:  {extracted.student_number}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    access_request_id = "c5ab9382-abb8-4148-8ea6-612158878f90"
    inspect_request(access_request_id)
