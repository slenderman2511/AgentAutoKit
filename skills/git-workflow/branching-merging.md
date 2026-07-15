# Branching, merging & rebasing

The shape of your history is a choice. Pick it deliberately; the defaults below minimize conflicts and keep history readable.

## Branch strategy

- **One branch per unit of work** (feature, fix, agent task). Name it consistently: `feat/<kebab>`, `fix/<kebab>`, `agent/<id>`.
- **Branch off the fresh base**, not a stale local `main`:
  ```bash
  git fetch origin && git switch -c feat/<name> origin/main
  ```
- **Keep branches short-lived.** The longer a branch lives away from `main`, the more the two diverge and the worse the eventual conflict. Integrate small and often.
- Keep `main` (and any shared integration branch) always-releasable — never commit directly to it in this kit; go through a branch + PR.

## Merge styles — pick per situation

| Style | Command | Result | Use when |
|---|---|---|---|
| **Fast-forward** | `git merge feat` (no divergence) | Branch pointer moves up; no merge commit | Linear history, base hasn't moved |
| **No-ff (merge commit)** | `git merge --no-ff feat` | Explicit merge commit preserving the branch | You want the branch grouped/visible in history |
| **Squash** | `git merge --squash feat` then commit | One commit, branch detail collapsed | Many WIP commits you want flattened into one logical change |

- This repo's worktree-merge convention is `git -C <repo-root> merge --no-ff feat/<name>` — preserves the branch as a unit. Follow it where it applies.
- Squash for noisy WIP history; `--no-ff` when the individual commits are meaningful and you want them grouped.
- **Merge into `main` from the root checkout, never from inside a worktree** — `main` is checked out at the root and git refuses a second checkout anyway.

## Rebase vs merge — the golden rule

**Rebase your own un-pushed work to stay linear; merge to integrate shared history. Never rebase commits anyone else may have based work on.**

```bash
# Keep a feature branch current (your branch, not yet shared / only you own it):
git fetch origin
git rebase origin/main            # replay your commits on top of latest main → linear

# Once the branch is pushed for review / another agent branched off it: don't rebase it.
git fetch origin
git merge origin/main             # bring main's changes in via a merge commit instead
```

Why: rebase **rewrites commit hashes**. If someone else (or a sibling agent) has those commits, rewriting them forces a divergence that can only be fixed by a destructive force-push — which discards their work. So:

- **Private/un-pushed branch** → `rebase` freely to keep it linear and current.
- **Pushed/shared branch** → `merge` upstream in; if you must rewrite, only `--force-with-lease` and only if you're certain no one else has it.

## Integration-branch pattern (for parallel work)

When several branches/agents must converge, use a shared **integration branch** rather than everyone racing `main`:

```bash
git switch -c integration/feature-x origin/main
# each agent branches off integration/feature-x, merges back into it frequently
# integration/feature-x merges to main once, when the whole feature is green
```

This localizes conflicts to the integration branch and keeps `main` clean. See [multi-agent-worktrees.md](./multi-agent-worktrees.md).

## Keeping a feature branch current

Rebase (or merge) upstream in **regularly** — daily, or before every push — so integration is a series of tiny reconciliations instead of one giant conflict at the end. After a rebase that touched a lockfile or generated file, regenerate it (e.g. `npm ci`) rather than resolving it by hand.

## Red flags to fix

- Rebasing/force-pushing a branch others have pulled or branched from.
- Long-lived branches that never sync with `main` (conflict time-bomb).
- Committing straight to `main`/a shared branch instead of via a branch + PR.
- Merging into `main` from inside a worktree.
- Squashing away commits that carried meaningful, separately-reviewable history (or `--no-ff`-preserving pure WIP noise) — match the style to the content.
