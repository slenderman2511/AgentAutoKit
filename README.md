# AgentAutoKit

Reusable multi-agent workflow kit for **npm + TypeScript + Vitest + Vercel** projects, for use with Claude Code. Ships as **both** a repo template and a Claude Code plugin.

## What's inside

**Agents** (`agents/`)
- `orchestrator` (opus) — judges difficulty, routes work, re-plans on failure
- `code-scout` (haiku, read-only) — fast code exploration
- `arch-advisor` (opus, read-only) — design decisions & tradeoffs
- `implementer` (sonnet) — default implementation
- `deep-debugger` (opus) — hard bugs (async/race/types); escalated when implementer fails ≥2×
- `test-writer` (sonnet) — Vitest coverage & edge cases
- `code-reviewer` (opus, read-only) — quality review, once per PR
- `security-auditor` (opus, read-only) — security review, in parallel with code-reviewer

**Guardrails** (`hooks/`)
- `protect-files.sh` — PreToolUse: blocks edits to `.env*`, secrets, CI workflows, migrations
- `verify.sh` — Stop: blocks finishing until `tsc --noEmit` + `vitest run` pass

**Command** — `/init-kit <task>` starts the coordinated workflow.

## Two ways to use it

### A) As a repo template (recommended — carries permission rules)

```bash
git clone https://github.com/slenderman2511/AgentAutoKit
./AgentAutoKit/scripts/init.sh /path/to/your/project
```

This copies `.claude/` (agents, commands, hooks, **settings.json with permission deny rules**) and a root `CLAUDE.md` into your project. Permission rules must live here — plugins can't ship them.

### B) As a Claude Code plugin (reusable agents/commands/hooks)

```
/plugin marketplace add slenderman2511/AgentAutoKit
/plugin install agent-auto-kit@agent-auto-kit-marketplace
```

Local test without installing:
```bash
claude --plugin-dir ./AgentAutoKit
claude plugin validate ./AgentAutoKit --strict
```

> **Important:** a plugin cannot ship permission rules (Claude Code only reads `agent`/`subagentStatusLine` from a plugin's settings). If you install via the plugin, add this to your project's `.claude/settings.json` manually:

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)", "Read(./.env.*)", "Read(./**/*.pem)", "Read(./**/*.key)", "Read(./**/secrets/**)",
      "Bash(rm -rf:*)", "Bash(git push:*)",
      "Bash(vercel deploy:*)", "Bash(vercel --prod:*)", "Bash(vercel promote:*)",
      "Bash(vercel rollback:*)", "Bash(vercel remove:*)", "Bash(vercel env rm:*)", "Bash(vercel domains:*)"
    ]
  }
}
```

## Workflow

```
/init-kit "add rate limiting to the login endpoint"
  → code-scout (map files)
  → arch-advisor (if design decision)
  → implementer  ──fail ≥2×──►  deep-debugger
  → test-writer
  → code-reviewer ∥ security-auditor   (once per PR)
      └─ changes requested ──► back to implementer (max 2 rounds)
  → human opens/merges the PR
```

## Customizing

- Swap model aliases in agent frontmatter (`opus`/`sonnet`/`haiku`) or pin IDs (`claude-opus-4-8`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`).
- Edit `hooks/protect-files.sh` to adjust protected paths.
- Tighten/loosen `template/.claude/settings.json` permissions per project.

## License
MIT
