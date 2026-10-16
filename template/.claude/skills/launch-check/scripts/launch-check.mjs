#!/usr/bin/env node
/**
 * launch-check: pre-launch checks for the PUBLIC web surface of a Next.js (App Router) project.
 * Zero dependencies (node: modules only), Node >= 20.9 (global fetch).
 *
 *   node launch-check.mjs static <dir>      [flags]   scan source files, no network
 *   node launch-check.mjs live <baseUrl>    [flags]   crawl a running production build or preview
 *
 * Flags: --prod-url <url> --private <glob,glob> --budget-kb <n> --max-urls <n> --header 'Name: value'
 *        --public-maps --browser --lighthouse --json --help       (run with --help for details)
 *
 * Exit codes: 0 no FAIL, 1 at least one FAIL, 2 usage error / unreachable base / 401-403 on "/".
 * Never run `live` against `next dev`: use `next build && next start` or a deployed preview.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { createRequire } from 'node:module';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const STATUS_ORDER = ['FAIL', 'WARN', 'SKIP', 'PASS'];
const REQUEST_TIMEOUT_MS = 15000;
const CONCURRENCY = 4;
const MAX_LINKS = 100;

const HELP = `launch-check <static|live> <dir|baseUrl> [flags]

  static <dir>       scan source files for launch blockers (placeholders, template leftovers,
                     missing sitemap/robots/not-found/icon/metadataBase, purple gradients, em dashes)
  live <baseUrl>     crawl a running site (next build && next start, or a preview URL);
                     only the origin of <baseUrl> is used, a basePath is ignored

Flags:
  --prod-url <url>       production URL; its origin in sitemap/canonicals is rewritten to <baseUrl>,
                         and prod-only FAILs (noindex, Disallow: /, canonical host) apply only when
                         <baseUrl> IS this origin
  --private <globs>      comma-separated paths expected noindex (e.g. "/dashboard/**,/admin/**"),
                         skipped for SEO checks
  --budget-kb <n>        first-load JS budget per page, gzip KB (default 200)
  --max-urls <n>         max pages to crawl from the sitemap (default 50)
  --header 'Name: value' extra request header for same-origin requests, repeatable (e.g. Vercel
                         protection bypass); values are redacted from the output
  --public-maps          downgrade public source maps (live and next.config) from FAIL to WARN
  --browser              visit pages with Playwright (resolved from the project) and report console errors
  --lighthouse           run Lighthouse performance 3x on "/" via npx (median score, min 90)
  --json                 print JSON instead of a markdown table
  --help                 show this text

Exit: 0 no FAIL, 1 any FAIL, 2 usage error / unreachable / 401-403 on "/".`;

// ---------------------------------------------------------------------------------------------
// Result model
// ---------------------------------------------------------------------------------------------

class ExitError extends Error {
  constructor(message, code = 2) {
    super(message);
    this.exitCode = code;
  }
}

// Header values (--header) are secrets: they must never reach a report row or an error message.
let secrets = [];

function redact(text) {
  let out = String(text ?? '');
  for (const secret of secrets) out = out.split(secret).join('***');
  return out;
}

class Report {
  constructor() {
    this.rows = [];
    this.passes = new Map();
    this.notPassed = new Set();
  }

  add(check, target, status, detail = '') {
    this.rows.push({ check: redact(check), target: redact(target), status, detail: redact(detail) });
    if (status !== 'PASS') this.notPassed.add(check);
  }

  /** Record one successful unit (page, link...) for a check; collapsed into one PASS row at finish. */
  ok(check, unit = 'page') {
    const entry = this.passes.get(check) ?? { n: 0, unit };
    entry.n += 1;
    this.passes.set(check, entry);
  }

  finish() {
    for (const [check, { n, unit }] of this.passes) {
      if (this.notPassed.has(check)) continue;
      this.rows.push({ check, target: '', status: 'PASS', detail: `${n} ${unit}${n === 1 ? '' : 's'} ok` });
    }
    const rank = (s) => STATUS_ORDER.indexOf(s);
    this.rows.sort((a, b) => rank(a.status) - rank(b.status) || a.check.localeCompare(b.check));
  }

  counts() {
    const c = { FAIL: 0, WARN: 0, SKIP: 0, PASS: 0 };
    for (const r of this.rows) c[r.status] += 1;
    return c;
  }
}

function listCap(items, n = 10) {
  const shown = items.slice(0, n).join(', ');
  return items.length > n ? `${shown} (+${items.length - n} more)` : shown;
}

function describeError(e) {
  if (!e) return 'unknown error';
  const cause = e.cause?.code ?? e.cause?.message;
  return cause ? `${e.message} (${cause})` : String(e.message ?? e);
}

// ---------------------------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------------------------

function parseArgs(argv) {
  const o = {
    mode: null, target: null, prodUrl: null, privateGlobs: [], budgetKb: 200, maxUrls: 50,
    headers: {}, publicMaps: false, browser: false, lighthouse: false, json: false, help: false,
  };
  const positional = [];
  const needValue = (i, flag) => {
    const v = argv[i + 1];
    if (v === undefined || (v.startsWith('--') && flag !== '--header')) throw new ExitError(`${flag} needs a value`);
    return v;
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    switch (a) {
      case '--help': case '-h': o.help = true; break;
      case '--json': o.json = true; break;
      case '--public-maps': o.publicMaps = true; break;
      case '--browser': o.browser = true; break;
      case '--lighthouse': o.lighthouse = true; break;
      case '--prod-url': o.prodUrl = needValue(i, a); i += 1; break;
      case '--private': o.privateGlobs = needValue(i, a).split(',').map((s) => s.trim()).filter(Boolean); i += 1; break;
      case '--budget-kb': o.budgetKb = Number(needValue(i, a)); i += 1; break;
      case '--max-urls': o.maxUrls = Number(needValue(i, a)); i += 1; break;
      case '--header': {
        const raw = needValue(i, a);
        i += 1;
        const idx = raw.indexOf(':');
        if (idx < 1) throw new ExitError("--header expects 'Name: value' (missing ':')");
        o.headers[raw.slice(0, idx).trim()] = raw.slice(idx + 1).trim();
        break;
      }
      default:
        if (a.startsWith('--')) throw new ExitError(`unknown flag ${a}`);
        positional.push(a);
    }
  }
  [o.mode, o.target] = positional;
  secrets = Object.values(o.headers).filter((v) => v.length >= 3);
  if (o.help) return o;
  if (!['static', 'live'].includes(o.mode) || !o.target) throw new ExitError('usage: launch-check <static|live> <dir|baseUrl> [flags] (see --help)');
  if (!Number.isFinite(o.budgetKb) || o.budgetKb <= 0) throw new ExitError('--budget-kb must be a positive number');
  if (!Number.isInteger(o.maxUrls) || o.maxUrls < 1) throw new ExitError('--max-urls must be a positive integer');
  return o;
}

