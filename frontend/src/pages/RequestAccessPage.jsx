/**
 * RequestAccessPage — /request-access
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Phase 2 additions:
 *   - Progress stepper showing the 4-step account activation flow
 *   - Trust cue: "Only PampangaStateU CCS students can request access."
 *
 * Claim polling:
 *   The backend hands this tab a "claim" at submission. This tab then polls
 *   GET /auth/request-access/status/ until the applicant clicks the emailed
 *   link in some other tab, at which point the poll returns a password-setup
 *   token and the user finishes signing up HERE — in the tab they started in.
 *
 *   The claim lives in sessionStorage (dies with the tab) so a reload re-enters
 *   the waiting state instead of showing a blank form. The setup token does NOT
 *   — it is short-lived and single-use, so it stays in component state only.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, Mail, Search, TriangleAlert, ClipboardList } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import RequestAccessForm from '../components/auth/RequestAccessForm';
import SetPasswordForm from '../components/auth/SetPasswordForm';
import LegalModal from '../components/legal/LegalModal';
import AuthBranding from '../components/brand/AuthBranding';

// sessionStorage, NOT localStorage: this holds a credential that can mint a
// password-setup token, and it must die with the tab.
const CLAIM_STORAGE_KEY = 'thesys.accessRequest.claim';

// Base cadence. The server's per-claim budget is 60/min, so ~15/min leaves
// generous headroom; the 429 branch below backs off if that ever changes.
const POLL_INTERVAL_MS = 4000;
const POLL_BACKOFF_CEILING_MS = 60000;

function readStoredClaim() {
  try {
    const raw = sessionStorage.getItem(CLAIM_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.decision) return null;
    return parsed;
  } catch {
    // Corrupt entry — treat as absent rather than trapping the user.
    return null;
  }
}

function writeStoredClaim(value) {
  try {
    sessionStorage.setItem(CLAIM_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Storage unavailable (private mode / quota). Polling still works for the
    // life of this render; only reload-survival is lost.
  }
}

function clearStoredClaim() {
  try {
    sessionStorage.removeItem(CLAIM_STORAGE_KEY);
  } catch {
    /* nothing to do */
  }
}

function mapError(err) {
  const code = err?.response?.data?.error?.code;
  const msg  = err?.response?.data?.error?.message;
  const map = {
    INVALID_EMAIL_DOMAIN:      'Use your PampangaStateU student-number email (e.g. 2023123456@pampangastateu.edu.ph).',
    EMAIL_ALREADY_REGISTERED:  'An account already exists for this email.',
    DUPLICATE_REQUEST_PENDING: 'A request for this email is already pending.',
    INVALID_REQUESTED_ROLE:    'Please choose Student or Faculty.',
    RATE_LIMITED_REQUEST_ACCESS: 'Too many requests. Please try again later.',
    FILE_VALIDATION_FAILED:    msg || 'Document validation failed. Please upload a valid file.',
    FILE_TOO_LARGE:            'File size must be less than 10 MB.',
    FILE_TYPE_NOT_ALLOWED:     'Please upload a PNG, JPG, or PDF file.',
  };
  return map[code] || msg || 'An error occurred. Please try again.';
}

const DECISIONS = {
  pending_email_verification: {
    Icon: Mail,
    iconColor: 'text-emerald-600',
    title: 'Check your PampangaStateU email',
    body: 'Your document was validated. We sent a verification link to your PampangaStateU institutional email. Please click the link to activate your account.',
    note: 'The link expires in 24 hours. Check your spam folder if you do not see it.',
    tone: 'success',
  },
  pending_manual_review: {
    Icon: Search,
    iconColor: 'text-amber-600',
    title: 'Your request needs manual review',
    body: 'Some details could not be verified automatically from your document. An administrator will review your request and contact you.',
    note: 'This usually happens when the document scan is unclear or details are partially readable.',
    tone: 'warning',
  },
  rejected: {
    Icon: TriangleAlert,
    iconColor: 'text-rose-600',
    title: 'We could not verify your PampangaStateU/CCS information',
    body: 'Your uploaded document does not show the required PampangaStateU and CCS/program information. Please ensure you upload a valid PampangaStateU Student ID or Certificate of Registration.',
    note: 'If you believe this is an error, contact the THESYS+ administrator.',
    tone: 'error',
  },
};

