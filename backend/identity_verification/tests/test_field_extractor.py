"""Unit tests for FieldExtractor.

Tests field extraction from OCR text using regex patterns.
Per Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7.
"""

import pytest

from identity_verification.services.field_extractor import FieldExtractor, ExtractedFields


@pytest.fixture
def field_extractor():
    """Create a FieldExtractor instance."""
    return FieldExtractor()


class TestFieldExtractorFullName:
    """Test full name extraction."""
    
    def test_extract_full_name_with_colon(self, field_extractor):
        """Extract full name with 'Name:' pattern."""
        text = "Name: Juan Dela Cruz\nStudent Number: 2021-12345"
        result = field_extractor.extract(text)
        assert result.full_name == "Juan Dela Cruz"
    
    def test_extract_full_name_with_student_prefix(self, field_extractor):
        """Extract full name with 'Student Name:' pattern."""
        text = "Student Name: Maria Santos\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.full_name == "Maria Santos"
    
    def test_extract_full_name_with_full_prefix(self, field_extractor):
        """Extract full name with 'Full Name:' pattern."""
        text = "Full Name: Pedro Reyes\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.full_name == "Pedro Reyes"
    
    def test_extract_full_name_with_comma(self, field_extractor):
        """Extract full name with comma (Last, First format)."""
        text = "Name: Dela Cruz, Juan\nID: 123456"
        result = field_extractor.extract(text)
        assert result.full_name == "Dela Cruz, Juan"
    
    def test_extract_full_name_with_middle_initial(self, field_extractor):
        """Extract full name with middle initial."""
        text = "Name: Juan D. Cruz\nProgram: BSCS"
        result = field_extractor.extract(text)
        assert result.full_name == "Juan D. Cruz"
    
    def test_extract_full_name_missing(self, field_extractor):
        """Handle missing full name."""
        text = "Program: BSIT\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.full_name is None


class TestFieldExtractorSchoolName:
    """Test school name extraction."""
    
    def test_extract_school_name_title_case(self, field_extractor):
        """Extract school name in title case."""
        text = "Pampanga State University\nCollege of Computing Studies"
        result = field_extractor.extract(text)
        assert result.school_name == "Pampanga State University"
    
    def test_extract_school_name_uppercase(self, field_extractor):
        """Extract school name in uppercase."""
        text = "PAMPANGA STATE UNIVERSITY\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.school_name == "Pampanga State University"
    
    def test_extract_school_name_with_label(self, field_extractor):
        """Extract school name with 'School:' label."""
        text = "School: Pampanga State University\nName: Juan Cruz"
        result = field_extractor.extract(text)
        assert result.school_name == "Pampanga State University"
    
    def test_extract_school_name_missing(self, field_extractor):
        """Handle missing school name."""
        text = "Name: Juan Cruz\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.school_name is None


class TestFieldExtractorCollege:
    """Test college extraction."""
    
    def test_extract_college_full_name(self, field_extractor):
        """Extract college with full name."""
        text = "College of Computing Studies\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.college == "College of Computing Studies"
    
    def test_extract_college_abbreviation(self, field_extractor):
        """Extract college abbreviation 'CCS'."""
        text = "College: CCS\nProgram: BSCS"
        result = field_extractor.extract(text)
        assert result.college == "CCS"
    
    def test_extract_college_standalone_ccs(self, field_extractor):
        """Extract standalone 'CCS' abbreviation."""
        text = "Name: Juan Cruz\nCCS\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.college == "CCS"
    
    def test_extract_college_with_label(self, field_extractor):
        """Extract college with 'College:' label."""
        text = "College: College of Computing Studies\nName: Juan"
        result = field_extractor.extract(text)
        assert result.college == "College of Computing Studies"
    
    def test_extract_college_missing(self, field_extractor):
        """Handle missing college."""
        text = "Name: Juan Cruz\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.college is None


