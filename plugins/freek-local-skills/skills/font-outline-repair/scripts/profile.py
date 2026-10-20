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
import ufoLib2


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
for path in args.ufos:
    pts = list(ufoLib2.Font.open(path)[glyph].contours[int(c)].points)
    n = len(pts)
    step = 1 if fwd else -1
    poly, segs = [], []
    i = a
    while i != b:
        j = (i + step) % n
        offs = []
        while not pts[j].type:
            offs.append(j)
            j = (j + step) % n
        P = lambda k: (pts[k].x, pts[k].y)
        if offs:
            s = seg_points(P(i), P(offs[0]), P(offs[1]), P(j))
            segs.append((i, j, [P(i), P(offs[0]), P(offs[1]), P(j)]))
        else:
            s = [(P(i)[0] + (P(j)[0] - P(i)[0]) * t / 10, P(i)[1] + (P(j)[1] - P(i)[1]) * t / 10) for t in range(11)]
            segs.append((i, j, None))
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
        for i, j, p in segs:
            ks = [0.0] * 33 if p is None else [sgn * 1000 * curvature(p, k / 32) for k in range(33)]
            jump = "" if prev_end is None else f", jump {ks[0] - prev_end:+.2f}"
            kind = "line" if p is None else "curve"
            print(f"  {i}-{j} {kind}: start {ks[0]:.2f}, least {min(ks):.2f}, peak {max(ks):.2f}, end {ks[-1]:.2f}{jump}")
            prev_end = ks[-1]
