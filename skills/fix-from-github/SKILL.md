---
name: fix-from-github
description: Drain the AI work queue — pick the next unclaimed open issue carrying the project's queue label (default `ai`, from CLAUDE.md "## Issue tracking"; bugs from add-bug-to-github ordered by severity, then features), claim it with an advisory lock comment, investigate, present a per-ticket PLAN GATE for approval, then execute automatically through the kit pipeline — worktree branch off the integration branch, implement, verify, review gate, DRAFT PR to the integration branch (never merge, never push the integration branch or main) — and move to the next ticket. Use when the user asks to "fix from github", "nhặt issue", "xử lý issue <N>", "work the ai queue", "drain the queue", "pick and fix the next bug", or wants queued tickets worked through. Not for producing tickets (add-bug-to-github / github-issue-flow Step 1), not for closing issues after a merge (github-issue-flow Step 4), and not for reviewing a local diff (/code-review).
---

# Drain the AI queue: claim → plan gate → fix → draft PR

This is the **consumer** of the `<ai>` work queue that `add-bug-to-github` produces. It picks
tickets one at a time, gets the plan approved, then runs the fix through the kit's own pipeline.
**Key difference from commit-to-main queue systems: the kit forbids direct pushes to protected
branches and CLI merges** — a ticket's terminal state here is a **draft PR to the integration
branch + updated issue**, not a closed issue. Closing happens via `github-issue-flow` Step 4 after
a human merges on GitHub.

Project facts: CLAUDE.md `## Issue tracking` (repo, queue label, label names) and `## Git
workflow` (integration branch, default `dev`) — see `github-issue-flow` "Project facts" for
defaults and the `<repo>` / `<ai>` / `<integration>` placeholders. Pass `--repo <repo>` on every
`gh` call.

## Setup (once per session)

1. Parse the user's arguments (all optional): a specific `#N` (fix just that one) ·
   `--severity <min>` · `--kind data|ui|logic|integration|perf` · `--scope <label>` ·
   `--max <n>` · `--once`.
2. `AGENT_ID` = a per-session identity string (e.g. `session-<random>`), used in claim comments
   so parallel sessions can tell each other apart — they usually post as the same GitHub user,
   so the id, not the login, is the owner.
3. `skip` = in-memory set of issue numbers released this session — never re-pick them.

## The loop

### 1. Read the queue

```bash
gh issue list --repo <repo> --state open --label <ai> --limit 100 --json number,title,labels,createdAt
```

Apply `--kind` / `--scope` as extra `--label bug:<kind>` / `--label <scope>` flags (repeated
`--label` = AND). Order: bugs by `severity:` (critical → high → medium → low → unlabeled), oldest
first within a band; features and everything else last. Drop numbers in `skip` and anything below
`--severity`. **Empty queue → stop** and report "queue drained".

### 2. Claim it (advisory lock)

Read the issue's claim/release trail:

```bash
gh api repos/<repo>/issues/<N>/comments --paginate \
  --jq '.[] | "\(.created_at) \(.body | split("\n")[0])"'
```

- A comment `🔒 CLAIM <agent-id> <ISO-time>` **younger than 90 min** with no later `🔓 RELEASE`
  → another session owns it; skip to the next ticket. A claim followed by a PR-link comment is
  **in-PR**, never stale — skip it too. (A bare claim older than 90 min = stale crash leftover —
  treat as free.)
- Free → `gh issue comment <N> --repo <repo> --body "🔒 CLAIM <AGENT_ID> <now ISO>"`, then
  **re-read**: if someone else's claim has an *earlier* `created_at`, you lost the race — post
  `🔓 RELEASE lost race`, skip, next ticket.

### 3. Investigate — nothing edited yet

Read the issue body: the machine footer (`<!-- queue:… kind:… severity:… scope:… ref:… -->`),
the Where/evidence, and the cited reference (the `## Source of truth` doc section or the spec in
`docs/superpowers/specs/`). Verify the claimed root cause against the actual code — tickets
record a *hypothesis*; the fix targets the *verified* cause (update the issue if they differ).
Size it S/M/L (`.claude/rules/workflow.md`) and route by difficulty per its model routing
(unknown root cause → `deep-debugger`, never guess with a cheap model). A `bug:data` ticket that
needs live data: ask before any read, per the project's data rules in `.claude/rules/`.

### 4. PLAN GATE — the human control point

Present for approval (AskUserQuestion or plan mode): verified root cause · exact change + files ·
tier · how it's verified (which tsc/test) · risk · whether a production data repair is involved.

- **Approved** → step 5, no further prompts *except* the non-negotiable gates below (and the
  permission prompts the kit's settings put on commit / push / PR creation).
- **Feedback** → revise, re-present.
- **Skip/reject** → post `🔓 RELEASE not fixing now: <reason>`, add to `skip`, next ticket.

An **L-tier** ticket's approval covers the approach only — the spec → `spec-reviewer` → plan pass
(`docs/superpowers/specs|plans/`) still runs before code. Too big for this session → release it
with "needs L-tier spec".

### 5. AUTO — execute through the project pipeline

Follow `github-issue-flow` Steps 2–3 exactly:

1. Fresh worktree + branch `fix/<slug>-<N>` off the latest `origin/<integration>` — one per
   ticket, never stacked on another ticket's branch. Surgical implementation (YAGNI); M tier
   writes its mini-plan in `docs/superpowers/plans/` first.
2. **Verify**: `npx tsc --noEmit` + targeted `npx vitest run <related test>` — changed logic ships
   with a test, ideally a regression test that failed before the fix; scripts get `node --check`
   + a read-only dry-run where applicable.
3. **Review gate**: `code-reviewer` ‖ `security-auditor` (when the diff touches a path CLAUDE.md
   lists as security-sensitive) + every project-specific gate. Apply findings, max 2 rounds.
4. Commit(s) end with `Refs #N`; push the branch; open a **draft PR to `<integration>`** with
   **`Closes #N`** in the body (it links the issue; native auto-close won't fire on a
   non-default base — `github-issue-flow` Step 4 closes it after the merge).
5. Update the issue: tick its checklist, comment with the PR link. **The claim stays** — the
   ticket is in-PR, not free. Keep the worktree; review feedback may need it.

**Never bypassed, even inside AUTO** (repo rules trump the drain loop):
- Production data writes (backfills/repairs) always stop for a dry-run + explicit user
  confirmation, per the project's data-safety rules — never folded silently into the code fix.
- No pushes to `<integration>`/`main`, no `gh pr merge`, no deploys.
- No edits to `.env*`, secrets, CI workflows or migrations (CLAUDE.md Rules) — a ticket that
  needs them is blocked (step 6) and goes to a human.

### 6. If blocked

Tests won't go green, the fix outgrows the approved plan, review findings survive 2 rounds, or a
dependency/credential is missing → post `🔓 RELEASE <what blocked it>`, add to `skip`, surface the
blocker to the user, next ticket. **Release, never close** — an unfixed ticket goes back to the
queue.

### 7. Loop

Report the iteration (draft PR #X opened for #N / released #N because …) and return to step 1.

## Stop conditions & backstops

Stop when: queue empty · `--max` reached · `--once` · user interrupts. Backstop: 3 consecutive
lost claims or 3 consecutive blocked tickets → something is systemically wrong; report and stop,
do not spin.

## Standing mode

To keep draining as new tickets arrive: `/loop 15m /fix-from-github [filters]`. Each pass exits
when the queue is empty; the loop re-checks on the interval.
