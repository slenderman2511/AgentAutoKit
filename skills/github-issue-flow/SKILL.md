---
name: github-issue-flow
description: Turn any change request (fix, update, new feature) into a tracked GitHub issue BEFORE any code, then drive it through the kit's pipeline — classify it (feature / bug / chore + optional scope), size it (S/M/L), open a well-labeled issue, link the worktree branch and draft PR to it, and close it after a human merges. Use whenever the user asks to fix a bug, change behavior, or add a feature and the work should be tracked ("open an issue for this", "track this change", "make it a ticket and do it"). Encodes the label taxonomy, the "a PR basing a non-default integration branch never auto-closes its issue" gotcha, and the hand-off of merge and deploy to the human. Not for filing a known bug without fixing it (add-bug-to-github), not for draining queued AI issues (fix-from-github), and not for reviewing a local diff (/code-review).
---

# Issue-driven change flow (classify → issue → PR → close)

Every update/fix/feature request becomes a **tracked GitHub issue first**, then follows the kit
playbook (`.claude/rules/workflow.md`: task sizing S/M/L → worktree → implement → review gate →
PR to the integration branch). The issue is closed once its PR merges; merge and deploy stay human.

This skill does NOT replace the playbook — it sits on top and wires it to GitHub issues. It owns
the issue conventions that `add-bug-to-github` (queue producer) and `fix-from-github` (queue
consumer) reuse.

## Project facts — read `CLAUDE.md` first

- **`## Issue tracking`** — repo `owner/name` (default: `gh repo view --json nameWithOwner -q .nameWithOwner`),
  AI work-queue label (default `ai`), type labels (`bug`, `feature`, `chore`), bug-kind labels
  (`bug:data|ui|logic|integration|perf`), severity labels (`severity:critical|high|medium|low`),
  optional scope labels, and the attribution footer rule (if any — end issue/PR bodies with it).
- **`## Git workflow`** — the integration branch (default `dev`) and how deploys happen.
- **`## Source of truth`** (optional) — the feature reference doc that features must cite.
- **Security-sensitive paths** — decide whether `security-auditor` joins the review gate.

Below, `<repo>`, `<integration>` and `<ai>` stand for those values. Pass `--repo <repo>` to every
`gh` call (forks and worktrees can otherwise resolve to the wrong repo) and substitute the values
literally — shell variables do not survive between Bash calls.

---

## Step 0 — Classify the request

1. **Type** (exactly one — mutually exclusive):
   | Type | Label | Definition |
   |---|---|---|
   | Feature | `feature` | New capability or enhancement to existing behavior. **MUST cite its reference**: the section of the `## Source of truth` doc when the project has one, else the spec in `docs/superpowers/specs/`. If nothing fits, the feature is under-specified → clarify with the user first. |
   | Bug | `bug` | Shipped behavior is wrong/broken. Include repro + expected vs actual. |
   | Chore | `chore` | Maintenance / refactor / docs / tooling with **no user-facing behavior change**. |

2. **Scope** — only if `## Issue tracking` defines scope labels (per app, package, area, tenant,
   customer…). Add every label that applies; if the project pairs an umbrella label with
   namespaced ones (`area` + `area:<name>`), add BOTH. Cross-scope → every affected label.
   Project-wide changes get no scope label. Scope is the routing key: it says where the change
   must be verified and deployed.

3. **Tier** — task sizing S / M / L (`.claude/rules/workflow.md`, Q1/Q2). Record it in the issue
   as a checklist so a new session can resume. Ambiguous tier rounds **up**.

