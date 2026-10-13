/**
 * HeroLayoutSwitcher — dev-server-only A/B/C/D picker for the landing hero
 * sign-in card, so the layouts can be shown to the panel side by side.
 *
 *   A  card always shown, solid frosted
 *   B  card always shown, see-through
 *   C  card slides in from the navbar Sign In button (the shipped default)
 *   D  like C, with the see-through card from B
 *
 * Production builds always get C (see useHeroLayout), and LandingPage only
 * renders this under `import.meta.env.DEV`.
 */

import { HERO_LAYOUTS } from '../../hooks/useHeroLayout';

export default function HeroLayoutSwitcher({ layout, onChange }) {
  return (
    <div role="radiogroup" aria-label="Sign-in layout (dev preview)"
      className="absolute left-4 bottom-4 z-30 hidden lg:flex items-center gap-1 rounded-full bg-slate-950/80 border border-white/15 p-1 pl-3 text-xs font-semibold text-slate-300 backdrop-blur">
      <span className="mr-1">Layout</span>
      {HERO_LAYOUTS.map((v) => (
        <button key={v} type="button" role="radio" aria-checked={layout === v} onClick={() => onChange(v)}
          className={`w-7 h-7 rounded-full uppercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
            layout === v ? 'bg-primary-solid text-white' : 'hover:bg-white/10 text-slate-200'
          }`}>
          {v}
        </button>
      ))}
    </div>
  );
}
