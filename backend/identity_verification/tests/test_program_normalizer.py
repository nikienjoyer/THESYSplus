"""Unit tests for ProgramNormalizer.

Tests program name normalization to canonical forms.
Per Requirements 5.1, 5.2, 5.3, 5.4, 5.6.
"""

import pytest

from identity_verification.normalizers import ProgramNormalizer


@pytest.fixture
def normalizer():
    """Create a ProgramNormalizer instance."""
    return ProgramNormalizer()


class TestProgramNormalizerBSIS:
    """Test BS Information System normalization."""
    
    def test_normalize_bsis_abbreviation(self, normalizer):
        """Normalize 'BSIS' to canonical form."""
        assert normalizer.normalize("BSIS") == "BS Information System"
    
    def test_normalize_bsis_with_hyphen(self, normalizer):
        """Normalize 'BS-IS' to canonical form."""
        assert normalizer.normalize("BS-IS") == "BS Information System"
    
    def test_normalize_bsis_with_space(self, normalizer):
        """Normalize 'BS IS' to canonical form."""
        assert normalizer.normalize("BS IS") == "BS Information System"
    
    def test_normalize_bsis_full_name(self, normalizer):
        """Normalize 'BS Information System' (already canonical)."""
        assert normalizer.normalize("BS Information System") == "BS Information System"
    
    def test_normalize_bsis_plural(self, normalizer):
        """Normalize 'BS Information Systems' (plural) to canonical."""
        assert normalizer.normalize("BS Information Systems") == "BS Information System"
    
    def test_normalize_bsis_full_title(self, normalizer):
        """Normalize 'Bachelor of Science in Information System' to canonical."""
        assert normalizer.normalize("Bachelor of Science in Information System") == "BS Information System"
    
    def test_normalize_bsis_full_title_plural(self, normalizer):
        """Normalize 'Bachelor of Science in Information Systems' to canonical."""
        assert normalizer.normalize("Bachelor of Science in Information Systems") == "BS Information System"
    
    def test_normalize_bsis_short_form(self, normalizer):
        """Normalize 'Information Systems' to canonical."""
        assert normalizer.normalize("Information Systems") == "BS Information System"
    
    def test_normalize_bsis_case_insensitive(self, normalizer):
        """Normalize 'bsis' (lowercase) to canonical."""
        assert normalizer.normalize("bsis") == "BS Information System"
    
    def test_normalize_bsis_mixed_case(self, normalizer):
        """Normalize 'BsIs' (mixed case) to canonical."""
        assert normalizer.normalize("BsIs") == "BS Information System"


class TestProgramNormalizerBSIT:
    """Test BS Information Technology normalization."""
    
    def test_normalize_bsit_abbreviation(self, normalizer):
        """Normalize 'BSIT' to canonical form."""
        assert normalizer.normalize("BSIT") == "BS Information Technology"
    
    def test_normalize_bsit_with_hyphen(self, normalizer):
        """Normalize 'BS-IT' to canonical form."""
        assert normalizer.normalize("BS-IT") == "BS Information Technology"
    
    def test_normalize_bsit_with_space(self, normalizer):
        """Normalize 'BS IT' to canonical form."""
        assert normalizer.normalize("BS IT") == "BS Information Technology"
    
    def test_normalize_bsit_full_name(self, normalizer):
        """Normalize 'BS Information Technology' (already canonical)."""
        assert normalizer.normalize("BS Information Technology") == "BS Information Technology"
    
    def test_normalize_bsit_full_title(self, normalizer):
        """Normalize 'Bachelor of Science in Information Technology' to canonical."""
        assert normalizer.normalize("Bachelor of Science in Information Technology") == "BS Information Technology"
    
    def test_normalize_bsit_plural(self, normalizer):
        """Normalize 'BS Information Technologies' (plural) to canonical."""
        assert normalizer.normalize("BS Information Technologies") == "BS Information Technology"
    
    def test_normalize_bsit_short_form(self, normalizer):
        """Normalize 'Information Technology' to canonical."""
        assert normalizer.normalize("Information Technology") == "BS Information Technology"
    
    def test_normalize_bsit_case_insensitive(self, normalizer):
        """Normalize 'bsit' (lowercase) to canonical."""
        assert normalizer.normalize("bsit") == "BS Information Technology"
    
    def test_normalize_bsit_mixed_case(self, normalizer):
        """Normalize 'BsIt' (mixed case) to canonical."""
        assert normalizer.normalize("BsIt") == "BS Information Technology"


