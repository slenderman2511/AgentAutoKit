---
name: e2e-flow
description: Use when running, debugging, or authoring end-to-end user-journey Playwright specs in this repo (tests/*.spec.ts) — e.g. registration/payment flows like pwc2026-flow or team-format-flow, adding a new full-journey spec, wiring its env/seeding prerequisites, or diagnosing a failed flow run (test-results/, playwright-report/). For generic Playwright technique (locators, flakiness, POM, CI), defer to the playwright-best-practices skill.
---

# E2E User-Journey Flows

Full-journey Playwright specs live in `tests/*.spec.ts` (currently `pwc2026-flow.spec.ts` and `team-format-flow.spec.ts`). They drive the real app against a local dev server, real Firebase, and real Stripe test-mode checkout — nothing is mocked. This skill covers how flows are composed and run in THIS repo; consult `playwright-best-practices` for generic locator/waiting/debugging advice.

## Running the suites

Prerequisites — Playwright has NO `webServer` block in `playwright.config.ts`, so the app must already be running:

1. Start the dev server yourself: `npm run dev` (Next.js on `http://localhost:3000`, the configured `baseURL`).
2. Env: the app needs its normal `.env.development` / `.env.local` Firebase + Stripe test-mode config. `pwc2026-flow` completes real Stripe Checkout redirects (`checkout.stripe.com`) with test card `4242 4242 4242 4242`, so Stripe must be in test mode.
3. Run:

```bash
npm run test:e2e            # playwright test (all of tests/)
npm run test:e2e:ui         # playwright test --ui
npx playwright test tests/pwc2026-flow.spec.ts   # one flow
```

Config facts (`playwright.config.ts`): `testDir: './tests'`, `workers: 1` and `fullyParallel: false` (flows run sequentially — they share live backend state; keep it that way), chromium only, `reporter: 'html'`, `trace: 'on-first-retry'`, `screenshot: 'only-on-failure'`, retries 2 on CI / 0 locally.

The gated team suite needs env and a pre-seeded event, otherwise it self-skips via `test.skip(...)`:

```bash
E2E_TEAM_EVENT_ID=<eventId> \
E2E_ADMIN_EMAIL=<email> E2E_ADMIN_PASSWORD=<pw> \
npx playwright test tests/team-format-flow.spec.ts
```

## How a flow spec is structured here

Two established patterns — pick the one matching your scenario:

**1. Self-provisioning journey (`pwc2026-flow.spec.ts`)** — creates its own user, needs no seeding:
- Unique identity per run: `const testEmail = \`test_bot_${Date.now()}@example.com\`` so reruns never collide on existing accounts.
- One `test()` with `test.setTimeout(300000)` (5 min), composed of numbered `test.step()` phases: Sign up -> Basic Info modal -> Event Registry Onboarding -> Entrance Fee (Stripe) -> Singles -> Doubles -> Team.
- Each phase ends by asserting a URL transition (`waitForURL('**/checkout/*?success=true*')`) then navigating back to the hub page (`page.goto('/pwc2026/tournament')`).
- Stripe Checkout block is repeated verbatim per payment: `waitForURL(/.*checkout\.stripe\.com.*/)`, fill `#cardNumber`/`#cardExpiry`/`#cardCvc`/`#billingName`, click `.SubmitButton`, wait for `?success=true` redirect.
- Conditional UI is handled with `if (await locator.isVisible())` guards (e.g. the "Complete Profile" modal that may or may not appear mid-Singles registration).

