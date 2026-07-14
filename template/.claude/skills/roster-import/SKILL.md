---
name: roster-import
description: Use when importing an external player roster (XLSX spreadsheets) into a tournament event's Firestore entries — e.g. "import the VPC roster", "load these registration spreadsheets", "bulk-add players from Excel" — or when assessing duplicates from, verifying, or rolling back such an import. Covers the assess → dry-run → APPLY=1 → verify → rollback pipeline in scripts/_import_vpc_roster.ts and its companion scripts.
---
# Roster Import (XLSX → Firestore entries)

Import spreadsheet rosters into `events/{eventId}/entries` + `events/{eventId}/athletes`, minting provisional users only when no existing identity matches. Reference implementation: the VPC Future Stars import (`vpc-future-stars-2026`, tenant `vpc`).

## Hard safety rules (non-negotiable)

- **Every Firestore write from Claude Code requires explicit user confirmation first** (`.claude/rules/firebase-data-safety.md`). State collection, operation, and doc count; show the exact command; wait for approval. Bulk ops (>10 docs) must show a dry-run count first.
- **Never run APPLY against prod without a clean dry-run and a post-import verify.** All four scripts load `.env.production` — treat every run as production.
- **Always keep a rollback path.** Every import write is tagged so `_rollback_import.ts` can find it: entries get `createdVia: 'roster_import'` + `createdBy: 'roster-import'` + `importSource`, athlete docs get `createdVia: 'roster_import'`, minted users get `provisionalCreatedBy: 'roster-import'`. Never strip these tags; a new import for a different event needs its own distinct tag.
- **Tenant isolation** (`.claude/rules/multi-tenant.md`): `events` and everything under `events/{eventId}/` is tenant-scoped. Scripts hardcode `process.env.TENANT_ID = 'vpc'` and write `tenantId: 'vpc'` on every entry. A new import must set both. `users` is the global collection — extra caution; deletes there are rollback-only.
- **Identity = normalized name + birth year. Never match by phone. Never write `cccd`.** Verify confirms cccd count is 0.
- **DRY-RUN is the default.** Writes/deletes happen only when `APPLY=1` is set explicitly.

## Pipeline (in order)

### 1. Assess duplicates (read-only)

```bash
npx tsx scripts/_assess_import_dups.ts
```

Reports which `roster_import` athletes duplicate a pre-existing (non-import) athlete by name+year in the same event. Run it before an import (baseline) and after (should add no new dups). No flags; no writes.

### 2. Dry-run the import

```bash
npx tsx scripts/_import_vpc_roster.ts          # dry-run (default)
```

Prints: distinct persons (split into REUSE-existing vs new), new entries vs skipped (already present in category+division), and flagged persons (`NO-DOB`, `NO-GENDER`, `[approx]`). Review flags with the organiser before applying — the script has a `GENDER_OVERRIDE` map for organiser-confirmed ambiguous cases.

### 3. Apply (only after user confirms)

```bash
APPLY=1 npx tsx scripts/_import_vpc_roster.ts
```

### 4. Verify

```bash
npx tsx scripts/_verify_import.ts
```

Checks all `roster_import` entries are `status='confirmed'`, `paymentStatus='UNPAID'`, `ratingSystem='PVNA'`, counts new athlete docs, and confirms zero members carry `cccd`. Then re-run step 1 to confirm the import created no duplicate identities.

### 5. Rollback (if the import is bad)

```bash
npx tsx scripts/_rollback_import.ts            # dry-run: lists counts + sample entries
APPLY=1 npx tsx scripts/_rollback_import.ts    # deletes, batched 400/commit
```

Deletes, in order: entries where `createdVia == 'roster_import'`, athlete docs whose id is a minted uid, then `users` where `provisionalCreatedBy == 'roster-import'`. Reused identities are untouched (only minted ones carry the tag). Confirm the dry-run sample with the user before APPLY — user deletion is irreversible.

## What the import actually does

- **Env/args:** no CLI args. `APPLY=1` env var is the only switch. Loads `.env.production` via dotenv; sets `TENANT_ID`. Event id and XLSX directory are hardcoded constants (`EVENT_ID`, `DIR`) — edit them for a new import.
- **Parsing:** reads XLSX files with the `xlsx` package; per-file column layouts are bespoke. Names are normalized (`ncol`: strip Vietnamese diacritics, lowercase, collapse). Category strings parse to `ms-junior` / `ws-junior` / `md-junior` / `wd-junior` / `xd-junior` + division `u10`–`u18`, mode `solo` | `pair`.
- **DOB:** parses Excel serials and `dd/mm/yyyy`; year-only DOB becomes `YYYY-01-01` with `birthdayApprox: true`.
- **Skip logic:** an entry is skipped if all its members already exist in that category+division (name + compatible year). Cancelled/rejected entries don't count as existing.
- **Identity reuse:** before minting, match against current event entries and athlete docs by name + compatible year. Reused members get `identityType: 'admin_manual_link'`; new ones get `walkin_raw`.
- **Minting:** `createProvisionalUser({ adminUid: 'roster-import', ... })` (from `src/lib/firebase/admin/identityMatching.ts`) writes a `users` doc with `provisional: true`, `authBacked: false`; the script then writes the athlete doc directly (`entranceFeeStatus: 'Not_Required'`, `onboardingCompleted: true`, `nationality: 'VN'`).
- **Entry shape:** `name` ("A / B"), `categoryId`, `divisionId`, `mode`, `captainUid` (first member), `globalUids`, `members[]` (with `athleteId`, `legacyUid`, `isCaptain`, `rating: 0`), `status: 'confirmed'`, `paymentStatus: 'UNPAID'`, `ratingSystem: 'PVNA'`, `isWalkIn: true`, `tenantId`.

## Data-model notes

- Roster-visible entry statuses are `confirmed` and `pending_verification` (`src/lib/delegationRoster.ts`); imported entries are `confirmed`, so they appear on public rosters immediately.
- Members are keyed by `athleteId || uid`; `src/lib/teamRoster.ts` rating-cap checks read `duprRating`/`rating` — imported members have `rating: 0` (unrated, flagged for admin assessment, non-blocking).

## Adapting to a new roster

1. Copy `_import_vpc_roster.ts`; change `EVENT_ID`, `DIR`, `TENANT_ID`/`tenantId`, and the per-file column parsers.
2. Use a fresh `createdVia`/`createdBy` tag pair and update the assess/verify/rollback scripts to match it.
3. Keep the same order: assess → dry-run → user confirmation → APPLY → verify → assess again.
