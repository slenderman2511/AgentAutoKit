# Keys, Naming & Locale-File Parity

A translation system is only as good as its keys and its parity. Missing keys leak raw identifiers or the wrong language to users; orphan keys rot. This file keeps both clean.

## Naming a key

A key names **meaning and location**, never the current copy.

- **Good**: `checkout.payButton`, `errors.network`, `roster.emptyState.title`, `auth.login.submit`
- **Bad**: `pay_now`, `text1`, `blueButton`, `save_changes_button_label_v2`

Rules:
- **Namespace by feature/screen**, then component, then role. Dot-separated, `camelCase` leaves: `feature.section.element`.
- **Never encode the text or styling** in the key. If the button copy changes from "Pay now" to "Complete order", the key `checkout.payButton` still fits — you change the value, not the key.
- **Reuse shared keys** for truly generic UI: `common.save`, `common.cancel`, `common.loading`, `common.yes`, `common.no`. But do *not* over-share — "Save" in a payment flow and "Save" as in bookmark may translate differently in Vietnamese ("Lưu" vs "Lưu lại"). When in doubt, keep them separate and specific.
- **Keys are stable identifiers.** Renaming a key is a breaking change: update every locale file and every call site in the same change, or the app shows a missing key.

## File structure

Keep the shape identical across every locale. Mirror namespaces as nested objects (or flat dotted keys — pick one and be consistent per project).

```jsonc
// messages/en.json                    // messages/vi.json
{                                      {
  "common": {                            "common": {
    "save": "Save",                        "save": "Lưu",
    "cancel": "Cancel"                     "cancel": "Hủy"
  },                                     },
  "checkout": {                          "checkout": {
    "payButton": "Pay now",                "payButton": "Thanh toán",
    "total": "Total: {amount}"             "total": "Tổng: {amount}"
  }                                      }
}                                      }
```

- **One file per locale** (`en.json`, `vi.json`), or one folder per locale with per-namespace files (`en/checkout.json`) for large apps. Whichever the project uses, keep locales structurally symmetric.
- Sort keys the same way in every file (alphabetical or grouped) so diffs stay reviewable and parity is eyeball-able.

## The parity rule: add to every locale, always

**Adding a string is not done until it exists in every locale.** The default project locales are `en` and `vi`; some add more. A key in `en` but not `vi` means a Vietnamese user sees English (or the raw key). A key in `vi` but not `en` is dead or a typo.

When you add, rename, or remove a key, do it in **all** locale files in the same commit.

## Detecting drift (missing & orphan keys)

Run a key-diff between locales. Quick check with `jq`:

```bash
# Keys present in en but missing from vi (flatten nested objects to dotted paths first)
diff \
  <(jq -r 'paths(scalars) | join(".")' messages/en.json | sort) \
  <(jq -r 'paths(scalars) | join(".")' messages/vi.json | sort)
# lines with '<' = only in en (missing from vi); lines with '>' = only in vi (orphan/typo)
```

Also catch **keys used in code but absent from the catalog** (the raw-key-on-screen bug): grep `t('...')` / `t("...")` call sites and compare against the locale keys. Many i18n toolchains ship this as a linter — prefer wiring it into CI.

## Enforce it in CI / lint

Manual diffs miss things. Add an automated gate so drift fails the build, not the user:

- **`i18next-parser`** — extracts every `t(...)` key from the source into catalogs; run it and fail if the catalog would change (keys used but not defined) or has unused keys.
- **`eslint-plugin-i18next`** / **`eslint-plugin-formatjs`** — flags literal JSX strings (hardcoded text) at lint time; the cheapest guard against Golden Rule #1.
- **A parity test** — a tiny unit test that loads every locale, flattens to key sets, and asserts they're equal. Cheap, deterministic, catches the "added to en, forgot vi" mistake before review.
- **next-intl** ships a message-format check; **FormatJS** has `formatjs lint`. Use whatever the project's library provides.

Keep the check in the same CI that runs tests, so a PR that adds an English-only key can't merge.

## Handling untranslated values during development

- Never ship an empty `""` value — it renders blank. If a translation is genuinely pending, leave the English text *and* flag it (a `// TODO(i18n)` next to the key, or a `_needsTranslation` marker your tooling reports) so it's visible, not silent.
- Do not disable the "missing key" warning in development — it's how you catch drift early. Only production should have a quiet, monitored fallback (log the missing key to your error tracker so you find out).
