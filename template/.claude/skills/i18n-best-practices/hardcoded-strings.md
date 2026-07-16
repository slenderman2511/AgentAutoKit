# Finding & Fixing Hardcoded Strings

The most common i18n bug: a literal that ships in one language only. This file is how you hunt them and how you fix them.

## What counts as a user-facing string (must be translated)

Anything a user can read, in any surface:

- Visible text in JSX: `<p>Save changes</p>`, `<Button>Đăng nhập</Button>`
- Attributes rendered to users: `placeholder`, `title`, `alt`, `aria-label`, `aria-description`, `label`
- Page/SEO metadata: `<title>`, `description`, Open Graph, `generateMetadata` return values
- Feedback: toast/snackbar text, `alert()`/`confirm()`, form validation messages, empty states, loading labels
- Errors surfaced to users: messages thrown/returned that reach the UI, `HttpsError` messages shown to the client, 404/500 page copy
- Out-of-band content: email subjects & bodies, SMS/push notification text, PDF/invoice labels
- Enum-ish display text: status labels ("Pending" → "Chờ duyệt"), role names, category names shown in the UI

## What is NOT a user-facing string (leave as a literal)

- **Translation keys themselves**: `t('checkout.payButton')` — the key is a literal, correctly.
- **Machine identifiers**: route paths, API field names, `enum` *values* stored in the DB, event names, CSS class names, `data-testid`.
- **Developer logs**: `console.log`, `logger.info`, internal error messages that never reach a user (still keep them English for the team).
- **Code/config**: env var names, HTTP header names, MIME types.

Rule of thumb: *if a translator would need to touch it, it's a string; if a translator touching it would break the app, it's an identifier.*

## Grep/rg patterns to surface literals

Run these over the target scope (a component, a folder, or the whole `app/`/`src/`). They over-report — triage the hits.

```bash
# JSX text nodes with letters (visible copy between tags)
rg -n '>[^<>{}]*[A-Za-zÀ-ỹ]{2,}[^<>{}]*<' --glob '*.tsx' --glob '*.jsx'

# User-facing attributes assigned a string literal
rg -n '(placeholder|title|alt|aria-label|label)=("|'\'')[^"'\'']*[A-Za-zÀ-ỹ]' --glob '*.tsx'

# Thrown / returned error strings that may reach the UI
rg -n 'throw new Error\((["'\''])' --glob '*.ts' --glob '*.tsx'

# alert/confirm/toast with a literal
rg -n '(alert|confirm|toast[.\w]*)\(\s*(["'\''])' --glob '*.ts' --glob '*.tsx'

# String concatenation building sentences (word-order bug — see formatting.md)
rg -n "t\([^)]*\)\s*\+|\+\s*t\(" --glob '*.tsx'
```

Two useful sanity greps:

```bash
# Find files that render text but never call the translation hook — high-suspicion
rg -L -n 'useTranslations|getTranslations|useTranslation' --glob '*.tsx' app/   # -L lists files WITHOUT a match

# Vietnamese text hardcoded directly in code (should be in vi.json, not the component)
rg -n '[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]' --glob '*.tsx' --glob '*.ts'
```

## The extract-to-key workflow

For each confirmed literal:

1. **Pick a meaningful key** by location + intent: `checkout.payButton`, `errors.network`, `roster.emptyState.title`. See [key-management.md](./key-management.md) for naming.
2. **Add the value to every locale in the same edit** — `en.json` gets the original text; `vi.json` gets a natural Vietnamese translation. Do not leave `vi` blank or copy the English in as a placeholder that ships. If you can't translate it confidently, flag it for a human reviewer in the PR rather than shipping a guess.
3. **Replace the literal** with the translation call for that surface:
   - Client component: `const t = useTranslations('checkout'); ... {t('payButton')}`
   - Server component: `const t = await getTranslations('checkout'); ... {t('payButton')}`
   - Attribute: `placeholder={t('search.placeholder')}`
4. **Interpolate, don't concatenate** anything dynamic — `t('welcome', { name })` with `"welcome": "Xin chào, {name}"`. Never `t('welcome') + name`. See [formatting.md](./formatting.md).
5. **Re-scan** to confirm the literal is gone and no new one crept into the replacement (e.g. a hardcoded `" "` separator or a `title="..."` you missed).

## Traps that pass a quick glance but break translation

- **Concatenation / template literals**: `` `${t('greeting')} ${name}!` `` bakes in word order and the `!`. Move the whole phrase into the message.
- **Conditional English**: `status === 'paid' ? 'Paid' : 'Unpaid'` — both branches are hardcoded. Map to keys: `t(`status.${status}`)`.
- **Pluralized by hand**: `count + (count === 1 ? ' item' : ' items')` — use ICU plural. See [formatting.md](./formatting.md).
- **Units glued to numbers**: `price + '₫'` or `qty + ' người'` — format through the locale and let the message hold the unit.
- **Default function params**: `function toast(msg = 'Success')` — the default is a hardcoded string.
- **Constants/enums with display text**: a `STATUS_LABELS = { paid: 'Paid' }` map is a hardcoded catalog; move labels to the locale files and key off the enum value.
- **Third-party component props**: date pickers, tables ("No rows"), charts — many accept a `labels`/`locale` prop; wire them to `t(...)`, don't accept their English defaults.
