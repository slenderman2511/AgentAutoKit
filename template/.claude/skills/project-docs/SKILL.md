---
name: project-docs
description: Set up and maintain the 8 core project docs an AI agent needs before writing code — PRD, DESIGN_SYSTEM, ARCHITECTURE, DATABASE, SECURITY, CODE_STYLE, TESTING, AGENTS — as numbered-section markdown in docs/, plus a one-file HTML viewer with a completion sidebar. Use when starting a new project or feature set ("before we vibe code", "set up project docs", "write a PRD / architecture / design system doc"), when an agent keeps guessing context that should be written down, when docs are stale after a change, or when the user asks to view/share the docs as a page.
---

# project-docs

Eight short documents give every agent (and every new teammate) the same locked-in context: what we
build, how it looks, how it is put together, what the data is, who may do what, how code is written,
how it is proven, and how agents behave. Vague context produces hallucinated code; these docs replace it.

```
/project-docs init  [docs-dir]     copy the 8 templates into docs/ (never overwrites an existing file)
/project-docs fill  [DOC|all]      fill a doc from the codebase + the user's decisions
/project-docs check [docs-dir]     status + open placeholders per doc
/project-docs view  [docs-dir]     build docs/index.html (sidebar, progress, numbered sections, diagrams)
```

| Doc | Answers | Fill mostly from |
|---|---|---|
| `PRD.md` | What, for whom, why, how we measure it | the user (problem, users, goals, metrics) |
| `DESIGN_SYSTEM.md` | Tokens, type, spacing, components, breakpoints | tokens/theme files, component library |
| `ARCHITECTURE.md` | Containers, stack, structure, data flow, boundaries | package manifests, folder tree, config |
| `DATABASE.md` | Entities, relations, scoping, indexes, migrations | schema / migrations / security rules |
| `SECURITY.md` | Threats, auth, roles, trust boundaries, secrets | auth code, middleware, rules, env usage |
| `CODE_STYLE.md` | Principles, tooling, naming, patterns, git | lint/format config, existing code |
| `TESTING.md` | Layers, commands, must-test list, CI lanes | test config, CI workflows (`test-guard`) |
| `AGENTS.md` | Agent roles, workflow, tools, limits | `.claude/` agents + rules, CLAUDE.md |

## Format (keep it — the viewer depends on it)

- Front matter: `title`, `summary`, `status: draft|review|done`, `owner`, `updated`.
- Body = sections `## NN · Title` (two-digit number, middle dot), each opened by one italic line
  `_what this section answers_`. Order is fixed; numbers say where to look ("ARCHITECTURE §04").
- Prefer tables, checklists (`- [ ]`), short lists and ```mermaid diagrams over paragraphs.
- Placeholders are `<…>` (and `#______` for colors). A doc is `done` only when `check` shows 0
  placeholders and the owner agreed. Delete a row that does not apply instead of leaving `<…>`.
- Write in the project's documentation language; keep code identifiers, paths and commands as-is.

## init

```bash
mkdir -p docs && for f in "$SKILL_DIR"/templates/*.md; do [ -e "docs/$(basename "$f")" ] || cp "$f" docs/; done
```
`$SKILL_DIR` = this skill's folder (plugin: `${CLAUDE_PLUGIN_ROOT}/skills/project-docs`; template
install: `.claude/skills/project-docs`). Existing files are never overwritten — merge by hand. If the
project already keeps one of these topics elsewhere (a SOT, `DESIGN.md`, ADRs), the doc becomes a
short summary that **links** to that source; never keep two copies of the same fact.

## fill

1. **Scout first** (read-only, delegate to a scout agent when wide): read the sources in the table
   above and fill every placeholder the code can answer. Cite paths (`src/lib/auth.ts`) instead of
   copying code.
2. **Ask only for decisions** the code cannot answer (product goals, metrics, priorities, roles,
   retention): batch them in one round, each with a recommended answer. For an M/L project use the
   `grill-me` skill. Never invent business facts — leave `<…>` and list it under "Open Questions".
3. Keep each doc to what an agent needs to act: one screen per section, no essays.
4. Set `status: review`, `updated: <today>`; the user flips it to `done`.

## check

```bash
python3 -I "$SKILL_DIR/scripts/build-docs-viewer.py" docs --check
```
Prints `n/8 standard docs done`, each doc's status and placeholder count (including front matter and
`<…>` inside text/mermaid fences), and missing standard docs. Exit 1 while any of the eight is missing,
not `done`, or still has a placeholder; extra docs (CHANGELOG, notes) are listed but never gate — usable
as a CI step or before handing docs to an agent.

## view

```bash
python3 -I "$SKILL_DIR/scripts/build-docs-viewer.py" docs -o docs/index.html --title "<Project> docs"
```
One HTML file: file tree with status dots and open-placeholder counts, a progress bar, the selected
doc as numbered sections with a section index, tables, checklists and rendered mermaid; light and
dark themes; works at phone width. The markdown stays the source of truth — regenerate after edits.
Add `--artifact` when publishing the file as a Claude Artifact (the host supplies doctype and head);
any static host takes the default output. Raw HTML inside the markdown is shown as text, never
executed, and non-http links lose their `href`.

## Keeping docs current

`AGENTS.md` §08 maps code changes to the doc they update. Reviewers treat a behavior change with no
matching doc update as a finding. Re-run `check` before a release.
