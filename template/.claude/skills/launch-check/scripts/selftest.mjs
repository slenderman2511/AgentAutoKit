#!/usr/bin/env node
/**
 * Self-test for launch-check.mjs. Fixtures are generated at runtime in the OS temp dir and a local
 * node:http server plays the site, so nothing is committed that a project's tsc/ESLint/Tailwind
 * could pick up.
 *
 *   node skills/launch-check/scripts/selftest.mjs        (from the repo root)
 */
import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { randomBytes } from 'node:crypto';
import { chmodSync } from 'node:fs';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const CLI = path.join(path.dirname(fileURLToPath(import.meta.url)), 'launch-check.mjs');
const PROD = 'https://prod.example';
const EM = '—';

function run(args, env = process.env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [CLI, ...args], { stdio: ['ignore', 'pipe', 'pipe'], env });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d; });
    child.stderr.on('data', (d) => { stderr += d; });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

async function runJson(args, env) {
  const res = await run([...args, '--json'], env);
  let parsed = null;
  try { parsed = JSON.parse(res.stdout); } catch { /* exit 2 paths print to stderr */ }
  return { ...res, json: parsed, rows: parsed?.rows ?? [] };
}

const find = (rows, check, status) => rows.find((r) => r.check === check && (!status || r.status === status));
const dump = (res) => `exit ${res.code}\n${res.rows.map((r) => `${r.status} ${r.check} ${r.target} ${r.detail}`).join('\n')}\n${res.stderr}`;

async function writeTree(root, files) {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, content);
  }
}

// ---------------------------------------------------------------------------------------------
// static
// ---------------------------------------------------------------------------------------------

