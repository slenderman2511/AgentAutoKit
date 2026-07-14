---
name: worktree-dev
description: Use when developing a feature or agent task that needs an isolated working copy — e.g. running a second dev server, testing a risky change without disturbing the main checkout, or parallel agent work. Triggers on requests to "work in a worktree", "spin up an isolated branch checkout", or run two branches side by side. Covers creating a worktree under .claude/worktrees/, deps/env/port setup, syncing with main, merging back, and cleanup.
---
# Worktree-based development

Work happens in git worktrees under `.claude/worktrees/`, one directory per task. Observed naming: `agent-<id>` for agent-driven tasks, `feat-<kebab-name>` for features (e.g. `feat-pickopz-platform`). Everything below is standard git-worktree practice applied to a Next.js + npm project.

## Create

From the repo root (base branch `main`):

```bash
git fetch origin
git worktree add .claude/worktrees/feat-<name> -b feat/<name> origin/main
```

- One branch per worktree; git refuses to check out a branch already checked out elsewhere (including `main`, which the root checkout holds).
- **Check whether `.claude/worktrees/` is git-ignored** — if only `.worktrees/` is in `.gitignore`, never `git add .claude/worktrees/`, and prefer path-scoped adds (`git add src/ tests/`) over `git add -A` from the worktree root. Adding a `.claude/worktrees/` entry to `.gitignore` is a safe improvement.

## Set up deps, env, ports

Each worktree is a separate directory: it shares the repo's git history but **not** `node_modules` or env files.

```bash
cd .claude/worktrees/feat-<name>
npm ci                                    # own node_modules; never symlink the root one
cp ../../../.env* . 2>/dev/null           # .env* is git-ignored, so worktrees start without it
```

- `.env*` files (`.env.local`, `.env.production`, …) are ignored by git and will be missing in a fresh worktree. Copy whichever exist in the root checkout.
- `npm run dev` defaults to port 3000, which the root checkout's dev server likely holds. Check for other port users in package.json scripts (e.g. an email-preview server on 3001). Run the worktree's server on an explicit free port:

```bash
npm run dev -- -p 3002
```

- If the project has a `prebuild` step, it runs per-worktree and needs no extra setup, but expect its output to differ from the root checkout's if branches diverge.

## Keep in sync with main

Rebase the worktree branch regularly; after a rebase that touched `package-lock.json`, re-run `npm ci`:

```bash
git fetch origin
git rebase origin/main
```

Don't rebase after pushing the branch for review — merge `origin/main` in instead.

## Merge back

Run the checks the repo expects (`npm run lint`, `npm test`, and `npm run build` for anything nontrivial) inside the worktree, then either push and open a PR, or merge locally from the root checkout:

```bash
git -C <repo-root> merge --no-ff feat/<name>
```

Never merge from inside the worktree into `main` — `main` is checked out at the root, and git will refuse anyway.

## Clean up

```bash
git worktree remove .claude/worktrees/feat-<name>
git worktree prune
git branch -d feat/<name>    # after merge
```

- `worktree remove` refuses if the tree is dirty; use `--force` only after confirming nothing in it is worth keeping (remember `node_modules` and copied `.env*` count as untracked noise, not work).
- Stray directories can survive removal — after `prune`, `rm -rf` any leftover dirs that `git worktree list` doesn't know about, and check `git worktree list` matches reality before creating a new worktree with a previously used name.

## Pitfalls checklist

- Separate `node_modules` per worktree: run `npm ci` in each; a missing install fails with module-not-found, a shared one breaks native/dedupe assumptions.
- Separate `.env*` per worktree: git-ignored, so they never come along with the checkout.
- Port collisions: pass `-p <port>` explicitly for every extra dev server.
- Keep `.claude/worktrees/` out of commits.
- Kill the worktree's dev server before `git worktree remove`; a running `next dev` holds `.next/` locks and dirties the tree.
