/**
 * useHeroLayout — which landing-hero sign-in layout to render (a/b/c/d).
 * Dev server: remembered in localStorage so it can be set before a panel
 * demo. Production: always 'c', since `import.meta.env.DEV` is false.
 */

import { useState } from 'react';

export const HERO_LAYOUTS = ['a', 'b', 'c', 'd'];
const DEFAULT_LAYOUT = 'c';
const STORAGE_KEY = 'thesys:heroLayout';

function readStored() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return HERO_LAYOUTS.includes(v) ? v : DEFAULT_LAYOUT;
  } catch {
    return DEFAULT_LAYOUT;
  }
}

export default function useHeroLayout() {
  const [layout, setLayout] = useState(() => (import.meta.env.DEV ? readStored() : DEFAULT_LAYOUT));
  const choose = (v) => {
    setLayout(v);
    try { localStorage.setItem(STORAGE_KEY, v); } catch { /* preview-only convenience */ }
  };
  return [layout, choose];
}
