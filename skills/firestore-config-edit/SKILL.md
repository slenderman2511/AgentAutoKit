---
name: firestore-config-edit
description: Use when editing, seeding, or syncing Firestore configuration in pickleball-tour — tenant config (tenants/{tenantId}, landing/theme/brand), event config (events/{eventId} fields like delegationConfig, prizeStructure, infoSections), platform config (system_config/*, global_settings), or deploying firestore.rules. Triggers - "change tenant theme", "seed event config", "update delegation quota", "sync config to dev", "deploy Firestore rules".
---
# Firestore Config Editing (pickleball-tour)

## Where config lives

| Path | Scope | Client write access (firestore.rules) |
|---|---|---|
| `system_config/{docId}` (e.g. `pvna`, `broadcast`) | Platform-global secrets/integrations | `allow read, write: if false` — Admin SDK scripts ONLY |
| `global_settings/{document=**}` | Platform-global | read public, write `isGlobalAdmin()` |
| `counters/{document=**}` | Platform-global | read public, write `isGlobalAdmin()` |
| `tenants/{tenantId}` | Tenant doc: `brand.*`, `landing.type`, `landing.sections` | update `isTenantAdminOf(tenantId)`; create/delete `isGlobalAdmin()` |
| `tenants/{tenantId}/settings/{document=**}` | Tenant settings | write `isTenantAdminOf(tenantId)` |
| `events/{eventId}` | Per-event config fields: `delegationConfig`, `infoSections`, `rulesAndFormat`, `prizeStructure`, `registrationInfo`, `restrictions`, `translations`, `brand.*`, `status` | update by global/tenant/event admin, gated on `resource.data.tenantId` |
| `events/{eventId}/categories/{catId}` | Category/division config (`tier`, `type`, `gender`, `teamConfig`, `divisions[]`) | event-scoped admin |

Environments: PROD = `pickleball-tour-prod` (`.env.production`), DEV = `pickleball-tour-dev` (`.env.development`). Scripts read `FIREBASE_PROJECT_ID` / `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY` from these files.

## Hard safety rules (from .claude/rules/firebase-data-safety.md)

1. **Every Firestore write/update/delete from Claude Code MUST be confirmed by the user first.** State collection, doc path, operation, doc count; show the exact command; wait for explicit y/n.
2. **Never hand-edit PROD config without the same change tested on DEV first.** Edit dev, verify in the dev app, then re-run against prod.
3. **Tenant scoping:** never query or mutate tenant-scoped data (`events`, `invoices`, `notifications`, `audit_logs`, `integrations`, and all `events/{eventId}/` subcollections) without a `tenantId` filter. Prefix tenant-scoped scripts: `TENANT_ID=vpc node scripts/my-script.mjs <eventId>`. Global collections (`users`, `global_settings`, `counters`, `system_config`) need no TENANT_ID.
4. **No per-tenant if/else in code** — config lives in Firestore (`tenant.brand`, `tenant.landing.type`, `event.brand.*`), never hardcoded.
5. **Bulk ops (>10 docs): dry-run count first.** Batch writes >100 docs always dry-run. Never `deleteDoc`/`deleteCollection` on prod, never touch `users/` cross-tenant, unless the user explicitly asks.
6. **Backup before destructive ops:** clone the affected event to dev (`clone_event_to_dev.ts`) before any script that clears-and-reseeds (e.g. the category reseed in `seed_fpt_hssv_dev_config.ts` deletes all existing categories first).

## Safe edit workflow

1. **Read current state** (reading event config / public fields needs no confirmation; sensitive collections do).
2. **Write or reuse a seed script** targeting DEV. Follow the existing pattern: load env via dotenv, import `adminDb` from `../src/lib/firebase/admin`, print the target project (`🚀 TARGET: ...`) before writing.
3. **Run against DEV, verify in the dev app**, then run the same script against PROD with user confirmation.
4. Use `{ merge: true }` for additive config edits; `{ merge: false }` only when a full overwrite is intended (that is what the sync/clone scripts use).

## Script commands (exact)

**Seed platform config (system_config):**
```bash
node scripts/seed-pvna-config.mjs                       # from PVNA_PARTNER_* env vars
node scripts/seed-pvna-config.mjs --partner-id=sporttora --api-key=pk_... --api-secret=sk_...
```
Writes `system_config/pvna` with merge. Requires FIREBASE_PROJECT_ID / FIREBASE_CLIENT_EMAIL / FIREBASE_PRIVATE_KEY; no TENANT_ID (global collection).

**Seed event config (note the asymmetric env defaults — check before running):**
```bash
npx tsx scripts/seed_fpt_hssv_dev_config.ts             # defaults to DEV; --prod targets prod
npx tsx scripts/seed_fpt_hssv_delegation_config.ts      # defaults to PROD; --dev targets dev
```
`seed_fpt_hssv_dev_config.ts` updates `events/fpt-hssv-2026` (full config incl. `delegationConfig`, `infoSections`, `prizeStructure`) and DELETES + reseeds all `categories` docs. `seed_fpt_hssv_delegation_config.ts` only sets `delegationConfig` (blocks `thcs`/`thpt`/`cd-dh`, quota, medal scoring).

**Sync config PROD → DEV (dry-run by default):**
```bash
node scripts/sync-broadcast-config-to-dev.mjs           # dry-run: prints masked config + plan
node scripts/sync-broadcast-config-to-dev.mjs --write   # copies system_config/broadcast to DEV (merge:false), sets events/tbe-newbie-2026 → TOURNAMENT_READY
```
Model new sync scripts on this: prod app read-only, dev app write target, secrets masked in output, explicit `--write` gate.

**Clone data PROD → DEV:**
```bash
npx tsx scripts/clone_firestore.ts                                        # ALL root collections, recursive, merge:false overwrite of DEV
npx tsx scripts/clone_event_to_dev.ts [eventId]                           # one event + subcollections + tenant doc (default fpt-hssv-2026)
npx tsx scripts/clone-event-prod-to-dev.ts <eventId> [--target-tenant <tenantId>]  # needs pickleball-tour-{prod,dev}-firebase-adminsdk-*.json in root
```
`clone_firestore.ts` is a full overwrite of DEV — confirm before running; never point it at prod as destination.

## Deploying firestore.rules

`firebase deploy` (and `--only firestore:rules|firestore:indexes|storage`) is BLOCKED in settings.json. Use the Admin SDK deployer instead — and never auto-deploy:

```bash
node scripts/deploy-firestore-rules.mjs dev    # test rules changes on dev first
node scripts/deploy-firestore-rules.mjs prod   # only after dev verification + explicit user "deploy" confirmation
```

Before deploying: show the `firestore.rules` diff, explain which collections/queries are affected and what could break, wait for explicit confirmation. The script reads credentials from `.env.development` / `.env.production` and releases via `releaseFirestoreRulesetFromSource` (equivalent to `firebase deploy --only firestore:rules`).

## Verify after any config change

- Print the target project ID before writing; re-read the doc after writing and echo key fields (mask secrets: show first/last 4 chars only, as `sync-broadcast-config-to-dev.mjs` does).
- For theming config, confirm `tenant.landing.type` is one of: `arena`, `federation`, `club-house`, `retreat`, `flex-league`, `portal`.
- For event status changes, use the canonical statuses (`DRAFT`, `PUBLISHED`, `REGISTRATION_OPEN`, `REGISTRATION_CLOSED`, `LIVE`, `COMPLETED`, `CANCELLED`, plus operational ones like `TOURNAMENT_READY`).
