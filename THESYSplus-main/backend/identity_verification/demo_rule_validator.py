#!/usr/bin/env python
"""Demonstration script for RuleValidator.

Shows how the RuleValidator validates extracted fields against business rules.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from identity_verification.services.field_extractor import ExtractedFields
from identity_verification.validators.rule_validator import RuleValidator


def print_result(title: str, fields: ExtractedFields, result):
    """Print validation result in a readable format."""
    print(f"\n{'='*80}")
    print(f"TEST: {title}")
    print(f"{'='*80}")
    print(f"Full Name:    {fields.full_name}")
    print(f"School:       {fields.school_name}")
    print(f"College:      {fields.college}")
    print(f"Program:      {fields.program}")
    print(f"Student #:    {fields.student_number}")
    print(f"\nValidation Result: {'✅ PASSED' if result.passed else '❌ FAILED'}")
    
    if not result.passed:
        print(f"\nFailures ({len(result.failures)}):")
        for i, failure in enumerate(result.failures, 1):
            print(f"  {i}. Field: {failure.field}")
            print(f"     Reason: {failure.reason}")
            print(f"     Expected: {failure.expected}")
            print(f"     Actual: {failure.actual}")


def main():
    """Run demonstration of RuleValidator."""
    validator = RuleValidator()
    
    print("RuleValidator Demonstration")
    print("=" * 80)
    print("This script demonstrates the RuleValidator validating extracted fields")
    print("against institutional requirements for Pampanga State University.")
    
    # Test 1: Valid Student ID
    fields1 = ExtractedFields(
        full_name="DELA CRUZ, JUAN MIGUEL",
        school_name="Pampanga State University",
        college="College of Computing Studies",
        program="BS Information Technology",
        program_raw="BSIT",
        student_number="2021-12345",
    )
    result1 = validator.validate(fields1)
    print_result("Valid Student ID - All Fields Correct", fields1, result1)
    
    # Test 2: Valid with abbreviations
    fields2 = ExtractedFields(
        full_name="SANTOS, MARIA CLARA",
        school_name="PSU",
        college="CCS",
        program="BS Computer Science",
        program_raw="BSCS",
        student_number="2022-54321",
    )
    result2 = validator.validate(fields2)
    print_result("Valid with Abbreviations (PSU, CCS)", fields2, result2)
    
    # Test 3: Wrong Institution
    fields3 = ExtractedFields(
        full_name="REYES, PEDRO",
        school_name="University of the Philippines",
        college="College of Computing Studies",
        program="BS Information Technology",
        program_raw="BSIT",
        student_number="2020-98765",
    )
    result3 = validator.validate(fields3)
    print_result("Wrong Institution (UP)", fields3, result3)
    
    # Test 4: Wrong College
    fields4 = ExtractedFields(
        full_name="GARCIA, ANA",
        school_name="Pampanga State University",
        college="College of Engineering",
        program="BS Information Technology",
        program_raw="BSIT",
        student_number="2023-11111",
    )
    result4 = validator.validate(fields4)
    print_result("Wrong College (Engineering)", fields4, result4)
    
    # Test 5: Wrong Program
    fields5 = ExtractedFields(
        full_name="LOPEZ, CARLOS",
        school_name="Pampanga State University",
        college="CCS",
        program="BS Biology",
        program_raw="BS Biology",
        student_number="2021-22222",
    )
    result5 = validator.validate(fields5)
    print_result("Wrong Program (Biology)", fields5, result5)
    
    # Test 6: Missing Required Fields
    fields6 = ExtractedFields(
        full_name=None,
        school_name="Pampanga State University",
        college=None,
        program="BS Information Technology",
        program_raw="BSIT",
        student_number=None,
    )
    result6 = validator.validate(fields6)
    print_result("Missing Required Fields (Name, College)", fields6, result6)
    
    # Test 7: OCR Typo (Minor - Should Pass)
    fields7 = ExtractedFields(
        full_name="MENDOZA, LUIS",
        school_name="Pampanga State Unversity",  # Typo: Unversity
        college="College of Computng Studies",   # Typo: Computng
        program="BS Information System",
        program_raw="BSIS",
        student_number="2022-33333",
    )
    result7 = validator.validate(fields7)
    print_result("Minor OCR Typos (Should Pass)", fields7, result7)
    
    # Test 8: Multiple Failures
    fields8 = ExtractedFields(
        full_name=None,
        school_name="Ateneo de Manila",
        college="School of Science",
        program="BS Biology",
        program_raw="BS Biology",
        student_number=None,
    )
    result8 = validator.validate(fields8)
    print_result("Multiple Failures (All Wrong)", fields8, result8)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    results = [result1, result2, result3, result4, result5, result6, result7, result8]
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"\nExpected Results:")
    print(f"  - Tests 1, 2, 7 should PASS (valid data or minor typos)")
    print(f"  - Tests 3, 4, 5, 6, 8 should FAIL (wrong data or missing fields)")
    print(f"\nActual Results: {'✅ CORRECT' if passed == 3 and failed == 5 else '❌ UNEXPECTED'}")


if __name__ == "__main__":
    main()