function renderMarkdown(report, title) {
  const c = report.counts();
  const cell = (s) => String(s ?? '').replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ');
  const lines = [
    `### ${title}`,
    '',
    `**${c.FAIL} FAIL · ${c.WARN} WARN · ${c.SKIP} SKIP · ${c.PASS} PASS**`,
    '',
    '| Status | Check | Target | Detail |',
    '|---|---|---|---|',
    ...report.rows.map((r) => `| ${r.status} | ${cell(r.check)} | ${cell(r.target)} | ${cell(r.detail)} |`),
  ];
  return lines.join('\n');
}

// ---------------------------------------------------------------------------------------------
// STATIC
// ---------------------------------------------------------------------------------------------

const SKIP_DIRS = new Set([
  '.git', '.claude', 'node_modules', '.next', 'out', 'dist', 'build', 'coverage', 'docs', '.vercel', '.turbo',
  '__tests__', '__mocks__', 'tests', 'test', 'e2e', 'mocks', 'fixtures', 'stories', '.storybook', 'storybook-static',
  'cypress', 'playwright', 'playwright-report', 'test-results',
]);
const TEXT_EXT = new Set(['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.html', '.json', '.css']);
const CODE_EXT = new Set(['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.html']);
const JSX_EXT = new Set(['.jsx', '.tsx', '.html']);
const SKIP_FILE_RE = /\.(?:test|spec|stories|e2e|mock|mocks|fixture|fixtures)\.[a-z]+$|(?:^|[._-])seeds?\.[cm]?[jt]s$/i;
const MAX_FILE_BYTES = 1024 * 1024;
const DEFAULT_ASSETS = ['next.svg', 'vercel.svg', 'file.svg', 'globe.svg', 'window.svg'];

// Built from parts so this file never contains a literal Tailwind gradient class.
const PURPLE_RE = new RegExp(`(?:${['from', 'via'].join('|')})-(?:${['purple', 'violet', 'fuchsia'].join('|')})-\\d{3}`);
const LOREM_RE = new RegExp(`${'lorem'}\\s+${'ipsum'}`, 'i');
const EM_DASH = '—';

const LINE_RULES = [
  { check: 'lorem-ipsum', status: 'FAIL', re: LOREM_RE },
  { check: 'create-next-app', status: 'FAIL', re: /Create Next App/i },
  { check: 'get-started-by-editing', status: 'FAIL', re: /Get started by editing/i },
  { check: 'source-maps-config', status: 'FAIL', re: /productionBrowserSourceMaps\s*:\s*true/, fileRe: /(?:^|\/)next\.config\.[^/]+$/, raw: true },
  { check: 'href-hash', status: 'FAIL', re: /href\s*=\s*(?:"#"|'#'|\{\s*["'`]#["'`]\s*\})/, exts: CODE_EXT },
  { check: 'placeholder-names', status: 'WARN', re: /\b(?:Jane Doe|John Doe|Acme Inc|Your tagline)/i },
  { check: 'hardcoded-copyright', status: 'WARN', re: /(?:©|&copy;)\s*20\d\d/, exts: JSX_EXT },
  { check: 'purple-gradient', status: 'WARN', re: PURPLE_RE, exts: new Set([...CODE_EXT, '.css']) },
  { check: 'vercel-app-hardcoded', status: 'WARN', re: /[\w-]+\.vercel\.app\b/, exts: CODE_EXT },
];

const SCRIPT_EXT = new Set(['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']);

/**
 * Blank out comments (newlines kept, so line numbers stay valid). Small string-aware scanner:
 * "//" after ":" is treated as part of a URL, and quotes end at a newline (JSX text has apostrophes).
 */
function stripComments(text, ext) {
  if (ext === '.html') return text.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '));
  const lineComments = SCRIPT_EXT.has(ext);
  if (!lineComments && ext !== '.css') return text;
  let out = '';
  let quote = null;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    const next = text[i + 1];
    if (quote) {
      out += c;
      if (c === '\\') { out += next ?? ''; i += 1; } else if (c === quote || (c === '\n' && quote !== '`')) quote = null;
      continue;
    }
    // `\/*` is an escaped slash inside a regex literal, not a comment; an unclosed `/*` is left as is.
    if (c === '/' && next === '*' && text[i - 1] !== '\\') {
      const end = text.indexOf('*/', i + 2);
      if (end === -1) { out += c; continue; }
      const stop = end + 2;
      out += text.slice(i, stop).replace(/[^\n]/g, ' ');
      i = stop - 1;
      continue;
    }
    if (lineComments && c === '/' && next === '/' && text[i - 1] !== ':') {
      const end = text.indexOf('\n', i);
      const stop = end === -1 ? text.length : end;
      out += ' '.repeat(stop - i);
      i = stop - 1;
      continue;
    }
    if (lineComments && (c === '"' || c === "'" || c === '`')) quote = c;
    out += c;
  }
  return out;
}

function walk(root) {
  const files = [];
  const visit = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isSymbolicLink()) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) visit(full);
        continue;
      }
      if (!entry.isFile()) continue;
      const ext = path.extname(entry.name).toLowerCase();
      if (!TEXT_EXT.has(ext) || SKIP_FILE_RE.test(entry.name)) continue;
      if (entry.name === 'package-lock.json' || entry.name.includes('.min.')) continue;
      files.push(full);
    }
  };
  visit(root);
  return files.sort();
}

