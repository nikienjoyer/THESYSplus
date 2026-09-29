---
name: THESYS+
description: Semantic thesis retrieval and topic trend analysis for PampangaStateU CCS
colors:
  primary: "#1e40af"
  primary-hover: "#1c3a99"
  primary-dark-mode: "#60a5fa"
  primary-solid-dark-mode: "#2563eb"
  primary-solid-hover-dark-mode: "#1d4ed8"
  accent-violet: "#7c3aed"
  ink-light: "#111827"
  ink-dark: "#ffffff"
  body-light: "#475569"
  body-dark: "#d1d5db"
  muted-light: "#6b7280"
  muted-dark: "#9ca3af"
  subtle-light: "#9ca3af"
  subtle-dark: "#4b5563"
  surface-light: "#ffffff"
  surface-dark: "rgba(255,255,255,0.03)"
  bg-light: "#f8fafc"
  bg-dark: "#080d24"
  bg-dark-elevated: "#0f1a3a"
  border-light: "#e2e8f0"
  border-dark: "rgba(255,255,255,0.09)"
  status-approved: "#059669"
  status-pending: "#d97706"
  status-rejected: "#e11d48"
  chart-ink-blue: "#1e40af"
  chart-violet: "#8b5cf6"
  chart-pink: "#ec4899"
  chart-amber: "#f59e0b"
  chart-emerald: "#10b981"
  chart-cyan: "#06b6d4"
  chart-red: "#ef4444"
  chart-lime: "#84cc16"
typography:
  display:
    fontFamily: "'Inter Variable', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(3.5rem, 12vw, 7.5rem)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.04em"
  page-title:
    fontFamily: "'Inter Variable', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
  card-title:
    fontFamily: "'Inter Variable', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "'Inter Variable', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  reading:
    fontFamily: "'Source Serif 4 Variable', Georgia, 'Times New Roman', serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.65
  section-label:
    fontFamily: "'Inter Variable', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.05em"
  meta:
    fontFamily: "'Inter Variable', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.5rem"
  xl: "0.75rem"
  pill: "9999px"
  full: "9999px"
spacing:
  card-padding: "1.25rem"
  card-padding-lg: "1.5rem"
  page-gutter: "1.25rem"
  page-gutter-lg: "2.5rem"
  section-gap: "1.5rem"
  grid-gap: "1rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.lg}"
    padding: "0.5rem 1rem"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "#ffffff"
  button-primary-dark-mode:
    backgroundColor: "{colors.primary-solid-dark-mode}"
    textColor: "#ffffff"
  button-primary-dark-mode-hover:
    backgroundColor: "{colors.primary-solid-hover-dark-mode}"
    textColor: "#ffffff"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.body-light}"
    rounded: "{rounded.lg}"
    padding: "0.5rem 1rem"
  card:
    backgroundColor: "{colors.surface-light}"
    rounded: "{rounded.xl}"
    padding: "{spacing.card-padding}"
  badge:
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.5rem"
    textColor: "{colors.primary}"
---

# Design System: THESYS+

## 1. Overview

**Creative North Star: "The Institutional Reading Room"**

THESYS+ is the digital memory of PampangaStateU's College of Computing Studies. Its visual system should read like a well-run institutional library that happens to have a research-grade AI engine underneath: disciplined, legible, and quietly authoritative. The current implementation is a dual-mode (light/dark) React + Tailwind interface with a consistent card vocabulary and a single institutional ink-blue. It is clean and functional, and its grammar still leans on generic SaaS dashboards in places. This document captures what exists today so future work keeps the parts that serve the product and replaces the parts that signal "template."

The system has two visual personalities depending on theme. Dark mode is the more considered of the two: a deep navy base (`#080d24`) with elevated panels rendered as faint white glass (`rgba(255,255,255,0.03)`), giving a focused, low-glare reading environment. Light mode is safer and flatter: a `slate-50` page with white cards and subtle shadows. Both now come from one semantic token layer in `tokens.css`: a `.dark` class on `<html>` redefines every variable, and the authenticated pages (Repository, Title Similarity, Trend Analysis, Analytics, Profile, Settings, Thesis Detail) read text, border, surface and status colors from token classes instead of per-page `isDark` palettes. Text fields share one `.thesys-input` class, and the Landing page has been moved onto the same tokens. The photo-hero overlays on the Landing page, the chart internals, and the remaining auth pages (Reset Password, Setup Account, Verify Email, Request Access) still use `isDark` ternaries and have not been migrated.

