"""Field extraction service for OCR text.

Extracts structured fields from raw OCR text using regex patterns.
Per Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..normalizers import ProgramNormalizer


@dataclass
class ExtractedFields:
    """Structured fields extracted from OCR text.
    
    Attributes:
        full_name: Full name of student
        school_name: Name of educational institution
        college: College/department name
        program: Degree program (normalized)
        program_raw: Original program text before normalization
        student_number: Student ID number (optional)
    """
    full_name: str | None = None
    school_name: str | None = None
    college: str | None = None
    program: str | None = None
    program_raw: str | None = None
    student_number: str | None = None


class FieldExtractor:
    """Extracts structured fields from OCR text using regex patterns.
    
    Extracts:
    - Full Name
    - School Name
    - College
    - Program (with normalization)
    - Student Number (optional)
    """
    
    def __init__(self):
        """Initialize field extractor with program normalizer."""
        self.program_normalizer = ProgramNormalizer()
    
    def extract(self, ocr_text: str) -> ExtractedFields:
        """Extract structured fields from OCR text.
        
        Args:
            ocr_text: Raw text from OCR extraction
            
        Returns:
            ExtractedFields with all extracted data
        """
        if not ocr_text:
            return ExtractedFields()
        
        # Extract each field with labeled patterns first
        full_name = self._extract_full_name(ocr_text)
        school_name = self._extract_school_name(ocr_text)
        college = self._extract_college(ocr_text)
        program_raw = self._extract_program(ocr_text)
        student_number = self._extract_student_number(ocr_text)
        
        # Apply fallback heuristics for unlabeled student IDs
        if not school_name:
            school_name = self._fallback_extract_school_name(ocr_text)
        
        if not program_raw:
            program_raw = self._fallback_extract_program(ocr_text)
        
        if not full_name:
            full_name = self._fallback_extract_full_name(ocr_text, school_name)
        
        if not student_number:
            student_number = self._fallback_extract_student_number(ocr_text)
        
        # Normalize program name
        program = self.program_normalizer.normalize(program_raw)
        
        return ExtractedFields(
            full_name=full_name,
            school_name=school_name,
            college=college,
            program=program,
            program_raw=program_raw,
            student_number=student_number,
        )
    
    def _extract_full_name(self, text: str) -> str | None:
        """Extract full name from OCR text.
        
        Patterns:
        - "Name: John Doe"
        - "Student Name: John Doe"
        - "Full Name: John Doe"
        """
        patterns = [
            r'(?:Full\s+)?(?:Student\s+)?Name\s*[:\-]\s*([A-Z][a-zA-Z\s,\.]+?)(?:\n|$)',
            r'Name\s*[:\-]\s*([A-Z][a-zA-Z\s,\.]+?)(?:\n|Student|ID|Number)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Clean up common OCR artifacts
                name = re.sub(r'\s+', ' ', name)
                name = name.strip(' ,.')
                if len(name) > 3:  # Minimum reasonable name length
                    return name
        
        return None
    
    def _extract_school_name(self, text: str) -> str | None:
        """Extract school/university name from OCR text.
        
        Patterns:
        - "Pampanga State University"
        - "PAMPANGA STATE UNIVERSITY"
        - "School: Pampanga State University"
        """
        patterns = [
            r'(Pampanga\s+State\s+University)',
            r'(PAMPANGA\s+STATE\s+UNIVERSITY)',
            r'(?:School|University)\s*[:\-]\s*(Pampanga\s+State\s+University)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                school = match.group(1).strip()
                # Normalize to title case
                return 'Pampanga State University'
        
        return None
    
    def _extract_college(self, text: str) -> str | None:
        """Extract college/department name from OCR text.
        
        Patterns:
        - "College of Computing Studies"
        - "CCS"
        - "College: CCS"
        """
        patterns = [
            r'(College\s+of\s+Computing\s+Studies)',
            r'(?:College|Dept|Department)\s*[:\-]\s*(College\s+of\s+Computing\s+Studies)',
            r'(?:College|Dept|Department)\s*[:\-]\s*(CCS)',
            r'\b(CCS)\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                college = match.group(1).strip()
                # Normalize common abbreviations
                if college.upper() == 'CCS':
                    return 'CCS'
                return 'College of Computing Studies'
        
        return None
    
    def _extract_program(self, text: str) -> str | None:
        """Extract degree program from OCR text.
        
        Patterns:
        - "Program: BS Information System"
        - "Course: BSIT"
        - "BS Computer Science"
        """
        patterns = [
            r'(?:Program|Course|Degree)\s*[:\-]\s*([A-Z][A-Za-z\s\-]+?)(?:\n|$)',
            r'\b(BS\s+Information\s+System[s]?)\b',
            r'\b(BS\s+Information\s+Technology)\b',
            r'\b(BS\s+Computer\s+Science)\b',
            r'\b(Associate\s+in\s+Computer\s+Technology)\b',
            r'\b(BSIS|BS-IS|BS\s+IS)\b',
            r'\b(BSIT|BS-IT|BS\s+IT)\b',
            r'\b(BSCS|BS-CS|BS\s+CS)\b',
            r'\b(ACT)\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                program = match.group(1).strip()
                # Clean up
                program = re.sub(r'\s+', ' ', program)
                if len(program) > 2:  # Minimum reasonable program length
                    return program
        
        return None
    
    def _extract_student_number(self, text: str) -> str | None:
        """Extract student ID number from OCR text.
        
        Patterns:
        - "Student No: 2021-12345"
        - "ID: 202112345"
        - "Student Number: 2021-12345"
        """
        patterns = [
            r'(?:Student\s+)?(?:No|Number|ID)\s*[:\-]\s*(\d{4}[\-\s]?\d{4,5})',
            r'(?:Student\s+)?(?:No|Number|ID)\s*[:\-]\s*(\d{8,10})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                student_num = match.group(1).strip()
                # Normalize format
                student_num = re.sub(r'\s+', '', student_num)
                return student_num
        
        return None
    
    # ========== FALLBACK EXTRACTION HEURISTICS ==========
    # These methods handle unlabeled student ID formats
    
    def _fallback_extract_school_name(self, text: str) -> str | None:
        """Fallback: Extract university name without labels.
        
        Detects university names by pattern matching:
        - Contains "STATE UNIVERSITY"
        - Contains "UNIVERSITY"
        - Multi-line patterns (e.g., "DON HONORIO VENTURA" + "STATE UNIVERSITY")
        
        Maps known universities to canonical PSU equivalent.
        Uses keyword scoring to handle OCR-mangled DHVSU names like
        "Don Honorio Ventur Hs Tate University".
        """
        # ------------------------------------------------------------------ #
        # 1. Exact substring checks (fast path, most common OCR outputs)      #
        # ------------------------------------------------------------------ #
        psu_exact_tokens = [
            'DON HONORIO VENTURA STATE UNIVERSITY',
            'DON HONORIO VENTURA',
            'DHVSU',
            'PAMPANGA STATE UNIVERSITY',
            'PSU',
        ]
        text_upper = text.upper()
        for token in psu_exact_tokens:
            if token in text_upper:
                return 'Pampanga State University'

        # ------------------------------------------------------------------ #
        # 2. Keyword-scoring across all lines (handles OCR mangling)          #
        #    "Don Honorio Ventur Hs Tate University" → score 3 → PSU          #
        # ------------------------------------------------------------------ #
        # Keywords weighted by distinctiveness:
        #   DON / HONORIO / VENTURA / VENTUR  →  only appear in DHVSU name
        #   STATE / UNIVERSITY / TATE / UNIVERS  →  common university words
        # Require ≥2 distinctive DHVSU keywords to minimise false-positives.
        distinctive_kws = ('don', 'honorio', 'ventura', 'ventur')
        lines_upper = [l.strip().upper() for l in text.split('\n') if l.strip()]
        for line in lines_upper:
            line_lower = line.lower()
            score = sum(1 for kw in distinctive_kws if kw in line_lower)
            if score >= 2:
                return 'Pampanga State University'

        # Also accept a line containing any ONE distinctive keyword + "state"
        # or "university" — e.g. "VENTURA STATE UNIVERSITY" with OCR drops
        for line in lines_upper:
            line_lower = line.lower()
            has_distinctive = any(kw in line_lower for kw in distinctive_kws)
            has_state_univ = 'state' in line_lower or 'universit' in line_lower or 'tate' in line_lower
            if has_distinctive and has_state_univ:
                return 'Pampanga State University'

        # ------------------------------------------------------------------ #
        # 3. Multi-line patterns (university name split across lines)         #
        # ------------------------------------------------------------------ #
        for i, line in enumerate(lines_upper):
            if 'STATE UNIVERSITY' in line:
                for j in range(max(0, i - 2), i):
                    prev_line = lines_upper[j].lower()
                    if not any(skip in prev_line for skip in ['campus', 'bachelor', 'information', 'computer']):
                        if any(kw in prev_line for kw in ('don', 'honorio', 'ventura', 'ventur')):
                            return 'Pampanga State University'

        # ------------------------------------------------------------------ #
        # 4. Generic regex patterns (other institutions)                      #
        # ------------------------------------------------------------------ #
        state_univ_pattern = r'([A-Z][A-Z\s]+STATE\s+UNIVERSITY)'
        match = re.search(state_univ_pattern, text)
        if match:
            univ_name = match.group(1).strip()
            if any(kw in univ_name.upper() for kw in ('DON HONORIO VENTURA', 'DHVSU', 'PAMPANGA')):
                return 'Pampanga State University'
            return univ_name.title()

        univ_pattern = r'([A-Z][A-Z\s]+UNIVERSITY)'
        match = re.search(univ_pattern, text)
        if match:
            univ_name = match.group(1).strip()
            if any(kw in univ_name.upper() for kw in ('DON HONORIO VENTURA', 'DHVSU', 'PAMPANGA')):
                return 'Pampanga State University'
            return univ_name.title()

        # Check for "BACHELOR OF SCIENCE" which indicates a university document
        # If we see this but no explicit university name, it might be PSU
        if 'BACHELOR OF SCIENCE' in text.upper():
            if any(prog in text.upper() for prog in ['INFORMATION SYSTEM', 'INFORMATION TECHNOLOGY', 'COMPUTER SCIENCE']):
                return 'Pampanga State University'

        return None
    
    def _fallback_extract_program(self, text: str) -> str | None:
        """Fallback: Extract program name without labels.
        
        Detects common CCS program names:
        - Information Systems
        - Information Technology
        - Computer Science
        - Computer Technology
        """
        # Known CCS programs (case-insensitive)
        program_patterns = [
            r'\b(Information\s+Systems?)\b',
            r'\b(Information\s+Technology)\b',
            r'\b(Computer\s+Science)\b',
            r'\b(Computer\s+Technology)\b',
        ]
        
        for pattern in program_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                program = match.group(1).strip()
                # Return raw program name (will be normalized by ProgramNormalizer)
                return program
        
        return None
    
    def _fallback_extract_full_name(self, text: str, school_name: str | None) -> str | None:
        """Fallback: Extract full name from uppercase multi-word text.
        
        Heuristic:
        - Line with 2-4 uppercase words
        - Each word 2+ characters
        - Not a university name
        - Not a program name
        - Not a college name
        - Not common document labels
        
        Args:
            text: OCR text
            school_name: Already extracted school name (to avoid confusion)
        """
        lines = text.split('\n')
        
        # Exclusion patterns (things that are NOT names)
        exclusions = [
            'UNIVERSITY',
            'STATE',
            'COLLEGE',
            'INFORMATION',
            'COMPUTER',
            'SCIENCE',
            'TECHNOLOGY',
            'STUDENT',
            'REPUBLIC',
            'PHILIPPINES',
            'CERTIFICATE',
            'REGISTRATION',
            'DEPARTMENT',
            'EDUCATION',
            'CAMPUS',  # Added: MAIN CAMPUS, etc.
            'BACHELOR',  # Added: BACHELOR OF SCIENCE
            'MASTER',
            'DOCTOR',
            'DIPLOMA',
            'DEGREE',
            'PROGRAM',
            'COURSE',
        ]
        
        # Find potential name lines
        candidates = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Must be mostly uppercase
            if not line.isupper():
                continue
            
            # Split into words
            words = line.split()
            
            # Must have 2-4 words (typical name format)
            if not (2 <= len(words) <= 4):
                continue
            
            # Each word must be 2+ characters
            if not all(len(w) >= 2 for w in words):
                continue
            
            # Must not contain exclusion keywords
            if any(excl in line for excl in exclusions):
                continue
            
            # Must not be the school name
            if school_name and school_name.upper() in line:
                continue
            
            # Must be mostly alphabetic (allow dots for middle initials)
            cleaned = line.replace('.', '').replace(' ', '')
            if not cleaned.isalpha():
                continue
            
            # Check context: prefer names that appear near program information
            # Look for program keywords in nearby lines
            context_score = 0
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                if j != i:
                    context_line = lines[j].upper()
                    if any(prog in context_line for prog in ['INFORMATION SYSTEM', 'INFORMATION TECHNOLOGY', 'COMPUTER SCIENCE', 'BACHELOR']):
                        context_score += 1
            
            # Store candidate with context score
            candidates.append((line.title(), context_score, i))
        
        # Return the candidate with highest context score
        # If tie, prefer the one that appears earlier (closer to top)
        if candidates:
            candidates.sort(key=lambda x: (-x[1], x[2]))  # Sort by score desc, then line number asc
            return candidates[0][0]
        
        return None
    
    def _fallback_extract_student_number(self, text: str) -> str | None:
        """Fallback: Extract student number from long digit sequences.
        
        Looks for:
        - 8-10 consecutive digits
        - 4 digits + hyphen/space + 4-6 digits
        
        Excludes:
        - Phone numbers (starts with 09, +63)
        - Years (19xx, 20xx in isolation)
        """
        # Pattern 1: 8-10 consecutive digits (not starting with 09 or 63)
        pattern1 = r'\b(?!09|63)(\d{8,10})\b'
        matches = re.findall(pattern1, text)
        
        for match in matches:
            # Exclude year-like patterns
            if match.startswith('19') or match.startswith('20'):
                if len(match) == 4:
                    continue
            return match
        
        # Pattern 2: 4 digits + separator + 4-6 digits
        pattern2 = r'\b(\d{4})[\-\s](\d{4,6})\b'
        match = re.search(pattern2, text)
        if match:
            # Combine and return
            return match.group(1) + match.group(2)
        
        return None
