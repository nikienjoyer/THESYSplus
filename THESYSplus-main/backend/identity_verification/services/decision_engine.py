"""Decision engine for identity verification.

Makes verification decisions based on OCR confidence and rule validation.
Per Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List

from ..services.ocr_extractor import OCRResult
from ..validators.rule_validator import RuleResult, RuleFailure


@dataclass
class Decision:
    """Verification decision result.
    
    Attributes:
        status: Decision status (auto_approved, pending_manual_review, rejected)
        reason: Human-readable reason for decision
        confidence_summary: Summary of confidence scores
        flagged_reasons: List of reasons for flagging (if any)
    """
    status: str  # 'auto_approved', 'pending_manual_review', 'rejected'
    reason: str
    confidence_summary: dict
    flagged_reasons: List[str]


class DecisionEngine:
    """Makes verification decisions based on OCR and rule validation.

    Decision Logic:
    - REJECTED: Clear invalid institution/college/program, OR missing fields
                with NO PSU/DHVSU signals in raw OCR text.
    - PENDING_MANUAL_REVIEW: Missing fields but OCR text contains PSU/DHVSU
                signals (likely blurry/partial PSU ID), or medium/low OCR
                confidence on an otherwise valid document.
    - AUTO_APPROVED: Rules pass + required fields complete + OCR ≥75%.

    Institution-signal scoring
    --------------------------
    When rule validation fails ONLY due to missing required fields (no
    explicit "Institution not allowed" failure), we score the raw OCR text
    for PSU/DHVSU-distinctive keywords.  These keywords are highly specific
    to Don Honorio Ventura State University / Pampanga State University and
    would not normally appear in IDs from other Philippine institutions:

        Distinctive: dhvsu, pampanga, honorio, ventura, ventur
        Supportive (require ≥2):  psu, ccs

    If NONE of these signals are detected the document almost certainly does
    not originate from PSU/DHVSU → REJECTED with reason 'invalid_institution'.
    If at least one distinctive signal (or ≥2 supportive signals) is present
    the document is likely a blurry or partial PSU ID → PENDING_MANUAL_REVIEW.
    """

    # OCR confidence thresholds
    OCR_CONFIDENCE_HIGH = 75.0    # Auto-approve threshold
    OCR_CONFIDENCE_MEDIUM = 60.0  # Manual review threshold

    # Keywords that are DISTINCTIVE to PSU / DHVSU.
    # Presence of ANY ONE of these in the raw OCR text is sufficient evidence
    # that the document originates from Don Honorio Ventura State University
    # (Pampanga State University).  These words do not commonly appear on IDs
    # from other Philippine universities.
    _PSU_DISTINCTIVE_KEYWORDS: FrozenSet[str] = frozenset({
        'dhvsu',
        'pampanga',
        'honorio',
        'ventura',
        'ventur',    # truncated OCR variant of "ventura"
    })

    # Supportive keywords — present on PSU documents but not exclusively PSU.
    # At least TWO of these together can serve as a weak PSU signal.
    _PSU_SUPPORTIVE_KEYWORDS: FrozenSet[str] = frozenset({
        'psu',
        'ccs',
        'college of computing',
    })

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def decide_mvp(
        self,
        ocr_result: OCRResult,
        rule_result: RuleResult,
    ) -> Decision:
        """Make verification decision (MVP logic — OCR + rules only).

        Args:
            ocr_result: OCR extraction result with confidence and raw text.
            rule_result: Rule validation result from RuleValidator.

        Returns:
            Decision with status, reason, confidence_summary, flagged_reasons.
        """
        flagged_reasons: List[str] = []

        # Step 1: Check rule validation result
        if not rule_result.passed:
            rejection_reasons = self._analyze_rule_failures(rule_result.failures)

            # 1a. Explicit clear rejection (wrong institution / college / program)
            if rejection_reasons['clear_rejection']:
                return Decision(
                    status='rejected',
                    reason='rule_validation_failed',
                    confidence_summary={
                        'ocr_confidence': ocr_result.overall_confidence,
                        'rule_validation': 'failed',
                        'rejection_type': 'clear_invalid',
                    },
                    flagged_reasons=rejection_reasons['reasons'],
                )

            # 1b. Only missing-field failures — apply PSU signal scoring.
            #     If no PSU/DHVSU signals are detected in the raw OCR text the
            #     document is not from PSU → REJECTED (invalid_institution).
            #     If PSU signals ARE present the document is likely a blurry or
            #     partial PSU ID → PENDING_MANUAL_REVIEW.
            has_psu_signal = self._has_psu_signal(ocr_result.raw_text)
            if not has_psu_signal:
                return Decision(
                    status='rejected',
                    reason='invalid_institution',
                    confidence_summary={
                        'ocr_confidence': ocr_result.overall_confidence,
                        'rule_validation': 'failed',
                        'rejection_type': 'no_psu_signal',
                    },
                    flagged_reasons=rejection_reasons['reasons'] + [
                        'No PSU/DHVSU institution signals detected in document',
                    ],
                )

            # PSU signals present but fields incomplete → manual review
            return Decision(
                status='pending_manual_review',
                reason='incomplete_extraction',
                confidence_summary={
                    'ocr_confidence': ocr_result.overall_confidence,
                    'rule_validation': 'incomplete',
                },
                flagged_reasons=rejection_reasons['reasons'],
            )

        # Step 2: Rules passed — check OCR confidence level
        ocr_confidence = ocr_result.overall_confidence

        if ocr_confidence >= self.OCR_CONFIDENCE_HIGH:
            return Decision(
                status='auto_approved',
                reason='high_confidence',
                confidence_summary={
                    'ocr_confidence': ocr_confidence,
                    'rule_validation': 'passed',
                    'threshold': self.OCR_CONFIDENCE_HIGH,
                },
                flagged_reasons=[],
            )

        if ocr_confidence >= self.OCR_CONFIDENCE_MEDIUM:
            flagged_reasons.append(f'OCR confidence medium ({ocr_confidence:.1f}%)')
            return Decision(
                status='pending_manual_review',
                reason='ocr_medium_confidence',
                confidence_summary={
                    'ocr_confidence': ocr_confidence,
                    'rule_validation': 'passed',
                    'threshold_high': self.OCR_CONFIDENCE_HIGH,
                    'threshold_medium': self.OCR_CONFIDENCE_MEDIUM,
                },
                flagged_reasons=flagged_reasons,
            )

        # Low confidence
        flagged_reasons.append(f'OCR confidence low ({ocr_confidence:.1f}%)')
        return Decision(
            status='pending_manual_review',
            reason='ocr_low_confidence',
            confidence_summary={
                'ocr_confidence': ocr_confidence,
                'rule_validation': 'passed',
                'threshold_medium': self.OCR_CONFIDENCE_MEDIUM,
            },
            flagged_reasons=flagged_reasons,
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _has_psu_signal(self, ocr_text: str) -> bool:
        """Return True if raw OCR text contains PSU/DHVSU institution signals.

        Scoring rules
        -------------
        - Any DISTINCTIVE keyword present  →  True  (strong signal)
        - Two or more SUPPORTIVE keywords  →  True  (weak-but-combined signal)
        - Otherwise                        →  False (no PSU signal)

        This is intentionally conservative: a single "psu" or "ccs" string is
        NOT sufficient because those abbreviations appear in other contexts.
        But "pampanga", "honorio", "ventura", or "dhvsu" are institution-
        specific and one occurrence is enough.

        Args:
            ocr_text: Raw OCR text string from Tesseract.

        Returns:
            True if the text plausibly originates from PSU/DHVSU.
        """
        if not ocr_text or not ocr_text.strip():
            return False

        text_lower = ocr_text.lower()

        # Check distinctive keywords — one is enough
        for kw in self._PSU_DISTINCTIVE_KEYWORDS:
            if kw in text_lower:
                return True

        # Check supportive keywords — require at least two
        supportive_count = sum(
            1 for kw in self._PSU_SUPPORTIVE_KEYWORDS if kw in text_lower
        )
        if supportive_count >= 2:
            return True

        return False

    def _analyze_rule_failures(self, failures: List[RuleFailure]) -> dict:
        """Analyse rule failures to determine rejection classification.

        Args:
            failures: List of RuleFailure objects from RuleValidator.

        Returns:
            Dict with:
              'clear_rejection' (bool) — True if an explicit wrong-value
                  failure was found (not just a missing-field failure).
              'reasons' (list[str]) — human-readable failure messages.
        """
        clear_rejection = False
        reasons: List[str] = []

        for failure in failures:
            if failure.reason == 'Institution not allowed':
                clear_rejection = True
                reasons.append(f'Invalid institution: {failure.actual}')

            elif failure.reason == 'College not allowed':
                clear_rejection = True
                reasons.append(f'Invalid college: {failure.actual}')

            elif failure.reason == 'Program not allowed':
                clear_rejection = True
                reasons.append(f'Invalid program: {failure.actual}')

            elif failure.reason == 'Required field is missing':
                reasons.append(f'Missing required field: {failure.field}')

        return {
            'clear_rejection': clear_rejection,
            'reasons': reasons,
        }
