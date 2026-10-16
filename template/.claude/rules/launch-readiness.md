# Launch readiness — public web surface — MUST FOLLOW

A site that compiles and passes review still routinely ships **looking vibe coded**: soft 404s, wrong
canonicals, missing OG image or favicon, placeholder copy, public source maps. Type-checks and
`code-reviewer` check rules, not "would a stranger trust this site". The `launch-check` skill closes the gap.

## When it fires

Before the review gate, whenever:
- the diff adds a public route/page, or touches root/route metadata, layout, `robots`, `sitemap`,
  `not-found`, icons, OG images or `next.config`;
- the user asks for a launch / SEO / "does this look vibe coded" check;
- before the first production deploy or a release PR.

Skip for private-only diffs (auth/admin routes), except their `noindex` and the hygiene checks.

## What to do

1. Run the `launch-check` skill: `static` always; `live` against `next build && next start`
   (never the dev server), and re-run `live` on the preview URL once it exists.
2. **FAIL** = fix before merge. **WARN** = fix or justify in one line.
3. Record the skill's **Launch readiness** table in the PR body.
4. Project facts (production URL, public vs private routes, budgets, business type) come from the
   `CLAUDE.md` section "Public web surface"; if it is missing, the skill asks the user.

## Guardrails

- The checklist, the precedence rules (project brand > hallmark; the em dash limit in UI copy beats
  hallmark's copy advice) and the PR table format live ONLY in the skill's `SKILL.md`. Do not copy
  them here or into other files; point to the skill.
- No blocking hook: this is a reminder at the review gate, not a stop on every edit.
- Screenshots and reports go in the PR / a scratch dir, never committed into the source tree.
