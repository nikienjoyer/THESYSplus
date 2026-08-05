"""Program name normalizers for identity verification.

Normalizes program name aliases to canonical forms.
Per Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6.
"""

from __future__ import annotations

import re


class ProgramNormalizer:
    """Normalizes program name variations to canonical forms.
    
    Handles common aliases and variations for:
    - BS Information System
    - BS Information Technology
    - BS Computer Science
    - Associate in Computer Technology
    """
    
    # Canonical program names
    CANONICAL = (
        'BS Information System',
        'BS Information Technology',
        'BS Computer Science',
        'Associate in Computer Technology',
    )
    
    # Alias mappings (case-insensitive, punctuation-flexible)
    ALIASES = {
        # BS Information System aliases
        'bsis': 'BS Information System',
        'bs-is': 'BS Information System',
        'bs is': 'BS Information System',
        'bs information systems': 'BS Information System',
        'bs information system': 'BS Information System',
        'bachelor of science in information systems': 'BS Information System',
        'bachelor of science in information system': 'BS Information System',
        'information systems': 'BS Information System',
        'information system': 'BS Information System',
        
        # BS Information Technology aliases
        'bsit': 'BS Information Technology',
        'bs-it': 'BS Information Technology',
        'bs it': 'BS Information Technology',
        'bs information technology': 'BS Information Technology',
        'bs information technologies': 'BS Information Technology',
        'bachelor of science in information technology': 'BS Information Technology',
        'information technology': 'BS Information Technology',
        
        # BS Computer Science aliases
        'bscs': 'BS Computer Science',
        'bs-cs': 'BS Computer Science',
        'bs cs': 'BS Computer Science',
        'bs computer science': 'BS Computer Science',
        'bachelor of science in computer science': 'BS Computer Science',
        'computer science': 'BS Computer Science',
        
        # Associate in Computer Technology aliases
        'act': 'Associate in Computer Technology',
        'associate in computer technology': 'Associate in Computer Technology',
        'associate computer technology': 'Associate in Computer Technology',
        'computer technology': 'Associate in Computer Technology',
    }
    
    def normalize(self, raw_program: str | None) -> str | None:
        """Normalize program name to canonical form.
        
        Args:
            raw_program: Raw program name from OCR
            
        Returns:
            Canonical program name if match found, else original value
        """
        if not raw_program:
            return None
        
        # Clean the input: lowercase, remove extra whitespace, remove punctuation
        cleaned = self._clean_text(raw_program)
        
        # Try exact match in aliases
        if cleaned in self.ALIASES:
            return self.ALIASES[cleaned]
        
        # Try fuzzy match (contains key phrase)
        for alias, canonical in self.ALIASES.items():
            if alias in cleaned or cleaned in alias:
                return canonical
        
        # No match found - return original
        return raw_program
    
    def _clean_text(self, text: str) -> str:
        """Clean text for matching: lowercase, remove punctuation, normalize whitespace."""
        # Lowercase
        text = text.lower()
        
        # Remove common punctuation but keep spaces and hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip
        text = text.strip()
        
        return text
