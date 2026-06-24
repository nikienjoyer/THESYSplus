/**
 * SimilaritySlider — similarity threshold range control.
 *
 * Renders a styled range input with a live percentage readout and a
 * coloured relevance pill that changes from green (strict) → amber
 * (balanced) → blue (broad) as the threshold decreases.
 *
 * Phase 1.1 Step 1: isDark ternaries for text colours replaced with
 * semantic token utilities. The track gradient and pill classes still
 * use direct Tailwind utilities mapped to the status quartet tokens;
 * the isDark prop is retained only for the track fill gradient (an
 * inline style value) and the prose-invert prose class. Layout,
 * spacing, behaviour, and slider mechanics are unchanged.
 *
 * Props
 * -----
 * value       {number}          current threshold 0–100 (integer percent)
 * onChange    {fn}              called with the new integer percent on every change
 * isDark      {boolean}         still needed for the inline track-fill gradient empty side
 * disabled    {boolean}         greyed out when no query is active
 * helperText  {string|null}     overrides the default helper text when provided
 */

export default function SimilaritySlider({ value, onChange, isDark, disabled, helperText }) {
  const MIN = 30;
  const MAX = 95;

  // Colour zones: strict (≥70), balanced (50–69), broad (<50)
  const getZone = (v) => {
    if (v >= 70) return 'strict';
    if (v >= 50) return 'balanced';
    return 'broad';
  };
  const zone = getZone(value);

  const zoneLabel = { strict: 'Strict', balanced: 'Balanced', broad: 'Broad' }[zone];

  // Pill classes — mapped to semantic token utilities where possible.
  // The dark-mode variants are token-backed via the CSS variables in tokens.css.
  const pillClass = {
    strict:   'bg-success-bg text-success-text border-success-border',
    balanced: 'bg-warning-bg text-warning-text border-warning-border',
    broad:    'bg-info-bg    text-info-text    border-info-border',
  }[zone];

  const trackFill = {
    strict:   'var(--color-success)',  // emerald
    balanced: 'var(--color-warning)',  // amber
    broad:    'var(--color-primary)',  // blue
  }[zone];

  // Percentage position of thumb on the track (for the background gradient)
  const pct = ((value - MIN) / (MAX - MIN)) * 100;

  // The empty side of the track still needs a fixed colour because
  // we can't use a CSS var in a linear-gradient without var() in inline style
  const trackEmptyColor = isDark ? 'rgba(255,255,255,0.08)' : '#e5e7eb';

  const trackStyle = {
    background: `linear-gradient(to right, ${trackFill} ${pct}%, ${trackEmptyColor} ${pct}%)`,
  };

  return (
    <div
      className={`flex flex-col gap-2 transition-opacity ${
        disabled ? 'opacity-40 pointer-events-none' : 'opacity-100'
      }`}
      aria-disabled={disabled}
    >
      {/* Row: label + value badge */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-body">
          Similarity Threshold
        </span>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold tabular-nums text-ink">
            {value}%
          </span>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${pillClass}`}
          >
            {zoneLabel}
          </span>
        </div>
      </div>

      {/* Range input */}
      <input
        type="range"
        min={MIN}
        max={MAX}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        style={trackStyle}
        className="similarity-slider w-full h-1.5 rounded-full appearance-none cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
        aria-label={`Similarity threshold: ${value}%`}
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        aria-valuenow={value}
      />

      {/* Tick labels */}
      <div className="flex justify-between">
        <span className="text-[10px] text-muted">{MIN}% Broad</span>
        <span className="text-[10px] text-muted">{MAX}% Strict</span>
      </div>

      {/* Helper text */}
      <p className="text-[11px] leading-snug text-body">
        {helperText ?? 'Lower thresholds show broader related studies. Higher thresholds show stricter semantic matches.'}
      </p>
    </div>
  );
}
