/**
 * WatermarkOverlay — tiled, rotated institutional watermark for PdfPreviewPage's
 * full-screen document view.
 *
 * Theme-independent by design, not by oversight: the surface this overlay sits
 * on is always the white PDF page, in both light and dark mode — the app's
 * `isDark` state describes the surrounding chrome, not the paper underneath.
 * A theme-reactive color here is a *bug*, not a missing feature: dark mode
 * previously rendered white text at 15% opacity onto white paper, which is
 * invisible. Do not reintroduce an `isDark`/theme branch on this color.
 *
 * Accepted tradeoff: in dark mode, the dark gutters flanking the page (painted
 * by the browser's native PDF viewer, not this component) will make the
 * watermark unreadable there. That's fine — the paper is the surface that
 * matters for a "Preview Only" stamp, not the gutters around it.
 *
 * `aria-hidden="true"` on the root: this overlay is 27 decorative `<span>`
 * text nodes (9 rows × 3 columns, all repeating the same sentence) with no
 * interactive or focusable content, so hiding the whole subtree from
 * assistive tech is safe. Without it, screen readers announce the watermark
 * sentence 27 times. The "this is a preview" context is already conveyed
 * accessibly elsewhere on the page (the Close Preview button label and the
 * iframe's title attribute), so no `sr-only` replacement text is needed here.
 */
const WATERMARK_TEXT = 'College of Computing Studies - Pampanga State University • Preview Only';

export default function WatermarkOverlay() {
  const rows = Array.from({ length: 9 });
  const cols = Array.from({ length: 3 });
  return (
    <div
      className="pointer-events-none select-none absolute inset-0 z-10 overflow-hidden"
      aria-hidden="true"
    >
      <div
        className="absolute flex flex-col items-center justify-center gap-14"
        style={{
          top: '-60%',
          left: '-60%',
          width: '220%',
          height: '220%',
          transform: 'rotate(-30deg)',
          opacity: 0.15,
        }}
      >
        {rows.map((_, r) => (
          <div key={r} className="flex gap-14 whitespace-nowrap">
            {cols.map((__, c) => (
              <span
                key={c}
                className="text-sm font-semibold tracking-wide text-gray-900"
              >
                {WATERMARK_TEXT}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
