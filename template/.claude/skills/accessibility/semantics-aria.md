# Semantics, ARIA, Names, Forms & Alt Text

The foundation of accessibility is correct HTML. Get the semantics right and most of a11y is free; get them wrong and no amount of ARIA rescues it.

## Semantic HTML first

Use the element that means what you intend. Native elements bring role, keyboard operability, and focus behavior for free:

- Actions → `<button>` (not `<div onClick>`). Navigation to a URL → `<a href>`.
- Structure → `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`, `<section>`, `<article>`.
- Lists → `<ul>/<ol>/<li>`; tabular data → `<table>` with `<th scope>`.
- Forms → `<form>`, `<label>`, `<fieldset>/<legend>`, `<input>/<select>/<textarea>`.

**The `<div onClick>` trap**: a clickable div is not focusable, not keyboard-operable, and has no role. If you truly can't use `<button>`, you must add `role="button"`, `tabindex="0"`, **and** key handlers for Enter/Space — three things a `<button>` gives you for nothing. Almost always: just use the button.

## Landmarks & heading structure

- **One `<main>`** per page; wrap primary nav in `<nav>`; use landmarks so AT users can jump between regions. Multiple same-type landmarks need distinguishing labels (`<nav aria-label="Primary">`, `<nav aria-label="Footer">`).
- **Headings form an outline**: exactly one `<h1>` per page (the page's topic), then `<h2>`/`<h3>` nested by meaning — **don't skip levels** (no `<h1>` → `<h3>`) and don't pick a heading level for its font size (style with CSS). Screen-reader users navigate by heading; a broken outline breaks navigation.
- Provide a **skip link** ("Skip to content") as the first focusable element (see [keyboard-focus.md](./keyboard-focus.md)).

## ARIA — rules of use

ARIA describes roles/states to AT but adds **zero** behavior. Misused, it actively misleads.

1. **First rule of ARIA: don't use ARIA if a native element works.** `<button>` > `<div role="button">`.
2. **Don't change native semantics.** No `<h2 role="tab">`; wrap or restructure instead.
3. **Name, Role, Value** — every custom control must expose:
   - **Role**: what it is (`role="tab"`, `role="dialog"`, `role="switch"`).
   - **Name**: what it's called (accessible name — below).
   - **Value/State**: its current state, kept in sync as it changes — `aria-expanded` (disclosure/menu), `aria-selected` (tab/option), `aria-checked` (switch/checkbox), `aria-current` (current page/step), `aria-disabled`, `aria-pressed` (toggle).
4. **Keep state attributes updated in code.** `aria-expanded="false"` that never flips to `"true"` is a lie to the screen reader. Toggle it whenever the visual state changes.
5. **`aria-hidden="true"`** removes an element from the accessibility tree — use it to hide decorative/duplicate content, **never** on a focusable element (creates a "focusable but invisible to AT" ghost).
6. Prefer following an established **ARIA Authoring Practices** pattern (dialog, tabs, combobox, menu, accordion) rather than inventing widget semantics.

## Accessible names

Every interactive element and meaningful image needs a name AT can announce. In priority order:

- **Visible text content** (best): `<button>Save</button>`, `<a href>Pricing</a>`.
- **`<label>` associated** with a form control (below).
- **`aria-labelledby`** pointing at visible text elsewhere, or **`aria-label`** when there's no visible text (e.g. an icon-only button: `<button aria-label="Close">✕</button>`).
- **Icon-only controls are the #1 offender** — a bare `<button><svg/></button>` announces as "button", nothing else. Always name them. (And that label is user-facing text → translate it, see `i18n-best-practices`.)

## Accessible forms

- **Every input has a programmatically associated label.** `<label for="email">Email</label><input id="email">` or wrap the input in the `<label>`. Placeholder is **not** a label (disappears on type, poor contrast).
- **Group related controls** with `<fieldset>` + `<legend>` (radio groups, address blocks).
- **Hints & errors**: link them with `aria-describedby="hintId errorId"` so AT reads them with the field. Mark invalid fields `aria-invalid="true"`.
- **Errors**: identify the field in text (not color alone — see [visual-contrast.md](./visual-contrast.md)), and surface them to AT (focus the first error or announce via a live region — see [keyboard-focus.md](./keyboard-focus.md)). WCAG 2.2 also expects accessible authentication (don't force memorizing/transcribing) and not re-asking info already provided.
- **`autocomplete`** attributes (`email`, `name`, `tel`, `one-time-code`) help everyone, especially motor/cognitive users and password managers.
- **Required**: use the `required` attribute; if you show `*`, also convey it in text/`aria-required`, not color alone.

## Alt text

- **Meaningful image** → `alt` describes its content/purpose concisely ("Bar chart: revenue up 20% in Q2"), not "image of…".
- **Decorative image** → `alt=""` (empty, present) so AT skips it. Never omit the attribute entirely.
- **Image of text** → avoid; if unavoidable, `alt` contains the exact text.
- **Functional image** (image inside a link/button) → `alt` describes the *action/destination*, not the picture.
- **Icons**: decorative inline icon → `aria-hidden="true"`; icon that *is* the control → give the control a name (above).
- **Complex images** (charts, diagrams) → short `alt` + a longer description nearby or via `aria-describedby`.
