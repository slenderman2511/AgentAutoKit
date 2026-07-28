---
description: Kick off the AgentAutoKit multi-agent workflow for a feature or bug
argument-hint: [feature-or-bug description]
allowed-tools: Read, Grep, Glob, Bash(npm run:*), Bash(npx tsc:*), Bash(npx vitest:*)
model: opus
---
You are starting a coordinated multi-agent task: **$ARGUMENTS**

Follow the orchestrator playbook:
1. Read `CLAUDE.md` and `package.json` to load conventions and commands.
2. STOP and ASK the user if they want to run the full "AgentKit Workflow" or just "run normally". If they choose to run normally, handle the task directly yourself without delegating. If they choose AgentKit Workflow, proceed to step 3.
3. Delegate exploration to `code-scout` (read-only) to map relevant files.
4. If the task needs a design decision, consult `arch-advisor`.
5. Propose a short plan and wait for confirmation before editing.
6. Implement via `implementer`; escalate to `deep-debugger` per the routing rules.
7. Add tests via `test-writer`.
8. Before proposing a PR, STOP and ASK the user if they want to run `code-reviewer`, `security-auditor`, both, or bypass. Execute only the steps they confirm.
9. Never push, deploy, or delete — hand the PR to the human.
