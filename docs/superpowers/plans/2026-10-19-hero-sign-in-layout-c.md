# Hero Sign-In: Layout C Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The team picked hero sign-in layout C, so remove layouts A, B and D and the dev-only A–D switcher, leaving C as the only code path.

**Architecture:** Layout C is the navbar Sign In button toggling the frosted hero card. Delete the `heroLayout` state and every branch that existed only for A, B or D. `HeroSignInCard` loses its see-through `see` prop, and `HeroLayoutSwitcher` and `useHeroLayout` are deleted.

**Tech Stack:** React 19, framer-motion, Tailwind, Vite.

**Spec:** The user's decision on 2026-10-19: "for the sign in, we picked C". Layouts were introduced in commits a778f54 (A), b5bf8ab (B) and f87338d (D); production already always renders C (`useHeroLayout`).

## Global Constraints

- No visual or behavior change for C, which production already renders. The only visible change is that the dev-server-only switcher disappears.
- No new files, and no new dependencies.
- Below `lg` (1024px) the hero card stays hidden and Sign In still goes to `/sign-in`, unchanged.

## Review Focus

1. **Signed-out desktop:** the navbar Sign In opens and closes the card. Escape or ✕ closes it and returns focus to Sign In.
2. **A stale `thesys:heroLayout` value in localStorage** (`'a'`, `'b'`, `'d'`) changes nothing; the key is simply ignored.
3. **Signed in:** no card and no Sign In button, unchanged.

---

### Task 1: Collapse to layout C

**Files:**
- Modify: `frontend/src/pages/LandingPage.jsx` (remove `useHeroLayout` and `HeroLayoutSwitcher` imports and usage; `heroToggles` is always true and `heroSeeThrough` always false; inline both)
- Modify: `frontend/src/components/auth/HeroSignInCard.jsx` (drop the `see` prop and its see-through classes; keep the frosted classes)
- Delete: `frontend/src/components/auth/HeroLayoutSwitcher.jsx`, `frontend/src/hooks/useHeroLayout.js`

**Interfaces:**
- Produces: `HeroSignInCard({ isDark, onClose, autoFocus })`.

- [ ] **Step 1: Inline C**
  - `showHeroSignIn = !isInitializing && !isAuthenticated && signInOpen`.
  - Render the navbar Sign In whenever the visitor is signed out.
  - Render `<HeroSignInCard isDark={isDark} onClose={closeSignIn} autoFocus />`.
  - Delete the switcher block and update the comment above the hero sign-in state.
- [ ] **Step 2: Simplify `HeroSignInCard`**
  - Keep only the non-`see` class strings.
  - Remove the `see` sentence from the header comment.
- [ ] **Step 3: Delete the two files** and confirm nothing imports them: `grep -rn "useHeroLayout\|HeroLayoutSwitcher\|heroSeeThrough\|heroToggles" frontend/src`. Expected: no output.
- [ ] **Step 4: Lint and build**

Run: `cd frontend && npx eslint src/pages/LandingPage.jsx src/components/auth && npx vite build --outDir <scratchpad>/build`
Expected: no new lint errors, and the build succeeds.

- [ ] **Step 5: Browser check** on 5174 at 1280px. Review Focus 1–3, plus 375px, where Sign In still goes to `/sign-in`.
- [ ] **Step 6: Commit** only these four paths. `LandingPage.jsx` also holds uncommitted navbar work, so stage with `git add -p` and keep only the layout hunks.
