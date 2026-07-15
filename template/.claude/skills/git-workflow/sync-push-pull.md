# Fetch / pull / push & staying in sync

Most "git went wrong" moments are a stale local ref meeting a moved remote. Sync deliberately.

## Fetch first, always

`git fetch` updates your remote-tracking refs (`origin/main`) **without** touching your working tree — it's the safe way to see what moved before you act.

```bash
git fetch origin                 # update origin/* refs, no working-tree change
git log --oneline origin/main    # inspect what's new upstream
git status                       # "ahead N / behind M" tells you the divergence
```

Prefer fetching the specific branch you care about: `git fetch origin main`.

## Pull = fetch + integrate — choose how it integrates

`git pull` fetches then merges (default) or rebases. For a clean, linear history prefer rebase:

```bash
git pull --rebase origin main        # replay your local commits on top of upstream
# make it the default for this repo:
git config pull.rebase true
git config pull.ff only              # or: refuse to auto-merge, forcing an explicit choice
```

- **`--rebase`**: your un-pushed local commits move on top of the new upstream — linear history, no merge bubble. Best for a branch only you (or one agent) own.
- **default merge**: creates a merge commit; fine for integrating shared branches you shouldn't rewrite.
- If a pull conflicts, resolve it (see [conflict-resolution.md](./conflict-resolution.md)) then `git rebase --continue` / commit the merge.

## Tracking branches & the first push

Set upstream once with `-u` so later `git push`/`git pull` need no arguments:

```bash
git push -u origin feat/<name>       # push AND set origin/feat/<name> as upstream
```

Create a branch already tracking its base: `git switch -c feat/<name> origin/main`.

## Push discipline

Push is a human-gated action in this kit (denied by default) — **propose** the command, don't assume it ran. The canonical form:

```bash
git push -u origin <branch>
```

**Retry only on network errors, with exponential backoff** (don't retry on a rejected/non-fast-forward — that needs a sync, below):

```bash
for i in 1 2 3 4; do
  git push -u origin <branch> && break
  echo "network retry $i"; sleep $((2**i))   # 2s, 4s, 8s, 16s
done
```

## "rejected — non-fast-forward" (someone else pushed)

The remote moved since you last fetched. **Do not** `--force` blindly. Sync first:

```bash
git fetch origin
git rebase origin/<branch>       # replay your commits on top of the remote's
# resolve any conflicts, then:
git push -u origin <branch>
```

Use `git pull --rebase` for the same effect in one step. Force-pushing here would discard the other person's/agent's commits.

## When you must overwrite your own remote branch

After an intentional rebase/amend of a branch **only you own**, the remote history differs and a normal push is rejected. Use the lease, never a bare force:

```bash
git push --force-with-lease origin feat/<name>
```

`--force-with-lease` refuses if the remote advanced beyond what you last fetched (i.e. someone else pushed) — it protects against clobbering an unseen commit. **Never** `--force`/`--force-with-lease` a shared, reviewed, or `main` branch.

## If the PR for your branch was already merged

A merged PR is finished — don't stack new commits on it. Restart the branch from the fresh default and push follow-up work as a new PR:

```bash
git fetch origin main
git switch -C <branch> origin/main    # rebuild from latest default (keeps the branch name)
# ... new work ...
git push -u origin <branch>           # force-with-lease is fine if it only held merged history
```

If the branch still carries **unmerged** commits beyond the merged history, keep them — rebase them onto the new base instead of discarding.

## Red flags to fix

- `git push --force` (bare) anywhere, or any force-push to `main`/a reviewed branch.
- Retrying a rejected non-fast-forward push instead of fetch+rebase.
- `git pull` with unresolved local changes and no plan for the merge bubble it creates.
- Working from a stale base (no `fetch` before branching/pushing).
- Assuming a push succeeded without seeing it complete (push is human-gated here).
