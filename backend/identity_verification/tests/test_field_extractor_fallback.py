"""Unit tests for FieldExtractor fallback heuristics.

Tests fallback extraction for unlabeled student ID formats.
"""

import pytest

from identity_verification.services.field_extractor import FieldExtractor


@pytest.fixture
def field_extractor():
    """Create a FieldExtractor instance."""
    return FieldExtractor()


class TestFallbackSchoolName:
    """Test fallback school name extraction."""
    
    def test_fallback_dhvsu_full_name(self, field_extractor):
        """Extract DHVSU and map to PSU."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS E. GONZAGA
        Information Systems
        2023313528
        """
        result = field_extractor.extract(text)
        assert result.school_name == "Pampanga State University"
    
    def test_fallback_dhvsu_abbreviation(self, field_extractor):
        """Extract DHVSU abbreviation and map to PSU."""
        text = """
        DHVSU
        JUAN DELA CRUZ
        Computer Science
        2021123456
        """
        result = field_extractor.extract(text)
        assert result.school_name == "Pampanga State University"
    
    def test_fallback_generic_state_university(self, field_extractor):
        """Extract generic state university name."""
        text = """
        MANILA STATE UNIVERSITY
        MARIA SANTOS
        Information Technology
        2022654321
        """
        result = field_extractor.extract(text)
        # Should extract but not map to PSU
        assert result.school_name == "Manila State University"


class TestFallbackProgram:
    """Test fallback program extraction."""
    
    def test_fallback_information_systems(self, field_extractor):
        """Extract 'Information Systems' without label."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS E. GONZAGA
        Information Systems
        2023313528
        """
        result = field_extractor.extract(text)
        assert result.program_raw == "Information Systems"
        assert result.program == "BS Information System"  # Normalized
    
    def test_fallback_information_technology(self, field_extractor):
        """Extract 'Information Technology' without label."""
        text = """
        PAMPANGA STATE UNIVERSITY
        JUAN DELA CRUZ
        Information Technology
        2021123456
        """
        result = field_extractor.extract(text)
        assert result.program_raw == "Information Technology"
        assert result.program == "BS Information Technology"  # Normalized
    
    def test_fallback_computer_science(self, field_extractor):
        """Extract 'Computer Science' without label."""
        text = """
        DHVSU
        MARIA SANTOS
        Computer Science
        2022654321
        """
        result = field_extractor.extract(text)
        assert result.program_raw == "Computer Science"
        assert result.program == "BS Computer Science"  # Normalized
    
    def test_fallback_computer_technology(self, field_extractor):
        """Extract 'Computer Technology' without label."""
        text = """
        PAMPANGA STATE UNIVERSITY
        PEDRO REYES
        Computer Technology
        2020987654
        """
        result = field_extractor.extract(text)
        assert result.program_raw == "Computer Technology"
        assert result.program == "Associate in Computer Technology"  # Normalized


class TestFallbackFullName:
    """Test fallback full name extraction."""
    
    def test_fallback_three_word_name(self, field_extractor):
        """Extract three-word uppercase name."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS GONZAGA
        Information Systems
        2023313528
        """
        result = field_extractor.extract(text)
        assert result.full_name == "Kurt Ross Gonzaga"
    
    def test_fallback_four_word_name_with_middle_initial(self, field_extractor):
        """Extract four-word uppercase name with middle initial."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS E. GONZAGA
        Information Systems
        2023313528
        """
        result = field_extractor.extract(text)
        assert result.full_name == "Kurt Ross E. Gonzaga"
    
    def test_fallback_two_word_name(self, field_extractor):
        """Extract two-word uppercase name."""
        text = """
        PAMPANGA STATE UNIVERSITY
        JUAN CRUZ
        Computer Science
        2021123456
        """
        result = field_extractor.extract(text)
        assert result.full_name == "Juan Cruz"
    
    def test_fallback_excludes_university_name(self, field_extractor):
        """Do not extract university name as person name."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS E. GONZAGA
        Information Systems
        """
        result = field_extractor.extract(text)
        # Should extract the person name, not the university
        assert result.full_name == "Kurt Ross E. Gonzaga"
        assert result.full_name != "Don Honorio Ventura State University"
    
    def test_fallback_excludes_program_name(self, field_extractor):
        """Do not extract program name as person name."""
        text = """
        PAMPANGA STATE UNIVERSITY
        JUAN DELA CRUZ
        INFORMATION SYSTEMS
        2021123456
        """
        result = field_extractor.extract(text)
        # Should extract the person name, not the program
        assert result.full_name == "Juan Dela Cruz"


