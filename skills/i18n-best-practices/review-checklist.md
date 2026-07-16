# i18n Review Checklist — audit → fix → verify

The protocol for making a feature (or a whole app) i18n-correct. A key that exists is not a screen that reads correctly — this checklist ends at *seen working in both languages*.

## 1. Locate

- [ ] Identify the library (`next-intl` / `react-i18next` / other) and where catalogs live (`messages/`, `locales/`, `en.json`, `vi.json`). See [framework-setup.md](./framework-setup.md).
- [ ] Confirm the list of active locales (at least `en`, `vi`) from the single source of truth.
- [ ] Scope the audit: the changed files in this PR, or the feature/folder named.

## 2. Audit (record each finding as file:line)

Hardcoded text — see [hardcoded-strings.md](./hardcoded-strings.md):
- [ ] No literal user-facing text in JSX.
- [ ] No literals in `placeholder`/`title`/`alt`/`aria-label`/`label`.
- [ ] No hardcoded copy in metadata / `<title>` / `generateMetadata`.
- [ ] No user-facing literals in thrown/returned errors, `alert`/`confirm`/toast.
- [ ] No hardcoded strings in emails/notifications/PDF labels.
- [ ] No display-text constant maps (`STATUS_LABELS = {...}`) holding English.

Structure & correctness:
- [ ] No sentence built by `+` concatenation or template literal — interpolation only. See [formatting.md](./formatting.md).
- [ ] Count-dependent text uses ICU `plural`; branchy text uses `select`.
- [ ] Dates/numbers/currency go through `Intl`/locale formatters (VND no decimals, `dd/MM/yyyy` for vi) — none hand-formatted.
- [ ] Keys are meaningful and namespaced, not text- or style-derived. See [key-management.md](./key-management.md).
- [ ] RSC boundary respected: no `t` passed server→client; hooks only in client components. See [framework-setup.md](./framework-setup.md).

## 3. Fix

- [ ] Extract each literal to a well-named key.
- [ ] Add the value to **every** locale in the same change — natural Vietnamese, not machine word-salad. Flag anything you can't translate confidently for a human, rather than guessing.
- [ ] Replace the literal with the right call for its surface (`useTranslations` client / `getTranslations` server / attribute).
- [ ] Fix concatenation → interpolation, hand-plurals → ICU, hand-formats → `Intl`.

## 4. Parity & tooling

- [ ] Key-diff every locale — no missing keys, no orphans. See the `jq` diff in [key-management.md](./key-management.md).
- [ ] Every `t('...')` call site has a defined key (no raw-key-on-screen).
- [ ] Automated gate in place (parity test / `i18next-parser` / eslint-plugin-i18next / next-intl or formatjs lint) so drift fails CI, not the user.

## 5. Verify (the part people skip)

Existence ≠ correctness. Actually look at the feature in both languages:

- [ ] Switch the locale (URL segment or switcher) and load the affected screens — **EN and VI both render real translated copy**, no raw keys, no wrong-language leakage.
- [ ] Interpolated/pluralized strings read naturally with real values (0, 1, many) in each language.
- [ ] Currency shows correctly per locale (e.g. `1.500.000 ₫` for vi, `$1,500.00` for en); dates in the right format.
- [ ] Long-translation layout holds — Vietnamese/German strings are often longer than English; no clipped buttons or broken wrapping.
- [ ] `<html lang>` matches the active locale.
- [ ] If a new locale was added, its whole end-to-end flow works (see the add-a-locale checklist in [framework-setup.md](./framework-setup.md)).

Use the project's run/preview flow to drive the UI (the kit's `run` / `e2e-flow` skills, or a Playwright pass with bilingual selectors). A screenshot per locale is the cheapest proof.

## Red flags (stop and fix before shipping)

- A visible English word where Vietnamese should be — a bug, not "fallback."
- A raw key (`checkout.payButton`) rendered on screen — missing catalog entry.
- `t('a') + t('b')`, `` `${t('x')} ${v}` ``, or `count === 1 ?` in the diff.
- `price + '₫'`, `.toLocaleString()` with a guessed format, hardcoded `dd/MM` / `MM/DD`.
- A new key added to `en.json` only.
- A `t` function or a whole translated object passed as a prop from a server component to a client one.
- Missing-key warnings disabled in development.