What this system explicitly rejects (carried from PRODUCT.md anti-references): generic AI-SaaS landing pages (pulsing badge, giant clamp-scaled name, grid-glow background, hero-metric counters, identical feature-card grids); the Tailwind-starter look (blue-600 + slate-50 + white card + gray-500 muted text as the entire identity); consumer-app gamification; dark-mode-with-purple-gradients developer-tool aesthetics; and dashboard-as-default treatment of every page.

**Key Characteristics:**
- One semantic token layer (`tokens.css` → `tokens.js` → Tailwind) drives both themes; token classes (`text-ink`, `bg-surface`, `border-border-default`) replace `isDark` ternaries on the app pages
- A single institutional ink-blue carries nearly all brand weight; violet appears as a secondary accent
- Filled primary surfaces use a dedicated solid token, so the white label passes AA in both themes
- Card-and-panel surfaces are the dominant layout primitive on every page
- A four-channel status color language (emerald / amber / rose / blue) reused consistently for thesis status, similarity scores, and trend saturation, exposed as `success` / `warning` / `danger` / `info` tokens
- Inline SVG charts only — no chart library
- Two self-hosted typefaces: Inter Variable for the interface, Source Serif 4 Variable for the thesis abstract and legal prose only
- Every authenticated page shares one shell (`PageShell`) and one heading (`PageHeader`)

## 2. Colors

The palette is a disciplined ink-blue on slate and navy neutrals, with the standard emerald/amber/rose semantic trio and a violet secondary. The blue was moved off Tailwind's default `blue-600` to a deeper, archival ink-blue so the brand no longer reads as a starter template. It is consistent, though nothing here yet belongs specifically to PampangaStateU beyond the blue itself.

### Primary
- **Institutional Ink-Blue** (`#1e40af` light / `#60a5fa` dark): Text, links, active nav, focus rings and "AI-enabled" accent markers, from `--color-primary`. In dark mode it lightens to blue-400 (7.55:1 on the navy base) because it is used for text and rings. Never use it as a fill behind white text.
- **Solid Primary** (`#1e40af` light / `#2563eb` dark): Every filled primary action — Upload Thesis, Search, Validate Title, Save Changes — from `--color-primary-solid`. White label contrast is 8.7:1 in light and 5.2:1 in dark.
- **Primary Hover** (`#1c3a99` light / `#1d4ed8` dark): Darkened fill on button hover, from `--color-primary-solid-hover`, paired with a blue glow shadow.

### Secondary
- **Accent Violet** (`#7c3aed` / `#8b5cf6`): Used sparingly — the Title Similarity feature icon, the second slot in the chart palette. Defined as the shadcn `--accent` token but underused as a brand element.

### Tertiary (Status & Data)
- **Approved / Strict / Low-similarity Green** (`#059669` light, `#34d399` dark): Approved thesis status, "low similarity" (safe) validation result, underexplored topic clusters, strict-threshold slider zone. Token: `success`.
- **Pending / Balanced / Emerging Amber** (`#d97706` light, `#fbbf24` dark): Pending-review status, moderately-similar validation, emerging topic clusters, balanced-threshold zone. Token: `warning`.
- **Rejected / High-similarity Rose** (`#e11d48` light / `#f87171` dark): Rejected status, highly-similar (risk) validation, saturated topic clusters, all error states. Token: `danger`.
- **Informational Blue**: Keyword chips and neutral notices. Light uses the ink-blue tint (`info-bg` blue-50, `info-text` `#1c3a99`); dark uses a blue-500 tint at 10% with blue-300 text. Token: `info`.
- **Chart Palette** (8-color cycle): `#1e40af #8b5cf6 #ec4899 #f59e0b #10b981 #06b6d4 #ef4444 #84cc16`. A deliberate full-spectrum set for differentiating chart series, with slot 1 anchored to the brand ink-blue, shared identically between AnalyticsDashboard and TrendAnalysis (`CHART_PALETTE` in `tokens.js`).

