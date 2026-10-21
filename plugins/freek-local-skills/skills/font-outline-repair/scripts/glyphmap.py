#!/usr/bin/env python3
"""A glyph map of a build for the designer: one HTML page with every glyph at every
static weight, drawn to one scale, zoomable, filled or as nodes and handles, with the
metric lines and the previous build as an overlay.

usage:
  glyphmap.py BUILD_DIR [--before BEFORE_DIR] [--ext otf] [--title T]
              [--labels BEFORE AFTER] [--no-points] --out map.html

Fonts are the static .otf (or --ext ttf) files below each folder, ordered by weight
class; the previous build's fonts are matched by weight class. A glyph opens all
weights side by side (arrow keys step through glyphs); "Changed" keeps only glyphs
whose outline or width differs from the previous build. Outlines are SVG paths from
the built fonts (components decomposed), so the page shows what readers get, rounding
included. Open it in a browser or publish it; it needs no network.

On one family every round had passed the audit and the reviewer, and the designer still
found about 20 problems in such a map (a barb at a bar end, joins pinched, a needle of
counter, a bar lighter than its siblings).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont


def fmt(v):
    return str(round(v)) if abs(v - round(v)) < 1e-6 else f"{v:.1f}"


def extract(path, points=True):
    f = TTFont(path)
    gs, cmap, os2 = f.getGlyphSet(), f.getBestCmap() or {}, f["OS/2"]
    rev = {}
    for u, n in sorted(cmap.items()):
        rev.setdefault(n, u)
    glyphs = {}
    for name in f.getGlyphOrder():
        pen = DecomposingRecordingPen(gs)
        gs[name].draw(pen)
        d, p = [], []
        for op, args in pen.value:
            if op == "moveTo":
                d.append("M" + " ".join(fmt(c) for c in args[0]))
                p += [*args[0], 0]
            elif op == "lineTo":
                d.append("L" + " ".join(fmt(c) for c in args[0]))
                p += [*args[0], 0]
            elif op == "curveTo":
                d.append("C" + " ".join(fmt(c) for pt in args for c in pt))
                p += [*args[0], 1, *args[1], 1, *args[2], 0]
            elif op == "qCurveTo":
                # TrueType: an implied on-curve point between two off-curve ones
                *offs, end = args
                if end is None:
                    end = ((offs[0][0] + offs[-1][0]) / 2, (offs[0][1] + offs[-1][1]) / 2)
                for k, q in enumerate(offs):
                    to = end if k == len(offs) - 1 else ((q[0] + offs[k + 1][0]) / 2, (q[1] + offs[k + 1][1]) / 2)
                    d.append("Q" + " ".join(fmt(c) for c in (*q, *to)))
                    p += [*q, 1, *to, 0]
            elif op in ("closePath", "endPath"):
                d.append("Z")
        g = {"w": round(gs[name].width), "d": "".join(d)}
        if points:
            g["p"] = [round(v) for v in p]
        if name in rev:
            g["u"] = rev[name]
        glyphs[name] = g
    name_t = f["name"]
    style = (name_t.getDebugName(17) or name_t.getDebugName(2) or Path(path).stem).strip()
    upm = f["head"].unitsPerEm
    return {"name": style, "wc": os2.usWeightClass, "glyphs": glyphs, "order": f.getGlyphOrder(), "upm": upm,
            "xh": getattr(os2, "sxHeight", 0) or 0, "cap": getattr(os2, "sCapHeight", 0) or 0,
            "asc": os2.sTypoAscender, "desc": os2.sTypoDescender}


def fonts_in(folder, ext):
    paths = sorted(Path(folder).rglob(f"*.{ext}"))
    if not paths:
        sys.exit(f"no .{ext} fonts below {folder}")
    out = []
    for p in paths:
        f = TTFont(p, lazy=True)
        if "fvar" in f:
            continue                    # the variable font: statics only
        out.append((f["OS/2"].usWeightClass, p))
    return [p for _, p in sorted(out)]


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --paper: #f1f3f6; --sheet: #fbfcfd; --ink: #14181f; --muted: #5d6675; --rule: #d6dbe3;
  --accent: #2c55d6; --accent-soft: #8fa5ea; --old: #d9483b; --metric: #b9c2cf;
  --font-ui: "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --font-data: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #0f1216; --sheet: #161a20; --ink: #e9ecf1; --muted: #98a2b2; --rule: #2a313b;
  --accent: #7d9bff; --accent-soft: #3f5596; --old: #ff7a6b; --metric: #3a4350; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #0f1216; --sheet: #161a20; --ink: #e9ecf1; --muted: #98a2b2; --rule: #2a313b;
  --accent: #7d9bff; --accent-soft: #3f5596; --old: #ff7a6b; --metric: #3a4350; color-scheme: dark }
* { box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font-family: var(--font-ui); margin: 0; }
.wrap { padding-inline: 16px; }
header.top { padding-block: 20px 8px; }
header.top h1 { font-size: 26px; margin: 0 0 4px; }
header.top p { margin: 0; color: var(--muted); font-size: 14px; max-width: 70ch; }
.bar { position: sticky; top: 0; z-index: 5; background: var(--paper); border-bottom: 1px solid var(--rule); padding-block: 10px;
       display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; }
.group { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-right: 4px; }
button.chip { font: 13px var(--font-ui); padding: 5px 10px; border: 1px solid var(--rule); background: var(--sheet); color: var(--ink);
              border-radius: 999px; cursor: pointer; }
button.chip[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--sheet); }
button.chip:focus-visible, input:focus-visible, .cell:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
input[type=range] { width: 140px; accent-color: var(--accent); }
input[type=search] { font: 14px var(--font-ui); padding: 6px 10px; border: 1px solid var(--rule); border-radius: 8px;
                     background: var(--sheet); color: var(--ink); width: 180px; max-width: 100%; }
.count { font: 12px var(--font-data); color: var(--muted); }
main { padding-block: 16px 48px; }
.grid { display: flex; flex-wrap: wrap; gap: 8px; }
.cell { background: var(--sheet); border: 1px solid var(--rule); border-radius: 6px; padding: 6px 6px 4px; cursor: pointer;
        display: flex; flex-direction: column; gap: 2px; }
.cell:hover { border-color: var(--accent); }
.cell .meta { display: flex; justify-content: space-between; gap: 8px; font: 10.5px var(--font-data); color: var(--muted); }
.cell .meta span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell .tag { color: var(--old); }
.row { display: flex; flex-direction: column; gap: 4px; width: 100%; }
.row .rowhead { font: 12px var(--font-data); color: var(--muted); display: flex; gap: 12px; }
.strip { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 4px; }
.strip .cell { flex: none; }
svg.g { display: block; }
svg.g path.fill { fill: var(--ink); }
svg.g path.outline { fill: none; stroke: var(--ink); stroke-width: 1; vector-effect: non-scaling-stroke; }
svg.g path.old { fill: none; stroke: var(--old); stroke-width: 1.25; vector-effect: non-scaling-stroke; }
svg.g line.m { stroke: var(--metric); stroke-width: 1; vector-effect: non-scaling-stroke; }
svg.g line.h { stroke: var(--accent-soft); stroke-width: 1; vector-effect: non-scaling-stroke; }
svg.g circle.on { fill: var(--accent); }
svg.g circle.off { fill: var(--sheet); stroke: var(--accent-soft); stroke-width: 1; vector-effect: non-scaling-stroke; }
.detail { position: fixed; inset: 0; z-index: 20; background: var(--paper); display: flex; flex-direction: column; }
.detail[hidden] { display: none; }
.detail header { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; padding-block: 12px; border-bottom: 1px solid var(--rule); }
.detail h2 { margin: 0; font-size: 22px; }
.detail .codes { font: 12px var(--font-data); color: var(--muted); }
.detail .spacer { flex: 1; }
.detail .proof { flex: 1; overflow: auto; padding-block: 16px; }
.detail .proof .strip { width: max-content; gap: 12px; }
.detail .proof .cell { cursor: default; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--muted); }
.legend i { display: inline-block; width: 18px; border-top: 2px solid; vertical-align: middle; margin-right: 6px; }
.empty { color: var(--muted); padding: 24px 0; }
</style></head><body>
<div class="wrap">
  <header class="top"><h1>__TITLE__</h1>
    <p>Every glyph of __N__ static weights, built from __BUILD__, drawn to one scale. Click a glyph for all weights side by side; arrow keys step through glyphs.</p></header>
  <div class="bar" role="toolbar" aria-label="View">
    <div class="group" id="weights" role="group" aria-label="Weight"><span class="label">Weight</span></div>
    <div class="group"><span class="label">Size</span><input type="range" id="size" min="70" max="520" step="10" value="150" aria-label="Glyph size"></div>
    <div class="group"><span class="label">Show</span>
      <button class="chip" id="t-nodes" aria-pressed="false">Nodes</button>
      <button class="chip" id="t-outline" aria-pressed="false">Outline only</button>
      <button class="chip" id="t-metrics" aria-pressed="true">Metrics</button>
      <button class="chip" id="t-old" aria-pressed="false">__OLDLABEL__ overlay</button></div>
    <div class="group"><span class="label">Filter</span>
      <button class="chip" id="t-changed" aria-pressed="false">Changed since __OLDLABEL__</button>
      <input type="search" id="q" placeholder="Name or character" aria-label="Search glyphs">
      <span class="count" id="count"></span></div>
  </div>
  <main><div class="grid" id="grid"></div></main>
</div>
<div class="detail wrap" id="detail" hidden>
  <header><h2 id="d-title"></h2><span class="codes" id="d-codes"></span>
    <div class="legend"><span><i style="color: var(--old)"></i>__OLDLABEL__ outline</span><span><i style="color: var(--accent)"></i>on-curve node</span><span><i style="color: var(--accent-soft)"></i>handle</span></div>
    <span class="spacer"></span>
    <button class="chip" id="d-prev" aria-label="Previous glyph">&larr;</button>
    <button class="chip" id="d-next" aria-label="Next glyph">&rarr;</button>
    <button class="chip" id="d-close">Close</button></header>
  <div class="proof"><div class="strip" id="d-strip"></div></div>
</div>
<script type="application/json" id="data-now">__NOW__</script>
<script type="application/json" id="data-old">__OLD__</script>
<script>
const NOW = JSON.parse(document.getElementById('data-now').textContent);
const OLD = JSON.parse(document.getElementById('data-old').textContent);
const WEIGHTS = NOW.map(f => f.name);
const BY = Object.fromEntries(NOW.map(f => [f.name, f]));
const OLDBY = Object.fromEntries(NOW.map(f => [f.name, OLD.find(o => o.wc === f.wc)]));
const MID = NOW.reduce((a, f) => Math.abs(f.wc - 400) < Math.abs(a.wc - 400) ? f : a, NOW[0]);
const ORDER = MID.order;
const UPM = MID.upm, TOP = Math.max(MID.asc, UPM * 0.95), BOTTOM = Math.min(MID.desc, -UPM * 0.25), H = TOP - BOTTOM, PAD = UPM * 0.04;
const load = (k, d) => { try { const v = localStorage.getItem('glyphmap.' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
const save = (k, v) => { try { localStorage.setItem('glyphmap.' + k, JSON.stringify(v)); } catch (e) {} };
const state = { weight: load('weight', MID.name), size: load('size', 150), nodes: load('nodes', false), outline: load('outline', false),
                metrics: load('metrics', true), old: load('old', false), changed: load('changed', false), q: '' };
if (!BY[state.weight] && state.weight !== 'All') state.weight = MID.name;
let current = null, shown = [];
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
function char(g) { return g && g.u !== undefined ? String.fromCodePoint(g.u) : ''; }
function code(g) { return g && g.u !== undefined ? 'U+' + g.u.toString(16).toUpperCase().padStart(4, '0') : 'unencoded'; }
function changed(name, w) { const a = BY[w].glyphs[name], o = OLDBY[w], b = o && o.glyphs[name]; return !!a && (!b || a.d !== b.d || a.w !== b.w); }
function svg(name, w, px) {
  const f = BY[w], g = f.glyphs[name]; if (!g) return '';
  const width = Math.max(g.w, UPM * 0.2) + 2 * PAD, scale = px / H, parts = [];
  if (state.metrics) {
    for (const y of [0, f.xh, f.cap, f.desc]) if (y) parts.push(`<line class="m" x1="${-PAD}" x2="${width - PAD}" y1="${y}" y2="${y}"/>`);
    parts.push(`<line class="m" x1="${-PAD}" x2="${width - PAD}" y1="0" y2="0"/><line class="m" x1="0" x2="0" y1="${BOTTOM}" y2="${TOP}"/><line class="m" x1="${g.w}" x2="${g.w}" y1="${BOTTOM}" y2="${TOP}"/>`);
  }
  parts.push(`<path class="${state.outline || state.nodes ? 'outline' : 'fill'}" d="${g.d}"/>`);
  const o = OLDBY[w];
  if (state.old && o && o.glyphs[name]) parts.push(`<path class="old" d="${o.glyphs[name].d}"/>`);
  if (state.nodes && g.p) {
    const r = 3 / scale, p = g.p, pts = [];
    for (let i = 0; i < p.length; i += 3) pts.push([p[i], p[i + 1], p[i + 2]]);
    for (let i = 0; i < pts.length; i++) if (pts[i][2] === 1) {   // each handle to the node it belongs to
      const prev = pts[i - 1], next = pts[i + 1], anchor = prev && prev[2] === 0 ? prev : next;
      if (anchor) parts.push(`<line class="h" x1="${anchor[0]}" y1="${anchor[1]}" x2="${pts[i][0]}" y2="${pts[i][1]}"/>`);
    }
    for (const [x, y, t] of pts) parts.push(t ? `<circle class="off" cx="${x}" cy="${y}" r="${r * 0.8}"/>` : `<circle class="on" cx="${x}" cy="${y}" r="${r}"/>`);
  }
  return `<svg class="g" width="${Math.round(width * scale)}" height="${px}" viewBox="${-PAD} ${-TOP} ${width} ${H}" role="img" aria-label="${esc(name)} ${esc(w)}"><g transform="scale(1,-1)">${parts.join('')}</g></svg>`;
}
function matches(name) {
  const q = state.q.trim().toLowerCase(); if (!q) return true;
  const g = MID.glyphs[name];
  return name.toLowerCase().includes(q) || char(g) === state.q.trim() || code(g).toLowerCase().includes(q);
}
function cell(n, w, px, label) {
  const g = BY[w].glyphs[n]; if (!g) return '';
  return `<div class="cell" tabindex="0" data-name="${esc(n)}" title="${esc(n)} · ${esc(w)}">${svg(n, w, px)}<div class="meta"><span>${esc(label)}</span><span>${changed(n, w) ? '<span class="tag">changed</span> ' : ''}${g.w}</span></div></div>`;
}
function render() {
  const grid = document.getElementById('grid'), ws = state.weight === 'All' ? WEIGHTS : [state.weight];
  shown = ORDER.filter(n => matches(n) && (!state.changed || ws.some(w => changed(n, w))));
  document.getElementById('count').textContent = `${shown.length} of ${ORDER.length}`;
  if (!shown.length) { grid.innerHTML = '<p class="empty">No glyph matches. Clear the search or the filter.</p>'; return; }
  grid.innerHTML = state.weight === 'All'
    ? shown.map(n => `<div class="row"><div class="rowhead"><span>${esc(n)}</span><span>${esc(char(MID.glyphs[n]))}</span><span>${code(MID.glyphs[n])}</span></div><div class="strip">` +
        WEIGHTS.map(w => cell(n, w, Math.round(state.size * 0.8), BY[w].wc)).join('') + '</div></div>').join('')
    : shown.map(n => cell(n, state.weight, state.size, n)).join('');
}
function openDetail(name) {
  current = name; document.getElementById('detail').hidden = false;
  const g = MID.glyphs[name], diff = WEIGHTS.filter(w => changed(name, w)).map(w => BY[w].wc);
  document.getElementById('d-title').textContent = `${name}  ${char(g)}`;
  document.getElementById('d-codes').textContent = `${code(g)} · ${OLD.length ? (diff.length ? 'changed at ' + diff.join(', ') : 'unchanged') : ''}`;
  const px = Math.max(220, Math.min(window.innerHeight - 190, 760));
  document.getElementById('d-strip').innerHTML = WEIGHTS.map(w => cell(name, w, px, `${w} ${BY[w].wc}`)).join('');
  try { history.replaceState(null, '', '#' + encodeURIComponent(name)); } catch (e) {}
}
function closeDetail() { document.getElementById('detail').hidden = true; current = null; try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} }
function step(dir) { if (!current) return; const list = shown.length ? shown : ORDER, i = list.indexOf(current); openDetail(list[(i + dir + list.length) % list.length]); }
function toggle(id, key) {
  const b = document.getElementById(id); b.setAttribute('aria-pressed', state[key]);
  if (!OLD.length && (key === 'old' || key === 'changed')) { b.hidden = true; state[key] = false; return; }
  b.addEventListener('click', () => { state[key] = !state[key]; b.setAttribute('aria-pressed', state[key]); save(key, state[key]); render(); if (current) openDetail(current); });
}
const wbox = document.getElementById('weights');
for (const w of [...WEIGHTS, 'All']) {
  const b = document.createElement('button'); b.className = 'chip'; b.textContent = w === 'All' ? 'All' : BY[w].wc; b.title = w;
  b.setAttribute('aria-pressed', state.weight === w);
  b.addEventListener('click', () => { state.weight = w; save('weight', w); wbox.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); render(); });
  wbox.appendChild(b);
}
toggle('t-nodes', 'nodes'); toggle('t-outline', 'outline'); toggle('t-metrics', 'metrics'); toggle('t-old', 'old'); toggle('t-changed', 'changed');
const size = document.getElementById('size'); size.value = state.size;
let pending; size.addEventListener('input', () => { state.size = +size.value; save('size', state.size); clearTimeout(pending); pending = setTimeout(render, 60); });
document.getElementById('q').addEventListener('input', e => { state.q = e.target.value; render(); });
document.getElementById('grid').addEventListener('click', e => { const c = e.target.closest('.cell'); if (c) openDetail(c.dataset.name); });
document.getElementById('grid').addEventListener('keydown', e => { const c = e.target.closest('.cell'); if (c && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openDetail(c.dataset.name); } });
document.getElementById('d-close').addEventListener('click', closeDetail);
document.getElementById('d-prev').addEventListener('click', () => step(-1));
document.getElementById('d-next').addEventListener('click', () => step(1));
document.addEventListener('keydown', e => { if (!current) return; if (e.key === 'Escape') closeDetail(); if (e.key === 'ArrowLeft') step(-1); if (e.key === 'ArrowRight') step(1); });
render();
const start = decodeURIComponent(location.hash.slice(1)); if (start && MID.glyphs[start]) openDetail(start);
</script></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build")
    ap.add_argument("--before")
    ap.add_argument("--ext", default="otf")
    ap.add_argument("--title")
    ap.add_argument("--labels", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--no-points", action="store_true", help="leave the nodes out (a smaller page)")
    ap.add_argument("--out", required=True)
    opt = ap.parse_args(argv)
    now = [extract(p, not opt.no_points) for p in fonts_in(opt.build, opt.ext)]
    old = [extract(p, False) for p in fonts_in(opt.before, opt.ext)] if opt.before else []
    family = TTFont(fonts_in(opt.build, opt.ext)[0], lazy=True)["name"].getDebugName(16) or \
        TTFont(fonts_in(opt.build, opt.ext)[0], lazy=True)["name"].getDebugName(1) or "Font"
    after_label, before_label = (opt.labels[1], opt.labels[0]) if opt.labels else (opt.build, opt.before or "")
    page = (TEMPLATE.replace("__TITLE__", html.escape(opt.title or f"{family} glyph map"))
            .replace("__N__", str(len(now))).replace("__BUILD__", html.escape(after_label))
            .replace("__OLDLABEL__", html.escape(before_label or "previous"))
            .replace("__NOW__", json.dumps(now, separators=(",", ":")).replace("</", "<\\/"))
            .replace("__OLD__", json.dumps(old, separators=(",", ":")).replace("</", "<\\/")))
    Path(opt.out).write_text(page, encoding="utf-8")
    unmatched = [f["name"] for f in now if old and not any(o["wc"] == f["wc"] for o in old)]
    print(f"{opt.out}: {len(now)} weights, {len(now[0]['order'])} glyphs, {Path(opt.out).stat().st_size / 1e6:.1f} MB"
          + (f"; previous build {len(old)} weights" if old else "")
          + (f"; no previous weight for {', '.join(unmatched)}" if unmatched else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
