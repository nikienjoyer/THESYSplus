"""The student number in the email must appear on the uploaded ID or COR.

Numbers are made up; the layouts copy what OCR returns for real documents
(boxed ID numbers, hyphenated COR numbers).
"""

import pytest

from identity_verification.validators.rule_validator import student_number_matches

EMAIL = '2023123456@pampangastateu.edu.ph'


@pytest.mark.parametrize('email, ocr', [
    (EMAIL, 'JUAN M. DELA CRUZ\n| 2023123456 |\nBachelor of Science in Information Systems'),
    (EMAIL, 'Student No.: 2023-123456'),
    (EMAIL, 'Student No: 2023 123456'),
    (EMAIL, 'Student No.: 2023123456 1st Semester'),
    ('2023123456@PampangaStateU.edu.ph', 'Student No: 2023123456'),
])
def test_number_from_email_found_on_document(email, ocr):
    assert student_number_matches(email, ocr)


@pytest.mark.parametrize('email, ocr', [
    # The reported case: the email belongs to another student.
    ('2023123499@pampangastateu.edu.ph', 'JUAN M. DELA CRUZ\n| 2023123456 |'),
    # Whole numbers only.
    (EMAIL, 'Ref: 120231234567'),
    ('202312345@pampangastateu.edu.ph', 'Student No: 2023123456'),
    # Not a student-number email, or nothing to compare.
    ('juan.delacruz@pampangastateu.edu.ph', 'juan.delacruz 2023123456'),
    ('', 'Student No: 2023123456'),
    (EMAIL, ''),
])
def test_number_from_email_missing_from_document(email, ocr):
    assert not student_number_matches(email, ocr)
