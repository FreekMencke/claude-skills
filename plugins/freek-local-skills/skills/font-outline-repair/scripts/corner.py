#!/usr/bin/env python3
"""Fair a small round corner of one to four curves where fair.py finds no layout: a curve
that leaves a straight edge with a long whole-unit direction ((73,-3): the nearest
whole-unit points on that line are 24 units out, too far for a 40-unit corner), or a
corner of more than two curves.

usage:
  corner.py FONT.ufo GLYPH RUN [--corner DEG] [--corner-b DEG] [--dev D]
            [--slide N] [--pick K] [--write]

RUN is CONTOUR:A>B or CONTOUR:A<B, as in fair.py: one to four cubic curves from node A
to node B. B stays, and A unless --slide. The handles and the nodes between are laid out
for curvature that rises and falls evenly along the outline (the integral of its change
per unit squared): no turn back against the corner, close to the curvature of the
outline beyond A and B at each end (0 where that turns the other way, a brace's S),
smooth through the nodes between, those nodes near where they were, handles not
crossing. It searches in real numbers first (each node between with one tangent), rounds,
then moves points one unit at a time while that helps; one unit at a time alone stalls
in a tight corner.
  --corner DEG    the handle next to A may leave the direction into A by this much (3;
                  the drawn masters leave such edges with a 2-4 degree corner)
  --corner-b DEG  the same at B (0: on B's line, moving in whole steps along it when that
                  step is short, else held)
  --dev D         the new outline stays within D units of the current one (4)
  --slide N       when a line runs into A, A may move back along it up to N units; every
                  4 units is tried (a corner too tight for its turn: on one family's
                  Black { the clean layout needed A 8 units further back)
  --pick K        write the K-th of the --slide positions, ranked by peak curvature (1)

It prints the curvature (1/radius, x1000, positive with the corner's turn) before and
after: least, peak, per curve start>peak>end, the jumps at the nodes between, the angle
off the edge at A and B, and the largest move. --write saves it. Look at it filled
(solid.py) beside the other masters, and measure it with profile.py --curves.

Written for a Black { (contour 0, 77>86, edge (73,-3)), where fair.py --edge refused
every --move/--dev/--turn: with A 8 units back, curvature 8 -> 38 -> 0, no turn back, no
jump at the nodes between. Static instances halfway between two masters still round each
point on its own; keeping every coordinate the same parity as the other master to avoid
that put 25 degrees of turn back into Black (references/case-notes.md).
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import ufoLib2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fair import adiff, angle, bez, curv, end_curvature, outline_poly, parse_run, primitive, segment_after, segment_before  # noqa: E402

SAMPLES = 40


def run_points(pts, a, b, s):
    """indices from node a to node b along s, every segment a cubic: [a, h, h, n, h, h, ..., b]"""
    n = len(pts)
    seq, i = [a], a
    while i != b:
        offs, j = [], (i + s) % n
        while pts[j].type is None:
            offs.append(j)
            j = (j + s) % n
        if len(offs) != 2:
            sys.exit(f"the segment from node {i} to {j} is not a cubic curve")
        seq += offs + [j]
        i = j
        if len(seq) > 13:
            sys.exit("RUN has more than four curves")
    return seq


def short_step(v, longest=12):
    st = primitive((round(v[0]), round(v[1]))) if v[0] or v[1] else None
    return st if st and max(abs(st[0]), abs(st[1])) <= longest else None


def unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def rot(u, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (u[0] * c - u[1] * s, u[0] * s + u[1] * c)


def signed(u, v):
    return math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))


class Corner:
    """One layout problem: the run's points (P, by contour index), the directions into A
    and out of B, the outline to stay near, and the cost."""

    def __init__(self, seq, P, tA, tB, ref, k_in, k_out, args):
        self.seq, self.args = seq, args
        self.A, self.B = seq[0], seq[-1]
        self.inner = seq[3:-1:3]
        self.ncurves = (len(seq) - 1) // 3
        self.seed = {i: tuple(P[i]) for i in seq}
        self.tA, self.tB, self.ref = tA, tB, ref
        self.sgn = 1
        self.sgn = 1 if sum(self.ks(P)) >= 0 else -1
        k_in, k_out = self.sgn * k_in, self.sgn * k_out
        # the outline beyond turns the other way (a brace's S): aim for 0 there, not against it
        self.aim_in, self.aim_out = max(k_in, 0.0), max(k_out, 0.0)
        self.k_in, self.k_out = k_in, k_out

    def curves(self, P):
        return [[P[self.seq[3 * k + j]] for j in range(4)] for k in range(self.ncurves)]

    def ks(self, P):
        return [self.sgn * 1000 * curv(cv, t / SAMPLES) for cv in self.curves(P) for t in range(SAMPLES + 1)]

    def arc_steps(self, P):
        q = [bez(cv, t / SAMPLES) for cv in self.curves(P) for t in range(SAMPLES + 1)]
        return [math.dist(a, b) for a, b in zip(q, q[1:])]

    def off_edge(self, P):
        A, B, hA, hB = P[self.A], P[self.B], P[self.seq[1]], P[self.seq[-2]]
        a = adiff(angle((hA[0] - A[0], hA[1] - A[1])), angle(self.tA))
        b = adiff(angle((B[0] - hB[0], B[1] - hB[1])), angle(self.tB))
        return a, b

    def deviation(self, P):
        qs = np.array([bez(cv, t / 12) for cv in self.curves(P) for t in range(13)])
        a, b = self.ref[:-1], self.ref[1:]
        d = b - a
        L2 = np.maximum((d ** 2).sum(1), 1e-12)
        t = np.clip(((qs[:, None, :] - a[None]) * d[None]).sum(2) / L2[None], 0, 1)
        near = a[None] + t[..., None] * d[None]
        return float(np.sqrt(((qs[:, None, :] - near) ** 2).sum(2)).min(1).max())

    def node_turn(self, P, i):
        j = self.seq.index(i)
        u, w = P[self.seq[j - 1]], P[self.seq[j + 1]]
        return adiff(angle((P[i][0] - u[0], P[i][1] - u[1])), angle((w[0] - P[i][0], w[1] - P[i][1])))

    def common(self, P, ks):
        # even rise and fall: the integral of (dk/ds)^2, so a short tight curve costs what it
        # shows (per sample, a short curve with a high peak was cheap); a jump at a node
        # counts over half a unit
        e = sum((y - x) ** 2 / max(d, 0.5) for x, y, d in zip(ks, ks[1:], self.arc_steps(P)))
        e += 4 * ((ks[0] - self.aim_in) ** 2 + (ks[-1] - self.aim_out) ** 2)   # into the outline beyond
        e += 2 * sum(math.dist(P[i], self.seed[i]) ** 2 for i in self.inner)  # stay near the outline
        e += 1e3 * max(0.0, self.deviation(P) - self.args.dev) ** 2
        return e

    def cost(self, P):
        """whole units: turning back, kinks at the nodes between and handles crossing as steps"""
        ks = self.ks(P)
        e = self.common(P, ks) + sum(1e4 for k in ks if k < -0.5)
        e += sum(50 * self.node_turn(P, i) ** 2 for i in self.inner)
        a, b = self.off_edge(P)
        e += 200 * (max(0, a - self.args.corner) ** 2 + max(0, b - self.args.corner_b - 0.3) ** 2)
        for cv in self.curves(P):
            if math.dist(cv[0], cv[1]) + math.dist(cv[2], cv[3]) > 1.15 * math.dist(cv[0], cv[3]) + 4:
                e += 1e3
        return e

    def smooth_layout(self, P):
        """The corner in real numbers: the handle at A at an angle within --corner of the
        edge and a length, each node between at a position with one tangent and two handle
        lengths, the handle at B like A's; minimised (Powell, bounded), then rounded."""
        from scipy.optimize import minimize
        seq, args = self.seq, self.args
        uA, uB = unit(self.tA), unit(self.tB)
        pa, pb, hA, hB = P[self.A], P[self.B], P[seq[1]], P[seq[-2]]
        span = math.dist(pa, pb)
        x0 = [math.dist(pa, hA), signed(uA, (hA[0] - pa[0], hA[1] - pa[1]))]
        bounds = [(0.5, span), (-args.corner, args.corner)]
        for i in self.inner:
            j = seq.index(i)
            n_, hi, ho = P[i], P[seq[j - 1]], P[seq[j + 1]]
            phi = math.degrees(math.atan2(ho[1] - hi[1], ho[0] - hi[0]))
            x0 += [n_[0], n_[1], phi, math.dist(n_, hi), math.dist(n_, ho)]
            r = 2 * args.dev
            bounds += [(n_[0] - r, n_[0] + r), (n_[1] - r, n_[1] + r), (phi - 45, phi + 45), (0.5, span), (0.5, span)]
        x0 += [math.dist(pb, hB), signed(uB, (pb[0] - hB[0], pb[1] - hB[1]))]
        bounds += [(0.5, span), (-args.corner_b, args.corner_b)]
        x0 = [min(max(v, lo), hi) for v, (lo, hi) in zip(x0, bounds)]

        def build(x):
            Q = {self.A: list(pa), self.B: list(pb)}
            d = rot(uA, x[1])
            Q[seq[1]] = [pa[0] + x[0] * d[0], pa[1] + x[0] * d[1]]
            k = 2
            for i in self.inner:
                j = seq.index(i)
                nx, ny, phi, li, lo = x[k:k + 5]
                k += 5
                u = (math.cos(math.radians(phi)), math.sin(math.radians(phi)))
                Q[i] = [nx, ny]
                Q[seq[j - 1]] = [nx - li * u[0], ny - li * u[1]]
                Q[seq[j + 1]] = [nx + lo * u[0], ny + lo * u[1]]
            d = rot(uB, x[k + 1])
            Q[seq[-2]] = [pb[0] - x[k] * d[0], pb[1] - x[k] * d[1]]
            return Q

        def f(x):
            Q = build(x)
            ks = self.ks(Q)
            e = self.common(Q, ks) + 1e3 * sum(min(0.0, k) ** 2 for k in ks)
            for cv in self.curves(Q):
                e += 1e2 * max(0.0, math.dist(cv[0], cv[1]) + math.dist(cv[2], cv[3]) - 1.15 * math.dist(cv[0], cv[3]) - 4) ** 2
            return e

        res = minimize(f, x0, method="Powell", bounds=bounds, options={"maxfev": 20000, "xtol": 1e-3, "ftol": 1e-6})
        return {i: [round(v[0]), round(v[1])] for i, v in build(res.x).items()}

    def moves(self):
        """each a list of (point, step): one unit in x or y for every free point; a node
        between with both its handles, and its two handles in opposite ways (turning its
        tangent); the end handles along their edge's step when it is short, and with no
        corner allowed at an end only along that step"""
        seq, units = self.seq, ((1, 0), (-1, 0), (0, 1), (0, -1))
        moves = [[(i, d)] for i in seq[1:-1] for d in units]
        for i in self.inner:
            j = seq.index(i)
            moves += [[(seq[j - 1], d), (i, d), (seq[j + 1], d)] for d in units]
            moves += [[(seq[j - 1], d), (seq[j + 1], (-d[0], -d[1]))] for d in units]
        for i, t, allow in ((seq[1], self.tA, self.args.corner), (seq[-2], self.tB, self.args.corner_b)):
            st = short_step(t)
            if allow <= 0.3:
                moves = [m for m in moves if len(m) > 1 or m[0][0] != i]
            if st:
                moves += [[(i, st)], [(i, (-st[0], -st[1]))]]
        return moves

    def polish(self, P, moves):
        best, better = self.cost(P), True
        while better:
            better = False
            for m in moves:
                for i, d in m:
                    P[i][0] += d[0]
                    P[i][1] += d[1]
                e = self.cost(P)
                if e < best - 1e-9:
                    best, better = e, True
                else:
                    for i, d in m:
                        P[i][0] -= d[0]
                        P[i][1] -= d[1]
        return best

    def fit(self, P):
        moves = self.moves()
        P1 = {i: list(v) for i, v in P.items()}
        best = self.polish(P1, moves)
        P2 = self.smooth_layout(P)
        best2 = self.polish(P2, moves)
        return (best, P1) if best <= best2 else (best2, P2)

    def describe(self, P):
        ks = self.ks(P)
        per = [ks[k * (SAMPLES + 1):(k + 1) * (SAMPLES + 1)] for k in range(self.ncurves)]
        jumps = [abs(per[k][-1] - per[k + 1][0]) for k in range(self.ncurves - 1)]
        a, b = self.off_edge(P)
        return (f"least {min(ks):6.2f}  peak {max(ks):6.2f}  per curve "
                + " ".join(f"{p[0]:.0f}>{max(p):.0f}>{p[-1]:.0f}" for p in per)
                + f"  jumps {' '.join(f'{j:.1f}' for j in jumps) or '-'}  off edge A {a:.1f} B {b:.1f} deg")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ufo")
    ap.add_argument("glyph")
    ap.add_argument("run", metavar="C:A>B|C:A<B")
    ap.add_argument("--corner", type=float, default=3.0)
    ap.add_argument("--corner-b", type=float, default=0.0)
    ap.add_argument("--dev", type=float, default=4.0)
    ap.add_argument("--slide", type=int, default=0)
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    font = ufoLib2.Font.open(args.ufo)
    c, A, B, s = parse_run(args.run)
    pts = font[args.glyph].contours[c].points
    seq = run_points(pts, A, B, s)
    P0 = {i: [pts[i].x, pts[i].y] for i in seq}
    before, after = segment_before(pts, A, s), segment_after(pts, B, s)
    E = (pts[before[0]].x, pts[before[0]].y)
    r = next(i for i in after[1:] if (pts[i].x, pts[i].y) != tuple(P0[B]))
    tB = (pts[r].x - P0[B][0], pts[r].y - P0[B][1])
    ref = np.array(outline_poly(pts, before[0], after[-1], s))
    k_in = end_curvature(pts, before, True, 1)
    k_out = end_curvature(pts, after, False, 1)

    # where A may go: as it is, or back along the line into it
    starts = [tuple(P0[A])]
    if args.slide:
        if len(before) != 2:
            sys.exit("--slide needs a line running into A")
        back = unit((E[0] - P0[A][0], E[1] - P0[A][1]))
        for u in range(4, args.slide + 1, 4):
            q = (round(P0[A][0] + u * back[0]), round(P0[A][1] + u * back[1]))
            if math.dist(q, E) > 2 and q not in starts:
                starts.append(q)

    rows = []
    for a in starts:
        P = {i: list(v) for i, v in P0.items()}
        P[A] = list(a)
        q = next(i for i in reversed(before[:-1]) if (pts[i].x, pts[i].y) != tuple(P0[A]))
        tA = (a[0] - pts[q].x, a[1] - pts[q].y) if len(before) == 2 else (P0[A][0] - pts[q].x, P0[A][1] - pts[q].y)
        cn = Corner(seq, P, tA, tB, ref, k_in, k_out, args)
        best, Pn = cn.fit(P)
        rows.append((best, a, cn, P, Pn))

    cn0 = rows[0][2]
    print(f"{args.glyph} {args.run}: curvature x1000, positive with the corner's turn; into A {cn0.k_in:.1f}, out of B {cn0.k_out:.1f}")
    print(f"  now:   {cn0.describe(P0)}")
    # by peak curvature, lowest first, those that turn back last: across --slide positions
    # the cost isn't comparable (on a Black {, A 4 units back cost less than 8 back, with a peak
    # of 51 against 38), and the roundest corner is what sliding is for
    ranked = sorted(rows, key=lambda r: (min(r[2].ks(r[4])) < -0.5, max(r[2].ks(r[4]))))
    for rank, (best, a, cn, P, Pn) in enumerate(ranked, 1):
        where = f"A {a[0]:g},{a[1]:g} " if args.slide else ""
        print(f"  {rank}: {where}{cn.describe(Pn)}  largest move {max(math.dist(Pn[i], P0[i]) for i in seq):.1f}, "
              f"from the outline {cn.deviation(Pn):.1f}; cost {cn.cost(P):.0f} -> {best:.0f}")
    held = [i for i in (seq[1], seq[-2]) if not any(len(m) == 1 and m[0][0] == i for m in cn0.moves())]
    if held:
        print(f"  held: {', '.join(map(str, held))} (its edge's whole-unit step is long; --corner/--corner-b let it turn)")
    best, a, cn, P, Pn = ranked[args.pick - 1]
    print("  " + " ".join(f"{i}:{Pn[i][0]:g},{Pn[i][1]:g}" for i in seq))
    if min(cn.ks(Pn)) < -0.5:
        print("  still turns back against the corner: not written; try a larger --corner, --dev or --slide")
        return 1
    if not args.write:
        print("  dry run: nothing written")
        return 0
    for i in seq:
        pts[i].x, pts[i].y = Pn[i]
    font.save()
    print(f"  written layout {args.pick}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
