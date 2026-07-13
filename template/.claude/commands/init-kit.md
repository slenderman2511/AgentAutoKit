---
description: Kick off the AgentAutoKit multi-agent workflow for a feature or bug
argument-hint: [feature-or-bug description]
allowed-tools: Read, Grep, Glob, Bash(npm run:*), Bash(npx tsc:*), Bash(npx vitest:*)
model: opus
---
You are starting a coordinated multi-agent task: **$ARGUMENTS**

Follow the orchestrator playbook:
1. Read `CLAUDE.md` and `package.json` to load conventions and commands.
2. Delegate exploration to `code-scout` (read-only) to map relevant files.
3. If the task needs a design decision, consult `arch-advisor`.
4. Propose a short plan and wait for confirmation before editing.
5. Implement via `implementer`; escalate to `deep-debugger` per the routing rules.
6. Add tests via `test-writer`.
7. Run `code-reviewer` and `security-auditor` in parallel before proposing a PR.
8. Never push, deploy, or delete — hand the PR to the human.
