---
name: responsive-design
description: Apply responsive-design best practices so UI renders well across desktop, tablet, and mobile when writing, reviewing, or fixing any layout, page, or component. Covers mobile-first breakpoints and fluid layouts (grid/flex, container queries), responsive images & fluid typography (srcset/sizes, next/image, clamp), touch targets & pointer/hover handling, the viewport meta tag & iOS safe areas, preventing horizontal overflow, responsive tables/nav/modals, and verifying across viewports. Use when asked to "make this responsive", "fix mobile layout", "it looks broken on phone", "add breakpoints", "why is there horizontal scroll", "make the nav/table work on mobile", "improve tablet view", or when reviewing ANY UI that will be viewed on more than one screen size. Complements frontend-design (aesthetics) — this owns cross-device layout correctness. Treat findings as things to fix, not just flag.
user-invocable: false
---

# Responsive Design

Reference discipline for **making UI render correctly across screen sizes** — phone, tablet, desktop, and the awkward sizes between. `frontend-design` owns the *aesthetic* (typography, color, motion, boldness); this skill owns *does it hold up at every width*. Apply these when writing or reviewing any layout — treat findings as things to *fix*, not just flag.

This skill is framework-level and reusable. It states *what responsive-correct looks like* regardless of Tailwind, CSS Modules, or plain CSS. Neighbors: `frontend-design` (visual direction — pair the two), `next-best-practices` (image/font optimization, `next/image`), `i18n-best-practices` (translated text expands — Vietnamese/German strings run longer than English and must not break the layout), and `e2e-flow`/`playwright-best-practices` (driving real viewports to verify).

## Golden rules (never violate)

1. **Mobile-first.** Author base styles for the smallest screen, then add complexity upward with `min-width` breakpoints. Never start desktop-only and bolt on mobile — that's how you get horizontal scroll and cramped phones. Read [breakpoints-layout.md](./breakpoints-layout.md).
2. **The page never scrolls horizontally.** A visible horizontal scrollbar at any width is a bug. Fixed widths, unbroken long strings, oversized images, and negative margins are the usual causes. Constrain with `max-width: 100%`, `min-width: 0` on flex/grid children, and `overflow-x` only on the element that genuinely needs it. Read [breakpoints-layout.md](./breakpoints-layout.md).
3. **Ship the viewport meta tag.** `<meta name="viewport" content="width=device-width, initial-scale=1">` must be present, or mobile browsers render at a fake 980px width and everything looks tiny. Read [touch-interaction.md](./touch-interaction.md).
4. **Breakpoints follow content, not device names.** Add a breakpoint where *the layout breaks*, not at "iPhone width." There is no fixed device list to target — design for ranges. Read [breakpoints-layout.md](./breakpoints-layout.md).
5. **Fluid over fixed.** Prefer `%`, `fr`, `minmax()`, `clamp()`, `flex`, and `gap` over hardcoded pixel widths/heights. Let content reflow; don't pin it. Read [breakpoints-layout.md](./breakpoints-layout.md) and [media-typography.md](./media-typography.md).
6. **Touch targets ≥ 44×44px; never depend on hover.** Fingers aren't cursors. Interactive elements need adequate hit area and spacing, and any hover-only affordance (menus, tooltips, actions) needs a tap/focus equivalent. Read [touch-interaction.md](./touch-interaction.md).
7. **Images and media are responsive by default.** `max-width: 100%; height: auto`, real `width`/`height` (or aspect-ratio) to reserve space, and `srcset`/`sizes` (or `next/image`) so phones don't download desktop-sized files. Read [media-typography.md](./media-typography.md).
8. **Verify at real widths, not one.** "Looks fine on my laptop" is not verification. Check a small phone, a large phone, tablet, and desktop — and confirm no overflow, no clipping, readable text, reachable controls. Read [testing-checklist.md](./testing-checklist.md).

## Reference files

Consult these based on what you're doing:

### Layout, breakpoints, and overflow
[breakpoints-layout.md](./breakpoints-layout.md) — mobile-first strategy, choosing breakpoints from content (and Tailwind's `sm/md/lg/xl/2xl`), fluid grid/flex with `minmax()`/`auto-fit`/`gap`, container queries for component-level responsiveness, the horizontal-overflow causes & fixes (`min-width:0`, `max-width:100%`, word-breaking), and responsive patterns for nav, tables, cards, and modals.

### Images, media, and typography
[media-typography.md](./media-typography.md) — responsive images (`srcset`/`sizes`, `next/image`, `aspect-ratio` to prevent layout shift), fluid type with `clamp()` and a sensible scale, responsive spacing, line-length/readability, and keeping icons/SVG/video/embeds fluid.

### Touch, pointers, viewport, and input
[touch-interaction.md](./touch-interaction.md) — the viewport meta tag, touch-target sizing & spacing, `hover`/`any-pointer` media queries (don't strand touch users), iOS safe-area insets (`env(safe-area-inset-*)`) and notches, mobile forms (input types, 16px+ font to stop iOS zoom, the on-screen keyboard), and `prefers-reduced-motion`/`prefers-color-scheme`.

### Proving it works
[testing-checklist.md](./testing-checklist.md) — the audit → fix → verify protocol: the breakpoint matrix to check, driving real viewports with Playwright/DevTools, the red-flag list (horizontal scroll, tap targets, clipped text, fixed widths), and the "seen working on phone AND desktop" bar before calling it done.

## Correction workflow (short form)

When asked to "make this responsive / fix mobile / add breakpoints":

1. **Confirm the foundations**: viewport meta tag present, mobile-first CSS (base = small screen), no global fixed widths. See [touch-interaction.md](./touch-interaction.md) and [breakpoints-layout.md](./breakpoints-layout.md).
2. **Find what breaks**: load the target at ~360px and look for horizontal scroll, clipped/overlapping content, tiny tap targets, unreadable text, and desktop-sized images. Record each with file:line.
3. **Fix mobile-first**: convert fixed widths to fluid, add `min-width` breakpoints where content demands, apply the right pattern for nav/tables/cards, make images/media fluid, ensure touch targets and hover fallbacks. Remember translated text runs longer — leave room (see `i18n-best-practices`).
4. **Kill overflow**: chase any horizontal scroll to its source (`min-width:0` on flex/grid kids, `max-width:100%` on media, break long strings). See [breakpoints-layout.md](./breakpoints-layout.md).
5. **Verify across viewports**: small phone, large phone, tablet, desktop — no overflow, readable, reachable. A screenshot per breakpoint is the cheapest proof. See [testing-checklist.md](./testing-checklist.md).
