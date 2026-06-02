"""Unit tests for RuleValidator.

Tests rule-based validation logic for identity verification.
Per Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8.
"""

import pytest

from identity_verification.services.field_extractor import ExtractedFields
from identity_verification.validators.rule_validator import RuleValidator, RuleFailure, RuleResult


@pytest.fixture
def rule_validator():
    """Create a RuleValidator instance."""
    return RuleValidator()


class TestRuleValidatorValidCases:
    """Test cases that should pass validation."""
    
    def test_valid_student_id_all_fields(self, rule_validator):
        """Valid Student ID with all fields present."""
        fields = ExtractedFields(
            full_name="DELA CRUZ, JUAN MIGUEL",
            school_name="Pampanga State University",
            college="College of Computing Studies",
            program="BS Information Technology",
            program_raw="BS Information Technology",
            student_number="2021-12345",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
        assert len(result.failures) == 0
    
    def test_valid_cor_with_ccs_abbreviation(self, rule_validator):
        """Valid COR with CCS abbreviation."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA CLARA",
            school_name="Pampanga State University",
            college="CCS",
            program="BS Computer Science",
            program_raw="BSCS",
            student_number="2022-54321",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
        assert len(result.failures) == 0
    
    def test_valid_with_psu_abbreviation(self, rule_validator):
        """Valid with PSU abbreviation."""
        fields = ExtractedFields(
            full_name="REYES, PEDRO",
            school_name="PSU",
            college="CCS",
            program="BS Information System",
            program_raw="BSIS",
            student_number="2020-98765",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
        assert len(result.failures) == 0
    
    def test_valid_act_program(self, rule_validator):
        """Valid with Associate in Computer Technology program."""
        fields = ExtractedFields(
            full_name="GARCIA, ANA",
            school_name="Pampanga State University",
            college="College of Computing Studies",
            program="Associate in Computer Technology",
            program_raw="ACT",
            student_number="2023-11111",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
        assert len(result.failures) == 0
    
    def test_valid_without_student_number(self, rule_validator):
        """Valid even without student number (optional field)."""
        fields = ExtractedFields(
            full_name="LOPEZ, CARLOS",
            school_name="Pampanga State University",
            college="CCS",
            program="BS Information Technology",
            program_raw="BSIT",
            student_number=None,
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
        assert len(result.failures) == 0


class TestRuleValidatorInvalidInstitution:
    """Test cases with wrong institution."""
    
    def test_wrong_institution(self, rule_validator):
        """Wrong institution should fail."""
        fields = ExtractedFields(
            full_name="DELA CRUZ, JUAN",
            school_name="University of the Philippines",
            college="College of Computing Studies",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 1
        assert result.failures[0].field == 'school_name'
        assert result.failures[0].reason == 'Institution not allowed'
        assert result.failures[0].actual == "University of the Philippines"
    
    def test_completely_different_institution(self, rule_validator):
        """Completely different institution should fail."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Ateneo de Manila University",
            college="CCS",
            program="BS Computer Science",
            program_raw="BSCS",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'school_name' for f in result.failures)


