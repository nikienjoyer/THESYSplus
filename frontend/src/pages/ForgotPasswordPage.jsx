/**
 * ForgotPasswordPage — /forgot-password
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Requirements: 5.1, 5.2, 15.1, 15.2
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';

const INSTITUTIONAL_EMAIL_RE = /^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$/i;

function mapError(err) {
  const code = err?.response?.data?.error?.code;
  const msg  = err?.response?.data?.error?.message;
  if (code === 'INVALID_EMAIL_DOMAIN')          return 'Please use your institutional email address.';
  if (code === 'RATE_LIMITED_FORGOT_PASSWORD')  return 'Too many requests. Please try again later.';
  return msg || 'An error occurred. Please try again.';
}

export default function ForgotPasswordPage() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const [email, setEmail]         = useState('');
  const [emailErr, setEmailErr]   = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState('');
  const [success, setSuccess]     = useState(false);

  const validateEmail = (v) => {
    if (v && !INSTITUTIONAL_EMAIL_RE.test(v.trim())) {
      setEmailErr('Please use your institutional email address.');
      return false;
    }
    setEmailErr('');
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateEmail(email)) return;
    setIsLoading(true);
    setError('');
    try {
      await client.post('/auth/forgot-password/', { email: email.trim().toLowerCase() });
      setSuccess(true);
    } catch (err) {
      setError(mapError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const cardBg  = isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200 shadow-sm';
  const inputCls = `w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
    isDark
      ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
      : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
  }`;

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <div className="flex flex-col items-center mb-8 select-none">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4 ${
            isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
          }`}>🎓</div>
          <h1 className="text-3xl font-extrabold tracking-tighter leading-none mb-1">
            <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
            <span className={isDark ? 'text-blue-400' : 'text-blue-600'}>SYS+</span>
          </h1>
          <p className={`text-xs tracking-widest uppercase font-medium mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            {success ? 'Check your email' : 'Forgot your password?'}
          </p>
        </div>

        <div className={`rounded-2xl border p-6 sm:p-8 ${cardBg}`}>
          {success ? (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center text-3xl mx-auto mb-4 ${
                isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
              }`}>✉️</div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Reset link sent
              </h2>
              <p className={`text-sm mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                If an account exists for that email, a password reset link has been sent.
              </p>
              <p className={`text-xs mb-6 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                The link expires in 30 minutes. Check your spam folder if you don't see it.
              </p>
              <Link to="/sign-in"
                className={`text-sm font-medium hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                Return to Sign In
              </Link>
            </div>
          ) : (
            <>
              <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Enter your institutional email and we'll send you a link to reset your password.
              </p>
              {/* Security trust cue */}
              <p className={`text-xs mb-4 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                🔒 For security, password reset links expire after 30 minutes.
              </p>
              <form onSubmit={handleSubmit} noValidate>
                <div className="mb-4">
                  <label htmlFor="fp-email"
                    className={`block text-sm font-medium mb-1.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    Institutional Email
                  </label>
                  <input
                    id="fp-email" type="email" required
                    value={email}
                    onChange={e => { setEmail(e.target.value); if (emailErr) setEmailErr(''); }}
                    onBlur={() => validateEmail(email)}
                    placeholder="2012345678@pampangastateu.edu.ph"
                    disabled={isLoading}
                    aria-invalid={!!emailErr}
                    className={`${inputCls} ${emailErr ? (isDark ? 'border-rose-500/50' : 'border-rose-400') : ''}`}
                  />
                  {emailErr && (
                    <p className={`text-xs mt-1 ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{emailErr}</p>
                  )}
                </div>

                {error && (
                  <div className={`rounded-lg border px-4 py-3 text-sm mb-4 ${
                    isDark ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' : 'bg-rose-50 border-rose-200 text-rose-700'
                  }`}>
                    {error}
                  </div>
                )}

                <button type="submit" disabled={isLoading || !!emailErr || !email}
                  className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                  {isLoading ? <><Spinner size="sm" /> Sending…</> : 'Send Reset Link'}
                </button>
              </form>
            </>
          )}
        </div>

        {/* Footer */}
        {!success && (
          <p className={`mt-5 text-center text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            Remember your password?{' '}
            <Link to="/sign-in" className={`font-medium hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
              Sign In
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
