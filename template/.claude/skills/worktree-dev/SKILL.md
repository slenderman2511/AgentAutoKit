---
name: worktree-dev
description: Set up a git worktree that can actually run the dev server and scripts — for any feature, fix or agent task that needs an isolated working copy (the worktree-first rule in .claude/rules/workflow.md), for running a second dev server, or when several Claude sessions share one checkout and collide. Also use when a dev server started inside a worktree returns HTTP 500 or a fallback page — that is almost always missing gitignored env files, not a code bug. Covers creating the worktree under .claude/worktrees/, copying env files, deps, ports, syncing with the integration branch, the PR hand-off, and cleanup. For general git discipline (rebase vs merge, conflicts), see git-workflow.
---
# Worktree-based development

Every code task runs in its own git worktree under `.claude/worktrees/`, one directory per
branch. The shared checkout is often on another session's branch; editing it tangles two tasks
and breaks each other's `tsc`/tests. A worktree is the isolation boundary that makes parallel
sessions safe.

## Create

From the repo root, branch off the LATEST integration branch named in `CLAUDE.md` (default `dev`):

```bash
git fetch origin dev --quiet
git worktree add -b fix/<name> .claude/worktrees/fix-<name> origin/dev
WT="$(pwd)/.claude/worktrees/fix-<name>"
```

- One branch per worktree; git refuses to check out a branch already checked out elsewhere.
- **Never create a worktree outside `.claude/worktrees/`** (e.g. `git worktree add ../app-copy`).
  Sibling worktrees look like a second full project, get forgotten, and end up orphaned.
- `.claude/worktrees/` must be gitignored (`init.sh` adds it). Never `git add` it; prefer
  path-scoped adds (`git add src/ tests/`) over `git add -A` from the worktree root.

## The one gotcha that wastes 20 minutes — env files

Env files are **gitignored** and live only in the main checkout, so a fresh worktree has none.
Without them, server-side SDKs have no credentials: the dev server returns HTTP 500 or silently
falls back to defaults. This is NOT a code bug — it is a missing-file problem.

```bash
MAIN="$(git rev-parse --show-toplevel)"      # run from the main checkout
for f in .env.local .env.development; do [ -f "$MAIN/$f" ] && cp "$MAIN/$f" "$WT/"; done
# .env.production ONLY when a script in this worktree must hit production — and treat every
# such run as production (dry-run first, confirm before writing).
```

- Copy only the files the dev server and your scripts need; list them in `CLAUDE.md` if the
  project has more than the usual ones.
- Keep paired variables identical: server code reads `X`, client code reads `NEXT_PUBLIC_X`;
  a mismatch between them causes silent misses.
- Env values copied from hosting dashboards can carry trailing newlines — scripts should
  `.trim()` every env var they read.

## Deps and ports

```bash
cd "$WT"
npm ci                     # worktrees never share node_modules; never symlink the root one
npm run dev -- -p 3002     # the main checkout's server usually holds 3000
```

- Check `package.json` scripts for other ports in use (e.g. an email-preview server on 3001).
- A `prebuild` step runs per worktree and needs no extra setup.

## Keep in sync

```bash
git fetch origin && git rebase origin/dev    # before the branch is pushed for review
```

After a rebase that touched `package-lock.json`, re-run `npm ci`. Once the branch is pushed for
review, merge `origin/dev` in instead of rebasing.

## Hand-off: PR, never a local merge

Verify inside the worktree (`npx tsc --noEmit` + the related tests, plus the project gates in
`CLAUDE.md`), run the review gate, then push the feature branch and open a PR that bases the
integration branch:

```bash
git push -u origin fix/<name>
gh pr create --base dev
```

Never merge into `dev`/`main` locally and never push to them — protected branches only move
through PRs the human merges.

## Clean up — after the PR merges

```bash
git worktree remove .claude/worktrees/fix-<name>
git branch -d fix/<name>
git worktree prune
```

- Do not remove a worktree before its PR merges — review feedback may need it.
- `worktree remove` refuses a dirty tree; use `--force` only after confirming nothing in it is
  worth keeping (`node_modules` and copied env files are noise, not work).
- `git worktree list` is the source of truth. A hand-deleted folder leaves a stub →
  `git worktree prune`. `locked` worktrees are skipped by prune by design.
- The link between a worktree and the repo is an absolute path: moving or renaming the folder
  breaks it until `git worktree repair`.

## Pitfalls checklist

- Env files copied in (the 500 / fallback-page symptom).
- Separate `node_modules` per worktree (`npm ci` in each).
- Explicit port for every extra dev server.
- `.claude/worktrees/` never committed.
- Stop the worktree's dev server before `git worktree remove` — a running `next dev` holds
  `.next/` locks and dirties the tree.
- Pick a distinct worktree name; `.claude/worktrees/` often holds other sessions' worktrees.
