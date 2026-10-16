---
name: launch-check
description: Launch and ship readiness check for the public web surface of a Next.js App Router project. Use before a first production deploy or a release PR, when asked "is this ready to launch?", "make it not look vibe coded", or for a pre-launch SEO/meta check (sitemap, robots, canonical, Open Graph, favicon, real 404, source maps, JS budget, console errors); and whenever a diff adds a public route or touches metadata, layout, robots, sitemap or next.config.
---

# launch-check

A site that "works" can still ship looking unfinished: template leftovers, one title on every page,
a soft 404, public source maps, no share image, an empty `robots.txt`. This skill is the checklist
for that last mile, plus a zero-dependency script that checks most of it mechanically.

## 1. Scope

Only the **public web surface**: marketing, content and public app pages. Auth-only and admin pages
get just `noindex` plus the hygiene items (no console errors, no placeholders, favicon, titles).

Project facts come from `CLAUDE.md`, section **"Public web surface"**: production URL, public routes,
private routes, budget override. If the section is missing, use the script flags (`--prod-url`,
`--private`, `--budget-kb`). If a fact is still unknown, ask the user; never guess the prod URL.

## 2. Checklist

**Check**: *static* (source scan), *live* (crawl a running build), *browser* (`--browser`),
*lighthouse* (`--lighthouse`), *manual* (reviewer judgment). **Level** is what the script reports
when the item is broken: FAIL blocks the merge, WARN needs a fix or a justification. Level
"prod only" means FAIL when the base URL is the production origin and WARN elsewhere.

### MUST

| Item | Next.js App Router recipe | Check | Level |
|---|---|---|---|
| Env-driven base URL; no hardcoded `*.vercel.app` (the custom domain itself is an ops task) | `metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL)` and `title: { template: '%s \| Brand', default: 'Brand' }` in the root `layout.tsx` | static, live | WARN |
| A URL for every meaningful view (tabs, filters, modals reachable by URL) | search params or nested routes, never state-only views | manual | - |
| Unique `<title>` and meta description per page | `generateMetadata` on dynamic routes, `export const metadata` on static ones | live | missing FAIL, duplicate WARN |
| Real 404 status (a soft 404 is a fail) and an error page | `app/not-found.tsx`, call `notFound()` for missing data, `app/error.tsx` | static, live | soft 404 FAIL, default Next 404 page WARN, missing files WARN |
| Absolute, self-referencing canonical (a wrong canonical is worse than none) | `alternates: { canonical: '/path' }` resolved by `metadataBase` | live | missing, relative, or pointing to `/` FAIL; other path mismatch WARN; wrong host prod only |
| `sitemap.xml` with only canonical, indexable URLs | `app/sitemap.ts` (or `next-sitemap`), no private or redirecting URLs | static, live | missing FAIL live, WARN static; private or redirecting URL WARN |
| `robots.txt`; never ship staging `Disallow: /` to prod; previews and staging are noindex | `app/robots.ts` reading the environment; `robots: { index: false }` outside prod | static, live | missing FAIL live, WARN static; `Disallow: /` and public `noindex` prod only |
| Pre-rendered HTML for public pages (crawlers and link-preview bots do not run JS) | SSG/ISR/SSR, no client-only rendering of main content | live (title, meta, canonical must be in the raw HTML) | FAIL via the title and meta checks |
| Internal links are real `<a href>` / `<Link>`, never `onClick` navigation on divs | `next/link` | live (broken links), manual | broken link FAIL |
| Favicon set, not the framework default | `app/icon.svg`, `app/apple-icon.png`, `app/manifest.ts` | static, live; the default Next favicon is manual | missing icon FAIL live, WARN static; template SVGs in `public/` WARN |
| Alt text on every image (decorative = `alt=""`) | `next/image` with `width`/`height` (or `fill` + `sizes`), `alt` always set | live | FAIL |
| Share image plus `og:title`, `og:description`, `og:url` | `opengraph-image.tsx` or a static 1200x630 file; `openGraph` in metadata | live | og:image missing or non-200 FAIL (timeout WARN); the rest WARN |
| `<html lang>` (and `hreflang` when multi-locale) | `<html lang="en">` in the root layout; `alternates.languages` | static, live | FAIL live, WARN static |
| No console errors, including hydration warnings and asset 404s | fix at the source | browser | FAIL (third-party WARN) |
| No public source maps | `productionBrowserSourceMaps: false`; upload maps privately to the error tracker | static, live | FAIL (WARN with `--public-maps`) |
| JS budget: first-load JS <= 200 KB gzip per route (estimate) and Lighthouse Performance >= 90 on the deployed URL | `next/font`, dynamic imports, `@next/bundle-analyzer` to find the weight | live, lighthouse | over budget FAIL, over 80% WARN; Lighthouse FAIL (WARN on localhost) |
| Private routes are `noindex` | `robots: { index: false }` in their layout metadata or an `X-Robots-Tag` header | live (`--private`) | WARN; a path that redirects to a public login page passes as auth-gated |
| Consistent redirects (www/apex, trailing slash, 301/308) | `redirects()` in `next.config`, one canonical host | manual | sitemap URL that redirects WARN |

### CONDITIONAL (apply only when the situation fits)

| Item | When and how | Check | Level |
|---|---|---|---|
| One clear `<h1>` per page | Good practice and accessibility, **not** a hard SEO rule (Google accepts several) | live | WARN |
| Breadcrumbs plus `BreadcrumbList` | Only when the site has 2 or more levels of hierarchy | manual | - |
| Structured data matching the business type | `<script type="application/ld+json">` with Organization / WebSite / Product / Event / Article. `LocalBusiness` only with a real physical location. It must match visible content: fabricated schema violates Google's spam policy | live (JSON parses), manual (truth) | invalid JSON FAIL |