class TestProgramNormalizerBSCS:
    """Test BS Computer Science normalization."""
    
    def test_normalize_bscs_abbreviation(self, normalizer):
        """Normalize 'BSCS' to canonical form."""
        assert normalizer.normalize("BSCS") == "BS Computer Science"
    
    def test_normalize_bscs_with_hyphen(self, normalizer):
        """Normalize 'BS-CS' to canonical form."""
        assert normalizer.normalize("BS-CS") == "BS Computer Science"
    
    def test_normalize_bscs_with_space(self, normalizer):
        """Normalize 'BS CS' to canonical form."""
        assert normalizer.normalize("BS CS") == "BS Computer Science"
    
    def test_normalize_bscs_full_name(self, normalizer):
        """Normalize 'BS Computer Science' (already canonical)."""
        assert normalizer.normalize("BS Computer Science") == "BS Computer Science"
    
    def test_normalize_bscs_full_title(self, normalizer):
        """Normalize 'Bachelor of Science in Computer Science' to canonical."""
        assert normalizer.normalize("Bachelor of Science in Computer Science") == "BS Computer Science"
    
    def test_normalize_bscs_short_form(self, normalizer):
        """Normalize 'Computer Science' to canonical."""
        assert normalizer.normalize("Computer Science") == "BS Computer Science"
    
    def test_normalize_bscs_case_insensitive(self, normalizer):
        """Normalize 'bscs' (lowercase) to canonical."""
        assert normalizer.normalize("bscs") == "BS Computer Science"
    
    def test_normalize_bscs_mixed_case(self, normalizer):
        """Normalize 'BsCs' (mixed case) to canonical."""
        assert normalizer.normalize("BsCs") == "BS Computer Science"


class TestProgramNormalizerACT:
    """Test Associate in Computer Technology normalization."""
    
    def test_normalize_act_abbreviation(self, normalizer):
        """Normalize 'ACT' to canonical form."""
        assert normalizer.normalize("ACT") == "Associate in Computer Technology"
    
    def test_normalize_act_full_name(self, normalizer):
        """Normalize 'Associate in Computer Technology' (already canonical)."""
        assert normalizer.normalize("Associate in Computer Technology") == "Associate in Computer Technology"
    
    def test_normalize_act_without_in(self, normalizer):
        """Normalize 'Associate Computer Technology' to canonical."""
        assert normalizer.normalize("Associate Computer Technology") == "Associate in Computer Technology"
    
    def test_normalize_act_short_form(self, normalizer):
        """Normalize 'Computer Technology' to canonical."""
        assert normalizer.normalize("Computer Technology") == "Associate in Computer Technology"
    
    def test_normalize_act_case_insensitive(self, normalizer):
        """Normalize 'act' (lowercase) to canonical."""
        assert normalizer.normalize("act") == "Associate in Computer Technology"
    
    def test_normalize_act_mixed_case(self, normalizer):
        """Normalize 'AcT' (mixed case) to canonical."""
        assert normalizer.normalize("AcT") == "Associate in Computer Technology"


class TestProgramNormalizerEdgeCases:
    """Test edge cases and error handling."""
    
    def test_normalize_unknown_program(self, normalizer):
        """Unknown program returns original value."""
        assert normalizer.normalize("BS Biology") == "BS Biology"
    
    def test_normalize_empty_string(self, normalizer):
        """Empty string returns None."""
        assert normalizer.normalize("") is None
    
    def test_normalize_none(self, normalizer):
        """None input returns None."""
        assert normalizer.normalize(None) is None
    
    def test_normalize_with_extra_whitespace(self, normalizer):
        """Extra whitespace is handled correctly."""
        assert normalizer.normalize("  BSIS  ") == "BS Information System"
    
    def test_normalize_with_punctuation(self, normalizer):
        """Punctuation is handled correctly."""
        assert normalizer.normalize("B.S.I.S.") == "BS Information System"
    
    def test_normalize_partial_match(self, normalizer):
        """Partial match works correctly."""
        # "Information System" should match even without "BS" prefix
        assert normalizer.normalize("Information System") == "BS Information System"


class TestProgramNormalizerCanonicalList:
    """Test canonical program list."""
    
    def test_canonical_tuple_exists(self, normalizer):
        """CANONICAL tuple is defined."""
        assert hasattr(normalizer, 'CANONICAL')
        assert isinstance(normalizer.CANONICAL, tuple)
    
    def test_canonical_contains_all_programs(self, normalizer):
        """CANONICAL contains all 4 programs."""
        assert len(normalizer.CANONICAL) == 4
        assert "BS Information System" in normalizer.CANONICAL
        assert "BS Information Technology" in normalizer.CANONICAL
        assert "BS Computer Science" in normalizer.CANONICAL
        assert "Associate in Computer Technology" in normalizer.CANONICAL
    
    def test_aliases_dict_exists(self, normalizer):
        """ALIASES dict is defined."""
        assert hasattr(normalizer, 'ALIASES')
        assert isinstance(normalizer.ALIASES, dict)
    
    def test_aliases_cover_all_programs(self, normalizer):
        """ALIASES cover all canonical programs."""
        canonical_set = set(normalizer.CANONICAL)
        alias_values = set(normalizer.ALIASES.values())
        assert canonical_set == alias_values