function stripPlaceholders(line) {
  return line.replace(/placeholder\s*=\s*(?:"[^"]*"|'[^']*'|\{[^}]*\})/g, 'placeholder=""');
}

function anyEntry(root, dirs, re) {
  return dirs.some((d) => {
    const full = path.join(root, d);
    return fs.existsSync(full) && fs.readdirSync(full).some((n) => re.test(n));
  });
}

function runStatic(o) {
  const root = path.resolve(o.target);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) throw new ExitError(`not a directory: ${o.target}`);
  const rep = new Report();
  const hits = new Map();
  const hit = (check, text) => hits.set(check, [...(hits.get(check) ?? []), text]);
  const files = walk(root);
  let sawMetadataBase = false;
  let sawHtmlLang = false;

  for (const file of files) {
    if (fs.statSync(file).size > MAX_FILE_BYTES) continue;
    const rel = path.relative(root, file).split(path.sep).join('/');
    const ext = path.extname(file).toLowerCase();
    const text = fs.readFileSync(file, 'utf8');
    const lines = text.split('\n');
    const codeLines = stripComments(text, ext).split('\n');
    if (/\bmetadataBase\b/.test(text)) sawMetadataBase = true;
    if (/<html\b[^>]*\blang\b/i.test(text)) sawHtmlLang = true;

    lines.forEach((raw, i) => {
      const line = stripPlaceholders(raw);
      const code = stripPlaceholders(codeLines[i] ?? '');
      for (const rule of LINE_RULES) {
        if (rule.exts && !rule.exts.has(ext)) continue;
        if (rule.fileRe && !rule.fileRe.test(rel)) continue;
        if (rule.re.test(rule.raw ? line : code)) hit(rule.check, `${rel}:${i + 1}`);
      }
    });

    const isMessages = ext === '.json' && /(?:^|\/)(?:messages|locales|i18n)\//.test(rel);
    if (ext === '.tsx' || ext === '.jsx' || isMessages) {
      const visible = isMessages ? lines : codeLines;
      const count = visible.reduce((n, l) => n + l.split(EM_DASH).length - 1, 0);
      const length = visible.join('\n').length;
      if (count > 3 || (count >= 2 && (count * 200) / Math.max(length, 1) > 1)) {
        const firstLine = visible.findIndex((l) => l.includes(EM_DASH)) + 1;
        hit('em-dash', `${rel}:${firstLine} (${count} in ${length} chars)`);
      }
    }
  }

  for (const rule of LINE_RULES) {
    const found = hits.get(rule.check);
    const status = rule.check === 'source-maps-config' && o.publicMaps ? 'WARN' : rule.status;
    if (found) rep.add(rule.check, '.', status, listCap(found));
    else rep.add(rule.check, '.', 'PASS', 'none found');
  }
  const emDash = hits.get('em-dash');
  if (emDash) rep.add('em-dash', '.', 'WARN', `UI copy with many em dashes, prefer commas/periods/colons: ${listCap(emDash)}`);
  else rep.add('em-dash', '.', 'PASS', 'none found');

  const defaults = DEFAULT_ASSETS.filter((n) => fs.existsSync(path.join(root, 'public', n))).map((n) => `public/${n}`);
  if (defaults.length) rep.add('default-assets', 'public/', 'WARN', `framework template leftovers: ${defaults.join(', ')}`);
  else rep.add('default-assets', 'public/', 'PASS', 'none found');

  const appDirs = ['app', 'src/app'];
  const presence = [
    ['sitemap', anyEntry(root, appDirs, /^sitemap\.(?:ts|js|tsx|jsx|xml)$/) || anyEntry(root, ['public'], /^sitemap.*\.xml$/) || anyEntry(root, ['.'], /^next-sitemap\.config\./), 'app/sitemap.ts, public/sitemap.xml or next-sitemap.config.*'],
    ['robots', anyEntry(root, appDirs, /^robots\.(?:ts|js|txt)$/) || anyEntry(root, ['public'], /^robots\.txt$/), 'app/robots.ts or public/robots.txt'],
    ['not-found', anyEntry(root, appDirs, /^not-found\.(?:tsx|jsx|ts|js)$/) || anyEntry(root, ['pages', 'src/pages'], /^404\./), 'app/not-found.tsx'],
    ['error-page', anyEntry(root, appDirs, /^(?:global-)?error\.(?:tsx|jsx|ts|js)$/) || anyEntry(root, ['pages', 'src/pages'], /^_error\./), 'app/error.tsx'],
    ['icon', anyEntry(root, appDirs, /^(?:icon|favicon)\.(?:svg|png|ico|jpg|jpeg|tsx|ts|js)$/) || anyEntry(root, ['public'], /^favicon\./), 'app/icon.svg, app/favicon.ico or public/favicon.*'],
  ];
  for (const [check, present, expected] of presence) {
    if (present) rep.add(check, '.', 'PASS', 'found');
    else rep.add(check, '.', 'WARN', `missing: ${expected}`);
  }
  if (sawMetadataBase) rep.add('metadataBase', '.', 'PASS', 'found');
  else rep.add('metadataBase', '.', 'WARN', 'no metadataBase in any file (set it in the root layout from an env var)');
  if (sawHtmlLang) rep.add('html-lang', '.', 'PASS', 'found');
  else rep.add('html-lang', '.', 'WARN', 'no <html lang=...> in any file');

  rep.add('files-scanned', '.', 'PASS', `${files.length} files`);
  rep.finish();
  return { rep, title: `launch-check static ${o.target}` };
}

// ---------------------------------------------------------------------------------------------
// HTML helpers (regex based, no dependencies)
// ---------------------------------------------------------------------------------------------

/** Numeric entities can be out of range in hostile or broken HTML: keep the original text then. */
function codePointOr(original, cp) {
  return Number.isInteger(cp) && cp >= 0 && cp <= 0x10ffff ? String.fromCodePoint(cp) : original;
}

function decodeEntities(s) {
  return s
    .replace(/&#x([0-9a-f]+);/gi, (m, h) => codePointOr(m, parseInt(h, 16)))
    .replace(/&#(\d+);/g, (m, d) => codePointOr(m, Number(d)))
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
}

function findTags(html, name) {
  return html.match(new RegExp(`<${name}\\b(?:"[^"]*"|'[^']*'|[^>"'])*>`, 'gi')) ?? [];
}

function getAttr(tag, name) {
  const m = tag.match(new RegExp(`[\\s"']${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s"'>]+))`, 'i'));
  return m ? decodeEntities(m[1] ?? m[2] ?? m[3]) : null;
}

function hasAttr(tag, name) {
  return new RegExp(`[\\s"']${name}(?=[\\s=/>])`, 'i').test(tag);
}

function stripBlocks(html, names) {
  let out = html.replace(/<!--[\s\S]*?-->/g, '');
  for (const n of names) out = out.replace(new RegExp(`<${n}\\b[\\s\\S]*?</${n}>`, 'gi'), '');
  return out;
}

function metaContent(html, key) {
  for (const tag of findTags(html, 'meta')) {
    const k = (getAttr(tag, 'name') ?? getAttr(tag, 'property') ?? '').toLowerCase();
    if (k === key) return (getAttr(tag, 'content') ?? '').trim();
  }
  return null;
}

function linkHref(html, rel) {
  for (const tag of findTags(html, 'link')) {
    const rels = (getAttr(tag, 'rel') ?? '').toLowerCase().split(/\s+/);
    if (rels.includes(rel)) return getAttr(tag, 'href');
  }
  return null;
}

function normPath(p) {
  return p.length > 1 ? p.replace(/\/+$/, '') || '/' : p;
}

function globToRegExp(glob) {
  let g = glob.startsWith('/') ? glob : `/${glob}`;
  let trailing = false;
  if (g.endsWith('/**')) { g = g.slice(0, -3); trailing = true; }
  const esc = (s) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
  const body = g.split('**').map((part) => part.split('*').map(esc).join('[^/]*')).join('.*');
  return new RegExp(`^${body}${trailing ? '(?:/.*)?' : '/?'}$`);
}

/** One shared limit for every network request (pages and assets alike). */
function makeSemaphore(max) {
  let active = 0;
  const waiting = [];
  return async (fn) => {
    if (active >= max) await new Promise((resolve) => waiting.push(resolve));
    else active += 1;
    try {
      return await fn();
    } finally {
      const next = waiting.shift();
      if (next) next();
      else active -= 1;
    }
  };
}

async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next;
      next += 1;
      results[i] = await fn(items[i], i);
    }
  });
  await Promise.all(workers);
  return results;
}

