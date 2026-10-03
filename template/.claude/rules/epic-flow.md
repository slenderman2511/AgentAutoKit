# Epic Flow — the layer above Task Sizing

Epic Flow wraps Task Sizing (S/M/L in `workflow.md`); it does NOT replace it. It answers one
question: *"in what order do we slice an epic?"* Task Sizing still decides *"how heavy is each
slice, and who does it"*.

**Goal #1: never build a big process for a small job.** Small work passes the gate and drops
straight into S/M/L — no prototype, no spec, no sweep.

## The gate (run it at the top of every task)

```
Task arrives
  │
  ├─ Is it an EPIC?  = several features/screens  +  data model OR UX not settled
  │
  ├─ NO ──→ Task Sizing S/M/L as usual. DONE.
  │         (button color · copy · one field · mirror one route · fix one known bug)
  │
  └─ YES ─→ Epic Flow, 4 steps ↓ ─→ each production slice falls back into S/M/L
```

**One-breath test:** *"Can I say, in one breath, what the data shape is and which screens change?"*
If yes and it is one task → **not an epic**, just do it.

> **The epic gate rounds DOWN, not up** — the opposite of Task Sizing. It is safe because the
> dangerous aspects (auth, payments, data isolation) are caught by `security-auditor` on its own
> path list, independent of tier. When unsure, start at **M** and escalate to Epic only when a
> second feature appears or the data is not settled.

## Epic Flow — 4 steps (only when the gate says YES)

1. **Lock the data** — schema + types. **Bake in immediately:** data scoping (tenant/user/org),
   payment contract, permission levels. (L tier: short spec → `spec-reviewer`. Output is a
   data-contract `.md`, not a UX description.)
2. **(OPT-IN) Thin UX prototype** — ONLY when the user asks for it, or the UX is genuinely
   unsettled. **Skipped by default**: use the data contract + `brainstorming` as the behavior spec.
   When on: happy path, throwaway, no scoping/error/i18n, **no TDD** (it will be thrown away). A
   self-contained HTML page (e.g. a Claude Artifact) linked from the feature's issue is enough.
3. **Slice production** — each slice = one child PR into the **epic branch** (one epic PR to the
   integration branch when deliverable — `general.md` § One feature / one task = ONE PR); each slice = one **S/M** task → `implementer` builds against the data
   contract (+ prototype if any). **TDD is back on here.**
4. **UI conformance + aspect sweep, once per epic** — run the `ui-design-conformance.md` loop
   (screenshots → `hallmark audit` vs prototype → `code-reviewer` triage → `implementer` applies
   ACCEPTs) on every screen of the epic; then UX polish · i18n · error/empty/loading states; then
   `security-auditor` ‖ `code-reviewer` **verify** that scoping and payments were baked in correctly.

## Aspects: defer to step 4 vs bake into step 1

| Defer to step 4 (fine to add later) | Must be in step 1 (lock the data) |
|---|---|
| error/loading/empty states | scoping field on every doc/row + query |
| i18n, copy | payment signature verification + webhook idempotency |
| logging, audit, analytics | permission boundaries (server-side role checks) |
| perf, cache, index | immutable fields |
| a11y polish | auth trust boundary |

**Golden rule:** if step 4 finds it must *add* a scoping filter, step 1 was wrong — go back and
fix the data, **don't patch it at the API**.

## Three sources of truth — separate lanes, never merged

- **Prototype** (if on) = truth for *behavior*. Off → behavior lives in the data contract + notes.
- **`docs/superpowers/plans/` checkboxes** = truth for *execution* (which step is done).
- **data-contract `.md`** = truth for *data* (shape + scoping + payments).

The one mistake: keeping a prose spec that *re-describes the UX* next to a prototype → two sources → drift.

## Overlapping systems — one role each

| System | Its ONLY role | When |
|---|---|---|
| **Task Sizing** | Router — decides **whether** a step happens (S/M/L) | Always, at the start of every task |
| **Superpowers** | Mechanics — **how** to do the step (`brainstorming` / `writing-plans` / `executing-plans` / TDD / verification) | When Task Sizing or Epic Flow says "do step X" |
| **Ponytail** | Brake — keeps diffs **small**, stops extra ceremony | Always |
| **Epic Flow** | Order — layers an epic (data → prototype → production → aspects) | Only when the gate says epic |
| **Workflow (ultracode)** | Scale — fan out many agents | Opt-in, when the user turns it on |

Read it top to bottom: *Task Sizing decides IF → Superpowers gives HOW → Ponytail keeps it SMALL →
Epic Flow sets the ORDER → Workflow only when you need SCALE.*

## Superpowers: respect each skill's trigger, don't fire the whole set

"If a skill applies, use it" means *don't SKIP a skill that applies* — not *fire every skill*. Each
skill has its own trigger, and a small UI task usually matches none of them:

- `brainstorming` = creative work / a NEW feature → a copy fix does not trigger it.
- `test-driven-development` = a feature or bugfix with logic → a button color change does not.
- `systematic-debugging` = there is a bug → an ordinary task does not.

Subagents carry `<SUBAGENT-STOP>`, so delegated work (step 3) stays lean automatically.
