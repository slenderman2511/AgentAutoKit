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

## Security-sensitive paths
_Any PR that touches these triggers `security-auditor`._
- `src/app/api/**` / `app/api/**` (API routes), webhooks, `middleware.ts`
- auth, sessions, permissions/roles, admin pages
- payments and billing
- security rules / access policies: <e.g. RLS policies, database security rules, storage rules>

## Project-specific gates
_Run before every PR, in addition to `npx tsc --noEmit`._
- <e.g. `npm run lint`, a custom check script — delete this line if none>

## Project rules
- <Invariants every agent must respect — data isolation, naming conventions, domain rules.
  Put longer ones in `.claude/rules/<topic>.md`; agents and reviewers read that folder.>

## Design system
_Read by `ui-verify` and `ui-prototype`._
- Tokens / theme classes: <e.g. `src/app/globals.css` CSS variables, `tailwind.config.ts`>
- Themes / variants a shared component must pass under: <e.g. light + dark, or each brand theme>
- Prohibitions: <e.g. no hardcoded colors, no raw palette classes — or point to `.claude/rules/ui-design.md`>

## Source of truth
_Read by `context-checkpoint`, `add-bug-to-github`, `github-issue-flow`._
- Feature reference doc: <e.g. `docs/PROJECT-SOURCE-OF-TRUTH.md` — delete this section if none>

## Issue tracking
_Read by `github-issue-flow`, `add-bug-to-github`, `fix-from-github`, `ui-prototype`._
- Repo: <owner/name — default: `gh repo view --json nameWithOwner`>
- AI work-queue label: `ai`
- Type labels: `bug`, `feature`, `chore` · bug kinds: `bug:data|ui|logic|integration|perf`
- Severity labels: `severity:critical|high|medium|low` · optional scope labels: <e.g. `area:<name>`>

## Skills & companion plugins
- Workflow skills (`.claude/skills/`): `worktree-dev`, `git-workflow`, `context-checkpoint`, `ui-prototype`, `ui-verify`, `github-issue-flow`, `add-bug-to-github`, `fix-from-github`, `conventions`.
- Best-practice skills: `frontend-design`, `hallmark`, `responsive-design`, `accessibility`, `seo`, `react-best-practices`, `composition-patterns`, `typescript-advanced-types`, `tailwind-css-patterns`, `nodejs-best-practices`, `nodejs-backend-patterns`, `playwright-best-practices`, `firebase-best-practices`, `payment-integration`, `stripe-best-practices`, `upgrade-stripe`, `i18n-best-practices`, `archify` (diagrams).
- Domain skills from the kit's reference project (tournament apps on Firebase): `roster-import`, `firestore-config-edit`, `e2e-flow` — delete them if they don't apply. Claude loads skills automatically when relevant.
- Next.js ships its own agent knowledge from 16.3 (`node_modules/next/dist/docs/` + the `AGENTS.md`/`CLAUDE.md` rules `next dev` generates); the kit no longer bundles `next-best-practices` (retired upstream, no license). Cache Components workflow skills: `npx skills add vercel/next.js`. Upgrades: `npx @next/codemod@latest upgrade`.
- Companion plugins are declared in `.claude/settings.json` (`enabledPlugins`): superpowers (process mechanics), ponytail (keeps diffs small), firebase, playground, playwright, github, code-review, context7, hookify, claude-mem. Claude Code offers them for install when you trust this folder.
- Hooks are the only real enforcement mechanism — this file reminds, a hook enforces. Anything that MUST happen belongs in a hook.

## Rules (non-negotiable — also enforced by hooks/permissions)
- Never push to `dev`/`main`, merge PRs, deploy, or `rm -rf`. Humans own releases.
- Never read or write `.env*`, secrets, CI workflows, or migrations.
- Done = green exit code: `tsc --noEmit` clean and the related tests green before finishing.
- New or changed logic ships with tests.
