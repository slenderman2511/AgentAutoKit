# Multi-agent parallelism with worktrees

Running several agents on one repo at once is a concurrency problem. Git worktrees give each agent an isolated working directory over **one shared object store**, so parallel work doesn't collide on disk. The discipline below keeps it from colliding in history either.

> Repo-specific setup (this kit's `.claude/worktrees/` layout, per-worktree `npm ci` / `.env` copy / dev-server ports for the Next.js app) lives in the **`worktree-dev`** skill. This file is the framework-level coordination model — read both.

## How worktrees actually work

```bash
git worktree add ../wt-agent-a -b agent/a origin/main   # new dir + new branch
git worktree list                                        # see all worktrees & their branches
git worktree remove ../wt-agent-a                        # tidy up when done
```

- All worktrees of a repo **share one `.git` object database and refs.** A commit made in worktree A is immediately visible as an object to worktree B — no push/pull between them needed to *see* each other's commits (you still merge to combine them).
- **Git refuses to check out the same branch in two worktrees.** This is a feature: it enforces one-branch-per-worktree, so two agents can't both be committing to `agent/a`.
- Each worktree has its **own working tree, index, and HEAD** — agent A's uncommitted changes and staged files are invisible to agent B. Isolation is real.
- Working trees are **not** shared: `node_modules`, `.env*`, build caches must be set up per worktree (see `worktree-dev`).

## The isolation rules for N agents

1. **One worktree + one branch per agent.** Never point two agents at the same branch or the same directory.
2. **Partition file ownership up front.** The biggest lever on conflicts: give each agent a disjoint set of files/modules. Two agents editing the same file *will* conflict; two agents in different modules almost never do. Write the partition down (a task manifest) so agents stay in their lane.
3. **Branch every agent off the same fresh base** (`origin/main` or a shared integration branch) so their diffs are minimal against the integration point.
4. **Commit small and sync often.** Each agent rebases its branch on the base frequently (`git fetch && git rebase origin/<base>`), so integration is many tiny reconciliations, not one end-of-run conflict storm.

## Integration-branch pattern

For a feature several agents build together, don't have them all race `main`:

```bash
git switch -c integration/feat-x origin/main
git push -u origin integration/feat-x
# each agent:  git worktree add ../wt-<agent> -b agent/<agent> origin/integration/feat-x
# agents merge their branch back into integration/feat-x as pieces land
# integration/feat-x → main once, when the whole thing is green
```

Conflicts localize to the integration branch; `main` stays clean and each merge to it is a single reviewed step.

## Merge-order: serialize integration

Parallel *work*, serial *integration*. When multiple agent branches are ready:

- Merge them into the base **one at a time**, rebuilding/rebasing the next on the newly-updated base before its merge. This turns an N-way conflict into N small 2-way ones.
- Decide a merge order (e.g. the branch touching shared/foundational files first) so later branches rebase onto it rather than fighting it.
- After each merge, run lint/build/test before the next — catch semantic conflicts early (see [conflict-resolution.md](./conflict-resolution.md)).

## Commit & push hygiene across agents

- Each agent **owns and pushes only its own branch.** No agent force-pushes or rebases another agent's branch (that discards work — see the golden rule in [branching-merging.md](./branching-merging.md)).
- Push is human-gated in this kit — agents **propose** their push; a coordinator (or human) integrates. Never assume a sibling's branch is pushed; `git fetch` to see it.
- Keep `.claude/worktrees/` (or wherever worktrees live) out of commits — path-scoped `git add src/ tests/`, not `git add -A` from a worktree root.

## Cleanup (no `rm -rf`)

```bash
git worktree remove ../wt-agent-a     # refuses if dirty; kill dev servers/processes first
git worktree prune                    # drop stale administrative entries
git branch -d agent/a                 # after it's merged
git worktree list                     # confirm reality matches before reusing a name
```

- Stop any process holding the worktree (dev server, watcher) before removing — a running process dirties the tree and locks build dirs.
- Only fall back to `rm -rf` on a leftover directory git no longer tracks (`rm -rf` is denied by default — confirm first).

## Red flags to fix

- Two agents on the same branch or same directory (lost work, constant collisions).
- No file-ownership partition → agents editing the same files → conflict storm.
- Agents rebasing/force-pushing each other's branches.
- Everyone racing `main` instead of a shared integration branch for joint work.
- Integrating all agent branches at once instead of serially with rebuilds between.
- Worktree dirs or `node_modules`/`.env*` committed; worktrees removed while a dev server still holds them.
