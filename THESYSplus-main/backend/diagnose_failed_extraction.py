#!/usr/bin/env python
"""Diagnostic script to investigate failed field extraction.

Retrieves the VerificationResult for a specific access request and tests
the FieldExtractor directly against the raw OCR text.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from identity_verification.models import VerificationResult
from identity_verification.services.field_extractor import FieldExtractor


def print_separator(title=""):
    """Print a visual separator."""
    if title:
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80 + "\n")
    else:
        print("\n" + "=" * 80 + "\n")


def diagnose_request(access_request_id: str):
    """Diagnose why field extraction failed for a specific request."""
    
    print_separator("DIAGNOSTIC REPORT: Failed Field Extraction")
    
    print(f"Access Request ID: {access_request_id}")
    print()
    
    # Retrieve VerificationResult
    try:
        result = VerificationResult.objects.get(access_request_id=access_request_id)
    except VerificationResult.DoesNotExist:
        print(f"❌ ERROR: No VerificationResult found for access_request_id={access_request_id}")
        return
    
    print(f"Verification Result ID: {result.id}")
    print(f"OCR Confidence: {result.ocr_confidence}%")
    print(f"Status: {result.status}")
    print(f"Decision Reason: {result.decision_reason}")
    
    print_separator("1. RAW OCR TEXT")
    
    ocr_text = result.ocr_raw_text or ""
    
    if not ocr_text:
        print("❌ ERROR: ocr_raw_text is empty or null")
        return
    
    print("Raw OCR Text:")
    print("-" * 80)
    print(ocr_text)
    print("-" * 80)
    print(f"\nLength: {len(ocr_text)} characters")
    print(f"Lines: {len(ocr_text.splitlines())} lines")
    
    print_separator("2. STORED EXTRACTED FIELDS (from database)")
    
    # Extract fields from JSON
    extracted_fields = result.extracted_fields or {}
    
    print(f"Full Name:       {extracted_fields.get('full_name')}")
    print(f"School Name:     {extracted_fields.get('school_name')}")
    print(f"College:         {extracted_fields.get('college')}")
    print(f"Program (raw):   {extracted_fields.get('program_raw')}")
    print(f"Program (norm):  {extracted_fields.get('program')}")
    print(f"Student Number:  {extracted_fields.get('student_number')}")
    
    print_separator("3. DIRECT FIELD EXTRACTOR TEST")
    
    # Test FieldExtractor directly
    extractor = FieldExtractor()
    extracted = extractor.extract(ocr_text)
    
    print("Direct FieldExtractor Output:")
    print(f"  Full Name:       {extracted.full_name}")
    print(f"  School Name:     {extracted.school_name}")
    print(f"  College:         {extracted.college}")
    print(f"  Program (raw):   {extracted.program_raw}")
    print(f"  Program (norm):  {extracted.program}")
    print(f"  Student Number:  {extracted.student_number}")
    
    print_separator("4. ANALYSIS")
    
    # Analyze why extraction failed
    issues = []
    
    # Check OCR confidence
    if result.ocr_confidence < 75:
        issues.append(f"⚠️  LOW OCR CONFIDENCE: {result.ocr_confidence}% (threshold: 75%)")
        issues.append("    → OCR quality issue: Text may be unclear, blurry, or poorly scanned")
    
    # Check if any fields were extracted
    fields_extracted = [
        extracted.full_name,
        extracted.school_name,
        extracted.program,
        extracted.student_number
    ]
    
    if not any(fields_extracted):
        issues.append("❌ COMPLETE EXTRACTION FAILURE: No fields extracted")
        issues.append("    → Possible causes:")
        issues.append("      1. OCR text format doesn't match any patterns")
        issues.append("      2. Text is too corrupted or garbled")
        issues.append("      3. Document is not a PSU student ID or COR")
    else:
        # Check individual fields
        if not extracted.full_name:
            issues.append("❌ Full name not extracted")
            issues.append("    → Check if name appears in OCR text")
            issues.append("    → Check if name format matches patterns")
        
        if not extracted.school_name:
            issues.append("❌ School name not extracted")
            issues.append("    → Check if 'PAMPANGA STATE UNIVERSITY' or 'DHVSU' appears")
            issues.append("    → Check for OCR typos in university name")
        
        if not extracted.program:
            issues.append("❌ Program not extracted")
            issues.append("    → Check if program name appears (Information Systems, etc.)")
            issues.append("    → Check for OCR typos in program name")
        
        if not extracted.student_number:
            issues.append("❌ Student number not extracted")
            issues.append("    → Check if 8-10 digit number appears")
            issues.append("    → Check if number is split across lines")
    
    # Check for specific patterns in OCR text
    ocr_upper = ocr_text.upper()
    
    print("Pattern Detection:")
    print()
    
    # University patterns
    if 'PAMPANGA STATE UNIVERSITY' in ocr_upper:
        print("✅ Found: 'PAMPANGA STATE UNIVERSITY'")
    elif 'DON HONORIO VENTURA' in ocr_upper:
        print("✅ Found: 'DON HONORIO VENTURA'")
    elif 'DHVSU' in ocr_upper:
        print("✅ Found: 'DHVSU'")
    elif 'UNIVERSITY' in ocr_upper:
        print("⚠️  Found: 'UNIVERSITY' (but not PSU)")
    else:
        print("❌ No university name detected")
    
    # Program patterns
    program_keywords = ['INFORMATION SYSTEM', 'INFORMATION TECHNOLOGY', 'COMPUTER SCIENCE', 'COMPUTER TECHNOLOGY']
    found_program = False
    for keyword in program_keywords:
        if keyword in ocr_upper:
            print(f"✅ Found program keyword: '{keyword}'")
            found_program = True
            break
    if not found_program:
        print("❌ No program keywords detected")
    
    # Number patterns
    import re
    numbers = re.findall(r'\d{8,10}', ocr_text)
    if numbers:
        print(f"✅ Found potential student numbers: {numbers}")
    else:
        print("❌ No 8-10 digit numbers detected")
    
    # Name patterns (uppercase words)
    lines = ocr_text.split('\n')
    uppercase_lines = [line.strip() for line in lines if line.strip().isupper() and len(line.strip().split()) in [2, 3, 4]]
    if uppercase_lines:
        print(f"✅ Found potential name lines: {uppercase_lines[:3]}")
    else:
        print("❌ No uppercase name patterns detected")
    
    print()
    print("Issues Detected:")
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("✅ No obvious issues detected")
    
    print_separator("5. CONCLUSION")
    
    # Determine root cause
    if result.ocr_confidence < 50:
        print("ROOT CAUSE: Very Low OCR Quality (<50%)")
        print("  → The document image is too poor quality for reliable OCR")
        print("  → Recommendation: Request user to upload a clearer image")
        print("  → This is an OCR QUALITY ISSUE, not a regex issue")
    elif result.ocr_confidence < 75:
        print("ROOT CAUSE: Low OCR Quality (50-75%)")
        print("  → The OCR text is readable but contains errors/noise")
        print("  → Extraction patterns may not match due to OCR typos")
        print("  → This is primarily an OCR QUALITY ISSUE")
        print("  → Fallback patterns may help but won't fix poor OCR")
    elif not any(fields_extracted):
        print("ROOT CAUSE: Pattern Mismatch")
        print("  → OCR confidence is acceptable but no fields extracted")
        print("  → The document format doesn't match expected patterns")
        print("  → This is a REGEX/PATTERN ISSUE")
        print("  → Recommendation: Review OCR text and update extraction patterns")
    else:
        print("ROOT CAUSE: Partial Extraction")
        print("  → Some fields extracted, others missing")
        print("  → May be due to OCR errors or pattern gaps")
        print("  → Review specific missing fields above")
    
    print_separator()


if __name__ == "__main__":
    # Access request ID from the failed request
    access_request_id = "600fe2b0-36af-4391-9c0d-48d719894340"
    
    diagnose_request(access_request_id)