### Neutral
- **Ink** (`#111827` light / `#ffffff` dark): Headings, primary values, thesis titles. Class: `text-ink`.
- **Body** (`#475569` light / `#d1d5db` dark): Paragraph and description text. Class: `text-body`.
- **Muted** (`#6b7280` light / `#9ca3af` dark): Section labels, sublabels, meta text. The dark value was raised specifically to pass AA (about 5.9:1 on the navy). Class: `text-muted`.
- **Subtle** (`#9ca3af` light / `#4b5563` dark): Separators and tick labels only, never readable copy. Class: `text-subtle`.
- **Surface** (`#ffffff` light / `rgba(255,255,255,0.03)` dark): Card and panel fills. Classes: `bg-surface`, `bg-surface-secondary`.
- **Page Background** (`#f8fafc` slate-50 light / `#080d24` navy dark; `#0f1a3a` for elevated dark surfaces like dropdowns, drawers, modals). Classes: `bg-canvas`, `bg-surface-elevated`.
- **Border** (`#e2e8f0` slate-200 light / `rgba(255,255,255,0.09)` dark). Classes: `border-border-default`, `border-border-strong` for buttons and inputs, `border-border-subtle` for inner dividers.

### Named Rules
**The One Blue Rule.** A single blue carries primary actions, links, active states, and AI-feature markers. Do not introduce a second "primary" color; the violet is a secondary accent, not a co-equal brand color.

**The Solid-Fill Rule.** A filled primary surface uses `bg-primary-solid` with `hover:bg-primary-solid-hover`. `bg-primary` is the text/ring blue and is too light behind a white label in dark mode (about 2.5:1).

**The Status Quartet Rule.** Emerald = good/safe/done, Amber = caution/pending/middle, Rose = risk/rejected/error, Blue = informational. This mapping is consistent across thesis status, similarity scoring, and trend saturation. Never reassign these meanings. Express them with the `success` / `warning` / `danger` / `info` token classes (`-bg`, `-border`, `-text`), not raw palette shades.

**The Token Source Rule.** `tokens.css` is the canonical palette. `tokens.js` exposes it to Tailwind, and the `--th-prim-*` ramp is the single place to change the brand blue. Do not add an `isDark ? 'text-gray-…' : 'text-gray-…'` pair for text, border, surface or status colors; use the token class. `isDark` remains acceptable for chart geometry, the Landing photo hero, and the auth pages not yet migrated.

## 3. Typography

**Display Font:** Inter Variable (self-hosted, Latin subset, weights 100–900, `font-display: swap`), falling back to `ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto`
**Body Font:** Same Inter Variable stack
**Reading Font:** Source Serif 4 Variable (`font-reading`), scoped to the thesis abstract on the detail page and the legal-modal prose only
**Label/Mono Font:** System mono only for the `⌘K` keyboard hint

**Character:** One neutral, highly legible sans across the product, so the interface reads the same on every operating system, with a single serif reserved for sustained reading. Hierarchy is built from size, weight, color, and letter-case. Tabular numerals are off by default and switched on with `tabular-nums` where figures align. The smallest text anywhere is 11px (`text-[11px]`); nothing functional goes below it.

### Hierarchy
- **Display** (800, `clamp(3.5rem, 12vw, 7.5rem)`, line-height 1, `-0.04em`): The landing-page "THESYS+" wordmark only. Two-color split: "THE" in ink, "SYS+" in blue. The only moment of typographic drama in the system; reaches ~7.5rem at wide viewports.
- **Page Title** (700, 1.5rem / `text-2xl`, `text-ink`): Every authenticated page heading through `PageHeader` — "Research Repository", "Title Similarity Validation", "Topic Trend Analysis", "Profile", "Account Settings". Identical weight, size, color and position on every route.
- **Card / Result Title** (600, 1rem–1.125rem / `text-base`–`text-lg`): Thesis card titles, feature card headings, cluster names. A thesis's own title on the detail page is content, not a page heading, and runs `text-2xl sm:text-3xl`.
- **Body** (400, 0.875rem / `text-sm`, line-height ~1.6): Descriptions and paragraph copy.
- **Reading** (400, `1.0625rem`, line-height 1.65, Source Serif 4): The thesis abstract, the most-read prose in the system, and legal prose. Keep measure near 65–75ch.
- **Section Label** (600, 0.75rem / `text-xs`, uppercase, `tracking-wider`, muted): The section-header treatment. It still appears on many panels across pages, about 28 occurrences.
- **Meta** (400, 0.75rem / `text-xs`): Program · year lines, author lists, timestamps, sublabels.

