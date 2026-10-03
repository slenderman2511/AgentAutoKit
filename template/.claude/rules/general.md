# General project rules

Managed by AgentAutoKit. Project-specific rules belong in their own `.claude/rules/*.md` files.

## Code style

- TypeScript strict mode — no `any` unless justified (prefer `unknown`).
- Prefer `interface` over `type` (except unions/intersections).
- Early returns; avoid nested conditionals.
- No silent error swallowing — always give the user feedback.
- Use the project's path alias for internal imports.
- Prefer server components/code paths; add client-only code only when necessary.

## Git workflow — MANDATORY

The **integration branch** is the one named in `CLAUDE.md` (default `dev`). The integration branch
and `main` are protected.

- **Never push directly to a protected branch.** Always feature branch + PR.
- **Every feature/fix/chore PR bases the integration branch**, never `main`. Only the release flow
  promotes the integration branch to `main`.
- **Merging a PR requires explicit user approval every time** — ask first, wait for a clear "yes".
  Merge only after the review gate (`code-reviewer` + `security-auditor` when it applies + `tsc`
  green). `gh pr merge` is in the permission `ask` list; treat that prompt as the gate.
- **Never deploy from the CLI.** Deployments happen through CI/the hosting integration or a human.
- Flow: `git switch -c fix/description origin/dev` → commit → push → `gh pr create --base dev`.

### One feature / one task = ONE PR

A PR is the unit of review, delivery and rollback — so it maps 1:1 to a task (one issue, one plan).

- **Don't split one task into several PRs.** Review fixes, test additions, doc updates and
  "forgot one file" commits for an OPEN PR are pushed to the SAME branch — never a new PR.
- **Don't bundle unrelated tasks into one PR.** A second, unrelated fix found on the way = its own
  task/issue → its own PR later. No drive-by riders.
- **Before `gh pr create`, check for an open PR on the same task/issue** (`gh pr list --head <branch>`,
  `gh pr list --search "<issue#>"`). If one exists, push there and update its body instead.
- **Epics:** each slice may get a child PR, but child PRs base an **epic branch**
  (`epic/<slug>-<issue>`), and only ONE epic PR goes to the integration branch when the epic is
  deliverable — not one integration-branch PR per slice.
- **Exceptions:** after a PR MERGES, follow-up work is a NEW PR from a fresh branch (never stack on
  merged history); urgent production hotfixes may ship alone even mid-epic.

### Forbidden commands

```bash
git push origin dev          # no direct push to protected branches
git push origin main
git push --force             # never rewrite shared history
git merge dev                # no local merges into protected branches
gh pr merge <n> --base main  # never merge a main-based PR from the CLI
vercel deploy / vercel --prod / vercel promote   # no manual deploys
```

## Before submitting

1. `npx tsc --noEmit` passes.
2. The related tests pass (targeted `npx vitest run <file>`).
3. No hardcoded environment-, tenant- or customer-specific values — config-driven.
4. All UI states handled (loading, error, empty, success).
5. Every project-specific gate listed in `CLAUDE.md` is green.
