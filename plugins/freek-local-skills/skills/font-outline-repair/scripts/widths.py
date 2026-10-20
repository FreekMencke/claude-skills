#!/usr/bin/env python3
"""Stroke widths of a derived glyph against its nearest master times the stem ratio.

usage:
  widths.py MASTER.ufo DERIVED.ufo GLYPH [--k K] [--along C:A-B ...]

Without --along: every segment of every contour, the width of the largest disc in the
ink touching it (the shrinking ball: it holds where strokes cross) as derived / (master
x k) at nine places along it; rows outside 0.85-1.15 are marked. With --along C:A-B:
widths square to the edge every ~8 units from node A to node B of contour C, master and
derived (derived given / k, so the two rows compare directly).

Use both: a ray square to one edge reads a taper larger than it is where the stroke
curves or meets another, and the disc reads a long gentle taper as no dip at all (& at
Thin: the loop thinned from 53 to 47 into its crossing over 150 units; the discs said
0.97-1.03). k defaults to the fonts' stem ratio (stem of n, l, I, H, o).
"""
import argparse
import math
import sys
from pathlib import Path

import ufoLib2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402
from contrast import Outline, seg_at, segs  # noqa: E402
from reshape import ink_side, outline_balls  # noqa: E402


def along(glyph, ci, a, b, step=8.0):
    cs = [list(c.points) for c in glyph.contours]
    ol = Outline(cs)
    pts = cs[ci]
    side = ink_side(ol, pts)
    sg = segs(pts)
    i0 = next(i for i, s in enumerate(sg) if s[0] == a)
    out, dist_along, prev, last = [], 0.0, None, -1e9
    for j in range(len(sg)):
        s = sg[(i0 + j) % len(sg)]
        for u in [q / 12 for q in range(12)]:
            p = seg_at(pts, s, u)
            t = L.unit(L.sub(seg_at(pts, s, min(u + 0.01, 1)), p))
            n = (-t[1] * side, t[0] * side)
            if prev:
                dist_along += L.dist(prev, p)
            prev = p
            if dist_along - last >= step:
                hit = ol.exit(p, n, skip=0.75)
                out.append(hit[0] if hit and hit[0] < 400 else None)
                last = dist_along
        if s[2] == b:
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("master")
    ap.add_argument("derived")
    ap.add_argument("glyph")
    ap.add_argument("--k", type=float)
    ap.add_argument("--along", nargs="+", default=[])
    opt = ap.parse_args(argv)
    fm, fd = ufoLib2.Font.open(opt.master), ufoLib2.Font.open(opt.derived)
    k = opt.k or L.ref_stem(fd)[1] / L.ref_stem(fm)[1]
    stem = L.ref_stem(fm)[1]
    gm, gd = fm[opt.glyph], fd[opt.glyph]
    if opt.along:
        for spec in opt.along:
            c, _, rng = spec.partition(":")
            a, _, b = rng.partition("-")
            wm, wd = along(gm, int(c), int(a), int(b)), along(gd, int(c), int(a), int(b))
            print(f"{opt.glyph} c{c} {a}->{b}, every ~8 units (derived / {k:.3f}):")
            print("  master  " + " ".join("-" if v is None else f"{v:.0f}" for v in wm))
            print("  derived " + " ".join("-" if v is None else f"{v / k:.0f}" for v in wd))
        return 0
    R = [list(c.points) for c in gm.contours]
    D = [list(c.points) for c in gd.contours]
    br = outline_balls(R, 8, set(), 2.5 * stem, near=0.3 * stem)
    bd = outline_balls(D, 8, set(), 2.5 * stem, near=0.3 * stem * k)
    print(f"{opt.glyph}: k {k:.3f}; derived disc / (master disc x k) along each segment")
    for ci in range(len(R)):
        for si, s in enumerate(segs(R[ci])):
            row = [None if hr is None or hd is None else hd / (hr * k)
                   for (_, _, _, hr), (_, _, _, hd) in zip(br[ci][si], bd[ci][si])]
            vals = [v for v in row if v is not None and math.isfinite(v)]
            flag = "  <<" if vals and (min(vals) < 0.85 or max(vals) > 1.15) else ""
            mid = br[ci][si][4][3]
            print(f"  c{ci} {s[0]:>2}-{s[2]:<2} master {2 * (mid or 0):5.1f} "
                  + " ".join(f"{v:4.2f}" if v is not None else "  - " for v in row) + flag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
