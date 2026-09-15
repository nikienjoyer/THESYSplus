/**
 * AnimatedCounter — counts a number up to its final value.
 *
 * Used on the three animated surfaces (LandingPage repository snapshot,
 * AnalyticsDashboardPage KPI cards, TrendAnalysisPage KPI cards) to make
 * the AI clustering/aggregation feel like a live computation rather than
 * a static label.
 *
 * Accessibility:
 *   A screen reader announcing every intermediate digit during the count-up
 *   is worse than no animation at all. The animating digits render in an
 *   `aria-hidden="true"` element; the final value is exposed once, via a
 *   visually-hidden span, so assistive tech only ever hears the settled
 *   number.
 *
 * Reduced motion:
 *   When `useReducedMotion()` is true, the final value renders immediately
 *   with no tween — this component checks it directly (rather than going
 *   through `useMotionVariants()`) since a bare number has no meaningful
 *   "instant variant" to share with the fadeUp/stagger variants.
 *
 * Value lifecycle:
 *   `value` may be `null`/`undefined` while the caller is still fetching
 *   (e.g. LandingPage renders '…' until /theses/public-stats/ resolves).
 *   Nothing animates until a real finite number arrives.
 */

import { useAnimatedCounterValue, DEFAULT_COUNTER_DURATION as DEFAULT_DURATION } from '../../lib/motion';

export default function AnimatedCounter({
  value,
  duration = DEFAULT_DURATION,
  placeholder = '…',
  formatter,
  className,
  ...props
}) {
  const { hasNumericValue, displayValue } = useAnimatedCounterValue(value, duration);
  const format = formatter || ((n) => String(n));

  if (!hasNumericValue) {
    return (
      <span className={className} {...props}>
        {placeholder}
      </span>
    );
  }

  return (
    <span className={className} {...props}>
      <span aria-hidden="true" className="tabular-nums">
        {format(displayValue)}
      </span>
      <span className="sr-only">{format(value)}</span>
    </span>
  );
}