describe('static', () => {
  let dirty;
  let clean;
  let quiet;

  before(async () => {
    dirty = await fs.mkdtemp(path.join(os.tmpdir(), 'lc-dirty-'));
    clean = await fs.mkdtemp(path.join(os.tmpdir(), 'lc-clean-'));
    quiet = await fs.mkdtemp(path.join(os.tmpdir(), 'lc-quiet-'));
    await writeTree(dirty, {
      'app/page.tsx': 'export default function P() {\n  return <main><p>Lorem ipsum dolor sit amet</p><a href="#">More</a><p>© 2024 Acme Inc</p></main>;\n}\n',
      'app/layout.tsx': 'export const metadata = { title: "Create Next App" };\nexport default function L({ children }) { return <html><body>{children}</body></html>; }\n',
      'app/form.tsx': 'export const F = () => <input placeholder="Lorem ipsum" />;\nexport const G = () => <input placeholder={"Jane Doe"} />;\nexport const H = () => <input placeholder="you@example.com" />;\n',
      // Class names assembled from parts so a project's Tailwind scan never sees a literal utility.
      'app/hero.tsx': `export const Hero = () => <h1 className="${['bg', 'gradient', 'to', 'r'].join('-')} ${['from', 'purple', '500'].join('-')}">Hi</h1>;\n`,
      'next.config.mjs': 'export default { productionBrowserSourceMaps: true };\n',
      // `\/*` in a regex literal must not open a comment that swallows the rest of the file.
      'app/regex.ts': 'export const trim = (s) => s.replace(/\\/*$/, "");\nexport const t = "Lorem ipsum";\n/* end */\n',
      'public/next.svg': '<svg/>',
      'messages/en.json': JSON.stringify({ a: `Fast ${EM} simple`, b: `Cheap ${EM} reliable`, c: `Safe ${EM} sound`, d: `Free ${EM} forever` }),
      '.claude/skills/x/page.tsx': 'export const X = () => <p>Lorem ipsum</p>;\n',
      'app/page.test.tsx': 'it("x", () => { render(<p>Lorem ipsum</p>); });\n',
      '__tests__/y.tsx': 'export const Y = () => <a href="#">Lorem ipsum</a>;\n',
      'docs/guide.md': 'Lorem ipsum\n',
      'app/url.tsx': 'export const U = () => <a href="https://a.b/x">Lorem ipsum</a>;\n',
      'src/site.ts': 'export const SITE = "https://my-app.vercel.app";\n',
    });
    await writeTree(quiet, {
      'src/mocks/handlers.ts': 'export const text = "Lorem ipsum dolor";\n',
      'prisma/seed.ts': 'export const seed = { bio: "Lorem ipsum", name: "Jane Doe" };\n',
      'cypress/e2e/home.cy.ts': 'cy.contains("Lorem ipsum");\n',
      'app/page.tsx': '// TODO Lorem ipsum replace this copy\n/* Lorem ipsum\n   block comment, href="#" */\nexport default function P() {\n  const u = "https://example.test/path"; // Lorem ipsum in a trailing comment\n  return <main>{u}</main>;\n}\n',
    });
    await writeTree(clean, {
      'app/layout.tsx': 'export const metadata = { metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"), title: { template: "%s | Shop", default: "Shop" } };\nexport default function L({ children }) { return <html lang="vi"><body>{children}</body></html>; }\n',
      'app/page.tsx': 'export default function P() { return <main><h1>Cửa hàng</h1><input placeholder="you@example.com" /></main>; }\n',
      'app/sitemap.ts': 'export default function sitemap() { return []; }\n',
      'app/robots.ts': 'export default function robots() { return { rules: { userAgent: "*", allow: "/" } }; }\n',
      'app/not-found.tsx': 'export default function NotFound() { return <h1>Không tìm thấy</h1>; }\n',
      'app/icon.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>',
      'app/error.tsx': 'export default function E() { return <p>Lỗi</p>; }\n',
    });
  });

  after(async () => {
    await fs.rm(dirty, { recursive: true, force: true });
    await fs.rm(clean, { recursive: true, force: true });
    await fs.rm(quiet, { recursive: true, force: true });
  });

  it('flags a dirty project with exit 1 and the expected rows', async () => {
    const res = await runJson(['static', dirty]);
    assert.equal(res.code, 1, dump(res));
    for (const check of ['lorem-ipsum', 'create-next-app', 'source-maps-config', 'href-hash']) {
      assert.ok(find(res.rows, check, 'FAIL'), `expected FAIL ${check}\n${dump(res)}`);
    }
    for (const check of ['default-assets', 'em-dash', 'placeholder-names', 'hardcoded-copyright', 'purple-gradient', 'sitemap', 'robots', 'not-found', 'icon', 'metadataBase', 'html-lang', 'error-page', 'vercel-app-hardcoded']) {
      assert.ok(find(res.rows, check, 'WARN'), `expected WARN ${check}\n${dump(res)}`);
    }
    assert.match(find(res.rows, 'lorem-ipsum').detail, /app\/page\.tsx:2/);
    assert.match(find(res.rows, 'em-dash').detail, /messages\/en\.json/);
  });

  it('does not FAIL on mocks, seeds, cypress or comments, but still sees code after a URL string', async () => {
    const res = await runJson(['static', quiet]);
    assert.equal(res.json.summary.FAIL, 0, dump(res));
    assert.ok(find(res.rows, 'lorem-ipsum', 'PASS'), dump(res));
    assert.ok(find(res.rows, 'placeholder-names', 'PASS'), dump(res));
    const dirtyRes = await runJson(['static', dirty]);
    assert.match(find(dirtyRes.rows, 'lorem-ipsum').detail, /app\/url\.tsx:1/);
    assert.match(find(dirtyRes.rows, 'lorem-ipsum').detail, /app\/regex\.ts:2/);
  });

  it('downgrades the next.config source map FAIL to WARN with --public-maps', async () => {
    const res = await runJson(['static', dirty, '--public-maps']);
    assert.ok(find(res.rows, 'source-maps-config', 'WARN'), dump(res));
    assert.ok(!find(res.rows, 'source-maps-config', 'FAIL'), dump(res));
  });

  it('ignores placeholder attributes, .claude, tests, __tests__ and markdown', async () => {
    const res = await runJson(['static', dirty]);
    const lorem = find(res.rows, 'lorem-ipsum').detail;
    assert.doesNotMatch(lorem, /form\.tsx/, 'placeholder values must be stripped');
    assert.doesNotMatch(lorem, /\.claude|page\.test|__tests__|guide\.md/);
    assert.doesNotMatch(find(res.rows, 'placeholder-names').detail, /form\.tsx/);
    assert.doesNotMatch(find(res.rows, 'href-hash').detail, /__tests__/);
  });

  it('passes a clean project with exit 0 and no warnings', async () => {
    const res = await runJson(['static', clean]);
    assert.equal(res.code, 0, dump(res));
    assert.equal(res.json.summary.FAIL, 0, dump(res));
    assert.equal(res.json.summary.WARN, 0, dump(res));
  });

  it('prints a markdown table with a summary header', async () => {
    const res = await run(['static', dirty]);
    assert.match(res.stdout, /\*\*\d+ FAIL · \d+ WARN · \d+ SKIP · \d+ PASS\*\*/);
    assert.match(res.stdout, /\| Status \| Check \| Target \| Detail \|/);
  });

  it('exits 2 on usage errors', async () => {
    assert.equal((await run([])).code, 2);
    assert.equal((await run(['static'])).code, 2);
    assert.equal((await run(['static', path.join(dirty, 'nope')])).code, 2);
    assert.equal((await run(['static', dirty, '--bogus'])).code, 2);
    assert.equal((await run(['--help'])).code, 0);
  });
});

