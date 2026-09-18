/**
 * motion.js — shared Framer Motion tokens for the three animated surfaces
 * (LandingPage, AnalyticsDashboardPage, TrendAnalysisPage).
 *
 * Scope: this is the ONLY place animation timing/easing values are defined
 * for JS-driven motion. Every consumer imports from here instead of
 * hardcoding durations/eases, so the motion language stays anchored to the
 * existing CSS tokens in `styles/tokens.css`:
 *
 *   --ease-out:      cubic-bezier(0, 0, 0.2, 1)   → EASE_OUT below
 *   --duration-normal:  150ms                     → DURATION.normal
 *   --duration-surface: 180ms                     → DURATION.surface
 *   --duration-enter:   200ms                     → DURATION.enter
 *
 * No spring physics, no bounce — every variant here is a tween using
 * EASE_OUT. Entrance travel is capped at 8px (TRAVEL_PX), matching the
 * ~4px ceiling already used by the `fade-in` keyframe in tailwind.config.js
 * (doubled, not exceeded, to stay legible on larger animated blocks).
 *
 * Bundle note: consumers must import `{ m }` and wrap the animated surface
 * in `<LazyMotion features={domAnimation}>` — never import `motion` from
 * 'framer-motion' directly. That pulls in the full feature set (drag,
 * layout animations, etc.) into the bundle; `domAnimation` is the minimal
 * set needed for opacity/transform tweens + exit animations.
 */

import { useEffect, useState } from 'react';
import { animate, useMotionValue, useReducedMotion, useTransform } from 'framer-motion';

// ── Easing ──────────────────────────────────────────────────────────────
// Matches --ease-out in tokens.css exactly.
export const EASE_OUT = [0, 0, 0.2, 1];

// ── Durations (seconds — Framer Motion works in seconds, not ms) ────────
export const DURATION = {
  normal:  0.15,  // --duration-normal
  surface: 0.18,  // --duration-surface
  enter:   0.2,   // --duration-enter
};

// Entrance travel ceiling — stays in family with the ~4px `fade-in` keyframe.
export const TRAVEL_PX = 8;

// ── Base variants ────────────────────────────────────────────────────────

/**
 * Opacity + a small upward slide-in. The default entrance for most content.
 *
 * Uses an explicit `transform` string rather than Framer Motion's `y:`
 * shorthand. The shorthand interpolates on the main thread; a raw transform
 * string lets content that mounts at an unpredictable moment (e.g. the
 * instant an async request resolves, exactly when frames are contended)
 * avoid adding to that contention. Renders the identical translateY either
 * way — this is an implementation detail, not a visual change.
 */
export const fadeUp = {
  hidden:  { opacity: 0, transform: `translateY(${TRAVEL_PX}px)` },
  visible: {
    opacity: 1,
    transform: 'translateY(0px)',
    transition: { duration: DURATION.enter, ease: EASE_OUT },
  },
};

/** Opacity-only entrance — used where any transform would be distracting
 * (e.g. content already inside a moving parent). */
export const fadeIn = {
  hidden:  { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: DURATION.enter, ease: EASE_OUT },
  },
};

/** Wrap a `.map()` list in this on the parent, `fadeUp`/`fadeIn` on each
 * child, and the children reveal in a gentle cascade instead of all at once. */
export const staggerContainer = {
  hidden:  {},
  visible: {
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.04,
    },
  },
};

// ── Bar-chart grow-in variants ───────────────────────────────────────────
// Used by HBarChart / YearBarChart / CountsBarChart to sweep a bar out from
// zero to its computed length. `pct` is a 0-100 number (already computed
// by the caller); these return a variant object with an explicit final
// percentage baked in, so each bar in a `.map()` gets its own variant.

/** Grow a bar's `width` from 0 to `${pct}%`. */
export function growWidth(pct) {
  return {
    hidden:  { width: 0 },
    visible: {
      width: `${pct}%`,
      transition: { duration: DURATION.enter, ease: EASE_OUT },
    },
  };
}

/** Grow a bar's `height` from 0 to `${pct}%` (vertical bar charts). */
export function growHeight(pct) {
  return {
    hidden:  { height: 0 },
    visible: {
      height: `${pct}%`,
      transition: { duration: DURATION.enter, ease: EASE_OUT },
    },
  };
}

