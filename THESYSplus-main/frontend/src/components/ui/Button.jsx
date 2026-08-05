/**
 * Reusable Button primitive — Foundation Phase shell.
 * Thin Tailwind-styled wrapper around <button> with prop forwarding.
 */
export default function Button({ className, children, ...props }) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50 bg-primary text-white hover:bg-primary/90 ${className || ''}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}
