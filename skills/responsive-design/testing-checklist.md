# Responsive Review Checklist — audit → fix → verify

"Looks fine on my laptop" is not verification. This is the protocol for proving a UI holds up from phone to desktop. Ends at *seen working at multiple widths*, not *should work*.

## 1. Foundations (check first — cheap, high-impact)

- [ ] Viewport meta tag present (`width=device-width, initial-scale=1`), zoom not disabled. See [touch-interaction.md](./touch-interaction.md).
- [ ] CSS is mobile-first (base styles = smallest screen; `min-width` breakpoints add up). See [breakpoints-layout.md](./breakpoints-layout.md).
- [ ] No global fixed `width` on containers; layout uses `max-width` + fluid units.
- [ ] Global media guard present (`img, video, svg { max-width: 100%; height: auto }`).

## 2. The breakpoint matrix (check every affected screen at each)

Don't target specific devices — check a **spread of widths** and the transitions between:

- [ ] **~320–360px** (small phone) — the hardest case; most bugs show here.
- [ ] **~390–430px** (large phone).
- [ ] **~768px** (tablet / portrait).
- [ ] **~1024px** (tablet landscape / small laptop).
- [ ] **~1280px+** (desktop) and one **ultrawide** (~1920px) — content shouldn't stretch unreadably.
- [ ] **Resize slowly through the whole range** — the breakpoints themselves are where things snap or overlap.

## 3. At each width, confirm

- [ ] **No horizontal scroll** on the page (the cardinal sin). See overflow fixes in [breakpoints-layout.md](./breakpoints-layout.md).
- [ ] Nothing clipped, cut off, or overlapping; no content hidden behind sticky bars/notch.
- [ ] Text is readable (size, line length, contrast) and long/translated strings wrap without breaking layout.
- [ ] Images/media scale, keep aspect ratio, and don't cause layout shift.
- [ ] Tap targets ≥44px with enough spacing; hover-only affordances have a touch/focus equivalent. See [touch-interaction.md](./touch-interaction.md).
- [ ] Nav, tables, modals use their responsive pattern (drawer, scroll/stack, sheet) — not a shrunken desktop version.
- [ ] Forms usable: correct keyboard, 16px+ inputs (no iOS zoom), fields reachable with keyboard open.

## 4. Drive real viewports (don't eyeball one size)

- **Browser DevTools** device toolbar — quick manual pass; toggle a coarse-pointer/touch emulation.
- **Playwright** — automate the matrix and capture proof (pairs with `e2e-flow`/`playwright-best-practices`):

```ts
for (const [w, h] of [[360, 800], [768, 1024], [1280, 800]]) {
  await page.setViewportSize({ width: w, height: h });
  await page.goto('/target');
  // assert no horizontal overflow:
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: `target-${w}.png`, fullPage: true });
}
```

- A **screenshot per breakpoint** is the cheapest, most convincing proof — attach mobile + desktop.
- Use the kit's `run` skill to launch the app, or Playwright to script the sweep.

## 5. Red flags (stop and fix before shipping)

- Any **horizontal scrollbar** at any width.
- A **fixed pixel width** (`width: 800px`, `min-width: 1200px`) on a layout container.
- **Missing viewport meta tag** (page renders tiny on mobile).
- Content **only tested at one width** ("works on my screen").
- **Hover-only** menus/actions with no touch path; tap targets smaller than a fingertip.
- **Inputs under 16px** (iOS zoom) or fields hidden behind the keyboard.
- Desktop-sized **images shipped to phones** (no `srcset`/`next/image`).
- `100vh` sections that overflow on mobile (use `dvh`/`svh`).
- A **table or `<pre>`** forcing the whole page to scroll sideways.
- Layout that **breaks when text is longer** (untested with Vietnamese/translated copy — see `i18n-best-practices`).