// ---------------------------------------------------------------------------------------------
// LIVE
// ---------------------------------------------------------------------------------------------

function makeContext(o) {
  let baseUrl;
  try { baseUrl = new URL(o.target); } catch { throw new ExitError(`invalid base URL: ${o.target}`); }
  if (!/^https?:$/.test(baseUrl.protocol)) throw new ExitError('base URL must be http(s)');
  let prodOrigin = null;
  if (o.prodUrl) {
    try { prodOrigin = new URL(o.prodUrl).origin; } catch { throw new ExitError(`invalid --prod-url: ${o.prodUrl}`); }
  }
  const baseOrigin = baseUrl.origin;
  const privateMatchers = o.privateGlobs.map(globToRegExp);
  return {
    o,
    baseOrigin,
    prodOrigin,
    isProd: prodOrigin !== null && prodOrigin === baseOrigin,
    isLocal: ['localhost', '127.0.0.1', '[::1]'].includes(baseUrl.hostname),
    headers: o.headers,
    gate: makeSemaphore(CONCURRENCY),
    basePath: baseUrl.pathname !== '/' ? baseUrl.pathname : null,
    noindexPages: [],
    foreignOrigins: new Set(),
    assetCache: new Map(),
    isPrivate: (p) => privateMatchers.some((re) => re.test(normPath(p))),
  };
}

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);
const MAX_REDIRECTS = 5;

/**
 * GET/HEAD with manual redirect handling: --header values are sent only to the base origin and are
 * dropped as soon as a redirect leaves it.
 */