function toneClasses(tone, isDark) {
  const map = {
    success: isDark
      ? { wrap: 'bg-emerald-500/10 border-emerald-500/25', icon: 'bg-emerald-500/20', title: 'text-white', body: 'text-gray-300', note: 'text-gray-500' }
      : { wrap: 'bg-emerald-50 border-emerald-200', icon: 'bg-emerald-100', title: 'text-gray-900', body: 'text-gray-700', note: 'text-gray-500' },
    warning: isDark
      ? { wrap: 'bg-amber-500/10 border-amber-500/25', icon: 'bg-amber-500/20', title: 'text-white', body: 'text-gray-300', note: 'text-gray-500' }
      : { wrap: 'bg-amber-50 border-amber-200', icon: 'bg-amber-100', title: 'text-gray-900', body: 'text-gray-700', note: 'text-gray-500' },
    error: isDark
      ? { wrap: 'bg-rose-500/10 border-rose-500/25', icon: 'bg-rose-500/20', title: 'text-white', body: 'text-gray-300', note: 'text-gray-500' }
      : { wrap: 'bg-rose-50 border-rose-200', icon: 'bg-rose-100', title: 'text-gray-900', body: 'text-gray-700', note: 'text-gray-500' },
    neutral: isDark
      ? { wrap: 'bg-blue-500/10 border-blue-500/20', icon: 'bg-blue-500/20', title: 'text-white', body: 'text-gray-300', note: 'text-gray-500' }
      : { wrap: 'bg-blue-50 border-blue-200', icon: 'bg-blue-100', title: 'text-gray-900', body: 'text-gray-700', note: 'text-gray-500' },
  };
  return map[tone] || map.neutral;
}

// ---------------------------------------------------------------------------
// Progress stepper
// ---------------------------------------------------------------------------
//
// Named steps rather than bare integers, because the mapping from flow state to
// highlighted node is not 1:1 — manual review reuses node index 1 under a
// different label.
const STEP_REJECTED       = -1;
const STEP_FORM           = 0;
const STEP_VERIFY_EMAIL   = 1;
const STEP_MANUAL_REVIEW  = 2;
const STEP_SET_PASSWORD   = 3;
const STEP_ACCOUNT_READY  = 4;

// Which of the four rendered nodes each flow step highlights.
const STEP_TO_NODE = {
  [STEP_FORM]:          0,
  [STEP_VERIFY_EMAIL]:  1,
  [STEP_MANUAL_REVIEW]: 1,   // same node, relabelled below
  [STEP_SET_PASSWORD]:  2,
  [STEP_ACCOUNT_READY]: 3,
};