### Named Rules
**The Uppercase-Label Saturation Problem.** The `text-xs font-semibold uppercase tracking-wider` section label is applied to a large share of containers. When every section is labeled identically, the labels stop marking hierarchy and become visual wallpaper. Reserve this treatment for 2–3 genuine structural breaks per page.

**The Shared-Header Rule.** A new authenticated page wraps its content in `PageShell` and opens with `PageHeader`. Do not hand-write an `<h1>`; the title should land in the identical spot on every route so navigation produces no layout shift.

## 4. Elevation

The system uses a **hybrid** strategy that differs by theme. In light mode, depth comes from soft shadows (`0 1px 3px` on cards, lifting to `0 6px 20px` on hover) plus 1px slate borders. In dark mode, shadows are largely abandoned — depth comes from **tonal layering**: the navy base (`#080d24`), faint-white-glass panels (`rgba(255,255,255,0.03)`), and a more opaque elevated surface (`#0f1a3a`) for dropdowns, drawers, and modals. Borders carry most of the separation work in dark mode.

### Shadow Vocabulary
- **card** (`0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)`): Resting card elevation, light mode only.
- **card-lift** (`0 6px 20px -4px rgb(0 0 0 / 0.12)`): Hover state on interactive cards (`.thesys-card-lift`), paired with `translateY(-2px)`.
- **blue-glow** (`0 0 0 1px rgb(59 130 246 / 0.15), 0 4px 16px -4px rgb(59 130 246 / 0.25)`): Primary-button hover and focus emphasis.
- **dropdown / modal** (`0 8px 30px -4px rgb(0 0 0 / 0.12)` light, `0 8px 30px -4px rgb(0 0 0 / 0.6)` dark): Floating surfaces.

### Named Rules
**The Dark-Mode-Is-Flat Rule.** In dark mode, surfaces carry no shadow at rest. Elevation is communicated by background lightness (glass over navy) and border opacity, not by shadow. Only floating layers (dropdown, drawer, modal) get a dark shadow.

**The Hover-Lift Rule.** Interactive cards rise 2px and gain shadow (light) or a brighter glass fill + border (dark) on hover via `.thesys-card-lift`. Static informational cards do not lift.

## 5. Shapes

Corners follow the Tailwind radius scale as overridden in `tailwind.config.js`, driven by `--radius: 0.5rem`: `rounded-sm` `0.25rem`, `rounded-md` `0.375rem`, `rounded-lg` `0.5rem`, and Tailwind's default `rounded-xl` `0.75rem`. Buttons, inputs and small controls use `rounded-lg`; panels and cards use `rounded-xl`, though some cards still use `rounded-lg`, so card radius is not yet a single value. Chips and avatars are fully round (`9999px`). Borders are always 1px; there are no thick or colored side stripes. Clipping and custom masks are not part of the form language.

## 6. Components

### Buttons
- **Shape:** Rounded `0.5rem`–`0.75rem` (`rounded-lg` / `rounded-xl`).
- **Primary:** `bg-primary-solid text-white`, `px-4 py-2.5` typical. Hover swaps to `bg-primary-solid-hover` plus the blue glow; active scales to 0.98. Used for all main actions. About 35 call sites use this recipe.
- **Secondary / Ghost:** Transparent with a 1px `border-border-strong`, `text-body`, faint `hover:bg-surface-secondary`. Used for Cancel, Clear, secondary CTAs.
- **Focus:** Universal `focus-visible:ring-2 focus-visible:ring-primary`, consistent across the app in both themes.
- **Canonical class:** `.thesys-btn-primary` exists in CSS (and follows the solid tokens) but no JSX uses it; buttons are written as inline Tailwind. The shared `ui/Button` primitive is used only on the auth screens.

