# Touch, Pointers, Viewport & Input

Desktop assumes a mouse, hover, and a physical keyboard. Mobile has none of those. These are the platform details that make a layout actually *usable* on a phone, not just visually shrunk.

## The viewport meta tag (non-negotiable)

Without it, mobile browsers render the page at a fake ~980px width and scale it down — everything looks tiny and the whole "responsive" CSS is ignored.

```html
<meta name="viewport" content="width=device-width, initial-scale=1" />
```

- In Next.js App Router, set it via the `viewport` export (or `metadata.viewport`) — don't hand-write a conflicting tag.
- **Do not** disable zoom (`maximum-scale=1, user-scalable=no`) — it's an accessibility failure. Let users pinch-zoom.
- Use `viewport-fit=cover` **only** when you're handling safe-area insets (below), e.g. for edge-to-edge designs on notched phones.

## Touch targets

- **Minimum 44×44px** (iOS HIG) / 48×48px (Material) hit area for anything tappable — buttons, links, icons, checkboxes. A 16px icon needs padding to reach that.
- **Spacing between targets**: at least ~8px so fingers don't hit the wrong one. Dense desktop toolbars must loosen on mobile.
- Small inline links in body text get a pass, but primary actions must be comfortably tappable.
- Extend hit area without visual bulk via padding or a `::before` overlay, not by enlarging the visible icon.

## Hover and pointer — don't strand touch users

Hover doesn't exist on touch. Any affordance that only appears on `:hover` (dropdown menus, "show actions" on a row, tooltips) is invisible/unusable on a phone. Provide a tap/focus path, and gate hover-only enhancements behind a query:

```css
/* Apply hover styles ONLY where a hover-capable pointer exists */
@media (hover: hover) and (pointer: fine) {
  .row:hover .actions { opacity: 1; }
}
/* Touch/coarse pointers get the actions always-visible or via tap */
@media (pointer: coarse) { .actions { opacity: 1; } }
```

- `hover: hover` = device can hover; `pointer: coarse` = finger, `pointer: fine` = mouse/stylus.
- Never rely on hover to reveal essential content or navigation.
- Ensure `:focus-visible` states exist for keyboard users alongside hover.

## iOS safe areas & notches

Edge-to-edge content on notched/rounded phones can hide behind the notch, home indicator, or rounded corners. With `viewport-fit=cover`, pad using the safe-area env vars:

```css
.app-bar   { padding-top: max(1rem, env(safe-area-inset-top)); }
.bottom-nav{ padding-bottom: max(0.5rem, env(safe-area-inset-bottom)); }
```

Matters most for sticky headers, bottom navs/tab bars, and full-screen modals.

## Mobile forms & the on-screen keyboard

- **Use the right `inputmode`/`type`** so the correct keyboard appears: `type="email"`, `type="tel"`, `inputmode="numeric"` (OTP/amounts), `type="url"`. Also improves autofill.
- **Font-size ≥ 16px on inputs** — iOS Safari auto-zooms into any input with smaller text, jarring the layout. Never set form fields below 16px.
- **The keyboard covers the bottom half of the screen** — ensure the focused field scrolls into view and submit buttons aren't permanently hidden behind it. Test with the keyboard open. Prefer `100dvh`/`100svh` over `100vh` so layout accounts for the dynamic mobile toolbar/keyboard (plain `100vh` overflows on mobile).
- Labels stay visible (don't rely on placeholder-as-label); error messages must fit and not overflow.
- Autocomplete attributes (`autocomplete="one-time-code"`, `name`, `email`) speed up mobile entry.

## Respect user & system preferences

- **`prefers-reduced-motion`**: gate non-essential animation so motion-sensitive users (and low-power devices) aren't overwhelmed:

```css
@media (prefers-reduced-motion: reduce) { *, ::before, ::after { animation: none !important; transition: none !important; } }
```

- **`prefers-color-scheme`**: support light/dark if the design does — mobile users switch modes often. (Coordinate with `frontend-design`.)
- **`dvh`/`svh`/`lvh` units** handle the mobile browser chrome expanding/collapsing; use them for full-height sections instead of `vh`.
