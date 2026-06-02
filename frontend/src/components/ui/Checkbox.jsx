/**
 * Reusable Checkbox primitive — Foundation Phase shell.
 * Thin Tailwind-styled wrapper around <input type="checkbox"> with prop forwarding.
 */
export default function Checkbox({ className, ...props }) {
  return (
    <input
      type="checkbox"
      className={`h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary dark:border-gray-600 ${className || ''}`.trim()}
      {...props}
    />
  );
}