### Badges / Chips
- **Implementation:** shadcn `<Badge variant="outline">` is the primary chip (pill, `rounded-full`, `px-2 py-0.5`, `text-xs`). A `.thesys-chip` CSS class also exists but is unused in JSX, and TitleSimilarity renders some chips as raw `<span>`. **Three different chip implementations still coexist.**
- **Keyword chips:** `bg-info-bg text-info-text border-info-border`.
- **Status badges:** Status-quartet colored through the token classes (approved = success, pending = warning, rejected = danger), uppercase.
- **Semantic-score badges:** Color-graded by score (≥80% emerald, ≥60% amber, <60% blue) with a leading color dot, plus a tooltip showing the raw cosine value.
- **Trend badges:** Emoji (🔴/🟡/🟢) + label, color-coded by saturation. Color is never the only signal.

### Cards / Containers
- **Two near-identical classes:** `.thesys-card` (5 files) and `.thesys-panel` (2 files). Both are `rounded-xl`, 1px border, theme-tuned fill. The only difference is `.thesys-panel` includes `padding: 1.25rem` by default; `.thesys-card` takes padding from utilities. The semantic distinction is unclear and they are used interchangeably. Many pages also compose the same surface directly as `bg-surface border-border-default`.
- **Background:** White (light) / `rgba(255,255,255,0.03)` glass (dark).
- **Border:** slate-200 (light) / white-9% (dark).
- **Internal padding:** `p-4` to `p-8` depending on context; charts use the panel default `1.25rem`.
- **Anti-pattern present:** the landing-page "Cognitive Capabilities" 2×2 grid of identical icon+heading+text cards.

### Inputs / Fields
- **Style:** `.thesys-input` supplies the fill (`--color-surface`), 1px border, ink text and muted placeholder for both themes; each field adds its own `rounded-lg`, `text-sm`, `px-3/4 py-2.5`. Add `border-danger` for an error state.
- **Focus:** Border shifts to the primary blue and a 2px primary ring appears on `:focus-visible`, identical in light and dark.
- **Read-only:** Muted fill + `cursor-not-allowed` (Settings name/email fields) — but styled too similarly to editable fields to read as locked at a glance.
- **File inputs:** Tailwind `file:` pseudo-element styling with blue-tinted button.

### Navigation (AppNavbar)
- **Structure:** Sticky top bar, `backdrop-blur-md` over a 75%-opacity background. Three-column CSS grid on desktop (`grid-cols-[1fr_auto_1fr]`): logo+breadcrumb left, centered nav links, actions right. Below `lg`, a separate `flex justify-between` mobile row with a hamburger that opens a portal drawer.
- **Active state:** Pill background highlight (`nav-active-bg`: white/10 dark, gray-100 light) on the active link; `aria-current="page"` set. A separate `.thesys-nav-link` underline-indicator class exists in CSS but is unused.
- **Logo:** The approved `thesys-symbol.svg` mark plus the "THESYS+" wordmark, rendered by `ThesysLogo`.
- **Mobile drawer:** Left-side portal drawer, 72 width, backdrop blur, Escape-to-close, and focus trapped by `useFocusTrap`. Text-only links, no icons.
- **Avatar dropdown:** shadcn Avatar with initials fallback; dropdown lists Profile / Saved Theses / Settings / Sign Out, with a portal-rendered logout confirmation modal that also traps focus.

### Charts (inline SVG, no library)
- **HBarChart:** Horizontal bars, label + track + value, cycles the 8-color chart palette. Labels truncate at `w-36 sm:w-48`.
- **YearBarChart:** Vertical bars for year-over-year growth.
- **DoughnutChart:** Stroke-dasharray ring for topic distribution, center total label. Becomes illegible past ~8 segments; legend wraps into tiny truncated text.
- **CountsBarChart:** Horizontal bars for theses-per-topic.
- **Accessibility:** SVG roots carry `role="img"` and segments carry `<title>`. Text-summary alternatives for the data are not yet present.

