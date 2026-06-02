"""Rule-based validation for identity verification.

Validates extracted fields against institutional requirements.
Per Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from rapidfuzz import fuzz

from ..services.field_extractor import ExtractedFields


@dataclass
class RuleFailure:
    """Represents a single rule validation failure.
    
    Attributes:
        field: Name of the field that failed validation
        reason: Human-readable reason for failure
        expected: Expected value(s)
        actual: Actual value found
    """
    field: str
    reason: str
    expected: str | List[str]
    actual: str | None


@dataclass
class RuleResult:
    """Result of rule validation.
    
    Attributes:
        passed: Whether all rules passed
        failures: List of rule failures (empty if passed)
    """
    passed: bool
    failures: List[RuleFailure]


class RuleValidator:
    """Validates extracted fields against institutional requirements.
    
    Validates:
    - Institution must be Pampanga State University (or PSU alias)
    - College must be College of Computing Studies (or CCS alias)
    - Program must be one of the canonical programs
    - All required fields must be present
    
    Uses negative detection on raw OCR text to distinguish:
    - OCR failure (missing field) → PENDING_MANUAL_REVIEW
    - Clear wrong institution/program → REJECTED
    """
    
    # Allowed institutions (with aliases)
    INSTITUTIONS = (
        'Pampanga State University',
        'PSU',
        'PAMPANGA STATE UNIVERSITY',
    )
    
    # Allowed colleges (with aliases)
    COLLEGES = (
        'College of Computing Studies',
        'CCS',
        'COLLEGE OF COMPUTING STUDIES',
    )
    
    # Canonical programs (must match ProgramNormalizer output)
    PROGRAMS_CANONICAL = (
        'BS Information System',
        'BS Information Technology',
        'BS Computer Science',
        'Associate in Computer Technology',
    )
    
    # Known wrong institutions (for negative detection)
    WRONG_INSTITUTIONS = (
        'University of the Philippines',
        'UP',
        'Holy Angel University',
        'HAU',
        'Angeles University Foundation',
        'AUF',
        'Ateneo',
        'De La Salle',
        'DLSU',
        'UST',
        'University of Santo Tomas',
    )
    
    # Known wrong programs (for negative detection)
    WRONG_PROGRAMS = (
        'BS Biology',
        'BS Nursing',
        'BS Accountancy',
        'BS Civil Engineering',
        'BS Electrical Engineering',
        'BS Mechanical Engineering',
        'BS Architecture',
        'BS Psychology',
        'BS Business Administration',
        'BSBA',
    )
    
    def validate(self, fields: ExtractedFields, ocr_raw_text: str = '') -> RuleResult:
        """Validate extracted fields against rules.
        
        Uses negative detection on raw OCR text to distinguish:
        - OCR failure (missing field) → uncertain rejection
        - Clear wrong institution/program → clear rejection
        
        College inference:
        - If college is missing but program is a valid CCS program,
          infer college as "College of Computing Studies"
        - Real PSU student IDs don't show college, only program
        
        Args:
            fields: Extracted fields from OCR
            ocr_raw_text: Raw OCR text for negative detection
            
        Returns:
            RuleResult with pass/fail status and failure details
        """
        failures = []
        
        # Step 1: Negative detection on raw OCR text
        # Check if OCR clearly contains wrong institution/program
        if ocr_raw_text:
            wrong_institution = self._detect_wrong_institution(ocr_raw_text)
            if wrong_institution:
                failures.append(RuleFailure(
                    field='school_name',
                    reason='Institution not allowed',
                    expected=list(self.INSTITUTIONS),
                    actual=wrong_institution,
                ))
            
            wrong_program = self._detect_wrong_program(ocr_raw_text)
            if wrong_program:
                failures.append(RuleFailure(
                    field='program',
                    reason='Program not allowed',
                    expected=list(self.PROGRAMS_CANONICAL),
                    actual=wrong_program,
                ))
        
        # Step 2: Infer college from program if missing
        # Real PSU student IDs don't show college, only program
        # Since CCS only has 4 allowed programs, we can infer college
        college_inferred = False
        if not fields.college and fields.program:
            if self._can_infer_college_from_program(fields.program):
                # Don't modify the original fields object
                # Just skip the missing college failure
                college_inferred = True
        
        # Step 3: Check required fields are present
        if not fields.full_name:
            failures.append(RuleFailure(
                field='full_name',
                reason='Required field is missing',
                expected='Non-empty name',
                actual=None,
            ))
        
        if not fields.school_name:
            # Only add missing field failure if we didn't already detect wrong institution
            if not any(f.field == 'school_name' and f.reason == 'Institution not allowed' for f in failures):
                failures.append(RuleFailure(
                    field='school_name',
                    reason='Required field is missing',
                    expected='Pampanga State University',
                    actual=None,
                ))
        
        if not fields.college and not college_inferred:
            # Only fail if college is missing AND cannot be inferred from program
            failures.append(RuleFailure(
                field='college',
                reason='Required field is missing',
                expected='College of Computing Studies or CCS',
                actual=None,
            ))
        
        if not fields.program:
            # Only add missing field failure if we didn't already detect wrong program
            if not any(f.field == 'program' and f.reason == 'Program not allowed' for f in failures):
                failures.append(RuleFailure(
                    field='program',
                    reason='Required field is missing',
                    expected=list(self.PROGRAMS_CANONICAL),
                    actual=None,
                ))
        
        # Step 4: Validate extracted fields (if present)
        if fields.school_name:
            if not self._validate_institution(fields.school_name):
                failures.append(RuleFailure(
                    field='school_name',
                    reason='Institution not allowed',
                    expected=list(self.INSTITUTIONS),
                    actual=fields.school_name,
                ))
        
        if fields.college:
            if not self._validate_college(fields.college):
                failures.append(RuleFailure(
                    field='college',
                    reason='College not allowed',
                    expected=list(self.COLLEGES),
                    actual=fields.college,
                ))
        
        if fields.program:
            if not self._validate_program(fields.program):
                failures.append(RuleFailure(
                    field='program',
                    reason='Program not allowed',
                    expected=list(self.PROGRAMS_CANONICAL),
                    actual=fields.program,
                ))
        
        return RuleResult(
            passed=len(failures) == 0,
            failures=failures,
        )
    
    def _detect_wrong_institution(self, ocr_text: str) -> str | None:
        """Detect if OCR text clearly contains a wrong institution.
        
        Args:
            ocr_text: Raw OCR text
            
        Returns:
            Name of wrong institution if detected, None otherwise
        """
        ocr_lower = ocr_text.lower()
        
        for wrong_inst in self.WRONG_INSTITUTIONS:
            # Check for exact phrase match (case-insensitive)
            if wrong_inst.lower() in ocr_lower:
                return wrong_inst
        
        return None
    
    def _detect_wrong_program(self, ocr_text: str) -> str | None:
        """Detect if OCR text clearly contains a wrong program.
        
        Args:
            ocr_text: Raw OCR text
            
        Returns:
            Name of wrong program if detected, None otherwise
        """
        ocr_lower = ocr_text.lower()
        
        for wrong_prog in self.WRONG_PROGRAMS:
            # Check for exact phrase match (case-insensitive)
            if wrong_prog.lower() in ocr_lower:
                return wrong_prog
        
        return None
    
    # PSU / DHVSU canonical forms used for fuzzy matching
    # "Don Honorio Ventura State University" is the formal name of PSU's
    # predecessor institution; DHVSU IDs still carry this name.
    _PSU_CANONICAL_FORMS = (
        'Pampanga State University',
        'Don Honorio Ventura State University',
        'DHVSU',
        'PSU',
    )

    # Minimum token-set-ratio score (0–100) to accept an institution as PSU/DHVSU.
    # token_set_ratio is robust to word-order differences and partial OCR drops.
    # 75 allows "Ventur Hs Tate University" to match "Don Honorio Ventura State
    # University" while still rejecting completely unrelated schools.
    _INSTITUTION_FUZZY_THRESHOLD = 75

    def _validate_institution(self, school_name: str) -> bool:
        """Check if institution is allowed.

        Strategy (most-specific to least-specific):
        1. Exact case-insensitive match against allowed aliases.
        2. PSU keyword pair ('pampanga' + 'state').
        3. DHVSU keyword scoring — requires ≥2 of the distinctive keywords
           {DON, HONORIO, VENTURA} or the exact abbreviation 'DHVSU'.
        4. Fuzzy token-set-ratio against all canonical PSU/DHVSU forms with
           threshold _INSTITUTION_FUZZY_THRESHOLD (75).

        The negative-detection list in WRONG_INSTITUTIONS is checked first by
        the caller (validate()), so we never reach here for clearly wrong schools.

        Args:
            school_name: School name extracted from OCR

        Returns:
            True if institution matches PSU/DHVSU
        """
        school_normalized = school_name.strip()
        school_lower = school_normalized.lower()

        # 1. Exact match (case-insensitive)
        for allowed in self.INSTITUTIONS:
            if school_lower == allowed.lower():
                return True

        # 2. PSU keyword pair
        if 'pampanga' in school_lower and 'state' in school_lower:
            return True

        # 3. DHVSU keyword scoring
        # Require DHVSU abbreviation OR at least 2 of the 3 distinctive forename
        # keywords — this handles "Don Honorio Ventur" (partial OCR) correctly.
        if 'dhvsu' in school_lower:
            return True
        distinctive_keywords = ('don', 'honorio', 'ventura')
        matched_keywords = sum(1 for kw in distinctive_keywords if kw in school_lower)
        # Also accept "ventur" as a truncated OCR variant of "ventura"
        if 'ventur' in school_lower:
            matched_keywords = max(matched_keywords, 1)
            # Count "don" or "honorio" separately
            if 'don' in school_lower or 'honorio' in school_lower:
                matched_keywords = 2
        if matched_keywords >= 2:
            return True

        # 4. Fuzzy token-set-ratio against canonical forms
        # token_set_ratio ignores word order and handles partial matches well,
        # making it ideal for OCR-dropped/mangled university names.
        for canonical in self._PSU_CANONICAL_FORMS:
            score = fuzz.token_set_ratio(school_lower, canonical.lower())
            if score >= self._INSTITUTION_FUZZY_THRESHOLD:
                return True

        return False
    
    def _validate_college(self, college: str) -> bool:
        """Check if college is allowed.
        
        Args:
            college: College name from OCR
            
        Returns:
            True if college is allowed
        """
        # Normalize for comparison
        college_normalized = college.strip()
        
        # Check exact match (case-insensitive)
        for allowed in self.COLLEGES:
            if college_normalized.lower() == allowed.lower():
                return True
        
        # Check if contains key phrase (for OCR typos)
        # Be conservative but allow minor typos
        college_lower = college_normalized.lower()
        
        # Check for "computing" or close variants (comput*)
        has_computing = ('comput' in college_lower)
        
        # Check for "studies" or close variants (stud*)
        has_studies = ('stud' in college_lower)
        
        if has_computing and has_studies:
            return True
        
        return False
    
    def _validate_program(self, program: str) -> bool:
        """Check if program is allowed.
        
        Args:
            program: Normalized program name (from ProgramNormalizer)
            
        Returns:
            True if program is allowed
        """
        # Program should already be normalized by ProgramNormalizer
        # Check exact match against canonical list
        return program in self.PROGRAMS_CANONICAL
    
    def _can_infer_college_from_program(self, program: str) -> bool:
        """Check if college can be inferred from program.
        
        Real PSU student IDs don't show college, only program.
        Since CCS only has 4 allowed programs, we can infer college.
        
        Args:
            program: Normalized program name
            
        Returns:
            True if program is a valid CCS program (college can be inferred)
        """
        # If program is one of the canonical CCS programs, we can infer CCS
        return program in self.PROGRAMS_CANONICAL
