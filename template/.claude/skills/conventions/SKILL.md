---
name: conventions
description: Project conventions for AgentAutoKit-managed repos — npm, TypeScript, Vitest, Vercel. Use when writing or reviewing code in this repo.
---
# Conventions

## Stack
- npm (use `npm ci` in CI, `npm install` locally)
- TypeScript — keep `npx tsc --noEmit` clean
- Vitest — colocated `*.test.ts`
- Vercel — previews on PR, prod on main (humans deploy)

## Rules
- Smallest change that solves the task.
- New/changed logic ships with tests.
- Never read or write `.env*`, secrets, CI workflows, or migrations without explicit human action.
- Never run `git push`, `vercel deploy --prod`, or `rm -rf`.
