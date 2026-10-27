# Mobile and tablet audit (plan D, Task 1)

Measured 2026-10-27 on 5174/8001, light mode, signed in as a faculty test account.
Each page loaded in a same-origin iframe at 375×812, 430×932, 768×1024 and 1024×1366; values come from
`getComputedStyle` / `getBoundingClientRect`, not eyeballing. Script: scratchpad `audit.js` (iframe width = viewport width, so media queries and the root `clamp()` respond as on a device; `pointer: coarse` is not emulated).

## Headline

- **Horizontal scroll: none.** No page scrolls sideways at any of the four widths.
- **Gutter: one mismatch.** Every band on every page starts at 20px (phone) / 32px (768) / 56px (1024), except the landing hero text at 32 / 48 / 64. Other "lefts" in the raw data are card insets, not bands.
- **Text under 12px: 6 pages + upload modal.** All from `text-[11px]` (and one 10px label on Trend Analysis).
- **Taps under 40px on phones: every signed-in page,** mostly the shared navbar.

## Findings, ranked by pages hit

| # | Page(s) | Width | Problem | Proposed fix | Status |
|---|---|---|---|---|---|
| 1 | All signed-in pages + landing (navbar) | 375, 430 | Menu and theme buttons 36px, logo link 28px, avatar 32px, landing "Sign In" 32px | `max-sm:min-h-10` / `max-sm:size-10` on these in `AppNavbar.jsx` | Fixed in e823bb1 |
| 2 | Repository, Title Similarity, Trend Analysis, Analytics, Settings, Upload modal | all | `text-[11px]` / 10px text: slider scale and pill (`SimilaritySlider.jsx`), result labels (`TitleSimilarityPage.jsx`, 10 uses), bar labels (`AnalyticsDashboardPage.jsx:133,145`, 14 labels), "Change Photo" (`SettingsPage.jsx:182`), "THESES" label (Trend Analysis, 10px), modal section labels | `text-[11px]` → `text-xs` everywhere (27 uses, 11 files); find and lift the 10px label | Fixed in e823bb1. "THESES" kept: SVG text in the donut's viewBox, scales with the chart |
| 3 | Navbar dropdown, search suggestions, profile badge, request access stepper, trend badge | all | Same `text-[11px]`, not on screen during the scan (inside menus or other states) | Same swap, found by grep | Fixed in e823bb1 |
| 4 | Landing | 375, 430, 768 | Hero text gutter `px-8 sm:px-12` sits 12–16px right of every other band | `px-5 sm:px-8 lg:px-16 xl:px-20` (`LandingPage.jsx:476`) | Fixed in e823bb1 |
| 5 | Repository | 375 | Keyword chips 26px tall; "Cite", "Cited by", status link and pagination under 40px | `max-sm:min-h-10` on chips and Cite | Cite, Cited by, status link, pagination fixed in 4629581. Chips fixed in d8a1ad9 (option B: 26px look, invisible 40px tap area, 16px row gap on phones) |
| 6 | Title Similarity | 375 | "Type a Title" / "Upload Title" tabs 32px | `max-sm:min-h-10` | Fixed in 9f9acf5 |
| 7 | Sign in (+ reset / setup password) | 375 | Auth header logo 28px and theme 36px; submit 36px; "Show password" 20px; "Forgot your password?" 20px | `max-sm:min-h-10`; enlarge the eye button's hit area | Fixed in 1ad4a02 (eye button gets `max-sm:p-2.5`, icon stays put) |
| 8 | Analytics | 375 | "View Reviewed…" link 14px tall | `max-sm:min-h-10` / `inline-flex items-center` | Fixed in 319ad7e |
| 9 | Trend Analysis, Settings, Profile | 375 | Buttons at 36–38px ("Explore text clusters", "Reviewed subjects", "Cancel", "Save Changes", "Edit Profile") | `max-sm:min-h-10` | Fixed in d72aefe, f0af8e4, a0a878a |
| 10 | Landing, sign-in card, role picker | all | `text-[15px]` (7) and `text-[13px]` (5): off-scale but not under the floor | `text-[15px]` → `text-sm sm:text-base`; `text-[13px]` → `text-sm` | Not changed: above the floor, and 15→16px would change desktop |
| 11 | Profile | 375 | Thesis-title links in "My theses" lists are 20px tall (one clamped line) | `max-sm:min-h-10` | Fixed in d8a1ad9 (option B: invisible tap area over title and meta, 47px; rows unchanged) |

## Re-run after Task 2 and Task 3

375×812 on Landing, Sign in, Repository, Title Similarity, Trend Analysis, Analytics, Profile, Settings; plus 812×375 and 820×1180 on Landing, Repository, Analytics, Trend Analysis:

- Horizontal scroll: none. Text under 12px outside SVG: none. Every page's H1 starts at the gutter (20px phone, 32px at 812/820).
- Taps under 40px on phones: none, apart from inline links inside sentences. Chips and Profile title links measured by elementFromPoint: 40px and 47px tap areas, no overlap; 22px with no extra area at 1280.
- Review Focus: (1) 812×375 landing and pages fit with no sideways scroll; the hero grows past `100svh` rather than clipping. (2) At 820×1180 the landing H1 sits at y≈896 because plan A's stacked sign-in card comes first; that's plan A's layout, not this plan's. (3) Analytics and Trend Analysis never scroll the page sideways at 375. (4) No input classes changed, so the `pointer: coarse` 16px rule is untouched. (5) Repository cards show no overflow at 375; Thesis detail still unmeasured (see Gaps).

Not flagged: inline text links inside paragraphs (Request Access, Forgot password, thesis titles in Profile lists). They sit inside running text where a 40px box would break the line; WCAG 2.5.8 exempts inline targets.

## Gaps

- **Thesis detail: not measured.** The page fails to compile on the current working tree (`ThesisDetailPage.jsx:218`, a `'…isn't…'` string from an uncommitted plain-language edit). Re-run after that edit is fixed.
- **Upload modal: grep only.** The test account's navbar did not expose the upload button inside the iframe, so the modal is covered by the static `text-[11px]` grep (3 uses), not by measurement.
- **PageHeader:** H1 wrapping was not measured; the titles are one or two words ("Repository", "Analytics"), so `PageHeader.jsx:20` stays `text-2xl` unless Task 3 finds a wrap.

## Tester question

Ask the alpha tester which pages felt off (and on which device). Their answer re-ranks this table.
