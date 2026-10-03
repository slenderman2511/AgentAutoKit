---
name: e2e-visual-proof
description: Use when an end-to-end run needs PROOF with pictures — screenshot every meaningful step of a real user journey (desktop, phone, or both), fix visible UI bugs found in the shots, and publish ONE self-contained review page (step gallery + API evidence table + honest notes) for the PR/issue. Runs as the camera of the L-tier e2e pass (layer 3 of e2e-flow) and feeds step 1 of the UI design-conformance loop. Triggers: "run e2e and capture each step", "screenshot the e2e steps", "e2e proof for the reviewer", "prove the feature works end to end".
---

# e2e-visual-proof — step screenshots → one review page

**Core idea:** a reviewer trusts pictures of the REAL flow on the REAL dev stack more than a green
checkmark. Run the e2e user journey (`e2e-flow`), shoot every meaningful step in the viewport(s) the
user chose, look at them, fix what is visibly broken, then publish ONE self-contained page.

**REQUIRED SUB-SKILL:** `e2e-flow` — how this repo's dev server, env and Playwright specs run.

## Step 0 — ASK before anything runs (one question)

1. **Viewport** — `Web desktop (1280×800)` · `Phone responsive (390×844)` · `Both`. Never pick for the
   user — it changes the spec, the run time and the page layout. (Native mobile apps: add a
   project-specific lane file next to this skill; it replaces Step 2.)
2. **Dev writes** — if the journey writes to a shared dev/staging backend, ask Yes/No in the SAME
   question (project, what gets seeded, cleaned up after). This is the e2e gate — don't ask twice.

## Step 1 — A fixture that can be re-run

Real-write e2e is one-shot: once scenario 1 registers/pays/approves, it can't replay. Keep ONE
throwaway seed script (outside `src/`) with `--up` (create data/users/flags, print prior values of
anything flipped) · `--run` (API scenarios → `PASS|FAIL name :: json`) · `--down` (delete everything,
restore flags). Every re-run = `--down` → `--up` → run.

## Step 2 — Shoot (Playwright spec via `npx playwright test`, not an MCP browser)

```ts
const SHOT_DIR = process.env.E2E_SHOT_DIR ?? 'e2e-shots';          // OUTSIDE test-results/ (wiped each run)
const VIEWPORT = process.env.E2E_VIEWPORT ?? 'desktop';
const SIZES = { desktop: { width: 1280, height: 800 }, mobile: { width: 390, height: 844 } };
if (VIEWPORT === 'mobile') test.use({ viewport: SIZES.mobile, isMobile: true, hasTouch: true });
else test.use({ viewport: SIZES.desktop });

async function shot(page: Page, id: string) {
  // hide framework dev overlays (e.g. Next's `nextjs-portal`) and say so in the notes — never hide app UI
  await page.screenshot({ path: `${SHOT_DIR}/${id}--${VIEWPORT}.png`, fullPage: false,
    style: 'nextjs-portal{display:none!important}' });
}
```

- Viewport-only, never `fullPage` — scroll the target into view first.
- Wait on a URL or a visible element, not `networkidle` (realtime listeners keep the network busy).
- Toasts: `await expect(toast).toBeVisible()`, wait ~700 ms for the fade-in, then shoot.
- "Both" = run the spec twice (`E2E_VIEWPORT=desktop`, reset fixture, `E2E_VIEWPORT=mobile`).
- Assert what each step proves in the same test — a picture without an assertion is decoration.

## Step 3 — Look at every shot, FIX the UI bugs you see, re-run (max 3 rounds)

Tile the shots into a grid and read it. Two buckets:
- **Capture defect** (blank toast, spinner, dev overlay, half-rendered) → fix the spec, re-shoot.
- **App UI bug** (horizontal overflow, clipped/wrapped buttons, wrong value/copy, contradictory
  states) → measure it (`getBoundingClientRect`, DOM text), send ONE `implementer` with every bug of
  the round (`file:line`, what's wrong, which rule), run the review gate on the fix, reset the
  fixture, re-shoot. Product-decision bugs go to the notes instead — and tell the user why.

## Step 4 — Build + publish the page

1. Write `manifest.json` (schema in the header of `build-proof-page.py`): title, meta links
   (PR/issue/branch@sha), KPIs per layer, `viewports`, ordered `steps` (`caption` = what the step
   PROVES), API `table`, honest `notes`; optional `ui` to localize the page chrome.
2. `python3 .claude/skills/e2e-visual-proof/build-proof-page.py manifest.json <shots_dir> out.html`
   (needs Pillow) → one self-contained HTML.
3. Publish it where reviewers can open it (Claude Artifact, a secret gist, or attach the file) and
   link it in the PR body + the issue close-out. Never commit the shots or page into `src/`.

## Step 5 — Cleanup (always)

`--down`, stop only the dev server you started, verify by reading back that seeded data is gone.

## Common mistakes

| Mistake | Fix |
|---|---|
| Choosing desktop/mobile yourself | Step 0, every time |
| Shots vanish after re-run | `E2E_SHOT_DIR` outside `test-results/` |
| Scenario 1 fails on 2nd run ("already registered") | `--down` → `--up` |
| Listing a visible UI bug in the notes and publishing | Step 3: fix → review → re-shoot |
| Captions describe the screen | Captions state what the step proves |
