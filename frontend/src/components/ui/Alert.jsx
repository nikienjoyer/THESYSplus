/**
 * Reusable Alert primitive — Foundation Phase shell.
 * Thin Tailwind-styled wrapper around <div role="alert"> with prop forwarding.
 */
export default function Alert({ className, children, ...props }) {
  return (
    <div
      role="alert"
      className={`rounded-md border p-4 text-sm ${className || ''}`.trim()}
      {...props}
    >
      {children}
    </div>
  );
}
