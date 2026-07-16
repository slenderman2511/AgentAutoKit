# Interpolation, Plurals & Locale-Aware Formatting

Word order, plural rules, and number/date/currency formats differ across languages. Never build these by hand — the message and the locale own them.

## Interpolation — never concatenate

A sentence with a dynamic value is **one message with a placeholder**, not fragments joined in code.

```jsonc
// en.json                                  // vi.json
"welcome": "Welcome back, {name}!"          "welcome": "Chào mừng trở lại, {name}!"
"cartTotal": "Your total is {amount}"       "cartTotal": "Tổng của bạn là {amount}"
```

```ts
t('welcome', { name })          // ✅ one message, translator controls word order & punctuation
t('welcome') + ' ' + name       // ❌ bakes in English word order and the space
`${t('greeting')} ${name}!`     // ❌ same bug via template literal
```

Why: in another language the variable may move to the front, take a different particle, or need no surrounding spaces. Only the translator can decide, and they can only do it if the whole phrase is one key.

## Plurals — ICU, not `if (count === 1)`

Let the plural category live in the message. ICU `plural` picks the right form per locale's CLDR rules.

```jsonc
// en.json
"items": "{count, plural, =0 {No items} one {# item} other {# items}}"
// vi.json  — Vietnamese has no plural inflection; one natural form, still keyed off count for =0
"items": "{count, plural, =0 {Không có mục nào} other {# mục}}"
```

```ts
t('items', { count })   // renders "3 items" / "3 mục", "1 item", "No items"
```

- `#` prints the number formatted for the locale.
- Use `=0`/`=1` for exact-count special cases; `one`/`other` (and `few`/`many`/`zero` where a language needs them) for CLDR categories. Don't hand-roll `count === 1 ? 'item' : 'items'` — it's wrong for most languages and unmaintainable.

## Select & gender

For finite branches (status, gender, type), use ICU `select` instead of conditional English:

```jsonc
"invite": "{gender, select, male {Anh ấy} female {Cô ấy} other {Họ}} đã mời bạn"
"status": "{s, select, paid {Đã thanh toán} pending {Chờ duyệt} other {Không xác định}}"
```

This replaces `status === 'paid' ? 'Paid' : ...` chains and keeps every branch translatable.

## Numbers, currency, dates — through the locale, never by hand

Use `Intl` (or your i18n library's formatter, which wraps `Intl`) keyed off the **active locale**. Never insert `,`/`.` separators manually or hardcode a date format string.

### Currency

Vietnamese Đồng and US Dollar format differently — symbol, separators, and decimals all change.

```ts
// VND: '₫' symbol, '.' thousands separator, NO decimal digits → "1.500.000 ₫"
new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(1500000)
// USD: '$' symbol, ',' thousands, 2 decimals → "$1,500.00"
new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(1500)
```

Rules:
- **Amount is data; currency + locale decide presentation.** Store money as an integer minor/major unit (VND has no minor unit — store whole đồng), format at the edge.
- **Never** `price + '₫'` or `price.toLocaleString() + ' VND'` with a guessed format — let `Intl` place the symbol and separators.
- Keep the numeric value locale-independent in the DB and in calculations; only format for display.

### Numbers & percent

```ts
new Intl.NumberFormat(locale).format(1234567.89)          // vi-VN: "1.234.567,89"  en-US: "1,234,567.89"
new Intl.NumberFormat(locale, { style: 'percent' }).format(0.075)  // "7,5 %" / "7.5%"
```

Note the separators **swap** between vi and en — this is exactly why manual formatting is a bug.

### Dates & times

```ts
new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(d) // "16/07/2026"
new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }).format(d)                                // "Jul 16, 2026"
```

- VI is `dd/MM/yyyy`; US is `MM/DD/YYYY`. Never hardcode either — pass the locale.
- Store timestamps as UTC (ISO 8601 / epoch); format to the user's locale **and** timezone at display time. If you use `date-fns`/`dayjs`/`luxon`, load and pass the matching locale — don't rely on the default.

### Relative time & lists

```ts
new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(-1, 'day')  // "yesterday" / "hôm qua"
new Intl.ListFormat(locale, { type: 'conjunction' }).format(['A','B','C'])  // "A, B, and C" / "A, B và C"
```

Don't build "3 ngày trước" or "A, B và C" with string math — the connectors and rules are locale-specific.

## Checklist for any string with a variable in it

- [ ] Whole phrase is one key; the variable is a `{placeholder}`, not concatenated.
- [ ] Count-dependent text uses ICU `plural`; branchy text uses `select`.
- [ ] Money uses `Intl.NumberFormat(..., { style: 'currency' })` with the right `currency` and locale (VND = no decimals).
- [ ] Dates use `Intl.DateTimeFormat` with the active locale + correct timezone; no hardcoded `dd/MM` or `MM/DD`.
- [ ] Number separators come from the locale, not typed in.
