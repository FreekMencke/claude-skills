"""Direction along a stretch of contour, from node A to node B (forward or backward):
total turning, how much of it turns back against the main turn (dips, S-bends), and the
sharpest turn per unit. usage: profile.py GLYPH C:A>B|C:A<B UFO... [--curves]

Run it over a straight edge and the curve it runs into, in each weight: a turn back of
about 2 degrees there read as a dip to the designer. --curves adds, per curve, its
curvature (1/radius, x1000, positive with the stretch's turn) at the start, its least
and peak, at the end, and the jump at each node: a curve that leaves a straight edge
with a high peak turns in one spot (a knee), one whose least is near 0 has a flat spot."""
import argparse
import math
import sys
import ufoLib2
from fontTools.pens.basePen import decomposeQuadraticSegment, decomposeSuperBezierSegment


def seg_points(p0, p1, p2, p3, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
        out.append((x, y))
    return out


def curvature(p, t):
    mt = 1 - t
    d1 = [3 * mt * mt * (p[1][k] - p[0][k]) + 6 * mt * t * (p[2][k] - p[1][k]) + 3 * t * t * (p[3][k] - p[2][k]) for k in (0, 1)]
    d2 = [6 * mt * (p[2][k] - 2 * p[1][k] + p[0][k]) + 6 * t * (p[3][k] - 2 * p[2][k] + p[1][k]) for k in (0, 1)]
    v = math.hypot(*d1)
    return 0.0 if v < 1e-9 else (d1[0] * d2[1] - d1[1] * d2[0]) / v**3


def cubics(p0, offs, p1, kind):
    """A segment as a list of cubics: [] for a line, one for a plain cubic; one off-curve
    point or a qcurve is a quadratic spline, more than two in a curve a super-Bezier,
    both split the way fontTools' pens do."""
    if not offs:
        return []
    if kind == "curve" and len(offs) == 2:
        return [[p0, *offs, p1]]
    if kind == "curve" and len(offs) > 2:
        out, q0 = [], p0
        for seg in decomposeSuperBezierSegment([*offs, p1]):
            out.append([q0, *seg])
            q0 = seg[2]
        return out
    out, q0 = [], p0
    for q, q1 in decomposeQuadraticSegment([*offs, p1]):
        out.append([q0, tuple(q0[d] + 2 / 3 * (q[d] - q0[d]) for d in (0, 1)), tuple(q1[d] + 2 / 3 * (q[d] - q1[d]) for d in (0, 1)), q1])
        q0 = q1
    return out


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("glyph")
ap.add_argument("spec", metavar="C:A>B|C:A<B", help="contour C, from node A forward (>) or backward (<) to B")
ap.add_argument("ufos", metavar="UFO", nargs="+")
ap.add_argument("--curves", action="store_true", help="curvature per curve and the jumps at nodes")
args = ap.parse_args()
glyph, spec = args.glyph, args.spec
c, rest = spec.split(":")
fwd = ">" in rest
a, b = (int(v) for v in rest.replace("<", ">").split(">"))
if a == b:
    sys.exit(f"{spec}: A and B are the same node; give two nodes")
for path in args.ufos:
    pts = list(ufoLib2.Font.open(path)[glyph].contours[int(c)].points)
    n = len(pts)
    for k in (a, b):
        if not 0 <= k < n or not pts[k].type:
            sys.exit(f"{path}: {glyph} contour {c} point {k} is not an on-curve point (the contour has {n} points)")
    step = 1 if fwd else -1
    P = lambda k: (pts[k].x, pts[k].y)
    poly, segs = [], []
    i = a
    while i != b:
        j = (i + step) % n
        offs = []
        while not pts[j].type:
            offs.append(j)
            j = (j + step) % n
        # split the segment in contour order, then turn it round when walking backward
        s0, s1 = (i, j) if fwd else (j, i)
        parts = cubics(P(s0), [P(k) for k in (offs if fwd else offs[::-1])], P(s1), pts[s1].type)
        if not fwd:
            parts = [p[::-1] for p in parts[::-1]]
        if parts:
            s = [q for k, p in enumerate(parts) for q in seg_points(*p)[(1 if k else 0):]]
        else:
            s = [(P(i)[0] + (P(j)[0] - P(i)[0]) * t / 10, P(i)[1] + (P(j)[1] - P(i)[1]) * t / 10) for t in range(11)]
        segs.append((i, j, parts))
        poly += s if not poly else s[1:]
        i = j
    angs, lens = [], []
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-6:
            continue
        angs.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
        lens.append(L)
    turns = [((b2 - b1 + 180) % 360) - 180 for b1, b2 in zip(angs, angs[1:])]
    total = sum(turns)
    back = sum(t for t in turns if (t > 0) != (total > 0))
    sharp = max(abs(t) / ((l1 + l2) / 2) for t, l1, l2 in zip(turns, lens, lens[1:]))
    label = "/".join(path.rstrip("/").split("/")[-2:])
    print(f"{label}: {spec} turns {total:+.1f} deg, back {back:+.1f} deg, sharpest {sharp:.1f} deg/unit")
    if args.curves:
        sgn = 1 if total >= 0 else -1
        prev_end = None
        for i, j, parts in segs:
            # curvature along the segment's cubics; a line has none
            ks = [sgn * 1000 * curvature(p, k / 32) for p in parts for k in range(33)] or [0.0] * 33
            jump = "" if prev_end is None else f", jump {ks[0] - prev_end:+.2f}"
            kind = "curve" if parts else "line"
            print(f"  {i}-{j} {kind}: start {ks[0]:.2f}, least {min(ks):.2f}, peak {max(ks):.2f}, end {ks[-1]:.2f}{jump}")
            prev_end = ks[-1]
