# Adopting i18n in a Project That Has None

The other reference files assume i18n is already wired. This one is for the **before**: a monolingual project (usually all-English or all-Vietnamese hardcoded) that needs to become multi-language. Covers *when to raise it*, *which library*, and *how to retrofit without a big-bang rewrite*.

## When to proactively suggest turning it on

If you're implementing or reviewing a feature in a project that has **no i18n setup** (no `next-intl`/`react-i18next`, no `messages/`/`locales/`, text hardcoded in components) and the project is expected to serve both EN and VI users, **say so** — don't silently keep adding hardcoded strings. Signals it's time:

- New user-facing screens/flows are being built (every hardcoded string added now is future migration debt).
- The product targets Vietnamese users but the UI is English-only (or vice-versa).
- The team mentions a second market, a translator, or "we'll localize later."

Raise it as a short recommendation with the cost framed honestly: adopting early is cheap; retrofitting a mature app is a real project. Then, if they agree, follow the path below. **Don't** unilaterally introduce an i18n library into an existing project without the human agreeing — it's an architectural change.

## Decide: which library

Match the app's rendering model (confirm with `next-best-practices`):

- **Next.js App Router (RSC)** → **`next-intl`** (recommended). Server-first, works cleanly across the server/client boundary, handles locale routing/middleware and formatting.
- **Next.js Pages Router / plain React SPA** → **`react-i18next`** (mature, client-oriented).
- **Already has one of them half-wired** → finish that one; never add a second i18n library.

Pick the **default locale** deliberately up front — many of these projects are Vietnamese-first, so `defaultLocale: 'vi'` with `en` as the second locale is common. This decision affects routing and fallback, so settle it before scaffolding.

## Greenfield vs retrofit

- **Greenfield** (i18n before real UI is built): set the library up first (below), then every feature is authored with keys from day one. Cheapest path — no migration debt.
- **Retrofit** (existing monolingual app): scaffold once, then migrate **incrementally**, slice by slice. Do **not** attempt to convert the whole app in one commit — it's unreviewable and regression-prone.

## Retrofit path (incremental, not big-bang)

**1. Scaffold once (one setup PR):**
- Install and configure the chosen library (see [framework-setup.md](./framework-setup.md)): config, provider, middleware/routing, `<html lang>`.
- Create empty-but-parallel catalogs: `en.json` and `vi.json` (plus any other target locale).
- Decide catalog structure and the namespacing convention **now** (see [key-management.md](./key-management.md)) so every later slice is consistent.
- Wire locale detection/persistence and a language switcher (even if only one screen is migrated yet).

**2. Stop the bleeding — prevent *new* hardcoded strings immediately:**
- Turn on `eslint-plugin-i18next` (or `formatjs`) so new literal JSX text fails lint from day one. This matters more than converting old code fast: it stops the debt from growing while you migrate.

**3. Migrate in slices, one route/feature at a time:**
For each slice, run the normal correction loop — find literals ([hardcoded-strings.md](./hardcoded-strings.md)) → meaningful keys → add to **every** locale → replace with `t(...)` → fix any concat/plural/format issues ([formatting.md](./formatting.md)) → **verify the slice renders in EN and VI** ([review-checklist.md](./review-checklist.md)). Ship the slice. Repeat. Small PRs stay reviewable and each one is independently correct.
- Use **`i18next-parser`** to bulk-surface hardcoded keys within a slice and scaffold catalog entries, then fill in real translations — it accelerates extraction; it does not replace writing natural Vietnamese.

**4. Add the parity gate early** (see [key-management.md](./key-management.md)) so that from the first migrated slice onward, an EN-only key can't merge. Adopting the gate *before* the app is fully migrated keeps already-migrated areas from regressing.

**5. Track progress** — a simple checklist of routes/features "migrated vs remaining" so the effort has a visible finish line and nothing is silently skipped.

## Retrofit gotchas (things a monolingual codebase hid)

- **Routing change**: introducing locale-prefixed URLs (`/vi/...`, `/en/...`) changes every path. Plan redirects from old URLs and update internal `<Link>`s and sitemaps — an SEO/broken-link risk if done carelessly.
- **Hardcoded dates/numbers/currency** scattered through the old code (`price + '₫'`, `dd/MM` strings) must move to `Intl` formatters as you migrate — easy to miss because they "looked fine" in one language. See [formatting.md](./formatting.md).
- **Display strings stored in the DB or in enums** (status labels, category names, email templates): these aren't in components, so a JSX-only scan misses them. Decide per case — key them in the catalog if they're fixed UI labels, or add a translation layer if they're data.
- **Emails / notifications / PDFs / SMS**: often the last hardcoded holdout. They're user-facing too — include them in the migration scope.
- **Third-party components** (date pickers, tables, charts) with English defaults need their `locale`/labels wired up.
- **Persisted user preference**: once there are two locales, remember the user's choice (cookie/profile) or every reload resets them.

## Definition of done for adoption

- Library scaffolded; default locale chosen; switcher + persistence work.
- New hardcoded strings are blocked by lint; parity is enforced in CI.
- Targeted scope (all routes, or the agreed subset) migrated and **verified in both languages**, not just key-complete.
- A tracked list shows what (if anything) is intentionally left for later — no silent gaps.
