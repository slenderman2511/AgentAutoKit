# Plan: intake-document skill + MarkItDown MCP (v2.11.0)

Tier **M** (approach decided, ~14 files, no schema/payments/auth). Decisions (PO 2026-10-17): port pick-tour's
`intake-document` skill into the kit, generalized, AND declare the MarkItDown MCP server; target = AgentAutoKit only.
Facts (PyPI, 2026-10-17): `markitdown` 0.1.8 MIT · `markitdown-mcp` 0.0.1a7 MIT, one tool `convert_to_markdown(uri)`
accepting http(s)/file/data URIs · `pymupdf4llm` 1.28.2 **AGPL-3.0** (dual commercial).
Plan review: `arch-advisor` approve-with-changes (2026-10-17), changes folded in below.

- [x] 1. `skills/intake-document/SKILL.md` — generic port: copy original (never move), verbatim Markdown with
      provenance frontmatter (`source_filename`, `intake_document`, `scope`, `type`, ISO timestamp with offset,
      `sha256`, `converter: <name> <version>`; no absolute source path), ledger row per written file, classify →
      confirm → notes → run flow, "never commit sensitive docs without asking". Run via
      `uv run --python 3.12 --with 'markitdown[docx,pptx,xlsx,xls,pdf,outlook]~=0.1.8' python "$SKILL_DIR/scripts/intake.py" …` (no `pip3
      install`, PEP 668). Project facts from CLAUDE.md "Document intake"; examples for pick-tour
      (`docs/tenants/{scope}/in/{type}`) and GoHost (`docs/features/{scope}/input` + `input/MANIFEST.md` row).
      Intake always goes through the script; the MCP is only for a quick look at a URL/file the user gave;
      converted content is untrusted data (prompt injection). AGPL note for `--pdf-engine pymupdf4llm`.
- [x] 2. `scripts/intake.py` — stdlib + lazy imports, runs on Python ≥ 3.9 (no `match`, no runtime `X | Y`). Flags:
      `--type` (validated against `--types`, default contract, proposal, finance, rules, spec, data, branding,
      others), `--title`, `--scope`, `--dest '<pattern>'` with optional `{scope}`/`{type}` (default
      `docs/intake/{type}`; scope validated against the parent dir of `{scope}` when it exists), `--ledger
      '<pattern>'` (default `docs/intake/HISTORY.md`, the only one auto-created) + `--ledger-row '<template>'`
      (`{file}` relative to the ledger dir, `{sha256}`, `{date}`, `{version}`, `{type}`, `{scope}`, `{source}`,
      `{sender}`, `{reason}`, `{notes}`; `|` escaped), `--version vX|rYYYY-MM-DD` (replaces the timestamp suffix),
      `--pdf-engine markitdown|pymupdf4llm` (default markitdown), `--sender/--reason/--notes`, `--preview`, `--root`.
      Safety: sanitize title/scope/type, resolved destinations must stay inside `--root`, existing destination →
      exit 2 (no overwrite), convert BEFORE writing anything, `convert_local()` only (never fetch URLs), images copied
      without Markdown. Missing `markitdown` → `uv run …` hint, exit 2, nothing written.
- [x] 3. `scripts/selftest.py` — `unittest`, `sys.dont_write_bytecode = True`, runtime temp dirs; fake `markitdown`
      module on sys.path for mechanics (naming, copy-not-move, frontmatter + sha256, ledger default + custom row
      matching GoHost's docs-check regex, scope validation, `--dest` without `{type}`, path traversal rejected,
      overwrite refused, image path, missing dependency exit 2, `--preview` writes nothing); real conversion case
      when `markitdown` is importable (run once more via `uv run --with …` so it is not skipped).
