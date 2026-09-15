/**
 * useBodyScrollLock — locks background page scroll while a modal is open.
 *
 * Setting `overflow: hidden` on `document.body` alone is not enough:
 *   - On many desktop layouts the scrolling context lives on `<html>`
 *     (`document.documentElement`), so body-only locks leave the page
 *     scrollable via keyboard/wheel.
 *   - iOS Safari ignores `overflow: hidden` entirely during touch swipes,
 *     letting the page scroll (and the modal drift) underneath the finger.
 *
 * This hook fixes both by locking overflow on *both* `<html>` and `<body>`,
 * and by returning a ref that should be attached to the modal's backdrop
 * overlay element — a non-passive `touchmove` listener on that ref blocks
 * iOS touch-scroll-through without affecting the modal's own scrollable
 * content (which lives outside the backdrop element and keeps native
 * touch/wheel scrolling).
 *
 * Usage:
 *   const backdropRef = useBodyScrollLock(isOpen);
 *   return isOpen && (
 *     <div ref={backdropRef} className="absolute inset-0 ..." onClick={onClose} />
 *   );
 *
 * Behaviour:
 *   - On open: captures the previous inline `overflow` value of `<html>`
 *     and `<body>`, then sets both to `hidden`.
 *   - While open: touches starting on the backdrop element never scroll
 *     the page, even on iOS Safari.
 *   - On close/unmount: restores the captured inline overflow values and
 *     removes the listener, so the page scrolls normally again.
 */

import { useEffect, useRef } from 'react';

export default function useBodyScrollLock(isOpen) {
  const backdropRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    const { body } = document;
    const html = document.documentElement;
    const prevBodyOverflow = body.style.overflow;
    const prevHtmlOverflow = html.style.overflow;

    body.style.overflow = 'hidden';
    html.style.overflow = 'hidden';

    const preventTouchScroll = (e) => { e.preventDefault(); };
    const backdrop = backdropRef.current;
    if (backdrop) {
      backdrop.addEventListener('touchmove', preventTouchScroll, { passive: false });
    }

    return () => {
      body.style.overflow = prevBodyOverflow;
      html.style.overflow = prevHtmlOverflow;
      if (backdrop) {
        backdrop.removeEventListener('touchmove', preventTouchScroll);
      }
    };
  }, [isOpen]);

  return backdropRef;
}
