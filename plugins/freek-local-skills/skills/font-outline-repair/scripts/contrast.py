#!/usr/bin/env python3
"""Give a derived Thin or Black the stroke proportions of its nearest master.

usage:
  contrast.py --masters 300=Light.ufo 400=Regular.ufo 700=Bold.ufo \
              --derived 100=derived/F-100.ufo 900=derived/F-900.ufo --out-dir DIR \
              [--mode 100=full 900=floor] [--glyphs a b] [--max-stroke 2.0]

Extrapolation moves every point along a straight line through the masters. Where a
stroke grows faster than the stem across the masters (a Bold crossbar 2.3 times
Light's while the stem grows 1.9 times), it shrinks faster toward Thin and ends
thinner than the weight; where two edges meet at a shallow angle (the crotch of v),
their meeting point overshoots. This keeps the derived weight's skeleton (where each
stroke runs, the proportions and the metrics extrapolation gives) and sets each
stroke's thickness from the nearest master scaled by the stem ratio: at Thin, Light's
contrast; at Black, Bold's.

Thickness. Rays are cast across each stroke in the nearest master and in the derived
glyph, along the normal of the edge: on a straight edge at 15% and 85% of its length
(clear of the joins at its ends), on a curve a few units from each node. A ray counts
only when it leaves through the same segment in both and that edge runs roughly
parallel to the one it started from (within 25 degrees for a straight edge, 35 for a
curve; otherwise it ran along a stroke or into a join and measured a length), and
when it is under --max-stroke stems. Where the derived stroke is off by more than 12%
(or 2 units) the edge moves by the difference; when the far side moves too, each side
takes half. A straight edge moves as a whole when its stroke has parallel sides in the
master, or when it is upright or level in every master (a stem's side, a bar's top),
so stems stay upright and bars don't turn into wedges; on a tapered stroke the
offset varies linearly along the edge. Corners between straight edges go where the
moved edges meet, and a node next to an edge that doesn't move slides along it.

Joins. The strokes are set first; the joins are checked on the result. At an inside
corner where strokes meet (the crotch of v, the notch of N, the top of the counter in
4) the depth into the join, along the corner's bisector, is compared with the master's
times the stem ratio; only corners extrapolation broke are changed (under half that
depth or over twice, or pushed through the far side). The corner slides along the edge
that has to stay (one upright or level in every master, else the straight one, else
the one whose stroke can't move as a whole), and the stroke meeting it moves as a whole:
both its sides by the same amount, so it keeps its thickness and taper, turning about
its far end or fitted between two such corners (N's diagonal between its notch and its
top join). At a crotch between two such strokes (v, w, <) both move, which narrows the
foot rather than thickening the strokes. A stroke's other side is the straight edge
across it that faces it along at least 70% of both lengths. A corner with no such
stroke moves on its own only when it was pushed through the far side (^), since that
thickens the strokes around it.

Checks. Handles follow in one of three ways (translated with their node, blended along
the curve, or scaled with the chord); each glyph keeps the one audit.py's derived-weight
checks like best, and only when they don't get worse (blocks first, then slows) and
no stem leans and no parallel-sided stroke tapers by over 1.5 units more than before
(audit.edge_measures, behind edge-turned and stroke-wedge: extrapolation keeps upright
edges upright and seldom makes a wedge, so these are the step's own).
A node whose two curve segments give estimates more than half a stem apart is left
alone, and a node never moves further from its derived place than extrapolation moved
it from the nearest master, plus one stem.

Separate parts that closed up (the T and M of a trademark sign, the rings of a per-mille
sign at Black: under 3% of the em apart where the nearest master keeps them at least
half as far again apart) are moved apart to the master's gap, and the glyph is widened
by as much.
A part inside another part's counter that runs into it (the R of a registered sign at
Black) is scaled down about its centre, by at most 15%, until its gap is the master's.
A free bar crossing one stroke (the bar of ð) that sticks out on its two sides in a
different ratio than in the master slides along its length to the master's ratio.
Each of these is kept only if the checks agree.

Left as derived: dots (a part about as wide as high and under about two stems, not
holding or held by another contour: the dot of i, !, :), strokes already within 12%
(or 2 units) of the target, coordinates all masters share exactly (a baseline, a stem edge
every master has at the same place), and y values on a blue zone or metric line of
the nearest master (x-height, cap height, overshoots), so the vertical metrics stay
those extrapolation gives.

--mode full   (default for weights lighter than the nearest master) thicker or
              thinner, to the master's proportions.
--mode floor  (default for heavier weights) only thickens strokes that came out
              thinner than in the nearest master: at Black a stroke never gets
              thinner than in Bold, but dots and counters keep the extrapolated
              sizes (scaling them all up would close the gaps).

Writes new UFOs to --out-dir with the same file names; reads the inputs only. Check
the result with audit.py --derived and look at it: this is a geometric rule, not a
designer.
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
from pathlib import Path

import ufoLib2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402

STEPS = 24
DEBUG = None  # a dict to receive plan_moves' intermediate values


def segs(pts):
    """[(i0, [handle indices], i1)] for a closed contour (list of points with .type)."""
    n = len(pts)
    ons = [i for i, p in enumerate(pts) if p.type]
    out = []
    for k, i0 in enumerate(ons):
        i1 = ons[(k + 1) % len(ons)]
        hs = []
        j = (i0 + 1) % n
        while j != i1:
            hs.append(j)
            j = (j + 1) % n
        out.append((i0, hs, i1))
    return out


def seg_at(pts, s, u):
    i0, hs, i1 = s
    P = [(pts[i0].x, pts[i0].y)] + [(pts[h].x, pts[h].y) for h in hs] + [(pts[i1].x, pts[i1].y)]
    if len(P) == 2:
        return (P[0][0] + (P[1][0] - P[0][0]) * u, P[0][1] + (P[1][1] - P[0][1]) * u)
    if len(P) == 4:
        return L.cubic_at(P[0], P[1], P[2], P[3], u)
    # quadratic or other: de Casteljau
    while len(P) > 1:
        P = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(P, P[1:])]
    return P[0]


def tangent(pts, s, at_start):
    """Unit tangent of segment s in travel direction, at its start or end node."""
    i0, hs, i1 = s
    if at_start:
        a = (pts[i0].x, pts[i0].y)
        for j in hs + [i1]:
            b = (pts[j].x, pts[j].y)
            if L.dist(a, b) > 1e-6:
                return L.unit(L.sub(b, a))
    else:
        b = (pts[i1].x, pts[i1].y)
        for j in list(reversed(hs)) + [i0]:
            a = (pts[j].x, pts[j].y)
            if L.dist(a, b) > 1e-6:
                return L.unit(L.sub(b, a))
    return None


class Outline:
    """Flattened contours of one glyph, for ray casting and inside tests."""

    def __init__(self, contours):
        self.contours = contours
        self.edges = []  # (a, b, ci, si, u0, u1)
        self.polys = []
        for ci, pts in enumerate(contours):
            poly = []
            for si, s in enumerate(segs(pts)):
                prev = seg_at(pts, s, 0.0)
                steps = STEPS if s[1] else 1
                for k in range(1, steps + 1):
                    u = k / steps
                    q = seg_at(pts, s, u)
                    self.edges.append((prev, q, ci, si, (k - 1) / steps, u))
                    poly.append(prev)
                    prev = q
            self.polys.append(poly)

    def winding(self, p):
        w = 0
        x, y = p
        for poly in self.polys:
            for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
                if y0 <= y < y1 or y1 <= y < y0:
                    xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    if xi > x:
                        w += 1 if y1 > y0 else -1
        return w

    def inside(self, p):
        return self.winding(p) != 0

    def exit(self, p, d, skip=0.75):
        """First crossing of the ray p + s*d (s > skip) with the outline: (s, ci, si, u, edge vector)."""
        best = None
        for a, b, ci, si, u0, u1 in self.edges:
            e = L.sub(b, a)
            den = d[0] * e[1] - d[1] * e[0]
            if abs(den) < 1e-12:
                continue
            w = L.sub(a, p)
            s = (w[0] * e[1] - w[1] * e[0]) / den
            t = (w[0] * d[1] - w[1] * d[0]) / den
            if s > skip and -1e-9 <= t <= 1 + 1e-9 and (best is None or s < best[0]):
                best = (s, ci, si, u0 + (u1 - u0) * t, e)
        return best


def separate_parts(dg, ng, upm):
    """Parts side by side (the T and M of a trademark sign, the rings of a per-mille
    sign) that ended under 3% of the em apart while the nearest master keeps them at
    least half as far again apart: shift everything right of the gap so the gap is the
    master's, and widen the glyph by as much. Returns the shift (0 when nothing)."""
    if len(dg.contours) < 2 or len(dg.contours) != len(ng.contours):
        return 0.0

    def boxes(g):
        out = []
        for c in g.contours:
            xs, ys = [p.x for p in c.points], [p.y for p in c.points]
            out.append((min(xs), min(ys), max(xs), max(ys)))
        return out

    db, nb = boxes(dg), boxes(ng)
    best = None
    # a vertical gap: a line x = v with every contour wholly on one side
    xs = sorted({b[2] for b in db})
    for right_edge in xs:
        left = [i for i, b in enumerate(db) if b[2] <= right_edge]
        right = [i for i, b in enumerate(db) if b[0] > right_edge]
        if not left or not right or len(left) + len(right) != len(db):
            continue
        gap = min(db[i][0] for i in right) - right_edge
        ngap = min(nb[i][0] for i in right) - max(nb[i][2] for i in left)
        if gap < 0.03 * upm and ngap >= 1.5 * max(gap, 1.0) and ngap > gap:
            if best is None or gap < best[0]:
                best = (gap, ngap, right)
    if best is None:
        return 0.0
    gap, ngap, right = best
    shift = round(ngap - gap)
    for i in right:
        for p in dg.contours[i].points:
            p.x += shift
    for a in dg.anchors:
        if a.x > min(db[i][0] for i in right):
            a.x += shift
    dg.width += shift
    return float(shift)