### Signature Component: SimilaritySlider
A custom range input with a live percentage readout and a relevance pill that shifts emerald→amber→blue as the threshold drops (Strict ≥70 / Balanced 50–69 / Broad <50). The track fills with the zone color via a gradient. Cross-browser thumb styling is hand-written for WebKit and Firefox. Well-built and genuinely distinctive — one of the strongest components in the system.

### Loading & Empty States
- **Skeletons:** `.thesys-skeleton` shimmer (gradient sweep, 1.6s) replacing flat pulses. Shape-matched to the content they precede.
- **Soft-loading:** A small spinner + "Updating results…" badge when refreshing already-visible data, instead of a full skeleton (Repository, dashboards).
- **Empty states:** `.thesys-empty` — centered Lucide icon + heading + supporting line, consistent across Repository / Analytics / Trends.

### Auth Screens
`SignInCard` now uses the token classes (`text-ink`, `text-body`, `text-danger`) and the shared `ui/Input`, `ui/Button` and `ui/Alert` primitives, so it matches the app. The other auth pages (Forgot Password, Reset Password, Setup Account, Verify Email, Request Access) still build their surfaces from `isDark` ternaries and inline buttons, so they are the remaining place where the visual vocabulary can drift from the authenticated pages.

## 7. Do's and Don'ts

### Do:
- **Do** keep `focus-visible:ring-2 focus-visible:ring-primary` on every interactive element, including native `<select>` controls and dark-mode inputs.
- **Do** use the semantic token classes for neutral and status color: `text-ink`, `text-body`, `text-muted`, `text-subtle`, `bg-surface`, `border-border-default`, and `bg-success-bg` / `text-danger-text` style pairs.
- **Do** fill primary buttons with `bg-primary-solid` and `hover:bg-primary-solid-hover`, and give every text field the `.thesys-input` class.
- **Do** preserve the status-quartet color language (emerald/amber/rose/blue) and its consistent meaning across status, scoring, and trends.
- **Do** keep the dark-mode tonal-layering approach (navy base → glass panel → `#0f1a3a` elevated). It is the strongest part of the current visual identity.
- **Do** keep the SimilaritySlider, the shimmer skeletons, the soft-loading indicator, and the `.thesys-empty` pattern. These are well-built.
- **Do** keep the three-column navbar grid and the portal-rendered drawers/modals.
- **Do** open every authenticated page with `PageShell` + `PageHeader`.
- **Do** use `<Badge>` (shadcn) as the single canonical chip and migrate raw `<span>` chips to it.

### Don't:
- **Don't** put `bg-primary` behind white text. It is the light text/ring blue in dark mode; use `bg-primary-solid`.
- **Don't** ship `text-gray-500` body or label text on the `#080d24` dark background — it measures ~3.4:1 and fails WCAG AA for sub-18px text. Use `text-muted`, whose dark value is `#9ca3af`.
- **Don't** add new `isDark ? 'text-gray-…' : 'text-gray-…'` pairs for neutral text, borders or surfaces; use the token classes.
- **Don't** add a second typeface. Inter Variable is the UI face and Source Serif 4 is reserved for the thesis abstract and legal prose.
- **Don't** use overshooting (spring or bounce) easing. All motion eases out without overshoot (`--ease-out`, `--ease-smooth`); the academic register stays calm.
- **Don't** put gray secondary text on tinted status surfaces. Tint it from the surface's own hue (e.g. `text-success-text` on `bg-success-bg`).
- **Don't** reach for the `text-xs uppercase tracking-wider` section label on every panel. It is saturated; reserve it for 2–3 real structural breaks per page.
- **Don't** reproduce the generic AI-SaaS landing pattern: pulsing badge + giant name + grid-glow background + hero-metric stat row + 2×2 identical feature cards. (PRODUCT.md anti-reference.)
- **Don't** let the institution shrink to a footnote. PampangaStateU CCS deserves real visual presence beside the mark.
- **Don't** add a second "primary" color. One blue. Violet stays secondary. (The One Blue Rule.)
- **Don't** maintain two near-identical surface classes (`.thesys-card` vs `.thesys-panel`) without a clear semantic distinction. Consolidate.
- **Don't** use a doughnut chart for 8+ topic clusters. It is illegible at that count.
- **Don't** hand-write a page `<h1>`; use `PageHeader`.
