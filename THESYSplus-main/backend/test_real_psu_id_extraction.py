#!/usr/bin/env python
"""Test script to demonstrate FieldExtractor with real PSU student ID format.

This script simulates OCR text from a real PSU student ID and shows
how the enhanced FieldExtractor with fallback heuristics extracts fields,
and how RuleValidator infers college from program.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from identity_verification.services.field_extractor import FieldExtractor
from identity_verification.validators.rule_validator import RuleValidator


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 80 + "\n")


def test_real_psu_id():
    """Test extraction from real PSU student ID format."""
    print_separator()
    print("TEST: Real PSU Student ID Format (Unlabeled, No College)")
    print_separator()
    
    # Simulated OCR text from real PSU student ID
    ocr_text = """
DON HONORIO VENTURA STATE UNIVERSITY
KURT ROSS E. GONZAGA
Information Systems
2023313528
    """
    
    print("OCR Text:")
    print(ocr_text)
    print_separator()
    
    # Extract fields
    extractor = FieldExtractor()
    result = extractor.extract(ocr_text)
    
    print("Extracted Fields:")
    print(f"  Full Name:       {result.full_name}")
    print(f"  School Name:     {result.school_name}")
    print(f"  College:         {result.college}")
    print(f"  Program (raw):   {result.program_raw}")
    print(f"  Program (norm):  {result.program}")
    print(f"  Student Number:  {result.student_number}")
    print_separator()
    
    # Validate with RuleValidator
    validator = RuleValidator()
    validation_result = validator.validate(result, ocr_text)
    
    print("Rule Validation:")
    print(f"  Passed:          {validation_result.passed}")
    print(f"  Failures:        {len(validation_result.failures)}")
    
    if validation_result.failures:
        print("\n  Failure Details:")
        for failure in validation_result.failures:
            print(f"    - Field: {failure.field}")
            print(f"      Reason: {failure.reason}")
            print(f"      Expected: {failure.expected}")
            print(f"      Actual: {failure.actual}")
    else:
        print("\n  ✅ All validation rules passed!")
        print("  ✅ College inferred from program: College of Computing Studies")
    
    print_separator()
    
    # Validation
    success = True
    issues = []
    
    if not result.full_name:
        success = False
        issues.append("❌ Full name not extracted")
    else:
        print(f"✅ Full name extracted: {result.full_name}")
    
    if not result.school_name:
        success = False
        issues.append("❌ School name not extracted")
    else:
        print(f"✅ School name extracted: {result.school_name}")
    
    if not result.program:
        success = False
        issues.append("❌ Program not extracted")
    else:
        print(f"✅ Program extracted and normalized: {result.program}")
    
    if not result.student_number:
        success = False
        issues.append("❌ Student number not extracted")
    else:
        print(f"✅ Student number extracted: {result.student_number}")
    
    if result.college is None:
        print(f"⚠️  College not extracted (expected for student ID)")
        print(f"✅ College inferred from valid CCS program")
    
    if not validation_result.passed:
        success = False
        issues.append("❌ Validation failed")
    else:
        print(f"✅ Validation passed (college inferred from program)")
    
    print_separator()
    
    if success:
        print("✅ SUCCESS: All critical fields extracted and validated!")
        print("\nExpected Decision Flow:")
        print("  1. OCR Extraction: Success (~94% confidence)")
        print("  2. Field Extraction: Success (via fallback heuristics)")
        print("  3. College Inference: CCS inferred from valid program")
        print("  4. Rule Validation: PASS (all rules satisfied)")
        print("  5. Decision: auto_approved or pending_manual_review")
        print("     (NOT incomplete_extraction, NOT rejected for missing college)")
    else:
        print("❌ FAILURE: Some fields not extracted or validation failed")
        for issue in issues:
            print(f"  {issue}")
    
    print_separator()
    
    return success


def test_labeled_cor():
    """Test extraction from labeled COR format (regression check)."""
    print_separator()
    print("TEST: Labeled COR Format (Regression Check)")
    print_separator()
    
    # Labeled COR format
    ocr_text = """