class TestFieldExtractorProgram:
    """Test program extraction."""
    
    def test_extract_program_bsis_full(self, field_extractor):
        """Extract 'BS Information System' full name."""
        text = "Program: BS Information System\nName: Juan"
        result = field_extractor.extract(text)
        assert result.program_raw == "BS Information System"
        assert result.program == "BS Information System"  # Normalized
    
    def test_extract_program_bsit_full(self, field_extractor):
        """Extract 'BS Information Technology' full name."""
        text = "Course: BS Information Technology\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.program_raw == "BS Information Technology"
        assert result.program == "BS Information Technology"
    
    def test_extract_program_bscs_full(self, field_extractor):
        """Extract 'BS Computer Science' full name."""
        text = "Program: BS Computer Science\nName: Juan"
        result = field_extractor.extract(text)
        assert result.program_raw == "BS Computer Science"
        assert result.program == "BS Computer Science"
    
    def test_extract_program_act_full(self, field_extractor):
        """Extract 'Associate in Computer Technology' full name."""
        text = "Program: Associate in Computer Technology\nName: Juan"
        result = field_extractor.extract(text)
        assert result.program_raw == "Associate in Computer Technology"
        assert result.program == "Associate in Computer Technology"
    
    def test_extract_program_bsis_abbreviation(self, field_extractor):
        """Extract 'BSIS' abbreviation and normalize."""
        text = "Course: BSIS\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.program_raw == "BSIS"
        assert result.program == "BS Information System"  # Normalized
    
    def test_extract_program_bsit_abbreviation(self, field_extractor):
        """Extract 'BSIT' abbreviation and normalize."""
        text = "Program: BSIT\nName: Juan"
        result = field_extractor.extract(text)
        assert result.program_raw == "BSIT"
        assert result.program == "BS Information Technology"  # Normalized
    
    def test_extract_program_bscs_abbreviation(self, field_extractor):
        """Extract 'BSCS' abbreviation and normalize."""
        text = "Course: BSCS\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.program_raw == "BSCS"
        assert result.program == "BS Computer Science"  # Normalized
    
    def test_extract_program_act_abbreviation(self, field_extractor):
        """Extract 'ACT' abbreviation and normalize."""
        text = "Program: ACT\nName: Juan"
        result = field_extractor.extract(text)
        assert result.program_raw == "ACT"
        assert result.program == "Associate in Computer Technology"  # Normalized
    
    def test_extract_program_with_hyphen(self, field_extractor):
        """Extract program with hyphen format."""
        text = "Course: BS-IT\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.program_raw == "BS-IT"
        assert result.program == "BS Information Technology"  # Normalized
    
    def test_extract_program_missing(self, field_extractor):
        """Handle missing program."""
        text = "Name: Juan Cruz\nCollege: CCS"
        result = field_extractor.extract(text)
        assert result.program_raw is None
        assert result.program is None


class TestFieldExtractorStudentNumber:
    """Test student number extraction."""
    
    def test_extract_student_number_with_hyphen(self, field_extractor):
        """Extract student number with hyphen format."""
        text = "Student No: 2021-12345\nName: Juan"
        result = field_extractor.extract(text)
        assert result.student_number == "2021-12345"  # Preserves hyphen format
    
    def test_extract_student_number_no_hyphen(self, field_extractor):
        """Extract student number without hyphen."""
        text = "ID: 202112345\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.student_number == "202112345"
    
    def test_extract_student_number_with_space(self, field_extractor):
        """Extract student number with space."""
        text = "Student Number: 2021 12345\nName: Juan"
        result = field_extractor.extract(text)
        assert result.student_number == "202112345"  # Normalized (spaces removed)
    
    def test_extract_student_number_missing(self, field_extractor):
        """Handle missing student number."""
        text = "Name: Juan Cruz\nProgram: BSIT"
        result = field_extractor.extract(text)
        assert result.student_number is None


class TestFieldExtractorIntegration:
    """Test full field extraction from realistic OCR text."""
    
    def test_extract_all_fields_student_id(self, field_extractor):
        """Extract all fields from realistic Student ID OCR text."""
        text = """
        Pampanga State University
        College of Computing Studies
        
        Student ID Card
        
        Name: Juan Dela Cruz
        Student No: 2021-12345
        Program: BS Information Technology
        """
        
        result = field_extractor.extract(text)
        
        assert result.full_name == "Juan Dela Cruz"
        assert result.school_name == "Pampanga State University"
        assert result.college == "College of Computing Studies"
        assert result.program_raw == "BS Information Technology"
        assert result.program == "BS Information Technology"
        assert result.student_number == "2021-12345"
    
    def test_extract_all_fields_cor(self, field_extractor):
        """Extract all fields from realistic COR OCR text."""
        text = """
        PAMPANGA STATE UNIVERSITY
        Certificate of Registration
        
        Student Name: Maria Santos
        College: CCS
        Course: BSCS
        Student Number: 2022-54321
        """
        
        result = field_extractor.extract(text)
        
        assert result.full_name == "Maria Santos"
        assert result.school_name == "Pampanga State University"
        assert result.college == "CCS"
        assert result.program_raw == "BSCS"
        assert result.program == "BS Computer Science"  # Normalized
        assert result.student_number == "2022-54321"
    
    def test_extract_partial_fields(self, field_extractor):
        """Extract partial fields when some are missing."""
        text = """
        Pampanga State University
        Name: Pedro Reyes
        Program: BSIS
        """
        
        result = field_extractor.extract(text)
        
        assert result.full_name == "Pedro Reyes"
        assert result.school_name == "Pampanga State University"
        assert result.college is None  # Missing
        assert result.program_raw == "BSIS"
        assert result.program == "BS Information System"  # Normalized
        assert result.student_number is None  # Missing
    
    def test_extract_empty_text(self, field_extractor):
        """Handle empty OCR text."""
        result = field_extractor.extract("")
        
        assert result.full_name is None
        assert result.school_name is None
        assert result.college is None
        assert result.program_raw is None
        assert result.program is None
        assert result.student_number is None
