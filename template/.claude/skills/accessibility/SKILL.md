---
name: accessibility
description: Apply web accessibility (a11y) best practices to WCAG 2.2 AA when writing, reviewing, or fixing any UI, component, page, or form. Covers semantic HTML & landmarks, correct ARIA (name/role/value, and the "no ARIA is better than bad ARIA" rule), keyboard operability & visible focus, focus management for modals/menus, color contrast & not-color-alone, text zoom/reflow, target size, accessible forms (labels, errors, autocomplete), alt text, live regions for dynamic updates, reduced motion, and the html lang attribute. Use when asked to "make this accessible", "fix a11y", "add ARIA", "keyboard navigation", "screen reader support", "check color contrast", "fix focus", "WCAG", "add alt text", "accessible form", or when reviewing ANY interactive or content UI. Complements frontend-design (aesthetics) and responsive-design (layout). Treat findings as things to fix, not just flag.
user-invocable: false
---

# Accessibility (a11y)

Reference discipline for **making UI usable by everyone** — keyboard users, screen-reader users, low-vision users, motor-impaired users, and anyone on assistive tech. The bar is **WCAG 2.2 level AA**. `frontend-design` owns how it looks and `responsive-design` owns how it reflows; this skill owns *can everyone actually operate and perceive it*. Apply these when writing or reviewing any UI — treat findings as things to *fix*, not just flag.

This skill is framework-level and reusable; the rules hold in React, plain HTML, or any framework. Neighbors: `frontend-design` (don't let aesthetics kill contrast/focus), `responsive-design` (zoom/reflow and target size overlap), and `i18n-best-practices` (the `lang` attribute, and translated `aria-label`s are strings too — never hardcode them).

## Golden rules (never violate)

1. **Semantic HTML first; ARIA only to fill gaps.** A real `<button>`, `<a href>`, `<nav>`, `<label>`, `<h1–h6>` comes with role, keyboard, and focus for free. **No ARIA is better than bad ARIA** — a wrong `role` or a `<div onClick>` with `role="button"` but no keyboard handler is worse than the native element. Read [semantics-aria.md](./semantics-aria.md).
2. **Everything works with the keyboard alone.** Every interactive element must be reachable by Tab, operable by Enter/Space (and arrows where appropriate), in a logical order, with no keyboard trap. If you can't do it without a mouse, it's broken. Read [keyboard-focus.md](./keyboard-focus.md).
3. **Focus is always visible.** Never `outline: none` without a stronger replacement. A keyboard user must always see where they are. Use `:focus-visible`. Read [keyboard-focus.md](./keyboard-focus.md).
4. **Every control has an accessible name.** Icon buttons, inputs, links — each needs a name a screen reader can announce (`<label>`, visible text, or `aria-label`/`aria-labelledby`). An unlabeled control is invisible to AT. Read [semantics-aria.md](./semantics-aria.md).
5. **Meet contrast, and never rely on color alone.** Text ≥ 4.5:1 (large text/UI components ≥ 3:1). Never convey meaning (error, status, required) by color only — pair it with text, icon, or shape. Read [visual-contrast.md](./visual-contrast.md).
6. **Images and media carry text alternatives.** Meaningful images need descriptive `alt`; decorative images get `alt=""`. Video needs captions. Read [semantics-aria.md](./semantics-aria.md).
7. **Announce dynamic changes.** Content that updates without a page load (toasts, validation, async results, loading) must reach AT via a live region or focus move — a silent visual-only update excludes screen-reader users. Read [keyboard-focus.md](./keyboard-focus.md).
8. **Respect the user's settings and set `lang`.** Honor `prefers-reduced-motion`; support zoom to 200%+ and reflow to 320px without loss; set `<html lang="vi">`/`"en"` so screen readers pronounce content correctly. Read [visual-contrast.md](./visual-contrast.md).

## Reference files

Consult these based on what you're doing:

### Semantics, ARIA, names/roles, forms, alt text
[semantics-aria.md](./semantics-aria.md) — semantic elements & landmark structure, heading hierarchy, the ARIA rules (native first, name/role/value, states like `aria-expanded`/`aria-selected`), accessible names, accessible forms (label association, `aria-describedby` for hints/errors, `aria-invalid`, `autocomplete`, fieldset/legend), and writing good `alt` text.

### Keyboard, focus, and dynamic announcements
[keyboard-focus.md](./keyboard-focus.md) — full keyboard operability, tab order & `tabindex` (0/-1 only, never positive), visible `:focus-visible`, skip links, focus management for modals/dialogs (trap + restore) and menus (roving tabindex, arrow keys, Esc), and ARIA live regions (`aria-live`, `role="status"`/`"alert"`) for toasts/validation/async.

### Contrast, color, zoom, motion, target size
[visual-contrast.md](./visual-contrast.md) — WCAG contrast ratios and how to check them, not-color-alone, text resize/zoom to 200% & 320px reflow, WCAG 2.2 target size (24×24 min), `prefers-reduced-motion`, `prefers-color-scheme`, and the `lang` attribute.

### Proving it works
[testing-checklist.md](./testing-checklist.md) — the audit → fix → verify protocol: the automated pass (axe/Lighthouse — catches ~30–40%), the keyboard-only pass, the screen-reader pass, the zoom/contrast pass, the red-flag list, and the "operable by keyboard AND announced by AT" bar before done.

## Correction workflow (short form)

When asked to "make this accessible / fix a11y / add ARIA":

1. **Check the structure**: is it built from semantic elements (`button`/`a`/`nav`/`label`/headings) or `div`/`span` soup? Fix the foundation before adding ARIA. See [semantics-aria.md](./semantics-aria.md).
2. **Do a keyboard-only pass**: unplug the mouse, Tab through the feature. Note anything unreachable, out-of-order, trapped, or with invisible focus. See [keyboard-focus.md](./keyboard-focus.md).
3. **Check names & alternatives**: every control announces a name; every meaningful image has `alt`; dynamic updates announce. Record each gap with file:line.
4. **Check perception**: contrast ratios, color-not-alone, zoom to 200% / reflow to 320px, target sizes. See [visual-contrast.md](./visual-contrast.md).
5. **Fix** foundation-up (semantics → names → keyboard/focus → live regions → contrast). Remember AT labels are translatable strings (see `i18n-best-practices`).
6. **Verify** with automated tooling *and* an actual keyboard + screen-reader pass — automated tools alone miss ~60%. See [testing-checklist.md](./testing-checklist.md).
