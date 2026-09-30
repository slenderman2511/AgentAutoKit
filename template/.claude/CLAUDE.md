# Project: <PROJECT_NAME>

Multi-agent workflow managed by AgentAutoKit. **The playbook — task sizing (S/M/L), worktree-first,
model routing and the mandatory review gate — lives in `.claude/rules/workflow.md`** and is loaded
automatically. Keep THIS file for facts about this project; edit every `<...>` placeholder.

## Commands
- Install: `npm ci`
- Test (targeted): `npx vitest run <file>` · full suite: `npx vitest run` (CI)
- Typecheck: `npx tsc --noEmit`
- Lint: `npm run lint`
- Build: `npm run build`

## Layout
- Source in `src/`, tests colocated as `*.test.ts`
- Specs in `docs/superpowers/specs/`, plans in `docs/superpowers/plans/`
- Worktrees in `.claude/worktrees/` (gitignored)

## Git workflow
- Integration branch: `dev` — every PR bases it; only the release flow promotes `dev` → `main`.
- Deploys: <how this project deploys, e.g. Vercel preview on PR, prod on main>.
- Details and forbidden commands: `.claude/rules/general.md`.

## Security-sensitive paths (trigger `security-auditor` on any PR that touches them)
- `src/app/api/**` / `app/api/**` (API routes), webhooks, `middleware.ts`
- auth, sessions, permissions/roles, admin pages
- payments and billing
- security rules / access policies: <e.g. RLS policies, database security rules, storage rules>

## Project-specific gates (run before every PR, in addition to `npx tsc --noEmit`)
- <e.g. `npm run lint`, a custom check script — delete this line if none>

## Project rules
- <Invariants every agent must respect — data isolation, naming conventions, domain rules.
  Put longer ones in `.claude/rules/<topic>.md`; agents and reviewers read that folder.>

## Skills & companion plugins
- Bundled skills (`.claude/skills/`): `frontend-design`, `responsive-design`, `accessibility`, `next-best-practices`, `playwright-best-practices`, `e2e-flow`, `worktree-dev`, `git-workflow`, `firebase-best-practices`, `firestore-config-edit`, `payment-integration`, `i18n-best-practices`, `roster-import`, `conventions`. Claude loads them automatically when relevant; delete the domain ones that don't apply.
- Companion plugins are declared in `.claude/settings.json` (`enabledPlugins`): superpowers (process mechanics), ponytail (keeps diffs small), firebase, playground, playwright, github, code-review, context7, hookify, claude-mem. Claude Code offers them for install when you trust this folder.
- Hooks are the only real enforcement mechanism — this file reminds, a hook enforces. Anything that MUST happen belongs in a hook.

## Rules (non-negotiable — also enforced by hooks/permissions)
- Never push to `dev`/`main`, merge PRs, deploy, or `rm -rf`. Humans own releases.
- Never read or write `.env*`, secrets, CI workflows, or migrations.
- Done = green exit code: `tsc --noEmit` clean and the related tests green before finishing.
- New or changed logic ships with tests.
