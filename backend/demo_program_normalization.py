#!/usr/bin/env python
"""Demonstration script for ProgramNormalizer integration with FieldExtractor.

This script demonstrates how the FieldExtractor automatically normalizes
program names using the ProgramNormalizer.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings')
django.setup()

from identity_verification.services.field_extractor import FieldExtractor


def demo_program_normalization():
    """Demonstrate program normalization in action."""
    
    print("=" * 80)
    print("ProgramNormalizer Integration Demo")
    print("=" * 80)
    print()
    
    # Initialize the field extractor (which includes the program normalizer)
    extractor = FieldExtractor()
    
    # Test cases with different program name variations
    test_cases = [
        {
            "name": "BSIS Abbreviation",
            "ocr_text": """
                Name: Juan Dela Cruz
                School: Pampanga State University
                College: CCS
                Program: BSIS
                Student No: 2021-12345
            """
        },
        {
            "name": "BS-IT with Hyphen",
            "ocr_text": """
                Name: Maria Santos
                School: Pampanga State University
                College: College of Computing Studies
                Course: BS-IT
                ID: 2022-54321
            """
        },
        {
            "name": "Full Program Name",
            "ocr_text": """
                Name: Pedro Reyes
                School: Pampanga State University
                College: CCS
                Program: Bachelor of Science in Computer Science
                Student Number: 2020-98765
            """
        },
        {
            "name": "ACT Abbreviation",
            "ocr_text": """
                Name: Ana Garcia
                School: Pampanga State University
                College: College of Computing Studies
                Program: ACT
                ID: 2023-11111
            """
        },
        {
            "name": "BS Information Systems (Plural)",
            "ocr_text": """
                Name: Carlos Mendoza
                School: Pampanga State University
                College: CCS
                Course: BS Information Systems
                Student No: 2021-22222
            """
        },
    ]
    
    # Process each test case
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test Case {i}: {test_case['name']}")
        print("-" * 80)
        
        # Extract fields (including program normalization)
        result = extractor.extract(test_case['ocr_text'])
        
        print(f"Full Name:       {result.full_name}")
        print(f"School:          {result.school_name}")
        print(f"College:         {result.college}")
        print(f"Program (Raw):   {result.program_raw}")
        print(f"Program (Norm):  {result.program}")
        print(f"Student Number:  {result.student_number}")
        
        # Highlight normalization
        if result.program_raw != result.program:
            print()
            print(f"✅ NORMALIZED: '{result.program_raw}' → '{result.program}'")
        else:
            print()
            print(f"✅ CANONICAL: '{result.program}' (already in canonical form)")
        
        print()
        print()
    
    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print()
    print("Summary:")
    print("- The FieldExtractor automatically normalizes program names")
    print("- Both raw and normalized values are stored")
    print("- All program aliases are mapped to canonical forms")
    print("- Unknown programs are preserved without normalization")


if __name__ == '__main__':
    demo_program_normalization()
