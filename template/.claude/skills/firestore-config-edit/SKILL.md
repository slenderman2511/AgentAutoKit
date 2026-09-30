---
name: firestore-config-edit
description: Edit tenant/event CONFIG directly in Firestore (theme, brand, feature flags, nav text) and bust the app cache so the change shows up. Use whenever flipping something on a tenant or event doc outside the admin UI — brand.themeClass, showNavText, landing config, featureFlags. Explains the 1-hour tenant-config cache, the tags each doc uses, and the GET /api/revalidate bust endpoint.
---

# Editing tenant/event config in Firestore

Editing a `tenants/*` or `events/*` doc directly (Firestore console or an MCP
`firestore_update_document`) does **NOT** auto-bust the app cache — the admin UI routes call
`revalidateTag(...)` for you, but a raw Firestore write does not. The change then waits out
the cache TTL (up to **1 hour** for tenant config). This has bitten the HPF theme rollout.

## The cache map (verbatim facts)

| What you edited | Firestore path | Cache tag | TTL | Source |
|---|---|---|---|---|
| Tenant config (brand, theme, landing, nav text, feature flags) | `tenants/{tenantId}` | `tenant-config` | **3600s (1h)** | `tenantConfig.server.ts:128` |
| Event list (landing status) | `events` (by tenantId) | `events`, `events-all` | 60s | `eventService.server.ts:7` |
| Event detail | `events/{eventId}` | `events`, `event-${eventId}` | **86400s (24h)** | `eventService.server.ts:8` |

Event detail is cached **24 hours** — after editing an event doc directly you almost always
need the bust; 60s list TTL is short but detail is not.

## Bust the cache

`GET /api/revalidate` — **admin-only** (event admin or above). It revalidates a fixed set of
tags (`tenant-config`, `events`, `tournament_groups`, `events-all`, `schedules`, `venues`,
`global-venues`) plus the home and `[eventId]` paths. Defined at
`src/app/api/revalidate/route.ts`, gated by `verifyAnyAdmin()` in
`src/lib/firebase/serverAuth.ts`.

It requires `Authorization: Bearer <Firebase ID token>`. A bare `curl` gets **401**, and so
does **opening the URL in a browser** — address-bar navigation cannot send an `Authorization`
header, and Firebase ID tokens live in IndexedDB, not cookies. There is no session-cookie
fallback and no secret bypass.

**The only practical way to bust manually:**

> Admin settings → **Information** tab → **"Làm mới trang công khai"** button
> (`/[eventId]/admin/settings?tab=information`, next to Save).

```bash
# Scripted, only if you already hold an admin ID token:
curl -s -H "Authorization: Bearer $ID_TOKEN" https://<tenant-domain>/api/revalidate
```

**Claude cannot call this endpoint** — it has no admin ID token. After a direct Firestore
config edit, tell the user to click that button; do not report the change as visible until
they confirm the bust.

Note it takes **no params** — it busts the whole tag set, not one doc. There is no way to
bust a single event via this endpoint; that's fine, it's cheap.

## Procedure for a direct config edit

1. **Confirm target project** first: `firebase_get_environment` (dev vs prod). Editing prod
   tenant config is a prod write.
2. **State the change and get user confirmation** (firebase-data-safety cardinal rule):
   collection, doc path, field, old→new value, which tenant, dev or prod.
3. Apply the write (MCP `firestore_update_document` or console).
4. **Ask the user to click** admin settings → Information → "Làm mới trang công khai".
   The endpoint is admin-gated and Claude cannot call it; a browser URL will 401.
5. **Verify** the rendered page reflects the change (e.g. new `themeClass` in body class,
   nav text visible). If it doesn't within a few seconds, re-run the bust; do not assume.

## Rules that still apply

- `tenantId` is **immutable** — never mutate it on an existing doc (AGENTS.md rule 6).
- No tenant-specific `if (tenantId === …)` branches — config drives behavior (rule 14). If
  you're editing config to change behavior, that's correct; adding a code branch is not.
- `tenantSecrets/{tenantId}` and `system_config/*` are **server-only** (firestore.rules
  denies clients) — don't expose their values in client-readable config.
- Prefer the admin UI route when one exists (it busts cache automatically):
  `POST /api/admin/tenant` and `POST /api/admin/events/[eventId]` already call the right
  `revalidateTag`. Direct edits are for fields those routes don't cover.
