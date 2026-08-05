---
name: THESYS+
description: Semantic thesis retrieval and topic trend analysis for PampangaStateU CCS
colors:
  primary: "#2563eb"
  primary-hover: "#1d4ed8"
  primary-dark-mode: "#60a5fa"
  accent-violet: "#7c3aed"
  ink-light: "#111827"
  ink-dark: "#ffffff"
  body-light: "#475569"
  body-dark: "#9ca3af"
  muted-light: "#6b7280"
  muted-dark: "#6b7280"
  surface-light: "#ffffff"
  surface-dark: "rgba(255,255,255,0.03)"
  bg-light: "#f8fafc"
  bg-dark: "#080d24"
  bg-dark-elevated: "#0f1a3a"
  border-light: "#e2e8f0"
  border-dark: "rgba(255,255,255,0.09)"
  status-approved: "#10b981"
  status-pending: "#f59e0b"
  status-rejected: "#e11d48"
  chart-blue: "#3b82f6"
  chart-violet: "#8b5cf6"
  chart-pink: "#ec4899"
  chart-amber: "#f59e0b"
  chart-emerald: "#10b981"
  chart-cyan: "#06b6d4"
  chart-red: "#ef4444"
  chart-lime: "#84cc16"
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(3.5rem, 12vw, 7.5rem)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.04em"
  page-title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
  card-title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  section-label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.05em"
  meta:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: "0.375rem"
  md: "0.5rem"
  lg: "0.75rem"
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
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "#ffffff"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.body-light}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
  card:
    backgroundColor: "{colors.surface-light}"
    rounded: "{rounded.lg}"
    padding: "{spacing.card-padding}"
  badge:
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.5rem"
    textColor: "{colors.primary}"
---

# Design System: THESYS+

## 1. Overview

**Creative North Star: "The Institutional Reading Room"**

THESYS+ is the digital memory of PampangaStateU's College of Computing Studies. Its visual system should read like a well-run institutional library that happens to have a research-grade AI engine underneath: disciplined, legible, and quietly authoritative. The current implementation is a competent dual-mode (light/dark) React + Tailwind interface with a consistent card vocabulary and a single signature blue. It is clean and functional, but it currently borrows its grammar from generic SaaS dashboards rather than from academic systems. This document captures what exists today so future work can keep the parts that serve the product and replace the parts that signal "template."

The system has two visual personalities depending on theme. Dark mode is the more considered of the two: a deep navy base (`#080d24`) with elevated panels rendered as faint white glass (`rgba(255,255,255,0.03)`), giving a focused, low-glare reading environment. Light mode is safer and flatter: a `slate-50` page with white cards and subtle shadows. Both are driven entirely by an `isDark` boolean threaded through every component, producing two hand-tuned palettes rather than a single token set that adapts.

What this system explicitly rejects (carried from PRODUCT.md anti-references): generic AI-SaaS landing pages (pulsing badge, giant clamp-scaled name, grid-glow background, hero-metric counters, identical feature-card grids); the Tailwind-starter look (blue-600 + slate-50 + white card + gray-500 muted text as the entire identity); consumer-app gamification; dark-mode-with-purple-gradients developer-tool aesthetics; and dashboard-as-default treatment of every page.

**Key Characteristics:**
- Dual hand-tuned themes (light + dark) gated on an `isDark` boolean, not adaptive CSS variables
- A single signature blue carries nearly all brand weight; violet appears as a secondary accent
- Card-and-panel surfaces are the dominant layout primitive on every page
- A four-channel status color language (emerald / amber / rose / blue) reused consistently for thesis status, similarity scores, and trend saturation
- Inline SVG charts only — no chart library
- System font stack throughout — zero typographic identity
- Tokens are placeholders; the real palette lives as hardcoded Tailwind hex values in JSX

## 2. Colors

The palette is a Tailwind default spectrum: blue-600 as primary, a violet secondary, and the standard emerald/amber/rose semantic trio. It is competent and consistent but carries no institutional identity — nothing here belongs specifically to PampangaStateU.

### Primary
- **Signature Blue** (`#2563eb` light / `#60a5fa` dark): Every primary action — Upload Thesis, Search, Validate Title, Save Changes — plus active nav pills, links, focus rings, and the "AI-enabled" accent markers. In dark mode it lightens to blue-400 for contrast against the navy base. This is Tailwind's `blue-600`, the single most-used SaaS accent of the era.
- **Primary Hover** (`#1d4ed8`): Darkened blue on button hover, paired with a blue glow shadow.