function ProgressStepper({ step, isDark }) {
  if (step === STEP_REJECTED) return null; // no stepper for rejected

  const isManualReview = step === STEP_MANUAL_REVIEW;

  // Manual review replaces "Verify Email" — no email was sent, so waiting for
  // one would be a lie. Pre-existing behaviour, preserved.
  const displaySteps = isManualReview
    ? ['Submit Request', 'Manual Review', 'Set Password', 'Account Ready']
    : ['Submit Request', 'Verify Email', 'Set Password', 'Account Ready'];

  // NOTE — this replaces an off-by-one in the previous implementation, which
  // computed `activeIdx + (step > 0 ? 1 : 0)` and so highlighted "Set Password"
  // while the applicant was still waiting to verify their email (and again
  // during manual review). It had to change: advancing the stepper to Set
  // Password would otherwise be invisible, since the highlight was already
  // sitting there.
  const activeNode = STEP_TO_NODE[step] ?? 0;

  // Account Ready is terminal, so its own node reads as complete too.
  const isTerminal = step === STEP_ACCOUNT_READY;

  return (
    <div className="mb-6">
      <div className="flex items-center gap-0">
        {displaySteps.map((label, i) => {
          const isComplete = i < activeNode || (isTerminal && i === activeNode);
          const isActive   = i === activeNode && !isTerminal;

          return (
            <div key={label} className="flex items-center flex-1 min-w-0">
              {/* Node */}
              <div className="flex flex-col items-center flex-shrink-0">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  isComplete
                    ? 'bg-emerald-500 border-emerald-500 text-white'
                    : isActive
                    ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white'
                    : isDark ? 'bg-transparent border-white/20 text-gray-600' : 'bg-transparent border-gray-200 text-gray-400'
                }`}>
                  {isComplete ? (
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <span className={`text-[9px] mt-1 text-center leading-tight max-w-[52px] ${
                  isComplete
                    ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                    : isActive
                    ? 'text-primary font-semibold'
                    : isDark ? 'text-gray-600' : 'text-gray-400'
                }`}>
                  {label}
                </span>
              </div>

              {/* Connector line (not after last) */}
              {i < displaySteps.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 mb-4 rounded-full transition-colors ${
                  i < activeNode
                    ? 'bg-emerald-500'
                    : isDark ? 'bg-white/10' : 'bg-gray-200'
                }`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function RequestAccessPage() {
  const { theme } = useTheme();
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState('');
  const [legalModal, setLegalModal] = useState(null); // 'privacy' | 'terms' | 'help' | null

  // Restored lazily from sessionStorage so a reload re-enters the waiting state
  // rather than showing an empty form. Lazy initialisers (not an effect) keep
  // this out of the setState-in-effect lint category.
  const [decision, setDecision] = useState(() => readStoredClaim()?.decision ?? null);
  const [claim, setClaim] = useState(() => readStoredClaim()?.claim ?? '');
  const [claimExpiresAt, setClaimExpiresAt] = useState(
    () => readStoredClaim()?.claim_expires_at ?? '',
  );

  // 'polling' | 'verified' | 'account_ready' | 'already_active' | 'expired'
  const [claimState, setClaimState] = useState('polling');

  // Deliberately component state, never storage — short-lived and single-use.
  const [setupToken, setSetupToken] = useState('');

  const handleSubmit = async (formData) => {
    setIsLoading(true);
    setError('');
    try {
      const res = await client.post('/auth/request-access/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      // Legacy branch answers 201, document-upload branch 202 — both carry the
      // same claim fields, so read them from whichever fired.
      const nextDecision = res.data?.decision || 'pending_manual_review';
      const nextClaim = res.data?.claim || '';
      const nextExpiry = res.data?.claim_expires_at || '';

      setDecision(nextDecision);
      setClaim(nextClaim);
      setClaimExpiresAt(nextExpiry);
      setClaimState('polling');
      writeStoredClaim({
        decision: nextDecision,
        claim: nextClaim,
        claim_expires_at: nextExpiry,
      });
    } catch (err) {
      setError(mapError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleTryAgain = () => {
    clearStoredClaim();
    setDecision(null);
    setClaim('');
    setClaimExpiresAt('');
    setClaimState('polling');
    setSetupToken('');
  };

  const handlePasswordSet = useCallback(() => {
    // The account is live now; the claim must not linger.
    clearStoredClaim();
    setSetupToken('');
    setClaimState('account_ready');
  }, []);

  // ── Claim polling ─────────────────────────────────────────────────────
  //
  // Only 'pending_email_verification' is pollable. 'pending_manual_review' has
  // no email in flight and 'rejected' is terminal, so polling either would be
  // pure noise against the server.
  const shouldPoll = (
    decision === 'pending_email_verification'
    && claimState === 'polling'
    && !!claim
    && !!claimExpiresAt
  );

  const inFlightRef = useRef(false);

  useEffect(() => {
    if (!shouldPoll) return undefined;

    let cancelled = false;
    let timerId = null;
    let intervalMs = POLL_INTERVAL_MS;

    // Absolute instant published by the server. Never a hardcoded 30 minutes —
    // the window can change server-side without this file drifting.
    const expiresAtMs = new Date(claimExpiresAt).getTime();

    const stopWith = (nextState) => {
      clearStoredClaim();
      setClaimState(nextState);
    };

    const schedule = () => {
      if (cancelled) return;
      timerId = setTimeout(tick, intervalMs);
    };

    const tick = async () => {
      if (cancelled || inFlightRef.current) return;

      if (Number.isFinite(expiresAtMs) && Date.now() >= expiresAtMs) {
        stopWith('expired');
        return;
      }

      // Pause entirely while backgrounded — otherwise a forgotten tab keeps
      // requesting for the whole 30-minute window.
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        schedule();
        return;
      }

      inFlightRef.current = true;
      try {
        const res = await client.get('/auth/request-access/status/', {
          params: { claim },
        });
        if (cancelled) return;

        const status = res.data?.status;
        if (status === 'verified') {
          setSetupToken(res.data?.setup_token || '');
          setClaimState('verified');
          // Storage is intentionally retained here: if the user reloads before
          // submitting a password, the restored claim lets the next poll mint a
          // fresh setup token. It is cleared on success instead.
          return;
        }
        if (status === 'already_active') { stopWith('already_active'); return; }
        if (status === 'expired')        { stopWith('expired'); return; }

        // pending_verification — reset any backoff and keep waiting.
        intervalMs = POLL_INTERVAL_MS;
        schedule();
      } catch (err) {
        if (cancelled) return;

        const code = err?.response?.data?.error?.code;
        const httpStatus = err?.response?.status;

        // A claim the server no longer recognises is, from here, the same
        // situation as an expired one.
        if (httpStatus === 404 || code === 'CLAIM_NOT_FOUND') {
          stopWith('expired');
          return;
        }

        // Safety valve only — the budget is 60/min against a ~15/min cadence.
        // Back off rather than surfacing an error the user cannot act on.
        if (httpStatus === 429 || code === 'RATE_LIMITED_CLAIM_STATUS') {
          intervalMs = Math.min(intervalMs * 2, POLL_BACKOFF_CEILING_MS);
          schedule();
          return;
        }

        // Network blip: stay silent and keep waiting. Tearing down the waiting
        // state over one dropped request would look like the submission failed.
        schedule();
      } finally {
        inFlightRef.current = false;
      }
    };

    const onVisibilityChange = () => {
      if (cancelled) return;
      if (document.visibilityState === 'visible') {
        // Resume immediately rather than waiting out the remaining interval.
        if (timerId) clearTimeout(timerId);
        tick();
      }
    };

    // Poll once straight away — covers the reload-after-verification case,
    // where the answer is already waiting.
    tick();
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [shouldPoll, claim, claimExpiresAt]);

  const decisionInfo = decision ? (DECISIONS[decision] || {
    Icon: ClipboardList,
    iconColor: 'text-blue-600',
    title: 'Request Submitted',
    body: 'Your request has been submitted. An administrator will review it.',
    note: '', tone: 'neutral',
  }) : null;

  // Map flow state → stepper step. Claim outcomes take precedence over the
  // original decision, since they describe where the user actually is now.
  let stepperStep;
  if (claimState === 'account_ready' || claimState === 'already_active') {
    stepperStep = STEP_ACCOUNT_READY;
  } else if (claimState === 'verified') {
    stepperStep = STEP_SET_PASSWORD;
  } else if (decision === 'pending_email_verification') {
    stepperStep = STEP_VERIFY_EMAIL;
  } else if (decision === 'pending_manual_review') {
    stepperStep = STEP_MANUAL_REVIEW;
  } else if (decision === 'rejected') {
    stepperStep = STEP_REJECTED;
  } else {
    stepperStep = STEP_FORM;
  }

  const cardBg = isDark
    ? 'bg-white/[0.03] border-white/10'
    : 'bg-white border-slate-200 shadow-card';

  const showPanel = (
    claimState === 'verified'
    || claimState === 'account_ready'
    || claimState === 'already_active'
    || claimState === 'expired'
  );

  const subtitle = claimState === 'verified' ? 'Set Password'
    : claimState === 'account_ready' ? 'Account Ready'
    : decision ? 'Request Status'
    : 'Request Access';

  return (
    <div className="relative z-10 flex flex-1 items-start justify-center px-4 py-10">
      <div className="w-full max-w-lg">

        {/* Branding */}
        <AuthBranding subtitle={subtitle} isDark={isDark} />

        {/* Progress stepper */}
        <ProgressStepper step={stepperStep} isDark={isDark} />

        <div>
          {showPanel ? (
            /* ── Claim outcome panels ── */
            <div className={`rounded-2xl border p-7 sm:p-9 ${cardBg}`}>
              {claimState === 'verified' && (
                <SetPasswordForm
                  setupToken={setupToken}
                  onSuccess={handlePasswordSet}
                  isDark={isDark}
                  idPrefix="ra"
                />
              )}

              {claimState === 'account_ready' && (
                <div className="text-center">
                  <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                    isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
                  }`}>
                    <CheckCircle2 className="w-7 h-7 text-emerald-500" aria-hidden="true" />
                  </div>
                  <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    Account Ready
                  </h2>
                  <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Your password has been set and your THESYS+ account is now active.
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate('/sign-in?reason=account_setup')}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                    Go to Sign In
                  </button>
                </div>
              )}

              {claimState === 'already_active' && (
                <div className="text-center">
                  <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                    isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
                  }`}>
                    <CheckCircle2 className="w-7 h-7 text-emerald-500" aria-hidden="true" />
                  </div>
                  <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    This account is already active.
                  </h2>
                  <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Your password has already been set, so there is nothing left to do here.
                  </p>
                  <Link to="/sign-in"
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                    Sign In
                  </Link>
                </div>
              )}

              {claimState === 'expired' && (
                <div className="text-center">
                  <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                    isDark ? 'bg-amber-500/15' : 'bg-amber-50'
                  }`}>
                    <Mail className="w-7 h-7 text-amber-500" aria-hidden="true" />
                  </div>
                  <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    Still waiting on your email
                  </h2>
                  {/* Deliberately NOT "session expired, start again": the access
                      request and the 24-hour email link are both still valid, and
                      telling the user to resubmit would mean re-uploading their ID
                      document for nothing. */}
                  <p className={`text-sm mb-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    This page stopped waiting for your verification. If you&apos;ve already
                    clicked the link in your email, you can sign in now. If not, the link
                    is still valid — click it and follow the instructions there.
                  </p>
                  <Link to="/sign-in"
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                    Sign In
                  </Link>
                </div>
              )}
            </div>
          ) : decision ? (
            /* ── Decision result ── */
            (() => {
              const cls = toneClasses(decisionInfo.tone, isDark);
              return (
                <div>
                  <div className={`rounded-xl border p-5 mb-6 ${cls.wrap}`}>
                    <div className="flex items-start gap-4">
                      <div className={`w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0 ${cls.icon}`}>
                        {decisionInfo.Icon && <decisionInfo.Icon className={`w-5 h-5 ${decisionInfo.iconColor}`} aria-hidden="true" />}
                      </div>
                      <div>
                        <h2 className={`font-bold text-base mb-1 ${cls.title}`}>{decisionInfo.title}</h2>
                        <p className={`text-sm ${cls.body}`}>{decisionInfo.body}</p>
                        {decisionInfo.note && (
                          <p className={`text-xs mt-2 ${cls.note}`}>{decisionInfo.note}</p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col items-center gap-2">
                    {decision === 'pending_email_verification' && (
                      <p
                        aria-live="polite"
                        className={`text-sm text-center ${isDark ? 'text-gray-400' : 'text-gray-600'}`}
                      >
                        Click the link in your email to verify your address. This page
                        will continue automatically once you do.
                      </p>
                    )}
                    {decision === 'rejected' && (
                      <button
                        type="button"
                        onClick={handleTryAgain}
                        className="px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
                      >
                        Try Again
                      </button>
                    )}
                    <Link to="/sign-in"
                      className={`text-sm mt-1 ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'}`}>
                      Return to Sign In
                    </Link>
                  </div>
                </div>
              );
            })()
          ) : (
            /* ── Form ── */
            <>
              <h2 className={`text-lg font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Request Account Access
              </h2>
              <RequestAccessForm
                onSubmit={handleSubmit}
                error={error}
                isLoading={isLoading}
                isDark={isDark}
                onOpenLegal={setLegalModal}
              />
            </>
          )}
        </div>

        {/* Footer links */}
        {!decision && (
          <div className="mt-5 text-center">
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              Already have an account?{' '}
              <Link to="/sign-in" className="font-medium hover:underline text-primary">
                Sign In
              </Link>
            </p>
          </div>
        )}
      </div>

      {/* Legal Modal */}
      <LegalModal
        isOpen={legalModal !== null}
        onClose={() => setLegalModal(null)}
        type={legalModal}
        isDark={isDark}
      />
    </div>
  );
}
