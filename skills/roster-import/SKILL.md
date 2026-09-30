---
name: roster-import
description: Import a roster from Excel (.xlsx) into Firestore as event entries for this pickleball tournament app. Use when the user hands over a spreadsheet of athletes/delegations and asks to seed entries, or references files under docs/tenants/**. Encodes the 6 data-seeding rules, the exact Entry/Participant shapes, doubles pairing, dry-run counting, and the mandatory confirm-before-write gate.
---

# Roster import → Firestore entries

Turns a `.xlsx` roster into `events/{eventId}/entries/*` documents. There is **no shared
xlsx helper** in this repo — each import is its own script under `scripts/`, all following
the same shape. This skill is that shape. Two good references to copy from:
`scripts/one-off/seed-hpf-members.mjs` (batched, env-parametric) and `scripts/one-off/_import_vpc_roster.ts`
(builds real doubles/singles entries with members).

## Hard rules (from CLAUDE.md "Data Seeding Rules" — never skip)

1. **`divisionId` MUST be `'default'`**, never the categoryId. The brackets page keys on
   `categoryId____divisionId`; `thcs-ms____thcs-ms` never matches `thcs-ms____default`.
2. **No `undefined` in any document** — Firestore rejects it. Use spread conditionals:
   `...(phone ? { phoneNumber: phone } : {})`, never `phoneNumber: phone || undefined`.
3. **Trim every env var**: `const TENANT_ID = (process.env.TENANT_ID || '').trim();`
   (Vercel/CI values carry trailing newlines → silent query misses.)
4. **Doubles pair every 2 athletes.** Odd count → last entry has 1 member; **flag it for
   review**, do not silently drop.
5. **Every write is tenant-scoped and confirmed by the user first** — see the gate below.
6. New docs include the authoritative `tenantId` (from `getTenantId()`), never from input.

## Exact document shapes (verbatim from `src/lib/firebase/eventService.ts`)

**Entry** (`eventService.ts:304`) — required fields to populate on import:

```ts
{
  name: string,              // team/pair display name
  eventId: string,
  categoryId: string,        // e.g. 'amateur_doubles_mens'
  divisionId: 'default',     // ALWAYS 'default' unless the category truly has >1 division
  captainUid: string,        // uid of first member (or a provisional id)
  members: Participant[],
  status: 'confirmed',       // imported rosters are confirmed
  mode: 'solo' | 'pair' | 'team',   // singles → 'solo', doubles/mixed → 'pair'
  createdAt: string,         // new Date().toISOString()
  ...(delegationId ? { delegationId } : {}),   // only for delegation events
}
```

**Participant / member** (`eventService.ts:229`):

```ts
{
  athleteId: string,         // resolved user id, or a provisional/walk-in id
  fullName: string,
  gender: Gender,            // canonical: 'mens'|'womens'|'boys'|'girls' etc — see category-naming rule
  status: 'confirmed',
  rating: 0,                 // 0 for imported data with no known rating
  identityType: 'walkin_raw',   // for raw imported athletes with no linked account
}
```

`status` and `identityType` are unions — the imported-roster values are `'confirmed'` and
`'walkin_raw'`. Full union lists live at those line refs; read them before using any other value.

## Reading the sheet

```js
import XLSX from 'xlsx';                       // or: const XLSX = require('xlsx')
const wb = XLSX.readFile(EXCEL_PATH);
const ws = wb.Sheets[wb.SheetNames[0]];
const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' }); // array-of-arrays
// row[0] is usually the header; map columns explicitly, do not trust order blindly.
```

Define inline `str()` / `num()` coercers per script (as `seed-hpf-members.mjs:64` does) —
sheet cells are often numbers where you expect strings.

## Workflow (MUST follow — this is a Firestore write)

1. **Parse & map** columns → athletes. Log how many rows, how many athletes, how many
   have missing gender/name.
2. **Pair for doubles** (every 2). Report the odd-one-out count explicitly.
3. **Validate** against the 6 rules — run `/seed-check` on the script before executing.
4. **Dry-run count**: print exactly how many entry docs and member docs will be written,
   to which `events/{eventId}/entries` path, for which tenant. Write nothing yet.
5. **State it and wait for explicit user confirmation** (per `.claude/rules/firebase-data-safety.md`).
   Template:
   > I will write 179 entries (358 members) to `events/bach-dang-open-2026/entries`
   > for tenant `hpf-haiphong`, all status=confirmed, divisionId=default. 3 odd athletes
   > flagged (1-member entries). Command: `TENANT_ID=hpf-haiphong node scripts/seed-<x>.mjs`. Proceed?
6. **Only after "yes"**, run with `TENANT_ID=<tenant> node scripts/…`. Batch writes at
   ≤400 docs per `db.batch()` (Firestore limit is 500; leave headroom).

## Anti-patterns that have bitten this repo

- `divisionId: categoryId` → bracket never renders the entries (rule 1).
- Forgetting `TENANT_ID` prefix → script errors before init, or worse writes to wrong tenant.
- Writing before the dry-run/confirm → violates firebase-data-safety cardinal rule.
