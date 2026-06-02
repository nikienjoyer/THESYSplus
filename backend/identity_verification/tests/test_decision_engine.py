"""Unit tests for DecisionEngine.

Tests decision logic for identity verification.
Per Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6.
"""

import pytest

from identity_verification.services.ocr_extractor import OCRResult
from identity_verification.services.decision_engine import DecisionEngine, Decision
from identity_verification.validators.rule_validator import RuleResult, RuleFailure


@pytest.fixture
def decision_engine():
    """Create a DecisionEngine instance."""
    return DecisionEngine()


class TestDecisionEngineAutoApproved:
    """Test cases that should result in AUTO_APPROVED."""
    
    def test_high_confidence_rules_pass(self, decision_engine):
        """High OCR confidence + rules pass → AUTO_APPROVED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=92.5,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(
            passed=True,
            failures=[],
        )
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'auto_approved'
        assert decision.reason == 'high_confidence'
        assert decision.confidence_summary['ocr_confidence'] == 92.5
        assert decision.confidence_summary['rule_validation'] == 'passed'
        assert len(decision.flagged_reasons) == 0
    
    def test_exactly_75_percent_confidence(self, decision_engine):
        """Exactly 75% confidence → AUTO_APPROVED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=75.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'auto_approved'
        assert decision.reason == 'high_confidence'
    
    def test_very_high_confidence(self, decision_engine):
        """Very high confidence (95%) → AUTO_APPROVED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=95.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'auto_approved'


class TestDecisionEnginePendingManualReview:
    """Test cases that should result in PENDING_MANUAL_REVIEW."""
    
    def test_medium_confidence_rules_pass(self, decision_engine):
        """Medium OCR confidence (60-75%) → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=65.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'ocr_medium_confidence'
        assert 'OCR confidence medium' in decision.flagged_reasons[0]
    
    def test_low_confidence_rules_pass(self, decision_engine):
        """Low OCR confidence (<60%) → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=45.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'ocr_low_confidence'
        assert 'OCR confidence low' in decision.flagged_reasons[0]
    
    def test_exactly_60_percent_confidence(self, decision_engine):
        """Exactly 60% confidence → PENDING_MANUAL_REVIEW (medium)."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=60.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'ocr_medium_confidence'
    
    def test_missing_required_fields_with_psu_signal(self, decision_engine):
        """Missing required fields but PSU signals present → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="PAMPANGA STATE UNIVERSITY\nSome blurry text",
            overall_confidence=85.0,  # High confidence
            success=True,
            error=None,
        )

        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Required field is missing',
                    expected='Pampanga State University',
                    actual=None,
                ),
            ],
        )

        decision = decision_engine.decide_mvp(ocr_result, rule_result)

        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'incomplete_extraction'
        assert 'Missing required field: school_name' in decision.flagged_reasons

    def test_missing_required_fields_no_psu_signal(self, decision_engine):
        """Missing required fields AND no PSU signals → REJECTED."""
        ocr_result = OCRResult(
            raw_text="Sample text",  # No PSU/DHVSU keywords
            overall_confidence=85.0,
            success=True,
            error=None,
        )

        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Required field is missing',
                    expected='Pampanga State University',
                    actual=None,
                ),
            ],
        )

        decision = decision_engine.decide_mvp(ocr_result, rule_result)

        assert decision.status == 'rejected'
        assert decision.reason == 'invalid_institution'
        assert decision.confidence_summary['rejection_type'] == 'no_psu_signal'


class TestDecisionEngineRejected:
    """Test cases that should result in REJECTED."""
    
    def test_wrong_institution(self, decision_engine):
        """Wrong institution → REJECTED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=90.0,  # High confidence
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Institution not allowed',
                    expected=['Pampanga State University', 'PSU'],
                    actual='University of the Philippines',
                ),
            ],
        )
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'rejected'
        assert decision.reason == 'rule_validation_failed'
        assert decision.confidence_summary['rejection_type'] == 'clear_invalid'
        assert 'Invalid institution' in decision.flagged_reasons[0]
    
    def test_wrong_college(self, decision_engine):
        """Wrong college → REJECTED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=88.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='college',
                    reason='College not allowed',
                    expected=['College of Computing Studies', 'CCS'],
                    actual='College of Engineering',
                ),
            ],
        )
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'rejected'
        assert decision.reason == 'rule_validation_failed'
        assert 'Invalid college' in decision.flagged_reasons[0]
    
    def test_wrong_program(self, decision_engine):
        """Wrong program → REJECTED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=92.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='program',
                    reason='Program not allowed',
                    expected=['BS Information System', 'BS Information Technology', 'BS Computer Science', 'Associate in Computer Technology'],
                    actual='BS Biology',
                ),
            ],
        )
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'rejected'
        assert decision.reason == 'rule_validation_failed'
        assert 'Invalid program' in decision.flagged_reasons[0]
    
    def test_multiple_clear_rejections(self, decision_engine):
        """Multiple clear rejections → REJECTED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=85.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Institution not allowed',
                    expected=['Pampanga State University'],
                    actual='Ateneo de Manila',
                ),
                RuleFailure(
                    field='college',
                    reason='College not allowed',
                    expected=['College of Computing Studies'],
                    actual='School of Science',
                ),
            ],
        )
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'rejected'
        assert len(decision.flagged_reasons) == 2


class TestDecisionEngineEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_confidence(self, decision_engine):
        """Zero OCR confidence → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="",
            overall_confidence=0.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'ocr_low_confidence'
    
    def test_100_percent_confidence(self, decision_engine):
        """100% OCR confidence → AUTO_APPROVED."""
        ocr_result = OCRResult(
            raw_text="Perfect text",
            overall_confidence=100.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'auto_approved'
    
    def test_just_below_high_threshold(self, decision_engine):
        """Just below 75% threshold → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=74.9,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'ocr_medium_confidence'
    
    def test_just_below_medium_threshold(self, decision_engine):
        """Just below 60% threshold → PENDING_MANUAL_REVIEW (low)."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=59.9,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'ocr_low_confidence'


class TestDecisionEngineConfidenceSummary:
    """Test confidence summary metadata."""
    
    def test_confidence_summary_auto_approved(self, decision_engine):
        """Confidence summary for AUTO_APPROVED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=85.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(passed=True, failures=[])
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.confidence_summary['ocr_confidence'] == 85.0
        assert decision.confidence_summary['rule_validation'] == 'passed'
        assert decision.confidence_summary['threshold'] == 75.0
    
    def test_confidence_summary_rejected(self, decision_engine):
        """Confidence summary for REJECTED."""
        ocr_result = OCRResult(
            raw_text="Sample text",
            overall_confidence=90.0,
            success=True,
            error=None,
        )
        
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='program',
                    reason='Program not allowed',
                    expected=['BS Information System'],
                    actual='BS Biology',
                ),
            ],
        )
        
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        
        assert decision.confidence_summary['ocr_confidence'] == 90.0
        assert decision.confidence_summary['rule_validation'] == 'failed'
        assert decision.confidence_summary['rejection_type'] == 'clear_invalid'


class TestDecisionEngineInstitutionSignal:
    """Test the PSU-signal scoring logic that gates incomplete_extraction vs rejected.

    Core behaviour under test: when rule validation fails ONLY due to missing
    fields (not explicit wrong-value failures), the decision engine must check
    whether the raw OCR text contains PSU/DHVSU signals before deciding between
    PENDING_MANUAL_REVIEW (plausible PSU document) and REJECTED (non-PSU).
    """

    # --- Wrong-school IDs (missing school_name because FieldExtractor
    #     couldn't extract it) → must be REJECTED ---

    def test_other_school_no_psu_signal_rejected(self, decision_engine):
        """Generic unrelated-school OCR text → REJECTED (no PSU signal)."""
        ocr_result = OCRResult(
            raw_text="Holy Angel University\nCollege of Engineering\nJuan Cruz\nBS Civil Engineering",
            overall_confidence=88.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Required field is missing',
                    expected='Pampanga State University',
                    actual=None,
                ),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'rejected'
        assert decision.reason == 'invalid_institution'
        assert decision.confidence_summary['rejection_type'] == 'no_psu_signal'

    def test_random_image_no_text_rejected(self, decision_engine):
        """No meaningful text (random image) → REJECTED."""
        ocr_result = OCRResult(
            raw_text="",
            overall_confidence=0.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='full_name', reason='Required field is missing',
                            expected='Non-empty name', actual=None),
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
                RuleFailure(field='college', reason='Required field is missing',
                            expected='College of Computing Studies or CCS', actual=None),
                RuleFailure(field='program', reason='Required field is missing',
                            expected=['BS Information System'], actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'rejected'
        assert decision.reason == 'invalid_institution'

    def test_whitespace_only_text_rejected(self, decision_engine):
        """Whitespace-only OCR text → REJECTED (treated same as empty)."""
        ocr_result = OCRResult(
            raw_text="   \n\t  \n  ",
            overall_confidence=10.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'rejected'
        assert decision.reason == 'invalid_institution'

    def test_ateneo_text_no_psu_signal_rejected(self, decision_engine):
        """Ateneo text without PSU keywords → REJECTED."""
        ocr_result = OCRResult(
            raw_text="Ateneo de Manila University\nSchool of Science\nMaria Santos\nBS Biology",
            overall_confidence=92.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'rejected'
        assert decision.reason == 'invalid_institution'

    # --- PSU/DHVSU IDs with incomplete extraction → PENDING_MANUAL_REVIEW ---

    def test_pampanga_keyword_pending_review(self, decision_engine):
        """'pampanga' in OCR → PSU signal → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="PAMPANGA STATE\nBlurry text here\nJuan Dela Cruz",
            overall_confidence=55.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
                RuleFailure(field='program', reason='Required field is missing',
                            expected=['BS Information System'], actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'incomplete_extraction'

    def test_dhvsu_keyword_pending_review(self, decision_engine):
        """'dhvsu' in OCR → PSU signal → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="DHVSU\nSome blurry lines\n2021-12345",
            overall_confidence=40.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='full_name', reason='Required field is missing',
                            expected='Non-empty name', actual=None),
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'incomplete_extraction'

    def test_honorio_keyword_pending_review(self, decision_engine):
        """'honorio' in OCR → PSU signal → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="Don Honorio Ventur Hs Tate University\nJuan Cruz\nInformation Technology",
            overall_confidence=62.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'incomplete_extraction'

    def test_ventur_partial_keyword_pending_review(self, decision_engine):
        """'ventur' (OCR-truncated 'ventura') → PSU signal → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="Don Honorio Ventur\nState University\nMaria Santos",
            overall_confidence=58.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'incomplete_extraction'

    def test_two_supportive_keywords_pending_review(self, decision_engine):
        """'psu' + 'ccs' together → weak PSU signal → PENDING_MANUAL_REVIEW."""
        ocr_result = OCRResult(
            raw_text="PSU\nCCS\nSome student name\n2022-54321",
            overall_confidence=50.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='full_name', reason='Required field is missing',
                            expected='Non-empty name', actual=None),
                RuleFailure(field='program', reason='Required field is missing',
                            expected=['BS Information System'], actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        assert decision.status == 'pending_manual_review'
        assert decision.reason == 'incomplete_extraction'

    def test_single_supportive_keyword_insufficient(self, decision_engine):
        """Only 'psu' alone (no distinctive kw) → REJECTED (not strong enough)."""
        ocr_result = OCRResult(
            raw_text="PSU student card\nSome name\n2021-11111",
            overall_confidence=80.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(field='school_name', reason='Required field is missing',
                            expected='Pampanga State University', actual=None),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        # "psu" alone is not distinctive enough — treated as no PSU signal
        assert decision.status == 'rejected'
        assert decision.reason == 'invalid_institution'

    # --- Explicit wrong-value failures always REJECTED regardless of OCR text ---

    def test_explicit_wrong_institution_always_rejected(self, decision_engine):
        """Explicit 'Institution not allowed' failure → always REJECTED."""
        ocr_result = OCRResult(
            raw_text="Holy Angel University — but wait, pampanga is nearby",
            overall_confidence=90.0,
            success=True,
            error=None,
        )
        rule_result = RuleResult(
            passed=False,
            failures=[
                RuleFailure(
                    field='school_name',
                    reason='Institution not allowed',
                    expected=['Pampanga State University'],
                    actual='Holy Angel University',
                ),
            ],
        )
        decision = decision_engine.decide_mvp(ocr_result, rule_result)
        # Even though "pampanga" appears in raw text, explicit rejection wins
        assert decision.status == 'rejected'
        assert decision.reason == 'rule_validation_failed'
        assert decision.confidence_summary['rejection_type'] == 'clear_invalid'

    # --- _has_psu_signal unit-level tests ---

    def test_has_psu_signal_distinctive_pampanga(self, decision_engine):
        assert decision_engine._has_psu_signal("PAMPANGA STATE UNIVERSITY") is True

    def test_has_psu_signal_distinctive_dhvsu(self, decision_engine):
        assert decision_engine._has_psu_signal("DHVSU main campus") is True

    def test_has_psu_signal_distinctive_honorio(self, decision_engine):
        assert decision_engine._has_psu_signal("Don Honorio Ventura") is True

    def test_has_psu_signal_distinctive_ventur(self, decision_engine):
        assert decision_engine._has_psu_signal("Don Honorio Ventur Hs Tate University") is True

    def test_has_psu_signal_supportive_psu_ccs(self, decision_engine):
        assert decision_engine._has_psu_signal("PSU\nCCS\nStudent ID") is True

    def test_has_psu_signal_single_supportive_insufficient(self, decision_engine):
        assert decision_engine._has_psu_signal("PSU student") is False

    def test_has_psu_signal_empty(self, decision_engine):
        assert decision_engine._has_psu_signal("") is False

    def test_has_psu_signal_none_equivalent(self, decision_engine):
        assert decision_engine._has_psu_signal("   ") is False

    def test_has_psu_signal_unrelated_text(self, decision_engine):
        assert decision_engine._has_psu_signal("Holy Angel University College of Engineering") is False
