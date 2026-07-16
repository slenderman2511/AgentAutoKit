# Wiring the Library Correctly

The two common setups in these Next.js projects are **`next-intl`** (recommended for App Router) and **`react-i18next`**. The rules in the other reference files hold regardless; this file covers the mechanics and the traps unique to each — plus the RSC boundary and the add-a-locale checklist.

First: **detect what the project already uses** before writing anything. Search for `next-intl`, `react-i18next`, `i18next`, `NextIntlClientProvider`, `I18nextProvider`, `useTranslations`, `useTranslation`, `messages/`, `locales/`. Match the existing setup — do not introduce a second i18n library.

## The RSC boundary (Next.js App Router)

This is the #1 source of i18n bugs in App Router. Server components and client components access translations differently.

- **Server components** (default, no `'use client'`): translations are loaded on the server. With next-intl use `getTranslations` (async). Do **not** call the `useTranslations`/`useTranslation` hook here — hooks are client-only.
- **Client components** (`'use client'`): use the hook (`useTranslations` / `useTranslation`). They read messages from a provider higher in the tree.
- **Never pass the `t` function from a server component to a client component as a prop** — it isn't serializable and will error or silently break. Instead, either translate on the server and pass the resulting **strings** down, or let the client component call its own hook.
- Keep as much translation on the server as possible (smaller client bundle); reach for the client hook only where the component is already `'use client'` for interactivity.

See `next-best-practices` for the general RSC/serialization rules.

## next-intl (recommended for App Router)

Typical wiring:

```ts
// i18n/routing.ts — declare locales in ONE place
export const routing = { locales: ['en', 'vi'], defaultLocale: 'vi' };

// middleware.ts — locale detection + routing (e.g. /vi/checkout, /en/checkout)
import createMiddleware from 'next-intl/middleware';
import { routing } from './i18n/routing';
export default createMiddleware(routing);
```

```tsx
// Server component
import { getTranslations } from 'next-intl/server';
export default async function Page() {
  const t = await getTranslations('checkout');
  return <h1>{t('title')}</h1>;
}

// Client component
'use client';
import { useTranslations } from 'next-intl';
export function PayButton() {
  const t = useTranslations('checkout');
  return <button>{t('payButton')}</button>;
}
```

- Wrap client subtrees in `NextIntlClientProvider` (usually in the locale layout) and pass only the messages the client needs.
- Metadata: translate inside `generateMetadata` with `getTranslations` — don't hardcode `<title>`.
- The **`locales` array is the single source of truth** — routing, middleware, and the add-a-locale step all read it.

## react-i18next

```ts
// i18n.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, vi: { translation: vi } },
  lng: 'vi', fallbackLng: 'vi',
  interpolation: { escapeValue: false },   // React already escapes
});
```

```tsx
'use client';
import { useTranslation } from 'react-i18next';
export function PayButton() {
  const { t } = useTranslation('checkout');   // namespace
  return <button>{t('payButton')}</button>;
}
```

- react-i18next is client-oriented; in App Router it must run in client components (or an SSR-aware wrapper). For heavy App Router use, next-intl fits the server model better — but do not migrate an existing project unasked.
- Set `fallbackLng` deliberately (project default is usually `vi`), and **do not** silently mask missing keys in dev — configure `saveMissing`/a missing-key handler so drift surfaces.
- Use namespaces to split large catalogs; keep them parallel across locales (see [key-management.md](./key-management.md)).

## Locale detection & persistence

- Detect from: URL segment (preferred for SEO & shareable links) → cookie/`localStorage` (returning user's choice) → `Accept-Language` header → default locale.
- **Persist the user's explicit choice** (cookie such as `NEXT_LOCALE`, or a user-profile setting) so a language switch survives navigation and reload.
- Set `<html lang="...">` to the active locale — accessibility and SEO depend on it.
- The language switcher must change the locale through the router/i18n instance (so the URL and formatters update), not just swap visible text.

## Adding a new locale — end-to-end checklist

When the project adds a locale (say `ja`) beyond `en`/`vi`:

1. **Register it** in the single source of truth (`routing.locales` for next-intl, `resources`/`supportedLngs` for i18next). Update middleware/routing config.
2. **Create the catalog** `ja.json` (or `ja/` folder) with **every key** the other locales have — no missing keys (see the parity check in [key-management.md](./key-management.md)). Get real translations; don't ship English-as-placeholder.
3. **Formatting**: confirm dates/numbers/currency use `Intl` with the active locale — new locale should "just work" if you followed [formatting.md](./formatting.md). Check the currency: a new market may use a different `currency` code.
4. **Plurals**: the new language may have plural categories `en`/`vi` don't (`few`, `many`, `zero`). Add those branches to ICU `plural` messages that need them.
5. **RTL** (if the new locale is Arabic/Hebrew/etc.): set `dir="rtl"` on `<html>` for that locale and audit layout/icons/logical CSS properties. Coordinate with `frontend-design`.
6. **Switcher & detection**: add it to the language switcher UI and `Accept-Language` mapping.
7. **Tests**: extend bilingual E2E selectors to the new locale where relevant (see `e2e-flow`), and update the parity test's expected locale set.
8. **Verify** the app renders end-to-end in the new locale — not just that keys exist. See [review-checklist.md](./review-checklist.md).