**2. Seeded, role-based journey (`team-format-flow.spec.ts`)** — asserts against pre-existing data:
- Reads `E2E_TEAM_EVENT_ID` / `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` from `process.env` and calls `test.skip(!EVENT_ID || ..., 'Set ... to run.')` at describe level so CI without the infra passes green.
- Seed the event first with `TENANT_ID=<tenant> node scripts/seed-team-formats.mjs <eventId> --commit` (dry-run without `--commit`, per `.claude/rules/firebase-data-safety.md`).
- Admin login is inline: goto `/login`, fill `input[type="email"]` / `input[type="password"]`, click `button:has-text("Sign In"), button:has-text("Đăng nhập")` — selectors match BOTH English and Vietnamese UI text (this app is bilingual; copy that pattern, e.g. `getByText(/Các trận trong cặp đấu|Sub-matches/)`).
- Data-dependent assertions are guarded with `if (await locator.count())` so the spec asserts the surface exists without hard-coding a specific seeded match.

There is also a legacy Puppeteer multi-user script, `scripts/debug/e2e_test.js` (three pre-seeded accounts like `pro_player@pwc.com` / `password123`, sign-out via clearing `firebaseLocalStorageDb` IndexedDB, screenshots to `scripts/debug/screenshots/`). It is a manual debug harness run with `node scripts/debug/e2e_test.js` — do NOT model new specs on it; write Playwright specs in `tests/` instead.

## Adding a new flow spec

1. Create `tests/<feature>-flow.spec.ts`. It is picked up automatically (`testDir: './tests'`; note this dir also holds many one-off `.ts` maintenance scripts — only `*.spec.ts` files run).
2. Decide seeding strategy:
   - New-user journeys: generate a timestamped account like `pwc2026-flow` does; no cleanup exists, accounts accumulate in dev Firebase.
   - Existing-data journeys: add/reuse a seeder in `scripts/` (pattern: dry-run by default, `--commit` to write, `TENANT_ID` required) and gate the spec on env vars with `test.skip(...)` plus a header comment documenting the exact run command, exactly as `team-format-flow.spec.ts` does.
3. Structure the journey as `test.step()` phases inside one long test with `test.setTimeout(300000)`; assert phase boundaries with `waitForURL` patterns.
4. Use relative `page.goto('/pwc2026/...')` paths — `baseURL` supplies the host.
5. Reuse the existing Stripe test-checkout block verbatim for any payment phase.
6. Do not add parallelism or extra projects to `playwright.config.ts`; flows assume `workers: 1`.

For locator style, waiting discipline, and flakiness fixes while writing steps, load `playwright-best-practices` (core/locators.md, core/assertions-waiting.md).

## When a flow fails

1. Failure artifacts land in `test-results/<spec>-<test>-chromium/` — failure screenshots always (config: `screenshot: 'only-on-failure'`).
2. Open the HTML report: `npx playwright show-report` (reporter output in `playwright-report/`).
3. Traces are only recorded on first retry (`trace: 'on-first-retry'`), and local retries are 0 — to get a trace locally rerun with `npx playwright test tests/<spec> --trace on`, then `npx playwright show-trace <test-results/...>/trace.zip`.
4. Triage in this order, matching how these flows break in practice:
   - Dev server not running / wrong port -> everything fails at first `goto` (start `npm run dev`).
   - Gated suite "passed" instantly -> it skipped; check the `E2E_TEAM_*` env vars.
   - Timeout inside a Stripe step -> Stripe env not in test mode, or the `checkout.stripe.com` redirect never fired; the 15–20s `waitForURL` timeouts in the spec are the usual failure point.
   - Selector miss on text like `REGISTRATION`, `19+`, `Pay via Stripe` -> UI copy changed (check both English and Vietnamese variants) — update the spec's text selectors.
   - Mid-journey modal appeared/disappeared (e.g. "Complete Profile") -> adjust the `isVisible()` guard rather than adding fixed waits.
5. Journeys are stateful: a run that dies mid-flow leaves a half-registered account behind. Since accounts are timestamped, just rerun — don't try to resume. Seeded events can be reset via `scripts/reset-event-for-testing.mjs`.
6. For deeper trace-viewer / flaky-test methodology, defer to `playwright-best-practices` (debugging/debugging.md, debugging/flaky-tests.md).
