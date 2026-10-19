# Navbar Full-Width Spread Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On desktop (≥1024px), spread the five nav links across most of the top bar, scale the text and logo up with the screen, and keep text from staying small on 2560px+ monitors.

**Architecture:** The desktop row keeps its `grid-cols-[1fr_auto_1fr]` so the links stay truly centered. The center `<ul>` gets a viewport-relative width and `justify-between`, so the links fill that width instead of bunching up. Both navbars, AppNavbar and the LandingPage, read from the shared class constants in `AppNavbar.jsx`. Change those once, then apply the same desktop-row classes in both files.

**Tech Stack:** React 19, Tailwind (arbitrary values), Vite.

**Spec:** In-chat design approved 2026-10-15, plus the user's follow-up "occupy the whole space". Mockup: `docs/superpowers/specs/mockups/2026-10-15-navbar-scaling.html`.

## Global Constraints

- Mobile row (`lg:hidden`) and the mobile drawer are unchanged.
- No new dependencies, and no new components or files in `src/`.
- Link list width: `lg` auto (current gap), `xl:w-[52vw]`, `2xl:w-[58vw]`. At ≥xl, each `<li>` is `flex-1` and each link is `block text-center`, so the box fills its equal share.
- Link text: `text-[0.9375rem] xl:text-base 2xl:text-[1.0625rem]`. Link padding: `px-3 xl:px-4 py-1.5 xl:py-2`.
- Bar padding: `py-3 xl:py-4` (horizontal padding unchanged).
- Logo (desktop row only): `origin-left xl:scale-[1.15] 2xl:scale-[1.3]`, which is roughly 32px and 36px.
- Root font: `clamp(16px, calc(100vw / 96), 24px)` (cap raised from 22px).

## Review Focus

1. **1280px width, logged in:** the right column holds Upload Thesis, avatar and theme toggle. The link list must not overlap them, and the gap should be at least 24px.
2. **1024–1279px (lg, below xl):** the list falls back to its auto width. It must look identical to today.
3. **Landing page, signed out, `heroToggles` on:** the Sign In button is in the right column. Same no-overlap check.
4. **Light theme:** the active pill and hover backgrounds still look right at the larger padding.
5. **Very wide screens, 3840px:** the root font stops at 24px, so the links get no bigger past that. Text must still not look tiny compared with the bar height.

---

### Task 1: Shared constants, root cap and both desktop rows

**Files:**
- Modify: `frontend/src/components/layout/AppNavbar.jsx` (the `NAV_BAR_CLASS` / `NAV_LINK_BASE` constants, then the desktop row's logo wrapper and `<ul>`)
- Modify: `frontend/src/pages/LandingPage.jsx:296-305` (desktop row's logo `Link` and `<ul>`)
- Modify: `frontend/src/index.css:100-103` (root clamp cap and its comment)

**Interfaces:**
- Produces: `NAV_BAR_CLASS`, `NAV_LINK_BASE`, and a new exported `NAV_LIST_CLASS` string, all in `AppNavbar.jsx`. LandingPage imports `NAV_LIST_CLASS` next to the existing ones.

- [ ] **Step 1: Write the overlap check.** No frontend test runner exists, so the check is a snippet you run in the browser on the page:

```js
(() => {
  const row = document.querySelector('nav > div.hidden.lg\\:grid');
  const [left, list, right] = row.children;
  const l = list.getBoundingClientRect(), r = right.querySelector('*').getBoundingClientRect(), g = left.getBoundingClientRect();
  return { gapRight: Math.round(r.left - l.right), gapLeft: Math.round(l.left - g.right), fill: +(l.width / row.clientWidth).toFixed(2) };
})()
```

Pass condition: `gapRight >= 24`, `gapLeft >= 24`, and at ≥1536px `fill >= 0.55`.

- [ ] **Step 2: Run it on the current build (baseline).** Start `test-backend` and `test-frontend` (port 5174). Open `/` at 1920×1080. Expected: `fill` is about 0.35 or less, which confirms the links are bunched.

- [ ] **Step 3: Implement.**
  - `NAV_BAR_CLASS`: change `py-3` to `py-3 xl:py-4`.
  - `NAV_LINK_BASE`: change `px-3 xl:px-4 py-1.5 … text-sm` to `px-3 xl:px-4 py-1.5 xl:py-2 … text-[0.9375rem] xl:text-base 2xl:text-[1.0625rem]`, and add `whitespace-nowrap`.
  - Add `export const NAV_LIST_CLASS = 'flex items-center gap-1 xl:w-[52vw] 2xl:w-[58vw] xl:[&>li]:flex-1';`. Use it on both desktop `<ul>`s. Each `<li>` takes an equal share of the width, so the active and hover boxes fill their slot.
  - `NAV_LINK_BASE`: also add `block text-center`, so the box stretches to the `<li>`'s full width.
  - Logo wrappers on both desktop rows: add `origin-left xl:scale-[1.15] 2xl:scale-[1.3]`.
  - `index.css`: change the cap from `22px` to `24px`, and the comment's "(20px at 1920)" note becomes "caps at 24px (~2300px wide)".

- [ ] **Step 4: Re-run the check at 1280, 1536, 1920 and 2560.** Do this on `/` signed out, on `/` signed in, and on `/repository` signed in. Expected: all pass conditions hold. Then take one screenshot at 1920 and one at 1024. The 1024 shot must match the baseline layout.

- [ ] **Step 5: Lint and commit**

```bash
npm --prefix frontend run lint
git add frontend/src/components/layout/AppNavbar.jsx frontend/src/pages/LandingPage.jsx frontend/src/index.css
git commit -m "Spread navbar links across the bar and scale them on wide screens"
```
