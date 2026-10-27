// Hero sign-in card geometry (lg+). The card spans the entrance's two brick
// pillars on the landscape photo, plus a little overhang each side. Fractions
// are of the photo's width (ccsdesktop: 2730×1536, cropped object-cover,
// centred horizontally), so the card stays on the pillars at any window size.
export const HERO_PHOTO_ASPECT = 2730 / 1536;
export const PILLAR_LEFT  = 0.6265;
export const PILLAR_RIGHT = 0.896;
export const CARD_OVERHANG = 20;

// Card's tallest state (error + notice shown) plus a 48px bottom margin.
const STACKED_CARD_ROOM = 520;

// All values are px relative to the hero section. textTop/textBottom are the
// eyebrow top and CTA bottom. On a tall screen the object-cover photo is
// cropped hard and the pillars land off screen, so the card stacks under the
// hero text instead. `reserve` is the space to keep under the text block so
// the hero's flex centring places text + card as one group (and grows the
// hero when they don't fit).
export function heroCardBox({ heroW, heroH, textLeft, textTop, textBottom }) {
  const photoW = Math.max(heroW, heroH * HERO_PHOTO_ASPECT);
  const photoLeft = (heroW - photoW) / 2;
  const left = photoLeft + photoW * PILLAR_LEFT - CARD_OVERHANG;
  const width = photoW * (PILLAR_RIGHT - PILLAR_LEFT) + CARD_OVERHANG * 2;
  if (left + width <= heroW - 16) {
    return { mode: 'pillars', left, top: textTop, width, height: textBottom - textTop };
  }
  return {
    mode: 'stacked',
    left: textLeft,
    top: textBottom + 32,
    width: Math.min(448, heroW - 2 * textLeft),
    reserve: 32 + STACKED_CARD_ROOM,
  };
}