def _polys(glyph, idx):
    return [Outline([list(glyph.contours[i].points)]).polys[0] for i in idx]


def shrink_inner(dg, ng):
    """Parts inside another part's counter (the R inside the ring of a registered sign)
    that touch or cross it, or come under half as close as in the nearest master: scale
    them about their centre until the gap is the master's again (at most 15% smaller).
    Returns the scale (1.0 when nothing)."""
    n = len(dg.contours)
    if n < 3 or n != len(ng.contours):
        return 1.0
    from scipy.spatial import cKDTree
    dp = _polys(dg, range(n))
    npl = _polys(ng, range(n))
    for c in range(n):
        # c: a counter (inside some other contour) that holds further contours
        if not any(j != c and _inside_poly(dp[c][0], dp[j]) for j in range(n)):
            continue
        inner = [j for j in range(n) if j != c and _inside_poly(npl[j][0], npl[c])]
        if not inner:
            continue
        gap_n = min(float(cKDTree(npl[c]).query(npl[j])[0].min()) for j in inner)

        def gap(scale):
            pts = [q for j in inner for q in dp[j]]
            cx = (min(q[0] for q in pts) + max(q[0] for q in pts)) / 2
            cy = (min(q[1] for q in pts) + max(q[1] for q in pts)) / 2
            moved = [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in pts]
            if not all(_inside_poly(q, dp[c]) for q in moved):
                return -1.0, (cx, cy)
            return float(cKDTree(dp[c]).query(moved)[0].min()), (cx, cy)
        g0, centre = gap(1.0)
        if g0 >= 0.5 * gap_n:
            continue
        lo, hi = 0.85, 1.0
        if gap(lo)[0] < gap_n:
            continue
        for _ in range(20):
            mid = (lo + hi) / 2
            if gap(mid)[0] >= gap_n:
                lo = mid
            else:
                hi = mid
        cx, cy = centre
        for j in inner:
            for p in dg.contours[j].points:
                p.x, p.y = cx + (p.x - cx) * lo, cy + (p.y - cy) * lo
        return lo
    return 1.0