// ── Doughnut arc draw-in ─────────────────────────────────────────────────
// Animates an SVG circle's stroke-dasharray "dash" length from 0 up to its
// final value, while the caller keeps `strokeDashoffset` fixed — this draws
// the arc in at its correct angular position instead of sweeping around
// the ring. `circumference` is passed through so the "gap" portion of the
// dasharray (circumference - dash) is always geometrically correct, even
// mid-animation.
export function drawArc(finalDash, circumference) {
  return {
    hidden:  { strokeDasharray: `0 ${circumference}` },
    visible: {
      strokeDasharray: `${finalDash} ${circumference - finalDash}`,
      transition: { duration: DURATION.enter, ease: EASE_OUT },
    },
  };
}

// ── Reduced-motion-aware variants ────────────────────────────────────────

const INSTANT = {
  hidden:  { opacity: 1, transform: 'translateY(0px)' },
  visible: { opacity: 1, transform: 'translateY(0px)', transition: { duration: 0 } },
};

const INSTANT_CONTAINER = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0, delayChildren: 0 } },
};

function instantGrowWidth(pct) {
  return { hidden: { width: `${pct}%` }, visible: { width: `${pct}%`, transition: { duration: 0 } } };
}

function instantGrowHeight(pct) {
  return { hidden: { height: `${pct}%` }, visible: { height: `${pct}%`, transition: { duration: 0 } } };
}

function instantDrawArc(finalDash, circumference) {
  const dashArray = `${finalDash} ${circumference - finalDash}`;
  return { hidden: { strokeDasharray: dashArray }, visible: { strokeDasharray: dashArray, transition: { duration: 0 } } };
}

// ── Animated counter (tweened integer) ───────────────────────────────────

export const DEFAULT_COUNTER_DURATION = 0.7; // seconds — deliberate, not slow

/**
 * useAnimatedCounterValue — tweens a number up to `value` and returns the
 * live rounded integer. Backs both the `AnimatedCounter` component (renders
 * HTML <span> markup) and any non-HTML render target that needs the same
 * count-up without that markup — e.g. an SVG <text> node inside
 * DoughnutChart, which can't host AnimatedCounter's <span> children.
 *
 * Callers own their own markup/accessibility treatment; this hook only
 * returns `{ hasNumericValue, displayValue }`.
 */
export function useAnimatedCounterValue(value, duration = DEFAULT_COUNTER_DURATION) {
  const reduceMotion = useReducedMotion();
  const hasNumericValue = typeof value === 'number' && Number.isFinite(value);

  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (v) => Math.round(v));
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const unsubscribe = rounded.on('change', (v) => setDisplayValue(v));
    return unsubscribe;
  }, [rounded]);

  useEffect(() => {
    if (!hasNumericValue) return undefined;

    if (reduceMotion) {
      // .set() synchronously notifies the 'change' subscription above,
      // which updates displayValue — no direct setState call needed here.
      motionValue.set(value);
      return undefined;
    }

    const controls = animate(motionValue, value, {
      duration,
      ease: EASE_OUT,
    });
    return () => controls.stop();
    // Deliberately re-runs whenever `value` changes so the counter replays
    // on every mount/data refresh (approved decision: replay on revisit,
    // no first-arrival gating).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, hasNumericValue, reduceMotion, duration]);

  return { hasNumericValue, displayValue };
}

/**
 * useMotionVariants — call once per component; returns the standard
 * variant set, swapped for zero-duration/no-op variants when the user has
 * OS-level reduced motion enabled. Consumers never need to call
 * `useReducedMotion()` themselves or branch on it in JSX.
 */
export function useMotionVariants() {
  const reduce = useReducedMotion();

  if (reduce) {
    return {
      reduceMotion: true,
      fadeUp: INSTANT,
      fadeIn: INSTANT,
      staggerContainer: INSTANT_CONTAINER,
      growWidth: instantGrowWidth,
      growHeight: instantGrowHeight,
      drawArc: instantDrawArc,
    };
  }

  return {
    reduceMotion: false,
    fadeUp,
    fadeIn,
    staggerContainer,
    growWidth,
    growHeight,
    drawArc,
  };
}
