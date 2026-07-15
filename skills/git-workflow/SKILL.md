---
name: git-workflow
description: Apply Git best practices when syncing, branching, merging, or resolving conflicts, and when running multiple agents in parallel with git worktrees. Use when asked to "push/pull/sync", "merge a branch", "rebase", "resolve a merge conflict", "set up worktrees for parallel agents", "run several agents without stepping on each other", or when reviewing/correcting any git workflow. For this repo's Next.js/npm worktree layout (.claude/worktrees/, deps/env/ports), defer to worktree-dev.
user-invocable: false
---

# Git Workflow

Reference discipline for **safe, low-conflict Git** — fetch/pull/push, branching, merge vs rebase, conflict resolution, and running many agents in parallel with worktrees. Apply these when writing, correcting, or reviewing any git workflow.

This skill is framework-level and reusable. It owns *what correct git looks like*. Two neighbors own repo specifics: **`worktree-dev`** owns THIS repo's worktree layout (`.claude/worktrees/`, per-worktree `npm ci` / `.env` / ports for the Next.js app) — defer there for setup mechanics; the kit's **guardrails** own what's allowed (see below). When they apply, follow them and this skill's correctness bar.

## Respect the kit's git guardrails

The kit's template `settings.json` deliberately gates write actions — assume this posture everywhere:

- **`git push` is denied by default** — it's a human-gated action. Propose the exact push command and let the human run/allow it; never assume push succeeded.
- **`git commit`, `gh pr create`, `gh pr merge` prompt (`ask`)** — expect a confirmation step; state what you're committing first.
- **`rm -rf` is denied** — clean up worktrees with `git worktree remove` / `prune`, not recursive delete (only fall back to `rm -rf` on a leftover dir git no longer tracks, with confirmation).
- Read-only git (`status`, `diff`, `log`) is always allowed — use it liberally to inspect before acting.

Never `git push --force` a shared/reviewed branch, never force-push `main`, never commit secrets or `node_modules`/`.env*`.

## Golden rules

1. **Inspect before you act.** `git status`, `git diff`, `git log --oneline --graph` before any merge/rebase/reset. Know what's staged, what's ahead/behind, and which branch you're on.
2. **Sync before you branch and before you push.** `git fetch` first; branch off the fresh base; pull/rebase before pushing so you're not racing a stale ref. Read [sync-push-pull.md](./sync-push-pull.md).
3. **One branch per unit of work; keep it short-lived.** Long-lived divergent branches are conflict factories. Small, frequently-integrated branches barely conflict. Read [branching-merging.md](./branching-merging.md).
4. **Rebase your own un-pushed work; merge shared history.** Never rebase/force-push commits others (or another agent) may have based work on. Read [branching-merging.md](./branching-merging.md).
5. **Resolve conflicts deliberately, verify after.** Understand both sides, keep the intended behavior of each, then re-run build/tests — a clean merge is not a correct merge. Read [conflict-resolution.md](./conflict-resolution.md).
6. **Parallel agents = isolated worktrees, partitioned work.** One worktree + one branch per agent, non-overlapping file ownership, frequent integration. Read [multi-agent-worktrees.md](./multi-agent-worktrees.md).
7. **`--force-with-lease`, never bare `--force`.** When you must overwrite your own remote branch, use the lease so you don't clobber an unseen push.

## Reference files

### Fetch / pull / push & staying in sync
[sync-push-pull.md](./sync-push-pull.md) — fetch vs pull, tracking branches & `-u`, pull-with-rebase to keep history linear, push discipline and the retry-with-backoff pattern for flaky networks, `--force-with-lease`, and recovering from "rejected — non-fast-forward".

### Branching, merging & rebasing
[branching-merging.md](./branching-merging.md) — branch strategy, fast-forward vs `--no-ff` vs squash merges and when to use each, rebase vs merge (the golden rule of not rebasing shared history), integration branches, and keeping a feature branch current.

### Resolving conflicts
[conflict-resolution.md](./conflict-resolution.md) — reading conflict markers, `ours`/`theirs`, resolving by hand vs with tools, `rerere` for repeated conflicts, lockfile/generated-file conflicts, aborting safely (`merge --abort`, `rebase --abort`), and verifying the result.

### Multi-agent parallelism with worktrees
[multi-agent-worktrees.md](./multi-agent-worktrees.md) — how worktrees share one object store, one-branch-per-worktree isolation, partitioning work to minimize conflicts, the integration-branch pattern, commit/sync cadence for many agents, merge-order serialization, and cleanup. Defers repo-specific setup to `worktree-dev`.

### Auditing / correcting a git workflow
[review-checklist.md](./review-checklist.md) — the red-flag list and the inspect → fix → verify protocol.

## Quick workflow (short form)

1. **Sync**: `git fetch origin && git switch -c feat/<name> origin/main` (branch off fresh base).
2. **Work**: small commits; `git fetch && git rebase origin/main` regularly to stay current.
3. **Resolve** any conflicts deliberately; re-run lint/build/test.
4. **Integrate**: open a PR (human-gated), or merge `--no-ff` from the root checkout.
5. **Push**: propose the `git push -u origin <branch>` command (push is human-gated); retry with backoff only on network errors.
6. **Clean up**: `git worktree remove` + `prune`, delete the merged branch.