class TestFallbackStudentNumber:
    """Test fallback student number extraction."""
    
    def test_fallback_ten_digit_number(self, field_extractor):
        """Extract 10-digit student number."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS E. GONZAGA
        Information Systems
        2023313528
        """
        result = field_extractor.extract(text)
        assert result.student_number == "2023313528"
    
    def test_fallback_nine_digit_number(self, field_extractor):
        """Extract 9-digit student number."""
        text = """
        PAMPANGA STATE UNIVERSITY
        JUAN DELA CRUZ
        Computer Science
        202112345
        """
        result = field_extractor.extract(text)
        assert result.student_number == "202112345"
    
    def test_fallback_eight_digit_number(self, field_extractor):
        """Extract 8-digit student number."""
        text = """
        DHVSU
        MARIA SANTOS
        Information Technology
        20211234
        """
        result = field_extractor.extract(text)
        assert result.student_number == "20211234"
    
    def test_fallback_excludes_phone_number(self, field_extractor):
        """Do not extract phone numbers starting with 09."""
        text = """
        PAMPANGA STATE UNIVERSITY
        JUAN DELA CRUZ
        Computer Science
        09171234567
        2021123456
        """
        result = field_extractor.extract(text)
        # Should extract student number, not phone number
        assert result.student_number == "2021123456"


class TestFallbackIntegration:
    """Test full fallback extraction from realistic unlabeled student IDs."""
    
    def test_real_psu_student_id_format(self, field_extractor):
        """Extract all fields from real PSU student ID format (unlabeled)."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        KURT ROSS E. GONZAGA
        Information Systems
        2023313528
        """
        
        result = field_extractor.extract(text)
        
        # All fields should be extracted via fallback
        assert result.school_name == "Pampanga State University"
        assert result.full_name == "Kurt Ross E. Gonzaga"
        assert result.program_raw == "Information Systems"
        assert result.program == "BS Information System"  # Normalized
        assert result.student_number == "2023313528"
        # College may be None (not on student ID)
    
    def test_dhvsu_student_id_variant(self, field_extractor):
        """Extract from DHVSU student ID variant."""
        text = """
        DHVSU
        JUAN DELA CRUZ
        Computer Science
        2021123456
        """
        
        result = field_extractor.extract(text)
        
        assert result.school_name == "Pampanga State University"
        assert result.full_name == "Juan Dela Cruz"
        assert result.program_raw == "Computer Science"
        assert result.program == "BS Computer Science"
        assert result.student_number == "2021123456"
    
    def test_mixed_labeled_and_unlabeled(self, field_extractor):
        """Extract from mixed labeled and unlabeled format."""
        text = """
        DON HONORIO VENTURA STATE UNIVERSITY
        Name: Maria Santos
        Information Technology
        2022654321
        """
        
        result = field_extractor.extract(text)
        
        # Labeled extraction takes precedence
        assert result.full_name == "Maria Santos"
        # Fallback fills in the rest
        assert result.school_name == "Pampanga State University"
        assert result.program_raw == "Information Technology"
        assert result.program == "BS Information Technology"
        assert result.student_number == "2022654321"
    
    def test_fallback_preserves_labeled_extraction(self, field_extractor):
        """Verify fallback doesn't override labeled extraction."""
        text = """
        School: Pampanga State University
        Name: Pedro Reyes
        Program: BSIT
        Student No: 2020-98765
        """
        
        result = field_extractor.extract(text)
        
        # All should come from labeled extraction (no fallback needed)
        assert result.school_name == "Pampanga State University"
        assert result.full_name == "Pedro Reyes"
        assert result.program_raw == "BSIT"
        assert result.program == "BS Information Technology"
        assert result.student_number == "2020-98765"
