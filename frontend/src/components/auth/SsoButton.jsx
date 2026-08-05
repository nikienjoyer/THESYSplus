/**
 * SsoButton — Placeholder for future institutional SSO integration.
 * 
 * Renders a visually disabled button with a "Coming Soon" tooltip.
 * Issues no network request on click per Requirement 6.2.
 * 
 * Requirements: 6.1, 6.2
 */

import Button from '../ui/Button';

export default function SsoButton({ className, ...props }) {
  return (
    <div className="relative group">
      <Button
        type="button"
        disabled
        className={`w-full ${className || ''}`.trim()}
        aria-label="Single Sign-On (Coming Soon)"
        {...props}
      >
        Sign in with SSO
      </Button>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap dark:bg-gray-700">
        Coming Soon
      </div>
    </div>
  );
}
