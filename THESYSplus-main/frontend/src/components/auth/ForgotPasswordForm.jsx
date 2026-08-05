/**
 * ForgotPasswordForm — Forgot password form component
 * 
 * Features:
 * - Email field with institutional validation
 * - Submit button with loading state
 * - Inline error display
 * 
 * Requirements: 5.1, 5.2, 15.1, 15.2
 */

import { useState } from 'react';
import Input from '../ui/Input';
import Button from '../ui/Button';
import Alert from '../ui/Alert';
import Spinner from '../ui/Spinner';

/**
 * Validates institutional email (pampangastateu.edu.ph apex + subdomains)
 */
function isInstitutionalEmail(email) {
  const regex = /^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$/i;
  return regex.test(email);
}

export default function ForgotPasswordForm({ onSubmit, error, isLoading }) {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');

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

    onSubmit({ email });
  };

  return (
    <div className="w-full max-w-md mx-auto p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-2 text-center text-gray-900 dark:text-white">
        Forgot Password
      </h2>
      <p className="text-sm text-gray-600 dark:text-gray-400 text-center mb-6">
        Enter your email address and we'll send you a link to reset your password.
      </p>

      <form onSubmit={handleSubmit} noValidate>
        {/* Email field */}
        <div className="mb-4">
          <label
            htmlFor="forgot-password-email"
            className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300"
          >
            Email
          </label>
          <Input
            id="forgot-password-email"
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

        {/* Error alert */}
        {error && (
          <Alert className="mb-4 bg-red-50 border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
            {error}
          </Alert>
        )}

        {/* Submit button */}
        <Button
          type="submit"
          className="w-full"
          disabled={isLoading || !!emailError}
        >
          {isLoading ? (
            <span className="flex items-center justify-center">
              <Spinner className="mr-2" />
              Sending...
            </span>
          ) : (
            'Send Reset Link'
          )}
        </Button>
      </form>
    </div>
  );
}
