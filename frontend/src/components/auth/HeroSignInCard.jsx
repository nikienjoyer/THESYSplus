/**
 * HeroSignInCard — frosted sign-in form that sits on the landing hero photo,
 * spanning the CCS entrance pillars. LandingPage positions the wrapper; the
 * card keeps its natural height (stretching it left a gap above the button).
 *
 * Same validation and error wording as the /sign-in page (signInHelpers).
 * On success the auth state flips, LandingPage stops rendering the card, and
 * AnimatePresence plays its exit — the visitor stays on the landing page.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { m, useReducedMotion } from 'framer-motion';
import { Clock, X } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { EASE_OUT } from '../../lib/motion';
import Spinner from '../ui/Spinner';
import { EyeIcon, EyeOffIcon } from '../ui/Icon';
import { isInstitutionalEmail, mapSignInError } from './signInHelpers';

// Enter slides in from the right; exit leaves the way it came, shorter and
// with a hair of scale so it reads as "put away" rather than "jumped".
const cardMotion = {
  hidden:  { opacity: 0, transform: 'translateX(12px) scale(1)' },
  visible: { opacity: 1, transform: 'translateX(0px) scale(1)', transition: { duration: 0.22, ease: EASE_OUT } },
  exit:    { opacity: 0, transform: 'translateX(8px) scale(0.98)', transition: { duration: 0.16, ease: EASE_OUT } },
};
const cardMotionReduced = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.15 } },
  exit:    { opacity: 0, transition: { duration: 0.12 } },
};

export default function HeroSignInCard({ isDark, onClose, autoFocus = false, notice }) {
  const { signIn } = useAuth();
  const reduceMotion = useReducedMotion();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const validateEmail = (value) => {
    if (!value) { setEmailError(''); return false; }
    if (!isInstitutionalEmail(value)) { setEmailError('Please use your institutional email address.'); return false; }
    setEmailError('');
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateEmail(email) || !password) return;
    setIsLoading(true);
    setError('');
    try {
      await signIn(email, password, rememberMe);
    } catch (err) {
      setError(mapSignInError(err));
      setIsLoading(false);
    }
  };

  // Dark: navy glass with light text. Light: white glass with ink text.
  const surface = isDark
    ? 'bg-[rgba(10,16,40,0.55)] border-white/20 backdrop-blur-[14px] backdrop-saturate-[1.3]'
    : 'bg-white/60 border-white/80 backdrop-blur-[14px] backdrop-saturate-[1.3]';
  const heading = isDark ? 'text-white' : 'text-ink';
  const sub     = isDark ? 'text-slate-300' : 'text-body';
  const link    = isDark ? 'text-blue-200 hover:text-white' : 'text-primary hover:text-primary-solid-hover';
  const field   = isDark
    ? 'bg-slate-950/45 border-white/20 text-white placeholder-slate-300 focus:border-blue-400/70'
    : 'bg-white/90 border-gray-300 text-ink placeholder-gray-500 focus:border-blue-400';
  const fieldBase = `w-full h-[42px] rounded-[9px] border px-3.5 text-sm outline-none transition-[border-color] duration-150 focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60 ${field}`;

  return (
    <m.form
      onSubmit={handleSubmit}
      noValidate
      aria-label="Sign in"
      variants={reduceMotion ? cardMotionReduced : cardMotion}
      initial="hidden"
      animate="visible"
      exit="exit"
      className={`pointer-events-auto w-full hidden lg:flex flex-col rounded-[14px] border px-6 pt-5 pb-4 shadow-[0_18px_40px_-12px_rgba(2,6,23,0.6)] ${surface}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className={`text-xl font-bold tracking-tight ${heading}`}>Sign in</h2>
          {notice ? (
            <p role="status" className={`mt-1 flex items-center gap-1.5 text-[13px] ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
              <Clock className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
              {notice}
            </p>
          ) : (
            <p className={`mt-1 text-[13px] ${sub}`}>Use your PampangaStateU email.</p>
          )}
        </div>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close sign in"
            className={`-mr-2 -mt-1 w-8 h-8 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${isDark ? 'text-slate-300 hover:text-white hover:bg-white/10' : 'text-body hover:text-ink hover:bg-black/5'}`}>
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="mt-4">
        <label htmlFor="hero-sign-in-email" className="sr-only">Email</label>
        <input
          id="hero-sign-in-email"
          type="email"
          autoComplete="username"
          autoFocus={autoFocus}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => validateEmail(email)}
          placeholder="Email"
          disabled={isLoading}
          aria-invalid={!!emailError}
          aria-describedby={emailError ? 'hero-email-error' : undefined}
          className={fieldBase}
        />
        {emailError && (
          <p id="hero-email-error" className={`mt-1 text-xs ${isDark ? 'text-red-300' : 'text-danger'}`}>{emailError}</p>
        )}

        <label htmlFor="hero-sign-in-password" className="sr-only">Password</label>
        <div className="relative mt-2.5">
          <input
            id="hero-sign-in-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            disabled={isLoading}
            className={`${fieldBase} pr-10`}
          />
          <button type="button" onClick={() => setShowPassword(!showPassword)} disabled={isLoading}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className={`absolute right-3 max-sm:right-0.5 max-sm:p-2.5 top-1/2 -translate-y-1/2 focus:outline-none ${isDark ? 'text-slate-300 hover:text-white' : 'text-muted hover:text-ink'}`}>
            {showPassword ? <EyeOffIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="mt-3">
        <div className={`flex items-center justify-between text-[12.5px] ${isDark ? 'text-slate-200' : 'text-body'}`}>
          <label htmlFor="hero-sign-in-remember" className="flex items-center gap-2 cursor-pointer">
            <input id="hero-sign-in-remember" type="checkbox" checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)} disabled={isLoading}
              className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary" />
            Remember me
          </label>
          <Link to="/forgot-password" className={`font-medium ${link}`}>Forgot password?</Link>
        </div>

        {error && (
          <p role="alert" className={`mt-3 rounded-lg border px-3 py-2 text-xs ${isDark ? 'border-red-400/40 bg-red-950/50 text-red-200' : 'bg-danger-bg border-danger-border text-danger-text'}`}>
            {error}
          </p>
        )}
      </div>

      <div className="mt-4">
        <button type="submit" disabled={isLoading || !!emailError}
          className="w-full h-[42px] inline-flex items-center justify-center rounded-[9px] bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover transition-[background-color,transform] duration-150 ease-out active:scale-[0.97] disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
          {isLoading ? <><Spinner className="mr-2" />Signing in…</> : 'Sign in'}
        </button>
        <p className={`mt-3 text-center text-[12.5px] ${sub}`}>
          Don&rsquo;t have an account?{' '}
          <Link to="/request-access" className={`font-semibold ${link}`}>Request Access</Link>
        </p>
      </div>
    </m.form>
  );
}