// ---------------------------------------------------------------------------------------------
// live
// ---------------------------------------------------------------------------------------------

const SECRET = 's3cr3t-token-value';
const GOOD_LIKE = new Set(['good', 'leak', 'nositemap', 'mw', 'noindex']);

function htmlPage({ title, description, canonical, ogImage = `${PROD}/og.png`, icon = '/icon.svg', lang = 'en', body, extraHead = '' }) {
  const head = [
    title === null ? '' : `<title>${title}</title>`,
    description ? `<meta name="description" content="${description}">` : '',
    canonical ? `<link rel="canonical" href="${canonical}">` : '',
    canonical ? `<meta property="og:url" content="${canonical}">` : '',
    ogImage ? `<meta property="og:image" content="${ogImage}">` : '',
    `<meta property="og:title" content="${title ?? ''}">`,
    description ? `<meta property="og:description" content="${description}">` : '',
    `<link rel="icon" href="${icon}">`,
    extraHead,
  ].join('\n');
  return `<!doctype html><html${lang ? ` lang="${lang}"` : ''}><head>${head}</head><body>${body}<script src="/_next/static/chunks/app.js" async></script><script src="/_vercel/insights/script.js" defer></script></body></html>`;
}

/** A second origin (another port): must never receive the --header value. */
function startOther() {
  const seen = [];
  const server = createServer((req, res) => {
    seen.push({ path: req.url, hasSecret: Object.values(req.headers).some((v) => String(v).includes(SECRET)) });
    if (req.url === '/landing') { res.writeHead(200, { 'content-type': 'text/html' }); res.end('<!doctype html><title>Landing</title>'); return; }
    res.writeHead(200, { 'content-type': req.url === '/icon.svg' ? 'image/svg+xml' : 'image/png' });
    res.end(req.url === '/icon.svg' ? '<svg xmlns="http://www.w3.org/2000/svg"/>' : Buffer.from('89504e470d0a1a0a', 'hex'));
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve({ server, seen, origin: `http://127.0.0.1:${server.address().port}` }));
  });
}

