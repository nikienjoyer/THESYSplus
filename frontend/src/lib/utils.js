import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * cn — Tailwind-aware class name combiner.
 *
 * Merges conditional class names (via clsx) then resolves conflicting
 * Tailwind utilities (via tailwind-merge) so the last class wins.
 *
 * Imported as `@/lib/utils` by all shadcn components.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