### Secondary
- **Accent Violet** (`#7c3aed` / `#8b5cf6`): Used sparingly — the Title Similarity feature icon, the second slot in the chart palette. Defined as the shadcn `--accent` token but underused as a brand element.

### Tertiary (Status & Data)
- **Approved / Strict / Low-similarity Green** (`#10b981` light, `#34d399` dark): Approved thesis status, "low similarity" (safe) validation result, underexplored topic clusters, strict-threshold slider zone.
- **Pending / Balanced / Emerging Amber** (`#f59e0b` light, `#fbbf24` dark): Pending-review status, moderately-similar validation, emerging topic clusters, balanced-threshold zone.
- **Rejected / High-similarity Rose** (`#e11d48` / `#f87171`): Rejected status, highly-similar (risk) validation, saturated topic clusters, all error states.
- **Chart Palette** (8-color cycle): `#3b82f6 #8b5cf6 #ec4899 #f59e0b #10b981 #06b6d4 #ef4444 #84cc16`. A deliberate full-spectrum set for differentiating chart series, shared identically between AnalyticsDashboard and TrendAnalysis.

### Neutral
- **Ink** (`#111827` light / `#ffffff` dark): Headings, primary values, thesis titles.
- **Body** (`#475569`/gray-600 light / `#9ca3af`/gray-400 dark): Paragraph and description text.
- **Muted** (`#6b7280`/gray-500 both modes): Section labels, sublabels, meta text. **This is the contrast risk** — see Do's and Don'ts.
- **Surface** (`#ffffff` light / `rgba(255,255,255,0.03)` dark): Card and panel fills.
- **Page Background** (`#f8fafc` slate-50 light / `#080d24` navy dark; `#0f1a3a` for elevated dark surfaces like dropdowns, drawers, modals).
- **Border** (`#e2e8f0` slate-200 light / `rgba(255,255,255,0.09)` dark).

### Named Rules
**The One Blue Rule.** A single blue carries primary actions, links, active states, and AI-feature markers. Do not introduce a second "primary" color; the violet is a secondary accent, not a co-equal brand color.

**The Status Quartet Rule.** Emerald = good/safe/done, Amber = caution/pending/middle, Rose = risk/rejected/error, Blue = informational. This mapping is consistent across thesis status, similarity scoring, and trend saturation. Never reassign these meanings.

**The Placeholder Token Rule.** `tokens.css` and `tokens.js` are explicitly marked `PLACEHOLDER pending Figma palette`. The live palette is hardcoded Tailwind hex in JSX. Treat the real values in this document as canonical, not the token files.

## 3. Typography

**Display Font:** System UI stack (`system-ui, -apple-system, 'Segoe UI', Roboto`)
**Body Font:** Same system stack
**Label/Mono Font:** System mono only for the `⌘K` keyboard hint

**Character:** There is no typographic identity. The product renders in whatever UI font the operating system provides — Segoe UI on Windows, San Francisco on macOS, Roboto on Android. Hierarchy is built entirely from size, weight, color, and letter-case rather than typeface character. This is the single largest gap between the current state and an "institutional reading room" identity.

### Hierarchy
- **Display** (800, `clamp(3.5rem, 12vw, 7.5rem)`, line-height 1, `-0.04em`): The landing-page "THESYS+" wordmark only. Two-color split: "THE" in ink, "SYS+" in blue. The only moment of typographic drama in the system; reaches ~7.5rem at wide viewports.
- **Page Title** (700, 1.5rem / `text-2xl`): Every authenticated page heading — "Research Repository", "Topic Trend Analysis", "Account Settings". All identical weight and size; no per-page differentiation.
- **Card / Result Title** (600, 1rem–1.125rem / `text-base`–`text-lg`): Thesis card titles, feature card headings, cluster names.
- **Body** (400, 0.875rem / `text-sm`, line-height ~1.6): All descriptions, abstracts, paragraph copy. Note: the thesis abstract — the most-read prose in the system — is set at this same `text-sm`, which is undersized for sustained reading.
- **Section Label** (600, 0.75rem / `text-xs`, uppercase, `tracking-wider`, muted gray): The universal section-header treatment. Appears on nearly every panel on every page: "Research by Program", "Top Keywords", "Topic Distribution", "Abstract", "Keywords", "General", "Account". Heavily overused.
- **Meta** (400, 0.75rem / `text-xs`): Program · year lines, author lists, timestamps, sublabels.

