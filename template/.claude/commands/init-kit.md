---
description: Kick off the AgentAutoKit workflow for a feature or bug — size it (S/M/L), route it to the specialist agents, and run the review gate
argument-hint: [feature-or-bug description]
allowed-tools: Read, Grep, Glob, Bash(npm run:*), Bash(npx tsc:*), Bash(npx vitest:*), Bash(git status), Bash(git diff:*), Bash(git log:*)
model: claude-opus-5-5
effort: high
---
You are starting a coordinated multi-agent task: **$ARGUMENTS**

Follow the playbook in `.claude/rules/workflow.md` when present (template installs; the steps below summarize it) and the project facts in `CLAUDE.md`. In order:

1. Read `CLAUDE.md` and `package.json` to load conventions, commands, the integration branch, and the security-sensitive paths.
2. **Think before coding.** State the assumptions the task rests on. If the request is ambiguous or several valid approaches exist, STOP and ask the user with `AskUserQuestion` — do not guess.
3. **Size the task S / M / L** (Q1: can the approach be stated in one sentence? Q2: does it touch schema, payments, webhooks, auth, security rules, or a `.claude/rules/` invariant?). Say the tier and why in one line. Ambiguous rounds UP.
   - **S** → implement directly (yourself or `implementer`); verify with `npx tsc --noEmit` + the related test file.
   - **M** → write a 10–20 line checkbox plan in `docs/superpowers/plans/`, show it, and wait for confirmation before editing.
   - **L** → spec in `docs/superpowers/specs/` (consult `arch-advisor` first only if the approach is undecided) → `spec-reviewer` → plan → wait for confirmation before editing.
4. Lookups that need searching → `code-scout` (batch independent ones in one message). A known path → read it directly.
5. Implement via `implementer`. Route to `deep-debugger` when the root cause is unclear or the same test fails twice.
6. New or changed logic → `test-writer` (or TDD inside the implementation step).
7. **Review gate before any PR**, on the full diff: `code-reviewer` (skip only docs/copy-only diffs) ‖ `security-auditor` when the diff touches a security-sensitive path; `npx tsc --noEmit` and every project-specific gate green. Findings go back to `implementer`, max 2 rounds.
8. Done = green exit code. Report only what a tool result in this session evidences.
9. Never push to protected branches, deploy, merge, or delete — hand the PR to the human.
