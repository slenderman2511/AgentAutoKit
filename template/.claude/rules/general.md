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
