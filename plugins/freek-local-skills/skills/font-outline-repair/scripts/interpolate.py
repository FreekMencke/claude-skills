#!/usr/bin/env python3
"""Rebuild glyphs of a drawn middle master on the line between its neighbours: each point
at LOW + t x (HIGH - LOW), keeping the middle master's advance width and left side
bearing, and its nodes on zone lines (baseline, x-height, cap height, ascender,
descender, blue zones) where they are.

usage: interpolate.py LOW.ufo MID.ufo HIGH.ufo --glyphs G [G ...] --t T [--write]

T is the glyph's own weight fraction between LOW and HIGH, not the axis location: its
stroke widths (widths.py) in MID minus LOW over HIGH minus LOW. Stems and diagonals can
differ (on one family 1/3 for stems, 0.36 for v and w, against 1/4 on the axis). Give
one --t per run; run it again for glyphs with another fraction.

Works on whole glyphs: on dense, wiggly outlines (braces) it adds rounding kinks, so use
fix.py repredict there. Points matching the line can still make a worse shape (a notch
blunter than in either neighbour): judge by the outline and its mirror or sibling glyphs.
Glyphs whose contours don't match point for point in all three are skipped. Dry run
unless --write; rounds to whole units when MID uses them."""
import argparse
import sys
from pathlib import Path

import ufoLib2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("low")
ap.add_argument("mid")
ap.add_argument("high")
ap.add_argument("--glyphs", nargs="+", required=True)
ap.add_argument("--t", type=float, required=True, help="the glyph's weight fraction between LOW (0) and HIGH (1)")
ap.add_argument("--zone-snap", type=float, default=3.0,
                help="a node of MID on a zone line keeps it when the rebuilt node lands within this many units (default 3)")
ap.add_argument("--write", action="store_true", help="save MID")
opt = ap.parse_args()

low, mid, high = (ufoLib2.Font.open(p) for p in (opt.low, opt.mid, opt.high))
info = mid.info
zones = {0, info.xHeight, info.capHeight, info.ascender, info.descender}
zones |= set(info.postscriptBlueValues or []) | set(info.postscriptOtherBlues or [])
zones = sorted(z for z in zones if z is not None)
whole = all(float(v).is_integer() for g in mid for c in g.contours for p in c.points for v in (p.x, p.y))


def shape(g):
    return [[p.type for p in c.points] for c in g.contours]


for name in opt.glyphs:
    if not all(name in f for f in (low, mid, high)):
        print(f"{name}: not in all three; skipped")
        continue
    gl, gm, gh = low[name], mid[name], high[name]
    if gm.components or not (shape(gl) == shape(gm) == shape(gh)):
        print(f"{name}: components, or contours that don't match point for point; skipped")
        continue
    old = [(p.x, p.y) for c in gm.contours for p in c.points]
    lsb = gm.getBounds(mid).xMin
    for cl, cm, ch in zip(gl.contours, gm.contours, gh.contours):
        for pl, pm, ph in zip(cl.points, cm.points, ch.points):
            pm.x, pm.y = pl.x + opt.t * (ph.x - pl.x), pl.y + opt.t * (ph.y - pl.y)
    dx = lsb - gm.getBounds(mid).xMin
    snapped, k = 0, 0
    for cm in gm.contours:
        pts = cm.points
        n = len(pts)
        for p in pts:
            p.x += dx
        for i, p in enumerate(pts):
            y0 = old[k + i][1]
            if p.type is None or y0 not in zones or abs(p.y - y0) > opt.zone_snap or p.y == y0:
                continue
            # the node back on its zone, its handles with it
            dy = y0 - p.y
            p.y = y0
            for j in ((i - 1) % n, (i + 1) % n):
                if pts[j].type is None:
                    pts[j].y += dy
            snapped += 1
        k += n
    if whole:
        fix.round_keeping_directions(gm)
    new = [(p.x, p.y) for c in gm.contours for p in c.points]
    worst = max(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(old, new))
    print(f"{name}: t={opt.t:g}, points moved up to {worst:.1f} units, {snapped} node(s) kept on a zone, "
          f"width {gm.width:g} and left side bearing {lsb:g} kept")
if opt.write:
    mid.save()
    print(f"saved {opt.mid}")
else:
    print("dry run: nothing saved (use --write)")
