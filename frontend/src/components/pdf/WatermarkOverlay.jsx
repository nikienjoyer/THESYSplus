/**
 * WatermarkOverlay — tiled, rotated institutional watermark for PDF preview
 * surfaces (ThesisDetailPage's inline card, PdfPreviewPage's full-screen view).
 */
const WATERMARK_TEXT = 'College of Computing Studies - Pampanga State University • Preview Only';

export default function WatermarkOverlay({ isDark }) {
  const rows = Array.from({ length: 9 });
  const cols = Array.from({ length: 3 });
  return (
    <div className="pointer-events-none select-none absolute inset-0 z-10 overflow-hidden">
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
                className={`text-sm font-semibold tracking-wide ${isDark ? 'text-white' : 'text-gray-900'}`}
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
