# Plan: launch-readiness rule + launch-check skill (v2.10.0)

Tier **M** (approach decided, ~16 files, no schema/payments/auth; the review-gate change is additive).
Decisions (PO 2026-10-17): rule + skill + script, no new blocking hook · em dash = limited in UI copy
only · default budget first-load JS ≤ 200 KB gzip per route, Lighthouse Performance ≥ 90.
Plan review: `arch-advisor` approve-with-changes (2026-10-17), changes folded in below.

- [x] 1. `skills/launch-check/SKILL.md` = single source: checklist MUST / CONDITIONAL / AVOID (what + Next.js
      recipe + how checked), precedence (project brand > hallmark; em-dash rule beats `hallmark/references/copy.md`
      for UI copy), PR table format, run with `node ${CLAUDE_SKILL_DIR}/scripts/launch-check.mjs`. Project facts
      from CLAUDE.md "Public web surface", else flags (`--prod-url`, `--private`, `--budget-kb`), else ask the user.
- [x] 2. `scripts/launch-check.mjs` (only `node:` imports, Node ≥ 20.9). `static <dir>`: FAIL only on clear tells
      (lorem, "Create Next App", "Get started by editing", `productionBrowserSourceMaps: true`, `href="#"`); missing
      sitemap/robots/not-found/icon/metadataBase/lang, purple-gradient pattern, em-dash density = WARN; skip
      `.claude node_modules .next out dist docs *.md(x)` tests/stories/mocks and `placeholder="…"`.
      `live <baseUrl>` against `next build && next start` (refuse dev) or a preview: rewrite prod origin → baseUrl,
      canonical by pathname, sitemap index, `--max-urls 50`, 4 parallel, same-origin; 401 → stop + `--header` hint;
      prod-only FAILs (noindex, `Disallow: /`, host) when baseUrl = prod URL. Per URL: status, title/description
      (missing FAIL, duplicate WARN), canonical, h1 (WARN), OG image (timeout WARN), img without alt attr (FAIL,
      skip `<noscript>`), JSON-LD parses, internal links resolve. JS = same-origin scripts + modulepreload, deduped,
      gzipped locally, labelled estimate. Source map: `sourceMappingURL` then `.map`, FAIL only on 200 + JSON v3
      (`--public-maps` → WARN). Random URL after redirects: 404/410 ok, 200 FAIL, Next default 404 text WARN.
      Favicon via `<link rel~=icon>` then `/favicon.ico`. `--browser`: Playwright resolved from the project cwd
      (pageerror + same-origin console = FAIL, third-party = WARN, missing = SKIP). `--lighthouse`: npx, median of 3,
      WARN on localhost. Output markdown table / `--json`; exit 1 on any FAIL.
- [x] 3. `scripts/selftest.mjs` — `node:test`, fixtures generated at runtime in `fs.mkdtemp(os.tmpdir())` + a local
      `node:http` server; nothing committed that a project's tsc/ESLint/Tailwind could pick up.
- [x] 4. `template/.claude/rules/launch-readiness.md` — only: when it fires (diff adds a public route or touches
      metadata/layout/robots/sitemap/next.config; user asks for a launch check; before the first prod deploy),
      hook into the gate, pointer to the skill. No checklist copy.
- [x] 5. `template/.claude/rules/workflow.md` rule 5: insert launch-check as (f), project-specific gates → (g).
- [x] 6. `hooks/review-gate.sh` (+ template, byte-identical): realign (d) tsc / (e) UI loop to workflow.md, add (f)
      launch-check skill.
- [x] 7. `agents/orchestrator.md` + `commands/init-kit.md` (+ template copies): add the launch-check gate line.
      `agents/code-reviewer.md` (+ template): REJECT hallmark proposals that add em dashes to UI copy.
- [x] 8. `template/.claude/CLAUDE.md`: "Public web surface" section + skill list. Mirror skill into
      `template/.claude/skills/launch-check/`. README: inventory, counts (35 → 36 skills, workflow 13 → 14),
      workflow skills table, gate, Upgrading note (copy the new CLAUDE.md section by hand). Bump plugin.json → 2.10.0.
- [x] 9. Verify from repo root: `node skills/launch-check/scripts/selftest.mjs` green; `bash -n` hooks; `jq -e .`
      JSON; `diff -rq` both surfaces; `claude plugin validate . --strict`; `scripts/init.sh <scratch> --dry-run` + real.
- [x] 10. Review gate: `code-reviewer` on full diff (no security-sensitive path, no API/data) → PR to `main`.
