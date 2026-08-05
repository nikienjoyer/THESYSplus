/**
 * useFocusTrap — traps keyboard focus within a container while it is open.
 *
 * WCAG 2.4.3 (Focus Order) / 2.1.2 (No Keyboard Trap, handled via Escape):
 * modal dialogs and drawers must keep Tab focus inside the open surface and
 * restore focus to the triggering element on close.
 *
 * Usage:
 *   const ref = useFocusTrap(isOpen, () => setOpen(false));
 *   return isOpen && <div ref={ref} role="dialog" aria-modal="true">…</div>;
 *
 * Behaviour:
 *   - On open: remembers the previously focused element, then moves focus to
 *     the first focusable element inside the container.
 *   - While open: Tab / Shift+Tab cycle within the container's focusable set.
 *   - On close: restores focus to the previously focused element.
 *
 * Escape handling is intentionally left to the caller (both existing drawers
 * already close on Escape), so this hook does not override it.
 */

import { useEffect, useRef } from 'react';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export default function useFocusTrap(isOpen) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement;

    // Move focus into the drawer on open
    const focusables = container.querySelectorAll(FOCUSABLE);
    if (focusables.length > 0) {
      focusables[0].focus();
    }

    function handleKeyDown(e) {
      if (e.key !== 'Tab') return;

      const items = container.querySelectorAll(FOCUSABLE);
      if (items.length === 0) return;

      const first = items[0];
      const last = items[items.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first || !container.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !container.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      // Restore focus to the trigger when the trap unmounts
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
    };
  }, [isOpen]);

  return containerRef;
}