function startSite(variant, { otherOrigin = '', baseSeen = [] } = {}) {
  const noise = randomBytes(6000).toString('base64');
  const good = GOOD_LIKE.has(variant);
  const homeTitle = variant === 'leak' ? `Home ${SECRET}` : 'Home | Shop';
  const aboutTitle = variant === 'leak' ? `Home ${SECRET}` : 'About | Shop';
  const noindexHead = variant === 'noindex' ? '<meta name="robots" content="noindex">' : '';
  const server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    baseSeen.push({ path: url.pathname, hasSecret: Object.values(req.headers).some((v) => String(v).includes(SECRET)) });
    const send = (status, type, body, extra = {}) => { res.writeHead(status, { 'content-type': type, ...extra }); res.end(body); };
    if (variant === 'protected') return send(401, 'text/plain', 'Authentication Required');
    switch (url.pathname) {
      case '/robots.txt':
        if (variant === 'nositemap') return send(200, 'text/plain', 'User-agent: *\nAllow: /\n');
        return send(200, 'text/plain', good ? `User-agent: *\nAllow: /\nSitemap: ${PROD}/sitemap.xml\n` : `User-agent: *\nDisallow: /\nSitemap: ${PROD}/sitemap.xml\n`);
      case '/sitemap.xml':
        if (variant === 'nositemap') return send(404, 'text/plain', 'nope');
        return send(200, 'application/xml', `<?xml version="1.0"?><urlset><url><loc>${PROD}/</loc></url><url><loc>${PROD}/about</loc></url></urlset>`);
      case '/':
        if (variant === 'dev') return send(200, 'text/html', '<!doctype html><html lang="en"><script src="/_next/static/chunks/%5Bturbopack%5D_browser_dev_hmr-client.js"></script></html>');
        return send(200, 'text/html', htmlPage(good
          ? {
            title: homeTitle,
            description: 'Welcome to the shop',
            canonical: `${PROD}/`,
            ogImage: variant === 'leak' ? `${otherOrigin}/og.png` : `${PROD}/og.png`,
            icon: variant === 'leak' ? `${otherOrigin}/icon.svg` : '/icon.svg',
            extraHead: noindexHead,
            body: `<h1>Home</h1><img src="/og.png" alt="Shop front"><img src="/deco.png" alt=""><a href="/about">About us</a><a href="https://other.example/x">Elsewhere</a>${variant === 'leak' ? '<a href="/jump">Jump</a>' : ''}`,
          }
          : { title: 'Same Title', description: 'Welcome', canonical: `${PROD}/`, ogImage: null, body: '<h1>Home</h1><img src="/og.png"><a href="/about">About</a><a href="/missing">Broken</a>', extraHead: '<script type="application/ld+json">{ not json</script>' }));
      case '/about':
        return send(200, 'text/html', htmlPage(good
          ? { title: aboutTitle, description: 'Who we are &#99999999; &#xFFFFFFFF; &amp; more', canonical: `${PROD}/about`, extraHead: noindexHead, body: '<h1>About</h1><a href="/">Home</a>' }
          : { title: 'Same Title', description: '', canonical: `${PROD}/about`, body: '<h1>About</h1>' }));
      case '/jump':
        return send(302, 'text/plain', '', { location: `${otherOrigin}/landing` });
      case '/dashboard':
        return send(302, 'text/plain', '', { location: '/login' });
      case '/login':
        return send(200, 'text/html', htmlPage({ title: 'Log in', description: 'Sign in', canonical: `${PROD}/login`, body: '<h1>Log in</h1>' }));
      case '/og.png':
      case '/deco.png':
        return send(200, 'image/png', Buffer.from('89504e470d0a1a0a', 'hex'));
      case '/icon.svg':
        return send(200, 'image/svg+xml', '<svg xmlns="http://www.w3.org/2000/svg"/>');
      case '/_next/static/chunks/app.js':
        return send(200, 'text/javascript', good ? 'console.log("ok");\n' : `var a="${noise}";\n//# sourceMappingURL=app.js.map\n`);
      case '/_next/static/chunks/app.js.map':
        if (good) return send(404, 'text/plain', 'not found');
        return send(200, 'application/json', '{"version":3,"sources":[],"names":[],"mappings":""}');
      default:
        if (variant === 'mw') return send(302, 'text/plain', '', { location: '/' });
        // good: real 404. bad: soft 404 (HTTP 200 for unknown URLs), but known-missing links still 404.
        if (good || url.pathname === '/missing') return send(404, 'text/html', '<!doctype html><html lang="en"><title>Not found</title><h1>Nothing here</h1></html>');
        return send(200, 'text/html', '<!doctype html><html lang="en"><title>Not found</title><h1>Nothing here</h1></html>');
    }
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve({ server, origin: `http://127.0.0.1:${server.address().port}` }));
  });
}

const closeServer = (s) => new Promise((resolve) => { s.server.close(resolve); s.server.closeAllConnections(); });

