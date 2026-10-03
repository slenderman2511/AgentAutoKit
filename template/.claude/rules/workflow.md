# AgentAutoKit workflow — MUST FOLLOW

This is the kit's playbook: how every task is sized, routed, verified and reviewed. Project facts
(commands, integration branch, security-sensitive paths, extra gates) live in the root `CLAUDE.md`.
This file is managed by AgentAutoKit and is re-synced on upgrade — put project-specific rules in
their own `.claude/rules/*.md` files instead of editing this one.

## Working discipline — every change, every tier

Task sizing (below) picks the *process weight*; this picks the *mindset*.

1. **Think before coding — state assumptions, ask when ambiguous.** Before writing or editing code,
   state the core assumptions your approach rests on. If the instruction is ambiguous, or several
   valid implementation paths exist, **STOP and ask the user** (use `AskUserQuestion`) — do not guess
   or pick silently. Escalate the *model* when the root cause is unclear; ask the *user* when the
   requirement is unclear.
2. **Simplicity first (YAGNI).** Write the minimum code that satisfies the stated task. No
   speculative features, no unrequested abstractions, no defensive boilerplate for edge cases nobody
   asked about. Mirror the surrounding code's existing patterns instead of inventing new ones.
3. **Surgical changes.** Touch only the files and lines the request needs. No refactoring of adjacent
   code, reformatting, renaming, or drive-by cleanups in untouched areas — genuine cleanup is its own
   task, never a rider on an unrelated change.
4. **Goal-driven verification.** Decide the success criterion *before* you start (which test or
   typecheck proves it done), then actually run it before handing back. Report only what a tool
   result in this session evidences.

## Worktree-first — every implement / bug-fix task

Start every code task in its own git worktree, not in the shared checkout. The shared checkout is
often on another session's branch; editing it tangles two tasks and breaks each other's `tsc`/tests.

- **Create:** `git fetch origin <integration> --quiet && git worktree add -b <branch> .claude/worktrees/<branch-slug> origin/<integration>`
  — branch off the LATEST integration branch named in `CLAUDE.md`. Use the `worktree-dev` skill to
  copy gitignored env files when you need the dev server or seed scripts.
- **Work, verify, commit and push inside the worktree**, then open the PR from there.
- **After the PR merges, delete the worktree:** `git worktree remove .claude/worktrees/<branch-slug>`
  (+ `git branch -d <branch>`; a hand-deleted folder leaves a stub → `git worktree prune`). Do not
  remove it before merge — review feedback may need it.
- **Exceptions (edit the shared checkout directly):** doc/config edits to `.claude/**`, `CLAUDE.md`,
  `AGENTS.md`, and trivial one-liners the user asks to apply in place.

## Task sizing — S / M / L (classify EVERY task before touching code)

> **Epic wrapper (`.claude/rules/epic-flow.md`):** for a multi-feature epic where the data model OR
> UX is not settled yet, run the Epic Flow gate first; each production slice then falls back into
> S/M/L below. Single tasks skip it entirely.

- **Q1:** Can the root cause / approach be stated in one sentence?
- **Q2:** Does it touch data schema or migrations, payments or webhooks, auth or permissions,
  security rules, or another invariant listed in `.claude/rules/`?

| Tier | When | Flow |
|---|---|---|
| **S** | Q1=yes, Q2=no, ≤3 files, mirrors an existing pattern | Implement directly (main session or `implementer`). NO spec, NO plan, NO arch-advisor. Verify: `npx tsc --noEmit` + the related test file. |
| **M** | Q1=yes, 4–10 files, or a new route/feature mirroring an existing one | NO spec. Write a 10–20 line checkbox mini-plan in `docs/superpowers/plans/` → `arch-advisor` plan-review (one read-only pass: layers, reuse, boundaries) → implement → full review gate. |
| **L** | Q2=yes, or Q1=no, or a new subsystem / data-model change | Spec in `docs/superpowers/specs/` → `spec-reviewer` → plan (checkbox state machine, `**Spec:**` backlink, Task 1 = pure logic + failing test) → execute → full review gate → **e2e user-journey pass** (`e2e-flow`) with the camera on (`e2e-visual-proof`: step screenshots in the viewport(s) the user picks + one proof page linked in the PR) BEFORE merge — when the project has an e2e suite; ask Yes/No first if it writes to a shared dev backend. |

- **Ambiguous tier rounds UP.** A mis-tiered L executed as S costs far more than the process it skipped.
- **Review gate scales with tier:** S = `code-reviewer` on the diff (skip entirely when the diff
  touches ONLY docs or UI copy). M/L = the full gate (Orchestrator rule 5). `security-auditor`
  triggers on its own path list regardless of tier — sizing never skips it.
- **Sizing ≠ routing.** Tier decides *process weight*; difficulty decides *model choice*. A 2-file
  change with an unknown root cause is S-sized but still goes to `deep-debugger`.
- **One design pass (L).** `arch-advisor` is an OPTIONAL consult before the spec, only when the
  approach is genuinely undecided. Once the spec exists, `spec-reviewer` is the single design gate.
