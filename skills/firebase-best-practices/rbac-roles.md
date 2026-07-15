# Roles & RBAC (standardization)

The most common Firebase mess is roles scattered across custom claims, `users/{uid}.role`, ad-hoc boolean flags (`isAdmin`), and UI-only checks that disagree with each other. Standardize: **one source of truth per role dimension, least privilege, enforced in rules.**

## Custom claims vs Firestore role docs — decide deliberately

| Criterion | Custom claims | Firestore role doc |
|---|---|---|
| Where | JWT (`request.auth.token.*`) | `users/{uid}` or `memberships/{...}` |
| Rules cost | Free | 1 `get()` read per check (billed, rate-limited) |
| Who can set | **Admin SDK only** (server) | Anyone the rules allow — must gate tightly |
| Freshness | Stale until token refresh (≤1h; force with `getIdToken(true)`) | Immediate |
| Payload limit | ~1000 bytes total across all claims | Unlimited |
| Best for | Coarse, slow-changing, security-critical: `admin`, `tenantId`, `plan`, top-level `role` | Fine-grained/relational/large: per-resource membership, per-team permissions, feature flags |

**Rule of thumb:** coarse security gates → custom claims (cheap in rules, unforgeable). Relational/fine-grained permissions → Firestore docs that the *server* writes and clients can only read. Don't put the same role in both — pick one and make it authoritative.

## A canonical role model

Standardize on a small, documented set. Example baseline:

```
Global roles (custom claim `role`):  owner > admin > member > viewer
Tenant scope   (custom claim `tenantId`):  which org the user belongs to
Per-resource   (Firestore membership doc):  role scoped to one team/project/event
```

- **Name roles consistently** — one casing, one vocabulary (`admin`, not `Admin`/`ADMIN`/`administrator` mixed). Define them once in a shared constant that both app code and rules comments reference.
- **Model hierarchy explicitly** rather than sprinkling booleans. Replace `isAdmin`, `isSuperAdmin`, `canEdit` flags with a single ordered `role`, and derive capabilities from it.
- **Least privilege:** default new users to the lowest role. Never grant `admin` as a default or via client-writable fields.

Encoding a hierarchy in rules:
```
function roleRank(r) {
  return r == 'owner' ? 4 : r == 'admin' ? 3 : r == 'member' ? 2 : r == 'viewer' ? 1 : 0;
}
function atLeast(r) { return isSignedIn() && roleRank(request.auth.token.role) >= roleRank(r); }
// allow update: if atLeast('member');
```

## Tenant-scoped roles

A user may be `admin` in tenant A and `viewer` in tenant B. Two clean patterns:

1. **Membership docs** (`memberships/{tenantId}_{uid}` with `{ tenantId, uid, role }`): flexible, immediate, costs a `get()` in rules. Good when membership changes often.
2. **Structured claims** (`request.auth.token.tenants = { t1: 'admin', t2: 'viewer' }`): free in rules, but bounded by the ~1KB claim budget and stale until refresh. Good for a handful of tenants per user.

Always require the doc's `tenantId` to match the caller's tenant (see multi-tenant isolation in [security-rules.md](./security-rules.md)).

## Setting custom claims (server only)

Claims are set with the Admin SDK — never from a client. Wrap it in an authorized Cloud Function / server route.

```js
import { getAuth } from 'firebase-admin/auth';

// Only callable by an existing admin (check the caller's own claims first!).
await getAuth().setCustomUserClaims(uid, { role: 'admin', tenantId: 'acme' });
```

- **Merge, don't clobber.** `setCustomUserClaims` replaces the entire claims object. Read existing claims and spread them if you're only changing one dimension.
- **Authorize the setter.** The function that sets claims must verify the caller is allowed to grant that role (prevent privilege escalation). Log every grant/revoke to an audit trail.
- **Keep claims small** — under ~1000 bytes total. Store rich profile/permission data in Firestore, not the token.

## The token-propagation gotcha

Custom claims are baked into the ID token. After you change a user's claims, **their existing token still has the old claims** until it refreshes (up to 1 hour), so rules and `request.auth.token` see stale roles.

```js
// Client: force a refresh so new claims take effect immediately
await auth.currentUser.getIdToken(true);
// Read them back:
const { claims } = await auth.currentUser.getIdTokenResult(true);
```

Pattern: after a server-side claim change, signal the client (e.g. a Firestore `refreshTime` field the client listens to) to call `getIdToken(true)`. To revoke access immediately regardless of token TTL, call `getAuth().revokeRefreshTokens(uid)` and enforce with `checkRevoked` on the server / a rules token-time check.

## Keep rules and app authorization in sync

The rules are the enforcement boundary; app code is convenience. When both check a role, they must agree:

- Derive UI capability from the **same role source** the rules use (the ID token's claims), not a separate cached flag.
- If the app hides an "Edit" button but the rules would allow the write, you have a security hole, not a UX bug — fix the rule.
- If the app shows an action the rules deny, users hit confusing permission errors — align them.

## Red flags to fix

- The same role stored in both a claim and a Firestore doc, written independently → they drift. Pick one authoritative source.
- Client-writable role/permission fields (`allow update` lets the user set their own `role`). Roles must only be set server-side.
- Boolean flag soup (`isAdmin`, `isMod`, `isSuper`) instead of one ordered role.
- Inconsistent role names across code, rules, and data.
- `admin` (or any elevated role) as a default value.
- Claim changes with no client refresh path → users stuck with stale permissions.
