# AgentAutoKit — developing the kit

This file is for sessions that work ON the kit itself. It is not installed into projects
(`scripts/init.sh` copies only `template/.claude/`, and the plugin ships `agents/`, `commands/`,
`hooks/`, `skills/`, `settings.json`).

## Reference project: pick-tour — the kit follows it

**pick-tour (SportTora) is the kit's reference implementation.** It runs this workflow in
production and is where process improvements are proven first. When evolving the kit:

- Treat `Khang-PROJ/Pickleball-WorldCup/pick-tour/.claude/` + its `CLAUDE.md` (sections Working
  Discipline, Worktree-first, Task Sizing, Model Routing) as the template. Port what is GENERIC;
  leave out what is SportTora-specific (multi-tenant rules, Firebase read-cost, theming, relay,
  tenant/deploy commands, `firebase-cost-watch`).
- Port by hand, in whichever direction applies. **Never run `init.sh` against pick-tour** — its
  agents are a tuned fork and the installer would sync them back to the kit's version.
- Keep the kit's own strengths when porting: least-privilege `tools:` per agent, the
  `protect-files` / `verify` / `metrics` hooks, and the telemetry + `/kit-tune` loop.

## Two surfaces, one behavior

- Plugin surface: `agents/`, `commands/`, `hooks/` (+ `hooks/hooks.json`), `skills/`, `settings.json`.
- Template surface: `template/.claude/` (+ `settings.json` with permissions, `rules/`, `workflows/`,
  `CLAUDE.md` → project root).
- Agents, `/init-kit`, hooks and scripts must stay byte-identical across both surfaces; only the
  script paths in `commands/kit-stats.md` / `kit-tune.md` differ (`${CLAUDE_PLUGIN_ROOT}` vs
  `.claude/scripts`). Check with `diff -rq agents template/.claude/agents` (and commands, hooks).
- Bump `version` in `.claude-plugin/plugin.json` on every behavior change — Claude Code only
  re-pulls a plugin when it changes.

## Skills — porting from pick-tour

- pick-tour's third-party skills are **symlinks** into `pick-tour/.agents/skills/` (installed by a
  skills registry; sources in `pick-tour/skills-lock.json`). Copy with `cp -RL` so the kit gets
  real files, never dangling links.
- **Third-party skill:** vendor unmodified, only if the upstream repo is licensed (check
  `gh api repos/<owner>/<repo>/license`). Add the upstream `LICENSE` text and a `SOURCE.md`
  (upstream repo, license, date). Never vendor an unlicensed repo — point to its install command
  in the template `CLAUDE.md` instead (e.g. `vercel-labs/next-skills` → moved to `vercel/next.js`).
- **pick-tour workflow skill** (context-checkpoint, ui-*, github-issue-*): generalize — project
  facts come from the template `CLAUDE.md` sections "Design system", "Source of truth",
  "Issue tracking", "Git workflow".
- **Domain skills** (`roster-import`, `firestore-config-edit`, `e2e-flow`) stay pickleball-specific
  and are refreshed verbatim from pick-tour.
- Same name, different skill: `accessibility` (kit's own, fuller than pick-tour's addyosmani one)
  and `worktree-dev` (kit's generic version + pick-tour's env-file lesson) are kit-owned.
- Skills live in both `skills/` and `template/.claude/skills/` — keep them identical.

## Models

Agent tiers are pinned IDs: `claude-opus-5-5`, `claude-sonnet-5-5`, `haiku` (Haiku 4.5, no
`effort`). When bumping a pin, also update `kit_rank_alias` in `scripts/kit-metrics-lib.sh` and the
default prices in `scripts/kit-stats.sh`, in both surfaces.

## Verify before claiming done

- `bash -n` on every changed `*.sh`; `jq -e .` on every changed `*.json`.
- `claude plugin validate . --strict`.
- `scripts/init.sh <scratch-project> --dry-run`, then a real install into a scratch project.
