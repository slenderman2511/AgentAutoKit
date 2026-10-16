---
title: Code Style
summary: How code is written here, so every file reads as if one person wrote it.
status: draft
owner: <@login>
updated: <YYYY-MM-DD>
---

## 01 · Principles
_The few rules that decide the rest._

1. **Readable over clever** — the next reader is a teammate or an agent with no context
2. **Small, surgical changes** — touch only what the task needs; no drive-by refactors
3. **One home per concept** — search before writing a helper, type or constant
4. **Fail loudly** — no swallowed errors; the user always gets feedback

## 02 · Tooling
_Formatters and linters decide style; humans don't argue about it._

| Tool | Command | Runs in |
|---|---|---|
| Formatter | `<prettier / pint / black>` | pre-commit, CI |
| Linter | `<eslint / phpstan / ruff>` | CI |
| Type check | `<tsc --noEmit / mypy>` | CI, before PR |

## 03 · Naming
_Names say what a thing is or does._

| Thing | Convention | Example |
|---|---|---|
| Files | <kebab-case / PascalCase> | `<example>` |
| Components / classes | PascalCase | `<InvoiceList>` |
| Functions / variables | camelCase, verbs for functions | `<calculateTotal>` |
| Constants | UPPER_SNAKE | `<MAX_RETRIES>` |
| Booleans | `is/has/can` prefix | `<isLoading>` |

## 04 · Project Patterns
_The patterns this codebase already uses. Mirror them._

- Data access: <repository / service / server action> — never from UI components
- State: <library / pattern>
- Errors: <Result type / exceptions + error boundary>; user-facing messages via <i18n key>
- Imports: <path alias>; dependency direction <UI → services → core>

## 05 · Functions & Components
_Size and shape._

- Early returns over nested conditionals
- One responsibility per function; extract when a block needs a comment to explain *what* it does
- Components handle every UI state: loading · empty · error · success

## 06 · Comments & Docs
_Comments explain why, not what._

- Comment non-obvious decisions, workarounds (with issue link) and invariants
- Public functions of shared modules get a one-line doc comment
- `TODO` only with an issue link: `TODO(#123): …`

## 07 · Git Conventions
_Branches, commits and PRs._

- Branch: `<type>/<issue>-<slug>` off `<integration branch>`
- Commits: Conventional Commits — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- PR: one task = one PR; description says why, how it was tested, and what to watch

## 08 · Review Checklist
_What reviewers (human or agent) check before approving._

- [ ] Follows the patterns above; no duplicated helper/type
- [ ] Types strict; no `any` without a reason
- [ ] Tests prove the change (see `TESTING.md`)
- [ ] No secrets, debug output or commented-out code
