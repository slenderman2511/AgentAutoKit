# Keyboard, Focus & Dynamic Announcements

If it works only with a mouse, it's broken for keyboard users, many screen-reader users, and motor-impaired users. This is where a11y is won or lost.

## Full keyboard operability

- **Every interactive element is reachable and operable by keyboard.** Tab/Shift+Tab moves between controls; Enter activates links/buttons; Space activates buttons and toggles; arrow keys move *within* composite widgets (menus, tabs, radios, listboxes, sliders); Esc closes overlays.
- **Native elements handle this for you** — another reason to use `<button>`/`<a>` over `<div>`. Custom widgets must implement the expected keys (follow the ARIA Authoring Practices pattern for the widget).
- **No keyboard trap.** Focus must be able to leave every component (the one deliberate exception: an open modal traps focus *inside itself* until closed — see below).

## Tab order & tabindex

- **DOM order = tab order.** Keep the source order logical; don't use CSS to reorder in a way that scrambles focus (flexbox `order`/grid placement can desync visual and tab order — verify).
- **`tabindex="0"`** puts a custom interactive element in the natural tab order. **`tabindex="-1"`** makes an element programmatically focusable (via JS) but not tabbable — used for focus management (e.g. focusing a heading or an error).
- **Never use positive `tabindex`** (`tabindex="1"`+) — it hijacks the global order and creates chaos.
- Don't make non-interactive text focusable; don't add `tabindex` to `<div>`s you only want to click.

## Visible focus

- **Never remove focus indication without replacing it.** `outline: none` alone is a WCAG failure.
- Use **`:focus-visible`** to show a clear indicator for keyboard focus (and avoid a ring on mouse click if desired):

```css
:focus-visible { outline: 2px solid; outline-offset: 2px; }  /* ensure ≥3:1 contrast vs background */
```

- The focus indicator must meet contrast against adjacent colors and be clearly visible (WCAG 2.2 strengthens focus-appearance expectations). Don't let it get clipped by `overflow: hidden`.

## Skip link

The first focusable element on the page should let keyboard users bypass repeated nav:

```html
<a href="#main" class="skip-link">Skip to content</a>
...
<main id="main">…</main>
```

Style it visually hidden until focused (don't `display:none` it — that removes it from focus order). The label is user-facing → translate it (`i18n-best-practices`).

## Focus management for overlays

**Modals / dialogs** (`role="dialog"` `aria-modal="true"`, with `aria-labelledby` naming it):
1. On open, **move focus into the dialog** (the first field, or the dialog container/heading with `tabindex="-1"`).
2. **Trap focus** inside while open — Tab from the last element wraps to the first, and content behind is `inert`/`aria-hidden`.
3. **Esc closes** it.
4. On close, **restore focus** to the element that opened it. Losing focus to `<body>` is disorienting.
- The native `<dialog>` element + `showModal()` gives you most of this for free — prefer it.

**Menus / dropdowns / tabs / comboboxes**: use **roving tabindex** (one item `tabindex="0"`, rest `-1`) or `aria-activedescendant`; arrow keys move selection, Enter/Space selects, Esc closes and returns focus to the trigger. Keep `aria-expanded` on the trigger in sync.

## Announcing dynamic changes (ARIA live regions)

A visual-only update (toast, inline validation, "3 results found", async spinner) is silent to screen readers. Route it through a live region or a focus move:

- **`role="status"`** / `aria-live="polite"` — non-urgent updates (saved, results loaded); announced when the user is idle.
- **`role="alert"`** / `aria-live="assertive"` — urgent (form errors, failures); interrupts.
- The live region must **exist in the DOM before** you inject text (AT watches it for changes); update its text content to trigger the announcement. Don't toggle it from `display:none`.
- Keep messages concise; don't spam assertive regions.
- For validation, either move focus to the first invalid field (announces its label + error via `aria-describedby`) or summarize errors in an `alert` region.
- **Loading states**: announce "Loading…"/"Loaded" via `role="status"`, and manage focus so it doesn't get lost when content swaps in.
- **Route changes** in SPAs (Next.js client nav): move focus to the new page's `<h1>`/main and/or announce the new page title — otherwise a screen-reader user doesn't know the page changed.
