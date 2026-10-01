/**
 * AuthBranding — reusable logo + wordmark block for auth pages.
 *
 * Renders the same THESYS+ wordmark as the landing page (mark beside the
 * two-tone text), scaled up, with an optional subtitle line below.
 *
 * Props:
 *   subtitle  {string}  — the context line below the wordmark (e.g. "Sign in to continue")
 */
import ThesysLogo from './ThesysLogo';

export default function AuthBranding({ subtitle }) {
  return (
    <div className="flex flex-col items-center mb-8 select-none">
      <h1 aria-label="THESYS+" className="mb-2">
        <ThesysLogo variant="wordmark" size={48} />
      </h1>
      {subtitle && (
        <p className={`text-xs tracking-widest uppercase font-medium mt-1 text-muted`}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
