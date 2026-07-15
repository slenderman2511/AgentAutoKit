# Resolving conflicts

A conflict means two changes touched the same lines and git can't pick — **you** must, by understanding both sides. A conflict-free merge is not automatically a correct one; verify after.

## Read the situation first

```bash
git status                 # lists "both modified" files — the conflicts
git diff                   # shows the conflict hunks
git log --merge -p <file>  # the commits from each side that touch this file
```

Conflict markers split the file into the two versions:

```
<<<<<<< HEAD (ours — the branch you're merging INTO / rebasing ONTO)
current side
=======
other side
>>>>>>> feat/x (theirs — the branch being merged IN / commit being replayed)
```

Note: during a **rebase**, "ours"/"theirs" are **reversed** vs a merge (rebase replays *their* commits onto *your* base), so read the branch labels, not the words.

## Resolve deliberately

For each hunk, decide what the code should *do* — usually you keep the intent of **both** sides, not one wholesale:

```bash
# Edit the file: remove the markers, combine the two intents into correct code.
git add <file>             # mark this conflict resolved
# merge:  git commit        (finish the merge)
# rebase: git rebase --continue
```

Shortcuts when one side is wholly correct:

```bash
git checkout --ours <file>    && git add <file>   # keep our version entirely
git checkout --theirs <file>  && git add <file>   # take their version entirely
```

Use `--ours`/`--theirs` only when a whole file should come from one side (e.g. a binary, or a file one branch deleted). For source code, hand-merge the logic.

Tools help on big conflicts: `git mergetool` (opens your configured 3-way tool), or your editor's merge UI.

## Lockfiles & generated files

Don't hand-merge `package-lock.json`, `yarn.lock`, build output, or snapshots — regenerate them:

```bash
git checkout --theirs package-lock.json   # or --ours; pick a base
npm install                                # regenerate from the merged package.json
git add package-lock.json
```

Resolve the **source of truth** (`package.json`) by hand, then regenerate its derivative. The same applies to any compiled/generated artifact.

## Repeated conflicts — enable rerere

If you rebase a long branch and keep re-resolving the *same* conflict, turn on **reuse recorded resolution** so git replays your fix automatically next time:

```bash
git config rerere.enabled true
```

## Bail out safely

If a merge/rebase is going sideways, abort and return to the pre-operation state — nothing is lost:

```bash
git merge --abort      # undo an in-progress merge
git rebase --abort     # undo an in-progress rebase, restore the original branch
git rebase --skip      # drop the current commit being replayed (only if it's truly redundant)
```

If you've already committed a bad merge but not pushed: `git reset --hard ORIG_HEAD` returns to just before it (destructive to the working tree — confirm nothing uncommitted is worth keeping).

## Verify — a clean merge is not a correct merge

Git resolving text does not mean the code is right. After every conflict resolution:

- Re-read the merged hunks — did you accidentally drop one side's logic or duplicate it?
- **Re-run lint / build / tests.** Semantic conflicts (both sides valid text, combined behavior broken — e.g. one side renamed a function the other still calls) only surface at build/test time.
- For a rebase, verify **each** replayed commit if the branch is long, not just the final state.

## Prevent conflicts in the first place

- Sync frequently (rebase/merge upstream often) so conflicts are tiny.
- Partition work so two agents/people rarely edit the same file (see [multi-agent-worktrees.md](./multi-agent-worktrees.md)).
- Keep commits and branches small and focused.

## Red flags to fix

- Conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) committed into a file.
- `--ours`/`--theirs` used on source code where both sides' logic was needed (silent loss of a change).
- Hand-edited lockfiles instead of regenerated.
- Resolved conflict never re-built/re-tested (semantic conflict shipped).
- `git checkout --theirs`/`--ours` confusion during a rebase (reversed meaning) dropping the wrong side.
