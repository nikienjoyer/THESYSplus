"""The registered name must appear on the uploaded ID or COR.

OCR lines here are copied from real verification results, where the
extracted ``full_name`` field was unusable ("Assesssed Fees", "Don Ho") but
the name was present in the raw OCR text.
"""

import pytest

from identity_verification.validators.rule_validator import name_matches


@pytest.mark.parametrize('first, last, ocr', [
    ('Romel', 'Salonga', 'Name: SALONGA, ROMEL SANTOS Year Level: 4th Year'),
    ('Kurt Ross', 'Gonzaga', 'Name: GONZAGA, KURT ROSS EDAYAN Year Level: 4th Year'),
    ('Jerry Vic', 'Torres', 'MAIN CAMPUS.\n\nJERRY VIC P. TORRES\n\n2023313546'),
    ('Reanne Kirby', 'Cortez', 'REANNE KIRBY Y. CORTEZ\n2023303521'),
    # One first-name word is enough: OCR may drop or truncate the other.
    ('Kurt Ross', 'Gonzaga', 'GONZAGA, KURT R0SS'),
    # Multi-word surnames and case/accents/punctuation are ignored.
    ('Juan', 'Dela Cruz', 'Name: DELA CRUZ, JUAN MIGUEL'),
    ('José', 'Peña', 'PENA, JOSE'),
    ('juan miguel', 'dela cruz', 'DELA-CRUZ, JUAN'),
])
def test_registered_name_found_on_document(first, last, ocr):
    assert name_matches(first, last, ocr)


@pytest.mark.parametrize('first, last, ocr', [
    # The reported case: John Mar Miclat uploaded Valerie Quizon's COR.
    ('John Mar', 'Miclat', 'Name: QUIZON, VALERIE DAPHNE DAVID Year Level: 4th Year'),
    # Someone else's ID under a made-up name.
    ('Gojo', 'Satoru', 'JERRY VIC P. TORRES\n2023313546'),
    # Surname alone is not enough, nor is the first name alone.
    ('Maria', 'Torres', 'JERRY VIC P. TORRES'),
    ('Jerry', 'Santos', 'JERRY VIC P. TORRES'),
    # Whole words only: "Mar" is not in "Marco", "Cruz" is not in "Cruzado".
    ('Mar', 'Cruz', 'MARCO CRUZADO'),
    # Nothing readable.
    ('Juan', 'Dela Cruz', ''),
])
def test_other_name_on_document_does_not_match(first, last, ocr):
    assert not name_matches(first, last, ocr)


def test_single_letter_initials_are_ignored():
    # "P." must not satisfy the first-name requirement on its own.
    assert not name_matches('P', 'Torres', 'JERRY VIC P. TORRES')


def test_missing_registered_name_never_matches():
    assert not name_matches('', '', 'JERRY VIC P. TORRES')
