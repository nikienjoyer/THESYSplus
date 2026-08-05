#!/usr/bin/env python
"""Simple demonstration of RuleValidator functionality."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from identity_verification.services.field_extractor import ExtractedFields
from identity_verification.validators.rule_validator import RuleValidator


def main():
    validator = RuleValidator()
    
    print("="*80)
    print("RuleValidator Demonstration")
    print("="*80)
    
    # Test 1: Valid Student ID
    print("\n1. Valid Student ID - All Fields Correct")
    print("-" * 80)
    fields1 = ExtractedFields(
        full_name="DELA CRUZ, JUAN MIGUEL",
        school_name="Pampanga State University",
        college="College of Computing Studies",
        program="BS Information Technology",
        program_raw="BSIT",
        student_number="2021-12345",
    )
    result1 = validator.validate(fields1)
    print(f"School: {fields1.school_name}")
    print(f"College: {fields1.college}")
    print(f"Program: {fields1.program}")
    print(f"Result: {'✅ PASSED' if result1.passed else '❌ FAILED'}")
    
    # Test 2: Wrong Institution
    print("\n2. Wrong Institution (University of the Philippines)")
    print("-" * 80)
    fields2 = ExtractedFields(
        full_name="REYES, PEDRO",
        school_name="University of the Philippines",
        college="College of Computing Studies",
        program="BS Information Technology",
        program_raw="BSIT",
    )
    result2 = validator.validate(fields2)
    print(f"School: {fields2.school_name}")
    print(f"College: {fields2.college}")
    print(f"Program: {fields2.program}")
    print(f"Result: {'✅ PASSED' if result2.passed else '❌ FAILED'}")
    if result2.failures:
        print(f"Failures:")
        for f in result2.failures:
            print(f"  - {f.field}: {f.reason} (got: {f.actual})")
    
    # Test 3: Wrong College
    print("\n3. Wrong College (Engineering)")
    print("-" * 80)
    fields3 = ExtractedFields(
        full_name="GARCIA, ANA",
        school_name="Pampanga State University",
        college="College of Engineering",
        program="BS Information Technology",
        program_raw="BSIT",
    )
    result3 = validator.validate(fields3)
    print(f"School: {fields3.school_name}")
    print(f"College: {fields3.college}")
    print(f"Program: {fields3.program}")
    print(f"Result: {'✅ PASSED' if result3.passed else '❌ FAILED'}")
    if result3.failures:
        print(f"Failures:")
        for f in result3.failures:
            print(f"  - {f.field}: {f.reason} (got: {f.actual})")
    
    # Test 4: Wrong Program
    print("\n4. Wrong Program (Biology)")
    print("-" * 80)
    fields4 = ExtractedFields(
        full_name="LOPEZ, CARLOS",
        school_name="Pampanga State University",
        college="CCS",
        program="BS Biology",
        program_raw="BS Biology",
    )
    result4 = validator.validate(fields4)
    print(f"School: {fields4.school_name}")
    print(f"College: {fields4.college}")
    print(f"Program: {fields4.program}")
    print(f"Result: {'✅ PASSED' if result4.passed else '❌ FAILED'}")
    if result4.failures:
        print(f"Failures:")
        for f in result4.failures:
            print(f"  - {f.field}: {f.reason} (got: {f.actual})")
    
    # Test 5: Missing Required Fields
    print("\n5. Missing Required Fields (Name and College)")
    print("-" * 80)
    fields5 = ExtractedFields(
        full_name=None,
        school_name="Pampanga State University",
        college=None,
        program="BS Information Technology",
        program_raw="BSIT",
    )
    result5 = validator.validate(fields5)
    print(f"Full Name: {fields5.full_name}")
    print(f"School: {fields5.school_name}")
    print(f"College: {fields5.college}")
    print(f"Program: {fields5.program}")
    print(f"Result: {'✅ PASSED' if result5.passed else '❌ FAILED'}")
    if result5.failures:
        print(f"Failures:")
        for f in result5.failures:
            print(f"  - {f.field}: {f.reason}")
    
    # Test 6: Valid with Abbreviations
    print("\n6. Valid with Abbreviations (PSU, CCS)")
    print("-" * 80)
    fields6 = ExtractedFields(
        full_name="SANTOS, MARIA",
        school_name="PSU",
        college="CCS",
        program="BS Computer Science",
        program_raw="BSCS",
    )
    result6 = validator.validate(fields6)
    print(f"School: {fields6.school_name}")
    print(f"College: {fields6.college}")
    print(f"Program: {fields6.program}")
    print(f"Result: {'✅ PASSED' if result6.passed else '❌ FAILED'}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    results = [result1, result2, result3, result4, result5, result6]
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"\nExpected: 2 passed (tests 1, 6), 4 failed (tests 2, 3, 4, 5)")
    print(f"Actual: {passed} passed, {failed} failed")
    print(f"Status: {'✅ CORRECT' if passed == 2 and failed == 4 else '❌ UNEXPECTED'}")


if __name__ == "__main__":
    main()
