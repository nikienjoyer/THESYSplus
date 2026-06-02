/**
 * SimilaritySlider — similarity threshold range control.
 *
 * Renders a styled range input with a live percentage readout and a
 * coloured relevance pill that changes from green (strict) → amber
 * (balanced) → blue (broad) as the threshold decreases.
 *
 * Props
 * -----
 * value       {number}          current threshold 0–100 (integer percent)
 * onChange    {fn}              called with the new integer percent on every change
 * isDark      {boolean}         toggles dark/light colour tokens
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

  const pillClass = {
    strict: isDark
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      : 'bg-emerald-50 text-emerald-700 border-emerald-200',
    balanced: isDark
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
      : 'bg-amber-50 text-amber-700 border-amber-200',
    broad: isDark
      ? 'bg-blue-500/15 text-blue-300 border-blue-500/30'
      : 'bg-blue-50 text-blue-700 border-blue-200',
  }[zone];

  const trackFill = {
    strict: '#10b981',   // emerald-500
    balanced: '#f59e0b', // amber-500
    broad: '#3b82f6',    // blue-500
  }[zone];

  // Percentage position of the thumb on the track (for background gradient)
  const pct = ((value - MIN) / (MAX - MIN)) * 100;

  const trackStyle = {
    background: `linear-gradient(to right, ${trackFill} ${pct}%, ${
      isDark ? 'rgba(255,255,255,0.08)' : '#e5e7eb'
    } ${pct}%)`,
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
        <span
          className={`text-xs font-medium ${
            isDark ? 'text-gray-400' : 'text-gray-500'
          }`}
        >
          Similarity Threshold
        </span>

        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-bold tabular-nums ${
              isDark ? 'text-white' : 'text-gray-900'
            }`}
          >
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
        <span className={`text-[10px] ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
          {MIN}% Broad
        </span>
        <span className={`text-[10px] ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
          {MAX}% Strict
        </span>
      </div>

      {/* Helper text */}
      <p className={`text-[11px] leading-snug ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
        {helperText ?? 'Lower thresholds show broader related studies. Higher thresholds show stricter semantic matches.'}
      </p>
    </div>
  );
}