### Named Rules
**The Uppercase-Label Saturation Problem.** The `text-xs font-semibold uppercase tracking-wider` section label is applied to nearly every container in the system. When every section is labeled identically, the labels stop marking hierarchy and become visual wallpaper. Reserve this treatment for 2–3 genuine structural breaks per page.

**The Flat Page-Title Rule (current state, not aspirational).** Every page title is `text-2xl` bold with a `text-sm` muted subtitle. There is no scale variation between a search engine page and a dashboard page; the type system provides no wayfinding.

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

## 5. Components

### Buttons
- **Shape:** Rounded `0.5rem`–`0.75rem` (`rounded-lg` / `rounded-xl`).
- **Primary:** Solid blue-600, white text, `px-4 py-2.5` typical. Hover darkens to blue-700 + blue glow; active scales to 0.98. Used for all main actions.
- **Secondary / Ghost:** Transparent with a 1px border (white/15 dark, gray-200/300 light), muted text, fills faintly on hover. Used for Cancel, Clear, secondary CTAs.
- **Focus:** Universal `focus-visible:ring-2 focus-visible:ring-blue-400` — consistent and correct across the entire app.
- **Canonical class:** `.thesys-btn-primary` exists in CSS but most buttons are written as inline Tailwind; the class is inconsistently adopted.

### Badges / Chips
- **Implementation:** shadcn `<Badge variant="outline">` is the primary chip (pill, `rounded-full`, `px-2 py-0.5`, `text-xs`). A `.thesys-chip` CSS class also exists but is unused in the main pages, and TitleSimilarity renders some chips as raw `<span>`. **Three different chip implementations coexist.**
- **Keyword chips:** Blue-tinted (`bg-blue-50` / `bg-blue-500/10`).
- **Status badges:** Status-quartet colored (approved=emerald, pending=amber, rejected=rose), uppercase.
- **Semantic-score badges:** Color-graded by score (≥80% emerald, ≥60% amber, <60% blue) with a leading color dot, plus a tooltip showing the raw cosine value.
- **Trend badges:** Emoji (🔴/🟡/🟢) + label, color-coded by saturation.

### Cards / Containers
- **Two near-identical classes:** `.thesys-card` and `.thesys-panel`. Both are `rounded-xl`, 1px border, theme-tuned fill. The only difference is `.thesys-panel` includes `padding: 1.25rem` by default; `.thesys-card` takes padding from utilities. The semantic distinction is unclear and they are used interchangeably.
- **Background:** White (light) / `rgba(255,255,255,0.03)` glass (dark).
- **Border:** slate-200 (light) / white-9% (dark).
- **Internal padding:** `p-4` to `p-8` depending on context; charts use the panel default `1.25rem`.
- **Anti-pattern present:** the landing-page "Cognitive Capabilities" 2×2 grid of identical icon+heading+text cards.

### Inputs / Fields
- **Style:** `rounded-lg`, 1px border, theme-tuned fill (`bg-white` light / `bg-white/[0.04]` dark), `text-sm`, `px-3/4 py-2.5`.
- **Focus:** Border shifts to blue (`focus:border-blue-400` light adds `ring-2 ring-blue-100`; dark uses `focus:border-blue-500/40`).
- **Read-only:** Muted fill + `cursor-not-allowed` (Settings name/email fields) — but styled too similarly to editable fields to read as locked at a glance.
- **File inputs:** Tailwind `file:` pseudo-element styling with blue-tinted button.

### Navigation (AppNavbar)
- **Structure:** Sticky top bar, `backdrop-blur-md` over a 75%-opacity background. Three-column CSS grid on desktop (`grid-cols-[1fr_auto_1fr]`): logo+breadcrumb left, centered nav links, actions right. Below `lg`, a separate `flex justify-between` mobile row with a hamburger that opens a portal drawer.
- **Active state:** Pill background highlight (`bg-white/10` dark, `bg-gray-100` light) on the active link; `aria-current="page"` set. A separate `.thesys-nav-link` underline-indicator class exists in CSS but the navbar uses the pill style instead.
- **Logo:** 🎓 emoji in a tinted rounded square + "THESYS+" wordmark. The emoji carries the entire institutional/brand load.
- **Mobile drawer:** Left-side portal drawer, 72 width, backdrop blur, Escape-to-close. **Does not trap focus** (accessibility gap). Text-only links, no icons.
- **Avatar dropdown:** shadcn Avatar with initials fallback; dropdown lists Profile / Saved Theses / Settings / Sign Out, with a portal-rendered logout confirmation modal.

