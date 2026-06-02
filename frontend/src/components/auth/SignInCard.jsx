/**
 * SignInCard — Sign-in form component with email, password, and remember-me.
 * 
 * Features:
 * - Email + password fields with proper labels (Requirement 17.3)
 * - Password visibility toggle (eye icon)
 * - Remember-me checkbox
 * - Submit button
 * - Inline error region with role="alert" (Requirement 17.5)
 * - Client-side institutional email validation on blur and submit
 * - Uses UI primitives from src/components/ui/
 * 
 * Requirements: 1.4, 4.1, 13.1, 13.2, 17.3, 17.5
 */

import { useState } from 'react';
import Input from '../ui/Input';
import Button from '../ui/Button';
import Checkbox from '../ui/Checkbox';
import Alert from '../ui/Alert';
import Spinner from '../ui/Spinner';
import { EyeIcon, EyeOffIcon } from '../ui/Icon';

/**
 * Validates institutional email (pampangastateu.edu.ph apex + subdomains)
 * Regex: ^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$
 */
function isInstitutionalEmail(email) {
  const regex = /^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$/i;
  return regex.test(email);
}

export default function SignInCard({ onSubmit, error, isLoading }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const validateEmail = (value) => {
    if (!value) {
      setEmailError('');
      return false;
    }
    if (!isInstitutionalEmail(value)) {
      setEmailError('Please use your institutional email address.');
      return false;
    }
    setEmailError('');
    return true;
  };

  const handleEmailBlur = () => {
    validateEmail(email);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Client-side validation
    const isEmailValid = validateEmail(email);
    if (!isEmailValid) {
      return;
    }

    if (!password) {
      return;
    }

    onSubmit({ email, password, rememberMe });
  };

  return (
    <div className="w-full max-w-md mx-auto p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6 text-center text-gray-900 dark:text-white">
        Welcome!
      </h2>

      <form onSubmit={handleSubmit} noValidate>
        {/* Email field */}
        <div className="mb-4">
          <label
            htmlFor="sign-in-email"
            className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300"
          >
            Email
          </label>
          <Input
            id="sign-in-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={handleEmailBlur}
            placeholder="2012345678@pampangastateu.edu.ph"
            disabled={isLoading}
            required
            aria-invalid={!!emailError}
            aria-describedby={emailError ? 'email-error' : undefined}
          />
          {emailError && (
            <p id="email-error" className="mt-1 text-sm text-red-600 dark:text-red-400">
              {emailError}
            </p>
          )}
        </div>

        {/* Password field */}
        <div className="mb-4">
          <label
            htmlFor="sign-in-password"
            className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300"
          >
            Password
          </label>
          <div className="relative">
            <Input
              id="sign-in-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              disabled={isLoading}
              required
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 focus:outline-none"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              disabled={isLoading}
            >
              {showPassword ? (
                <EyeOffIcon className="w-5 h-5" />
              ) : (
                <EyeIcon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        {/* Remember me checkbox */}
        <div className="mb-4 flex items-center">
          <Checkbox
            id="sign-in-remember-me"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            disabled={isLoading}
          />
          <label
            htmlFor="sign-in-remember-me"
            className="ml-2 text-sm text-gray-700 dark:text-gray-300"
          >
            Remember me
          </label>
        </div>

        {/* Error alert */}
        {error && (
          <Alert className="mb-4 bg-red-50 border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
            {error}
          </Alert>
        )}

        {/* Submit button */}
        <Button
          type="submit"
          className="w-full mb-4"
          disabled={isLoading || !!emailError}
        >
          {isLoading ? (
            <span className="flex items-center justify-center">
              <Spinner className="mr-2" />
              Signing in...
            </span>
          ) : (
            'Sign In'
          )}
        </Button>
      </form>
    </div>
  );
}
