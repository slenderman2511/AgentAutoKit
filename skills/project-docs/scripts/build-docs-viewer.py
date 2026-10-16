#!/usr/bin/env python3
"""Bundle a project's docs/*.md into ONE self-contained HTML viewer.

Usage:
  build-docs-viewer.py [DOCS_DIR] [-o OUT.html] [--title "My App Docs"]
  build-docs-viewer.py [DOCS_DIR] --check        # report status + open placeholders, no HTML
  build-docs-viewer.py [DOCS_DIR] -o page.html --artifact   # omit doctype/head tags (Claude Artifact wraps them)

--check gates only the eight standard docs: exit 0 when all exist, are `status: done` and have no
open placeholder; extra docs are listed for information.

DOCS_DIR defaults to ./docs. The eight standard docs come first in a fixed order
(PRD, DESIGN_SYSTEM, ARCHITECTURE, DATABASE, SECURITY, CODE_STYLE, TESTING, AGENTS);
any other *.md in the folder follows alphabetically. Each file may start with a
front-matter block (title, summary, status: draft|review|done, owner, updated).

The HTML embeds the markdown and renders it in the browser (marked + mermaid from
cdnjs), so it opens from disk, a static host, or a Claude Artifact. Read-only.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

ORDER = ["PRD", "DESIGN_SYSTEM", "ARCHITECTURE", "DATABASE", "SECURITY", "CODE_STYLE", "TESTING", "AGENTS"]
PLACEHOLDER = re.compile(r"<[^<>\n`]{1,80}>|&lt;[^&\n]{1,80}&gt;|#_{6}")
NOT_PLACEHOLDER = re.compile(r"^(<|&lt;)(br\b|/?(https?|mailto):|[^\s>&]+@)", re.I)
FENCE = re.compile(r"```([\w-]*)\n(.*?)```", re.S)
PROSE_FENCES = {"", "text", "txt", "mermaid"}  # their <…> are placeholders; other languages hold real code


def holes(text):
    return [h for h in PLACEHOLDER.findall(text) if not NOT_PLACEHOLDER.match(h)]


def parse(path):
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("'\"")
    prose = FENCE.sub(lambda f: f.group(2) if f.group(1).lower() in PROSE_FENCES else "", body)
    open_holes = holes(prose) + (holes(m.group(1)) if m else [])
    return {
        "file": path.name,
        "id": re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-"),
        "title": meta.get("title") or path.stem.replace("_", " ").title(),
        "summary": meta.get("summary", ""),
        "status": meta.get("status", "draft").lower(),
        "owner": meta.get("owner", ""),
        "updated": meta.get("updated", ""),
        "placeholders": len(open_holes),
        "core": path.stem.upper() in ORDER,
        "body": body,
    }


def collect(docs_dir):
    files = {p.stem.upper(): p for p in sorted(docs_dir.glob("*.md"))}
    ordered = [files.pop(k) for k in ORDER if k in files]
    ordered += [files[k] for k in sorted(files) if files[k].name.lower() not in ("readme.md",)]
    return [parse(p) for p in ordered]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docs", nargs="?", default="docs")
    ap.add_argument("-o", "--out")
    ap.add_argument("--title")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--artifact", action="store_true", help="omit doctype/meta (the Artifact host adds them)")
    a = ap.parse_args()

    docs_dir = Path(a.docs)
    if not docs_dir.is_dir():
        print(f"not a directory: {docs_dir}", file=sys.stderr)
        return 2
    docs = collect(docs_dir)
    if not docs:
        print(f"no *.md files in {docs_dir}", file=sys.stderr)
        return 2

    if a.check:
        core = [d for d in docs if d["core"]]
        ready = [d for d in core if d["status"] == "done" and not d["placeholders"]]
        print(f"{len(ready)}/{len(ORDER)} standard docs done")
        for d in docs:
            if d["core"]:
                flag = "" if d in ready else "  ← open"
            else:
                flag = "  (extra, not gated)"
            print(f"  {d['file']:<20} {d['status']:<7} placeholders={d['placeholders']}{flag}")
        missing = [k for k in ORDER if k not in {d['file'][:-3].upper() for d in core}]
        if missing:
            print("missing: " + ", ".join(f"{k}.md" for k in missing))
        return 0 if len(ready) == len(ORDER) else 1

    project = a.title or f"{docs_dir.resolve().parent.name} docs"
    out = Path(a.out) if a.out else docs_dir / "index.html"
    # "<" → \u003c keeps "</script>" and "<!--" in any doc from ending or confusing the <script> block.
    payload = json.dumps(docs, ensure_ascii=False).replace("<", "\\u003c")
    head = "" if a.artifact else HEAD
    page = head + TEMPLATE.replace("__TITLE__", html.escape(project)).replace("__DATA__", payload)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(docs)} docs, {out.stat().st_size // 1024} KB)")
    return 0


HEAD = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
"""

