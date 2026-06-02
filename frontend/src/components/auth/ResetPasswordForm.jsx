/**
 * ResetPasswordForm — Reset password form component
 * 
 * Features:
 * - New password field with visibility toggle
 * - Confirm password field with visibility toggle
 * - Client-side password strength validation (≥12 chars, ≥1 letter, ≥1 digit)
 * - Password match validation
 * - Submit button with loading state
 * - Inline error display
 * 
 * Requirements: 5.3, 5.4, 5.5, 15.3, 15.4
 */

import { useState } from 'react';
import Input from '../ui/Input';
import Button from '../ui/Button';
import Alert from '../ui/Alert';
import Spinner from '../ui/Spinner';
import { EyeIcon, EyeOffIcon } from '../ui/Icon';

/**
 * Validates password strength (≥12 chars, ≥1 letter, ≥1 digit)
 */
function validatePasswordStrength(password) {
  if (password.length < 12) {
    return 'Password must be at least 12 characters.';
  }
  if (!/[a-zA-Z]/.test(password)) {
    return 'Password must include at least one letter.';
  }
  if (!/[0-9]/.test(password)) {
    return 'Password must include at least one digit.';
  }
  return '';
}

export default function ResetPasswordForm({ onSubmit, error, isLoading }) {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [newPasswordError, setNewPasswordError] = useState('');
  const [confirmPasswordError, setConfirmPasswordError] = useState('');

  const validateNewPassword = (value) => {
    if (!value) {
      setNewPasswordError('');
      return false;
    }
    const error = validatePasswordStrength(value);
    setNewPasswordError(error);
    return !error;
  };

  const validateConfirmPassword = (value) => {
    if (!value) {
      setConfirmPasswordError('');
      return false;
    }
    if (value !== newPassword) {
      setConfirmPasswordError('Passwords do not match.');
      return false;
    }
    setConfirmPasswordError('');
    return true;
  };

  const handleNewPasswordBlur = () => {
    if (newPassword) {
      validateNewPassword(newPassword);
    }
  };

  const handleConfirmPasswordBlur = () => {
    if (confirmPassword) {
      validateConfirmPassword(confirmPassword);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Client-side validation
    const isNewPasswordValid = validateNewPassword(newPassword);
    const isConfirmPasswordValid = validateConfirmPassword(confirmPassword);
    
    if (!isNewPasswordValid || !isConfirmPasswordValid) {
      return;
    }

    onSubmit({ new_password: newPassword });
  };

  return (
    <div className="w-full max-w-md mx-auto p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-2 text-center text-gray-900 dark:text-white">
        Reset Password
      </h2>
      <p className="text-sm text-gray-600 dark:text-gray-400 text-center mb-6">
        Enter your new password below.
      </p>

      <form onSubmit={handleSubmit} noValidate>
        {/* New Password field */}
        <div className="mb-4">
          <label
            htmlFor="reset-password-new"
            className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300"
          >
            New Password
          </label>
          <div className="relative">
            <Input
              id="reset-password-new"
              type={showNewPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              onBlur={handleNewPasswordBlur}
              placeholder="Enter new password"
              disabled={isLoading}
              required
              className="pr-10"
              aria-invalid={!!newPasswordError}
              aria-describedby={newPasswordError ? 'new-password-error' : undefined}
            />
            <button
              type="button"
              onClick={() => setShowNewPassword(!showNewPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 focus:outline-none"
              aria-label={showNewPassword ? 'Hide password' : 'Show password'}
              disabled={isLoading}
            >
              {showNewPassword ? (
                <EyeOffIcon className="w-5 h-5" />
              ) : (
                <EyeIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          {newPasswordError && (
            <p id="new-password-error" className="mt-1 text-sm text-red-600 dark:text-red-400">
              {newPasswordError}
            </p>
          )}
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            At least 12 characters, including letters and digits
          </p>
        </div>

        {/* Confirm Password field */}
        <div className="mb-4">
          <label
            htmlFor="reset-password-confirm"
            className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300"
          >
            Confirm Password
          </label>
          <div className="relative">
            <Input
              id="reset-password-confirm"
              type={showConfirmPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              onBlur={handleConfirmPasswordBlur}
              placeholder="Confirm new password"
              disabled={isLoading}
              required
              className="pr-10"
              aria-invalid={!!confirmPasswordError}
              aria-describedby={confirmPasswordError ? 'confirm-password-error' : undefined}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 focus:outline-none"
              aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
              disabled={isLoading}
            >
              {showConfirmPassword ? (
                <EyeOffIcon className="w-5 h-5" />
              ) : (
                <EyeIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          {confirmPasswordError && (
            <p id="confirm-password-error" className="mt-1 text-sm text-red-600 dark:text-red-400">
              {confirmPasswordError}
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
          disabled={isLoading || !!newPasswordError || !!confirmPasswordError}
        >
          {isLoading ? (
            <span className="flex items-center justify-center">
              <Spinner className="mr-2" />
              Resetting...
            </span>
          ) : (
            'Reset Password'
          )}
        </Button>
      </form>
    </div>
  );
}
