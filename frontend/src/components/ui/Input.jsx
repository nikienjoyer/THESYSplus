/**
 * Reusable Input primitive — Foundation Phase shell.
 * Thin Tailwind-styled wrapper around <input> with prop forwarding.
 */
export default function Input({ className, ...props }) {
  return (
    <input
      className={`flex h-10 w-full rounded-md border border-gray-300 bg-background px-3 py-2 text-sm placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 ${className || ''}`.trim()}
      {...props}
    />
  );
}
