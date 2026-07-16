# Accessibility Review Checklist — audit → fix → verify

Automated tools catch only ~30–40% of WCAG issues. Real verification needs a keyboard pass and a screen-reader pass. This is the protocol; it ends at *operated by keyboard AND announced by AT*, not *should be accessible*.

## 1. Automated pass (fast, first — but not sufficient)

- [ ] Run **axe** (axe DevTools / `@axe-core/playwright`) or **Lighthouse** accessibility audit on the target. Fix every reported violation.
- [ ] Wire axe into the e2e suite so regressions fail CI (pairs with `e2e-flow`/`playwright-best-practices`):

```ts
import AxeBuilder from '@axe-core/playwright';
const results = await new AxeBuilder({ page }).analyze();
expect(results.violations).toEqual([]);
```

- [ ] Check the HTML validates and has no duplicate `id`s (breaks `for`/`aria-*` associations).
- ⚠️ Passing axe ≠ accessible. It can't judge whether alt text is *meaningful*, focus order is *logical*, or a name *makes sense*. Continue to the manual passes.

## 2. Keyboard-only pass (the highest-value manual check)

Put the mouse away. Tab through the whole feature:

- [ ] Every interactive element is **reachable** by Tab and **operable** (Enter/Space/arrows/Esc as appropriate).
- [ ] **Focus is always visible** and never lost to `<body>`.
- [ ] **Tab order is logical** and matches visual order.
- [ ] **No keyboard trap** (except an intentional modal, which must trap *and* release on close).
- [ ] Modals/menus: focus moves in on open, Esc closes, focus returns to the trigger on close.
- [ ] Skip link works and is the first focusable element.

## 3. Screen-reader pass

Use a real screen reader — **VoiceOver** (macOS: Cmd+F5), **NVDA** (Windows, free), or TalkBack/VoiceOver on mobile:

- [ ] Every control **announces a meaningful name and role** ("Close, button" — not just "button").
- [ ] **State changes are announced** (`aria-expanded`, selected, checked) as you operate widgets.
- [ ] **Headings/landmarks** let you navigate the page structure; the outline makes sense.
- [ ] **Images**: meaningful ones announce useful `alt`; decorative ones are skipped.
- [ ] **Dynamic updates** (toasts, validation, async results, route changes) are announced via live regions / focus.
- [ ] **Forms**: labels, hints, and errors are read with their fields; invalid fields are identifiable.

## 4. Perception pass

- [ ] **Contrast**: text ≥4.5:1 (large ≥3:1), UI components/focus ring ≥3:1 — including placeholder, disabled, hover, and text-over-image states. See [visual-contrast.md](./visual-contrast.md).
- [ ] **Not color alone**: errors/status/links/required convey meaning without relying on hue.
- [ ] **Zoom to 200%** and **reflow at 320px**: no content/functionality lost, no reading requiring horizontal scroll.
- [ ] **Target size** ≥24×24 (prefer 44px).
- [ ] **`prefers-reduced-motion`** honored; nothing flashes >3×/s; auto-moving content has a pause.
- [ ] **`<html lang>`** set to the active locale.

## 5. Red flags (stop and fix before shipping)

- `<div>`/`<span>` used as buttons/links (no role, not focusable, no keyboard).
- `outline: none` with no visible replacement focus style.
- Icon-only button/link with **no accessible name**.
- Input with **no associated `<label>`** (placeholder-as-label).
- **Positive `tabindex`**, or `aria-hidden="true"` on a focusable element.
- `aria-expanded`/`aria-selected`/`aria-checked` that **never updates** in code.
- Meaning conveyed by **color only** (red-border-only errors).
- Contrast below AA (gray-on-white "subtle" text is the classic).
- **Modal** that doesn't trap focus, doesn't close on Esc, or doesn't restore focus.
- **Dynamic content** (toast/validation/async) that updates silently for AT.
- Missing **`<html lang>`**, missing **viewport** allowing zoom.
- Accessible name / `alt` **hardcoded in one language** (should be translated — see `i18n-best-practices`).