def center_crossings(dg, ng):
    """A bar (a separate contour of four straight edges, closer to level than upright)
    that crosses one stroke of another contour and nothing else (the bar of ð) and
    sticks out on the two sides in a different ratio than in the nearest master: slide
    it along its own length until the ratio is the master's. Returns the largest slide
    (0 when none)."""
    n = len(dg.contours)
    if n < 2 or n != len(ng.contours):
        return 0.0
    dp, npl = _polys(dg, range(n)), _polys(ng, range(n))
    moved = 0.0
    for pi in range(n):
        if [p.type for p in dg.contours[pi].points] != ["line"] * 4:
            continue
        for qi in range(n):
            if qi == pi:
                continue
            res = []
            for polys, g in ((npl, ng), (dp, dg)):
                P, Q = polys[pi], polys[qi]
                # P's long axis: its longest straight edge
                c = list(g.contours[pi].points)
                best = max(((L.dist((a.x, a.y), (b.x, b.y)), (a, b)) for a, b in zip(c, c[1:] + c[:1])
                            if a.type and b.type in ("line",)), default=None, key=lambda x: x[0])
                if best is None:
                    break
                a, b = best[1]
                u = L.unit((b.x - a.x, b.y - a.y))
                if abs(u[1]) > 0.5:
                    break  # an upright part (a stem): sliding it would move the metrics
                v = (-u[1], u[0])
                rot = [[(L.dot(q, u), L.dot(q, v)) for q in poly] for poly in (P, Q)]
                us = [q[0] for q in rot[0]]
                vs = [q[1] for q in rot[0]]
                vm = (min(vs) + max(vs)) / 2
                runs = [r for r in L.ink_runs([rot[1]], vm, horizontal=True) if r[1] > min(us) and r[0] < max(us)]
                if len(runs) != 1 or not min(us) < runs[0][0] < runs[0][1] < max(us):
                    break  # P doesn't cross a stroke of Q along its middle
                others = [[(L.dot(q, u), L.dot(q, v)) for q in polys[j]] for j in range(n) if j not in (pi, qi)]
                if any(min(us) < r[1] and r[0] < max(us) for r in L.ink_runs(others, vm, horizontal=True)) if others else False:
                    break  # it meets another part too (the bar of a 4 joins its diagonal)
                q0, q1 = runs[0]
                res.append((q0 - min(us), max(us) - q1, u))
            if len(res) != 2:
                continue
            (lm, rm, _), (ld, rd, u) = res
            if lm <= 0 or rm <= 0 or ld + rd <= 0:
                continue
            want_l = (ld + rd) * lm / (lm + rm)
            delta = ld - want_l  # slide P this far along u
            if abs(delta) < 2:
                continue
            for p in dg.contours[pi].points:
                p.x, p.y = p.x + u[0] * delta, p.y + u[1] * delta
            moved = max(moved, abs(delta))
    return moved


def _inside_poly(pt, poly):
    x, y = pt
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def parallel(e, t, deg=35):
    return L.norm(e) > 1e-9 and abs(L.cross(L.unit(e), t)) <= math.sin(math.radians(deg))


def zone_ys(font):
    i = font.info
    ys = set()
    for v in (i.postscriptBlueValues or []) + (i.postscriptOtherBlues or []):
        ys.add(round(v))
    for v in (0, i.xHeight, i.capHeight, i.ascender, i.descender):
        if v is not None:
            ys.add(round(v))
    return ys


