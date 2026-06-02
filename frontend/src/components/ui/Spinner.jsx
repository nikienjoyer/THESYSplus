/**
 * Spinner — animated loading indicator.
 *
 * Renders a clean dual-ring SVG spinner. The outer track is muted;
 * the inner arc is the primary accent colour.
 *
 * Props:
 *   className  — additional Tailwind classes (e.g. size overrides)
 *   size       — 'sm' | 'md' (default) | 'lg'
 */
const SIZE = { sm: 'h-4 w-4', md: 'h-5 w-5', lg: 'h-7 w-7' };

export default function Spinner({ className, size = 'md', ...props }) {
  return (
    <svg
      className={`animate-spin ${SIZE[size] ?? SIZE.md} ${className || ''}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      {...props}
    >
      {/* Track ring */}
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="2.5"
        className="opacity-15"
      />
      {/* Active arc */}
      <path
        d="M12 3a9 9 0 0 1 9 9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        className="opacity-80"
      />
    </svg>
  );
}
