# API & Data-Model Contract — MUST FOLLOW

API routes and persisted data shapes are a **contract shared by every client** (web, mobile apps,
other services). Clients rarely share types, so the compiler cannot see a break — it surfaces at
runtime, and installed mobile builds keep calling the old shape for weeks.

Reviewed by `api-data-reviewer` (review gate). Fill in the project's clients and conventions below.

## 1. Versioning — additive-only by default

- **Safe:** new route; new OPTIONAL request field (server defaults it); new response field; new enum
  value only if every client tolerates unknown values.
- **Breaking:** rename/remove a field, change its type or meaning, optional → required, change status
  codes / error shape / pagination shape, remove a route, rename a wire enum value.
- **Shipping a breaking change:** add the new shape ALONGSIDE the old → ship clients reading the new
  one → wait for the client rollout → remove the old in a separate change. Introduce explicit
  versioning (`/v2` path or a client-version header + minimum-version gate) only when a change cannot
  be made additive — that is an architecture decision (`arch-advisor`).

## 2. API shape — serve every client

- Return data, not presentation; shared labels come from one shared function or a server field.
- Auth that non-browser clients can use (bearer token), not cookie-only.
- Lean, paginated responses (limit + cursor); never "return everything, filter on the client" for a large set.
- Errors: one house shape with a stable machine-readable `code` clients branch on; never change an existing code.
- Timestamps serialized (ISO string or epoch ms), never DB-native objects.
- Idempotent writes for anything a client may retry on a flaky network.

## 3. Data model

- Scoping/tenancy fields on every new record per project rules; immutable once set.
- New field on an existing collection/table = optional + defaulted on read, or ship a backfill.
- One declaration per type (shared package), schema docs updated in the same change.
- Every new query: filtered, bounded (limit/cursor), index added in the same change; no N+1 per row.
- No unbounded arrays/maps on one record — growing lists become a child collection/table; shard hot counters.

## 4. Read cost

State the cost of every new/changed read up front: rows per call × calls per day (× viewers for
realtime listeners, × devices for polls, × app resumes for mobile refetch). Prefer a cached/indexed
read or one bounded endpoint shared by all clients over per-client duplicate reads.

## Review checklist
- [ ] Contract change is additive, or has an add-alongside → migrate → remove plan.
- [ ] Every other consumer checked (or marked "not verified").
- [ ] Lean + paginated; stable error `code`; timestamps serialized; retry-safe writes.
- [ ] Scoping fields; new fields optional/backfilled; type declared once; schema docs updated.
- [ ] Every new query bounded + indexed; read cost stated.