def plan_moves(name, dg, ng, mgs, k, mode, max_stroke, stem_n, zones, stem_d, parts=("thickness", "joins")):
    """{(contour, node): (dx, dy)} that give dg's strokes ng's proportions times k.
    parts: "thickness" (strokes), "joins" (inside corners), or both."""
    if not dg.contours or len(dg.contours) != len(ng.contours):
        return {}
    D = [list(c.points) for c in dg.contours]
    N = [list(c.points) for c in ng.contours]
    if any(len(a) != len(b) for a, b in zip(D, N)):
        return {}
    if any(p.type == "move" for c in N for p in c[:1]):
        return {}
    if any(len(m.contours) != len(N) or any(len(a.points) != len(b) for a, b in zip(m.contours, N)) for m in mgs):
        return {}
    on = Outline(N)
    od = Outline(D)
    # dots (the dot of i, !, :, a period) are not strokes: their size is not the
    # stem's, so leave them as extrapolated
    dots = set()
    for ci, c in enumerate(N):
        xs, ys = [p.x for p in c], [p.y for p in c]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if max(w, h) < 2.2 * stem_n and min(w, h) > 0.6 * max(w, h) and \
                not any(j != ci and on.polys[j] and _inside_poly(on.polys[ci][0], on.polys[j]) for j in range(len(N))) and \
                not any(j != ci and on.polys[j] and _inside_poly(on.polys[j][0], on.polys[ci]) for j in range(len(N))):
            dots.add(ci)
    nseg = [segs(c) for c in N]
    dseg = [segs(c) for c in D]
    limit = max_stroke * stem_n
    def held(ci, node):
        """(x held, y held): shared by all masters, or y on a zone of the nearest master."""
        xs = {m.contours[ci].points[node].x for m in mgs}
        ys = {m.contours[ci].points[node].y for m in mgs}
        return len(xs) == 1, len(ys) == 1 or round(N[ci][node].y) in zones

    def near_u(pts, s, at_start):
        """Parameter a few units along segment s from its start (or end) node: rays
        start there, inside the stroke, not on a corner where they could run along
        the next edge."""
        ln = max(L.dist(seg_at(pts, s, 0.0), seg_at(pts, s, 1.0)), 1e-6)
        u = min(3.0 / ln, 0.1)
        return u if at_start else 1.0 - u

    def pt(P, ci, i):
        return (P[ci][i].x, P[ci][i].y)

    # straight edges upright or level in every master stay so (a stem's side, a bar's top)
    upright = set()
    for ci, ss in enumerate(nseg):
        for si, (i0, hs, i1) in enumerate(ss):
            if not hs and (all(abs(m.contours[ci].points[i0].x - m.contours[ci].points[i1].x) < 0.01 for m in mgs) or
                           all(abs(m.contours[ci].points[i0].y - m.contours[ci].points[i1].y) < 0.01 for m in mgs)):
                upright.add((ci, si))

    # straight edges long enough to measure
    lines_n = {(ci, si) for ci, ss in enumerate(nseg) for si, s_ in enumerate(ss)
               if not s_[1] and ci not in dots and L.dist(pt(N, ci, s_[0]), pt(N, ci, s_[2])) >= 8}

    # the other side of each straight edge's stroke, tapered or not, when the two edges
    # face each other along most of their length (a stroke whose other side is split
    # into pieces, like the middle strokes of w, has none)
    side_of = {}
    for ci, si in sorted(lines_n):
        a, b = pt(N, ci, nseg[ci][si][0]), pt(N, ci, nseg[ci][si][2])
        t = L.unit(L.sub(b, a))
        mid = L.mul(L.add(a, b), 0.5)
        nrm = next((c_ for c_ in ((-t[1], t[0]), (t[1], -t[0])) if on.inside(L.add(mid, L.mul(c_, 1.0)))), None)
        hit = on.exit(mid, nrm) if nrm else None
        if hit is None or hit[0] > limit or (hit[1], hit[2]) not in lines_n or not parallel(hit[4], t, 25):
            continue
        h0, h1 = pt(N, hit[1], nseg[hit[1]][hit[2]][0]), pt(N, hit[1], nseg[hit[1]][hit[2]][2])
        la, lb = L.dist(a, b), L.dist(h0, h1)
        pr = sorted((L.dot(L.sub(h0, a), t), L.dot(L.sub(h1, a), t)))
        ov = min(la, pr[1]) - max(0.0, pr[0])
        if ov >= 0.7 * la and ov >= 0.7 * lb:
            side_of[(ci, si)] = (hit[1], hit[2])

    # stroke thickness, measured across the stroke in the nearest master and in the
    # derived glyph: on a straight edge at 15% and 85% of its length (clear of the joins
    # at its ends), on a curve a few units from each node
    est = []
    for ci, c in enumerate(N if "thickness" in parts else []):
        if ci in dots:
            continue
        for si, s in enumerate(nseg[ci]):
            ln = L.dist(seg_at(c, s, 0.0), seg_at(c, s, 1.0))
            straight = not s[1]
            for at_start, node in ((True, s[0]), (False, s[2])):
                t = tangent(c, s, at_start)
                if t is None:
                    continue
                u = (0.15 if at_start else 0.85) if straight and ln >= 20 else near_u(c, s, at_start)
                probe = seg_at(c, s, u)
                nrm = next((c_ for c_ in ((-t[1], t[0]), (t[1], -t[0])) if on.inside(L.add(probe, L.mul(c_, 1.0)))), None)
                if nrm is None:
                    continue
                hit = on.exit(probe, nrm)
                if hit is None or hit[0] > limit:
                    continue
                th, hc, hs, hu, ev = hit
                # across a stroke the far side runs roughly parallel to this side; a ray
                # leaving through an edge at a steep angle went along the stroke (a
                # length, not a thickness: from a terminal's cut, into a join)
                if not parallel(ev, t, 25 if straight else 35):
                    continue
                target = th * k
                # the same ray in the derived glyph, through the same far segment
                cur, use_n = None, nrm
                dt = tangent(D[ci], dseg[ci][si], at_start)
                dprobe = seg_at(D[ci], dseg[ci][si], u)
                if dt is not None:
                    dn = (-dt[1], dt[0]) if L.dot((-dt[1], dt[0]), nrm) > 0 else (dt[1], -dt[0])
                    if od.inside(L.add(dprobe, L.mul(dn, 1.0))):
                        dh = od.exit(dprobe, dn)
                        if dh is not None and dh[0] < 4 * th and (dh[1], dh[2]) == (hc, hs):
                            cur, use_n, hu = dh[0], dn, dh[3]
                if cur is None:
                    cur = L.dot(L.sub(seg_at(D[hc], dseg[hc][hs], hu), dprobe), nrm)
                partner = (hc, dseg[hc][hs][0]) if hu < 0.03 else (hc, dseg[hc][hs][2]) if hu > 0.97 else None
                if partner == (ci, node):
                    continue
                excess = 0.0 if mode == "floor" and cur >= th else cur - target
                est.append({"ci": ci, "si": si, "node": node, "u": u, "n": use_n, "excess": excess, "far": (hc, hs),
                            "th": th, "line": straight and ln >= 20, "curve": not straight,
                            "act": abs(excess) >= max(2.0, 0.12 * target)})
    # a straight edge whose stroke has the same thickness near both ends in the master
    th_at = {}
    for e in est:
        if e["line"]:
            th_at.setdefault((e["ci"], e["si"]), []).append(e["th"])
    even = {key for key, v in th_at.items() if len(v) == 2 and abs(v[0] - v[1]) <= max(1.5, 0.04 * (v[0] + v[1]) / 2)}

    # too thick or too thin: move this side; when the far side moves as well, each half
    active = {(e["ci"], e["si"]) for e in est if e["act"]}

    def share(e):
        hc, hs = e["far"]
        if (hc, hs) not in active:
            return 1.0
        ends = (dseg[hc][hs][0], dseg[hc][hs][2])
        vertical = abs(e["n"][1]) >= abs(e["n"][0])
        return 0.5 if any(not held(hc, m)[1 if vertical else 0] for m in ends) else 1.0

    # inside corners where strokes meet (the crotch of v, the notch of N, the top of the
    # counter in 4): their depth into the join, measured along the corner's bisector,
    # scaled like a stroke, where extrapolation broke it
    junction, stroke_req = {}, {}
    for ci, c in enumerate(N if "joins" in parts else []):
        if ci in dots:
            continue
        for node in [i for i, p in enumerate(c) if p.type and not p.smooth]:
            si_in = next((j for j, s_ in enumerate(nseg[ci]) if s_[2] == node), None)
            si_out = next((j for j, s_ in enumerate(nseg[ci]) if s_[0] == node), None)
            if si_in is None or si_out is None:
                continue
            t_in, t_out = tangent(c, nseg[ci][si_in], False), tangent(c, nseg[ci][si_out], True)
            if t_in is None or t_out is None:
                continue
            b0 = L.add(L.mul(t_in, -1), t_out)
            if L.norm(b0) < 1e-6:
                continue
            b0 = L.unit(b0)
            p = (c[node].x, c[node].y)
            if on.inside(L.add(p, L.mul(b0, 1.5))):
                continue  # convex corner
            b = L.mul(b0, -1)
            if not on.inside(L.add(p, L.mul(b, 1.5))):
                continue
            hit = on.exit(p, b)
            if hit is None or hit[0] > limit:
                continue
            th, hc, hs, hu, ev = hit
            target = th * k
            pd = (D[ci][node].x, D[ci][node].y)
            far = None
            dtin = tangent(D[ci], dseg[ci][si_in], False)
            dtout = tangent(D[ci], dseg[ci][si_out], True)
            db = None
            if dtin is not None and dtout is not None:
                v = L.add(L.mul(dtin, -1), dtout)
                if L.norm(v) > 1e-6:
                    db = L.mul(L.unit(v), -1)
                    if L.dot(db, b) < 0:
                        db = L.mul(db, -1)
            if db is not None and od.inside(L.add(pd, L.mul(db, 1.5))):
                dh = od.exit(pd, db)
                if dh is not None and dh[1] == hc and dh[0] < 4 * th:
                    far = L.add(pd, L.mul(db, dh[0]))
            use_b = db or b
            if far is None:
                far = seg_at(D[hc], dseg[hc][hs], hu)
            want = L.sub(far, L.mul(use_b, target))
            delta = L.dot(L.sub(want, pd), use_b)
            # only corners extrapolation broke: pushed through the far side, or left
            # with under half the depth the master's proportions give (or over twice)
            depth = L.dot(L.sub(far, pd), use_b)
            if 0.5 * target <= depth <= 2.0 * target or abs(delta) < max(2.0, 0.12 * target):
                continue
            # the corner slides along the edge that has to stay where it is: one upright
            # or level in every master, else the straight one, else the one whose stroke
            # can't move as a whole; when both strokes can, along the bisector
            sides = (si_in, si_out)
            straight = [x for x in sides if not dseg[ci][x][1]]
            up = [x for x in straight if (ci, x) in upright]
            if len(up) == 2:
                continue  # a stem meeting a bar: their thicknesses place the corner
            movable = [x for x in straight if (ci, x) in side_of and (ci, x) not in upright]
            slide = up[0] if up else straight[0] if len(straight) == 1 else None
            if slide is None and len(straight) == 2 and len(movable) == 1:
                slide = next(x for x in straight if x not in movable)
            direction = use_b
            if slide is not None:
                e = tangent(D[ci], dseg[ci][slide], True)
                if e is not None:
                    e = e if L.dot(e, use_b) > 0 else L.mul(e, -1)
                    if L.dot(e, use_b) > math.cos(math.radians(75)):
                        direction = e
                    else:
                        slide = None
            J = L.mul(direction, delta / max(L.dot(direction, use_b), 1e-6))
            other = next((x for x in sides if x != slide), None) if slide is not None else None
            # move whole strokes (both sides by the same amount, so they keep their
            # thickness and taper), turning each about its far end or between two such
            # corners: the stroke meeting the edge that stays, or, at a crotch between
            # two strokes (v, w, <), both
            movers = [other] if other is not None and other in movable else \
                movable if slide is None and len(movable) == 2 else []
            if movers:
                for x in movers:
                    stroke_req.setdefault(tuple(sorted(((ci, x), side_of[(ci, x)]))), []).append(((ci, node), J))
            elif depth < 0:
                # a corner on its own thickens the strokes around it (the crotch of W
                # went from 27 to 32): only where extrapolation pushed it through the
                # far side
                junction[(ci, node)] = J

    # thickness wishes; a probe next to a corner the join rule moves measured the
    # collapsed join, not the stroke: the join rule decides that end
    at_join = set(junction) | {cn for reqs in stroke_req.values() for cn, _ in reqs}
    wish, line_probe, parallel_seg = {}, {}, set()
    for e in est:
        if (e["ci"], e["node"]) in at_join:
            continue
        vec = L.mul(e["n"], e["excess"] * share(e))
        if e["curve"]:
            if e["act"]:
                wish.setdefault((e["ci"], e["node"]), {}).setdefault(e["si"], []).append(vec)
        else:
            line_probe.setdefault((e["ci"], e["si"]), []).append((e["u"], vec, e["act"]))
            if e["act"] and (e["ci"], e["si"]) in even:
                parallel_seg.add((e["ci"], e["si"]))

    def mean(vs):
        return (sum(v[0] for v in vs) / len(vs), sum(v[1] for v in vs) / len(vs)) if vs else None

    def left_normal(ci, si):
        i0, _, i1 = dseg[ci][si]
        a, b = pt(D, ci, i0), pt(D, ci, i1)
        if L.dist(a, b) < 1e-6:
            return None, None
        t = L.unit(L.sub(b, a))
        return (-t[1], t[0]), t

    # straight edges: an offset along their normal at each end
    line_extra = {}
    for (A, B), reqs in stroke_req.items():
        n_a, t_a = left_normal(*A)
        if n_a is None:
            continue
        a0 = pt(D, A[0], dseg[A[0]][A[1]][0])
        ends = [pt(D, c_, dseg[c_][s_][j]) for c_, s_ in (A, B) for j in (0, 2)]
        ss = [L.dot(L.sub(q, a0), t_a) for q in ends]
        req = [(L.dot(L.sub(pt(D, *cn), a0), t_a), L.dot(J, n_a)) for cn, J in reqs]
        if max(r[0] for r in req) - min(r[0] for r in req) > 10:
            ms = sum(r[0] for r in req) / len(req)
            mf_ = sum(r[1] for r in req) / len(req)
            vs = sum((r[0] - ms) ** 2 for r in req)
            slope = sum((r[0] - ms) * (r[1] - mf_) for r in req) / vs

            def field(s_, ms=ms, mf_=mf_, slope=slope):
                return mf_ + slope * (s_ - ms)
        else:
            s_c = sum(r[0] for r in req) / len(req)
            f_c = sum(r[1] for r in req) / len(req)
            s_far = max(ss, key=lambda q: abs(q - s_c))

            def field(s_, s_c=s_c, f_c=f_c, s_far=s_far):
                return f_c * (s_ - s_far) / (s_c - s_far) if abs(s_c - s_far) > 1e-6 else f_c
        for c_, s_ in (A, B):
            n_e, _ = left_normal(c_, s_)
            if n_e is None:
                continue
            sgn = L.dot(n_a, n_e)
            for j in (0, 2):
                node = dseg[c_][s_][j]
                q = pt(D, c_, node)
                ex = line_extra.setdefault((c_, s_), {})
                ex[node] = ex.get(node, 0.0) + field(L.dot(L.sub(q, a0), t_a)) * sgn
    for (ci, node), J in junction.items():
        for si, s_ in enumerate(dseg[ci]):
            if node not in (s_[0], s_[2]):
                continue
            if s_[1]:
                wish.setdefault((ci, node), {}).setdefault(si, []).append(J)
            else:
                n_e, _ = left_normal(ci, si)
                if n_e is not None:
                    ex = line_extra.setdefault((ci, si), {})
                    ex[node] = ex.get(node, 0.0) + L.dot(J, n_e)

    edge_off = {}
    for ci, ss in enumerate(dseg):
        for si, (i0, hs, i1) in enumerate(ss):
            if hs:
                continue
            n_e, t = left_normal(ci, si)
            if n_e is None:
                continue
            offs = {i0: 0.0, i1: 0.0}
            probes = line_probe.get((ci, si), [])
            if any(a for _, _, a in probes):
                vals = [(u, L.dot(v, n_e)) for u, v, _ in probes]
                us = sorted({round(u, 4) for u, _ in vals})
                if (ci, si) in parallel_seg or (ci, si) in upright or len(us) < 2:
                    o = sum(v for _, v in vals) / len(vals)
                    offs = {i0: o, i1: o}
                else:
                    # a tapered stroke: the offset varies linearly along the edge
                    mu = sum(u for u, _ in vals) / len(vals)
                    mv = sum(v for _, v in vals) / len(vals)
                    sl = sum((u - mu) * (v - mv) for u, v in vals) / sum((u - mu) ** 2 for u, _ in vals)
                    offs = {i0: mv - sl * mu, i1: mv + sl * (1 - mu)}
            for node, o in line_extra.get((ci, si), {}).items():
                offs[node] = offs.get(node, 0.0) + o
            if any(abs(v) > 1e-9 for v in offs.values()):
                edge_off[(ci, si)] = (n_e, t, offs)

    moves = {}
    for ci, ss in enumerate(dseg):
        for node in [s_[0] for s_ in ss]:
            si_in = next(j for j, s_ in enumerate(ss) if s_[2] == node)
            si_out = next(j for j, s_ in enumerate(ss) if s_[0] == node)
            lines = []
            for x in (si_in, si_out):
                if ss[x][1]:
                    continue
                if (ci, x) in edge_off:
                    n_e, t_e, offs = edge_off[(ci, x)]
                    lines.append((n_e, t_e, offs.get(node, 0.0)))
                else:
                    n_e, t_e = left_normal(ci, x)
                    if n_e is not None:
                        lines.append((n_e, t_e, 0.0))  # an edge that stays: the node slides along it
            curves = [w for x in (si_in, si_out) if ss[x][1] for w in wish.get((ci, node), {}).get(x, [])]
            if len(lines) == 2:
                (n1, _, o1), (n2, _, o2) = lines
                if abs(o1) < 1e-9 and abs(o2) < 1e-9:
                    continue
                den = n1[0] * n2[1] - n1[1] * n2[0]
                if abs(den) < math.sin(math.radians(15)):
                    d = mean([L.mul(n1, o1), L.mul(n2, o2)])
                else:
                    d = ((o1 * n2[1] - o2 * n1[1]) / den, (n1[0] * o2 - n2[0] * o1) / den)
            elif len(lines) == 1:
                n1, t1, o1 = lines[0]
                along = sum(L.dot(w, t1) for w in curves) / len(curves) if curves else 0.0
                if abs(o1) < 1e-9 and abs(along) < 1e-9:
                    continue
                d = L.add(L.mul(n1, o1), L.mul(t1, along))
            else:
                if not curves:
                    continue
                # the estimates from the two segments at a node must agree; where they
                # don't (a join, a curve turning fast) the rule doesn't know: leave it
                if max((L.dist(x, y) for x in curves for y in curves), default=0) > 0.5 * stem_d:
                    continue
                d = mean(curves)
            # coordinates all masters share stay; y on a zone of the nearest master stays
            hx, hy = held(ci, node)
            moves[(ci, node)] = (0.0 if hx else d[0], 0.0 if hy else d[1])
    if DEBUG is not None:
        DEBUG.update(est=est, junction=junction, stroke_req=stroke_req, side_of=side_of, wish=wish, edge_off=edge_off,
                     parallel_seg=parallel_seg, line_probe=line_probe)
    # a node never moves further from its derived place than extrapolation moved it from
    # the nearest master, plus a stem: a correction, not a new drawing
    for (ci, node), (dx, dy) in list(moves.items()):
        pd = (D[ci][node].x, D[ci][node].y)
        bound = L.dist(pd, (N[ci][node].x, N[ci][node].y)) + stem_d
        if math.hypot(dx, dy) > bound:
            del moves[(ci, node)]
    return moves


