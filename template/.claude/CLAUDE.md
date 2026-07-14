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

## Skills & companion plugins
- Bundled skills (`.claude/skills/`): `frontend-design`, `next-best-practices`, `playwright-best-practices`, `e2e-flow`, `worktree-dev`, `roster-import`, `firestore-config-edit`, `conventions`. Claude loads them automatically when relevant.
- Companion plugins are declared in `.claude/settings.json` (`enabledPlugins`): firebase, playground, playwright, github, code-review, context7 (official marketplace), hookify (claude-code marketplace), superpowers (obra's marketplace), claude-mem (thedotmack — cross-session memory). Claude Code offers them for install when you trust this folder.
- Hooks are the only real enforcement mechanism — CLAUDE.md reminds, but an agent can forget. Anything that MUST happen belongs in a hook (use the hookify plugin to author new ones), not just in this file.

## Workflow
- Start coordinated work with `/init-kit <description>`.
- The orchestrator routes: code-scout → arch-advisor → implementer → (deep-debugger) → test-writer → code-reviewer ∥ security-auditor.
- Review "changes requested" loops back to implementer, max 2 rounds.

## Rules (non-negotiable — also enforced by hooks/permissions)
- Never run `git push`, `vercel deploy --prod`, or `rm -rf`. Humans own releases.
- Never read or write `.env*`, secrets, CI workflows, or migrations.
- Keep `tsc --noEmit` clean and `vitest run` green before finishing any task.
- New or changed logic ships with tests.
