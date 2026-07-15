---
name: firebase-best-practices
description: Apply Firebase best practices when writing, reviewing, correcting, or hardening Firebase code and config — Firestore/Storage security rules, composite & single-field indexes (firestore.indexes.json), Firebase Auth, and role/permission (RBAC) design. Use when asked to "fix/optimize Firestore indexes", "audit/tighten security rules", "standardize roles", "set up custom claims", "make this Firebase project production-safe", or when reviewing any .rules / indexes.json / Auth / custom-claims code. For project-specific Firestore config editing/seeding/deploys, defer to firestore-config-edit.
user-invocable: false
---

# Firebase Best Practices

Reference discipline for **correcting and hardening** Firebase: security rules, RBAC/roles, Auth, and index optimization. Apply these rules when writing or reviewing any Firebase code — treat findings as things to *fix*, not just flag.

This skill is framework-level and reusable. It is NOT about one project's data model. If a repo already ships a project-specific config skill (e.g. `firestore-config-edit`), that skill owns *where config lives* and *how to deploy it in this repo*; this skill owns *what correct looks like*. When both apply, follow the project skill's deploy/safety workflow and this skill's correctness bar.

## Golden rules (never violate)

1. **Deny by default.** Every `match` starts from no access. Never ship `allow read, write: if true;` or a top-level `match /{document=**}` that grants access.
2. **Rules are the only server-side authorization for client SDK access.** Client code is untrusted; UI checks are UX, not security. If a path can be reached by the Web/mobile SDK, its rules must fully enforce authz + validation.
3. **Security rules are NOT filters.** A rule that allows reading a doc does not scope a query — the query must itself constrain to the allowed set, or it errors/leaks. Read [security-rules.md](./security-rules.md).
4. **Roles have exactly one source of truth.** Pick custom claims *or* a Firestore role doc per role dimension — never let the two disagree silently. Read [rbac-roles.md](./rbac-roles.md).
5. **Never expose Admin SDK / service-account credentials to a client.** Admin SDK bypasses all rules and runs server-side only. Read [auth.md](./auth.md).
6. **Never hand-invent composite indexes or delete `firestore.indexes.json` entries blind.** Indexes cost write latency + storage; missing ones fail queries at runtime. Optimize deliberately. Read [indexes.md](./indexes.md).
7. **Dev-first, never auto-deploy.** Test rules/index changes against an emulator or dev project, show the diff, and get explicit human confirmation before any production deploy.

## Reference files

Consult these based on what you're doing:

### Auditing or writing security rules
[security-rules.md](./security-rules.md) — deny-by-default structure, helper functions, `request.auth` checks, custom-claims vs `get()`/`exists()` lookups (and their read cost), data validation on `request.resource.data`, immutable/ownership fields, multi-tenant isolation, "rules aren't filters", Storage rules, and the emulator/rules-unit-test loop.

### Designing or standardizing roles & permissions
[rbac-roles.md](./rbac-roles.md) — the decision matrix for custom claims vs Firestore role docs, a canonical role schema, least-privilege hierarchies, tenant-scoped roles, setting claims with the Admin SDK, and the token-propagation gotcha (`getIdToken(true)`).

### Hardening Firebase Auth
[auth.md](./auth.md) — App Check, email-enumeration protection, MFA, password policy/reCAPTCHA, session & token lifetime, revoking sessions, and safe Admin SDK usage.

### Fixing or optimizing indexes & queries
[indexes.md](./indexes.md) — single-field (auto) vs composite (manual) indexes, when a composite index is required, single-field exemptions to cut write cost / dodge limits, collection-group indexes, query optimization (cursor pagination, `count()`, denormalization), the missing-index error→link→CLI flow, TTL policies, and the storage/write cost model.

### Running a full correction pass
[review-checklist.md](./review-checklist.md) — the audit → correct → verify protocol: which files to open, the red-flag list, and the dev-first deploy gate.

## Correction workflow (short form)

When asked to "make this Firebase project correct/optimized":

1. **Locate the artifacts**: `firestore.rules`, `storage.rules`, `firestore.indexes.json`, `firebase.json`, and Auth/custom-claims code (search for `setCustomUserClaims`, `request.auth.token`, `getIdToken`).
2. **Audit** against [review-checklist.md](./review-checklist.md) — record concrete findings with file:line.
3. **Fix** the highest-severity issues first: open-access rules > missing validation > role inconsistencies > missing/wasteful indexes.
4. **Verify** with the emulator (rules unit tests, index-backed queries) before proposing any deploy.
5. **Propose the deploy** as a diff + blast-radius summary; wait for explicit human confirmation. Never run `firebase deploy` unprompted.