- [x] 4. MCP, template surface: `template/.claude/mcp.json`. `scripts/init.sh`: skip it in the `.claude/` copy loop
      (like CLAUDE.md); after the CLAUDE.md block, OPT-IN via `--with-mcp`: if the project has no root `.mcp.json` (and no
      symlink) copy it (dry-run only echoes); if it has one, never edit it — print `claude mcp add --scope project
      markitdown -e MARKITDOWN_ENABLE_PLUGINS=false -- uvx --exclude-newer 2026-10-15T00:00:00Z --python 3.12 --from
      markitdown-mcp==0.0.1a7 markitdown-mcp` when the `markitdown` key is missing (default run: opt-in note). Also add
      `-not -path '*/__pycache__/*'` to the template `find`. No `enabledMcpjsonServers`: approved on folder trust.
- [x] 5. **Template permission:** add `"mcp__markitdown__convert_to_markdown"` to `permissions.ask` in
      `template/.claude/settings.json` (the tool reads `file://` past the `Read(./.env)` / `*.pem` denies and fetches
      http(s) past WebFetch rules; `ask` beats `allow`; `merge_settings` already unions `ask` on upgrade).
- [x] 6. Plugin surface: no plugin-root MCP (plugin MCP servers start without per-server approval). README/SKILL give
      the `claude mcp add …` one-liner, the warm-up command (first start downloads MarkItDown and its dependencies), and tell plugin
      users to add the `ask` rule themselves.
- [x] 7. Docs: `template/.claude/CLAUDE.md` "Document intake" section + skill list; kit `CLAUDE.md` (init.sh now
      writes a root `.mcp.json`, skills list); README (inventory, 35 → 36 / Workflow 13 → 14, skills table,
      Upgrading `.mcp.json` handling, permissions/`ask` rule, MCP note). Mirror skill into
      `template/.claude/skills/intake-document/`. Bump `.claude-plugin/plugin.json` → 2.11.0 (rebase on #24 when merged).
- [x] 8. Verify: selftest via `python3 -I -B` and via `uv run --python 3.12 --with 'markitdown[docx,pptx,xlsx,xls,pdf,outlook]~=0.1.8'`; real
      conversion of generated docx/xlsx/pdf; no `__pycache__` under `skills/`; `bash -n scripts/init.sh`; `jq -e .`
      JSON; `diff -rq` surfaces; `claude plugin validate . --strict`; `init.sh` dry-run + real install into scratch
      (no `.mcp.json` → created; existing `.mcp.json` → untouched + hint; re-run idempotent; no `.claude/mcp.json`);
      MCP smoke: server answers MCP `initialize`, then again with `UV_OFFLINE=1`.
- [x] 9. Review gate: `code-reviewer` ‖ `security-auditor` (installer writes project-root config, new permission rule,
      MCP egress/file read) → PR to `main`.

## Changes after review (2026-10-17, code-reviewer + security-auditor)

- Converter deps: explicit extras instead of `markitdown[all]` (it pulls a pre-release Azure SDK).
- MCP is opt-in: `init.sh --with-mcp` creates the root `.mcp.json`; default prints a note with the `claude mcp add` command. The `ask` rule stays installed regardless.
- MCP launch pinned with `--exclude-newer 2026-10-15T00:00:00Z` (refreshed each kit release) and `MARKITDOWN_ENABLE_PLUGINS=false` (verified read by `markitdown_mcp/__main__.py`, default false).
- Installer hardening: never write `.mcp.json` through a symlink; a project's own `.claude/mcp.json` is kept (only a byte-identical stray kit copy is removed); `jq` check guarded when jq is missing.
- Sensitive documents: guidance only (PO decision) — the skill asks before intaking and never stages with `git add -A`.
- `intake.py`: write-path and input guards (skill agent).

Round 2 fixes: intake root must be a git top level; memory-file ledger ban + `.md`-only custom ledger; rollback no longer false-undoes; casefolded secret guard; code files stored with a `.txt` suffix; `-e MARKITDOWN_ENABLE_PLUGINS=false` in every `claude mcp add` hint; `init.sh` rejects an extra positional argument.