### Charts (inline SVG, no library)
- **HBarChart:** Horizontal bars, label + track + value, cycles the 8-color chart palette. Labels truncate at `w-36 sm:w-48`.
- **YearBarChart:** Vertical bars for year-over-year growth.
- **DoughnutChart:** Stroke-dasharray ring for topic distribution, center total label. Becomes illegible past ~8 segments; legend wraps into tiny truncated text.
- **CountsBarChart:** Horizontal bars for theses-per-topic.
- **Accessibility gap:** charts have `<title>` on segments but no `role="img"` + `aria-label` on the SVG root, and no text-summary alternative.

### Signature Component: SimilaritySlider
A custom range input with a live percentage readout and a relevance pill that shifts emerald→amber→blue as the threshold drops (Strict ≥70 / Balanced 50–69 / Broad <50). The track fills with the zone color via a gradient. Cross-browser thumb styling is hand-written for WebKit and Firefox. Well-built and genuinely distinctive — one of the strongest components in the system.

### Loading & Empty States
- **Skeletons:** `.thesys-skeleton` shimmer (gradient sweep, 1.6s) replacing flat pulses. Shape-matched to the content they precede.
- **Soft-loading:** A small spinner + "Updating results…" badge when refreshing already-visible data, instead of a full skeleton (Repository, dashboards).
- **Empty states:** `.thesys-empty` — centered Lucide icon + heading + supporting line, consistent across Repository / Analytics / Trends.

### Inconsistent Component: SignInCard
**The clearest design-system violation in the codebase.** SignInCard does not use any THESYS+ tokens. It uses `bg-white dark:bg-gray-800`, `rounded-lg shadow-md`, `text-red-600`, generic `text-gray-700 dark:text-gray-300`, and a "Welcome!" heading. It belongs to a different, earlier design vocabulary (generic gray scale, no navy, no `.thesys-*` classes) and looks like a different product than the authenticated pages.

## 6. Do's and Don'ts

### Do:
- **Do** keep the `focus-visible:ring-2 focus-visible:ring-blue-400` pattern on every interactive element. It is consistent and correct.
- **Do** preserve the status-quartet color language (emerald/amber/rose/blue) and its consistent meaning across status, scoring, and trends.
- **Do** keep the dark-mode tonal-layering approach (navy base → glass panel → `#0f1a3a` elevated). It is the strongest part of the current visual identity.
- **Do** keep the SimilaritySlider, the shimmer skeletons, the soft-loading indicator, and the `.thesys-empty` pattern. These are well-built.
- **Do** keep the three-column navbar grid and the portal-rendered drawers/modals.
- **Do** use `<Badge>` (shadcn) as the single canonical chip and migrate raw `<span>` chips to it.

### Don't:
- **Don't** ship `text-gray-500` body or label text on the `#080d24` dark background — it measures ~3.4:1 and fails WCAG AA for sub-18px text. Bump to at least `text-gray-400`.
- **Don't** rely on the system font stack as the final identity. Load one typeface; the abstract reading experience and brand character both depend on it.
- **Don't** reach for the `text-xs uppercase tracking-wider` section label on every panel. It is saturated; reserve it for 2–3 real structural breaks per page.
- **Don't** reproduce the generic AI-SaaS landing pattern: pulsing badge + giant name + grid-glow background + hero-metric stat row + 2×2 identical feature cards. (PRODUCT.md anti-reference.)
- **Don't** let the 🎓 emoji carry institutional identity. PampangaStateU CCS deserves real visual presence, not a footnote string.
- **Don't** add a second "primary" color. One blue. Violet stays secondary. (The One Blue Rule.)
- **Don't** keep SignInCard on its divergent `bg-gray-800` / `text-red-600` vocabulary. Bring it onto the navy + `.thesys-*` system.
- **Don't** maintain two near-identical surface classes (`.thesys-card` vs `.thesys-panel`) without a clear semantic distinction. Consolidate.
- **Don't** use a doughnut chart for 8+ topic clusters. It is illegible at that count.
- **Don't** ship the mobile drawer without focus trapping, or charts without `role="img"` + `aria-label`. Both are WCAG gaps.
- **Don't** use Tailwind's default `blue-600` as the brand color long-term — it is the AI-SaaS template tell. Commit to a deliberate institutional color. (PRODUCT.md anti-reference.)