HANDLE_MODES = ("translate", "blend", "scale")


def apply_moves(glyph, moves, handles="translate"):
    """Move nodes by moves {(contour, node): (dx, dy)} and their handles:
    translate  each handle with its own node (tangent directions kept)
    blend      the curve gets the node moves blended along it (a linear offset), then
               the handles at smooth nodes are lined up again
    scale      handles keep their direction and scale with their curve's chord"""
    for ci, c in enumerate(glyph.contours):
        pts = list(c.points)
        old = [(p.x, p.y) for p in pts]
        for node in [i for i, p in enumerate(pts) if p.type]:
            dx, dy = moves.get((ci, node), (0.0, 0.0))
            pts[node].x, pts[node].y = old[node][0] + dx, old[node][1] + dy
        for i0, hs, i1 in segs(pts):
            if not hs:
                continue
            d0, d1 = moves.get((ci, i0), (0.0, 0.0)), moves.get((ci, i1), (0.0, 0.0))
            first, last = hs[:len(hs) // 2 or 1], hs[len(hs) // 2 or 1:]
            if handles == "translate":
                for h in first:
                    pts[h].x, pts[h].y = L.add(old[h], d0)
                for h in last:
                    pts[h].x, pts[h].y = L.add(old[h], d1)
            elif handles == "blend":
                n = len(hs) + 1
                for j, h in enumerate(hs, 1):
                    w = j / n
                    pts[h].x, pts[h].y = L.add(old[h], L.add(L.mul(d0, 1 - w), L.mul(d1, w)))
            else:
                a0, a1 = old[i0], old[i1]
                b0, b1 = (pts[i0].x, pts[i0].y), (pts[i1].x, pts[i1].y)
                ch0, ch1 = L.dist(a0, a1), L.dist(b0, b1)
                r = ch1 / ch0 if ch0 > 1e-6 else 1.0
                for h in first:
                    pts[h].x, pts[h].y = L.add(b0, L.mul(L.sub(old[h], a0), r))
                for h in last:
                    pts[h].x, pts[h].y = L.add(b1, L.mul(L.sub(old[h], a1), r))
        if handles == "blend":
            n = len(pts)
            for i, p in enumerate(pts):
                a, b = pts[(i - 1) % n], pts[(i + 1) % n]
                if not p.type or not p.smooth or a.type or b.type:
                    continue
                va, vb = L.sub((p.x, p.y), (a.x, a.y)), L.sub((b.x, b.y), (p.x, p.y))
                if L.norm(va) < 1e-6 or L.norm(vb) < 1e-6:
                    continue
                u = L.unit(L.add(L.unit(va), L.unit(vb)))
                a.x, a.y = L.sub((p.x, p.y), L.mul(u, L.norm(va)))
                b.x, b.y = L.add((p.x, p.y), L.mul(u, L.norm(vb)))
    return max((math.hypot(dx, dy) for dx, dy in moves.values()), default=0.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--masters", nargs="+", required=True)
    ap.add_argument("--derived", nargs="+", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--mode", nargs="*", default=[], help="weight=full|floor")
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--max-stroke", type=float, default=2.0, help="ignore rays longer than this many stems (default 2)")
    ap.add_argument("--ref", help="reference master for the checks (default: the middle one, as audit.py)")
    opt = ap.parse_args(argv)

    def pairs(items):
        return {k: Path(v) for k, _, v in (x.partition("=") for x in items)}

    masters, derived = pairs(opt.masters), pairs(opt.derived)
    modes = {k: v for k, _, v in (x.partition("=") for x in opt.mode)}
    mf = {k: ufoLib2.Font.open(p) for k, p in masters.items()}
    stems = {k: L.ref_stem(f)[1] for k, f in mf.items()}
    out = Path(opt.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for label, path in derived.items():
        dst = out / path.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(path, dst)
        df = ufoLib2.Font.open(dst)
        sd = L.ref_stem(df)[1]
        near = min(mf, key=lambda m: abs(stems[m] - sd))
        k = sd / stems[near]
        mode = modes.get(label) or ("full" if k < 1 else "floor")
        nf = mf[near]
        zones = zone_ys(nf)
        changed, worst, reverted, used = 0, (0.0, None), [], {}
        from audit import DerivedChecker
        checker = DerivedChecker(list(mf.items()), (label, df), ref=opt.ref)

        def judge(name):
            sev = [i["severity"] for i in checker.issues(name)]
            return (sev.count("blocks"), sev.count("slows")), checker.geometry(name)

        def leans_or_wedges(before, after):
            """A stem that now leans, or a parallel-sided stroke that now tapers, by over
            1.5 units more than before (and beyond what edge_checks lets pass)."""
            for key, v in after.items():
                b = before.get(key)
                if b is None:
                    continue
                if key[0] == "turn" and v[0] > 1.5 and v[0] - b[0] > 1.0:
                    return True
                if key[0] == "wedge" and abs(v[0] - v[1]) > 3.0 and abs(v[0] - v[1]) - abs(b[0] - b[1]) > 1.5:
                    return True
            return False
        for name in (opt.glyphs or df.keys()):
            if name not in nf or name not in df or not df[name].contours:
                continue
            mg = [f[name] for f in mf.values()]
            before = df[name].copy()

            def variant(hm):
                # strokes first, then the joins on the result: setting the strokes of v
                # to their thickness already lifts its crotch; only joins still broken
                # after that are moved
                g = before.copy()
                w = 0.0
                for part in ("thickness", "joins"):
                    mv = plan_moves(name, g, nf[name], mg, k, mode, opt.max_stroke, stems[near], zones, sd, parts=(part,))
                    if mv and max(math.hypot(*v) for v in mv.values()) > 0.01:
                        w = max(w, apply_moves(g, mv, hm))
                return g, w
            if variant("translate")[1] <= 0.01:
                continue
            # try each way of moving the handles; keep the best, and only when the
            # audit's derived checks don't get worse than the plain derivation
            s0, g0 = judge(name)
            best = (s0, None, None, 0.0)
            for hm in HANDLE_MODES:
                df[name], w = variant(hm)
                sc, g = judge(name)
                if leans_or_wedges(g0, g):
                    continue  # never a stem that leans or a stroke that turns into a wedge
                if sc < best[0] or (sc == best[0] and best[1] is None):
                    best = (sc, df[name].copy(), hm, w)
            if best[1] is None:
                df[name] = before
                reverted.append(f"{name} {s0}")
                continue
            df[name] = best[1]
            w = best[3]
            used[best[2]] = used.get(best[2], 0) + 1
            changed += 1
            if w > worst[0]:
                worst = (w, name)
        # parts that closed up: move them apart and widen (kept only if the checks agree)
        widened = []
        for name in (opt.glyphs or df.keys()):
            if name not in nf or name not in df or not df[name].contours:
                continue
            before = df[name].copy()
            s0 = checker.score(name)
            sh = separate_parts(df[name], nf[name], df.info.unitsPerEm or 1000)
            if sh <= 0:
                continue
            if checker.score(name) > s0:
                df[name] = before
                continue
            widened.append(f"{name} +{sh:g}")
        # a part inside a counter that runs into it (the R of a registered sign at
        # Black), and a crossing part that slid off-centre (the bar of eth): kept only
        # if the checks agree
        others = []
        for name in (opt.glyphs or df.keys()):
            if name not in nf or name not in df or not df[name].contours:
                continue
            for fn, what in ((shrink_inner, "scaled"), (center_crossings, "slid")):
                before = df[name].copy()
                s0 = checker.score(name)
                r = fn(df[name], nf[name])
                if (fn is shrink_inner and r >= 1.0) or (fn is center_crossings and r <= 0):
                    continue
                if checker.score(name) > s0:
                    df[name] = before
                    continue
                others.append(f"{name} {what} {'×%.3f' % r if fn is shrink_inner else '%.0f units' % r}")
        if all(float(p.x).is_integer() for g in nf for c in g.contours for p in c.points[:3]):
            from fix import round_keeping_directions
            for name in (opt.glyphs or df.keys()):
                if name in df:
                    round_keeping_directions(df[name])
        df.save()
        print(f"{label}: stem {sd:.1f}, proportions from {near} (stem {stems[near]:.1f}, ratio {k:.3f}, mode {mode}): "
              f"{changed} glyphs changed, largest move {worst[0]:.1f} units ({worst[1]}) -> {dst}")
        print(f"  handles: {used}")
        if widened:
            print(f"  parts moved apart, glyph widened by as much: {', '.join(widened)}")
        if others:
            print(f"  inner parts scaled down, crossing parts re-centred: {', '.join(others)}")
        if reverted:
            print(f"  left as derived, every variant made the checks worse (blocks, slows before): {', '.join(reverted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
