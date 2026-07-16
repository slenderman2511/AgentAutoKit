# Layout, Breakpoints & Overflow

The core of responsive: a layout that reflows cleanly from 320px to ultrawide, with breakpoints placed where content needs them and zero horizontal scroll.

## Mobile-first, always

Author the base (no media query) for the **smallest** screen, then layer complexity upward with `min-width`:

```css
/* base = mobile: single column */
.grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
/* enhance upward */
@media (min-width: 48rem)  { .grid { grid-template-columns: repeat(2, 1fr); } }  /* tablet */
@media (min-width: 64rem)  { .grid { grid-template-columns: repeat(4, 1fr); } }  /* desktop */
```

Why min-width not max-width: mobile is the constrained case and the most common device — get it right first, then *add* for bigger screens. Starting desktop-first (`max-width`) means overriding everything back down and is the #1 source of broken phone layouts.

Tailwind is mobile-first by design: unprefixed = all sizes; `sm:`/`md:`/`lg:`/`xl:`/`2xl:` apply **from that width up**. So `class="grid-cols-1 md:grid-cols-2 lg:grid-cols-4"` is the snippet above.

## Choosing breakpoints — content, not devices

Add a breakpoint **where the layout starts to look wrong**, not at a specific phone's pixel width. Device sizes change every year; content doesn't. Resize the browser slowly and watch for the first sign of strain (line length too long, cards too wide/narrow, nav crowding) — put a breakpoint there.

Tailwind's defaults are a fine starting scale (`sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536`), but treat them as ranges to design *between*, and add custom ones when content demands. Use `rem` for breakpoints so they respect the user's font size.

## Fluid layout primitives

Prefer intrinsically responsive CSS that needs *fewer* breakpoints:

```css
/* Responsive grid with NO media queries — wraps automatically */
.cards { display: grid; gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr)); }

/* Flex that wraps and lets children shrink */
.row { display: flex; flex-wrap: wrap; gap: 1rem; }
.row > * { flex: 1 1 16rem; min-width: 0; }   /* min-width:0 lets them shrink below content size */
```

- `minmax(min(16rem, 100%), 1fr)` — cards are ≥16rem but never overflow a narrow screen (the `min(…, 100%)` guard).
- `fr`, `%`, `flex`, `gap`, `clamp()` over fixed `px` widths. Use `max-width` on containers (`max-width: 72rem; margin-inline: auto`) instead of fixed `width`.
- Use logical properties (`margin-inline`, `padding-block`) so layouts also work under RTL locales (see `i18n-best-practices`).

## Container queries — responsive per component, not per page

When a component (a card, a sidebar widget) must adapt to **its container's** width rather than the viewport, use container queries. Essential for reusable components that live in different-width slots:

```css
.card-wrap { container-type: inline-size; }
@container (min-width: 24rem) { .card { display: grid; grid-template-columns: auto 1fr; } }
```

Tailwind: `@container` + `@sm:`/`@md:` variants. Reach for this instead of viewport media queries whenever the component's layout depends on where it's placed, not on the screen.

## Killing horizontal overflow (no page-level x-scroll)

A horizontal scrollbar at any width is a bug. Common causes → fixes:

- **Flex/grid child won't shrink** → add `min-width: 0` (flex items default to `min-width: auto`, refusing to shrink below content). The single most common fix.
- **Fixed-width element** (`width: 800px`) → use `max-width: 100%` / `width: 100%` with a `max-width` cap.
- **Oversized media** → `img, video, svg { max-width: 100%; height: auto; }` globally.
- **Unbreakable long string** (URL, token, no-space text) → `overflow-wrap: anywhere` (or `word-break: break-word`) on the text container.
- **Negative margins / `100vw`** wider than the content area (scrollbar width) → prefer `100%`; if using `100vw` full-bleed, account for scrollbar.
- **Debug**: temporarily add `* { outline: 1px solid red; }` or scan for the culprit — the widest element sticking past the viewport edge is the offender.

Put `overflow-x: auto` **only** on the specific element that must scroll (a wide data table, a code block), never as a blanket fix on `body` — that hides the real bug.

## Responsive patterns for common components

- **Navigation**: full horizontal nav on desktop → hamburger/drawer or bottom-nav on mobile. Ensure the menu button is a real focusable `<button>` with an accessible label, and the menu is reachable by keyboard and touch.
- **Tables**: wide tables don't fit phones. Options: wrap in `overflow-x: auto` (with a scroll hint), collapse to stacked cards (each row → a labeled card), or hide non-essential columns at small widths. Never let a table force the whole page to scroll.
- **Cards / galleries**: `auto-fit` + `minmax` grid (above) reflows column count automatically.
- **Modals / dialogs**: on mobile, prefer full-screen or bottom-sheet over a tiny centered box; cap with `max-height` + internal scroll; keep the close control in reach of the thumb.
- **Two-column → stacked**: sidebars and split layouts collapse to a single column on mobile; decide the source order so the important content comes first in the DOM (screen readers and mobile both read top-down).
