# Correction pass: inspect → fix → verify

Use this when asked to audit or fix a git workflow, or before a risky merge/rebase/push. Inspect first; never rewrite shared history; verify after.

## 1. Inspect (read-only, always allowed)

```bash
git status                          # branch, staged/unstaged, ahead/behind
git log --oneline --graph -20       # shape of recent history
git branch -vv                      # branches + their upstreams + ahead/behind
git worktree list                   # every worktree and its checked-out branch
git diff / git diff --staged        # what's about to be committed
git fetch origin                    # see the true remote state before deciding
```

## 2. Audit — red-flag checklist

**Sync / push / pull** ([sync-push-pull.md](./sync-push-pull.md))
- [ ] Branched off a **freshly fetched** base, not a stale local `main`.
- [ ] No bare `git push --force`; no force-push to `main` or a reviewed branch.
- [ ] Non-fast-forward rejections handled by fetch+rebase, not force.
- [ ] `-u` upstream set; push retries only on **network** errors (backoff), not on rejections.
- [ ] Push treated as human-gated (proposed, not assumed done).

**Branching / merging / rebasing** ([branching-merging.md](./branching-merging.md))
- [ ] One short-lived branch per unit of work; branches sync with base regularly.
- [ ] **No rebase/force-push of shared/pushed branches** (rebase only private, un-pushed work).
- [ ] Merge style (ff / `--no-ff` / squash) matches the content; merges into `main` from the root, not a worktree.
- [ ] Joint work uses an integration branch, not everyone racing `main`.

**Conflicts** ([conflict-resolution.md](./conflict-resolution.md))
- [ ] No conflict markers committed; both sides' intent preserved (no silent `--ours`/`--theirs` loss).
- [ ] Lockfiles/generated files regenerated, not hand-merged.
- [ ] Result re-built/re-tested (semantic conflicts caught); `rerere` on for repeated conflicts.

**Multi-agent worktrees** ([multi-agent-worktrees.md](./multi-agent-worktrees.md))
- [ ] One worktree + one branch per agent; no two agents on the same branch/dir.
- [ ] File ownership partitioned; agents don't rewrite each other's branches.
- [ ] Serial integration with rebuilds between merges.
- [ ] Worktree dirs / `node_modules` / `.env*` kept out of commits; clean removal (no `rm -rf`).

## 3. Fix — order of operations

1. **Data-loss risks first**: pending force-push to shared history, a rebase of shared commits, `reset --hard` with unsaved work. Stop and re-plan these.
2. **Divergence**: stale base, unsynced branch → fetch + rebase/merge.
3. **Conflict correctness**: re-resolve any hunk where logic was dropped; regenerate lockfiles.
4. **Hygiene**: upstreams, branch naming, committed noise, worktree cleanup.

Prefer non-destructive fixes. When a rewrite is unavoidable, confirm no one else holds the commits and use `--force-with-lease`.

## 4. Verify

- `git log --oneline --graph` — history is the shape you intended (linear where you rebased, grouped where you `--no-ff`'d).
- `git status` clean; no stray conflict markers (`git grep -nE '^(<<<<<<<|=======|>>>>>>>)'`).
- **Re-run lint / build / tests** after any merge/rebase — semantic conflicts don't show in `git status`.
- `git worktree list` matches reality; merged branches deleted.
- Confirm the remote is what you expect (`git fetch` + `git log origin/<branch>`) before declaring done — especially since push is human-gated and may not have run yet.
