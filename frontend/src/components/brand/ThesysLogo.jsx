/**
 * ThesysLogo — Official THESYS+ brand mark component.
 *
 * Renders the approved thesys-symbol.svg asset directly as a
 * CSS background-image, which triggers the browser's full SVG
 * rendering engine including the mask and filter elements that
 * the asset relies on.
 *
 * Why background-image instead of <img>:
 *   The SVG uses <mask> with feColorMatrix luminance-to-alpha filters.
 *   When rendered via <img src>, some browsers do not execute external
 *   SVG filter/mask references, causing the artwork to be invisible.
 *   background-image always executes the full SVG renderer.
 *
 * Crop logic:
 *   The SVG canvas is 1440×810. The mark sits inside:
 *     <g clip-path> → 580.125–859.875 (x), 265–545 (y) → 280×280 region
 *     <g transform="matrix(0.75,0,0,0.75,580.125,265)"> positions the raster
 *   background-size scales the full canvas so the 280×280 mark region
 *   fills the target tile exactly. background-position shifts the canvas
 *   so the mark's top-left aligns with the container origin.
 *
 * Variants:
 *   "symbol"   — mark tile only
 *   "wordmark" — mark + "THESYS+" typography, horizontal
 *   "full"     — mark + "THESYS+" + institutional descriptor
 *
 * Props:
 *   variant   — 'symbol' | 'wordmark' | 'full'  (default: 'wordmark')
 *   size      — side length of the symbol tile in px (default: 28)
 *   className — extra wrapper classes
 *   isDark    — controls wordmark text colour
 */

import symbolSvg from '../../assets/branding/thesys-symbol.svg';

// Exact mark bounds from the SVG clipPath element:
//   <path d="M 580.125 265 L 859.875 265 L 859.875 545 L 580.125 545 Z"/>
const CANVAS_W = 1440;
const CANVAS_H = 810;
const MARK_X   = 580.125;
const MARK_Y   = 265;
const MARK_W   = 859.875 - 580.125;  // ≈ 279.75
const MARK_H   = 545 - 265;          // = 280

/**
 * SymbolTile — renders the mark via CSS background-image.
 *
 * background-size: set so the full canvas scales to fit the mark into `size` px.
 * background-position: negative offset to shift the mark to the tile origin.
 */
function SymbolTile({ size }) {
  const scale   = size / Math.max(MARK_W, MARK_H);
  const bgW     = Math.round(CANVAS_W * scale);
  const bgH     = Math.round(CANVAS_H * scale);
  const bgLeft  = -Math.round(MARK_X * scale);
  const bgTop   = -Math.round(MARK_Y * scale);

  return (
    <span
      role="img"
      aria-label="THESYS+ symbol"
      style={{
        display:           'inline-block',
        width:             size + 'px',
        height:            size + 'px',
        flexShrink:        0,
        backgroundImage:   `url(${symbolSvg})`,
        backgroundRepeat:  'no-repeat',
        backgroundSize:    `${bgW}px ${bgH}px`,
        backgroundPosition:`${bgLeft}px ${bgTop}px`,
      }}
    />
  );
}

export default function ThesysLogo({
  variant   = 'wordmark',
  size      = 28,
  className = '',
  isDark    = false,
}) {
  const textSize = Math.round(size * 0.5) + 'px';

  if (variant === 'symbol') {
    return (
      <span className={`inline-flex items-center justify-center flex-shrink-0 ${className}`}>
        <SymbolTile size={size} />
      </span>
    );
  }

  if (variant === 'wordmark') {
    return (
      <span className={`inline-flex items-center gap-2 select-none ${className}`}>
        <SymbolTile size={size} />
        <span className="font-bold tracking-wide leading-none" style={{ fontSize: textSize }}>
          <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
          <span className="text-primary">SYS+</span>
        </span>
      </span>
    );
  }

  // full — mark + wordmark + institutional descriptor
  return (
    <span className={`inline-flex flex-col gap-1 select-none ${className}`}>
      <span className="inline-flex items-center gap-2">
        <SymbolTile size={size} />
        <span className="font-bold tracking-wide leading-none" style={{ fontSize: textSize }}>
          <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
          <span className="text-primary">SYS+</span>
        </span>
      </span>
      <span
        className={isDark ? 'text-gray-500' : 'text-gray-500'}
        style={{ fontSize: Math.round(size * 0.28) + 'px', lineHeight: 1.3 }}
      >
        Pampanga State University · College of Computing Studies
      </span>
    </span>
  );
}