TEMPLATE = r"""<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* Layout: a drafting-table reader — file tree with completion state on the left, one document on a sheet on the right. */
:root {
  --bg: #eef2f5; --sheet: #ffffff; --ink: #17202b; --muted: #5a6676; --line: #d9e0e7;
  --accent: #1d6a86; --accent-soft: #e2f0f5; --ph-ink: #8a4f00; --ph-bg: #fff2d6; --ok: #1d7a4c; --code-bg: #f4f6f8;
  --f-display: "Manrope", "Segoe UI", system-ui, sans-serif;
  --f-body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --f-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0e1319; --sheet: #151c25; --ink: #e4e9ef; --muted: #93a0b0; --line: #26313e;
  --accent: #62b9d3; --accent-soft: #14303b; --ph-ink: #f1c46a; --ph-bg: #2d2412; --ok: #4fc38b; --code-bg: #1b232e; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0e1319; --sheet: #151c25; --ink: #e4e9ef; --muted: #93a0b0; --line: #26313e;
  --accent: #62b9d3; --accent-soft: #14303b; --ph-ink: #f1c46a; --ph-bg: #2d2412; --ok: #4fc38b; --code-bg: #1b232e; color-scheme: dark }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 16px/1.6 var(--f-body); }
.app { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 24px; max-width: 1240px; margin: 0 auto; padding-block: 24px; padding-inline: 16px; }
aside { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 16px); align-self: start; display: grid; gap: 16px; }
.brand { font: 800 15px/1.2 var(--f-display); letter-spacing: .02em; }
.brand small { display: block; font: 400 13px var(--f-mono); color: var(--muted); margin-top: 4px; }
.tree { display: grid; gap: 2px; font: 13px/1.4 var(--f-mono); }
.tree .dir { color: var(--muted); padding: 4px 8px; }
.tree a { display: grid; grid-template-columns: 14px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 6px 8px 6px 20px; border-radius: 6px; color: var(--ink); text-decoration: none; }
.tree a:hover { background: var(--accent-soft); }
.tree a[aria-current="page"] { background: var(--accent-soft); color: var(--accent); font-weight: 500; }
.tree a:focus-visible, .toc a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.dot { width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--muted); }
.dot.done { background: var(--ok); border-color: var(--ok); }
.dot.review { border-color: var(--accent); background: linear-gradient(90deg, var(--accent) 50%, transparent 50%); }
.count { font-size: 11px; color: var(--ph-ink); background: var(--ph-bg); border-radius: 999px; padding: 0 7px; }
.progress { display: grid; gap: 6px; font: 12px var(--f-mono); color: var(--muted); }
.bar { height: 6px; border-radius: 999px; background: var(--line); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--ok); }
.sheet { background: var(--sheet); border: 1px solid var(--line); border-radius: 12px; padding: clamp(20px, 4vw, 48px); min-width: 0; }
.path { font: 12px var(--f-mono); color: var(--muted); display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.pill { font: 600 11px/1 var(--f-mono); text-transform: uppercase; letter-spacing: .06em; padding: 5px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); }
.pill.done { color: var(--ok); border-color: currentColor; }
.pill.review { color: var(--accent); border-color: currentColor; }
h1 { font: 800 clamp(28px, 4vw, 40px)/1.15 var(--f-display); margin: 16px 0 8px; text-wrap: balance; letter-spacing: -.01em; }
.lede { color: var(--muted); font-size: 18px; max-width: 62ch; margin: 0; }
.meta { font: 12px var(--f-mono); color: var(--muted); margin-top: 12px; }
.toc { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 24px 0 8px; padding-top: 16px; border-top: 1px solid var(--line); font: 13px var(--f-body); }
.toc a { color: var(--muted); text-decoration: none; }
.toc a:hover { color: var(--accent); }
.toc b { font: 500 12px var(--f-mono); color: var(--accent); margin-right: 4px; }
section.part { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 0 16px; padding-top: 32px; margin-top: 32px; border-top: 1px solid var(--line); }
section.part:first-of-type { border-top: 0; margin-top: 8px; }
.num { font: 500 13px var(--f-mono); color: var(--accent); padding-top: 6px; }
.part h2 { font: 700 22px/1.3 var(--f-display); margin: 0; text-wrap: balance; }
.part .sub { color: var(--muted); margin: 4px 0 16px; font-style: normal; }
.part-body { min-width: 0; }
.part-body > :last-child { margin-bottom: 0; }
p, li { max-width: 72ch; }
a { color: var(--accent); }
.tbl { overflow-x: auto; margin: 16px 0; border: 1px solid var(--line); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font: 600 11px/1.4 var(--f-mono); text-transform: uppercase; letter-spacing: .06em; color: var(--muted); background: var(--code-bg); }
tr:last-child td { border-bottom: 0; }
code { font: 13px var(--f-mono); background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }
pre { background: var(--code-bg); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; overflow-x: auto; font: 13px/1.55 var(--f-mono); }
pre code { background: none; padding: 0; }
td code { white-space: nowrap; }
pre.mermaid { background: var(--sheet); text-align: center; }
blockquote { margin: 16px 0; padding: 14px 18px; border-radius: 8px; background: var(--accent-soft); color: var(--ink); }
blockquote p { margin: 0; }
ul.contains-task-list, ul:has(> li > input[type=checkbox]) { list-style: none; padding-left: 4px; }
li > input[type=checkbox] { accent-color: var(--ok); margin-right: 8px; transform: translateY(1px); }
.ph { color: var(--ph-ink); background: var(--ph-bg); border-radius: 4px; padding: 0 4px; font: 13px var(--f-mono); }
@media (max-width: 820px) {
  .app { grid-template-columns: minmax(0, 1fr); }
  aside { position: static; }
  .tree { grid-auto-flow: column; grid-auto-columns: max-content; overflow-x: auto; padding-bottom: 4px; }
  .tree .dir { display: none; }
  .tree a { padding-left: 8px; }
  section.part { grid-template-columns: minmax(0, 1fr); }
  .num { padding: 0 0 4px; }
}
@media (prefers-reduced-motion: no-preference) { .tree a { transition: background .15s } }
</style>

<div class="app">
  <aside>
    <div class="brand">__TITLE__<small id="files-count"></small></div>
    <div class="progress"><span id="progress-label"></span><div class="bar"><i id="progress-bar"></i></div></div>
    <nav class="tree" id="tree" aria-label="Documents"><div class="dir">docs/</div></nav>
  </aside>
  <main class="sheet" id="sheet"></main>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.8/mermaid.min.js"></script>
<script>
const DOCS = __DATA__;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// Raw HTML in the markdown is shown as text, so "<placeholder>" stays visible and nothing executes.
marked.use({ gfm: true, renderer: { html(token) { return esc(typeof token === "string" ? token : token.text); } } });
const dark = () => document.documentElement.dataset.theme === "dark" ||
  (document.documentElement.dataset.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);

function markPlaceholders(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.parentElement.closest("pre") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  const rx = /(<(?!br\b|\/?(?:https?|mailto):|[^\s>]+@)[^<>\n]{1,80}>|#_{6})/gi;
  for (const n of nodes) {
    if (!rx.test(n.data)) continue; rx.lastIndex = 0;
    const frag = document.createDocumentFragment(); let last = 0;
    n.data.replace(rx, (m, _g, i) => { frag.append(n.data.slice(last, i));
      const s = document.createElement("span"); s.className = "ph"; s.textContent = m; frag.append(s); last = i + m.length; });
    frag.append(n.data.slice(last)); n.replaceWith(frag);
  }
}

function render(doc) {
  const sheet = document.getElementById("sheet");
  const tmp = document.createElement("div");
  tmp.innerHTML = marked.parse(doc.body);
  tmp.querySelectorAll("a[href]").forEach(a => { if (!/^(https?:|mailto:|#|\.{0,2}\/|[\w.-]+(\/|\.md|$))/i.test(a.getAttribute("href"))) a.removeAttribute("href"); });
  tmp.querySelectorAll("table").forEach(t => { const w = document.createElement("div"); w.className = "tbl"; t.replaceWith(w); w.append(t); });
  tmp.querySelectorAll("pre > code.language-mermaid").forEach(c => { const p = document.createElement("pre"); p.className = "mermaid"; p.textContent = c.textContent; c.parentElement.replaceWith(p); });
  // Group content under each "## NN · Title" into a numbered part.
  const parts = []; let cur = null; const intro = document.createElement("div");
  for (const el of [...tmp.childNodes]) {
    if (el.nodeName === "H2") {
      const m = el.textContent.match(/^\s*(\d{1,2})\s*[·.\-—:]\s*(.+)$/);
      cur = { num: m ? m[1].padStart(2, "0") : "", title: m ? m[2] : el.textContent, nodes: [] }; parts.push(cur);
    } else if (cur) cur.nodes.push(el); else intro.append(el);
  }
  const statusLabel = { done: "done", review: "in review" }[doc.status] || "draft";
  sheet.innerHTML = `
    <div class="path"><span>docs / ${esc(doc.file)}</span><span class="pill ${esc(doc.status)}">${statusLabel}</span>
      ${doc.placeholders ? `<span class="count">${doc.placeholders} to fill</span>` : ""}</div>
    <h1>${esc(doc.title)}</h1>${doc.summary ? `<p class="lede">${esc(doc.summary)}</p>` : ""}
    <div class="meta">${[doc.owner && "owner " + doc.owner, doc.updated && "updated " + doc.updated].filter(Boolean).map(esc).join(" · ")}</div>
    ${parts.length ? `<nav class="toc" aria-label="Sections">${parts.map((p, i) => `<a href="#${doc.id}--${i + 1}"><b>${esc(p.num)}</b>${esc(p.title)}</a>`).join("")}</nav>` : ""}`;
  if (intro.childNodes.length) sheet.append(intro);
  parts.forEach((p, i) => {
    const s = document.createElement("section"); s.className = "part"; s.id = `${doc.id}--${i + 1}`;
    const body = document.createElement("div"); body.className = "part-body";
    const h = document.createElement("h2"); h.textContent = p.title; body.append(h);
    const nodes = p.nodes.filter(n => !(n.nodeType === 3 && !n.data.trim()));
    if (nodes[0] && nodes[0].nodeName === "P" && nodes[0].children.length === 1 && nodes[0].firstElementChild.nodeName === "EM" && nodes[0].textContent.trim() === nodes[0].firstElementChild.textContent.trim()) {
      const sub = document.createElement("p"); sub.className = "sub"; sub.textContent = nodes.shift().textContent; body.append(sub); }
    nodes.forEach(n => body.append(n));
    s.innerHTML = `<div class="num">${esc(p.num)}</div>`; s.append(body); sheet.append(s);
  });
  markPlaceholders(sheet);
  document.querySelectorAll(".tree a").forEach(a => { if (a.dataset.id === doc.id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  if (window.mermaid) { mermaid.initialize({ startOnLoad: false, theme: dark() ? "dark" : "neutral", securityLevel: "strict" });
    mermaid.run({ nodes: sheet.querySelectorAll("pre.mermaid") }).catch(() => {}); }
}

function boot() {
  const tree = document.getElementById("tree");
  DOCS.forEach(d => { const a = document.createElement("a"); a.href = "#" + d.id; a.dataset.id = d.id;
    a.innerHTML = `<span class="dot ${esc(d.status)}" aria-hidden="true"></span><span>${esc(d.file)}</span>${d.placeholders ? `<span class="count" title="${d.placeholders} placeholders to fill">${d.placeholders}</span>` : ""}`;
    tree.append(a); });
  const core = DOCS.filter(d => d.core); const gated = core.length ? core : DOCS;
  const done = gated.filter(d => d.status === "done" && !d.placeholders).length;
  document.getElementById("files-count").textContent = `${DOCS.length} documents`;
  document.getElementById("progress-label").textContent = `Documentation progress · ${done}/${gated.length} done`;
  document.getElementById("progress-bar").style.width = (100 * done / gated.length) + "%";
  const show = () => {
    const h = decodeURIComponent(location.hash.slice(1));
    const doc = DOCS.find(d => h === d.id || h.startsWith(d.id + "--")) || DOCS[0];
    render(doc);
    const target = h && document.getElementById(h);
    if (target && target.tagName === "SECTION") target.scrollIntoView(); };
  addEventListener("hashchange", show); show();
}
boot();
</script>
"""

if __name__ == "__main__":
    sys.exit(main())