- **Plans are durable state machines:** tick a `- [ ]` only after that step is verified. A new
  session resumes from the first unticked step.

### Speed rules (all tiers)

- Known file path → Read it directly; searching → `code-scout`. Batch independent lookups in ONE message.
- Run `npx tsc --noEmit` ONCE on the final accumulated diff, not after every edit.
- S/M tiers run targeted test files only; the full suite belongs to CI.
- **Done = green exit code.** Red tests are reported red, with output. Never claim done from re-reading your own code.
- **S/M commits and PRs are done by the main session directly.** Spawning `github-workflow` for a
  single commit + PR adds a round-trip re-gathering context the main session already has — reserve
  it for multi-branch, rebase or conflict work.

## Model routing — subagent delegation

The main session is the **orchestrator**. Delegate routine work to `.claude/agents/` so cheaper
models absorb the token load. Fable is NEVER assigned to a subagent.

**`.claude/agents/` is the single agent roster.** Tune it in place with `/kit-tune`, score it with
`/kit-stats`. Do not run a parallel roster from another orchestration framework on top of it.

| Task type | Agent | Model | Effort |
|---|---|---|---|
| Find files/symbols/call sites, check configs, summarize existing code | `code-scout` | haiku | – |
| Small features, known-cause fixes, pattern-following refactors (1–5 files) | `implementer` | claude-sonnet-5-5 | high |
| Write/fix Vitest or Playwright tests, test factories | `test-writer` | claude-sonnet-5-5 | high |
| Complex git ops ONLY (multi-branch, rebase, conflicts) | `github-workflow` | claude-sonnet-5-5 | high |
| Approach genuinely undecided BEFORE the spec (optional design consult) | `arch-advisor` | claude-opus-5-5 | xhigh |
| Security review of security-sensitive paths (once per PR) | `security-auditor` | claude-opus-5-5 | xhigh |
| M-tier plan review — one read-only pass before implementing | `arch-advisor` | claude-opus-5-5 | xhigh |
| API / data-model contract review — versioning, all clients, schema, indexes, read cost (once per PR) | `api-data-reviewer` | claude-opus-5-5 | xhigh |
| Post-change review against project rules (once per PR) | `code-reviewer` | claude-opus-5-5 | xhigh |
| Unknown root cause, race conditions, complex multi-file refactors | `deep-debugger` | claude-opus-5-5 | xhigh |
| Review a design spec before the plan (L tier only) | `spec-reviewer` | claude-opus-5-5 | xhigh |

### Orchestrator rules

1. **Delegate searches, read known paths directly.** Lookups that need *searching* go to
   `code-scout`; a known path is read in the main session.
2. **Parallelize independent lookups** — spawn them in a single message.
3. **Route by difficulty, not by size:** obvious fix → `implementer`; "why is this happening?" →
   `deep-debugger`; "how should we build this?" → `arch-advisor` first, then `implementer`.
4. **Escalate when uncertain — cheap models never guess.** `implementer`/`test-writer` are for
   changes whose approach is decided and whose root cause is known. If you cannot state the root
   cause in one sentence, or the fix spans an unclear number of files, route to `deep-debugger` or
   run `arch-advisor` first. Ambiguous difficulty defaults UP, never down.
5. **Review gate is MANDATORY before every PR.** On the full accumulated diff: (a) `code-reviewer`
   once; (b) `security-auditor` once IF the diff touches a security-sensitive path listed in
   `CLAUDE.md`; (c) `api-data-reviewer` once IF the diff touches API routes, a persisted data
   type/schema, index definitions, or adds a collection/table/field/query; (d) `npx tsc --noEmit`
   green; (e) the UI design-conformance loop (`ui-design-conformance.md`) IF the diff adds or visibly changes a page/screen or user-facing component; (f) every project-specific gate listed in `CLAUDE.md` green. Run (a) ‖ (b) ‖ (c) in parallel. Findings go back to `implementer`, max 2 rounds, then stop and
   summarize the blocker for the human. A PreToolUse hook reminds you at `gh pr create` — treat it as
   a stop, not noise.
6. **Subagents return concise summaries** — do not ask them for full file dumps.
7. **Never pass `model` to the Agent tool.** It overrides the agent's pinned tier for that run, so
   an `implementer` call silently costs opus prices. Pick a different agent instead; `/kit-stats`
   flags overridden runs as off-pin.

### Main-session model policy

- **Daily driver:** `claude-opus-5-5`, pinned via `"model"` in `.claude/settings.json` (project
  settings beat user settings, so every machine runs the same model). Override per session with
  `claude --model sonnet` on light days.
- **Escalate manually** to `claude --model claude-fable-5-1` ONLY for genuinely hard tasks: large
  migrations, long autonomous work, complex multi-stage debugging. It costs ~2.5× Opus 5.5 per token.
- **Do NOT set `CLAUDE_CODE_SUBAGENT_MODEL`** — it overrides the per-agent `model` frontmatter and
  breaks this routing.
