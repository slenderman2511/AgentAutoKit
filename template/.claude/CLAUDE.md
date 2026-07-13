# Project: <PROJECT_NAME>

Multi-agent workflow managed by AgentAutoKit.

## Commands
- Install: `npm ci`
- Test: `npx vitest run`
- Typecheck: `npx tsc --noEmit`
- Lint: `npm run lint`
- Build: `npm run build`

## Layout
- Source in `src/`, tests colocated as `*.test.ts`
- Deploys via Vercel (preview on PR, prod on main)

## Workflow
- Start coordinated work with `/init-kit <description>`.
- The orchestrator routes: code-scout → arch-advisor → implementer → (deep-debugger) → test-writer → code-reviewer ∥ security-auditor.
- Review "changes requested" loops back to implementer, max 2 rounds.

## Rules (non-negotiable — also enforced by hooks/permissions)
- Never run `git push`, `vercel deploy --prod`, or `rm -rf`. Humans own releases.
- Never read or write `.env*`, secrets, CI workflows, or migrations.
- Keep `tsc --noEmit` clean and `vitest run` green before finishing any task.
- New or changed logic ships with tests.