> **Ensure labels exist.** `gh issue create` rejects the whole call if any label is missing.
> Bootstrap the taxonomy once — idempotent, `--force` updates labels that already exist. Use the
> names from `## Issue tracking` where they differ; add new scope labels the same way.
> ```bash
> while read -r name color; do
>   gh label create "$name" --repo <repo> --color "$color" --force
> done <<'EOF'
> feature 0e8a16
> bug d73a4a
> chore cfd3d7
> ai 7057ff
> bug:data f9d0c4
> bug:ui f9d0c4
> bug:logic f9d0c4
> bug:integration f9d0c4
> bug:perf f9d0c4
> severity:critical b60205
> severity:high d93f0b
> severity:medium fbca04
> severity:low c2e0c6
> EOF
> ```

---

## Step 1 — Open the issue BEFORE writing code

Never start implementing before the issue exists — it is the unit of tracking.

**Title:** `<type>: <concise imperative summary>` (e.g. `bug: checkout drops the coupon on retry`).

**Labels:** the type label + any scope labels. (`<ai>` is only for tickets that should wait in the
queue for later pickup — that is `add-bug-to-github`'s job.)

```bash
gh issue create --repo <repo> --title "<type>: <summary>" --label <type>[,<scope>…] --body-file - <<'EOF'
<body from the template below>
EOF
```

**Body template:**

```md
## Context
<what prompted this — user report, request, observed behavior>

## Type & scope
- Type: feature | bug | chore
- Reference: <Source-of-truth section | spec path>   (features: required)
- Scope: <scope label(s)> or "project-wide"

## Problem / goal
<bug: repro steps + expected vs actual | feature/chore: the goal>

## Task sizing
- Tier: S | M | L   (.claude/rules/workflow.md)
- Touches a Q2 surface (schema/migrations, payments/webhooks, auth/permissions, security rules, a .claude/rules/ invariant)? yes/no

## Plan (checklist — resume from first unticked)
- [ ] Analyze / confirm root cause
- [ ] M: mini-plan in docs/superpowers/plans/ · L: spec → spec-reviewer → plan (link it)
- [ ] Implement (worktree branch referencing #N)
- [ ] tsc + targeted tests green
- [ ] Review gate (code-reviewer; security-auditor if a security-sensitive path)
- [ ] Draft PR to <integration>
- [ ] Merged by a human → issue closed
- [ ] Deployed per the project's own process (human)

## Acceptance criteria
<the observable success condition — the test/typecheck that proves it done>
```

`gh` prints the new issue URL — its last path segment is `#N`; every later step references it.

### Step 1b — Attach the UX prototype (when one exists)

If the feature went through the opt-in prototype step (`.claude/rules/epic-flow.md` step 2), the
prototype IS the behavior spec — link it so implementation maps against a bookmarkable artifact,
not prose.

- Add a `## Prototype` section to the issue (`gh issue edit` / `gh issue comment`) with BOTH
  links: the **interactive render** (e.g. the published Artifact, or
  `https://gistpreview.github.io/?<GIST_ID>`) and the **source / download** (e.g. the gist).
- **The link IS the attachment.** Do NOT commit the throwaway prototype and do NOT paste its HTML
  into the issue. Note its visibility (a secret gist = anyone-with-the-link); tell the user if the
  team needs wider access.
- **State the UX decisions locked/changed** vs the original ask, and add the line **"production
  build maps 100% to this prototype (+ responsive/theming/rules)"** so the implementer treats it
  as the spec. Keep the technical spec to data/API only — never re-describe the UX in prose
  (epic-flow: separate sources of truth, or they drift).
- Prototype changes → update this section **in the same turn**.

---

## Step 2 — Analyze & implement (the playbook, unchanged)

- **Working discipline**: state assumptions, ask when ambiguous, YAGNI, surgical changes.
- **Model routing**: `code-scout` to locate, `implementer` for known-cause S/M, `deep-debugger`
  for unknown root cause. Route by difficulty, not size.
- **Worktree-first**, branch named for the issue (or `feat/…` / `chore/…`):
  `git fetch origin <integration> --quiet && git worktree add -b fix/<slug>-<N> .claude/worktrees/fix-<slug>-<N> origin/<integration>`
- M/L plans in `docs/superpowers/plans/` carry an `**Issue:** #N` line; link plan/spec from the issue.
- **Commits** reference the issue: end the subject/body with `Refs #N`.
- Tick the issue's checklist as each step is **verified** (test/typecheck actually run), so the
  issue doubles as the durable resume state: `gh issue view <N> --repo <repo> --json body -q .body`
  into a scratch file → edit → `gh issue edit <N> --repo <repo> --body-file <file>`.

---

## Step 3 — Review gate, draft PR, merge (human)

- **Mandatory review gate** before the PR (workflow.md Orchestrator rule 5): `code-reviewer` ‖
  `security-auditor` (if the diff touches a path CLAUDE.md lists as security-sensitive), in
  parallel; `npx tsc --noEmit` green; every project-specific gate in CLAUDE.md green. S-tier
  docs/UI-copy-only diff → `tsc` green suffices. Findings → `implementer`, max 2 rounds.
- Open a **draft** PR **against `<integration>`** — never `main`:
  `gh pr create --repo <repo> --draft --base <integration> --title "<type>: <summary> (#N)" --body-file -`
- **Link the issue in the PR body with `Closes #N`.** ⚠️ **Gotcha:** GitHub's native auto-close
  on `Closes/Fixes/Resolves #N` only fires when the PR merges into the repo's **default** branch.
  PRs basing a non-default integration branch (e.g. `dev`) link the issue but **never close it**
  on merge — Step 4 does. Keep `Closes #N` anyway (it links the issue and states intent); use
  `Refs #N` only to link without claiming to resolve it. Check once:
  `gh repo view <repo> --json defaultBranchRef -q .defaultBranchRef.name` — if it equals
  `<integration>`, native auto-close works and Step 4 is just a verification.
- **Merging is the human's call** — ask and wait for an explicit "yes" every time
  (`.claude/rules/general.md`). Never merge on your own.

---

## Step 4 — Close the issue after the merge

Only ever close **after** the PR is actually merged — never pre-close:

```bash
gh pr view <PR> --repo <repo> --json state,mergedAt,baseRefName   # must be MERGED
gh issue view <N> --repo <repo> --json state -q .state            # still OPEN? then:
gh issue close <N> --repo <repo> --reason completed \
  --comment "Merged to <integration> in #<PR>. Deploy follows the project's release process."
```

If `## Issue tracking` says the repo runs a close-on-merge workflow (one that parses
`Closes/Fixes/Resolves #N` on integration-branch merges and closes the issue), it does this for
you — the commands above become the fallback for when it didn't fire (e.g. the PR used `Refs #N`).

Then remove the worktree: `git worktree remove .claude/worktrees/<slug>` + `git branch -d <branch>`.

---

## Step 5 — Hand off

Hand the merged PR to the human; deploys follow the project's own process (CLAUDE.md
`## Git workflow` → Deploys). Never deploy from the CLI. If the user later reports where it went
live, add that to the issue's closing comment thread.

---

## Quick reference

| Action | How |
|---|---|
| Repo, labels, integration branch | CLAUDE.md `## Issue tracking` / `## Git workflow` |
| Create / edit / comment / close an issue | `gh issue create\|edit\|comment\|close --repo <repo>` |
| Create/update a label | `gh label create <name> --color <hex> --force` |
| Tier / process weight | `.claude/rules/workflow.md` task sizing S/M/L |
| Who implements | `.claude/rules/workflow.md` model routing (route by difficulty) |
| Review gate | Orchestrator rule 5 (code-reviewer ‖ security-auditor + tsc + project gates) |
| Merge / deploy | Human only |

**Invariants:** (1) issue exists before code; (2) feature issues cite their reference (SoT
section or spec); (3) every branch/commit/PR references `#N`; (4) a PR basing a non-default
integration branch never auto-closes its issue — verify and close it manually after the merge;
(5) merge and deploy are never done by the agent.
