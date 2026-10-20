#!/usr/bin/env python3
"""Check that a fix step changed only what it should: compare two versions of the
same UFOs glyph by glyph.

usage:
  compare.py BEFORE.ufo AFTER.ufo [BEFORE2.ufo AFTER2.ufo ...] [--tol 1.0] [--glyphs a b]
             [--json out.json]

For every glyph whose outline changed it reports:
  shape    the largest distance between the two visible outlines (overlaps removed,
           so an edge moving inside an overlap doesn't count), measured both ways
           (densely sampled, so it catches bulges a node-to-node check misses)
  bbox     how far the bounding box moved (extremes lost or shifted)
  corners  corner nodes (bend over 10 degrees) lost, added, or turned by over 3 degrees,
           matched by position
  contours count and direction of contours
  width, anchors, components
Anything over --tol (shape, bbox) or any change in corners, contours, width, anchors
or components is listed as a problem. Prints a summary and exits 1 on problems.
Reads only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ufoLib2
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402
from compat import pts_of, signed_area  # noqa: E402


def visible(polys):
    """The polygons with overlaps removed: the outline that renders."""
    import pathops
    p = pathops.Path()
    pen = p.getPen()
    for poly in polys:
        if len(poly) < 3:
            continue
        pen.moveTo(poly[0])
        for q in poly[1:]:
            pen.lineTo(q)
        pen.closePath()
    try:
        p.simplify(fix_winding=True)
    except Exception:
        return polys
    out = []
    for verb, pts in p.segments:
        if verb == "moveTo":
            out.append([pts[0]])
        elif verb == "lineTo":
            out[-1].append(pts[0])
        elif verb == "closePath" and out:
            out[-1].append(out[-1][0])
    return out


def samples(glyph, font, per=40, spacing=0.5):
    """Points along the visible outline no more than `spacing` units apart: curves are
    flattened, overlaps removed, then every edge is subdivided, so a distance to the
    nearest sample is a distance to the outline."""
    out = []
    for poly in visible(L.glyph_polygons(glyph, font, steps=per)):
        for a, b in zip(poly, poly[1:]):
            k = max(1, int(L.dist(a, b) / spacing))
            out.extend((a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(k))
        if poly:
            out.append(poly[-1])
    return out


def node_bends(glyph):
    """{(x, y): bend in degrees} for every on-curve node."""
    out = {}
    for c in glyph.contours:
        P = pts_of(c)
        closed = P and P[0].type != "move"
        for i, p in enumerate(P):
            if p.type is None:
                continue
            t_in, t_out = L.node_tangents(P, i, closed)
            if t_in and t_out:
                out[(round(p.x), round(p.y))] = L.angle_deg(t_in, t_out)
    return out


def corner_changes(ga, gb, tol=3.0):
    """Corners (bend over 10 degrees) lost, added or changed by more than tol, matched by position."""
    a, b = node_bends(ga), node_bends(gb)
    out = []
    for pos, ang in a.items():
        if ang > 10:
            nb = b.get(pos)
            if nb is None:
                out.append(f"corner at {pos} ({ang:.0f}°) gone")
            elif abs(nb - ang) > tol:
                out.append(f"corner at {pos} {ang:.0f}° -> {nb:.0f}°")
    for pos, ang in b.items():
        if ang > 10 and pos not in a:
            out.append(f"new corner at {pos} ({ang:.0f}°)")
        elif ang > 10 and a.get(pos, 0) <= 10 and ang - a.get(pos, 0) > tol:
            out.append(f"corner at {pos} {a.get(pos, 0):.0f}° -> {ang:.0f}°")
    return out


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def compare_glyph(name, ga, fa, gb, fb):
    probs, info = [], {}
    same = [[(p.x, p.y, p.type) for p in c.points] for c in ga.contours] == \
           [[(p.x, p.y, p.type) for p in c.points] for c in gb.contours]
    if abs(ga.width - gb.width) >= 0.5:
        probs.append(f"width {ga.width:g} -> {gb.width:g}")
    an_a = {a.name: (a.x, a.y) for a in ga.anchors}
    an_b = {a.name: (a.x, a.y) for a in gb.anchors}
    if set(an_a) != set(an_b) or any(L.dist(an_a[k], an_b[k]) >= 0.5 for k in an_a):
        probs.append("anchors changed")
    ca, cb = list(ga.components), list(gb.components)
    if [c.baseGlyph for c in ca] != [c.baseGlyph for c in cb] or any(
            max(abs(x - y) for x, y in zip(a.transformation, b.transformation)) >= 0.5 for a, b in zip(ca, cb)):
        probs.append("components changed")
    if same:
        return None, probs, info
    sa, sb = samples(ga, fa), samples(gb, fb)
    if not sa or not sb:
        probs.append("outline appeared or vanished")
        return 0.0, probs, info
    d1 = cKDTree(sb).query(sa)[0].max()
    d2 = cKDTree(sa).query(sb)[0].max()
    info["shape"] = round(float(max(d1, d2)), 2)
    ba, bb = bbox(sa), bbox(sb)
    info["bbox"] = round(max(abs(x - y) for x, y in zip(ba, bb)), 2)
    if len(ga.contours) != len(gb.contours):
        probs.append(f"contours {len(ga.contours)} -> {len(gb.contours)}")
    else:
        for k, (ca, cb) in enumerate(zip(ga.contours, gb.contours)):
            if signed_area(pts_of(ca)) * signed_area(pts_of(cb)) < 0:
                probs.append(f"contour {k} reversed")
    probs += corner_changes(ga, gb)
    info["nodes"] = (sum(1 for c in ga.contours for p in c.points if p.type),
                     sum(1 for c in gb.contours for p in c.points if p.type))
    return info["shape"], probs, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+", help="BEFORE.ufo AFTER.ufo, repeated")
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--json")
    opt = ap.parse_args(argv)
    if len(opt.pairs) % 2:
        sys.exit("give BEFORE AFTER pairs")
    report, bad = [], 0
    for a, b in zip(opt.pairs[0::2], opt.pairs[1::2]):
        fa, fb = ufoLib2.Font.open(a), ufoLib2.Font.open(b)
        missing = sorted(set(fa.keys()) ^ set(fb.keys()))
        changed, worst, nodes = 0, (0.0, None), [0, 0]
        rows = []
        for name in sorted(set(fa.keys()) & set(fb.keys())):
            if opt.glyphs and name not in opt.glyphs:
                continue
            shape, probs, info = compare_glyph(name, fa[name], fa, fb[name], fb)
            if shape is not None:
                changed += 1
                if shape > worst[0]:
                    worst = (shape, name)
                if info.get("bbox", 0) > opt.tol:
                    probs.append(f"bbox moved {info['bbox']}")
                if shape > opt.tol:
                    probs.append(f"shape moved {shape}")
                if "nodes" in info:
                    nodes[0] += info["nodes"][0]
                    nodes[1] += info["nodes"][1]
            if probs:
                rows.append({"glyph": name, "problems": probs, **info})
        bad += len(rows) + len(missing)
        label = Path(b).name
        print(f"{label}: {changed} glyphs changed, nodes in them {nodes[0]} -> {nodes[1]}, "
              f"largest shape change {worst[0]} ({worst[1]}), {len(rows)} with problems"
              + (f", glyphs added/removed: {' '.join(missing)}" if missing else ""))
        for r in rows[:25]:
            try:
                print(f"  {r['glyph']}: {'; '.join(r['problems'])}")
            except BrokenPipeError:
                return 1
        if len(rows) > 25:
            print(f"  … {len(rows) - 25} more")
        report.append({"before": a, "after": b, "changed": changed, "nodes": nodes, "worst": worst, "problems": rows, "missing": missing})
    if opt.json:
        Path(opt.json).write_text(json.dumps(report, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
