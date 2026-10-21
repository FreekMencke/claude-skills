#!/usr/bin/env python3
"""Glyphs at weights between the masters, as a static instance draws them (rounded to
whole units, halves up as fontmake does) or as the variable font does (--raw), and the
bends they get there that no master has.

usage:
  between.py SOURCES... --glyphs G [G ...] --weights W [W ...] [--raw]
             [--out-dir DIR] [--bend DEG]

SOURCES is a .designspace or weight=UFO pairs (the masters; weight axis only). Each
weight is interpolated between the two masters around it (through the axis map), never
extrapolated: derive.py does that. Writes DIR/<weight>.ufo with the glyphs (and the
glyphs their components use), for solid.py and profile.py, and lists every node that
bends more than --bend degrees (1) at a weight where it bends under 0.5 in every master:
a straight edge or a smooth node that kinks only in between. Rounded, those come from
short handles; with --raw they come from the masters disagreeing (a smooth node whose
handles split in a different ratio in each master, an edge laid out in different steps).
"""
import argparse
import math
import sys
from pathlib import Path

import ufoLib2
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.misc.roundTools import otRound


def angle(v):
    return math.degrees(math.atan2(v[1], v[0]))


def bend_at(pts, i):
    """signed turn at node i between the directions to its neighbours (coincident ones skipped)"""
    n = len(pts)
    p = pts[i]
    a = next((pts[(i - k) % n] for k in range(1, n) if (pts[(i - k) % n][0], pts[(i - k) % n][1]) != (p[0], p[1])), None)
    b = next((pts[(i + k) % n] for k in range(1, n) if (pts[(i + k) % n][0], pts[(i + k) % n][1]) != (p[0], p[1])), None)
    if a is None or b is None:
        return 0.0
    return (angle((b[0] - p[0], b[1] - p[1])) - angle((p[0] - a[0], p[1] - a[1])) + 180) % 360 - 180


def load_masters(sources):
    """[(design location, font)] sorted, and a function from user weight to design location"""
    if len(sources) == 1 and sources[0].endswith(".designspace"):
        ds = DesignSpaceDocument.fromfile(sources[0])
        axis = next((a for a in ds.axes if a.tag == "wght"), ds.axes[0])
        others = {a.name: a.map_forward(a.default) for a in ds.axes if a is not axis}
        masters = []
        for s in ds.sources:
            if s.layerName or any(s.location.get(nm, dv) != dv for nm, dv in others.items()):
                continue  # sparse layers and sources off the other axes' defaults
            loc = s.location.get(axis.name, axis.map_forward(axis.default))
            masters.append((loc, ufoLib2.Font.open(s.path)))
        return sorted(masters, key=lambda m: m[0]), axis.map_forward
    masters = []
    for arg in sources:
        w, _, path = arg.partition("=")
        masters.append((float(w), ufoLib2.Font.open(path)))
    return sorted(masters, key=lambda m: m[0]), lambda w: w


def needed(font, names):
    out, todo = [], list(names)
    while todo:
        g = todo.pop()
        if g in out:
            continue
        out.append(g)
        todo += [c.baseGlyph for c in font[g].components]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--glyphs", nargs="+", required=True)
    ap.add_argument("--weights", nargs="+", type=float, required=True)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--out-dir", default="between")
    ap.add_argument("--bend", type=float, default=1.0)
    args = ap.parse_args(argv)

    masters, to_design = load_masters(args.sources)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # otRound (halves up), as fontmake rounds: Python's round takes halves to even, and at a
    # weight halfway between two masters every odd difference is a half (an 8.1 degree kink
    # where the built font has 4.8)
    rnd = (lambda v: v) if args.raw else otRound
    names = needed(masters[0][1], args.glyphs)

    # bends in the masters, per glyph/contour/node
    master_bends = {}
    for g in args.glyphs:
        for loc, f in masters:
            for ci, c in enumerate(f[g].contours):
                pts = [(p.x, p.y) for p in c.points]
                for i, p in enumerate(c.points):
                    if p.type:
                        key = (g, ci, i)
                        master_bends[key] = max(master_bends.get(key, 0.0), abs(bend_at(pts, i)))

    for w in args.weights:
        x = to_design(w)
        pair = next(((m0, m1) for m0, m1 in zip(masters, masters[1:]) if m0[0] <= x <= m1[0]), None)
        if not pair:
            sys.exit(f"weight {w:g} is outside the masters ({masters[0][0]:g}-{masters[-1][0]:g} in design units)")
        (x0, f0), (x1, f1) = pair
        t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
        font = ufoLib2.Font()
        font.info.unitsPerEm = f0.info.unitsPerEm
        for name in names:
            g0, g1 = f0[name], f1[name]
            g = font.newGlyph(name)
            g.width = otRound(g0.width + (g1.width - g0.width) * t)
            g.unicodes = list(g0.unicodes)
            for c0, c1 in zip(g0.contours, g1.contours):
                if len(c0.points) != len(c1.points):
                    sys.exit(f"{name}: masters at {x0:g} and {x1:g} are not compatible")
                pen = g.getPointPen()
                pen.beginPath()
                for p0, p1 in zip(c0.points, c1.points):
                    pen.addPoint((rnd(p0.x + (p1.x - p0.x) * t), rnd(p0.y + (p1.y - p0.y) * t)), p0.type, p0.smooth)
                pen.endPath()
            for k0, k1 in zip(g0.components, g1.components):
                tr = [a + (b - a) * t for a, b in zip(k0.transformation, k1.transformation)]
                g.components.append(type(k0)(k0.baseGlyph, tuple(tr[:4]) + (rnd(tr[4]), rnd(tr[5]))))
        path = out / f"{w:g}.ufo"
        font.save(path, overwrite=True)
        rows = []
        for gname in args.glyphs:
            for ci, c in enumerate(font[gname].contours):
                pts = [(p.x, p.y) for p in c.points]
                for i, p in enumerate(c.points):
                    if not p.type:
                        continue
                    b = bend_at(pts, i)
                    if abs(b) > args.bend and master_bends.get((gname, ci, i), 0.0) < 0.5:
                        rows.append(f"{gname} {ci}:{i} {b:+.1f}")
        mode = "raw" if args.raw else "rounded"
        print(f"{w:g} ({mode}, {t:.2f} of the way from {x0:g} to {x1:g}): {path}")
        print("  bends no master has: " + (", ".join(rows) if rows else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
