#!/usr/bin/env python3
"""Build ONE self-contained e2e proof page (Claude Artifact page contract) from step screenshots.

Usage:  python3 build-proof-page.py manifest.json <shots_dir> out.html
Needs:  Pillow (`pip3 install pillow`).

Screenshots: <shots_dir>/<step id>--desktop.png and/or <step id>--mobile.png
(a bare <step id>.png is treated as desktop). Missing files are listed and the build fails.

manifest.json:
{
  "title": "Checkout E2E Proof",                 # <title>: 2-4 word NAME, no "- explainer"
  "heading": "Guest checkout — E2E proof",
  "subtitle": "What was run, where (project/tenant), cleaned up after.",
  "meta":  [{"label": "PR #4162", "href": "https://github.com/..."}, {"label": "branch x @ abc123"}],
  "kpis":  [{"value": "12/12", "label": "L2 · API on dev"}],
  "viewports": ["desktop", "mobile"],            # what the user chose in Step 0 (+ "tablet"; order = column order)
  "viewport_labels": {"mobile": "Phone 375×812"},  # optional: override the default size labels
  "steps": [{"id": "01-user-register", "actor": "User", "title": "…", "caption": "what this PROVES"}],
  "table": {"title": "API scenarios (L2)", "columns": ["#", "Scenario", "HTTP", "Result", ""],
            "rows": [["S1", "…", "400", "…", "PASS"]]},   # HTTP cell gets a 2xx/4xx/5xx chip, PASS/FAIL colored
  "ui": {"steps_heading": "…"},                 # optional: override page chrome strings (see UI below)
  "notes": ["Honest caveats: hidden dev overlay + why, UX oddities seen, data cleaned."]
}
"""
import base64, html, io, json, os, sys

from PIL import Image

WIDTH = {"desktop": 1100, "tablet": 640, "mobile": 420}
ACTOR_CLASSES = ["a1", "a2", "a3", "a4"]
UI = {"steps_heading": "UI flow, step by step", "zoom_hint": "Click a shot to zoom.",
      "notes_heading": "Notes for the reviewer", "zoom": "Zoom step", "close": "Close"}


def esc(s):
    return html.escape(str(s))


def encode(path, viewport):
    im = Image.open(path).convert("RGB")
    im.thumbnail((WIDTH[viewport], 2000))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70, optimize=True, progressive=True)
    return base64.b64encode(buf.getvalue()).decode(), im.size


def find_shot(shots, step_id, vp):
    for name in (f"{step_id}--{vp}.png", f"{step_id}.png" if vp == "desktop" else None):
        if name and os.path.exists(os.path.join(shots, name)):
            return os.path.join(shots, name)
    return None


