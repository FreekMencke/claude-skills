#!/usr/bin/env python3
"""High-resolution before/after sheet of every glyph a step changed.

usage:
  beforeafter.py BEFORE.ufo AFTER.ufo --out sheet.png [--glyphs a b] [--cols 6]
                 [--cell 2.2] [--dpi 150] [--comb] [--overlay [--ref REF.ufo]] [--title "Regular, point reduction"]

Each glyph gets two cells, before and after, drawn at the same scale with nodes,
handles and (with --comb) curvature combs at the same comb scale, and titled with
its node counts. Without --glyphs it draws every glyph whose outline differs.
--overlay draws one cell per glyph instead: before filled red, after as a blue line,
with both advance widths, which shows where a regenerated weight moved a part (a
bar, a terminal) or changed the spacing; use it to compare against an earlier
version of that weight. --ref REF.ufo adds a third weight as a green line, such as the
nearest drawn master, to show which of the two follows its shape.
--overlay-nodes draws one cell per glyph with both versions' outlines and nodes on
top of each other (before red, after blue; with --comb both curvature combs in the
same colours), for a step that keeps the shape and changes the points, such as point
reduction: the nodes that went are the red ones without a blue one on them, and a
blue comb smoother than the red one is a curve that got cleaner.
Reads only; writes the PNG.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import ufoLib2  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import comb_scale, contour_path, draw_comb, glyph_path  # noqa: E402

BLUE = "#1f77b4"


def nodes(g):
    return sum(1 for c in g.contours for p in c.points if p.type)


def draw(ax, font, g, comb, box, title, color, comb_max=None):
    p = glyph_path(font, g)
    if p is not None:
        ax.add_patch(PathPatch(p, facecolor="#e9e9e9", edgecolor="none"))
    for c in g.contours:
        cp = contour_path(c)
        if cp is not None:
            ax.add_patch(PathPatch(cp, facecolor="none", edgecolor="black", lw=0.6))
        pts = c.points
        n = len(pts)
        for i, pt in enumerate(pts):
            if pt.type is None:
                for k in ((i - 1) % n, (i + 1) % n):
                    if pts[k].type is not None:
                        ax.plot([pt.x, pts[k].x], [pt.y, pts[k].y], color=BLUE, lw=0.35)
                ax.plot(pt.x, pt.y, "o", ms=1.4, mfc="white", mec=BLUE, mew=0.4)
            else:
                ax.plot(pt.x, pt.y, "o" if pt.smooth else "s", ms=1.8, color="black")
    if comb:
        draw_comb(ax, g, comb, comb_max)
    x0, y0, x1, y1 = box
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#cccccc")
    ax.set_title(title, fontsize=6, color=color)


GREEN = "#2a9d3a"


def draw_overlay(ax, fa, ga, fb, gb, box, title, fr=None, gr=None):
    layers = [(fa, ga, "#f2a3a3", "#c0392b", 0.5)]
    if gr is not None:
        layers.append((fr, gr, "none", GREEN, 0.7))
    layers.append((fb, gb, "none", "#1f4fb4", 0.8))
    for font, g, face, edge, lw in layers:
        p = glyph_path(font, g)
        if p is not None:
            ax.add_patch(PathPatch(p, facecolor=face, edgecolor=edge, lw=lw, alpha=0.8 if face != "none" else 1))
        ax.axvline(g.width, color=edge, lw=0.5, ls=":")
    ax.axvline(0, color="#999999", lw=0.5)
    x0, y0, x1, y1 = box
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#cccccc")
    ax.set_title(title, fontsize=6)


RED = "#d62728"


def draw_nodes_overlay(ax, fa, ga, fb, gb, comb, box, title, comb_max=None):
    p = glyph_path(fb, gb)
    if p is not None:
        ax.add_patch(PathPatch(p, facecolor="#ececec", edgecolor="none"))
    if comb:
        draw_comb(ax, ga, comb, comb_max, color=RED, alpha=0.45)
        draw_comb(ax, gb, comb, comb_max, color=BLUE, alpha=0.75)
    for g, col, lw in ((ga, RED, 0.6), (gb, BLUE, 0.9)):
        for c in g.contours:
            cp = contour_path(c)
            if cp is not None:
                ax.add_patch(PathPatch(cp, facecolor="none", edgecolor=col, lw=lw))
    for c in ga.contours:
        for pt in c.points:
            if pt.type:
                ax.plot(pt.x, pt.y, "o", ms=4.2, mfc="none", mec=RED, mew=0.8)
    for c in gb.contours:
        for pt in c.points:
            if pt.type:
                ax.plot(pt.x, pt.y, "o" if pt.smooth else "s", ms=2.4, color=BLUE)
    x0, y0, x1, y1 = box
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#cccccc")
    ax.set_title(title, fontsize=8)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--cols", type=int, default=6, help="glyph pairs per row (default 6)")
    ap.add_argument("--cell", type=float, default=2.2, help="cell size in inches (default 2.2)")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--comb", action="store_true")
    ap.add_argument("--overlay", action="store_true", help="one cell per glyph: before filled red, after as a blue line")
    ap.add_argument("--overlay-nodes", action="store_true",
                    help="one cell per glyph: both outlines and their nodes on top of each other (before red, after blue)")
    ap.add_argument("--ref", help="with --overlay: a third UFO drawn as a green line, such as the nearest drawn master")
    ap.add_argument("--title")
    opt = ap.parse_args(argv)
    if opt.ref and not opt.overlay:
        ap.error("--ref needs --overlay")

    fa, fb = ufoLib2.Font.open(opt.before), ufoLib2.Font.open(opt.after)
    fr = ufoLib2.Font.open(opt.ref) if opt.ref else None
    names = opt.glyphs or [n for n in (fa.glyphOrder or sorted(fa.keys())) if n in fb and
                           [[(p.x, p.y, p.type) for p in c.points] for c in fa[n].contours] !=
                           [[(p.x, p.y, p.type) for p in c.points] for c in fb[n].contours]]
    if not names:
        print("No changed glyphs.")
        return 0
    upm = fa.info.unitsPerEm or 1000
    rows = (len(names) + opt.cols - 1) // opt.cols
    per = 1 if opt.overlay or opt.overlay_nodes else 2
    fig, axes = plt.subplots(rows, opt.cols * per, figsize=(opt.cell * opt.cols * per, opt.cell * 1.2 * rows), squeeze=False)
    before_nodes = after_nodes = 0
    for k, name in enumerate(names):
        r, c = divmod(k, opt.cols)
        ga, gb = fa[name], fb[name]
        na, nb = nodes(ga), nodes(gb)
        before_nodes += na
        after_nodes += nb
        desc = fa.info.descender or -0.25 * upm
        asc = fa.info.ascender or 0.8 * upm
        gr = fr[name] if fr is not None and name in fr else None
        w = max(ga.width, gb.width, gr.width if gr is not None else 0, 0.3 * upm)
        box = (-0.05 * upm, desc - 0.04 * upm, w + 0.05 * upm, asc + 0.04 * upm)
        if opt.overlay_nodes:
            # shorter teeth than side by side: two combs share the cell, and the tight
            # roundings at terminals would otherwise cover the glyph
            comb = comb_scale(ga, 0.025 * upm) if opt.comb else None
            draw_nodes_overlay(axes[r][c], fa, ga, fb, gb, comb, box, f"{name}  nodes {na} -> {nb}", 0.03 * upm)
            continue
        if opt.overlay:
            wtxt = f"width {ga.width:g}" + (f" -> {gb.width:g}" if gb.width != ga.width else "")
            draw_overlay(axes[r][c], fa, ga, fb, gb, box, f"{name}  {wtxt}", fr, gr)
            continue
        comb = comb_scale(ga, 0.04 * upm) if opt.comb else None  # same scale both sides
        draw(axes[r][2 * c], fa, ga, comb, box, f"{name}  before {na}", "black", 0.08 * upm)
        draw(axes[r][2 * c + 1], fb, gb, comb, box, f"{name}  after {nb}", "#2a7a2a" if nb < na else "black", 0.08 * upm)
    for k in range(len(names), rows * opt.cols):
        r, c = divmod(k, opt.cols)
        for j in range(per):
            axes[r][per * c + j].set_axis_off()
    head = opt.title or f"{Path(opt.before).name} -> {Path(opt.after).name}"
    if opt.overlay:
        ref = f", green line: {fr.info.styleName or Path(opt.ref).stem}" if fr is not None else ""
        head += f" (red fill: before, blue line: after{ref})"
    if opt.overlay_nodes:
        head += " (red: before, blue: after; red rings without a blue dot are nodes that went)"
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.5 / (opt.cell * 1.2 * rows)))
    fig.suptitle(f"{head}: {len(names)} glyphs, nodes {before_nodes} -> {after_nodes}", fontsize=12, y=1 - 0.15 / (opt.cell * 1.2 * rows))
    fig.savefig(opt.out, dpi=opt.dpi)
    print(f"{opt.out}: {len(names)} glyphs, nodes {before_nodes} -> {after_nodes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
