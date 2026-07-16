# AgentAutoKit

Reusable multi-agent workflow kit for **npm + TypeScript + Vitest + Vercel** projects, for use with Claude Code. Ships as **both** a repo template and a Claude Code plugin.

The idea: instead of one general assistant doing everything, AgentAutoKit gives you a small **team of specialist agents** — each on the right model tier, each with the narrowest tools it needs — coordinated by an orchestrator and fenced in by guardrail hooks so nothing risky (secrets, deploys, un-tested code) slips through.

---

## Table of contents

- [Product at a glance](#product-at-a-glance)
- [Install & use](#install--use)
- [Full inventory: every tool & feature](#full-inventory-every-tool--feature)
- [How it is delivered](#how-it-is-delivered)
- [The agent team](#the-agent-team)
- [Deep dive: what each agent does](#deep-dive-what-each-agent-does)
- [The workflow, step by step](#the-workflow-step-by-step)
- [A run, end to end](#a-run-end-to-end)
- [Guardrails](#guardrails)
- [Bundled skills & companion plugins](#bundled-skills--companion-plugins)
- [Self-tuning: measure → score → re-allocate](#self-tuning-measure--score--re-allocate)
- [Live status line — see which agents are running](#live-status-line--see-which-agents-are-running)
- [Customizing](#customizing)
- [License](#license)

---

## Product at a glance

AgentAutoKit is a drop-in `.claude/` configuration. Once installed into a project, typing `/init-kit <task>` starts a coordinated pipeline: explore → (design) → implement → (debug) → test → review, with two hooks acting as a safety net on every edit and every attempt to finish.

The moving parts:

| Part | What it is | Where it lives |
|------|------------|----------------|
| **Agents** | 8 specialists with scoped tools + model tiers | `agents/` (plugin) · `template/.claude/agents/` |
| **Guardrails** | Shell hooks that block unsafe edits and un-verified finishes | `hooks/` · `template/.claude/hooks/` |
| **Telemetry & tuning** | Per-model speed/cost + fit scoring that feeds routing back into itself | `scripts/` + `SubagentStop` hook |
| **Status line** | Live view of which agents are running (agent-panel rows + bottom bar) | `scripts/*statusline.sh` + `subagentStatusLine`/`statusLine` |
| **Commands** | `/init-kit` (entry), `/kit-stats` (scorecard), `/kit-tune` (re-allocate) | `commands/` · `template/.claude/commands/` |
| **Skills** | 13 auto-loaded skills: framework best practices + domain workflows | `skills/` · `template/.claude/skills/` |
| **Companion plugins** | 9 plugins declared for the whole team via `enabledPlugins` | `template/.claude/settings.json` |
| **Installer** | Idempotent merge-aware `init.sh` — installs, upgrades, never clobbers | `scripts/init.sh` |

---

## Install & use

Pick ONE of the two surfaces per project — never both, or agents, commands and skills load twice under the same names.

### A) As a repo template (recommended — carries permission rules + companion plugins)

```bash
git clone https://github.com/slenderman2511/AgentAutoKit
./AgentAutoKit/scripts/init.sh /path/to/your/project            # install or upgrade
./AgentAutoKit/scripts/init.sh /path/to/your/project --dry-run  # preview what would change
```

This merges `.claude/` (agents, commands, hooks, skills, **settings.json with permission deny rules and the companion-plugin roster**) and a root `CLAUDE.md` into your project.

**Upgrading** = `git pull` in the kit clone, then re-run the same `init.sh` command. It is idempotent and merge-safe:

- Missing files installed; identical files skipped; drifted files **synced to the kit's version** and listed for `git diff` review.
- Files your project added itself (extra skills, agents, commands) are never touched — no duplicates, no conflicts.
- `settings.json` is **deep-merged, never overwritten**: your permission rules, hooks, `enabledPlugins` and marketplaces are kept; the kit only fills gaps. To permanently opt out of a kit-declared plugin, set it to `false` instead of deleting the key (a deleted key gets re-filled on the next upgrade).
- An existing root `CLAUDE.md` is never overwritten; the installed kit version is stamped in `.claude/.agentautokit-version`.

### B) As a Claude Code plugin (agents/commands/hooks/skills, no permission rules)

**Step 1 — register the marketplace (once per machine).** This step is required: `plugin install` and `marketplace update` only know marketplaces you have added, so skipping it fails with `Marketplace 'agent-auto-kit-marketplace' not found`.

```bash
claude plugin marketplace add slenderman2511/AgentAutoKit
```

(or `/plugin marketplace add slenderman2511/AgentAutoKit` inside a session). If this repo is private for you, your machine needs git credentials that can read it — run `gh auth login` first.

**Step 2 — install:**

```bash
claude plugin install agent-auto-kit@agent-auto-kit-marketplace
```

**Upgrading** (Claude Code caches plugins and only re-pulls when `version` in `plugin.json` changes):

```bash
claude plugin marketplace update agent-auto-kit-marketplace   # refresh the marketplace clone
claude plugin update agent-auto-kit                           # pull the new plugin version
```

Check what you have with `claude plugin marketplace list` and `claude plugin list`.

Local test without installing:

```bash
claude --plugin-dir ./AgentAutoKit
claude plugin validate ./AgentAutoKit --strict
```

> **Important:** a plugin cannot ship permission rules or `enabledPlugins` (Claude Code only reads `agent`/`subagentStatusLine` from a plugin's settings). If you install via the plugin, add the deny rules to your project's `.claude/settings.json` yourself — copy them from [`template/.claude/settings.json`](template/.claude/settings.json).

### Then, in any installed project

```
/init-kit "add rate limiting to the login endpoint"
```

---

## Full inventory: every tool & feature

### The 8 agents

| Agent | Tier | Access | Job |
|-------|------|--------|-----|
| `orchestrator` | opus | read-only + Agent | Judges difficulty, routes to specialists, re-plans on failure, logs routing telemetry. Never writes code. |
| `code-scout` | haiku | read-only | Cheap fan-out exploration: locate code, map structure before anyone edits. |
| `arch-advisor` | opus | read-only | Design/architecture decisions before implementation. |
| `implementer` | sonnet | read-write | Routine feature/bugfix implementation. |
| `deep-debugger` | opus | read-write | Escalation target: tests failing ≥2×, async/race conditions, subtle state bugs. |
| `test-writer` | sonnet | read-write | Coverage for new/changed logic. |
| `code-reviewer` | opus | read-only | Pre-PR review (runs in parallel with security-auditor, once per PR). |
| `security-auditor` | opus | read-only | Pre-PR security pass on auth/API/rules surfaces. |

### The 3 commands

| Command | What it does |
|---------|--------------|
| `/init-kit <task>` | Entry point — kicks off the coordinated explore → design → implement → debug → test → review pipeline. |
| `/kit-stats` | Aggregates telemetry into a scorecard: per-model p50/p95 duration + cost (incl. cache tokens), per-(agent, tier) fit score, pipeline health. |
| `/kit-tune [--apply]` | Proposes (dry-run) or applies model-tier promotions/demotions from measured fit, guarded by `min_samples`. |

### The guardrail hooks

| Hook | Event | Enforcement |
|------|-------|-------------|
| `protect-files.sh` | `PreToolUse` (Edit/Write) | Blocks edits to `.env*`, secrets, keys, CI workflows, migrations. |
| `verify.sh` | `Stop` | Blocks finishing until `tsc --noEmit` + `vitest run` are green on a dirty worktree; logs pass/fail telemetry. |
| `metrics-subagent.sh` | `SubagentStop` | Measures every subagent run (tokens incl. cache, duration per sidechain) into `events.jsonl`. Never blocks. |

Hooks are the kit's enforcement layer — CLAUDE.md only reminds; hooks make rules stick. The bundled **hookify** plugin authors new ones conversationally.

### Telemetry & self-tuning (details [below](#self-tuning-measure--score--re-allocate))

- Two-sided measurement: hard numbers from transcripts (speed/tokens/cost) + pipeline proxies from the orchestrator (escalations, review rounds, verify pass rate).
- Fit scored per (agent, tier) so promotions are evaluated on fresh evidence; demotion is opt-in and requires a real escalation signal.
- Auto-tune edits one reversible `model:` frontmatter line, dry-run by default, human-reviewed diff.

### The 13 skills (details [below](#bundled-skills--companion-plugins))

`frontend-design` · `responsive-design` (+4 refs) · `next-best-practices` (+20 refs) · `playwright-best-practices` (~60 refs) · `e2e-flow` · `worktree-dev` · `roster-import` · `firestore-config-edit` · `firebase-best-practices` (+8 refs) · `payment-integration` (+6 refs) · `git-workflow` (+5 refs) · `i18n-best-practices` (+6 refs) · `conventions` — auto-loaded by Claude when the task matches their triggers.

### The 9 companion plugins

`firebase` · `playground` · `playwright` · `github` · `code-review` · `context7` (official marketplace) · `hookify` (claude-code) · `superpowers` (obra) · `claude-mem` (cross-session memory) — declared once in the template's `settings.json`, offered to every teammate who trusts the folder.

### Permission guardrails (template only)

`deny` on secret reads (`.env*`, `*.pem`, `*.key`), destructive shell (`rm -rf`), `git push`, and all deploy commands; `ask` on commits and PR creation; `allow` on the safe everyday loop (lint/test/build/tsc/vitest, kit scripts, read-only git/vercel).

### Live status line

Agent-panel rows per running subagent + a bottom-bar rollup, driven by `statusline.sh`/`subagent-statusline.sh`.

### Merge-aware installer

`init.sh` installs missing files, skips identical ones, syncs drifted ones (listed for `git diff` review), deep-merges `settings.json` (project values win; permission lists unioned; already-enabled plugins never re-added), never touches project-added files, stamps `.claude/.agentautokit-version`, supports `--dry-run`.

---

## How it is delivered

The kit exists in two forms from the same repo. They differ in one important way: **plugins cannot ship permission rules** — Claude Code only reads `agent`/`subagentStatusLine` from a plugin's settings — so the permission `deny`/`allow`/`ask` lists live only in the template's `settings.json`.

```mermaid
flowchart TB
  subgraph KIT["AgentAutoKit repo"]
    direction LR
    P["Plugin surface<br/>agents · commands · hooks · skills"]
    T["Template surface<br/>template/.claude + CLAUDE.md"]
  end
  P -->|"/plugin install"| PROJ
  T -->|"scripts/init.sh"| PROJ
  subgraph PROJ["Your project/.claude"]
    CMD["/init-kit command"]
    AG["8 specialist agents"]
    HK["Guardrail hooks"]
    ST["settings.json<br/>permission deny/allow/ask"]
  end
  note["Plugins cannot ship permission rules —<br/>only the template carries settings.json"]
  T -.->|"carries"| ST
  P -.->|"cannot ship"| note
  note -.-> ST
```

**Rule of thumb:** use the **template** if you want the permission guardrails (recommended); use the **plugin** if you just want reusable agents/commands/hooks and will add the deny rules yourself.

---

## The agent team

Eight agents split into three lanes — one coordinator, four read-only advisors, three read-write builders. Model tier is chosen per role: `haiku` for cheap fan-out exploration, `sonnet` for routine building, `opus` for judgement-heavy work (design, hard bugs, review).

```mermaid
flowchart TB
  ORC["orchestrator · opus<br/>coordinator, read-only, never writes code"]
  subgraph RO["Read-only advisors"]
    direction LR
    SC["code-scout · haiku<br/>explore & map"]
    AA["arch-advisor · opus<br/>design tradeoffs"]
    CR["code-reviewer · opus<br/>quality review"]
    SA["security-auditor · opus<br/>security review"]
  end
  subgraph RW["Read-write builders"]
    direction LR
    IM["implementer · sonnet<br/>default coding"]
    DD["deep-debugger · opus<br/>hard bugs"]
    TW["test-writer · sonnet<br/>vitest coverage"]
  end
  ORC --> RO
  ORC --> RW
```

| Agent | Model | Writes code? | Tools | One-line job |
|-------|-------|:---:|-------|--------------|
| `orchestrator` | opus | no | `Read, Grep, Glob` + delegation | Judge difficulty, route work, re-plan on failure |
| `code-scout` | haiku | no | `Read, Grep, Glob` | Locate files, call sites, dead code, TODOs |
| `arch-advisor` | opus | no | `Read, Grep, Glob` | 2–3 approaches + a recommendation |
| `implementer` | sonnet | **yes** | `Edit, Write, npm/tsc/vitest, git status/diff` | Smallest change that solves the task |
| `deep-debugger` | opus | **yes** | `Edit, Write, npm/tsc/vitest, git status/diff` | Root-cause fix for async/race/type/state bugs |
| `test-writer` | sonnet | **yes** | `Edit, Write, vitest, git diff` | Vitest coverage for edge & error paths |
| `code-reviewer` | opus | no | `Read, Grep, Glob, git diff/log` | Severity-rated review of the diff |
| `security-auditor` | opus | no | `Read, Grep, Glob, git diff` | Secrets, injection, authz, path traversal |

---

## Deep dive: what each agent does

### `orchestrator` — the coordinator (opus, read-only)
The entry brain. It never edits code itself; its whole job is judgement and routing.

- **Inputs:** the task, plus a quick read of `CLAUDE.md` + `package.json` to load conventions and commands.
- **Decides:** how hard the task is, which specialist to call, and — critically — what to do when a branch fails (re-plan rather than stop).
- **Escalation rule it enforces:** send `implementer` → `deep-debugger` **only** when the same test fails ≥ 2× on one change, or the problem is async/race, complex generics, or subtle state.
- **Feedback loop:** if review comes back "changes requested", route findings back to `implementer`, capped at **2 rounds**; after that, stop and summarize the blocker for the human.
- **Hard limits:** never push/deploy/delete, never bypass the verify gate.

> Note on execution: the orchestration *playbook* is what the `/init-kit` command runs in the main session (which can delegate). `orchestrator.md` documents that playbook.

### `code-scout` — the explorer (haiku, read-only)
Cheap, fast, high fan-out. Runs first so the expensive agents don't burn tokens re-discovering the codebase.

- **Returns:** files that matter (path + one line each), key functions/types and where they live, and anything surprising (dead code, duplicate logic, TODOs).
- **Boundaries:** proposes no changes; refuses to read `.env*`/secrets and says so instead.

### `arch-advisor` — the designer (opus, read-only)
Pulled in only when a task needs a real design decision, so you pay for opus judgement only when it matters.

- **Returns:** 2–3 viable approaches with concrete tradeoffs, one clear recommendation tied to the codebase's existing patterns, and flagged risks (coupling, migration cost, performance, testability).
- **Style:** decision-oriented — always ends with a recommendation, not a menu.

### `implementer` — the default builder (sonnet)
The workhorse. Most tasks live and die here.

- **Method:** read first (or reuse code-scout's map) → make the **smallest** change that fully solves the task → keep `tsc --noEmit` clean and `vitest run` green → match existing style.
- **Self-limiting:** if it hits the same test failure twice, it stops and reports so the orchestrator can escalate — it does not thrash.
- **Boundaries:** won't touch protected files (the hook blocks it anyway), won't push/deploy/delete.

### `deep-debugger` — the specialist (opus)
Called for the bugs `implementer` can't crack: async/race conditions, complex generics, subtle state.

- **Method:** form an explicit root-cause hypothesis *before* touching code → confirm with targeted logging or a minimal failing test → fix the root cause, not the symptom → verify with tsc + vitest → **remove debug scaffolding** before finishing.
- **Output contract:** explains the root cause in one paragraph so the fix is understood, not just applied.

### `test-writer` — the coverage author (sonnet)
Ships alongside every change with new/changed logic.

- **Method:** read the code under test and the diff → write tests for intended behavior, edge cases, and error paths → colocated `*.test.ts` matching conventions → run `vitest run` and confirm green.
- **Integrity rule:** never edits source to make a test pass — if the code looks wrong, it reports rather than papering over it.

### `code-reviewer` — quality gate (opus, read-only, once per PR)
Reviews the accumulated `git diff`, not every edit.

- **Returns:** issues grouped **Critical / Warning / Suggestion**, each with file + line + what to change; says so plainly when the diff is clean.
- **Boundaries:** reports only — the orchestrator routes fixes back to `implementer`.

### `security-auditor` — security gate (opus, read-only, once per PR)
Runs **in parallel** with `code-reviewer` so the two gates don't serialize.

- **Checks:** committed/logged secrets, injection (SQL/command/XSS), unsafe deserialization, missing authz/authn and IDOR, unsafe user-input handling and path traversal, dependency risks introduced by the change.
- **Returns:** findings by severity with concrete remediation; reports only, never edits.

---

## The workflow, step by step

```mermaid
flowchart TD
  A["/init-kit &lt;task&gt;"] --> B["orchestrator<br/>read CLAUDE.md + package.json, judge difficulty"]
  B --> C["code-scout<br/>map files, call sites, TODOs"]
  C --> D{"design decision<br/>needed?"}
  D -->|yes| E["arch-advisor<br/>2-3 approaches + recommendation"]
  D -->|no| F["implementer<br/>smallest change, tsc clean + vitest green"]
  E --> F
  F --> G{"same test fails ≥2×<br/>or async / race / types?"}
  G -->|yes| H["deep-debugger<br/>hypothesis-first root-cause fix"]
  G -->|no| I["test-writer<br/>edge + error cases"]
  H --> I
  I --> J["code-reviewer  ∥  security-auditor<br/>once per PR, in parallel"]
  J --> K{"changes<br/>requested?"}
  K -->|"yes · max 2 rounds"| F
  K -->|no| L["human opens / merges PR"]
```

The two decision diamonds are where the kit earns its keep: **escalation** (route hard bugs to opus instead of letting sonnet thrash) and the **review loop** (bounded at 2 rounds so it can't spin forever).

---

## A run, end to end

A concrete trace of "add rate limiting to the login endpoint":

```mermaid
sequenceDiagram
  actor Dev
  participant O as orchestrator
  participant S as code-scout
  participant I as implementer
  participant T as test-writer
  participant R as code-reviewer
  participant Sec as security-auditor
  Dev->>O: /init-kit "add rate limiting to login"
  O->>S: locate endpoint + middleware
  S-->>O: files, call sites, TODOs
  O->>I: implement rate limiter
  I-->>O: diff (tsc clean, vitest green)
  O->>T: cover edge + error cases
  T-->>O: tests added, green
  par once per PR
    O->>R: review diff
  and
    O->>Sec: audit diff
  end
  R-->>O: findings by severity
  Sec-->>O: security findings
  O-->>Dev: summary + PR-ready branch
```

---

## Guardrails

Two hooks enforce the rules regardless of what any agent decides. They are the reason the kit is safe to run semi-autonomously.

```mermaid
flowchart LR
  subgraph EVERY["On every Edit / Write / MultiEdit"]
    direction TB
    E1["PreToolUse"] --> PF["protect-files.sh"]
    PF --> PD{"protected path?<br/>.env · *.pem · *.key<br/>secrets/ · CI · migrations"}
    PD -->|yes| BLK["exit 2 — edit blocked"]
    PD -->|no| OK["edit allowed"]
  end
  subgraph FIN["When an agent tries to stop"]
    direction TB
    S1["Stop hook"] --> VF["verify.sh"]
    VF --> VG{"tsc --noEmit &&<br/>vitest run pass?"}
    VG -->|no| RB["block + feed failures back"]
    VG -->|yes| DONE["finish allowed"]
  end
```

- **`protect-files.sh`** (PreToolUse on `Edit|Write|MultiEdit`) — blocks writes to `.env*`, `*.pem`, `*.key`, `secrets/`, `.github/workflows/`, and `migrations/` (matched whether the path is absolute or root-relative). Exits `2`, and its stderr is fed back to the agent so it knows *why* it was blocked.
- **`verify.sh`** (Stop) — before an agent is allowed to finish, runs `tsc --noEmit` then `vitest run`. On failure it emits a `block` decision with the tail of the output, forcing a fix before completion. Skips gracefully when there is no `package.json`, and guards against infinite Stop-hook loops.

Complementing the hooks, the template's `settings.json` sets **permission** policy:

- `deny` — reading `.env`/`*.pem`/`*.key`/`secrets/`, plus `rm -rf`, `git push`, and destructive `vercel` verbs (`deploy`, `--prod`, `promote`, `rollback`, `remove`, `env rm`, `domains`).
- `allow` — safe read-only commands (`git status/diff/log`, `npm run lint/test/build`, `tsc`, `vitest`, `vercel env pull/list/logs`).
- `ask` — `git commit`, `gh pr create`, `gh pr merge` (humans confirm).

---

## Bundled skills & companion plugins

The kit ships a set of skills (loaded automatically by Claude when relevant) and declares a set of companion plugins that projects installed from the **template** pick up when the folder is trusted.

### Skills (`skills/` · `template/.claude/skills/`)

| Skill | What it covers | Origin |
|-------|----------------|--------|
| `frontend-design` | Distinctive, production-grade UI work — avoids generic "AI slop" aesthetics | Anthropic (see LICENSE.txt) |
| `responsive-design` | Reusable cross-device layout correctness: mobile-first breakpoints, fluid grid/flex + container queries, responsive images & fluid type, touch targets & hover fallbacks, viewport/safe-area, horizontal-overflow fixes, verify across viewports (4 reference files) | kit |
| `next-best-practices` | Next.js App Router conventions: RSC boundaries, data patterns, metadata, error handling (+20 reference files) | Vercel-style reference |
| `playwright-best-practices` | Full Playwright discipline: locators, flakiness, POM, CI/CD, auth, mocking (~60 reference files) | currents.dev, MIT |
| `e2e-flow` | Running/authoring full user-journey Playwright specs (dev server, seeding, Stripe test checkout, bilingual selectors) | authored from pickleball-tour |
| `worktree-dev` | Feature work in isolated git worktrees under `.claude/worktrees/` — deps, env, ports, merge-back, cleanup | authored from pickleball-tour |
| `roster-import` | Safe XLSX → Firestore roster import pipeline: assess dups → dry-run → apply → verify → rollback | authored from pickleball-tour |
| `firestore-config-edit` | Editing/seeding/syncing Firestore config + rules deploys, dev-first, with hard safety rules | authored from pickleball-tour |
| `firebase-best-practices` | Reusable Firebase correctness bar: security rules, RBAC/role standardization, Auth hardening, index optimization, Cloud Functions, Realtime Database, Remote Config (8 reference files) | kit |
| `payment-integration` | Reusable online-payment correctness bar across Stripe, Apple Pay, Google Pay, 9Pay, SePay: server-authoritative amounts, webhook/IPN signature verification, idempotency, VietQR reconciliation (6 reference files) | kit |
| `git-workflow` | Reusable Git discipline: fetch/pull/push sync, merge vs rebase, conflict resolution, and multi-agent parallelism with worktrees (5 reference files) | kit |
| `i18n-best-practices` | Reusable multi-language (EN/VI +) correctness bar: adopt/retrofit i18n in a monolingual project, catch hardcoded strings, keep locale files in parity, ICU interpolation/plurals, locale-aware date/number/currency (VND) formatting, next-intl & react-i18next setup, add-a-locale checklist (6 reference files) | kit |
| `conventions` | The kit's own coding conventions | kit |

`roster-import` and `firestore-config-edit` are domain-specific (tournament apps on Firebase); delete their folders from projects where they don't apply.

### Companion plugins (declared in the template's `settings.json`)

`enabledPlugins` + `extraKnownMarketplaces` in `template/.claude/settings.json` declare: `firebase`, `playground`, `playwright`, `github`, `code-review`, `context7` (all `@claude-plugins-official`), `hookify` (`@claude-code`), `superpowers` (`@superpowers-marketplace`, obra's), and `claude-mem` (`@thedotmack`) for semantic cross-session memory — it captures tool activity, compresses it with Claude into local SQLite, and injects relevant context into new sessions. When a teammate trusts the project folder, Claude Code surfaces these for install.

> Plugins cannot cascade-install other plugins — a plugin's own `settings.json` only honours `agent`/`subagentStatusLine`. So, like the permission rules, the companion-plugin declarations only ship with the **template**.

Why `hookify` is on the list: hooks are the only real enforcement mechanism in Claude Code — CLAUDE.md reminds, but an agent can forget. Anything that must always happen belongs in a hook, and hookify makes authoring them conversational.

---

## Self-tuning: measure → score → re-allocate

The kit measures itself and feeds the numbers back into routing, so model allocation gets closer to your real workload over time instead of staying at hand-picked defaults.

```mermaid
flowchart LR
  subgraph RUN["Each /init-kit run"]
    direction TB
    OR["orchestrator routes"] --> SUB["subagents do the work"]
  end
  SUB -->|"SubagentStop hook<br/>metrics-subagent.sh"| EV["events.jsonl<br/>speed + tokens per model"]
  OR -->|"kit-record.sh<br/>route / escalation / review"| EV
  VER["verify.sh · Stop hook"] -->|"pass / fail"| EV
  EV -->|"/kit-stats"| SC["scorecard.json + .md<br/>fit score + cost per model"]
  SC -->|"/kit-tune --apply<br/>only if ≥ min_samples"| FM["agent frontmatter<br/>model tier promoted / demoted"]
  FM -->|"next run"| OR
  SC -.->|"read at start of run"| OR
```

### What is measured, and how honestly

Two halves, deliberately kept separate because they differ in how measurable they are:

| Signal | Source | Reliability |
|--------|--------|-------------|
| **Speed & token cost per model** | `SubagentStop` hook parses the session transcript (`isSidechain` turns → model, `usage`, timestamps) | Directly measured |
| **"Fit" per agent** | Pipeline **proxies** logged by the orchestrator: escalation to `deep-debugger`, review rounds, verify first-pass | Proxy — correlates with quality, not ground truth |

There is no automatic quality oracle, so "fit" is defined as objective pipeline outcomes. For v1: `fit_score = 1 − escalation_rate` (an agent that keeps needing escalation is under-powered for its tasks). Fit is computed **per (agent, tier)** — the route events record which tier the agent was on — so after a promotion the new tier starts with a clean score instead of inheriting the failures that caused the promotion.

### The three commands / files

- **Telemetry** lands in `.claude/metrics/events.jsonl` (git-ignored). Written by the `SubagentStop` hook (speed/cost), `verify.sh` (pass/fail), and `kit-record.sh` (routing/escalation/review, called by the orchestrator).
- **`/kit-stats`** → aggregates events into `.claude/metrics/scorecard.{json,md}`: per-model p50/p95 duration + estimated cost (including cache read/write tokens, which dominate real Claude Code usage), per-(agent, tier) fit score, and pipeline health (verify first-pass rate, avg review rounds).
- **`/kit-tune`** → reads the scorecard and, **only past a sample threshold**, moves an agent along the ladder `haiku → sonnet → opus`. Dry-run by default; `--apply` edits the `model:` frontmatter line and logs the decision to `tuning-log.md`. The edit is a normal diff a human reviews before committing.

### Tuning thresholds

Configurable in `.claude/metrics/tuning.json` (defaults shown):

```json
{ "min_samples": 20, "promote_if_fit_below": 0.6, "enable_demote": false, "demote_if_fit_above": 0.97 }
```

An agent is **promoted** one tier when it has ≥ `min_samples` runs **on its current tier** and the fit score for that tier falls below `promote_if_fit_below` (rows from tiers the agent has since left are ignored). Demotion (to save cost on over-provisioned agents) is opt-in — and it additionally requires the agent to have at least one escalation on record: agents with no escalation path (scout, advisors, reviewers) have a fit score pinned at 1.0, which says nothing about over-provisioning, so blind demotion would slowly ratchet the whole team down to haiku.

Token prices for the cost estimate live in `.claude/metrics/pricing.json` — set your real per-model rates, including cache pricing:

```json
{ "sonnet": { "in": 3, "out": 15, "cache_read": 0.3, "cache_write": 3.75 } }
```

`cache_read`/`cache_write` default to 0.1× / 1.25× of `in` when omitted.

> **Honest limits:** the transcript format is internal and may change between Claude Code versions, so the parser is defensive and best-effort. Proxies correlate with quality but are not a substitute for it. Small samples are noisy — that is what `min_samples` guards against. Full auto-tune is scoped to a single reversible frontmatter edit, never anything destructive.

> Full metrics only ships with the **template** install (it carries `scripts/`). A plugin-only install still gets the `SubagentStop` speed/cost telemetry, but add the `scripts/` + commands to your project for the scorecard and auto-tune.

---

## Live status line — see which agents are running

The kit surfaces running agents in **two places**, because Claude Code exposes two separate status hooks:

**1. Agent panel rows — `subagentStatusLine`** (the authoritative one). Claude Code renders one row per active subagent below the prompt; the kit replaces the default `name · description · tokens` row with model tier, context usage, and status:

```
🤖 code-scout    haiku · 4% ctx   [running]
🤖 implementer   sonnet · 22% ctx [running]
🤖 code-reviewer opus · 6% ctx    [completed]
```

Claude Code passes a `tasks[]` array (id, name, model, `tokenCount`, `contextWindowSize`, status) on stdin once per refresh tick; the script (`scripts/subagent-statusline.sh`) prints one `{"id","content"}` line per row. This is the **only** status surface a plugin can ship, and the kit ships it in the plugin's `settings.json` — so it works for **both** plugin and template installs.

**2. Bottom bar — `statusLine`** (template only). A compact one-liner with model, dir, git branch, and a rollup of active agents:

```
▸ Opus  agentautokit  ⎇ main  🤖 code-scout · implementer×2
```

- Script: `scripts/statusline.sh`. It detects active agents by diffing `Task` tool-use ids against completed `tool_result` ids in the transcript, and reuses the same transcript the metrics hook reads.
- Set with `refreshInterval: 2` so it keeps updating **while a subagent runs** — the bottom bar is otherwise event-driven (it would only refresh when the main agent next speaks).
- Shows `·idle·` when nothing is delegating.

### Who can ship what

| Surface | Setting key | Plugin can ship? | Where the kit puts it |
|---------|-------------|:---:|-----------------------|
| Agent-panel rows | `subagentStatusLine` | ✅ yes | plugin `settings.json` + `template/.claude/settings.json` |
| Bottom bar | `statusLine` | ❌ no (project/user only) | `template/.claude/settings.json` |

Per the [plugin reference](https://code.claude.com/docs/en/plugins-reference), a plugin's `settings.json` only honours the `agent` and `subagentStatusLine` keys — `statusLine` must live in project or user settings. A plugin-only install therefore gets the agent-panel rows automatically; add the `statusLine` block to your `.claude/settings.json` if you also want the bottom-bar rollup:

```json
{
  "statusLine": {
    "type": "command",
    "command": "$CLAUDE_PROJECT_DIR/.claude/scripts/statusline.sh",
    "padding": 0,
    "refreshInterval": 2
  }
}
```

> Project settings override a user-level status line, so inside kit projects the bottom bar replaces your global one — edit or remove the block to keep yours. The bottom-bar active-agent rollup assumes the classic CLI transcript layout; it degrades to model + branch elsewhere, while the agent-panel rows use Claude Code's native `tasks[]` data and always work.

---

## Customizing

- Swap model aliases in agent frontmatter (`opus`/`sonnet`/`haiku`) or pin IDs (`claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`).
- Edit `hooks/protect-files.sh` to adjust protected paths.
- Tighten/loosen `template/.claude/settings.json` permissions per project.

## License
MIT
