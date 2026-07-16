# Images, Media & Typography

Media that doesn't scale and type that doesn't reflow are the fastest ways to break a layout on a phone. Make both fluid.

## Responsive images

Two jobs: (1) never overflow the container, (2) don't ship desktop-sized bytes to a phone.

```css
/* Global guard — every image scales down, keeps ratio */
img, picture, video, svg { max-width: 100%; height: auto; }
```

- **Serve the right size** with `srcset`/`sizes` so the browser picks a file matched to the rendered width and DPR:

```html
<img
  src="hero-800.jpg"
  srcset="hero-400.jpg 400w, hero-800.jpg 800w, hero-1600.jpg 1600w"
  sizes="(min-width: 64rem) 50vw, 100vw"
  width="1600" height="900" alt="…" loading="lazy" />
```

- **Next.js**: use `next/image` — it does `srcset`, lazy-loading, and sizing for you. Always pass `sizes` for `fill`/responsive images, and give real `width`/`height` (or `aspect-ratio`) so space is reserved. See `next-best-practices`.
- **Always set `width`/`height` or `aspect-ratio`** to reserve space and prevent layout shift (CLS) as images load.
- `object-fit: cover` (with a fixed aspect box) for art-directed crops; `<picture>` with different `<source>` when the *crop itself* should change between mobile and desktop.
- `loading="lazy"` for below-the-fold images; keep the hero eager.
- Background images: `background-size: cover` + set an explicit box height (ideally via `aspect-ratio`), and consider `image-set()` for DPR.

## Fluid typography

Text should scale smoothly between breakpoints, not jump. Use `clamp()`:

```css
:root {
  --step-0: clamp(1rem, 0.9rem + 0.5vw, 1.125rem);    /* body */
  --step-2: clamp(1.5rem, 1.2rem + 1.5vw, 2.25rem);   /* heading */
}
h1 { font-size: var(--step-2); line-height: 1.1; }
p  { font-size: var(--step-0); line-height: 1.6; }
```

- `clamp(min, preferred, max)` — the `min` protects small screens, `max` stops giant text on ultrawide, the `vw` term scales in between. Include a `rem` in the preferred term so text still responds to the user's zoom/font-size setting (pure `vw` breaks accessibility zoom).
- **Use `rem`, not `px`,** for font sizes so users who set a larger default get larger text.
- **Line length**: cap measure at ~`60–75ch` (`max-width: 70ch`) for readable paragraphs — full-width text on desktop is hard to read.
- **Headings** need tighter `line-height` (1.05–1.2) than body (1.5–1.7); revisit at small sizes so long headings wrap gracefully.
- Tailwind: the `text-*` scale + arbitrary `text-[clamp(...)]`, or a fluid-type plugin.

## Responsive spacing

- Scale padding/margins with the viewport too — cramped desktop spacing feels wrong on mobile and vice-versa. `clamp()` or breakpoint-stepped spacing (`p-4 md:p-8 lg:p-12`).
- Use `gap` on flex/grid for consistent spacing that collapses cleanly when items wrap — avoid margin hacks.
- Section rhythm: generous vertical spacing on desktop, tighter on mobile; use `padding-block: clamp(2rem, 6vw, 6rem)`.

## Keep everything else fluid too

- **SVG/icons**: size in `em`/`rem` so they scale with surrounding text; set `width`/`height` or a `viewBox` + `max-width`.
- **Video / iframes / embeds** (YouTube, maps): wrap in an `aspect-ratio` box so they stay 16:9 and never overflow:

```css
.embed { aspect-ratio: 16 / 9; width: 100%; }
.embed > iframe { width: 100%; height: 100%; border: 0; }
```

- **Long content** (tables, code, `<pre>`): give it its own `overflow-x: auto` container rather than letting it push the page wide. See [breakpoints-layout.md](./breakpoints-layout.md).
- **Remember text expansion**: the same UI in Vietnamese or German is often 20–40% longer than English. Don't size buttons/labels to the English string — let them wrap or grow. See `i18n-best-practices`.
