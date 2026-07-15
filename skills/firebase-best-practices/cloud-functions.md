# Cloud Functions best practices

Functions run privileged server code (Admin SDK bypasses rules), so they are the place to enforce authorization that clients can't — and the place a missing check becomes a full breach.

## Pick the right trigger

| Trigger | Use for | Auth model |
|---|---|---|
| `onCall` (callable) | Client-invoked RPC from the app | SDK passes the user's ID token → `request.auth` populated & verified for you; supports App Check |
| `onRequest` (HTTP) | Webhooks, public/3rd-party endpoints | **You** verify identity — parse & `verifyIdToken`, or validate a webhook signature |
| Background (`onDocumentWritten`, `onObjectFinalized`, Pub/Sub, schedule) | React to data/events | No end-user; runs as service account — do your own authz on the payload |

Prefer `onCall` for app-to-backend calls: it wires up auth and App Check. Use `onRequest` only when you genuinely need a raw HTTP endpoint, and then do the verification yourself.

## Never trust the client

- In `onCall`, gate on `request.auth` (reject if null) and check the caller's role/claims before privileged work — don't assume "callable = authorized."
- Never trust a `uid`, `role`, `amount`, or `isAdmin` sent in the payload. Derive identity from `request.auth`, derive role from verified claims or a server-read doc.
- Validate and type-check every input. Reject unexpected shapes early.
- Enforce **App Check** on callable/HTTP functions (`enforceAppCheck: true`) to block non-genuine clients.

```ts
export const setUserRole = onCall({ enforceAppCheck: true }, async (request) => {
  if (!request.auth) throw new HttpsError('unauthenticated', 'Sign in required');
  const caller = request.auth.token;
  if (caller.role !== 'admin') throw new HttpsError('permission-denied', 'Admins only');
  // ... validate request.data, then act
});
```

## Idempotency (critical for background & retried functions)

Background functions have **at-least-once** delivery — they can fire more than once for one event. Any function that isn't naturally idempotent (increments, sends, charges, fan-out writes) must dedupe.

- Key work by the event ID / a deterministic doc ID and use a transaction or `create`-if-absent to make retries no-ops.
- Enable retries (`retry: true`) only for functions you've made idempotent; otherwise a retry storm corrupts data.

## Performance & cost

- **Cold starts:** keep dependencies lean, do heavy init lazily/at module scope (reused across warm invocations), and set `minInstances` for latency-critical functions. Don't over-provision — min instances bill even when idle.
- **Concurrency (2nd gen):** a single instance can serve multiple requests — ensure your code is concurrency-safe (no shared mutable globals per-request).
- **Set `region`** close to your data/users; cross-region calls add latency and egress cost.
- **Bound work:** set sane `timeoutSeconds` / `memory`; avoid unbounded loops over large collections in one invocation (paginate or fan out).
- Reuse clients (Admin SDK, HTTP agents) at module scope; don't re-init per request.

## Secrets & config

- Store secrets in **Secret Manager** (`defineSecret` / `--set-secrets`), never hardcoded and never in client-readable config. Don't log them.
- Don't commit service-account keys; on GCP use the runtime's default credentials.
- Validate required env/secrets at startup and fail fast if missing.

## Errors & observability

- In callables, throw `HttpsError` with a proper code (`unauthenticated`, `permission-denied`, `invalid-argument`, `failed-precondition`) — the client SDK maps these cleanly. Don't leak internals in the message.
- Catch and log with structured logging (`functions.logger`); include a correlation/event id. Let unexpected errors surface (so retries/alerts work) rather than swallowing them.

## Red flags to fix

- `onRequest` handler doing privileged work with no token/signature verification.
- `onCall` that reads `request.data.uid`/`role` instead of `request.auth`.
- Non-idempotent background function with retries on (or a naturally-retried trigger with no dedupe).
- Secrets in code, plaintext env, or logs.
- Heavy work / client init inside the handler instead of module scope.
- App Check not enforced on public callable endpoints.
- Unbounded collection scans in a single invocation.
