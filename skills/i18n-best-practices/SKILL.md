---
name: i18n-best-practices
description: Apply i18n/multi-language best practices when writing, reviewing, or hardening any user-facing feature in a bilingual (EN/VI) or multi-locale project — catching hardcoded strings, enforcing translation-key conventions, keeping locale files in parity (no missing/orphan keys across en & vi), correct interpolation/pluralization/ICU, locale-aware formatting of dates/numbers/currency (VND, dd/MM/yyyy), and safe setup of next-intl or react-i18next in Next.js (server vs client components). Use when asked to "add a translation", "make this multi-language", "extract hardcoded text", "add a new locale", "audit i18n", "fix missing translations", "why is this key showing raw", or when reviewing ANY component/page/email/error message that renders text a user will read. Treat findings as things to fix, not just flag.
user-invocable: false
---

# i18n Best Practices

Reference discipline for **correcting and hardening** multi-language features. Every project here ships at least English + Vietnamese and may add more locales, so *any* user-facing string is an i18n surface. Apply these rules when writing or reviewing any feature that renders text — treat findings as things to *fix*, not just flag.

This skill is framework-level and reusable. It owns *what correct i18n looks like* — the rules below hold whether the project uses `next-intl`, `react-i18next`, or a plain message catalog. When a repo ships a project-specific skill that says *where locale files live* and *how they're loaded in this repo*, that skill owns the mechanics; this skill owns the correctness bar. Neighbors: `next-best-practices` (RSC server/client boundary — critical for where translations can run), `frontend-design` (RTL/layout when a new locale needs it), and `e2e-flow` (bilingual selectors in tests).

## Golden rules (never violate)

1. **No hardcoded user-facing strings.** Every word a user can read goes through the translation layer with a key — never a literal in JSX, `alert()`, thrown `Error` messages surfaced to users, email/notification bodies, toast text, `<title>`/metadata, `aria-label`, `placeholder`, or `alt`. Literals are only for keys, test IDs, machine identifiers, and developer logs. Read [hardcoded-strings.md](./hardcoded-strings.md).
2. **All locales stay in parity.** Every key present in `en` must exist in `vi` (and any other locale), and vice-versa — no missing keys (user sees raw `foo.bar` or English fallback) and no orphan keys (dead weight). Adding a string means adding it to **every** locale in the same change. Read [key-management.md](./key-management.md).
3. **Never build a sentence by concatenation.** Word order differs across languages. Use one key with interpolation/ICU for the whole phrase — never `t('hello') + ' ' + name` or `t('you_have') + count + t('items')`. Read [formatting.md](./formatting.md).
4. **Format dates, numbers, and currency through the locale, not by hand.** VND is `₫` with `.` thousands separators and no decimals (`1.500.000 ₫`); VI dates are `dd/MM/yyyy`; EN is `$` / `MM/DD/YYYY`. Use `Intl`/the i18n library's formatters keyed off the active locale — never a hardcoded format string or manual `,`/`.` insertion. Read [formatting.md](./formatting.md).
5. **Pluralize with ICU, not with `if (count === 1)`.** English has one/other; other languages differ (Vietnamese has no plural inflection but still needs a natural phrasing). Let the plural rules live in the message. Read [formatting.md](./formatting.md).
6. **Respect the RSC boundary.** In Next.js App Router, server components and client components load translations differently. Don't pass a non-serializable `t` function across the boundary or call a client-only hook in a server component. Read [framework-setup.md](./framework-setup.md).
7. **A key names its meaning, not its current text.** `checkout.payButton`, not `pay_now_button_blue` or `text_1`. Rename the value freely; never rename a key just because the English copy changed. Read [key-management.md](./key-management.md).
8. **Fallback is a safety net, not a plan.** A visible English string where Vietnamese should be is a bug, not "graceful degradation." Missing translations must be caught before ship, not silently fall back in production. Read [review-checklist.md](./review-checklist.md).

## Reference files

Consult these based on what you're doing:

### Finding & fixing hardcoded text
[hardcoded-strings.md](./hardcoded-strings.md) — what counts as user-facing (and the exceptions), `grep`/`rg` patterns to surface literals in JSX/attributes/thrown errors/emails, the extract-to-key workflow, and the traps (concatenation, string templates, conditional English).

### Keys, naming, and locale-file parity
[key-management.md](./key-management.md) — naming & namespacing conventions, the "add to every locale at once" rule, detecting missing vs orphan keys across `en`/`vi`, JSON structure, and CI/lint checks that fail the build on drift.

### Interpolation, plurals, dates, numbers, currency
[formatting.md](./formatting.md) — ICU message syntax, interpolation (never concatenate), plural/select/gender, and locale-aware `Intl` formatting for VND/USD, dates (`dd/MM/yyyy` vs `MM/DD/YYYY`), numbers, and relative time.

### Wiring up the library correctly
[framework-setup.md](./framework-setup.md) — `next-intl` (App Router: server components, `useTranslations` in client, `getTranslations` on server, middleware/routing) and `react-i18next` patterns, the RSC serialization boundary, locale detection/persistence, and the checklist for **adding a new locale** end-to-end.

### Running a full correction pass
[review-checklist.md](./review-checklist.md) — the audit → fix → verify protocol: which files to open, the red-flag list, the parity check, and how to prove the feature renders correctly in EN *and* VI before calling it done.

## Correction workflow (short form)

When asked to "make this multi-language / audit i18n / add a translation":

1. **Locate the i18n setup**: find the config and catalogs — search for `next-intl`, `react-i18next`, `i18next`, `messages/`, `locales/`, `en.json`, `vi.json`, `useTranslations`, `getTranslations`, `useTranslation`, `NextIntlClientProvider`. Note which library and where locale files live.
2. **Scan for hardcoded strings** in the target scope with the patterns in [hardcoded-strings.md](./hardcoded-strings.md) — record each with file:line.
3. **Fix**: extract each literal to a well-named key, add the value to **every** locale (write natural Vietnamese, not machine-translated word salad — if unsure of a translation, flag it for a human rather than guessing), and replace the literal with a `t(...)` call.
4. **Check parity** and formatting: run the key-diff between locales, confirm dates/numbers/currency go through locale formatters, confirm plurals use ICU. See [key-management.md](./key-management.md) and [formatting.md](./formatting.md).
5. **Verify** the feature actually renders in both EN and VI (switch the locale and look — see [review-checklist.md](./review-checklist.md)). A key that exists is not the same as a screen that reads correctly.
