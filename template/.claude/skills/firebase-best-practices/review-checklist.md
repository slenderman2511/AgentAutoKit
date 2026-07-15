# Correction pass: audit → fix → verify

Use this when asked to "audit", "harden", "make production-safe", or "optimize" a Firebase project. Work top-down by severity; verify with the emulator; never auto-deploy.

## 1. Locate the artifacts

```bash
# Rules & index config
firestore.rules            storage.rules            firestore.indexes.json
firebase.json              .firebaserc
# Auth / roles code (grep the repo)
```
Search points:
- `setCustomUserClaims` — where roles are granted (must be server-only + authorized).
- `request.auth.token` — which claims the rules trust.
- `getIdToken` / `getIdTokenResult` — token/claim refresh handling.
- `initializeApp` with a service account / `firebase-admin` — Admin SDK usage (server only).
- Client queries (`where`, `orderBy`, `collectionGroup`) — must mirror rules constraints and have backing indexes.

## 2. Audit — red-flag checklist

**Security rules** ([security-rules.md](./security-rules.md))
- [ ] No `allow read, write: if true;`, no blanket `match /{document=**}` grant, no expired dev-mode open rule.
- [ ] `rules_version = '2'` set.
- [ ] Write rules validate `request.resource.data` (shape via `hasOnly`, types, immutables, no client-set privileged fields).
- [ ] `create` uses `request.resource.data`; `delete` uses `resource.data`.
- [ ] Ownership/tenant rules exist AND the client queries carry the matching `where` (rules aren't filters).
- [ ] `get()`/`exists()` used only where a custom claim can't do the job; call count within limits.

**Roles / RBAC** ([rbac-roles.md](./rbac-roles.md))
- [ ] One source of truth per role dimension; claim and doc don't drift.
- [ ] Roles set server-side only; no client-writable `role`/permission field.
- [ ] Consistent role vocabulary; hierarchy modeled as an ordered role, not boolean soup.
- [ ] Lowest-privilege default; no elevated default role.
- [ ] Claim-change → client refresh path exists (`getIdToken(true)`).

**Auth** ([auth.md](./auth.md))
- [ ] No service-account key in the repo or client bundle.
- [ ] Email-enumeration protection on; generic sign-in errors.
- [ ] App Check enabled (at least monitoring) on public backends.
- [ ] MFA enforced for elevated roles; password policy set.
- [ ] Server routes verify ID tokens; don't trust client-sent `uid`/`role`.
- [ ] Revocation path exists for compromised accounts.

**Indexes** ([indexes.md](./indexes.md))
- [ ] `firestore.indexes.json` in version control, in sync with deployed indexes.
- [ ] Composite indexes exist for every multi-field / filter+order query (no swallowed `FAILED_PRECONDITION`).
- [ ] Single-field exemptions on large arrays/blobs and never-queried fields.
- [ ] Cursor pagination (not `offset`); `count()`/aggregation instead of full-collection reads.
- [ ] No high-volume monotonic indexed field creating a hotspot.

## 3. Fix — order of operations

1. **Open access / privilege escalation** (anything that lets the wrong party read or write). Highest severity — fix first.
2. **Missing validation** allowing data corruption or field injection.
3. **Role inconsistencies** (drift, client-writable roles, naming).
4. **Correctness of indexes** (queries that error on missing indexes).
5. **Efficiency** (wasteful indexes, offset pagination, over-broad `get()`).

Make the smallest correct change; keep rule/query/role changes together so they stay consistent.

## 4. Verify

```bash
firebase emulators:start --only firestore,storage,auth
# Run rules unit tests: assert BOTH allow and deny paths for every rule touched.
# Run the affected queries against the emulator with indexes loaded — confirm no FAILED_PRECONDITION.
```
An unverified rule is an unfinished fix. Test the deny path, not just the happy path.

## 5. Propose the deploy — never auto-deploy

- Show the `firestore.rules` / `firestore.indexes.json` diff.
- State the blast radius: which collections/queries/roles change and what could break.
- Deploy dev first, verify in the dev app, then prod **only after explicit human confirmation**:
  ```bash
  firebase deploy --only firestore:rules --project dev
  firebase deploy --only firestore:indexes --project dev
  # prod only after sign-off
  ```
- If the repo has a project-specific deploy path (e.g. a blocked `firebase deploy` + Admin SDK deployer script), follow that project's skill instead of running `firebase deploy` directly.
