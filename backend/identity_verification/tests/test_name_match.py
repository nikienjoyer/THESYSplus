"""The registered name must appear on the uploaded ID or COR.

Names and numbers are made up; the OCR layouts copy real verification
results, where the extracted ``full_name`` field was unusable ("Assesssed
Fees") but the name was present in the raw OCR text.
"""

import pytest

from identity_verification.validators.rule_validator import name_matches


@pytest.mark.parametrize('first, last, ocr', [
    # COR layout: "Name: LAST, FIRST MIDDLE Year Level: ..."
    ('Ana', 'Bautista', 'Name: BAUTISTA, ANA LOPEZ Year Level: 4th Year'),
    ('Mark Anthony', 'Villanueva', 'Name: VILLANUEVA, MARK ANTHONY RAMOS Year Level: 4th Year'),
    # ID layouts: "FIRST M. LAST" above the student number.
    ('Paolo Miguel', 'Ramos', 'MAIN CAMPUS.\n\nPAOLO MIGUEL D. RAMOS\n\n2023123456'),
    ('Carla Mae', 'Santiago', 'CARLA MAE T. SANTIAGO\n2023123457'),
    # One first-name word is enough: OCR may drop or misread the other.
    ('Mark Anthony', 'Villanueva', 'VILLANUEVA, MARK ANTH0NY'),
    # Multi-word surnames and case/accents/punctuation are ignored.
    ('Juan', 'Dela Cruz', 'Name: DELA CRUZ, JUAN MIGUEL'),
    ('José', 'Peña', 'PENA, JOSE'),
    ('juan miguel', 'dela cruz', 'DELA-CRUZ, JUAN'),
])
def test_registered_name_found_on_document(first, last, ocr):
    assert name_matches(first, last, ocr)


@pytest.mark.parametrize('first, last, ocr', [
    # The reported case: an applicant uploaded another student's COR.
    ('Carlo', 'Mendoza', 'Name: AQUINO, LIZA MARIE PEREZ Year Level: 4th Year'),
    # Someone else's ID under a made-up name.
    ('Gojo', 'Satoru', 'PAOLO MIGUEL D. RAMOS\n2023123456'),
    # Surname alone is not enough, nor is the first name alone.
    ('Maria', 'Ramos', 'PAOLO MIGUEL D. RAMOS'),
    ('Paolo', 'Santos', 'PAOLO MIGUEL D. RAMOS'),
    # Whole words only: "Mar" is not in "Marco", "Cruz" is not in "Cruzado".
    ('Mar', 'Cruz', 'MARCO CRUZADO'),
    # Nothing readable.
    ('Juan', 'Dela Cruz', ''),
])
def test_other_name_on_document_does_not_match(first, last, ocr):
    assert not name_matches(first, last, ocr)


def test_single_letter_initials_are_ignored():
    # "D." must not satisfy the first-name requirement on its own.
    assert not name_matches('D', 'Ramos', 'PAOLO MIGUEL D. RAMOS')


def test_missing_registered_name_never_matches():
    assert not name_matches('', '', 'PAOLO MIGUEL D. RAMOS')
