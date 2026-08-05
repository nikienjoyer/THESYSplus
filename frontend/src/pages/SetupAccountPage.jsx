/**
 * SetupAccountPage — /setup-account?token=<plaintext>
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Landed on from the single "Welcome to THESYS+ - Set Up Your Account"
 * email sent when an administrator approves an access request.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AuthBranding from '../components/brand/AuthBranding';

function validateStrength(pw) {
  if (pw.length < 12)         return 'Password must be at least 12 characters.';
  if (!/[a-zA-Z]/.test(pw))  return 'Password must include at least one letter.';
  if (!/[0-9]/.test(pw))     return 'Password must include at least one digit.';
  return '';
}

function mapError(err) {
  const code = err?.response?.data?.error?.code;
  const msg  = err?.response?.data?.error?.message;
  if (code === 'INVALID_RESET_TOKEN') return '__INVALID_TOKEN__';
  if (code === 'WEAK_PASSWORD')       return 'Password must be at least 12 characters and include both letters and digits.';
  if (code === 'RATE_LIMITED_IP' || code === 'RATE_LIMITED_RESET_PASSWORD') return 'Too many requests. Please try again later.';
  return msg || 'An error occurred. Please try again.';
}

function EyeIcon({ off }) {
  return off ? (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"/>
    </svg>
  ) : (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
    </svg>
  );
}

export default function SetupAccountPage() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPw, setNewPw]               = useState('');
  const [confirmPw, setConfirmPw]       = useState('');
  const [showNew, setShowNew]           = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);
  const [newErr, setNewErr]             = useState('');
  const [confirmErr, setConfirmErr]     = useState('');
  const [serverErr, setServerErr]       = useState('');
  const [invalidToken, setInvalidToken] = useState(!token);
  const [isLoading, setIsLoading]       = useState(false);

  useEffect(() => { if (!token) setInvalidToken(true); }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const strengthErr = validateStrength(newPw);
    if (strengthErr) { setNewErr(strengthErr); return; }
    if (newPw !== confirmPw) { setConfirmErr('Passwords do not match.'); return; }
    setIsLoading(true);
    setServerErr('');
    try {
      await client.post('/auth/setup-password/', { token, new_password: newPw });
      navigate('/sign-in?reason=account_setup');
    } catch (err) {
      const mapped = mapError(err);
      if (mapped === '__INVALID_TOKEN__') setInvalidToken(true);
      else setServerErr(mapped);
    } finally {
      setIsLoading(false);
    }
  };

  const cardBg   = isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200 shadow-sm';
  const inputCls = (hasErr) => `w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors pr-11 ${
    isDark
      ? `bg-white/[0.04] text-gray-200 placeholder-gray-500 focus:border-blue-500/40 ${hasErr ? 'border-rose-500/50' : 'border-white/10'}`
      : `bg-white text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 ${hasErr ? 'border-rose-400' : 'border-gray-200'}`
  }`;
  const eyeCls   = `absolute right-3 top-1/2 -translate-y-1/2 transition-colors focus:outline-none ${
    isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'
  }`;
  const labelCls = `block text-sm font-medium mb-1.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`;
  const errCls   = `text-xs mt-1 ${isDark ? 'text-rose-400' : 'text-rose-600'}`;
  const hintCls  = `text-xs mt-1 ${isDark ? 'text-gray-600' : 'text-gray-400'}`;

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <AuthBranding subtitle="Create a secure password to activate your THESYS+ account." isDark={isDark} />

        <div className={`rounded-2xl border p-6 sm:p-8 ${cardBg}`}>
          {invalidToken ? (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                isDark ? 'bg-rose-500/15' : 'bg-rose-50'
              }`}>
                <TriangleAlert className="w-7 h-7 text-rose-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Link invalid or expired
              </h2>
              <p className={`text-sm mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                This account setup link is invalid or has expired.
              </p>
              <p className={`text-xs mb-6 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Setup links expire after 30 minutes. Use "Forgot your password?" on the sign-in
                page to request a new one.
              </p>
              <Link to="/forgot-password"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                Request New Link
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate>
              <h2 className={`text-xl font-bold mb-5 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Set Up Your Password
              </h2>

              {/* New password */}
              <div className="mb-4">
                <label htmlFor="sa-new" className={labelCls}>New Password</label>
                <div className="relative">
                  <input id="sa-new"
                    type={showNew ? 'text' : 'password'}
                    value={newPw}
                    onChange={e => { setNewPw(e.target.value); if (newErr) setNewErr(''); }}
                    onBlur={() => { if (newPw) setNewErr(validateStrength(newPw)); }}
                    placeholder="Enter new password"
                    disabled={isLoading} required aria-invalid={!!newErr}
                    className={inputCls(!!newErr)}
                  />
                  <button type="button" tabIndex={-1} onClick={() => setShowNew(v => !v)}
                    className={eyeCls} aria-label={showNew ? 'Hide password' : 'Show password'}>
                    <EyeIcon off={showNew} />
                  </button>
                </div>
                {newErr
                  ? <p className={errCls}>{newErr}</p>
                  : <p className={hintCls}>At least 12 characters, including letters and digits.</p>
                }
              </div>

              {/* Confirm password */}
              <div className="mb-5">
                <label htmlFor="sa-confirm" className={labelCls}>Confirm Password</label>
                <div className="relative">
                  <input id="sa-confirm"
                    type={showConfirm ? 'text' : 'password'}
                    value={confirmPw}
                    onChange={e => { setConfirmPw(e.target.value); if (confirmErr) setConfirmErr(''); }}
                    onBlur={() => { if (confirmPw && confirmPw !== newPw) setConfirmErr('Passwords do not match.'); }}
                    placeholder="Confirm new password"
                    disabled={isLoading} required aria-invalid={!!confirmErr}
                    className={inputCls(!!confirmErr)}
                  />
                  <button type="button" tabIndex={-1} onClick={() => setShowConfirm(v => !v)}
                    className={eyeCls} aria-label={showConfirm ? 'Hide password' : 'Show password'}>
                    <EyeIcon off={showConfirm} />
                  </button>
                </div>
                {confirmErr && <p className={errCls}>{confirmErr}</p>}
              </div>

              {serverErr && (
                <div className={`rounded-lg border px-4 py-3 text-sm mb-4 ${
                  isDark ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' : 'bg-rose-50 border-rose-200 text-rose-700'
                }`}>
                  {serverErr}
                </div>
              )}

              <button type="submit"
                disabled={isLoading || !!newErr || !!confirmErr || !newPw || !confirmPw}
                className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Spinner size="sm" /> Activating…</> : 'Set Up Password'}
              </button>
            </form>
          )}
        </div>

        {!invalidToken && (
          <p className={`mt-5 text-center text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            Already activated your account?{' '}
            <Link to="/sign-in" className="font-medium hover:underline text-primary">
              Sign In
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
