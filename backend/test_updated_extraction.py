#!/usr/bin/env python
"""Test updated FieldExtractor with actual OCR text."""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from identity_verification.models import VerificationResult
from identity_verification.services.field_extractor import FieldExtractor


def test_updated_extraction(access_request_id: str):
    """Test updated extraction on actual OCR text."""
    
    print("=" * 80)
    print("UPDATED FIELD EXTRACTOR TEST")
    print("=" * 80)
    
    # Retrieve VerificationResult
    try:
        result = VerificationResult.objects.get(access_request_id=access_request_id)
    except VerificationResult.DoesNotExist:
        print(f"ERROR: No VerificationResult found")
        return
    
    ocr_text = result.ocr_raw_text
    
    print("\nRAW OCR TEXT:")
    print("-" * 80)
    print(ocr_text)
    print("-" * 80)
    
    print("\nOLD EXTRACTED FIELDS (from database):")
    print("-" * 80)
    old_fields = result.extracted_fields or {}
    print(f"full_name:       {old_fields.get('full_name')} {'❌' if old_fields.get('full_name') == 'Main Campus' else '✅'}")
    print(f"school_name:     {old_fields.get('school_name')} {'❌' if not old_fields.get('school_name') else '✅'}")
    print(f"college:         {old_fields.get('college')}")
    print(f"program:         {old_fields.get('program')} {'✅' if old_fields.get('program') else '❌'}")
    print(f"program_raw:     {old_fields.get('program_raw')} {'✅' if old_fields.get('program_raw') else '❌'}")
    print(f"student_number:  {old_fields.get('student_number')} {'✅' if old_fields.get('student_number') else '❌'}")
    
    print("\nNEW EXTRACTED FIELDS (updated FieldExtractor):")
    print("-" * 80)
    
    extractor = FieldExtractor()
    new_fields = extractor.extract(ocr_text)
    
    print(f"full_name:       {new_fields.full_name} {'✅' if new_fields.full_name and 'KURT' in new_fields.full_name.upper() else '❌'}")
    print(f"school_name:     {new_fields.school_name} {'✅' if new_fields.school_name else '❌'}")
    print(f"college:         {new_fields.college}")
    print(f"program:         {new_fields.program} {'✅' if new_fields.program else '❌'}")
    print(f"program_raw:     {new_fields.program_raw} {'✅' if new_fields.program_raw else '❌'}")
    print(f"student_number:  {new_fields.student_number} {'✅' if new_fields.student_number else '❌'}")
    
    print("\nCOMPARISON:")
    print("-" * 80)
    
    improvements = []
    regressions = []
    
    # Check full_name
    if old_fields.get('full_name') == 'Main Campus' and new_fields.full_name and 'KURT' in new_fields.full_name.upper():
        improvements.append("✅ full_name: Fixed (was 'Main Campus', now correct name)")
    elif old_fields.get('full_name') != new_fields.full_name:
        if new_fields.full_name:
            improvements.append(f"✅ full_name: Changed from '{old_fields.get('full_name')}' to '{new_fields.full_name}'")
        else:
            regressions.append(f"❌ full_name: Lost extraction (was '{old_fields.get('full_name')}')")
    
    # Check school_name
    if not old_fields.get('school_name') and new_fields.school_name:
        improvements.append(f"✅ school_name: Now extracted ('{new_fields.school_name}')")
    elif old_fields.get('school_name') and not new_fields.school_name:
        regressions.append(f"❌ school_name: Lost extraction (was '{old_fields.get('school_name')}')")
    
    # Check program (should stay the same)
    if old_fields.get('program') == new_fields.program:
        improvements.append(f"✅ program: Preserved ('{new_fields.program}')")
    else:
        if new_fields.program:
            improvements.append(f"⚠️  program: Changed from '{old_fields.get('program')}' to '{new_fields.program}'")
        else:
            regressions.append(f"❌ program: Lost extraction (was '{old_fields.get('program')}')")
    
    # Check student_number (should stay the same)
    if old_fields.get('student_number') == new_fields.student_number:
        improvements.append(f"✅ student_number: Preserved ('{new_fields.student_number}')")
    else:
        if new_fields.student_number:
            improvements.append(f"⚠️  student_number: Changed from '{old_fields.get('student_number')}' to '{new_fields.student_number}'")
        else:
            regressions.append(f"❌ student_number: Lost extraction (was '{old_fields.get('student_number')}')")
    
    if improvements:
        print("\nImprovements:")
        for imp in improvements:
            print(f"  {imp}")
    
    if regressions:
        print("\nRegressions:")
        for reg in regressions:
            print(f"  {reg}")
    
    if not regressions:
        print("\n✅ SUCCESS: No regressions detected")
    else:
        print("\n❌ FAILURE: Regressions detected")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    access_request_id = "c5ab9382-abb8-4148-8ea6-612158878f90"
    test_updated_extraction(access_request_id)
