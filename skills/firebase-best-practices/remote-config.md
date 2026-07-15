# Remote Config best practices

Remote Config delivers server-controlled parameters to clients (feature flags, tunables, staged rollouts). Its values are **readable by the client** — treat it as public configuration, never as a secret store.

## Security & trust boundary

- **Never put secrets in Remote Config** — API keys, credentials, private URLs. Clients (and anyone inspecting them) can read every parameter and condition value.
- **Never gate security on it.** A feature flag hiding an admin action is UX, not authorization — the real gate is security rules / a Functions check. A tampered client can flip a client-side flag.
- Use **server-side Remote Config** (Admin SDK) when a value must be evaluated in a trusted context (e.g. driving backend behavior) rather than trusting a client-reported flag.

## Parameters, defaults, conditions

- **Always ship in-app defaults** (`setDefaults`) so the app behaves correctly offline or before the first fetch. Don't assume a fetched value exists.
- Name parameters with a **consistent convention** (e.g. `feature_x_enabled`, `checkout_timeout_ms`) and a stable type; document each one. Avoid one param that means different things by context.
- Keep **conditions** minimal and readable; order matters (first match wins). Prefer targeting by audience/version/percentile over sprawling ad-hoc conditions.
- Prune stale flags — dead parameters accumulate and confuse rollout logic.

## Fetch cadence & throttling

- Respect `minimumFetchInterval` — over-fetching gets **throttled** by the service. In production use a sensible interval (e.g. hours); use a low interval only in dev.
- **Separate fetch from activate.** `fetchAndActivate` applies immediately; for a controlled switch, `fetch()` in the background and `activate()` at a safe moment (e.g. next launch) so config doesn't change mid-session and cause UI fl::icker or inconsistent state.
- Handle fetch failure gracefully — fall back to last-activated or in-app defaults.

## Rollouts & change management

- Use **conditions / percentage rollouts** to stage changes; watch metrics, then widen. Don't flip a risky flag to 100% globally in one step.
- Remote Config keeps a **version history** — use it to review and **roll back** a bad change. Treat template changes like deploys: know the blast radius before publishing.
- For anything user-affecting, publish to a test/dev project or a small audience first (dev-first, same as rules/indexes).

## Red flags to fix

- Any secret/credential/private endpoint stored as a parameter.
- Security or entitlement decisions made solely on a client-side flag.
- No in-app defaults → broken behavior before first fetch / when offline.
- Aggressive fetch interval in production (throttling, wasted calls).
- Inconsistent parameter naming/types; abandoned stale flags.
- Big-bang 0→100% rollout of a risky change with no staging or rollback plan.
