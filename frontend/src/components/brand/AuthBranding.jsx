/**
 * AuthBranding — reusable logo + wordmark block for auth pages.
 *
 * Renders the THESYS+ symbol (48px) above the two-tone wordmark text,
 * with an optional subtitle line below.
 *
 * Props:
 *   subtitle  {string}  — the context line below the wordmark (e.g. "Sign in to continue")
 *   isDark    {boolean}
 */
import ThesysLogo from './ThesysLogo';

export default function AuthBranding({ subtitle, isDark }) {
  return (
    <div className="flex flex-col items-center mb-8 select-none">
      {/* Symbol only — 48px, no redundant text here since wordmark follows below */}
      <ThesysLogo variant="symbol" size={48} className="mb-4" />
      {/* Wordmark text — larger display size for auth pages */}
      <h1 className="text-3xl font-extrabold tracking-tighter leading-none mb-1">
        <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
        <span className="text-primary">SYS+</span>
      </h1>
      {subtitle && (
        <p className={`text-xs tracking-widest uppercase font-medium mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