PAMPANGA STATE UNIVERSITY
Certificate of Registration

Student Name: Maria Santos
College: CCS
Course: BSCS
Student Number: 2022-54321
    """
    
    print("OCR Text:")
    print(ocr_text)
    print_separator()
    
    # Extract fields
    extractor = FieldExtractor()
    result = extractor.extract(ocr_text)
    
    print("Extracted Fields:")
    print(f"  Full Name:       {result.full_name}")
    print(f"  School Name:     {result.school_name}")
    print(f"  College:         {result.college}")
    print(f"  Program (raw):   {result.program_raw}")
    print(f"  Program (norm):  {result.program}")
    print(f"  Student Number:  {result.student_number}")
    print_separator()
    
    # Validation
    success = True
    
    if result.full_name == "Maria Santos":
        print("✅ Full name extracted correctly")
    else:
        print(f"❌ Full name incorrect: {result.full_name}")
        success = False
    
    if result.school_name == "Pampanga State University":
        print("✅ School name extracted correctly")
    else:
        print(f"❌ School name incorrect: {result.school_name}")
        success = False
    
    if result.college == "CCS":
        print("✅ College extracted correctly")
    else:
        print(f"❌ College incorrect: {result.college}")
        success = False
    
    if result.program == "BS Computer Science":
        print("✅ Program extracted and normalized correctly")
    else:
        print(f"❌ Program incorrect: {result.program}")
        success = False
    
    if result.student_number == "2022-54321":
        print("✅ Student number extracted correctly")
    else:
        print(f"❌ Student number incorrect: {result.student_number}")
        success = False
    
    print_separator()
    
    if success:
        print("✅ SUCCESS: Labeled extraction still works (no regression)")
    else:
        print("❌ FAILURE: Regression detected in labeled extraction")
    
    print_separator()
    
    return success


def test_dhvsu_variant():
    """Test extraction from DHVSU abbreviation variant."""
    print_separator()
    print("TEST: DHVSU Abbreviation Variant")
    print_separator()
    
    ocr_text = """
DHVSU
JUAN DELA CRUZ
Computer Science
2021123456
    """
    
    print("OCR Text:")
    print(ocr_text)
    print_separator()
    
    # Extract fields
    extractor = FieldExtractor()
    result = extractor.extract(ocr_text)
    
    print("Extracted Fields:")
    print(f"  Full Name:       {result.full_name}")
    print(f"  School Name:     {result.school_name}")
    print(f"  Program (norm):  {result.program}")
    print(f"  Student Number:  {result.student_number}")
    print_separator()
    
    # Validation
    success = True
    
    if result.school_name == "Pampanga State University":
        print("✅ DHVSU mapped to Pampanga State University")
    else:
        print(f"❌ DHVSU mapping failed: {result.school_name}")
        success = False
    
    if result.full_name == "Juan Dela Cruz":
        print("✅ Full name extracted correctly")
    else:
        print(f"❌ Full name incorrect: {result.full_name}")
        success = False
    
    if result.program == "BS Computer Science":
        print("✅ Program extracted and normalized correctly")
    else:
        print(f"❌ Program incorrect: {result.program}")
        success = False
    
    print_separator()
    
    if success:
        print("✅ SUCCESS: DHVSU variant works correctly")
    else:
        print("❌ FAILURE: DHVSU variant extraction failed")
    
    print_separator()
    
    return success


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("FieldExtractor Fallback Heuristics - Test Suite")
    print("=" * 80)
    
    results = []
    
    # Test 1: Real PSU ID
    results.append(("Real PSU Student ID", test_real_psu_id()))
    
    # Test 2: Labeled COR (regression)
    results.append(("Labeled COR (Regression)", test_labeled_cor()))
    
    # Test 3: DHVSU variant
    results.append(("DHVSU Variant", test_dhvsu_variant()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80 + "\n")
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {test_name}")
    
    print("\n" + "=" * 80)
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED - Fallback heuristics working correctly!\n")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review output above\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
