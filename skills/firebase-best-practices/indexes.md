# Indexes & query optimization (Firestore)

Every Firestore query must be backed by an index. Getting this right is the difference between fast, cheap queries and runtime failures or write-cost blowups.

## Two kinds of index

| | Single-field | Composite |
|---|---|---|
| Created | **Automatically** for every field (ascending, descending, and array-contains) | **Manually** — you declare them in `firestore.indexes.json` |
| Needed for | Single equality/range/order on one field | Any query combining multiple fields (multiple `where`, or `where` + `orderBy` on different fields) |
| Cost | Storage + write amplification per field | Additional storage + write latency per composite |

Firestore auto-creates single-field indexes, so simple queries "just work." Composite indexes must exist *before* the query runs or the query throws.

## When you need a composite index

You need one whenever a query can't be served by single-field indexes alone. Common triggers:

- Two or more equality filters on different fields, OR an equality + a range/inequality: `where('status','==','open').where('createdAt','>',t)`.
- Any filter combined with `orderBy` on a **different** field: `where('tenantId','==',x).orderBy('createdAt','desc')`.
- `array-contains` (or `array-contains-any`) combined with another filter or an order.
- `in` / `!=` / `not-in` combined with ordering on another field.
- Range/inequality filters on a field plus ordering — the ordering must start with that field.

Firestore's constraint: your **first `orderBy` must match the field of any range/inequality filter**. If you filter `>` on `price`, you must `orderBy('price')` first (then others).

## Let Firestore tell you the index — don't guess

When a query needs a missing composite index, the SDK throws a `FAILED_PRECONDITION` error containing a **direct console link that pre-fills the exact index**. This is the canonical way to author composites — do not hand-craft `firestore.indexes.json` from memory.

Workflow:
1. Run the query (emulator or dev) → capture the error.
2. Follow the link to create it, OR add the equivalent entry to `firestore.indexes.json`.
3. Deploy indexes: `firebase deploy --only firestore:indexes` (dev-first; never auto-deploy to prod).
4. Keep `firestore.indexes.json` in version control as the source of truth — it's what `deploy` reconciles against.

```json
{
  "indexes": [
    {
      "collectionGroup": "orders",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "tenantId", "order": "ASCENDING" },
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "createdAt", "order": "DESCENDING" }
      ]
    }
  ]
}
```

Field order in a composite matters: **equality fields first, then the range/order field last.** Reordering changes which queries it serves.

## Single-field exemptions — cut write cost & dodge limits

Auto-indexing every field is wasteful (and sometimes impossible) for:
- **Large arrays / maps** you never query on — each element gets indexed, inflating write cost and risking the per-document index-entry limit.
- **Long strings / big blobs** used for display only.
- **Monotonic values written at high frequency** (sequential timestamps/counters) that create index hotspots.

Add a **single-field index exemption** (in `firestore.indexes.json` `fieldOverrides`, or via console) to disable indexing on fields you never filter/order by. This reduces write latency and storage without affecting queries you don't run.

```json
{
  "fieldOverrides": [
    {
      "collectionGroup": "posts",
      "fieldPath": "rawHtmlBody",
      "indexes": []
    }
  ]
}
```

## Collection-group queries

To query a subcollection across all parents (`collectionGroup('comments')`), enable a **collection-group scoped index** (`"queryScope": "COLLECTION_GROUP"`). Without it the collection-group query fails. Watch the security-rules side too — collection-group reads need matching rules on the subcollection path.

## Query optimization beyond indexes

- **Paginate with cursors, not offset.** `startAfter(lastDoc)` reads only what you return; `offset(n)` is billed for all skipped docs. Never use large offsets.
- **Use aggregation queries** (`count()`, `sum()`, `average()`) instead of reading a whole collection to count/total it — vastly cheaper.
- **Denormalize for read patterns.** Firestore has no joins; duplicate the fields you filter/sort on onto the doc so one indexed query answers the read. Maintain duplicates via Cloud Functions/transactions.
- **Avoid `!=` / `not-in` / `array-contains-any` where possible** — they're limited, index-heavy, and often better modeled as a positive filter or a denormalized boolean.
- **Cap `in`/`array-contains-any` to their value limit** (30 values) and prefer narrower queries.
- **Watch hotspots:** monotonically increasing indexed fields (timestamps, sequential IDs) concentrate writes on one index range (~500 writes/sec soft limit per narrow range). Shard the key or drop the index if you don't query it.

## TTL policies

For ephemeral data (sessions, ephemeral events, expiring tokens), set a **TTL policy** on a timestamp field so Firestore auto-deletes expired docs instead of you paying to scan-and-delete. Combine with a single-field exemption if you never query that field.

## Cost model — why "just add an index" isn't free

- Each index entry is **extra storage** and **extra write work** — every write updates every index the document participates in. More indexes = higher write latency and cost.
- Composite indexes multiply with array fields (array-contains composites expand per element).
- So: add composites the queries actually need, and **exempt** fields you never query. Optimizing indexes is a two-way street — adding the missing ones *and* removing/exempting the wasteful ones.

## Red flags to fix

- A query wrapped in try/catch that swallows `FAILED_PRECONDITION` (missing index hidden instead of created).
- `firestore.indexes.json` not in version control, or drifted from the deployed indexes.
- Auto-indexed large arrays/blobs with no exemption → bloated writes.
- `offset()` pagination or reading whole collections to count.
- Monotonic timestamp/counter fields indexed and written at high volume (hotspot).
- Range filter on one field but `orderBy` starting on a different field (will error).