### AVOID

| Item | Detail | Check | Level |
|---|---|---|---|
| Placeholders | lorem ipsum and `href="#"` FAIL; Jane Doe, John Doe, Acme Inc, "Your tagline", hardcoded "© 2024" WARN; `example.com` in visible copy, fake testimonials, TODO in UI are manual | static, manual | FAIL / WARN as listed |
| Framework template leftovers | "Create Next App" title and "Get started by editing" FAIL; `next.svg`/`vercel.svg`/`file.svg`/`globe.svg`/`window.svg` in `public/` WARN; the default favicon is manual (no hash is pinned) | static, manual | FAIL / WARN as listed |
| Purple/violet gradient hero or gradient-text headline | Taste only, unless it IS the brand (see `hallmark/references/anti-patterns.md`) | static, manual | WARN |
| Em dashes in UI copy | Limit them; prefer commas, periods, colons. They stay fine in code, comments and docs | static (density) | WARN |
| Huge JS bundles | See the budget above | live | see budget |

## 3. Precedence

1. Project brand and design tokens beat hallmark opinions.
2. For **UI copy**, this skill's em-dash rule overrides `hallmark/references/copy.md` (which recommends em dashes).
3. This skill complements the vendored `seo` skill (deeper SEO reference) and `accessibility`; when
   they disagree on a launch blocker, the stricter one wins.

## 4. How to run

Never against `next dev`: its bundles are unminified. The script refuses a server that looks like dev
(webpack and Turbopack markers), but that detection is a heuristic, not a guarantee.

Build with the production URL set in whatever env var feeds `metadataBase` (for example
`NEXT_PUBLIC_SITE_URL=https://example.com`), so canonical and Open Graph URLs resolve as they will in
production. The script rewrites that prod origin to the base URL it crawls.

```bash
# 1. Source scan, no network
node ${CLAUDE_SKILL_DIR}/scripts/launch-check.mjs static .

# 2. Production build served locally
NEXT_PUBLIC_SITE_URL=https://example.com npm run build && npx next start -p 3100
node ${CLAUDE_SKILL_DIR}/scripts/launch-check.mjs live http://localhost:3100 \
  --prod-url https://example.com [--browser] [--lighthouse]
```

Once the Vercel preview exists, re-run `live` against it and update the PR table. Only the **origin**
of the base URL is used: a `basePath` is ignored (the script says so in a SKIP row).

Vercel Deployment Protection answers 401 on previews. Pass the bypass header, with the value read
from an environment variable and never pasted into a PR or chat:

```bash
node ${CLAUDE_SKILL_DIR}/scripts/launch-check.mjs live "$PREVIEW_URL" --prod-url https://example.com \
  --header "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET"
```

Header values are sent only to the base origin (redirects to another origin drop them), are redacted
from every output row, and reach Lighthouse through a private temp file, not argv. Lighthouse and
Chrome cannot scope headers per origin, and with `--browser` a same-origin request that redirects to
another origin keeps them (a Playwright limit), so use a throwaway bypass secret for those runs.

| Flag | Meaning |
|---|---|
| `--prod-url <url>` | Production URL. Prod-only FAILs (noindex, `Disallow: /`, canonical host) apply only when the base URL **is** this origin; elsewhere they are WARN |
| `--private <glob,glob>` | Paths expected `noindex` (e.g. `/dashboard/**,/admin/**`). Skipped for SEO checks; missing noindex is WARN |
| `--budget-kb <n>` | First-load JS budget per page in gzip KB (default 200). Above it FAIL, above 80% WARN |
| `--max-urls <n>` | Max sitemap URLs to crawl (default 50), 4 requests in parallel, same origin only |
| `--header 'Name: value'` | Extra request header, repeatable |
| `--public-maps` | Public source maps (live, and `productionBrowserSourceMaps: true` in static) become WARN instead of FAIL (accepted exception) |
| `--browser` | Visit pages with Playwright resolved from the project; uncaught errors and same-origin console errors FAIL, third-party WARN; no Playwright means one SKIP row; `/_vercel/*` 404s on localhost are a SKIP |
| `--lighthouse` | Lighthouse performance 3x on `/` via `npx`, median score; < 90 FAIL (WARN on localhost) |
| `--json` | Print JSON rows instead of the markdown table |
| `--help` | Usage |

Exit codes: `0` no FAIL, `1` at least one FAIL, `2` usage error, unreachable base URL or 401/403 on `/`
(fix the access first, do not read the output as a verdict).

What the script cannot judge (still on you): whether structured data tells the truth, URL-addressable
views, redirect policy, the default favicon, copy quality, taste. Mark those in the PR as manual items.

## 5. Recording in the PR

Add a **"Launch readiness"** section to the PR body:

1. The script's markdown table (from the local `live` run, replaced by the preview run when it exists).
2. A short list of **WARN items accepted**, one line of reason each.
3. The **manual items** you checked (structured data truth, URL per view, redirects, copy).

**FAIL = must fix before merge. WARN = fix or justify.** A SKIP (for example no Playwright) is
reported as is, never counted as a pass.

## Self-test

`node ${CLAUDE_SKILL_DIR}/scripts/selftest.mjs` builds fixtures in a temp directory and starts local
HTTP servers, so nothing in the skill can trip a project's `tsc`, ESLint or Tailwind scan.
