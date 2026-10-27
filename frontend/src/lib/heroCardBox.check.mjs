// Run: node frontend/src/lib/heroCardBox.check.mjs (no output = pass)
import assert from 'node:assert/strict';
import { heroCardBox, HERO_PHOTO_ASPECT, PILLAR_LEFT, PILLAR_RIGHT, CARD_OVERHANG } from './heroCardBox.js';

const input = (heroW, heroH) => ({
  heroW, heroH,
  textLeft: heroW >= 1280 ? 80 : 64, // lg:px-16 / xl:px-20
  textTop: heroH / 2 - 150,
  textBottom: heroH / 2 + 150,
});

for (const [w, h] of [[1366, 768], [1920, 1080], [1280, 800], [2560, 1440]]) {
  const box = heroCardBox(input(w, h));
  const photoW = Math.max(w, h * HERO_PHOTO_ASPECT);
  const photoLeft = (w - photoW) / 2;
  assert.equal(box.mode, 'pillars', `${w}x${h}`);
  assert.ok(Math.abs(box.left - (photoLeft + photoW * PILLAR_LEFT - CARD_OVERHANG)) < 0.5, `${w}x${h} left`);
  assert.ok(Math.abs(box.width - (photoW * (PILLAR_RIGHT - PILLAR_LEFT) + CARD_OVERHANG * 2)) < 0.5, `${w}x${h} width`);
  assert.equal(box.height, 300);
}

for (const [w, h] of [[1080, 1920], [1024, 1366], [1280, 1024]]) {
  const inp = input(w, h);
  const box = heroCardBox(inp);
  assert.equal(box.mode, 'stacked', `${w}x${h}`);
  assert.ok(box.left + box.width <= w - 16, `${w}x${h} fits`);
  assert.ok(box.top > inp.textBottom, `${w}x${h} below text`);
  assert.equal(box.height, undefined);
  assert.ok(box.reserve > 32);
  assert.equal(box.minHeroHeight, undefined);
}