class TestRuleValidatorInvalidCollege:
    """Test cases with wrong college."""
    
    def test_wrong_college(self, rule_validator):
        """Wrong college should fail."""
        fields = ExtractedFields(
            full_name="REYES, PEDRO",
            school_name="Pampanga State University",
            college="College of Engineering",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 1
        assert result.failures[0].field == 'college'
        assert result.failures[0].reason == 'College not allowed'
        assert result.failures[0].actual == "College of Engineering"
    
    def test_college_of_business(self, rule_validator):
        """College of Business should fail."""
        fields = ExtractedFields(
            full_name="GARCIA, ANA",
            school_name="Pampanga State University",
            college="College of Business Administration",
            program="BS Information System",
            program_raw="BSIS",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'college' for f in result.failures)


class TestRuleValidatorInvalidProgram:
    """Test cases with wrong program."""
    
    def test_wrong_program(self, rule_validator):
        """Wrong program should fail."""
        fields = ExtractedFields(
            full_name="LOPEZ, CARLOS",
            school_name="Pampanga State University",
            college="CCS",
            program="BS Biology",
            program_raw="BS Biology",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 1
        assert result.failures[0].field == 'program'
        assert result.failures[0].reason == 'Program not allowed'
        assert result.failures[0].actual == "BS Biology"
    
    def test_engineering_program(self, rule_validator):
        """Engineering program should fail."""
        fields = ExtractedFields(
            full_name="MENDOZA, LUIS",
            school_name="Pampanga State University",
            college="CCS",
            program="BS Computer Engineering",
            program_raw="BS Computer Engineering",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'program' for f in result.failures)
    
    def test_non_normalized_program_fails(self, rule_validator):
        """Non-normalized program (should have been normalized) fails."""
        fields = ExtractedFields(
            full_name="TORRES, ROSA",
            school_name="Pampanga State University",
            college="CCS",
            program="BSIT",  # Should have been normalized to "BS Information Technology"
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'program' for f in result.failures)


class TestRuleValidatorMissingFields:
    """Test cases with missing required fields."""
    
    def test_missing_full_name(self, rule_validator):
        """Missing full name should fail."""
        fields = ExtractedFields(
            full_name=None,
            school_name="Pampanga State University",
            college="CCS",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'full_name' and f.reason == 'Required field is missing' for f in result.failures)
    
    def test_missing_school_name(self, rule_validator):
        """Missing school name should fail."""
        fields = ExtractedFields(
            full_name="DELA CRUZ, JUAN",
            school_name=None,
            college="CCS",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'school_name' and f.reason == 'Required field is missing' for f in result.failures)
    
    def test_missing_college_with_valid_program(self, rule_validator):
        """Missing college with valid CCS program should pass (college inferred)."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Pampanga State University",
            college=None,
            program="BS Computer Science",
            program_raw="BSCS",
        )
        
        result = rule_validator.validate(fields)
        
        # Should pass because college can be inferred from valid CCS program
        assert result.passed
        assert len(result.failures) == 0
    
    def test_missing_college_with_invalid_program(self, rule_validator):
        """Missing college with invalid program should fail."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Pampanga State University",
            college=None,
            program="BS Nursing",  # Not a CCS program
            program_raw="BS Nursing",
        )
        
        result = rule_validator.validate(fields)
        
        # Should fail because program is invalid (cannot infer college)
        assert not result.passed
        assert any(f.field == 'program' and f.reason == 'Program not allowed' for f in result.failures)
    
    def test_missing_college_and_program(self, rule_validator):
        """Missing both college and program should fail."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Pampanga State University",
            college=None,
            program=None,
            program_raw=None,
        )
        
        result = rule_validator.validate(fields)
        
        # Should fail because both college and program are missing
        assert not result.passed
        assert any(f.field == 'college' and f.reason == 'Required field is missing' for f in result.failures)
        assert any(f.field == 'program' and f.reason == 'Required field is missing' for f in result.failures)
    
    def test_missing_program(self, rule_validator):
        """Missing program should fail."""
        fields = ExtractedFields(
            full_name="REYES, PEDRO",
            school_name="Pampanga State University",
            college="CCS",
            program=None,
            program_raw=None,
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert any(f.field == 'program' and f.reason == 'Required field is missing' for f in result.failures)
    
    def test_all_fields_missing(self, rule_validator):
        """All fields missing should fail with multiple failures."""
        fields = ExtractedFields(
            full_name=None,
            school_name=None,
            college=None,
            program=None,
            program_raw=None,
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 4  # All 4 required fields
        assert any(f.field == 'full_name' for f in result.failures)
        assert any(f.field == 'school_name' for f in result.failures)
        assert any(f.field == 'college' for f in result.failures)
        assert any(f.field == 'program' for f in result.failures)


class TestRuleValidatorOCRTypos:
    """Test cases with OCR typos (conservative validation)."""
    
    def test_institution_typo_pampanga_state(self, rule_validator):
        """Minor typo in institution name (contains 'pampanga' and 'state')."""
        fields = ExtractedFields(
            full_name="GARCIA, ANA",
            school_name="Pampanga State Unversity",  # Typo: Unversity
            college="CCS",
            program="BS Information System",
            program_raw="BSIS",
        )
        
        result = rule_validator.validate(fields)
        
        # Should pass - contains key words "pampanga" and "state"
        assert result.passed
        assert len(result.failures) == 0
    
    def test_college_typo_computing_studies(self, rule_validator):
        """Minor typo in college name (contains 'computing' and 'studies')."""
        fields = ExtractedFields(
            full_name="LOPEZ, CARLOS",
            school_name="Pampanga State University",
            college="College of Computng Studies",  # Typo: Computng
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        # Should pass - contains key words "computing" and "studies"
        assert result.passed
        assert len(result.failures) == 0
    
    def test_institution_major_typo_fails(self, rule_validator):
        """Major typo in institution name should fail."""
        fields = ExtractedFields(
            full_name="MENDOZA, LUIS",
            school_name="Pampanga St te",  # Major typo
            college="CCS",
            program="BS Computer Science",
            program_raw="BSCS",
        )
        
        result = rule_validator.validate(fields)
        
        # Should fail - missing "state" keyword
        assert not result.passed
        assert any(f.field == 'school_name' for f in result.failures)
    
    def test_college_major_typo_fails(self, rule_validator):
        """Major typo in college name should fail."""
        fields = ExtractedFields(
            full_name="TORRES, ROSA",
            school_name="Pampanga State University",
            college="CC",  # Major typo - missing key words
            program="BS Information System",
            program_raw="BSIS",
        )
        
        result = rule_validator.validate(fields)
        
        # Should fail - missing "computing" and "studies" keywords
        assert not result.passed
        assert any(f.field == 'college' for f in result.failures)


class TestRuleValidatorMultipleFailures:
    """Test cases with multiple validation failures."""
    
    def test_wrong_institution_and_college(self, rule_validator):
        """Wrong institution and college should report both failures."""
        fields = ExtractedFields(
            full_name="DELA CRUZ, JUAN",
            school_name="University of the Philippines",
            college="College of Engineering",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 2
        assert any(f.field == 'school_name' for f in result.failures)
        assert any(f.field == 'college' for f in result.failures)
    
    def test_wrong_institution_college_program(self, rule_validator):
        """Wrong institution, college, and program should report all failures."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Ateneo de Manila",
            college="School of Science and Engineering",
            program="BS Biology",
            program_raw="BS Biology",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 3
        assert any(f.field == 'school_name' for f in result.failures)
        assert any(f.field == 'college' for f in result.failures)
        assert any(f.field == 'program' for f in result.failures)
    
    def test_missing_and_wrong_fields(self, rule_validator):
        """Missing fields and wrong values should report all failures."""
        fields = ExtractedFields(
            full_name=None,
            school_name="University of the Philippines",
            college=None,
            program="BS Biology",
            program_raw="BS Biology",
        )
        
        result = rule_validator.validate(fields)
        
        assert not result.passed
        assert len(result.failures) == 4
        assert any(f.field == 'full_name' and f.reason == 'Required field is missing' for f in result.failures)
        assert any(f.field == 'school_name' and f.reason == 'Institution not allowed' for f in result.failures)
        assert any(f.field == 'college' and f.reason == 'Required field is missing' for f in result.failures)
        assert any(f.field == 'program' and f.reason == 'Program not allowed' for f in result.failures)


class TestRuleValidatorCaseInsensitivity:
    """Test case-insensitive validation."""
    
    def test_uppercase_institution(self, rule_validator):
        """Uppercase institution should pass."""
        fields = ExtractedFields(
            full_name="GARCIA, ANA",
            school_name="PAMPANGA STATE UNIVERSITY",
            college="COLLEGE OF COMPUTING STUDIES",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
    
    def test_lowercase_institution(self, rule_validator):
        """Lowercase institution should pass."""
        fields = ExtractedFields(
            full_name="LOPEZ, CARLOS",
            school_name="pampanga state university",
            college="college of computing studies",
            program="BS Computer Science",
            program_raw="BSCS",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed
    
    def test_mixed_case_abbreviations(self, rule_validator):
        """Mixed case abbreviations should pass."""
        fields = ExtractedFields(
            full_name="MENDOZA, LUIS",
            school_name="psu",
            college="ccs",
            program="BS Information System",
            program_raw="BSIS",
        )
        
        result = rule_validator.validate(fields)
        
        assert result.passed


class TestRuleValidatorOCRMangledDHVSU:
    """Regression tests: OCR-mangled DHVSU/PSU names must not be rejected.

    These cases represent real Tesseract OCR errors observed on physical
    DHVSU student IDs (Don Honorio Ventura State University).
    See: GitHub issue — "Don Honorio Ventur Hs Tate University" rejected.
    """

    def test_ocr_mangled_dhvsu_typical(self, rule_validator):
        """Reported bug case: 'Don Honorio Ventur Hs Tate University'."""
        fields = ExtractedFields(
            full_name="DELA CRUZ, JUAN",
            school_name="Don Honorio Ventur Hs Tate University",
            college=None,
            program="BS Information Technology",
            program_raw="BSIT",
        )
        result = rule_validator.validate(fields)
        assert result.passed, (
            f"Expected PASS for OCR-mangled DHVSU name but got FAIL: "
            f"{[f.actual for f in result.failures]}"
        )

    def test_ocr_mangled_dhvsu_missing_letters(self, rule_validator):
        """'Don Honorio Ventura Stat University' — 'e' dropped from State."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Don Honorio Ventura Stat University",
            college=None,
            program="BS Computer Science",
            program_raw="BSCS",
        )
        result = rule_validator.validate(fields)
        assert result.passed, (
            f"Expected PASS but got: {[f.actual for f in result.failures]}"
        )

    def test_ocr_mangled_don_honorio_only(self, rule_validator):
        """Only 'Don Honorio' extracted — still identifiable as DHVSU."""
        fields = ExtractedFields(
            full_name="REYES, PEDRO",
            school_name="Don Honorio University",
            college=None,
            program="BS Information System",
            program_raw="BSIS",
        )
        result = rule_validator.validate(fields)
        assert result.passed, (
            f"Expected PASS but got: {[f.actual for f in result.failures]}"
        )

    def test_ocr_honorio_ventura_keywords(self, rule_validator):
        """'Honorio Ventura State Univ' — missing Don, has 2 distinctive kws."""
        fields = ExtractedFields(
            full_name="GARCIA, ANA",
            school_name="Honorio Ventura State Univ",
            college=None,
            program="BS Computer Science",
            program_raw="BSCS",
        )
        result = rule_validator.validate(fields)
        assert result.passed, (
            f"Expected PASS but got: {[f.actual for f in result.failures]}"
        )

    def test_dhvsu_abbreviation_exact(self, rule_validator):
        """Exact 'DHVSU' abbreviation must always pass."""
        fields = ExtractedFields(
            full_name="LOPEZ, CARLOS",
            school_name="DHVSU",
            college="CCS",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        result = rule_validator.validate(fields)
        assert result.passed

    def test_dhvsu_abbreviation_lowercase(self, rule_validator):
        """'dhvsu' (lowercase) must pass."""
        fields = ExtractedFields(
            full_name="MENDOZA, LUIS",
            school_name="dhvsu",
            college="CCS",
            program="BS Computer Science",
            program_raw="BSCS",
        )
        result = rule_validator.validate(fields)
        assert result.passed

    def test_completely_unrelated_school_still_rejected(self, rule_validator):
        """Unrelated school must still be rejected after fuzzy fix."""
        fields = ExtractedFields(
            full_name="DELA CRUZ, JUAN",
            school_name="Holy Angel University",
            college="CCS",
            program="BS Information Technology",
            program_raw="BSIT",
        )
        result = rule_validator.validate(fields)
        assert not result.passed
        assert any(f.field == 'school_name' for f in result.failures)

    def test_ateneo_still_rejected(self, rule_validator):
        """Ateneo must still be rejected."""
        fields = ExtractedFields(
            full_name="SANTOS, MARIA",
            school_name="Ateneo de Manila University",
            college="CCS",
            program="BS Computer Science",
            program_raw="BSCS",
        )
        result = rule_validator.validate(fields)
        assert not result.passed

    def test_up_diliman_still_rejected(self, rule_validator):
        """University of the Philippines Diliman must still be rejected."""
        fields = ExtractedFields(
            full_name="REYES, PEDRO",
            school_name="University of the Philippines Diliman",
            college="CCS",
            program="BS Computer Science",
            program_raw="BSCS",
        )
        result = rule_validator.validate(fields)
        assert not result.passed


class TestFieldExtractorOCRMangledDHVSU:
    """Regression tests: FieldExtractor must extract school_name from OCR-
    mangled DHVSU text so that the rule validator receives a value to fuzzy-
    match against (rather than None → missing_required_information).
    """

    def test_typical_ocr_mangled_dhvsu_line(self):
        """'Don Honorio Ventur Hs Tate University' → school_name = PSU."""
        from identity_verification.services.field_extractor import FieldExtractor
        fe = FieldExtractor()
        text = (
            "Don Honorio Ventur Hs Tate University\n"
            "DELA CRUZ JUAN MIGUEL\n"
            "Information Technology\n"
            "2021123456\n"
        )
        result = fe.extract(text)
        assert result.school_name == "Pampanga State University", (
            f"school_name was {result.school_name!r}, expected 'Pampanga State University'"
        )

    def test_ventura_state_ocr_split(self):
        """'Don Honorio Ventura' on one line, 'Hs Tate University' on next."""
        from identity_verification.services.field_extractor import FieldExtractor
        fe = FieldExtractor()
        text = (
            "Don Honorio Ventura\n"
            "Hs Tate University\n"
            "SANTOS MARIA CLARA\n"
            "Computer Science\n"
            "2022654321\n"
        )
        result = fe.extract(text)
        assert result.school_name == "Pampanga State University", (
            f"school_name was {result.school_name!r}"
        )
