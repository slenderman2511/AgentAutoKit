---
name: ui-prototype
description: Build a throwaway UX PROTOTYPE for a NEW feature/screen before any production code — one self-contained HTML file styled with the project's REAL design tokens (CLAUDE.md "## Design system"), realistic domain mock data, and an interactive state machine that demos the UX decisions; published as a Claude Artifact (stable URL across iterations) — or, in Claude Code CLI without the Artifact tool, as a secret GitHub gist rendered via gistpreview (see §4b) — and linked into the feature's GitHub issue as the BEHAVIOR SPEC. Use when the user asks to "prototype feature X", "show me the UI before coding", "mock up this screen", "UI preview", "dựng UI preview", "xem UI trước", "prototype tính năng X", "mockup màn hình", "cho tôi xem giao diện trước khi code", or when step 2 of `.claude/rules/epic-flow.md` (thin UX prototype, opt-in) fires — this skill is that step's default lane. Not for production UI code (→ frontend-design + the project's rules), not for verifying UI after implementation (→ ui-verify).
---

# UI prototype — a throwaway UX spec before code

The loop that works: prototype HTML → publish → the user clicks through and reacts (e.g. "a
list, not a grid") → revise at the same URL → record the settled decisions in the issue → the
prototype stands as the behavior spec for the implement phase. The whole value is **locking the
UX with something clickable before a single line of production code**.

Epic Flow step 2 is opt-in: run this when the user asks for it or the UX is genuinely
unsettled; otherwise the data contract + `brainstorming` is the behavior spec.

## 0. Throwaway discipline — read before the first line of HTML

- **Happy path ONLY.** No data scoping (tenant/user/org), no i18n, no error/empty/loading
  states, no TDD — it will be thrown away (epic-flow step 2). Real logic (entitlement, payment,
  quotas) is faked with a boolean/toggle.
- **Never copy prototype code into production.** Production is rebuilt on the design system
  under all project rules ("## Design system", `.claude/rules/*`, `responsive-design`,
  `accessibility`). The prototype is only the truth for *behavior*.
- **No double SOT**: once a prototype exists, do NOT write a prose spec re-describing the UX
  (epic-flow: "the one mistake"). Specs in `docs/superpowers/specs/` describe data/API only;
  for UX they link the prototype.
- The file lives in the session's **scratchpad** (or outside the repo) — never committed.

## 1. Build the HTML (one self-contained file)

**Load the `artifact-design` skill BEFORE writing the file** (the Artifact tool's page
contract). Then apply the project's REAL design system — never invent a theme:

- Read tokens and rules from CLAUDE.md "## Design system" and any `.claude/rules/*` UI rule
  files, then resolve their actual values in the codebase (CSS variables per theme,
  `tailwind.config.*` / `@theme`). Section missing → use the tokens found in the codebase and
  say so in the issue comment.
- Declare them in the prototype's `:root` under the **same names** as production, so the
  implementer maps them 1:1. Fill this before writing markup:

| Role | Token (name as in the codebase) | Value |
|---|---|---|
| surfaces, base → raised | … | … |
| text on surface / muted text | … | … |
| primary / on-primary (use as sparingly as production does) | … | … |
| elevation (the shadow/glass the system allows), radius | … | … |
| fonts, display / body | … | Google Fonts — the only stylesheet host the Artifact CSP allows |

- Same prohibitions as production (the "## Design system" list) — the prototype must look like
  something the project could ship. Mobile-first (`flex-col` → `lg:flex-row`), tap target
  ≥ 44px, `touch-action: manipulation`.

## 2. Mock data + simulated media

- Mock data comes from the **real domain** (plausible names, the label formats the product
  actually uses, valid scores/amounts/dates) — no lorem. Amounts not settled yet say
  "illustrative price (TBD)".
- **The Artifact CSP blocks remote hosts** (only Google Fonts stylesheets and a short script-CDN
  allowlist load — `artifact-design` has the list): no iframe/YouTube embeds, no remote images,
  no API calls. Simulate media with **canvas** or inline SVG — e.g. a live video feed = a
  top-down scene with a few dots wobbling on `sin(t)`, ~40 lines; a QR = random grid + 3 finder
  squares; photos/avatars = token-colored gradients or initials. Keep it inline on the gist path
  too, so both publish routes render the same.
- `prefers-reduced-motion` → stop animations.

## 3. Interactive state machine — the soul of the prototype

The prototype exists to **settle UX decisions through real interaction**, not to look pretty:

- Simulate EVERY state the user must decide on (e.g. signed out → signed in without access →
  timed preview with countdown → locked → purchase → unlocked; switching items; a 3-step
  checkout sheet).
- **Demo control bar**, bottom-right: a "PROTOTYPE" label in a color clearly outside the
  design system, quick state toggles (no access ↔ has access) + reset — so the user can walk
  every branch without replaying the flow.
- Demo **production's technical constraints** when they shape the UX — e.g. "only one video
  player mounted at a time" (many autoplaying embeds can take a page down): the prototype shows
  exactly that (one focused tile + static cards). Don't draw what production may not build.

## 4. Publish via Claude Artifact

- `<title>` = short product-style name; set `icon` on the first publish and keep it across
  versions.
- Iterate = overwrite the **SAME file path** and republish → same URL; set a `label` per
  version (`v1-prototype`, `v2-list-layout`…).
- Remind the user: the Artifact is **private by default** — for the team to open it from the
  issue, they share it from the page.

## 4b. Publish via gist (CLI / no Artifact tool) — proven recipe

In Claude Code CLI on a local machine (and when the GitHub MCP fails) there is no Artifact tool
or `artifact-design` skill. The fallback: **secret gist + gistpreview render + `gh` CLI**.
Everything in §0–§3 still holds (throwaway, real tokens, inline/canvas media, state machine,
demo bar) — only the publish step changes.

1. **File OUTSIDE the repo** (scratchpad, never committed) — e.g. `../<name>-prototype.html` at
   the workspace root. Product `<title>` + a fixed inline favicon.
2. **Create the gist** (secret by default) → prints its URL:
   ```bash
   gh gist create --desc "<Feature> — UX prototype (throwaway)" /abs/path/<name>-prototype.html
   ```
3. **Render link** (real HTML, not raw): `https://gistpreview.github.io/?<GIST_ID>` — works
   for **secret** gists too (only the id is needed). This is the link for the user and the issue.
4. **Open locally**: `open <file>` (macOS) / `xdg-open <file>` (Linux).
5. **Iterate = SAME URL**: overwrite the same file, then PATCH the gist via the API
   (deterministic; `gh gist edit` needs `$EDITOR`, so it is NOT usable non-interactively):
   ```bash
   python3 - <<'PY' > /tmp/gp.json
   import json; print(json.dumps({"files":{"<name>-prototype.html":{"content":open("/abs/path/<name>-prototype.html",encoding="utf-8").read()}}}))
   PY
   gh api -X PATCH gists/<GIST_ID> --input /tmp/gp.json --jq '.html_url'
   ```
   The key under `files` must be the gist's existing filename — a new key adds a second file.
6. **Attach to the issue** with `gh` (no MCP needed): `gh issue create …` or
   `gh issue comment <n> --body-file …` — gistpreview link + source gist link + the note
   **"secret gist: anyone with the link can open it"** + the settled UX decisions.
7. Wider team access → make the gist public (or tell the user to), like the Artifact "share" note.

## 5. Record it in the GitHub issue as the behavior spec

- Repo and labels come from CLAUDE.md "## Issue tracking". No issue for the feature yet → open
  one first via the `github-issue-flow` skill. Issue exists → comment (`gh issue comment` or the
  GitHub MCP `add_issue_comment`, plus any attribution footer the project requires) with: the
  prototype link, the "private by default" / "secret gist" note, and **the UX decisions
  settled — or CHANGED vs the original description** (e.g. "list layout instead of the grid;
  still one player mounted at a time").
- The user changes their mind after clicking through → fix the prototype + **update the issue
  in the same turn** — prototype and issue disagreeing is spec drift; the implement phase will
  build the wrong thing.
- At implement time (normal S/M/L per `.claude/rules/workflow.md`): the plan in
  `docs/superpowers/plans/` and the PR point to the prototype as the UX spec; production is free
  in the details but must keep the settled behavior.

## Gotchas (each one has cost real time)

1. **Don't let the prototype promise what production forbids** — every hard constraint (one
   player mounted, preview limits, realtime updates only where production allows them) must be
   visible in the prototype, or the user approves an impossible UX.
2. **Prototype changes layout but the issue doesn't = two specs fighting.** Update the issue in
   the same edit.
3. **Don't embed real logic or prices** — TBD prices say "illustrative"; webhooks/payments are a
   "Simulate" button.
4. **CSP**: forget "no remote assets" and the Artifact renders blank — everything inline/canvas.
5. The prototype does NOT replace `ui-verify` or the review gate for production code — it
   comes BEFORE code, not after.