describe('live', () => {
  const sites = {};
  let other;
  const leakSeen = [];
  let tmp;

  before(async () => {
    other = await startOther();
    for (const variant of ['good', 'bad', 'protected', 'nositemap', 'mw', 'noindex', 'dev']) sites[variant] = await startSite(variant);
    sites.leak = await startSite('leak', { otherOrigin: other.origin, baseSeen: leakSeen });
    tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'lc-bin-'));
  });

  after(async () => {
    await Promise.all([...Object.values(sites), other].map(closeServer));
    await fs.rm(tmp, { recursive: true, force: true });
  });

  it('passes a good site (prod origin rewritten to the local base) with exit 0', async () => {
    const res = await runJson(['live', sites.good.origin, '--prod-url', PROD]);
    assert.equal(res.code, 0, dump(res));
    assert.equal(res.json.summary.FAIL, 0, dump(res));
    assert.equal(res.json.summary.WARN, 0, dump(res));
    assert.match(res.json.title, /2 page\(s\)/, 'both sitemap URLs must be crawled after rewriting');
    for (const check of ['robots.txt', 'sitemap', 'canonical', 'og:image', 'og:url', 'img-alt', 'soft-404', 'favicon', 'js-budget', 'js-assets', 'title-unique']) {
      assert.ok(find(res.rows, check, 'PASS'), `expected PASS ${check}\n${dump(res)}`);
    }
  });

  it('survives out-of-range numeric entities in HTML', async () => {
    const res = await run(['live', sites.good.origin, '--prod-url', PROD, '--json']);
    assert.notEqual(res.code, 2, `crashed:\n${res.stderr}`);
    assert.doesNotMatch(res.stderr, /RangeError/);
  });

  it('fails a bad site with the expected FAIL rows, and Disallow: / is only a WARN off prod', async () => {
    const res = await runJson(['live', sites.bad.origin, '--prod-url', PROD, '--budget-kb', '4']);
    assert.equal(res.code, 1, dump(res));
    for (const check of ['soft-404', 'og:image', 'img-alt', 'json-ld', 'internal-links', 'source-maps', 'description', 'js-budget']) {
      assert.ok(find(res.rows, check, 'FAIL'), `expected FAIL ${check}\n${dump(res)}`);
    }
    assert.ok(find(res.rows, 'title-unique', 'WARN'), dump(res));
    assert.ok(find(res.rows, 'robots.txt', 'WARN'), dump(res));
    assert.ok(!find(res.rows, 'robots.txt', 'FAIL'), 'Disallow: / must not FAIL when base is not prod');
    assert.match(find(res.rows, 'internal-links', 'FAIL').target, /\/missing/);
    assert.match(find(res.rows, 'js-budget', 'FAIL').detail, /estimate/);
  });

  it('still analyzes "/" when the sitemap is missing', async () => {
    const res = await runJson(['live', sites.nositemap.origin, '--prod-url', PROD]);
    assert.equal(res.code, 1, dump(res));
    assert.ok(find(res.rows, 'sitemap', 'FAIL'), dump(res));
    assert.match(res.json.title, /1 page\(s\)/, dump(res));
    assert.ok(find(res.rows, 'title', 'PASS'), dump(res));
    assert.ok(find(res.rows, 'canonical', 'PASS'), dump(res));
  });

  it('reports a redirect-to-home catch-all as a failed 404 without suggesting notFound()', async () => {
    const res = await runJson(['live', sites.mw.origin, '--prod-url', PROD]);
    const row = find(res.rows, 'soft-404', 'FAIL');
    assert.ok(row, dump(res));
    assert.match(row.detail, /redirects to \/ \(200\)/);
    assert.match(row.detail, /middleware/);
    assert.doesNotMatch(row.detail, /notFound\(\)/);
  });

  it('treats a private path that redirects to a public page as auth-gated', async () => {
    const res = await runJson(['live', sites.good.origin, '--prod-url', PROD, '--private', '/dashboard']);
    const row = find(res.rows, 'private-noindex', 'PASS');
    assert.ok(row, dump(res));
    assert.match(row.detail, /auth-gated \(redirects to \/login\)/);
    assert.ok(!find(res.rows, 'private-noindex', 'WARN'), dump(res));
  });

  it('aggregates noindex WARNs on a non-prod origin into one row', async () => {
    const res = await runJson(['live', sites.noindex.origin, '--prod-url', PROD]);
    const rows = res.rows.filter((r) => r.check === 'noindex');
    assert.equal(rows.length, 1, dump(res));
    assert.equal(rows[0].status, 'WARN');
    assert.match(rows[0].target, /2 page\(s\)/);
    assert.equal(res.code, 0, dump(res));
  });

  it('refuses a Turbopack dev server (exit 2)', async () => {
    const res = await run(['live', sites.dev.origin, '--json']);
    assert.equal(res.code, 2, res.stderr);
    assert.match(res.stderr, /next dev/);
  });

  it('downgrades public source maps to WARN with --public-maps', async () => {
    const res = await runJson(['live', sites.bad.origin, '--prod-url', PROD, '--public-maps']);
    assert.ok(find(res.rows, 'source-maps', 'WARN'), dump(res));
    assert.ok(!find(res.rows, 'source-maps', 'FAIL'), dump(res));
  });

  it('fails Disallow: / when the base origin is the production origin', async () => {
    const res = await runJson(['live', sites.bad.origin, '--prod-url', sites.bad.origin]);
    assert.ok(find(res.rows, 'robots.txt', 'FAIL'), dump(res));
    assert.equal(res.code, 1);
  });

  it('sends --header only to the base origin and redacts its value from every row', async () => {
    const res = await runJson(['live', sites.leak.origin, '--prod-url', PROD, '--header', `x-launch-secret: ${SECRET}`]);
    assert.equal(res.code, 0, dump(res));
    assert.ok(leakSeen.some((r) => r.path === '/' && r.hasSecret), 'the base origin must receive the header');
    for (const wanted of ['/og.png', '/icon.svg', '/landing']) {
      assert.ok(other.seen.some((r) => r.path === wanted), `the other origin should be hit for ${wanted} (og:image, favicon, redirect)`);
    }
    assert.deepEqual(other.seen.filter((r) => r.hasSecret), [], 'the header leaked to another origin');
    const dup = find(res.rows, 'title-unique', 'WARN');
    assert.ok(dup, dump(res));
    assert.match(dup.detail, /\*\*\*/);
    assert.doesNotMatch(`${res.stdout}${res.stderr}`, new RegExp(SECRET));
  });

  it('keeps the --header value out of Lighthouse argv and error rows (fake npx)', async () => {
    const bin = path.join(tmp, 'bin');
    const log = path.join(tmp, 'npx.log');
    await fs.mkdir(bin);
    await fs.writeFile(path.join(bin, 'npx'), [
      '#!/usr/bin/env node',
      "const fs = require('node:fs');",
      'const args = process.argv.slice(2);',
      "const arg = args.find((a) => a.startsWith('--extra-headers='));",
      "const file = arg ? arg.slice(arg.indexOf('=') + 1) : null;",
      'const entry = { args, file, content: file && fs.existsSync(file) ? fs.readFileSync(file, "utf8") : null, mode: file && fs.existsSync(file) ? fs.statSync(file).mode & 0o777 : null };',
      "fs.appendFileSync(process.env.FAKE_NPX_LOG, JSON.stringify(entry) + '\\n');",
      "process.stderr.write('lighthouse failed: ' + args.join(' '));",
      'process.exit(3);',
    ].join('\n'));
    chmodSync(path.join(bin, 'npx'), 0o755);
    const env = { ...process.env, PATH: `${bin}${path.delimiter}${process.env.PATH}`, FAKE_NPX_LOG: log };
    const res = await runJson(['live', sites.good.origin, '--prod-url', PROD, '--lighthouse', '--header', `x-launch-secret: ${SECRET}`], env);
    const row = find(res.rows, 'lighthouse', 'SKIP');
    assert.ok(row, dump(res));
    assert.doesNotMatch(`${res.stdout}${res.stderr}`, new RegExp(SECRET));
    const entries = (await fs.readFile(log, 'utf8')).trim().split('\n').map((l) => JSON.parse(l));
    assert.equal(entries.length, 3);
    for (const e of entries) {
      assert.ok(!e.args.join(' ').includes(SECRET), 'secret must not be in argv');
      assert.ok(e.file, 'headers are passed as a file path');
      assert.ok(e.content.includes(SECRET), 'the file carries the header for lighthouse');
      assert.equal(e.mode, 0o600);
    }
    await assert.rejects(fs.access(entries[0].file), 'the temp headers file must be deleted afterwards');
  });

  it('exits 2 with a --header hint on 401', async () => {
    const res = await run(['live', sites.protected.origin, '--json']);
    assert.equal(res.code, 2, `${res.stdout}\n${res.stderr}`);
    assert.match(res.stderr, /--header/);
  });

  it('exits 2 when the base is unreachable', async () => {
    const res = await run(['live', 'http://127.0.0.1:1', '--json']);
    assert.equal(res.code, 2, res.stderr);
  });

  it('does not echo a malformed --header value', async () => {
    const res = await run(['live', sites.good.origin, '--header', `Bearer-${SECRET}`]);
    assert.equal(res.code, 2);
    assert.doesNotMatch(res.stderr, new RegExp(SECRET));
  });

  it('prints a markdown table sorted FAIL first', async () => {
    const res = await run(['live', sites.bad.origin, '--prod-url', PROD]);
    const firstRow = res.stdout.split('\n').find((l) => /^\| (FAIL|WARN|SKIP|PASS) \|/.test(l));
    assert.match(firstRow, /^\| FAIL \|/);
  });
});