def main(manifest_path, shots, out):
    m = json.load(open(manifest_path, encoding="utf-8"))
    UI.update(m.get("ui", {}))
    vps = m.get("viewports") or ["desktop"]
    actors = {}
    missing, cards = [], []
    for i, s in enumerate(m["steps"], 1):
        cls = actors.setdefault(s.get("actor", ""), ACTOR_CLASSES[len(actors) % len(ACTOR_CLASSES)])
        figs = []
        for vp in vps:
            p = find_shot(shots, s["id"], vp)
            if not p:
                missing.append(f"{s['id']}--{vp}.png")
                continue
            b64, (w, h) = encode(p, vp)
            figs.append(
                f'<button type="button" class="thumb {vp}" aria-label="{UI["zoom"]} {i} ({vp})">'
                f'<img src="data:image/jpeg;base64,{b64}" alt="{esc(s["title"])} — {vp}" width="{w}" height="{h}" loading="lazy"></button>'
            )
        cards.append(
            f'<article class="step"><div class="shots n{len(figs)}">{"".join(figs)}</div>'
            f'<div class="cap"><span class="num">{i:02d}</span><span class="who {cls}">{esc(s.get("actor", ""))}</span>'
            f'<h3>{esc(s["title"])}</h3><p>{esc(s.get("caption", ""))}</p></div></article>'
        )
    if missing:
        sys.exit("missing screenshots:\n  " + "\n  ".join(missing))

    def pill(x):
        label = esc(x["label"])
        inner = f'<a href="{esc(x["href"])}">{label}</a>' if x.get("href") else label
        return f'<span class="pill">{inner}</span>'

    meta = "".join(pill(x) for x in m.get("meta", []))
    kpis = "".join(f'<div class="kpi"><b>{esc(k["value"])}</b><span>{esc(k["label"])}</span></div>' for k in m.get("kpis", []))

    def cell(c):
        t = str(c)
        if t.isdigit() and len(t) == 3:
            return f'<td><span class="code c{t[0]}">{t}</span></td>'
        if t in ("PASS", "FAIL"):
            return f'<td class="{t.lower()}">{t}</td>'
        return f"<td>{esc(t)}</td>"

    table = ""
    if m.get("table"):
        t = m["table"]
        head = "".join(f"<th>{esc(c)}</th>" for c in t["columns"])
        rows = "".join("<tr>" + "".join(cell(c) for c in r) + "</tr>" for r in t["rows"])
        table = f'<h2>{esc(t["title"])}</h2><div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
    notes = "".join(f"<li>{esc(n)}</li>" for n in m.get("notes", []))
    notes = f'<h2>{UI["notes_heading"]}</h2><ul class="notes">{notes}</ul>' if notes else ""
    # both → wide card (desktop + phone side by side); phone-only → narrow cards, 4-5 per row
    card_min = ("720px" if len(vps) > 2 else "520px") if len(vps) > 1 else ("220px" if vps == ["mobile"] else "340px")
    labels = {"desktop": "Web 1280×800", "tablet": "Tablet 768×1024", "mobile": "Phone 390×844", **m.get("viewport_labels", {})}
    vp_label = " + ".join(labels[v] for v in vps)

    dark = ("--bg:#131313;--ink:#ECEDF1;--mute:#A3A8B5;--card:#1C1B1B;--rec:#2A2A2A;--pri:#9DB0FF;"
            "--ok:#6FD39C;--okbg:#143322;--warn:#F0C040;--warnbg:#3A2F10;--bad:#FFB4AB;--badbg:#3B1715;"
            "--a2:#9DB0FF;--a2bg:#1E2547;--a3:#F0C040;--a3bg:#3A2F10;--a4:#E0A6FF;--a4bg:#2E1A3A;color-scheme:dark")
    page = f"""<title>{esc(m["title"])}</title>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#F7F8FA;--ink:#14161C;--mute:#5A6072;--card:#FFFFFF;--rec:#E9ECF3;--pri:#2540C8;--ok:#0F8A4B;--okbg:#E3F5EA;--warn:#8A5A00;--warnbg:#FFF3D6;--bad:#B3261E;--badbg:#FCE8E6;--a2:#2540C8;--a2bg:#E4E8FB;--a3:#8A5A00;--a3bg:#FFF3D6;--a4:#7A2FA8;--a4bg:#F3E6FB}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{dark}}}}}
:root[data-theme="dark"]{{{dark}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Be Vietnam Pro",system-ui,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:32px 64px}}
h1,h2,h3{{font-family:"Space Grotesk",system-ui,sans-serif;letter-spacing:-.02em;text-wrap:balance;margin:0}}h1{{font-size:clamp(26px,4vw,40px);line-height:1.1}}h2{{font-size:22px;margin:40px 0 14px}}h3{{font-size:16px;margin-top:6px}}
.sub{{color:var(--mute);margin:8px 0 0;max-width:75ch}}.meta{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}.pill{{background:var(--rec);color:var(--ink);border-radius:999px;padding:4px 12px;font-size:13px}}.pill a{{color:var(--pri)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:24px}}.kpi{{background:var(--card);color:var(--ink);border-radius:14px;padding:16px 18px}}.kpi b{{display:block;font:700 28px "Space Grotesk",system-ui,sans-serif;color:var(--ok);font-variant-numeric:tabular-nums}}.kpi span{{color:var(--mute);font-size:13px}}
.flow{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,{card_min}),1fr));gap:16px}}
.step{{background:var(--card);color:var(--ink);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}}
.shots{{display:grid;gap:8px;background:var(--rec);padding:8px}}.shots.n2{{grid-template-columns:3fr 1fr;align-items:start}}.shots.n3{{grid-template-columns:1.6fr .75fr .46fr;align-items:start}}
.thumb{{display:block;width:100%;padding:0;border:0;background:none;cursor:zoom-in;touch-action:manipulation}}.thumb img{{display:block;width:100%;height:auto;border-radius:6px}}.thumb.mobile img,.thumb.tablet img{{border-radius:14px;outline:3px solid var(--ink);outline-offset:-1px}}
.thumb:focus-visible,.close:focus-visible{{outline:3px solid var(--pri);outline-offset:2px}}
.cap{{padding:12px 16px 16px}}.cap p{{margin:4px 0 0;color:var(--mute);font-size:14px}}.num{{font:700 13px "Space Grotesk",system-ui,sans-serif;color:var(--mute);margin-right:8px}}
.who{{font-size:12px;font-weight:700;border-radius:6px;padding:2px 8px}}.a1{{background:var(--okbg);color:var(--ok)}}.a2{{background:var(--a2bg);color:var(--a2)}}.a3{{background:var(--a3bg);color:var(--a3)}}.a4{{background:var(--a4bg);color:var(--a4)}}
.tbl{{overflow-x:auto;background:var(--card);border-radius:14px}}table{{width:100%;min-width:720px;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}th,td{{text-align:left;padding:10px 14px;vertical-align:top;color:var(--ink)}}th{{color:var(--mute);font-weight:500;background:var(--rec)}}
.code{{font-family:ui-monospace,Menlo,monospace;font-weight:700;border-radius:6px;padding:1px 7px}}.c2{{background:var(--okbg);color:var(--ok)}}.c4{{background:var(--warnbg);color:var(--warn)}}.c5{{background:var(--badbg);color:var(--bad)}}.pass{{color:var(--ok);font-weight:700}}.fail{{color:var(--bad);font-weight:700}}
.notes{{background:var(--card);color:var(--ink);border-radius:14px;padding:6px 20px 6px 36px}}.notes li{{margin:10px 0}}
dialog{{border:0;padding:0;background:transparent;max-width:96vw;max-height:94vh}}dialog::backdrop{{background:rgba(0,0,0,.82)}}dialog img{{max-width:96vw;max-height:86vh;display:block;border-radius:10px;margin:0 auto}}dialog p{{color:#fff;margin:8px 0 0;font-size:14px;text-align:center}}
.close{{position:fixed;top:12px;right:12px;min-width:44px;min-height:44px;border-radius:999px;border:0;background:#fff;color:#14161C;font-size:20px;cursor:pointer;touch-action:manipulation}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important;animation:none!important}}}}
</style>
<main class="wrap">
<h1>{esc(m.get("heading", m["title"]))}</h1>
<p class="sub">{esc(m.get("subtitle", ""))}</p>
<div class="meta">{meta}<span class="pill">{vp_label}</span></div>
<div class="kpis">{kpis}</div>
<h2>{UI['steps_heading']}</h2>
<p class="sub" style="margin-top:-6px">{UI['zoom_hint']}</p>
<div class="flow">{"".join(cards)}</div>
{table}
{notes}
</main>
<dialog id="lb"><button type="button" class="close" aria-label="{UI['close']}">×</button><img alt=""><p></p></dialog>
<script>
const lb=document.getElementById('lb'),im=lb.querySelector('img'),cap=lb.querySelector('p');
document.querySelectorAll('.thumb').forEach(b=>b.addEventListener('click',()=>{{const i=b.querySelector('img');im.src=i.src;cap.textContent=i.alt;lb.showModal();}}));
lb.addEventListener('click',()=>lb.close());
</script>
"""
    open(out, "w", encoding="utf-8").write(page)
    print(f"wrote {out}: {len(page) // 1024} KB, {len(m['steps'])} steps × {len(vps)} viewport(s)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