async function request(ctx, url, { method = 'GET', readBody = true } = {}) {
  return ctx.gate(async () => {
    let current = url;
    let verb = method;
    try {
      for (let hop = 0; hop <= MAX_REDIRECTS; hop += 1) {
        const headers = new URL(current).origin === ctx.baseOrigin ? ctx.headers : {};
        const res = await fetch(current, { method: verb, headers, redirect: 'manual', signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
        const location = res.headers.get('location');
        if (REDIRECT_STATUSES.has(res.status) && location) {
          await res.body?.cancel();
          current = new URL(location, current).href;
          if (res.status === 303) verb = 'GET';
          continue;
        }
        let body = Buffer.alloc(0);
        if (readBody) body = Buffer.from(await res.arrayBuffer());
        else await res.body?.cancel();
        return { ok: true, status: res.status, headers: res.headers, body, text: body.toString('utf8'), finalUrl: current };
      }
      throw new Error(`more than ${MAX_REDIRECTS} redirects`);
    } catch (error) {
      const timedOut = error?.name === 'TimeoutError' || error?.name === 'AbortError';
      return { ok: false, error, timedOut, status: 0, headers: new Headers(), body: Buffer.alloc(0), text: '', finalUrl: current };
    }
  });
}

/** Map a URL on the prod origin (or an origin seen in the sitemap) onto the base origin. */
function rewrite(ctx, url) {
  if (url.origin !== ctx.baseOrigin && (url.origin === ctx.prodOrigin || ctx.foreignOrigins.has(url.origin))) {
    return new URL(`${url.pathname}${url.search}`, ctx.baseOrigin);
  }
  return url;
}

/** Without --prod-url, the first foreign origin seen in robots/sitemap is treated as production. */
function noteForeignOrigin(ctx, url) {
  if (url.origin !== ctx.baseOrigin && url.origin !== ctx.prodOrigin && ctx.foreignOrigins.size === 0) ctx.foreignOrigins.add(url.origin);
}

function getAsset(ctx, url) {
  if (!ctx.assetCache.has(url)) ctx.assetCache.set(url, request(ctx, url));
  return ctx.assetCache.get(url);
}

function parseRobots(text) {
  const groups = [];
  const sitemaps = [];
  let current = null;
  let sawRule = false;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trim();
    const idx = line.indexOf(':');
    if (idx < 1) continue;
    const key = line.slice(0, idx).trim().toLowerCase();
    const value = line.slice(idx + 1).trim();
    if (key === 'sitemap') { sitemaps.push(value); continue; }
    if (key === 'user-agent') {
      if (!current || sawRule) { current = { agents: [], disallow: [] }; groups.push(current); sawRule = false; }
      current.agents.push(value.toLowerCase());
    } else if (key === 'disallow' || key === 'allow') {
      sawRule = true;
      if (current && key === 'disallow') current.disallow.push(value);
    }
  }
  const star = groups.filter((g) => g.agents.includes('*'));
  return { sitemaps, blocksAll: star.some((g) => g.disallow.includes('/')) };
}

function xmlLocs(xml) {
  return [...xml.matchAll(/<loc>\s*([\s\S]*?)\s*<\/loc>/gi)].map((m) => decodeEntities(m[1].replace(/<!\[CDATA\[|\]\]>/g, '')).trim());
}

async function checkRobots(ctx, rep) {
  const res = await request(ctx, `${ctx.baseOrigin}/robots.txt`);
  const looksLikeHtml = /^\s*<(?:!doctype|html)/i.test(res.text);
  if (!res.ok || res.status !== 200 || looksLikeHtml) {
    rep.add('robots.txt', '/robots.txt', 'FAIL', res.ok ? `status ${res.status}${looksLikeHtml ? ' (HTML, not robots.txt)' : ''}` : describeError(res.error));
    return { sitemaps: [] };
  }
  const parsed = parseRobots(res.text);
  if (parsed.blocksAll) {
    rep.add('robots.txt', '/robots.txt', ctx.isProd ? 'FAIL' : 'WARN', ctx.isProd ? 'Disallow: / on the production origin blocks all crawlers' : 'Disallow: / (fine for staging/preview, make sure it is not what prod serves)');
  } else {
    rep.add('robots.txt', '/robots.txt', 'PASS', `${parsed.sitemaps.length} Sitemap line(s)`);
  }
  return parsed;
}

async function collectSitemapUrls(ctx, rep, robots) {
  const sources = robots.sitemaps.length ? robots.sitemaps : [`${ctx.baseOrigin}/sitemap.xml`];
  const locs = [];
  const queue = sources.map((s) => ({ url: s, depth: 0 }));
  let fetched = 0;
  while (queue.length && fetched < 12) {
    const { url, depth } = queue.shift();
    fetched += 1;
    let target;
    try {
      const raw = new URL(url, ctx.baseOrigin);
      noteForeignOrigin(ctx, raw);
      target = rewrite(ctx, raw);
    } catch { rep.add('sitemap', url, 'WARN', 'unparseable sitemap URL'); continue; }
    if (target.origin !== ctx.baseOrigin) { rep.add('sitemap', url, 'WARN', 'sitemap on another origin, skipped'); continue; }
    const res = await request(ctx, target.href);
    if (!res.ok || res.status !== 200) {
      rep.add('sitemap', target.pathname, 'FAIL', res.ok ? `status ${res.status}` : describeError(res.error));
      continue;
    }
    const entries = xmlLocs(res.text);
    if (/<sitemapindex\b/i.test(res.text) && depth < 2) entries.forEach((e) => queue.push({ url: e, depth: depth + 1 }));
    else locs.push(...entries);
  }
  if (!locs.length) {
    if (!rep.rows.some((r) => r.check === 'sitemap' && r.status === 'FAIL')) rep.add('sitemap', '/sitemap.xml', 'FAIL', 'no <loc> entries');
    return ['/'];
  }

  const urls = [];
  let dropped = 0;
  for (const loc of locs) {
    let u;
    try { u = new URL(loc); } catch { dropped += 1; continue; }
    noteForeignOrigin(ctx, u);
    const mapped = rewrite(ctx, u);
    if (mapped.origin !== ctx.baseOrigin) { dropped += 1; continue; }
    urls.push(`${normPath(mapped.pathname)}${mapped.search}`);
  }
  if (dropped) rep.add('sitemap', '/sitemap.xml', 'WARN', `${dropped} <loc> entries on other origins or invalid, ignored`);
  const unique = [...new Set(urls)];
  if (!unique.includes('/')) unique.unshift('/');
  rep.ok('sitemap', 'sitemap');
  return unique;
}

/** Heuristic only: dev chunk names (webpack and Turbopack) and the "development" build id. */
function looksLikeNextDev(html) {
  return /\/_next\/static\/chunks\/(?:main-app|react-refresh)\.js|hmr-client|%5Bturbopack%5D|\[turbopack\]|"buildId":"development"|\\"b\\":\\"development\\"/.test(html)
    || html.includes('/_next/static/development/');
}

function analyzeNoindex(ctx, rep, label, html, headers, isPrivatePage) {
  const robotsMeta = `${metaContent(html, 'robots') ?? ''} ${metaContent(html, 'googlebot') ?? ''}`.toLowerCase();
  const header = (headers.get('x-robots-tag') ?? '').toLowerCase();
  const noindex = robotsMeta.includes('noindex') || header.includes('noindex');
  if (isPrivatePage) {
    if (noindex) rep.ok('private-noindex');
    else rep.add('private-noindex', label, 'WARN', 'private route without noindex (meta robots or X-Robots-Tag)');
    return;
  }
  if (!noindex) rep.ok('noindex');
  else if (ctx.isProd) rep.add('noindex', label, 'FAIL', 'public page is noindex on the production origin');
  else ctx.noindexPages.push(label);
}

function analyzeCanonical(ctx, rep, label, html, pagePath) {
  const href = linkHref(html, 'canonical');
  if (!href) { rep.add('canonical', label, 'FAIL', 'missing <link rel="canonical">'); return; }
  let canon;
  try { canon = new URL(href); } catch { rep.add('canonical', label, 'FAIL', `not absolute: ${href}`); return; }
  const canonPath = normPath(canon.pathname);
  if (canonPath === '/' && pagePath !== '/') { rep.add('canonical', label, 'FAIL', 'canonical points to / on a non-home page'); return; }
  if (canonPath !== pagePath) { rep.add('canonical', label, 'WARN', `canonical path ${canonPath} differs from page path`); return; }
  if (ctx.isProd && canon.origin !== ctx.prodOrigin) { rep.add('canonical', label, 'FAIL', `canonical host ${canon.host} is not the production host`); return; }
  if (canon.hostname.endsWith('.vercel.app') && canon.origin !== ctx.baseOrigin) {
    rep.add('canonical', label, ctx.isProd ? 'FAIL' : 'WARN', `canonical uses a hardcoded ${canon.hostname}`);
    return;
  }
  rep.ok('canonical');
}

async function analyzeOgImage(ctx, rep, label, html, pageUrl) {
  const content = metaContent(html, 'og:image');
  if (!content) { rep.add('og:image', label, 'FAIL', 'missing og:image'); return; }
  let target;
  try { target = rewrite(ctx, new URL(content, pageUrl)); } catch { rep.add('og:image', label, 'FAIL', `invalid og:image URL: ${content}`); return; }
  const res = await getAsset(ctx, target.href);
  if (res.timedOut) rep.add('og:image', label, 'WARN', `timeout fetching ${target.pathname}`);
  else if (!res.ok) rep.add('og:image', label, 'WARN', `could not fetch ${target.pathname}: ${describeError(res.error)}`);
  else if (res.status !== 200) rep.add('og:image', label, 'FAIL', `og:image ${target.pathname} returned ${res.status}`);
  else rep.ok('og:image');
}

function collectScripts(ctx, html, pageUrl) {
  const raw = stripBlocks(html, []);
  const urls = new Set();
  const add = (href) => {
    if (!href) return;
    try {
      const u = rewrite(ctx, new URL(href, pageUrl));
      // /_vercel/* (analytics, speed-insights) is only served on Vercel; off it, it 404s by design.
      if (ctx.isLocal && u.pathname.startsWith('/_vercel/')) return;
      if (u.origin === ctx.baseOrigin) urls.add(u.href);
    } catch { /* malformed asset URL: nothing to measure */ }
  };
  for (const tag of findTags(raw, 'script')) {
    if (!hasAttr(tag, 'nomodule')) add(getAttr(tag, 'src'));
  }
  for (const tag of findTags(raw, 'link')) {
    const rel = (getAttr(tag, 'rel') ?? '').toLowerCase();
    if (rel === 'modulepreload' || (rel === 'preload' && (getAttr(tag, 'as') ?? '').toLowerCase() === 'script')) add(getAttr(tag, 'href'));
  }
  return [...urls];
}

async function analyzeJsBudget(ctx, rep, label, scripts) {
  if (!scripts.length) { rep.ok('js-budget'); return; }
  const results = await Promise.all(scripts.map((s) => getAsset(ctx, s)));
  let bytes = 0;
  const failed = [];
  results.forEach((r, i) => {
    if (!r.ok || r.status !== 200) { failed.push(new URL(scripts[i]).pathname); return; }
    bytes += zlib.gzipSync(r.body).length;
  });
  if (failed.length) rep.add('js-assets', label, 'FAIL', `script assets not loadable: ${listCap(failed, 5)}`);
  else rep.ok('js-assets');
  const kb = Math.round(bytes / 1024);
  const detail = `~${kb} KB gzip (estimate), budget ${ctx.o.budgetKb} KB`;
  if (kb > ctx.o.budgetKb) rep.add('js-budget', label, 'FAIL', detail);
  else if (kb > ctx.o.budgetKb * 0.8) rep.add('js-budget', label, 'WARN', detail);
  else rep.ok('js-budget');
}

async function analyzeSourceMaps(ctx, rep, scripts, seen) {
  for (const script of scripts) {
    if (seen.has(script)) continue;
    seen.add(script);
    const asset = await getAsset(ctx, script);
    if (!asset.ok || asset.status !== 200) continue;
    const tail = asset.text.slice(-600);
    const m = tail.match(/\/\/[#@]\s*sourceMappingURL=(\S+)\s*$/m);
    let mapUrl;
    try {
      if (m && m[1].startsWith('data:')) { rep.add('source-maps', new URL(script).pathname, ctx.o.publicMaps ? 'WARN' : 'FAIL', 'inline source map embedded in the bundle'); continue; }
      mapUrl = m ? new URL(m[1], script) : new URL(`${script.split('?')[0]}.map`);
    } catch { continue; }
    const map = await getAsset(ctx, mapUrl.href);
    let isMap = false;
    if (map.ok && map.status === 200) {
      try { isMap = JSON.parse(map.text).version === 3; } catch { isMap = false; }
    }
    if (isMap) rep.add('source-maps', mapUrl.pathname, ctx.o.publicMaps ? 'WARN' : 'FAIL', 'public source map (set productionBrowserSourceMaps: false, upload maps privately to the error tracker)');
    else rep.ok('source-maps', 'script');
  }
}

function collectLinks(ctx, html, pageUrl, from, linkMap) {
  for (const tag of findTags(stripBlocks(html, ['script', 'style', 'noscript']), 'a')) {
    const href = getAttr(tag, 'href');
    if (!href || href.startsWith('#') || /^(?:mailto|tel|javascript|data):/i.test(href)) continue;
    let u;
    try { u = rewrite(ctx, new URL(href, pageUrl)); } catch { continue; }
    if (u.origin !== ctx.baseOrigin || u.pathname.startsWith('/_next/')) continue;
    const key = `${normPath(u.pathname)}${u.search}`;
    if (!linkMap.has(key)) linkMap.set(key, { url: `${ctx.baseOrigin}${key}`, from });
  }
}

async function analyzePage(ctx, rep, page, shared) {
  const label = page.key;
  const { html, headers } = page;
  if (page.isPrivate) {
    analyzeNoindex(ctx, rep, label, html, headers, true);
    return;
  }
  const pagePath = normPath(new URL(page.finalUrl).pathname);
  if (pagePath !== normPath(page.key.split('?')[0])) {
    rep.add('redirect', label, 'WARN', `sitemap URL redirects to ${pagePath}, list the final URL`);
  }

  const titleMatch = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? decodeEntities(titleMatch[1]).trim() : '';
  if (title) { rep.ok('title'); shared.titles.set(title, [...(shared.titles.get(title) ?? []), label]); } else rep.add('title', label, 'FAIL', 'missing <title>');

  const description = metaContent(html, 'description');
  if (description) { rep.ok('description'); shared.descriptions.set(description, [...(shared.descriptions.get(description) ?? []), label]); } else rep.add('description', label, 'FAIL', 'missing meta description');

  analyzeCanonical(ctx, rep, label, html, pagePath);

  const htmlTag = findTags(html, 'html')[0] ?? '';
  if (getAttr(htmlTag, 'lang')) rep.ok('html-lang'); else rep.add('html-lang', label, 'FAIL', 'missing <html lang>');

  const visible = stripBlocks(html, ['script', 'style', 'noscript', 'template']);
  const h1s = (visible.match(/<h1\b/gi) ?? []).length;
  if (h1s === 1) rep.ok('h1'); else rep.add('h1', label, 'WARN', `${h1s} <h1> elements (one clear h1 is good practice)`);

  await analyzeOgImage(ctx, rep, label, html, page.finalUrl);
  for (const key of ['og:title', 'og:description', 'og:url']) {
    if (metaContent(html, key)) rep.ok(key); else rep.add(key, label, 'WARN', `missing ${key}`);
  }

  const noAlt = findTags(visible, 'img').filter((t) => !hasAttr(t, 'alt'));
  if (noAlt.length) rep.add('img-alt', label, 'FAIL', `${noAlt.length} <img> without alt: ${listCap(noAlt.map((t) => getAttr(t, 'src') ?? '(no src)'), 3)}`);
  else rep.ok('img-alt');

  const ldBlocks = [...html.matchAll(/<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)];
  const badLd = ldBlocks.filter((m) => { try { JSON.parse(m[1]); return false; } catch { return true; } });
  if (badLd.length) rep.add('json-ld', label, 'FAIL', `${badLd.length} of ${ldBlocks.length} JSON-LD block(s) are not valid JSON`);
  else if (ldBlocks.length) rep.ok('json-ld');

  analyzeNoindex(ctx, rep, label, html, headers, false);

  collectLinks(ctx, html, page.finalUrl, label, shared.links);
  const scripts = collectScripts(ctx, html, page.finalUrl);
  await analyzeJsBudget(ctx, rep, label, scripts);
  await analyzeSourceMaps(ctx, rep, scripts, shared.seenScripts);
}

function reportDuplicates(rep, check, map, what) {
  for (const [value, pages] of map) {
    if (pages.length > 1) rep.add(check, listCap(pages, 5), 'WARN', `duplicate ${what}: "${value.slice(0, 80)}"`);
    else rep.ok(check);
  }
}

/** A private path that redirects to a public page (login) is auth-gated: nothing to index there. */
function authGatedTo(ctx, key, finalUrl) {
  const finalPath = normPath(new URL(finalUrl).pathname);
  return finalPath !== normPath(key.split('?')[0]) && !ctx.isPrivate(finalPath) ? finalPath : null;
}

async function checkLinks(ctx, rep, fetchedKeys, linkMap) {
  const pending = [...linkMap.entries()].filter(([key]) => !fetchedKeys.has(key));
  const capped = pending.slice(0, MAX_LINKS);
  await mapLimit(capped, CONCURRENCY, async ([key, { url, from }]) => {
    const priv = ctx.isPrivate(key.split('?')[0]);
    const res = await request(ctx, url, { readBody: priv });
    if (!res.ok) rep.add('internal-links', key, 'FAIL', `unreachable (linked from ${from}): ${describeError(res.error)}`);
    else if (res.status >= 400 && !(priv && (res.status === 401 || res.status === 403))) rep.add('internal-links', key, 'FAIL', `status ${res.status} (linked from ${from})`);
    else rep.ok('internal-links', 'link');
    if (priv && res.ok && res.status < 400) {
      const gated = authGatedTo(ctx, key, res.finalUrl);
      if (gated) rep.add('private-noindex', key, 'PASS', `auth-gated (redirects to ${gated})`);
      else analyzeNoindex(ctx, rep, key, res.text, res.headers, true);
    }
  });
  if (pending.length > capped.length) rep.add('internal-links', '-', 'SKIP', `checked ${capped.length} of ${pending.length} internal links`);
}

async function checkNotFound(ctx, rep) {
  const probe = `/__launch-check-${Math.random().toString(36).slice(2, 10)}`;
  const res = await request(ctx, `${ctx.baseOrigin}${probe}`);
  if (!res.ok) { rep.add('soft-404', probe, 'FAIL', describeError(res.error)); return; }
  const landedOn = normPath(new URL(res.finalUrl).pathname);
  if (res.status === 200 && landedOn !== probe) rep.add('soft-404', probe, 'FAIL', `unknown URL redirects to ${landedOn} (200); fix the middleware or redirect matcher so unknown paths reach the 404 page`);
  else if (res.status === 200) rep.add('soft-404', probe, 'FAIL', 'unknown URL returns 200 (soft 404): call notFound() so the status is a real 404');
  else if (res.status !== 404 && res.status !== 410) rep.add('soft-404', probe, 'FAIL', `unknown URL returns ${res.status}, expected 404`);
  else if (res.text.includes('This page could not be found.')) rep.add('soft-404', probe, 'WARN', 'real 404 status but the default Next.js 404 page: add app/not-found.tsx');
  else rep.add('soft-404', probe, 'PASS', `status ${res.status}`);
}

async function checkFavicon(ctx, rep, homeHtml, homeUrl) {
  let target = new URL('/favicon.ico', ctx.baseOrigin);
  const href = linkHref(homeHtml, 'icon');
  if (href) {
    try { target = rewrite(ctx, new URL(href, homeUrl)); } catch { rep.add('favicon', href, 'FAIL', 'invalid icon href'); return; }
  }
  const res = await getAsset(ctx, target.href);
  if (res.ok && res.status === 200) rep.add('favicon', target.pathname, 'PASS', 'loads');
  else rep.add('favicon', target.pathname, 'FAIL', res.ok ? `status ${res.status}` : describeError(res.error));
}

async function checkBrowser(ctx, rep, urls) {
  let chromium;
  try {
    const req = createRequire(path.join(process.cwd(), 'package.json'));
    let mod;
    try { mod = req('playwright'); } catch { mod = req('@playwright/test'); }
    chromium = mod.chromium;
  } catch {
    rep.add('browser', '-', 'SKIP', 'Playwright not found in this project (install playwright or @playwright/test)');
    return;
  }
  let browser;
  try { browser = await chromium.launch(); } catch (e) {
    rep.add('browser', '-', 'SKIP', `could not launch Chromium: ${describeError(e)} (try: npx playwright install chromium)`);
    return;
  }
  try {
    const context = await browser.newContext();
    if (Object.keys(ctx.headers).length) {
      // Extra headers only on requests that START same-origin. Playwright keeps them across the redirects
      // such a request follows, so a same-origin 3xx to another origin still carries them (see SKILL.md).
      await context.route('**/*', (route) => {
        const req = route.request();
        if (new URL(req.url()).origin === ctx.baseOrigin) route.continue({ headers: { ...req.headers(), ...ctx.headers } });
        else route.continue();
      });
    }
    const vercelOnly = (u) => {
      if (!ctx.isLocal || !u) return false;
      try { return new URL(u).pathname.startsWith('/_vercel/'); } catch { return false; }
    };
    let sawVercelOnly = false;
    for (const url of urls) {
      const page = await context.newPage();
      const label = new URL(url).pathname;
      const problems = [];
      page.on('pageerror', (e) => problems.push(['FAIL', `uncaught error: ${String(e.message).slice(0, 160)}`]));
      page.on('console', (msg) => {
        if (msg.type() !== 'error') return;
        const src = msg.location()?.url ?? '';
        const text = msg.text().slice(0, 160);
        if (vercelOnly(src)) { sawVercelOnly = true; return; }
        const thirdParty = src && !src.startsWith(ctx.baseOrigin);
        problems.push([thirdParty || text.includes('ERR_BLOCKED_BY_CLIENT') ? 'WARN' : 'FAIL', `console error: ${text}`]);
      });
      page.on('requestfailed', (req) => {
        const err = req.failure()?.errorText ?? '';
        if (vercelOnly(req.url())) { sawVercelOnly = true; return; }
        if (req.url().startsWith(ctx.baseOrigin) && !err.includes('ERR_ABORTED')) problems.push(['FAIL', `request failed: ${req.url().replace(ctx.baseOrigin, '')} (${err})`]);
      });
      page.on('response', (res) => {
        if (res.status() >= 400 && vercelOnly(res.url())) { sawVercelOnly = true; return; }
        if (res.url().startsWith(ctx.baseOrigin) && res.status() >= 400 && res.request().resourceType() !== 'document') problems.push(['FAIL', `${res.status()} ${res.url().replace(ctx.baseOrigin, '')}`]);
      });
      try {
        await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      } catch (e) {
        problems.push(['WARN', `navigation did not settle: ${describeError(e)}`]);
      }
      await page.close();
      if (!problems.length) rep.ok('browser');
      for (const [status, detail] of problems) rep.add('browser', label, status, detail);
    }
    if (sawVercelOnly) rep.add('browser-vercel-endpoints', '/_vercel/*', 'SKIP', 'Vercel-only endpoint (analytics / speed-insights), not served outside Vercel');
  } finally {
    await browser.close();
  }
}

async function checkLighthouse(ctx, rep) {
  const url = `${ctx.baseOrigin}/`;
  const scores = [];
  let lastError = '';
  // Headers go through a private temp file: argv is visible in `ps` and in error messages.
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'launch-check-'));
  try {
    const args = ['--yes', 'lighthouse', url, '--only-categories=performance', '--output=json', '--quiet', '--chrome-flags=--headless'];
    if (Object.keys(ctx.headers).length) {
      const headersFile = path.join(tmpDir, 'headers.json');
      fs.writeFileSync(headersFile, JSON.stringify(ctx.headers), { mode: 0o600 });
      args.push(`--extra-headers=${headersFile}`);
    }
    for (let i = 0; i < 3; i += 1) {
      try {
        const { stdout } = await execFileAsync('npx', args, { timeout: 180000, maxBuffer: 64 * 1024 * 1024 });
        const score = JSON.parse(stdout)?.categories?.performance?.score;
        if (typeof score === 'number') scores.push(Math.round(score * 100));
        else lastError = 'no performance score in output';
      } catch (e) {
        // Never echo e.message: it contains the full command line.
        lastError = e?.killed || e?.signal ? 'timeout' : `exit ${e?.code ?? 'unknown'}`;
      }
    }
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
  if (!scores.length) { rep.add('lighthouse', '/', 'SKIP', `could not run Lighthouse (${lastError}); try: npx lighthouse ${url}`); return; }
  scores.sort((a, b) => a - b);
  const median = scores[Math.floor(scores.length / 2)];
  const detail = `performance ${median} (median of ${scores.length}: ${scores.join(', ')})`;
  if (median < 90) rep.add('lighthouse', '/', ctx.isLocal ? 'WARN' : 'FAIL', `${detail}, target >= 90${ctx.isLocal ? ' (local machine, re-check on the preview)' : ''}`);
  else rep.add('lighthouse', '/', 'PASS', detail);
}

async function runLive(o) {
  const ctx = makeContext(o);
  const rep = new Report();

  if (ctx.basePath) rep.add('base-path', ctx.basePath, 'SKIP', 'only the origin of the base URL is crawled; a basePath is ignored');
  const home = await request(ctx, `${ctx.baseOrigin}/`);
  if (!home.ok) throw new ExitError(`cannot reach ${ctx.baseOrigin}: ${describeError(home.error)}`);
  if (home.status === 401 || home.status === 403) {
    throw new ExitError(`${ctx.baseOrigin}/ returned ${home.status}. The site is protected (Vercel Deployment Protection or basic auth). Re-run with --header 'x-vercel-protection-bypass: <value from an env var>' (never paste the secret into a PR or chat).`);
  }
  if (looksLikeNextDev(home.text)) throw new ExitError('this looks like `next dev` (dev chunks, no minified bundles). Run `npm run build && npx next start -p 3100` and point launch-check at that.');

  const robots = await checkRobots(ctx, rep);
  const paths = await collectSitemapUrls(ctx, rep, robots);

  const privateLiterals = o.privateGlobs.filter((g) => !g.includes('*')).map((g) => normPath(g.startsWith('/') ? g : `/${g}`));
  const sitemapPublic = paths.filter((p) => !ctx.isPrivate(p.split('?')[0]));
  const sitemapPrivate = [...new Set(paths.filter((p) => !sitemapPublic.includes(p)))];
  if (sitemapPrivate.length) rep.add('sitemap', '-', 'WARN', `${sitemapPrivate.length} private URL(s) listed in the sitemap: ${listCap(sitemapPrivate)}`);
  if (sitemapPublic.length > o.maxUrls) rep.add('sitemap', '-', 'SKIP', `crawling ${o.maxUrls} of ${sitemapPublic.length} sitemap URLs (--max-urls)`);
  const privateKeys = [...new Set([...sitemapPrivate, ...privateLiterals])].slice(0, o.maxUrls);
  const crawl = [...sitemapPublic.slice(0, o.maxUrls), ...privateKeys];

  const pages = await mapLimit(crawl, CONCURRENCY, async (key) => {
    const res = key === '/' ? home : await request(ctx, `${ctx.baseOrigin}${key}`);
    return { key, isPrivate: ctx.isPrivate(key.split('?')[0]), status: res.status, ok: res.ok, error: res.error, html: res.text, headers: res.headers, finalUrl: res.finalUrl };
  });

  const shared = { titles: new Map(), descriptions: new Map(), links: new Map(), seenScripts: new Set() };
  const okPages = [];
  for (const page of pages) {
    if (!page.ok) { rep.add('page-status', page.key, 'FAIL', describeError(page.error)); continue; }
    const expectGone = page.isPrivate && (page.status === 401 || page.status === 403);
    if (page.status !== 200 && !expectGone) {
      rep.add('page-status', page.key, page.isPrivate ? 'WARN' : 'FAIL', `status ${page.status}`);
      continue;
    }
    rep.ok('page-status');
    const gated = page.isPrivate && !expectGone ? authGatedTo(ctx, page.key, page.finalUrl) : null;
    if (gated) { rep.add('private-noindex', page.key, 'PASS', `auth-gated (redirects to ${gated})`); continue; }
    if (!expectGone) okPages.push(page);
  }
  await mapLimit(okPages, CONCURRENCY, (page) => analyzePage(ctx, rep, page, shared));
  if (ctx.noindexPages.length) {
    rep.add('noindex', `${ctx.noindexPages.length} page(s)`, 'WARN', `public pages are noindex (expected on previews, must not ship to prod): ${listCap(ctx.noindexPages, 5)}`);
  }
  reportDuplicates(rep, 'title-unique', shared.titles, 'title');
  reportDuplicates(rep, 'description-unique', shared.descriptions, 'description');

  await checkLinks(ctx, rep, new Set(pages.map((p) => p.key)), shared.links);
  await checkNotFound(ctx, rep);
  await checkFavicon(ctx, rep, home.text, home.finalUrl);
  if (o.browser) await checkBrowser(ctx, rep, okPages.map((p) => `${ctx.baseOrigin}${p.key}`));
  if (o.lighthouse) await checkLighthouse(ctx, rep);

  rep.finish();
  const prod = ctx.prodOrigin ? `, prod ${ctx.prodOrigin}${ctx.isProd ? ' (base IS prod)' : ''}` : '';
  return { rep, title: `launch-check live ${ctx.baseOrigin}${prod}, ${okPages.length} page(s)` };
}

// ---------------------------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------------------------

async function main() {
  try {
    const o = parseArgs(process.argv.slice(2));
    if (o.help) { console.log(HELP); return 0; }
    const { rep, title } = o.mode === 'static' ? runStatic(o) : await runLive(o);
    if (o.json) console.log(JSON.stringify({ title, summary: rep.counts(), rows: rep.rows }, null, 2));
    else console.log(renderMarkdown(rep, title));
    return rep.counts().FAIL > 0 ? 1 : 0;
  } catch (e) {
    if (e instanceof ExitError) {
      console.error(`launch-check: ${redact(e.message)}`);
      return e.exitCode;
    }
    console.error(`launch-check: unexpected error: ${redact(e?.stack ?? e)}`);
    return 2;
  }
}

process.exitCode = await main();
