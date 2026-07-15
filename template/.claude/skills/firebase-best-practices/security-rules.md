# Security Rules (Firestore & Storage)

Security rules are the **only** authorization layer for the client SDKs. They must fully enforce both *who can do what* and *what shape the data may take*. Client/UI checks are UX only.

## Deny by default

Every path is denied until a `match` explicitly allows it. Never widen the default.

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // ❌ NEVER: grants the entire database to anyone
    // match /{document=**} { allow read, write: if true; }

    // ✅ Grant per collection, narrowly.
    match /posts/{postId} {
      allow read: if true;                      // public read is a deliberate choice
      allow create: if isSignedIn() && isValidPost();
      allow update, delete: if isOwner(resource.data.authorId);
    }
  }
}
```

- `rules_version = '2'` is required for `match /{name=**}` recursive semantics and for modern Storage rules. Always set it.
- Split `read`→`get`/`list` and `write`→`create`/`update`/`delete` when they differ. `list` is where over-broad reads leak whole collections.
- A recursive `match /{document=**}` inside a collection applies to all nested subcollections — only use it when you truly mean "and everything below."

## Helper functions — write authz once

Factor repeated checks into functions. They read better and are the single place to fix a bug.

```
function isSignedIn() { return request.auth != null; }
function uid() { return request.auth.uid; }
function isOwner(ownerId) { return isSignedIn() && uid() == ownerId; }

// Role via CUSTOM CLAIM — free, no document read:
function hasRole(role) { return isSignedIn() && request.auth.token.role == role; }
function isAdmin() { return hasRole('admin'); }

// Role via FIRESTORE LOOKUP — costs 1 document read, billed & rate-limited:
function roleDoc() { return get(/databases/$(database)/documents/users/$(uid())).data; }
function isAdminByDoc() { return isSignedIn() && roleDoc().role == 'admin'; }
```

**Custom claims vs `get()`/`exists()`** — the most important rules-performance decision:

| | Custom claim (`request.auth.token.*`) | `get()` / `exists()` lookup |
|---|---|---|
| Cost | Free, in-token | **Counts as a document read** (billed); capped per request |
| Latency | None | Adds a read round-trip to every evaluated rule |
| Freshness | Stale until token refresh (≤1h, or force `getIdToken(true)`) | Always current |
| Best for | Coarse, slow-changing roles (admin, tenant, plan) | Fine-grained/relational checks (membership, ownership by another doc) |

Prefer custom claims for role gates. Reserve `get()`/`exists()` for relationships you can't encode in a token. Firestore caps `get`/`exists` calls per rule evaluation (10 for single-doc requests, 20 for multi-doc queries) — exceeding it denies the request. See [rbac-roles.md](./rbac-roles.md).

## Rules are NOT filters

Allowing reads on a subset of docs does **not** scope a `list` query. The query itself must constrain to what's allowed, or the whole query is rejected (it is not silently trimmed).

```
match /orders/{orderId} {
  allow read: if isOwner(resource.data.userId);
}
```
```js
// ❌ Rejected — rules can't evaluate resource.data across an unconstrained list
const snap = await getDocs(collection(db, 'orders'));
// ✅ The query must mirror the rule's constraint
const snap = await getDocs(query(collection(db, 'orders'), where('userId', '==', uid)));
```

When you write an ownership/tenant rule, the corresponding client query MUST carry the matching `where` clause. Fixing rules without fixing the queries breaks the app.

## Validate the data, not just the caller

Authorization is half the job. Validate `request.resource.data` on writes so clients can't corrupt shape, escalate fields, or mutate immutables.

```
function isValidPost() {
  let d = request.resource.data;
  return d.keys().hasAll(['authorId', 'title', 'createdAt'])
    && d.keys().hasOnly(['authorId', 'title', 'body', 'createdAt', 'updatedAt'])
    && d.authorId == uid()                        // can't forge another author
    && d.title is string && d.title.size() <= 200
    && d.createdAt == request.time;               // server-stamped
}

match /posts/{postId} {
  allow create: if isSignedIn() && isValidPost();
  allow update: if isOwner(resource.data.authorId)
    && request.resource.data.authorId == resource.data.authorId   // immutable owner
    && request.resource.data.createdAt == resource.data.createdAt; // immutable timestamp
}
```

- `hasOnly([...])` blocks clients from writing unexpected fields (e.g. `role`, `isAdmin`, `balance`).
- Compare `request.resource.data.X == resource.data.X` to freeze immutable fields on update.
- Never trust a client-sent role/permission/price field. Privileged fields belong to Admin SDK / Cloud Functions, or are gated so only privileged callers may set them.

## Multi-tenant isolation

Tenant-scoped data must be unreadable/unwritable across tenants. Encode the tenant on the caller (claim) and on the doc, and require they match.

```
function tenant() { return request.auth.token.tenantId; }
function inTenant(t) { return isSignedIn() && tenant() == t; }

match /events/{eventId} {
  allow read:  if inTenant(resource.data.tenantId);
  allow write: if inTenant(request.resource.data.tenantId) && isTenantAdmin();
}
```
Client queries must include `where('tenantId', '==', myTenantId)` (rules-aren't-filters again).

## Storage rules

Same discipline, plus validate content type and size to stop abuse.

```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /users/{userId}/avatar/{file} {
      allow read: if true;
      allow write: if request.auth != null
        && request.auth.uid == userId
        && request.resource.size < 5 * 1024 * 1024
        && request.resource.contentType.matches('image/.*');
    }
  }
}
```

## Common pitfalls to fix on sight

- `allow read, write: if true;` or `if request.auth != null;` as blanket write access — signed-in ≠ authorized.
- A dev-mode "expires on" open rule left in prod (`allow read, write: if request.time < timestamp.date(...)`).
- Reading roles with `get()` on every rule when a custom claim would do — silent read-cost blowup.
- Rules that authorize but don't validate — clients inject `isAdmin: true` or overwrite `balance`.
- `resource.data` used in `create` rules (there is no existing doc — use `request.resource.data`); `request.resource.data` used to gate `delete` (there is no incoming doc — use `resource.data`).
- Rules updated without updating the client queries to match — app breaks or leaks.

## Test before you deploy

Never eyeball rules into production. Use the emulator + rules unit tests.

```bash
firebase emulators:start --only firestore,storage,auth
```
```js
// @firebase/rules-unit-testing
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';

const env = await initializeTestEnvironment({ projectId: 'demo', firestore: { rules } });
const alice = env.authenticatedContext('alice', { role: 'user' });
await assertSucceeds(getDoc(doc(alice.firestore(), 'posts/p1')));
await assertFails(setDoc(doc(alice.firestore(), 'posts/p2'), { authorId: 'bob' })); // can't forge author
```

Cover both the allow AND the deny path for every rule you touch. A rule that passes the happy path but never tested the deny path is unverified.
