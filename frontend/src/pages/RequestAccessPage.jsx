/**
 * RequestAccessPage — /request-access
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Phase 2 additions:
 *   - Progress stepper showing the 4-step account activation flow
 *   - Trust cue: "Only PampangaStateU CCS students can request access."
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, Search, TriangleAlert, ClipboardList, Lock } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import RequestAccessForm from '../components/auth/RequestAccessForm';
import LegalModal from '../components/legal/LegalModal';
import AuthBranding from '../components/brand/AuthBranding';

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
// step: 0 = form, 1 = email verification pending, 2 = manual review, -1 = rejected
function ProgressStepper({ step, isDark }) {
  const STEPS = [
    { label: 'Submit Request' },
    { label: 'Verify Email' },
    { label: 'Set Password' },
    { label: 'Account Ready' },
  ];

  // For manual review we show a special "Manual Review" active step instead of step 2
  const isManualReview = step === 2;
  const isRejected = step === -1;

  if (isRejected) return null; // no stepper for rejected

  const displaySteps = isManualReview
    ? [
        { label: 'Submit Request' },
        { label: 'Manual Review' },
        { label: 'Set Password' },
        { label: 'Account Ready' },
      ]
    : STEPS;

  // active index: 0 = form, 1 = email pending, 2 = manual review
  const activeIdx = step === 0 ? 0 : step === 1 ? 1 : step === 2 ? 1 : 0;
  const completedIdx = step === 0 ? -1 : 0; // step 0 (Submit) is complete once decision is shown

  return (
    <div className="mb-6">
      <div className="flex items-center gap-0">
        {displaySteps.map((s, i) => {
          const isComplete = i <= completedIdx;
          const isActive   = i === activeIdx + (step > 0 ? 1 : 0);
          const isFuture   = !isComplete && !isActive;

          return (
            <div key={s.label} className="flex items-center flex-1 min-w-0">
              {/* Node */}
              <div className="flex flex-col items-center flex-shrink-0">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  isComplete
                    ? isDark ? 'bg-emerald-500 border-emerald-500 text-white' : 'bg-emerald-500 border-emerald-500 text-white'
                    : isActive
                    ? isDark ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white'
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
                  {s.label}
                </span>
              </div>

              {/* Connector line (not after last) */}
              {i < displaySteps.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 mb-4 rounded-full transition-colors ${
                  i < activeIdx + (step > 0 ? 1 : 0)
                    ? isDark ? 'bg-emerald-500' : 'bg-emerald-500'
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
  const isDark = theme === 'dark';
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState('');
  const [decision, setDecision]   = useState(null);
  const [legalModal, setLegalModal] = useState(null); // 'privacy' | 'terms' | 'help' | null

  const handleSubmit = async (formData) => {
    setIsLoading(true);
    setError('');
    try {
      const res = await client.post('/auth/request-access/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDecision(res.data.decision || 'pending_manual_review');
    } catch (err) {
      setError(mapError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const cardBg = isDark
    ? 'bg-white/[0.03] border-white/10'
    : 'bg-white border-slate-200 shadow-card';

  const decisionInfo = decision ? (DECISIONS[decision] || {
    Icon: ClipboardList,
    iconColor: 'text-blue-600',
    title: 'Request Submitted',
    body: 'Your request has been submitted. An administrator will review it.',
    note: '', tone: 'neutral',
  }) : null;

  // Map decision → stepper step
  const stepperStep = decision === 'pending_email_verification' ? 1
    : decision === 'pending_manual_review' ? 2
    : decision === 'rejected' ? -1
    : 0;

  return (
    <div className="relative z-10 flex flex-1 items-start justify-center px-4 py-10">
      <div className="w-full max-w-lg">

        {/* Branding */}
        <AuthBranding subtitle={decision ? 'Request Status' : 'Request Access'} isDark={isDark} />

        {/* Progress stepper */}
        <ProgressStepper step={stepperStep} isDark={isDark} />

        {/* Card */}
        <div className={`rounded-2xl border p-6 sm:p-8 ${cardBg}`}>
          {decision ? (
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
                      <p className={`text-sm text-center ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        After clicking the verification link, you will receive a second email to set your password.
                      </p>
                    )}
                    {decision === 'rejected' && (
                      <button
                        type="button"
                        onClick={() => setDecision(null)}
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
              {/* Trust cue */}
              <p className={`text-xs mb-5 flex items-center gap-1.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                <Lock className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
                Only PampangaStateU CCS students can request access.
              </p>
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
