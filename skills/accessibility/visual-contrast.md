# Contrast, Color, Zoom, Motion & Target Size

Perception accessibility: making sure people with low vision, color blindness, motion sensitivity, or motor limits can actually see and hit the UI. This is where `frontend-design`'s aesthetics must not win at a11y's expense.

## Color contrast (WCAG AA)

Minimum contrast ratios:

- **Normal text**: ≥ **4.5:1** against its background.
- **Large text** (≥ 24px, or ≥ 18.66px/14pt bold): ≥ **3:1**.
- **UI components & graphical objects** (input borders, icons that convey meaning, focus indicators, chart segments you must distinguish): ≥ **3:1** against adjacent colors.
- **AAA** (stricter, aim where feasible): 7:1 normal / 4.5:1 large.

Rules:
- **Check real rendered colors**, including text over images/gradients (add a scrim/overlay if needed) and hover/disabled/placeholder states. Placeholder text and light-gray "subtle" labels are the usual failures.
- Use a contrast checker (browser DevTools shows the ratio in the color picker; axe/Lighthouse flag failures).
- Don't trust a swatch — semi-transparent text and overlapping layers change the effective ratio.

## Never rely on color alone

Color must not be the *only* way information is conveyed (people with color blindness or low vision miss it):

- **Form errors**: red border **plus** an error message and/or icon — not just red.
- **Status** (success/pending/failed): color **plus** a label or icon/shape.
- **Links in body text**: distinguish by more than color (underline them) so they're identifiable without hue perception.
- **Charts/legends**: differentiate series by pattern, label, or direct annotation, not color alone. (See the `dataviz` guidance if charts are involved.)
- **Required fields**: text or `*` with a text explanation, not a red label only.

## Text resize, zoom & reflow

- **Zoom to 200%** must not lose content or functionality (WCAG 1.4.4). Build with relative units (`rem`/`em`) and fluid layout so text scales — overlaps directly with `responsive-design`.
- **Reflow (1.4.10)**: at 320px-equivalent width, content reflows to a single column with **no horizontal scrolling** for reading (two-directional scroll only for things like data tables/maps). This is the same discipline as `responsive-design`'s "no horizontal overflow."
- **Text spacing (1.4.12)**: layout must survive users overriding line-height/letter/word spacing — avoid fixed-height text containers that clip.
- Don't disable browser zoom (`user-scalable=no` is a failure — see `responsive-design`'s viewport note).

## Target size (WCAG 2.2)

- **Minimum 24×24px** CSS for pointer targets (2.5.8, AA), with spacing so adjacent targets don't overlap — or provide an equivalent larger target. (Touch guidance in `responsive-design` recommends 44px, which comfortably satisfies this.)
- Applies to buttons, icon controls, checkboxes, close buttons, small "×" chips. Enlarge hit area with padding rather than shrinking the visible mark.

## Motion & animation

- **Respect `prefers-reduced-motion`** — gate non-essential animation, parallax, auto-playing motion:

```css
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; scroll-behavior: auto !important; }
}
```

- **No content flashes more than 3×/second** (seizure risk, WCAG 2.3.1).
- **Auto-playing/moving content** (carousels, marquees, auto-advancing) lasting >5s needs a pause/stop/hide control (2.2.2).
- Don't convey information *only* through motion.

## System preferences & language

- **`prefers-color-scheme`**: if you offer dark mode, ensure *both* themes meet contrast — dark mode often regresses contrast on muted text.
- **`<html lang="vi">` / `"en"`**: set the page language so screen readers use correct pronunciation; set `lang` on any inline passage in a different language. This ties directly to `i18n-best-practices` — the active locale should drive the `lang` attribute.
- Don't fight OS-level settings (font size, contrast, reduced transparency) with hard overrides.
