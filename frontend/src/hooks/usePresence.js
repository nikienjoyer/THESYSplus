import { useEffect, useState } from 'react';

/**
 * usePresence — keep an overlay mounted long enough to play its exit.
 *
 * Returns [mounted, closing]. Render while `mounted`; put
 * `data-closing` on the wrapper while `closing` so CSS can run the
 * exit keyframes (see "Exit motion" in index.css). `exitMs` must match
 * the longest exit animation inside. Reduced-motion users skip the wait.
 */
export default function usePresence(open, exitMs = 150) {
  const [mounted, setMounted] = useState(open);
  if (open && !mounted) setMounted(true);

  useEffect(() => {
    if (open || !mounted) return undefined;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const t = setTimeout(() => setMounted(false), reduce ? 0 : exitMs);
    return () => clearTimeout(t);
  }, [open, mounted, exitMs]);

  return [open || mounted, !open && mounted];
}
