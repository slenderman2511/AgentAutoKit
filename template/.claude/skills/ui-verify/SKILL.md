---
name: ui-verify
description: Verify UI changes AFTER implementation — catch broken layouts at mobile/tablet/desktop breakpoints, compute WCAG color contrast under every theme/variant the component ships in, and enforce the project's design-system rules (no hardcoded colors, bg↔text pairing, the prohibitions listed in CLAUDE.md "## Design system"). Use after implementing or changing any component/page UI, before the review gate, or when asked to "check the UI", "verify the UI", "the layout is broken", "text is unreadable / washed out", or to verify responsive/contrast/theme compliance. Three passes — static code check, computed contrast, live Playwright check — each with pass/fail evidence. Not a creative skill (that's frontend-design), not a full a11y audit (that's accessibility), not a pre-code UX mockup (that's ui-prototype).
---

# UI verification after implement (web)

Run this on the UI diff of the current change, not the whole app. Three passes, in order —
static is cheapest, live is most expensive. Report a pass/fail table with evidence; a fail
means fix and re-run, not a footnote. It runs before the review gate
(`.claude/rules/workflow.md`, Orchestrator rule 5) and does not replace it.

## Where the rules come from

This skill is the *checker*; the project owns the rules:

- `CLAUDE.md` → **"## Design system"**: where tokens/theme classes live, which themes/variants a
  shared component must be checked under (light/dark, brand themes…), and the project's design
  prohibitions.
- Any UI rule files in `.claude/rules/*` (design language, theming, responsive), and
  `AGENTS.md` if present.
- `.claude/rules/general.md` → "Before submitting": all UI states handled; no hardcoded
  environment-, tenant- or customer-specific values.

If "## Design system" is missing, fall back to the tokens actually defined in the codebase (CSS
custom properties in the global stylesheet, `tailwind.config.*` / `@theme`, theme classes or
`[data-theme]` selectors) and **say so in the report** ("no Design system section — checked
against tokens in `<file>`"). When this skill and a project rule file disagree, the rule file
wins; update this skill.

## Pass 1 — Static (grep the diff, read the code)

Token & theming compliance:

- **No hardcoded colors** in components: grep the diff for `#[0-9a-fA-F]{3,8}`, `rgb(`, `hsl(`,
  and raw Tailwind palette classes (`bg-gray-`, `bg-white`, `text-black`, `bg-slate-`…).
  Everything must go through the project's tokens (semantic utilities, `var(--token)`, theme
  classes) — otherwise switching the theme doesn't switch the color.
- **Every container background is paired with an explicit text class**: each surface/bg
  utility has its matching on-surface text token set on the texts inside — never inherited from
  an ancestor painted on a different surface. This is the white-on-white bug class; treat a
  bare container as a fail even if it "looks fine" in the theme you happened to test.
- **Project prohibitions**: every rule listed under "## Design system" (banned elements such
  as borders/dividers or shadows, restricted accent-color usage, alignment/typography rules) is
  a check — grep for the banned classes, read for the rest.
- **No per-brand/per-customer conditionals**: no `if (tenantId === …)` / `if (brand === …)`
  styling — config/theme-driven only.

States & interaction:

- All states handled: loading (`if (loading && !data)` only — never blank already-rendered data
  on refetch), error (never swallowed), empty (contextual), buttons `disabled={isSubmitting}` +
  indicator.
- Interactive elements are `<button>`/`<Link>` (never `<div onClick>`), navigation is
  `<Link href>`, `touch-manipulation` present, tap targets ≥44px (e.g. `p-3 md:p-2`).
- Tables wrapped in `overflow-x-auto`; images/iframes have explicit dimensions.

## Pass 2 — Contrast (compute, never eyeball)

Compute WCAG ratios for every bg↔text pair the diff introduces or touches:

```
L = 0.2126·R + 0.7152·G + 0.0722·B   (sRGB channels linearized: c/12.92 if c≤0.03928
                                       else ((c+0.055)/1.055)^2.4, c = channel/255)
ratio = (L_lighter + 0.05) / (L_darker + 0.05)
```

Thresholds (WCAG AA): **4.5:1** normal text · **3:1** large text (≥24px, or ≥18.66px
bold) and UI components/focus indicators. Quick script: a few lines of node in the
scratchpad — paste the hex pairs, print ratios; the `accessibility` skill
(`visual-contrast.md`) has the full reference. Semi-transparent colors: composite them over the
real surface first, then compute.

**⚠️ Check per theme/variant, not once.** A shared component renders under every theme/variant
listed in "## Design system" — resolve the actual color values of the tokens the component
uses from **each** theme block (the CSS variables per theme class / `.dark` / `[data-theme]`
selector, or the Tailwind theme) and compute the ratio for **each** theme. The same token pair
can pass on the dark theme and fail on the light one. Report the worst theme.

Colors injected at runtime (brand/user-configured values written into a CSS variable from
data) can't be precomputed — flag any text sitting on such a variable for a runtime check with
real config.

## Pass 3 — Live (Playwright MCP against the dev server)

With the dev server running (`npm run dev`; in a worktree, `worktree-dev` covers env files and
ports), for each changed page/component route (`browser_navigate`):

1. **Breakpoints**: `browser_resize` to **375×812** (mobile), **768×1024** (tablet),
   **1280×800** (desktop). At each:
   - **Overflow probe** (`browser_evaluate`):
     `document.documentElement.scrollWidth > document.documentElement.clientWidth`
     → any horizontal overflow = broken layout. Then locate the offender:
     elements whose `getBoundingClientRect().right > window.innerWidth`.
     (Usual causes and fixes: `responsive-design`, `breakpoints-layout.md`.)
   - **Screenshot and actually look at it** (`browser_take_screenshot`): clipped/overlapping
     text, truncation that hides meaning, wrapped buttons, invisible text (the bg↔text pairing
     bug shows up here), broken grids.
2. **Themes**: re-screenshot under each theme/variant the component ships in — switch the
   project's theme hook (a class on `<html>`/`<body>`, a `data-theme` attribute) via
   `browser_evaluate`, faster than reconfiguring the app; for OS-driven dark mode use
   `browser_emulate_media`. At minimum: the darkest and the lightest. Single-theme project →
   skip.
3. **States**: trigger reachable loading/empty/error states (throttle, empty filters,
   bad id) and screenshot.
4. **Console**: `browser_console_messages` — hydration mismatches and React key errors
   count as fails.

## Report

| Check | Result | Evidence |
|---|---|---|
| Tokens / bg↔text pairing | PASS/FAIL | file:line |
| Prohibitions | PASS/FAIL | file:line |
| States | PASS/FAIL | which state missing |
| Contrast (worst theme) | PASS/FAIL | pair, theme, ratio vs threshold |
| Layout 375 / 768 / 1280 | PASS/FAIL | overflow px + screenshot |
| Console clean | PASS/FAIL | message |

Fails → fix → re-run the failed pass only. Findings that reveal a rule gap (a case the
project's rules don't cover) → propose the edit to "## Design system" or the relevant
`.claude/rules/*` file in the same PR, so the rules stay current with the code.
