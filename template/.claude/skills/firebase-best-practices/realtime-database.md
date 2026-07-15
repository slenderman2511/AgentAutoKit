# Realtime Database best practices

RTDB is a different product from Firestore with a **different rules language**, a **different index mechanism**, and a **different data-modeling discipline**. Don't apply Firestore patterns blindly.

## RTDB vs Firestore — choose deliberately

Prefer **Firestore** for most new apps (richer queries, better scaling, composite indexes). Reach for **RTDB** when you need very low-latency presence, high-frequency small updates, or simple sync (chat presence, live cursors, IoT streams). If a repo already commits to one, don't mix without reason.

## Security rules (RTDB dialect)

Rules are a JSON tree of `.read` / `.write` / `.validate` / `.indexOn` expressions keyed by path — **not** the Firestore `match`/`allow` language.

```json
{
  "rules": {
    ".read": false, ".write": false,
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid === $uid",
        ".write": "auth != null && auth.uid === $uid",
        "role": { ".write": "false" },
        ".validate": "newData.hasChildren(['displayName'])"
      }
    }
  }
}
```

Key differences from Firestore rules — get these right:

- **Rules cascade.** A `.read`/`.write` granted at a parent applies to **all** descendants and **cannot be revoked deeper**. Grant at the narrowest node; never put `".read": true` high in the tree.
- **Read/write are all-or-nothing per location** — RTDB rules do NOT filter. If a client reads `/messages`, the rule at `/messages` must allow reading the *whole* node. Structure data so clients only read subtrees they're entitled to.
- `newData` = the write being attempted, `data` = existing, `auth` = the token (`auth.token.role` for custom claims), `$var` = path captures, `root` = db root for cross-references.
- Use `.validate` for shape/type/immutability (`newData.isString()`, `newData.val() === data.val()` to freeze a field). `.validate` runs only when `.write` already allowed and does not cascade like read/write.
- **Deny by default** at the root (`".read": false, ".write": false`) and open specific paths.

## Data modeling — flatten, don't nest

- **Avoid deep nesting.** Fetching a node downloads the **entire subtree**. Keep the tree shallow and split data into separate top-level lists you can fetch independently.
- **Denormalize / fan-out.** No joins — duplicate data where it's read, and fan-out writes (multi-path update) to keep copies consistent atomically:
  ```js
  const updates = {};
  updates[`/posts/${id}`] = post;
  updates[`/user-posts/${uid}/${id}`] = post;
  await update(ref(db), updates);   // atomic multi-path
  ```
- Use **push IDs** (`push()`) for lists — chronological, collision-free, no hotspot.

## Indexing queries with `.indexOn`

RTDB has no automatic query indexes. Any `orderByChild('x')` used at scale needs an `.indexOn` at that node in the rules, or the server sorts client-side over the whole node (slow, and warns in logs).

```json
"messages": { ".indexOn": ["timestamp", "authorId"] }
```
Add `.indexOn` for every field you `orderByChild`/`equalTo` on. Missing it is a silent performance cliff, not an error.

## Performance & cost

- RTDB bills on **bandwidth + storage** and connection count — shallow reads and narrow paths save both.
- Use `limitToLast`/`limitToFirst` + `startAt`/`endAt` for pagination; never download an unbounded list.
- Detach listeners (`off()`) when done to avoid leaked bandwidth.
- Consider **sharding** across database instances for very high write throughput.
- For write contention on counters, use transactions (`runTransaction`) rather than read-then-set.

## Red flags to fix

- `".read": true` / `".write": true` high in the tree (cascades to everything below).
- Treating RTDB rules like a query filter (they read whole nodes).
- Deeply nested data forcing giant subtree downloads.
- `orderByChild` without a matching `.indexOn`.
- No root-level deny default.
- Client-writable `role`/privileged fields with no `.write": false` / `.validate` guard.
- Listeners never detached; unbounded list reads.
