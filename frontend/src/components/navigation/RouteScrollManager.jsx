import { useLayoutEffect, useRef } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';

// React Router's BrowserRouter does not restore scroll positions for page routes.
// Keep positions by history-entry key so Back and Forward return to the right page.
const scrollPositions = new Map();

function restorePosition(position) {
  if (position === 0) {
    window.scrollTo(0, 0);
    return () => {};
  }

  let cancelled = false;
  const scroll = () => {
    if (cancelled) return;
    window.scrollTo(0, position);
  };
  const stop = () => {
    cancelled = true;
    window.clearInterval(interval);
    window.clearTimeout(timeout);
    for (const event of ['wheel', 'touchstart', 'pointerdown', 'keydown']) {
      window.removeEventListener(event, stop);
    }
  };
  const interval = window.setInterval(scroll, 100);
  // Delayed API content can make the saved offset reachable only after render.
  const timeout = window.setTimeout(stop, 10000);
  for (const event of ['wheel', 'touchstart', 'pointerdown', 'keydown']) {
    window.addEventListener(event, stop, { once: true, passive: true });
  }
  scroll();
  return stop;
}

export default function RouteScrollManager() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const previousPath = useRef(null);

  useLayoutEffect(() => {
    const key = location.key;
    const remember = () => scrollPositions.set(key, window.scrollY);
    if (!scrollPositions.has(key)) remember();
    window.addEventListener('scroll', remember, { passive: true });
    return () => {
      window.removeEventListener('scroll', remember);
    };
  }, [location.key]);

  useLayoutEffect(() => {
    const priorPath = previousPath.current;
    previousPath.current = location.pathname;

    // Leave the initial load, query changes, and anchor navigation alone.
    if (priorPath === null || priorPath === location.pathname || location.hash) return;

    if (navigationType === 'POP') {
      const position = scrollPositions.get(location.key);
      // A missing entry belongs to the browser (e.g. navigation from outside the app).
      return position === undefined ? undefined : restorePosition(position);
    }

    window.scrollTo(0, 0);
  }, [location.key, location.pathname, location.hash, navigationType]);

  return null;
}
