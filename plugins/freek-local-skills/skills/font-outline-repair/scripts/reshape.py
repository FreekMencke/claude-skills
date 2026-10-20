#!/usr/bin/env python3
"""Repair single glyphs of a derived weight (Thin, Black) against its nearest drawn master.

usage:
  reshape.py OP TARGETS... --masters 300=Light.ufo 400=Regular.ufo 700=Bold.ufo \
             --derived 100=Thin.ufo 900=Black.ufo [--ref 300] [--from 700] [--write] [op options]

TARGETS name a glyph at a derived weight, GLYPH@WEIGHT, often with a contour and nodes:
GLYPH@WEIGHT:CONTOUR:A-B (node indices as audit.py and render.py number them). The
nearest master is the drawn master whose stem is closest to the derived weight's; k is
the stem ratio between them (on one family: Thin 28.4 / Light 61.1 = 0.465, Black 145 / Bold
118 = 1.229). Every op prints what it did and audit.py's derived checks for the glyph
(blocks, slows) before and after. Without --write nothing is saved. Rounds to whole
units, keeping handle directions, when the masters use whole units.

These come after derive.py and contrast.py, for what the contrast step can't fix. They
change only the derived UFOs, so a new derivation undoes them: keep the calls in one
script and run it again after every derivation. Look at each result enlarged (render.py,
beforeafter.py --overlay --ref) before keeping it: the checks find spots, the picture
decides.

ops
  copy-shape  G@W:C:A-B ... [--similar]
                                    the points between nodes A and B take the nearest
                                    master's (or --from's) shape, mapped per axis so A and
                                    B stay: curls and dents a few units deep that repredict
                                    leaves (each point under its --min-dev). --similar
                                    turns and scales the piece as a whole instead (the tip
                                    of a counter, whose ends lie at nearly one height).
  junction    G@W:C:J-K ...         a straight edge at node J meets a curve beyond node K
                                    through a short piece J-K (either way round: edge into J,
                                    or edge out of J), and extrapolation put J or K past the
                                    real meeting point so the piece folds back (the inside
                                    corner of a crossing: & at Thin; the joins of a cent
                                    sign's bar): J goes onto the crossing (the corner kept),
                                    K along the curve by the master's J-K x k, the piece cut
                                    from the curve and the curve trimmed, its shape kept.
  bar         G@W --edges c0:1+c0:2+..,c0:3+c1:0+..
                                    a straight bar or leg crossing curves: its two edges (the
                                    nodes on each, in any contour) made straight and parallel
                                    again at the master's width x k about the derived centre
                                    line, its end corners slid along their cuts, every join
                                    put where the new edge crosses the curve it meets.
  min-segment G@W:C:A-B ... --length L
                                    a short straight segment A-B that extrapolation turned
                                    round (a notch passing zero, the barb of an arrow): A and
                                    B slide along their other edges until A-B points the
                                    master's way and is L long.
  same-part   G@W --part P:C        every contour of G with the structure of contour C of
                                    glyph P becomes that contour, about its own centre (the
                                    dots of a dieresis as the i's dot, where the masters
                                    agree).
  copy-sync   COPY=BASE@W           COPY is BASE shifted in x in every master; at W it is
                                    made so again (tabular figures that drifted). Either can
                                    be the base: take the one the checks like better.
  bar-place   G@W --bar C --crossed C
                                    a free bar (four straight edges) crossing one stroke:
                                    put where the master has it along that stroke, with
                                    the master's overhang, angle and thickness as derived
                                    (the bar of eth sliding down its tail and past the
                                    advance width).
  inset       G@W ... [--keep-edge bottom|top] [--seat bottom]
                                    a single-stroke glyph evenly too heavy or light (the
                                    accents and cedilla, whose strokes grow slower than the
                                    stem): every edge moves in by half the median excess
                                    over master x k, except straight edges on the kept line;
                                    --seat moves it back onto its old bottom.
  chevron     G@W ...               a seven-node chevron (circumflex, caron shapes): each
                                    arm rebuilt about its centre line at master x k,
                                    parallel-sided, the apex the master's depth x k, the
                                    derived height kept. inset over-thins the apex.
  strokes     G@W ... [--nodes i,j] node by node to master x k, half each side; a node on a
                                    zone line slides along it or stays, and the node across
                                    takes the whole difference; curve middles still off get
                                    their handles moved. --nodes limits which may move.
  upright     G@W:C --nodes i,j     a stroke under a zone line (the arm of r, the hook of f
                                    under the ascender): those nodes move up or down until
                                    the stroke is master x k measured upright.
  follow-edge G@W:C:FIRST-LAST/BASE ...
                                    points along a nearly straight edge follow the master's
                                    departures from it times k (x only): wandering stems.
  offset-inner G@W:C --inner i,j,... --outer i,j,...
                                    the inside of a bend (nodes --inner, first and last
                                    kept) rebuilt as an offset of the outside (segments
                                    starting at --outer) at master x k, handles fitted.
  rebuild-stroke G@W[:C] ... [--centre own|ref] [--sides A-B,C-D] [--keep-nodes i,j]
                 [--keep-limits [LIST]] [--realign] [--smooth N]
                                    an open stroke rebuilt about a centre line at master x k:
                                    by default contour C between its two straight end cuts
                                    (S, s, the hook of ?); --sides names the two sides as
                                    node ranges, a side in several runs as A-B+C-D (the 3,
                                    whose inside its bar cuts in two), and --keep-nodes the
                                    junctions that stay (the bar's ends). --centre ref uses
                                    the master's centre line fitted onto the derived
                                    proportions (when the derived centre line is itself
                                    lumpy); --keep-limits keeps derived limits of the
                                    contour (alone: an S's bowls and overshoots, else a list
                                    from left,right,top,bottom,upper-left,lower-right);
                                    --realign lines handles up again where rounding bent
                                    short ones (keeps the way the checks like best).
  rebuild-outline G@W ... [--centre ref|own] [--smooth-centre [F]] [--fill-crossings [F]]
                  [--short F] [--keep-short] [--keep-limits [LIST]]
                                    the whole glyph, every contour, rebuilt about the master's
                                    centre lines at master x k, for strokes that run uneven
                                    through crossings and joins (&, a cent sign's bowl and
                                    bar, a barbed C). Widths are the largest disc in the
                                    master's ink touching each point, so they hold where
                                    strokes cross; the centre lines are fitted per axis onto
                                    the derived ones (--centre own: the derived centre lines).
                                    Corners go where the rebuilt edges meet; stroke-end cuts
                                    stay where derived; pieces shorter than F x stem
                                    (default 0.25, at most 1.5% of the em) with a corner at
                                    both ends (a chamfer, a
                                    notch) or at a stroke's outside (a terminal's flare)
                                    take the master's shape x k at the new corner
                                    (--keep-short: their derived shape); one running on
                                    smoothly from an inside corner is rebuilt with the edge
                                    it continues. Straight edges stay straight. A node that
                                    lands past a corner the rebuilt edges make (or past a
                                    kept node), so that the piece between them nearly
                                    vanished or turned round, slides back along its edge
                                    until the piece points the master's way: heavier than
                                    the master, little pieces at a crossing pass zero
                                    (Black &). Within half a stem of an end cut each edge
                                    keeps the width it has just before. --keep-nodes
                                    C:A-B,... keeps points as derived. --verbose lists the
                                    crossings it followed and the strokes it carried
                                    through. Run it after the spot fixes: it starts from
                                    the derived cuts and proportions. A thinner weight shows
                                    the master's small faults more: --smooth-centre takes
                                    out wiggles in its centre lines shorter than F stems
                                    (default 1; a local quadratic, so curves and stroke ends
                                    stay), --fill-crossings stops the master's thinning of a
                                    stroke into a crossing: each edge, followed through the
                                    crossing to where it goes on, keeps the width it has on
                                    either side over F stems each way (default 3; at most
                                    --fill-cap, 1.2; less when it bends the edge next to it).
                                    An edge is followed through a crossing even where the
                                    stroke turns there (up to 60 degrees: the bowl of &
                                    turning up into its arm); where it turns, the stroke is
                                    also carried through the crossing as one, as if the
                                    other weren't there: its edges before and after the
                                    crossing share one centre line, its own on each side
                                    up to 1.3 x 0.75 stem from the inside corners and a
                                    curve between that matches both in position and
                                    direction, so it stays parallel-sided and lines up
                                    across; its edges are then cut by the other's (a union
                                    of the continued stroke and the crossing one). Short pieces at a corner that run
                                    on smoothly from an inside corner are rebuilt with the
                                    edge they continue.
  union       G@W --part P          a glyph that is another glyph with a straight band laid
                                    over it (a cent sign: c and its bar): P at W moved where
                                    the masters put it (their offsets' trend over weight),
                                    united (booleanOperations) with G's band, found from its
                                    long parallel straight edges and ended at its cuts, at
                                    the master's width x k. G's points go where they sit on
                                    the same union in the master, a node within a few units
                                    of a corner onto it, curves fitted between; so G stays
                                    compatible. Fix P first: G takes its shape. For a part
                                    that lines up across the band where rebuilding G alone
                                    keeps the master's misalignment there.

Ops that move handles try them translated, blended and scaled (inset also with overlong
handles shortened) and keep whichever the checks like best.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

import ufoLib2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402
from contrast import HANDLE_MODES, Outline, apply_moves, seg_at, segs, tangent, zone_ys  # noqa: E402


class Ctx:
    """The fonts, the nearest master per derived weight, the checks."""

    def __init__(self, opt):
        def pairs(items):
            return {k: Path(v) for k, _, v in (x.partition("=") for x in items)}
        self.mpaths, self.dpaths = pairs(opt.masters), pairs(opt.derived)
        self.fonts = {k: ufoLib2.Font.open(p) for k, p in {**self.mpaths, **self.dpaths}.items()}
        self.stems = {k: L.ref_stem(f)[1] for k, f in self.fonts.items()}
        self.ref = opt.ref
        self.source = getattr(opt, "source", None)
        self.checkers = {}

    def near(self, w):
        if self.source:
            return self.source
        return min(self.mpaths, key=lambda m: abs(self.stems[m] - self.stems[w]))

    def k(self, w, ref=None):
        return self.stems[w] / self.stems[ref or self.near(w)]

    def checker(self, w):
        if w not in self.checkers:
            from audit import DerivedChecker
            self.checkers[w] = DerivedChecker([(m, self.fonts[m]) for m in self.mpaths], (w, self.fonts[w]), ref=self.ref)
        return self.checkers[w]

    def score(self, name, w):
        return self.checker(w).score(name)

    def best_of(self, name, w, attempt, modes=HANDLE_MODES):
        """attempt(mode) on a fresh copy of the glyph for each mode; keep the best by the
        derived checks (blocks, then slows; the first on a tie)."""
        f = self.fonts[w]
        before = f[name].copy()
        s0, best = self.score(name, w), None
        for mode in modes:
            f[name] = before.copy()
            out = attempt(mode)
            sc = self.score(name, w)
            if best is None or sc < best[0]:
                best = (sc, f[name].copy(), mode, out)
        f[name] = best[1]
        return best[2], s0, best[0], best[3]


def whole_units(ctx):
    return all(float(p.x).is_integer() for m in ctx.mpaths for g in list(ctx.fonts[m])[:20]
               for c in g.contours for p in c.points)


def round_glyph(ctx, g):
    if whole_units(ctx):
        from fix import round_keeping_directions
        round_keeping_directions(g)


def parse_target(t):
    """GLYPH@WEIGHT[:CONTOUR[:A-B]] -> (glyph, weight, contour or None, (a, b) or None, extra)."""
    name, _, rest = t.partition("@")
    parts = rest.split(":")
    w = parts[0]
    ci = int(parts[1]) if len(parts) > 1 else None
    span, extra = None, None
    if len(parts) > 2:
        sp, _, extra = parts[2].partition("/")
        a, _, b = sp.partition("-")
        span = (int(a), int(b or a))
        extra = int(extra) if extra else None
    return name, w, ci, span, extra


def ints(s):
    return [int(x) for x in s.split(",") if x != ""]


# --- measuring ---------------------------------------------------------------------

def node_rays(glyph, maxt):
    """(contour, node) -> (thickness, inward normal, exit point) across the stroke, along
    the normal of the node's longer adjacent segment; only rays leaving through an edge
    within 35 degrees of it count."""
    cs = [list(c.points) for c in glyph.contours]
    ol = Outline(cs)
    out = {}
    for ci, pts in enumerate(cs):
        sg = segs(pts)
        for k, s in enumerate(sg):
            prev = sg[k - 1]
            i = s[0]

            def chord(x):
                return L.dist((pts[x[0]].x, pts[x[0]].y), (pts[x[2]].x, pts[x[2]].y))
            t = tangent(pts, s, True) if chord(s) >= chord(prev) else tangent(pts, prev, False)
            if t is None:
                continue
            p = (pts[i].x, pts[i].y)
            n = (-t[1], t[0])
            if not ol.inside(L.add(p, L.mul(n, 1.0))):
                n = (t[1], -t[0])
                if not ol.inside(L.add(p, L.mul(n, 1.0))):
                    continue
            hit = ol.exit(p, n, skip=0.75)
            if not hit or hit[0] > maxt:
                continue
            e = hit[4]
            if L.norm(e) < 1e-9 or abs(L.cross(L.unit(e), t)) > math.sin(math.radians(35)):
                continue
            out[(ci, i)] = (hit[0], n, L.add(p, L.mul(n, hit[0])))
    return out


def mid_rays(glyph, maxt):
    """(contour, start node) -> (thickness, inward normal, segment) at each curve's middle."""
    cs = [list(c.points) for c in glyph.contours]
    ol = Outline(cs)
    out = {}
    for ci, pts in enumerate(cs):
        for s in segs(pts):
            if not s[1]:
                continue
            p, a, b = seg_at(pts, s, 0.5), seg_at(pts, s, 0.49), seg_at(pts, s, 0.51)
            t = L.unit(L.sub(b, a))
            n = (-t[1], t[0])
            if not ol.inside(L.add(p, L.mul(n, 1.0))):
                n = (t[1], -t[0])
            hit = ol.exit(p, n, skip=0.75)
            if not hit or hit[0] > maxt or abs(L.cross(L.unit(hit[4]), t)) > math.sin(math.radians(35)):
                continue
            out[(ci, s[0])] = (hit[0], n, s)
    return out


def top_y(glyph, x):
    polys = Outline([list(c.points) for c in glyph.contours]).polys
    ys = []
    for poly in polys:
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
                ys.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return max(ys)


def line_hits(poly, p, u):
    """Parameters t where the line p + t*u crosses the closed polygon, sorted."""
    ts = []
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        e = (x1 - x0, y1 - y0)
        den = u[0] * e[1] - u[1] * e[0]
        if abs(den) < 1e-12:
            continue
        w = (x0 - p[0], y0 - p[1])
        t = (w[0] * e[1] - w[1] * e[0]) / den
        s = (w[0] * u[1] - w[1] * u[0]) / den
        if 0 <= s < 1:
            ts.append(t)
    return sorted(ts)


def meet(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + s * d[0], p[1] + s * d[1])


def fit_cubic(p0, p3, t0, t3, samples):
    """Handles for a cubic p0 -> p3 leaving along t0 and arriving along -t3 that best fit
    the samples (least squares on the two handle lengths, chord-length parameters)."""
    import numpy as np
    pts = [p0] + list(samples) + [p3]
    d = np.cumsum([0.0] + [math.dist(a, b) for a, b in zip(pts, pts[1:])])
    ts = d / d[-1]
    A, rhs = np.zeros((2, 2)), np.zeros(2)
    P0, P3, T0, T3 = map(np.array, (p0, p3, t0, t3))
    for t, q in zip(ts[1:-1], pts[1:-1]):
        b0, b1, b2, b3 = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        a1, a2 = b1 * T0, b2 * T3
        r = np.array(q) - (P0 * (b0 + b1) + P3 * (b2 + b3))
        A += [[a1 @ a1, a1 @ a2], [a1 @ a2, a2 @ a2]]
        rhs += [a1 @ r, a2 @ r]
    chord = math.dist(p0, p3)
    try:
        al, be = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError:
        al = be = chord / 3
    if al <= 0.05 * chord or be <= 0.05 * chord:
        al = be = chord / 3
    return tuple(P0 + al * T0), tuple(P3 + be * T3)


# --- ops ---------------------------------------------------------------------------

def op_copy_shape(ctx, opt):
    for t in opt.targets:
        name, w, ci, (a, b), _ = parse_target(t)
        src = ctx.fonts[opt.source or ctx.near(w)][name]
        dst = ctx.fonts[w][name]
        s0 = ctx.score(name, w)
        ps, pd = list(src.contours[ci].points), list(dst.contours[ci].points)
        A, B, A2, B2 = ps[a], ps[b], pd[a], pd[b]

        def axis(s0_, s1, d0, d1):
            if abs(s1 - s0_) < 1:
                return lambda v: v + (d0 - s0_)
            kk = (d1 - d0) / (s1 - s0_)
            return lambda v: d0 + (v - s0_) * kk
        fx, fy = axis(A.x, B.x, A2.x, B2.x), axis(A.y, B.y, A2.y, B2.y)
        if opt.similar:
            # turned and scaled as a whole (A onto A', B onto B'): the piece keeps its
            # angles, where per axis a span of a few units in one direction blows it up
            # (the tip of a counter: its ends at nearly one height)
            za, zb, za2, zb2 = complex(A.x, A.y), complex(B.x, B.y), complex(A2.x, A2.y), complex(B2.x, B2.y)
            m = (zb2 - za2) / (zb - za) if zb != za else 1

            def sim(x, y):
                z = za2 + (complex(x, y) - za) * m
                return z.real, z.imag
        worst, n, i = 0.0, len(pd), (a + 1) % len(pd)
        while i != b:
            if opt.similar:
                nx, ny = (round(v) for v in sim(ps[i].x, ps[i].y))
            else:
                nx, ny = round(fx(ps[i].x)), round(fy(ps[i].y))
            worst = max(worst, math.hypot(nx - pd[i].x, ny - pd[i].y))
            pd[i].x, pd[i].y, pd[i].smooth = nx, ny, ps[i].smooth
            i = (i + 1) % n
        print(f"{name}@{w}: points {a + 1}-{b - 1} of contour {ci} from {opt.source or ctx.near(w)}'s shape, "
              f"largest move {worst:.1f}; checks {s0} -> {ctx.score(name, w)}")


def op_min_segment(ctx, opt):
    for t in opt.targets:
        name, w, ci, (a, b), _ = parse_target(t)
        g, ref = ctx.fonts[w][name], ctx.fonts[ctx.near(w)][name]
        p, q = list(g.contours[ci].points), list(ref.contours[ci].points)
        n = len(p)
        s0 = ctx.score(name, w)
        d = L.unit((q[b].x - q[a].x, q[b].y - q[a].y))
        pa, pb = (p[a].x, p[a].y), (p[b].x, p[b].y)
        ua = L.unit(L.sub(pa, (p[(a - 1) % n].x, p[(a - 1) % n].y)))   # a's other edge, towards a
        ub = L.unit(L.sub((p[(b + 1) % n].x, p[(b + 1) % n].y), pb))   # b's other edge, from b
        x = meet(pa, ua, pb, ub)
        # new a = x + s*ua, new b = x + r*ub, with b - a = length*d (Cramer)
        v = L.mul(d, opt.length)
        det = L.cross(ua, ub)
        r, s = L.cross(ua, v) / det, L.cross(ub, v) / det
        na, nb = L.add(x, L.mul(ua, s)), L.add(x, L.mul(ub, r))
        old = (pa, pb)
        p[a].x, p[a].y = round(na[0]), round(na[1])
        p[b].x, p[b].y = round(nb[0]), round(nb[1])
        print(f"{name}@{w}: segment {a}-{b} of contour {ci} {old} -> {(p[a].x, p[a].y), (p[b].x, p[b].y)}, "
              f"{opt.length:g} long the master's way; checks {s0} -> {ctx.score(name, w)}")


def op_same_part(ctx, opt):
    pname, _, pci = opt.part.partition(":")
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        f = ctx.fonts[w]
        part = f[pname].contours[int(pci or 0)].points
        xs, ys = [q.x for q in part], [q.y for q in part]
        pc = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        s0, sizes = ctx.score(name, w), []
        for c in f[name].contours:
            if len(c.points) != len(part) or [q.type for q in c.points] != [q.type for q in part]:
                continue
            cx, cy = [q.x for q in c.points], [q.y for q in c.points]
            dx = round((min(cx) + max(cx)) / 2 - pc[0])
            dy = round((min(cy) + max(cy)) / 2 - pc[1])
            sizes.append(f"{max(cx) - min(cx):g}x{max(cy) - min(cy):g}")
            for q, r in zip(c.points, part):
                q.x, q.y, q.smooth = r.x + dx, r.y + dy, r.smooth
        print(f"{name}@{w}: {len(sizes)} contour(s) {', '.join(sizes)} -> {max(xs) - min(xs):g}x{max(ys) - min(ys):g} "
              f"({pname} contour {pci or 0}), centres kept; checks {s0} -> {ctx.score(name, w)}")


def flat_points(g):
    return [p for c in g.contours for p in c.points]


def shifted_copy_map(a, b):
    """If glyph b is glyph a shifted in x (same points, maybe in another order or
    contour): (index map over all points b -> a, shift); else None."""
    if len(a.contours) != len(b.contours):
        return None
    pa, pb = flat_points(a), flat_points(b)
    if not pa or len(pa) != len(pb):
        return None
    dx = round(min(p.x for p in pb) - min(p.x for p in pa))
    where = {(p.x, p.y, bool(p.type)): i for i, p in enumerate(pa)}
    m = [where.get((p.x - dx, p.y, bool(p.type))) for p in pb]
    return (m, dx) if None not in m and len(set(m)) == len(m) else None


def op_copy_sync(ctx, opt):
    for t in opt.targets:
        pair, _, w = t.partition("@")
        copy, _, base = pair.partition("=")
        maps = {}
        for m in ctx.mpaths:
            r = shifted_copy_map(ctx.fonts[m][base], ctx.fonts[m][copy])
            if r is None:
                raise SystemExit(f"{copy} is not a shifted {base} in {m}")
            maps[m] = r
        if len({tuple(x) for x, _ in maps.values()}) != 1:
            raise SystemExit(f"{copy}'s point order relative to {base} differs between the masters")
        idx = next(iter(maps.values()))[0]
        f = ctx.fonts[w]
        s0 = ctx.score(copy, w)
        src, dst = flat_points(f[base]), flat_points(f[copy])
        # the shift at W: from the right end of the base line, as in the masters
        dx = round(max(p.x for p in dst if p.y == 0) - max(p.x for p in src if p.y == 0)) \
            if any(p.y == 0 for p in src) else round(min(p.x for p in dst) - min(p.x for p in src))
        worst = 0.0
        for i, p in enumerate(dst):
            q = src[idx[i]]
            worst = max(worst, math.hypot(q.x + dx - p.x, q.y - p.y))
            p.x, p.y = q.x + dx, q.y
        print(f"{copy}@{w}: {base} shifted {dx:+d} (masters: {', '.join(f'{d:+d}' for _, d in maps.values())}), "
              f"largest move {worst:.1f}; checks {s0} -> {ctx.score(copy, w)}")


def op_bar_place(ctx, opt):
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        g, ref = ctx.fonts[w][name], ctx.fonts[ctx.near(w)][name]
        s0 = ctx.score(name, w)

        def frame(gl):
            P = [(p.x, p.y) for p in gl.contours[opt.bar].points]
            a = ((P[0][0] + P[3][0]) / 2, (P[0][1] + P[3][1]) / 2)
            b = ((P[1][0] + P[2][0]) / 2, (P[1][1] + P[2][1]) / 2)
            u = L.unit(L.sub(b, a))
            ln = L.dist(a, b)
            stroke = Outline([list(gl.contours[opt.crossed].points)]).polys[0]
            ts = [x for x in line_hits(stroke, a, u) if 0 < x < ln]
            return a, u, ln, ts, stroke, P
        aR, uR, lnR, tsR, _, _ = frame(ref)
        over = (tsR[0] + (lnR - tsR[-1])) / 2
        cy = aR[1] + uR[1] * (tsR[0] + tsR[-1]) / 2
        a, u, ln, ts, stroke, P = frame(g)
        lo, hi = min(x for x, _ in P), max(x for x, _ in P)
        xs = [x for x in line_hits(stroke, (0, cy), (1, 0)) if lo - ln / 2 < x < hi + ln / 2]
        c = ((xs[0] + xs[-1]) / 2, cy)
        hits = line_hits(stroke, c, u)
        t0, t1 = max(x for x in hits if x <= 0), min(x for x in hits if x >= 0)
        na = L.add(c, L.mul(u, t0 - over))
        nb = L.add(c, L.mul(u, t1 + over))
        pts = g.contours[opt.bar].points
        oa = ((pts[0].x + pts[3].x) / 2, (pts[0].y + pts[3].y) / 2)
        ob = ((pts[1].x + pts[2].x) / 2, (pts[1].y + pts[2].y) / 2)
        for i, (o, nw) in ((0, (oa, na)), (3, (oa, na)), (1, (ob, nb)), (2, (ob, nb))):
            pts[i].x = round(pts[i].x + nw[0] - o[0])
            pts[i].y = round(pts[i].y + nw[1] - o[1])
        print(f"{name}@{w}: bar crosses at y {cy:.0f} with overhang {over:.0f} as in {ctx.near(w)} "
              f"(was {ts[0]:.0f}/{ln - ts[-1]:.0f}), right end {max(p.x for p in pts)} against width {g.width}; "
              f"checks {s0} -> {ctx.score(name, w)}")


def stroke_excess(ctx, name, w, k):
    ref = ctx.fonts[ctx.near(w)]
    maxt = 2 * ctx.stems[ctx.near(w)]
    rl, rt = node_rays(ref[name], maxt), node_rays(ctx.fonts[w][name], maxt)
    pairs = [(rt[q][0], rl[q][0]) for q in rt if q in rl]
    med = statistics.median(t for t, _ in pairs)
    diffs = [t - tl * k for t, tl in pairs if t < 1.5 * med]
    return statistics.median(diffs), len(diffs)


def inset(glyph, delta, fixed_y=None, mode="translate"):
    """Every edge moves inward by delta, except straight edges on y = fixed_y; corners go
    where the moved edges meet; handles follow as apply_moves does in mode."""
    moves = {}
    for ci, c in enumerate(glyph.contours):
        pts = list(c.points)
        n = len(pts)
        area = sum(pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y for i in range(n))
        left = area > 0

        def inward(t):
            return (-t[1], t[0]) if left else (t[1], -t[0])
        sg = segs(pts)

        def fixed(s):
            return (fixed_y is not None and not s[1]
                    and abs(pts[s[0]].y - fixed_y) < 0.5 and abs(pts[s[2]].y - fixed_y) < 0.5)
        for k, s in enumerate(sg):
            prev = sg[k - 1]
            i = s[0]
            t_in, t_out = tangent(pts, prev, False), tangent(pts, s, True)
            d_in, d_out = (0.0 if fixed(prev) else delta), (0.0 if fixed(s) else delta)
            n_in, n_out = inward(t_in), inward(t_out)
            p = (pts[i].x, pts[i].y)
            if abs(L.cross(t_in, t_out)) < math.sin(math.radians(3)):
                moves[(ci, i)] = L.mul(L.unit(L.add(n_in, n_out)), (d_in + d_out) / 2)
                continue
            a, b = L.add(p, L.mul(n_in, d_in)), L.add(p, L.mul(n_out, d_out))
            q = L.add(a, L.mul(t_in, L.cross(L.sub(b, a), t_out) / L.cross(t_in, t_out)))
            moves[(ci, i)] = L.sub(q, p)
    apply_moves(glyph, moves, mode)


def clamp_overlong(glyph, keep=0.95):
    n = 0
    for c in glyph.contours:
        pts = list(c.points)
        for i0, hs, i1 in segs(pts):
            if len(hs) != 2:
                continue
            p0, p1, p2, p3 = pts[i0], pts[hs[0]], pts[hs[1]], pts[i1]
            d1, d2 = (p1.x - p0.x, p1.y - p0.y), (p2.x - p3.x, p2.y - p3.y)
            den = d1[0] * d2[1] - d1[1] * d2[0]
            if abs(den) < 1e-9:
                continue
            s = ((p3.x - p0.x) * d2[1] - (p3.y - p0.y) * d2[0]) / den
            r = ((p3.x - p0.x) * d1[1] - (p3.y - p0.y) * d1[0]) / den
            if s > 0 and r > 0:
                if s < 1:
                    p1.x, p1.y = p0.x + d1[0] * s * keep, p0.y + d1[1] * s * keep
                    n += 1
                if r < 1:
                    p2.x, p2.y = p3.x + d2[0] * r * keep, p3.y + d2[1] * r * keep
                    n += 1
    return n


def op_inset(ctx, opt):
    from fontTools.pens.boundsPen import BoundsPen
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        f = ctx.fonts[w]
        k = ctx.k(w)
        g0 = f[name]
        fy = None
        if opt.keep_edge == "bottom":
            fy = min(p.y for c in g0.contours for p in c.points)
        elif opt.keep_edge == "top":
            fy = max(p.y for c in g0.contours for p in c.points)
        excess, n = stroke_excess(ctx, name, w, k)

        def attempt(mode, name=name, fy=fy, excess=excess):
            g = f[name]
            inset(g, excess / 2, fixed_y=fy, mode=mode.split("+")[0])
            if mode.endswith("+clamp"):
                clamp_overlong(g)
            if opt.seat == "bottom":
                bp = BoundsPen(f)
                g.draw(bp)
                bp0 = BoundsPen(f)
                before.draw(bp0)
                dy = bp0.bounds[1] - bp.bounds[1]
                for c in g.contours:
                    for p in c.points:
                        p.y += dy
            round_glyph(ctx, g)
        before = g0.copy()
        mode, s0, s1, _ = ctx.best_of(name, w, attempt, HANDLE_MODES + ("translate+clamp", "scale+clamp"))
        after, _ = stroke_excess(ctx, name, w, k)
        print(f"{name}@{w}: strokes {excess:+.1f} off {ctx.near(w)} x {k:.3f} (median of {n} nodes) -> {after:+.1f}; "
              f"handles {mode}; checks {s0} -> {s1}")


def op_chevron(ctx, opt):
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        k = ctx.k(w)
        lt, g = ctx.fonts[ctx.near(w)][name], ctx.fonts[w][name]
        s0 = ctx.score(name, w)
        P = [(p.x, p.y) for p in g.contours[0].points]
        Q = [(p.x, p.y) for p in lt.contours[0].points]
        if len(P) != 7 or any(p.type != "line" for p in g.contours[0].points) or not (P[0][1] == P[1][1] == P[3][1] == P[4][1]):
            raise SystemExit(f"{name}: not a seven-node chevron (0/1 left foot, 2 inside apex, 3/4 right foot, 5/6 top)")

        def dist_to_line(p, a, b):
            return abs(L.cross(L.unit(L.sub(b, a)), L.sub(p, a)))

        def line_x(p, q, y):
            return p[0] + (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1])
        tl, tr = dist_to_line(Q[1], Q[0], Q[6]) * k, dist_to_line(Q[3], Q[4], Q[5]) * k
        apex = (Q[5][1] - Q[2][1]) * k
        base, top, y2 = P[0][1], P[5][1], P[2][1]
        before = (dist_to_line(P[1], P[0], P[6]), dist_to_line(P[3], P[4], P[5]), top - y2)
        cl0, cl2 = ((P[0][0] + P[1][0]) / 2, base), ((line_x(P[0], P[6], y2) + P[2][0]) / 2, y2)
        cr0, cr2 = ((P[3][0] + P[4][0]) / 2, base), ((line_x(P[4], P[5], y2) + P[2][0]) / 2, y2)
        dl, dr = L.unit(L.sub(cl2, cl0)), L.unit(L.sub(cr2, cr0))
        nl, nr = (-dl[1], dl[0]), (dr[1], -dr[0])
        out_l, in_l = L.add(cl0, L.mul(nl, tl / 2)), L.sub(cl0, L.mul(nl, tl / 2))
        out_r, in_r = L.add(cr0, L.mul(nr, tr / 2)), L.sub(cr0, L.mul(nr, tr / 2))
        flat = (1.0, 0.0)
        new = [None] * 7
        new[0], new[1] = meet(out_l, dl, (0, base), flat), meet(in_l, dl, (0, base), flat)
        new[3], new[4] = meet(in_r, dr, (0, base), flat), meet(out_r, dr, (0, base), flat)
        new[2] = meet(in_l, dl, in_r, dr)
        ytop = new[2][1] + apex
        new[6], new[5] = meet(out_l, dl, (0, ytop), flat), meet(out_r, dr, (0, ytop), flat)
        if new[6][0] >= new[5][0]:
            raise SystemExit(f"{name}: the arms meet below the top")
        sy = (top - base) / (ytop - base)
        for p, (x, y) in zip(g.contours[0].points, new):
            p.x, p.y = round(x), round(base + (y - base) * sy)
        P2 = [(p.x, p.y) for p in g.contours[0].points]
        after = (dist_to_line(P2[1], P2[0], P2[6]), dist_to_line(P2[3], P2[4], P2[5]), P2[5][1] - P2[2][1])
        print(f"{name}@{w}: arms {before[0]:.1f}/{before[1]:.1f} -> {after[0]:.1f}/{after[1]:.1f} "
              f"({ctx.near(w)} x k {tl:.1f}/{tr:.1f}), apex {before[2]:.0f} -> {after[2]:.0f} ({apex:.1f}), "
              f"height kept; checks {s0} -> {ctx.score(name, w)}")


def set_strokes(ctx, name, w, k, only, mode):
    ref = ctx.fonts[ctx.near(w)]
    th = ctx.fonts[w]
    maxt = 2 * ctx.stems[ctx.near(w)]
    zones = zone_ys(th) | zone_ys(ref)
    gl, gt = ref[name], th[name]
    rl, rt = node_rays(gl, maxt), node_rays(gt, maxt)
    nodes = {(ci, i): (p.x, p.y) for ci, c in enumerate(gt.contours) for i, p in enumerate(c.points) if p.type}

    def on_zone(key):
        return any(abs(nodes[key][1] - z) <= 1 for z in zones)

    def locked(key):
        return on_zone(key) and key in rt and abs(rt[key][1][1]) > 0.7
    want = {}
    for key, (tt, n, ex) in rt.items():
        if key not in rl or (only is not None and key[1] not in only):
            continue
        target = rl[key][0] * k
        if abs(tt - target) <= max(2.0, 0.12 * target):
            continue
        partner = min(nodes, key=lambda q: L.dist(nodes[q], ex))
        want[key] = (tt - target, n, partner)
    moves, report = {}, []
    for key, (diff, n, partner) in want.items():
        half = diff / 2
        if locked(partner) or (only is not None and partner[1] not in only):
            half = diff
        if on_zone(key):
            if abs(n[1]) > 0.7:
                continue
            moves[key] = (half / n[0], 0.0)
        else:
            moves[key] = (n[0] * half, n[1] * half)
        report.append(diff)
    if moves:
        apply_moves(gt, moves, mode)
    # curve middles still off: both handles along the middle normal by 4/3 of half the difference
    ml, mt = mid_rays(gl, maxt), mid_rays(th[name], maxt)
    mids = 0
    for key, (tt, n, s) in mt.items():
        if key not in ml or (only is not None and key[1] not in only):
            continue
        diff = tt - ml[key][0] * k
        if abs(diff) <= max(2.0, 0.12 * ml[key][0] * k):
            continue
        pts = th[name].contours[key[0]].points
        for i in s[1]:
            pts[i].x += n[0] * diff / 2 * 4 / 3
            pts[i].y += n[1] * diff / 2 * 4 / 3
        mids += 1
    round_glyph(ctx, th[name])
    worst = max((math.hypot(*v) for v in moves.values()), default=0.0)
    return (f"{len(moves)} nodes moved" + (f" (off {min(report):+.1f} to {max(report):+.1f}, largest move {worst:.1f})"
                                           if report else "") + f", {mids} curve middles evened")


def op_strokes(ctx, opt):
    only = set(ints(opt.nodes)) if opt.nodes else None
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        k = ctx.k(w)
        mode, s0, s1, msg = ctx.best_of(name, w, lambda m, name=name, w=w: set_strokes(ctx, name, w, k, only, m))
        print(f"{name}@{w}: to {ctx.near(w)} x {k:.3f} node by node: {msg}; handles {mode}; checks {s0} -> {s1}")


def op_upright(ctx, opt):
    nodes = ints(opt.nodes)
    for t in opt.targets:
        name, w, ci, _, _ = parse_target(t)
        ci = ci or 0
        k = ctx.k(w)

        def attempt(mode, name=name, w=w):
            a, g = ctx.fonts[ctx.near(w)][name], ctx.fonts[w][name]
            pa, pb = a.contours[ci].points, g.contours[ci].points
            moves, rep = {}, []
            for i in nodes:
                want = (top_y(a, pa[i].x) - pa[i].y) * k
                have = top_y(g, pb[i].x) - pb[i].y
                moves[(ci, i)] = (0.0, have - want)
                rep.append(f"{i}: {have:.0f}->{want:.0f}")
            apply_moves(g, moves, mode)
            round_glyph(ctx, g)
            return ", ".join(rep)
        mode, s0, s1, msg = ctx.best_of(name, w, attempt)
        print(f"{name}@{w}: upright to {ctx.near(w)} x {k:.3f} ({msg}); handles {mode}; checks {s0} -> {s1}")


def op_follow_edge(ctx, opt):
    for t in opt.targets:
        name, w, ci, (first, last), base = parse_target(t)
        k = ctx.k(w)
        a, b = ctx.fonts[ctx.near(w)][name].contours[ci].points, ctx.fonts[w][name].contours[ci].points
        s0 = ctx.score(name, w)
        worst = 0.0
        for i in range(first, last + 1):
            x = b[base].x + (a[i].x - a[base].x) * k
            worst = max(worst, abs(x - b[i].x))
            b[i].x = math.floor(x + 0.5)
        print(f"{name}@{w}: points {first}-{last} follow {ctx.near(w)}'s edge x {k:.3f} (from point {base}), "
              f"largest move {worst:.1f}; checks {s0} -> {ctx.score(name, w)}")


def op_offset_inner(ctx, opt):
    inner, outer = ints(opt.inner), set(ints(opt.outer))
    for t in opt.targets:
        name, w, ci, _, _ = parse_target(t)
        ci = ci or 0
        k = ctx.k(w)
        gr, gt = ctx.fonts[ctx.near(w)][name], ctx.fonts[w][name]
        s0 = ctx.score(name, w)
        pr, pt = list(gr.contours[ci].points), list(gt.contours[ci].points)
        sgr, sgt = segs(pr), segs(pt)
        dense = [(seg_at(pr, s, j / 200), si, j / 200) for si, s in enumerate(sgr) if s[0] in outer for j in range(201)]
        olt = Outline([pt])

        def target(si, u, th):
            a, b = seg_at(pt, sgt[si], max(u - 0.002, 0)), seg_at(pt, sgt[si], min(u + 0.002, 1))
            q = seg_at(pt, sgt[si], u)
            d = L.unit(L.sub(b, a))
            n = (-d[1], d[0])
            if not olt.inside(L.add(q, L.mul(n, 1.0))):
                n = (d[1], -d[0])
            return L.add(q, L.mul(n, th * k))
        seg_of = {s[0]: s for s in sgr}
        new, curves = {}, {}
        for a, b in zip(inner, inner[1:]):
            s, samp = seg_of[a], []
            for j in range(13):
                p = seg_at(pr, s, j / 12)
                q, si, u = min(dense, key=lambda x: L.dist(x[0], p))
                samp.append(target(si, u, L.dist(q, p)))
            curves[(a, b)] = samp
            new.setdefault(a, samp[0])
            new[b] = samp[-1]
        new[inner[0]] = (pt[inner[0]].x, pt[inner[0]].y)
        new[inner[-1]] = (pt[inner[-1]].x, pt[inner[-1]].y)
        old = {i: (pt[i].x, pt[i].y) for i in inner}
        for i in inner[1:-1]:
            pt[i].x, pt[i].y = new[i]
        for (a, b), samp in curves.items():
            s = [x for x in segs(pt) if x[0] == a][0]
            if len(s[1]) != 2:
                continue
            p0, p3 = new[a], new[b]
            h0, h3 = pt[s[1][0]], pt[s[1][1]]
            sr = seg_of[a]
            ra, rb = (pr[sr[0]].x, pr[sr[0]].y), (pr[sr[2]].x, pr[sr[2]].y)
            cd = L.unit(L.sub(rb, ra))
            if all(abs(L.cross(cd, L.sub((pr[h].x, pr[h].y), ra))) < 1.5 for h in sr[1]):
                h0.x, h0.y = L.add(p0, L.mul(L.sub(p3, p0), 1 / 3))      # straight in the master: straight
                h3.x, h3.y = L.add(p0, L.mul(L.sub(p3, p0), 2 / 3))
                continue
            t0 = L.unit(L.sub((h0.x, h0.y), old[a])) if a == inner[0] else L.unit(L.sub(samp[1], samp[0]))
            t3 = L.unit(L.sub((h3.x, h3.y), old[b])) if b == inner[-1] else L.unit(L.sub(samp[-2], samp[-1]))
            (h0.x, h0.y), (h3.x, h3.y) = fit_cubic(p0, p3, t0, t3, samp[1:-1])
        round_glyph(ctx, gt)
        worst = max(math.dist(old[i], new[i]) for i in inner)
        print(f"{name}@{w}: inside of the bend offset from the outside at {ctx.near(w)} x {k:.3f}, "
              f"largest move {worst:.1f}; checks {s0} -> {ctx.score(name, w)}")


LIMITS_S = "upper-left,lower-right,top,bottom"


def stroke_limits(pts, which):
    """Outer limits of a contour (points with .type): left, right, top, bottom of its box,
    or upper-left (the left of its upper half) and lower-right (the right of its lower
    half) for an S, whose terminals sit right of the upper bowl and left of the lower."""
    poly = Outline([pts]).polys[0]
    top, bottom = max(y for _, y in poly), min(y for _, y in poly)
    mid = (top + bottom) / 2
    val = {"left": lambda: min(x for x, _ in poly), "right": lambda: max(x for x, _ in poly),
           "top": lambda: top, "bottom": lambda: bottom,
           "upper-left": lambda: min(x for x, y in poly if y > mid),
           "lower-right": lambda: max(x for x, y in poly if y < mid)}
    return {w: val[w]() for w in which}


def keep_limits(pts, want, which):
    """Scale and shift the points per axis so the contour's limits are want again (two
    limits on an axis: scale and shift; one: shift only)."""
    now = stroke_limits(pts, which)
    out = []
    for axis, los, his in (("x", ("upper-left", "left"), ("lower-right", "right")), ("y", ("bottom",), ("top",))):
        lo = next((w for w in los if w in want), None)
        hi = next((w for w in his if w in want), None)
        if lo and hi:
            s = (want[hi] - want[lo]) / (now[hi] - now[lo])
            f = (lambda v, s=s, lo=lo: want[lo] + (v - now[lo]) * s)
        elif lo or hi:
            d = want[lo or hi] - now[lo or hi]
            s, f = 1.0, (lambda v, d=d: v + d)
        else:
            continue
        for p in pts:
            if axis == "x":
                p.x = f(p.x)
            else:
                p.y = f(p.y)
        out.append(f"{axis}{s:.3f}")
    return " ".join(out)


def realign(pts, nodes, tol=1.0, rule="best"):
    """At these nodes (fitted with one tangent), line the two handles up again when
    rounding to whole units bent them apart by over tol degrees (a short handle rounded
    one unit sideways turns several degrees): turn one handle onto the other's line,
    rule "best" whichever leaves the smaller bend once rounded, "short" the shorter."""
    def bend(va, vb):
        return abs(math.degrees(math.atan2(va[0] * vb[1] - va[1] * vb[0], va[0] * vb[0] + va[1] * vb[1])))
    n = len(pts)
    for i in nodes:
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        p = pts[i]
        if a.type is not None or b.type is not None:
            continue
        va, vb = (p.x - a.x, p.y - a.y), (b.x - p.x, b.y - p.y)
        la, lb = math.hypot(*va), math.hypot(*vb)
        if la < 1e-6 or lb < 1e-6 or bend(va, vb) <= tol:
            continue
        nb = (round(p.x + va[0] / la * lb), round(p.y + va[1] / la * lb))     # b onto a's line
        na = (round(p.x - vb[0] / lb * la), round(p.y - vb[1] / lb * la))     # a onto b's line
        turn_b = la >= lb if rule == "short" else \
            bend(va, (nb[0] - p.x, nb[1] - p.y)) <= bend((p.x - na[0], p.y - na[1]), vb)
        if turn_b:
            b.x, b.y = nb
        else:
            a.x, a.y = na


def op_rebuild_stroke(ctx, opt):
    import numpy as np
    which = [w for w in (opt.keep_limits or "").split(",") if w]
    kept = set(ints(opt.keep_nodes)) if opt.keep_nodes else set()
    for t in opt.targets:
        name, w, ci, _, _ = parse_target(t)
        k = ctx.k(w)
        gr, gt = ctx.fonts[ctx.near(w)][name], ctx.fonts[w][name]
        if ci is None:
            if len(gt.contours) != 1:
                raise SystemExit(f"{name}: has {len(gt.contours)} contours: name one, {name}@{w}:CONTOUR")
            ci = 0
        s0 = ctx.score(name, w)
        pr, pt = list(gr.contours[ci].points), list(gt.contours[ci].points)
        want = stroke_limits(pt, which) if which else None
        sg = segs(pt)
        if opt.sides:
            sides = []
            for spec in opt.sides.split(","):
                side = []
                for rng in spec.split("+"):          # a side in several runs (the inside of a 3, cut by its bar)
                    a, _, b = rng.partition("-")
                    a, b = int(a), int(b)
                    i0 = next(i for i, s in enumerate(sg) if s[0] == a)
                    for j in range(len(sg)):
                        s = sg[(i0 + j) % len(sg)]
                        side.append(s)
                        if s[2] == b:
                            break
                sides.append(side)
            if len(sides) != 2:
                raise SystemExit(f"{name}: --sides needs two sides, A-B,C-D (a side in runs: A-B+C-D)")
        else:
            cuts = [(s[0], s[2]) for s in sg if not s[1]]
            if len(cuts) != 2:
                raise SystemExit(f"{name}: needs exactly two straight end cuts (or --sides), found {len(cuts)}")
            cut_starts = {a for a, _ in cuts}
            start = next(i for i, s in enumerate(sg) if s[0] == cuts[0][1])
            order = sg[start:] + sg[:start]
            sides, cur = [], []
            for s in order:
                if s[0] in cut_starts:
                    sides.append(cur)
                    cur = []
                else:
                    cur.append(s)
            sides = [x for x in sides + [cur] if x]
            if len(sides) != 2:
                raise SystemExit(f"{name}: expected two sides between the cuts, found {len(sides)}")
        orig = [(p.x, p.y) for p in pt]
        steps = 16
        dr = [[seg_at(pr, s, j / 60) for s in x for j in range(61)] for x in sides]
        dt = [[seg_at(pt, s, j / 60) for s in x for j in range(61)] for x in sides]

        def nearest(p, poly):
            return min(poly, key=lambda q: (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2)
        plan, pairs = {}, []
        for si, side in enumerate(sides):
            for s in side:
                row = []
                for j in range(steps + 1):
                    u = j / steps
                    p_r, p_t = seg_at(pr, s, u), seg_at(pt, s, u)
                    q_r, q_t = nearest(p_r, dr[1 - si]), nearest(p_t, dt[1 - si])
                    c = ((p_t[0] + q_t[0]) / 2, (p_t[1] + q_t[1]) / 2)
                    c_r = ((p_r[0] + q_r[0]) / 2, (p_r[1] + q_r[1]) / 2)
                    row.append([c, L.unit(L.sub(p_t, q_t)), L.dist(p_r, q_r) * k, c_r, L.unit(L.sub(p_r, q_r))])
                    pairs.append((c_r, c))
                plan[s[0]] = (s, row)
        if opt.centre == "ref":
            ax, bx = np.polyfit([a[0] for a, _ in pairs], [b[0] for _, b in pairs], 1)
            ay, by = np.polyfit([a[1] for a, _ in pairs], [b[1] for _, b in pairs], 1)
            for s, row in plan.values():
                for r in row:
                    r[0] = (ax * r[3][0] + bx, ay * r[3][1] + by)
                    r[1] = L.unit((r[4][0] / ax, r[4][1] / ay))
        if opt.smooth:
            for side in sides:
                seq = [(s[0], j) for s in side for j in range(steps + 1)]
                cs = [plan[a][1][j][0] for a, j in seq]
                for i, (a, j) in enumerate(seq):
                    wd = min(opt.smooth, i, len(cs) - 1 - i)
                    win = cs[i - wd:i + wd + 1]
                    plan[a][1][j][0] = (sum(x for x, _ in win) / len(win), sum(y for _, y in win) / len(win))
        samples = {a: [L.add(r[0], L.mul(r[1], r[2] / 2)) for r in row] for a, (s, row) in plan.items()}
        old = {i: (p.x, p.y) for i, p in enumerate(pt) if p.type}
        new = {}
        for a, (s, row) in plan.items():
            new.setdefault(s[0], samples[a][0])
            new[s[2]] = samples[a][-1]
        for i in kept & set(new):
            new[i] = old[i]                      # a junction that stays (the waist of a 3)
        for i, xy in new.items():
            pt[i].x, pt[i].y = xy
        by_end = {plan[a][0][2]: a for a in plan}

        def tangent_at(i):
            before = samples[by_end[i]][-2] if i in by_end else None
            after = samples[i][1] if i in samples else None
            if before is None:
                return L.unit(L.sub(after, new[i]))
            if after is None:
                return L.unit(L.sub(new[i], before))
            return L.unit(L.sub(after, before))
        for a, (s, row) in plan.items():
            if len(s[1]) == 2:
                b = s[2]
                # a kept node keeps its own handle direction, so the part next to it still joins
                t0 = L.unit(L.sub(orig[s[1][0]], orig[a])) if a in kept else tangent_at(a)
                t3 = L.unit(L.sub(orig[s[1][1]], orig[b])) if b in kept else L.mul(tangent_at(b), -1)
                c1, c2 = fit_cubic(new[a], new[b], t0, t3, samples[a][1:-1])
                (pt[s[1][0]].x, pt[s[1][0]].y), (pt[s[1][1]].x, pt[s[1][1]].y) = c1, c2
        worst = max(L.dist(old[i], new[i]) for i in new)
        scale = ""
        if which:
            scale = f", derived {'/'.join(which)} kept ({keep_limits(pt, want, which)})"
        round_glyph(ctx, gt)
        note = ""
        if opt.realign:
            nodes = [i for i in new if i not in kept]
            rebuilt = ctx.fonts[w][name].copy()

            def attempt(rule, nodes=nodes, rebuilt=rebuilt, name=name, w=w, ci=ci):
                ctx.fonts[w][name] = rebuilt.copy()
                if rule != "none":
                    realign(list(ctx.fonts[w][name].contours[ci].points), nodes, rule=rule)
            rule, _, _, _ = ctx.best_of(name, w, attempt, ("none", "best", "short"))
            note = f", handles re-lined: {rule}"
        print(f"{name}@{w}: contour {ci} rebuilt about the {'master' if opt.centre == 'ref' else 'derived'} centre line at "
              f"{ctx.near(w)} x {k:.3f}{scale}{note}, largest move {worst:.1f}; checks {s0} -> {ctx.score(name, w)}")


LIMITS_BOX = "left,right,top,bottom"


def ink_side(ol, pts):
    """+1 when the ink lies left of the contour's direction, -1 when right (vote of the
    segments' middles)."""
    votes = 0
    for s in segs(pts):
        p, a, b = seg_at(pts, s, 0.5), seg_at(pts, s, 0.45), seg_at(pts, s, 0.55)
        if L.dist(a, b) < 1e-9:
            continue
        t = L.unit(L.sub(b, a))
        votes += 1 if ol.inside(L.add(p, (-t[1], t[0]))) else -1
    return 1 if votes >= 0 else -1


def outline_balls(cs, steps, cut_segs=(), cap=None, near=0.0):
    """Every segment of every contour sampled at steps+1 points: the point, unit tangent,
    inward normal and the radius of the largest disc inside the ink that touches the
    outline there (the shrinking ball: half the stroke's width, measured square to the
    stroke even where two strokes cross). Segments sharing a convex corner with the
    sample's own segment don't limit it, so a stroke's end cut doesn't pinch the disc
    near the end; nor do the end cuts in cut_segs, nor points closer than near on the
    sample's own or the next two segments either way (a slight bend at a node would
    otherwise pinch it to a few units). Radii over cap are None."""
    import numpy as np
    ol = Outline(cs)
    dense, owner = [], []
    for ci, pts in enumerate(cs):
        for si, s in enumerate(segs(pts)):
            if (ci, si) in cut_segs:
                continue
            poly = [seg_at(pts, s, j / 32) for j in range(33)]
            length = sum(L.dist(a, b) for a, b in zip(poly, poly[1:]))
            n = max(8, int(length / 2))
            dense += [seg_at(pts, s, j / n) for j in range(n)]
            owner += [(ci, si)] * n
    Q = np.array(dense)
    own = np.array([ci * 10000 + si for ci, si in owner])
    q_ci = np.array([ci for ci, _ in owner])
    q_si = np.array([si for _, si in owner])
    out = []
    for ci, pts in enumerate(cs):
        side = ink_side(ol, pts)
        sg = segs(pts)
        rows = []
        for si, s in enumerate(sg):
            convex = []
            for nb, at in (((si - 1) % len(sg), s[0]), ((si + 1) % len(sg), s[2])):
                a_in = tangent(pts, sg[(si - 1) % len(sg)], False) if at == s[0] else tangent(pts, s, False)
                a_out = tangent(pts, s, True) if at == s[0] else tangent(pts, sg[(si + 1) % len(sg)], True)
                if a_in and a_out and L.cross(a_in, a_out) * side > math.sin(math.radians(25)):
                    convex.append(ci * 10000 + nb)
            P, T, N = [], [], []
            for j in range(steps + 1):
                u = j / steps
                p = seg_at(pts, s, u)
                a, b = seg_at(pts, s, max(u - 0.004, 0)), seg_at(pts, s, min(u + 0.004, 1))
                t = L.unit(L.sub(b, a)) if L.dist(a, b) > 1e-9 else (1.0, 0.0)
                P.append(p)
                T.append(t)
                N.append((-t[1] * side, t[0] * side))
            Pa, Na = np.array(P), np.array(N)
            V = Q[None, :, :] - Pa[:, None, :]
            dot = (V * Na[:, None, :]).sum(2)
            d2 = (V ** 2).sum(2)
            gap = np.abs(q_si - si)
            gap = np.minimum(gap, len(sg) - gap)
            close = ((q_ci == ci) & (gap <= 2))[None, :] & (d2 < near * near)
            ok = (dot > 0.02 * np.sqrt(d2)) & (d2 > 4.0) & ~np.isin(own, convex)[None, :] & ~close
            r = np.where(ok, d2 / (2 * np.where(ok, dot, 1.0)), np.inf).min(1)
            rows.append([(P[j], T[j], N[j], None if (cap and r[j] > cap) or not np.isfinite(r[j]) else float(r[j]))
                         for j in range(steps + 1)])
        out.append(rows)
    return out


def bend_at(pts, sg, si):
    """Degrees the outline turns at the start node of segment si (180 when it can't tell)."""
    a, b = tangent(pts, sg[si - 1], False), tangent(pts, sg[si], True)
    if not (a and b):
        return 180.0
    return abs(math.degrees(math.atan2(L.cross(a, b), L.dot(a, b))))


def steady_ends(br, R, kind, cut_segs, steps, reach):
    """Each side of a stroke-end cut: the disc radius of the samples within reach of the
    cut's corner becomes that of the first sample beyond (along the long segments that
    lead to the cut). br rows are (point, tangent, normal, radius), changed in place."""
    for ci, si in cut_segs:
        sg = segs(R[ci])
        n = len(sg)
        cut_a = (R[ci][sg[si][0]].x, R[ci][sg[si][0]].y)
        cut_b = (R[ci][sg[si][2]].x, R[ci][sg[si][2]].y)
        for corner, step in ((cut_a, -1), (cut_b, 1)):
            seq = []
            k = (si + step) % n
            while kind[ci][k] == "long" and len(seq) < 4 * (steps + 1):
                js = range(steps, -1, -1) if step < 0 else range(steps + 1)
                seq += [(k, j) for j in js]
                k = (k + step) % n
                if k == si:
                    break
            near = [(k, j) for k, j in seq if L.dist(br[ci][k][j][0], corner) < reach]
            beyond = next(((k, j) for k, j in seq if L.dist(br[ci][k][j][0], corner) >= reach
                           and br[ci][k][j][3] is not None), None)
            if not near or beyond is None:
                continue
            h = br[ci][beyond[0]][beyond[1]][3]
            for k, j in near:
                br[ci][k][j] = br[ci][k][j][:3] + (h,)


def _dist_crotch(p, crotch):
    return min(L.dist(p, q) for q in crotch) if crotch else math.inf


def clean_centres(side, crotch, r_near, C0):
    """Centres of an edge's samples clear of the crossing (1.3 r_near from any inside
    corner). side: (contour, (segment, sample), point) from the crossing outward."""
    return [C0[c][si][j] for c, (si, j), p in side
            if C0[c][si][j] is not None and _dist_crotch(p, crotch) >= 1.3 * r_near]


def _half_fit(sides, crotch, r_near, C0):
    """A stroke's centre line on one side of a crossing, from its edges' clean centres:
    (point at the clean end nearest the crossing, unit tangent there pointing into the
    crossing, quadratic evaluator) or None."""
    import numpy as np
    pts = [(c, _dist_crotch(p, crotch)) for side in sides for c_, (si, j), p in side
           for c in [C0[c_][si][j]] if c is not None and _dist_crotch(p, crotch) >= 1.3 * r_near]
    if len(pts) < 6:
        return None
    A = np.array([c for c, _ in pts])
    mean = A.mean(axis=0)
    axis = np.linalg.svd(A - mean)[2][0]
    tt = (A - mean) @ axis
    fx, fy = np.polyfit(tt, A[:, 0], 2), np.polyfit(tt, A[:, 1], 2)
    k0 = min(range(len(pts)), key=lambda i: pts[i][1])          # the clean end
    t0 = float(tt[k0])
    end = (float(np.polyval(fx, t0)), float(np.polyval(fy, t0)))
    tan = L.unit((float(np.polyval(np.polyder(fx), t0)), float(np.polyval(np.polyder(fy), t0))))
    if L.dot(tan, L.sub(tuple(mean), end)) > 0:                 # point away from the clean part
        tan = L.mul(tan, -1)
    return end, tan, (lambda t: (float(np.polyval(fx, t)), float(np.polyval(fy, t)))), mean, axis


def carry_stroke(group, crotch, r_near, C0, N0, hw, stem):
    """One stroke running into a crossing, seen from its edges (sides: (contour,
    (segment, sample), point) from the crossing outward). Within 1.3 r_near of an inside
    corner each edge's centre and direction are replaced, and its width never drops below
    its clean part's. A stroke that goes on out of the crossing (its sides fall in two
    halves, the edges before and after) gets one curve from its clean centre line on one
    side to the other, matching both in position and direction, so it lines up across
    the crossing without a kink; a stroke that ends in it is carried on as a quadratic.
    Returns how many samples changed."""
    import numpy as np
    # the halves: sides whose clean centres lie together
    halves = []
    for side in group:
        cs_ = clean_centres(side, crotch, r_near, C0)
        for h in halves:
            other = [c for sd in h for c in clean_centres(sd, crotch, r_near, C0)]
            if cs_ and other and statistics.median(min(L.dist(p, q) for q in other) for p in cs_) < 0.15 * stem:
                h.append(side)
                break
        else:
            halves.append([side])
    fits = [_half_fit(h, crotch, r_near, C0) for h in halves]
    if any(f is None for f in fits):
        return 0
    if len(halves) == 2:
        (a, ta, *_), (b, tb, *_) = fits
        ln = 0.4 * L.dist(a, b)
        P = [a, L.add(a, L.mul(ta, ln)), L.add(b, L.mul(tb, ln)), b]
        curve = [L.cubic_at(*P, i / 200) for i in range(201)]
    else:
        end, tan, f, mean, axis = fits[0]
        curve = None
    n = 0
    for side in group:
        clean = [(c, si, j) for c, (si, j), p in side
                 if C0[c][si][j] is not None and _dist_crotch(p, crotch) >= 1.3 * r_near]
        h_clean = statistics.median([hw[c][si][j] for c, si, j in clean]) if clean else None
        for c, (si, j), p in side:
            dc = _dist_crotch(p, crotch)
            if dc >= 1.3 * r_near or C0[c][si][j] is None:
                continue
            wgt = 1.0 if dc < 1.1 * r_near else (1.3 * r_near - dc) / (0.2 * r_near)
            wgt = wgt * wgt * (3 - 2 * wgt)
            if curve is not None:
                k_ = min(range(len(curve)), key=lambda i: L.dist(curve[i], C0[c][si][j]))
                base = curve[k_]
                tan = L.unit(L.sub(curve[min(k_ + 1, 200)], curve[max(k_ - 1, 0)]))
            else:
                t = float((np.array(C0[c][si][j]) - mean) @ axis)
                base = f(t)
                tan = L.unit(L.sub(f(t + 0.5), f(t - 0.5)))
            nn = (-tan[1], tan[0])
            if L.dot(nn, N0[c][si][j]) < 0:
                nn = (tan[1], -tan[0])
            C0[c][si][j] = L.add(L.mul(base, wgt), L.mul(C0[c][si][j], 1 - wgt))
            N0[c][si][j] = L.unit(L.add(L.mul(nn, wgt), L.mul(N0[c][si][j], 1 - wgt)))
            if h_clean is not None:
                hw[c][si][j] = max(hw[c][si][j], wgt * h_clean + (1 - wgt) * hw[c][si][j])
            n += 1
    return n


def short_piece(pts, sg, si, side):
    """A short segment kept whole (the master's x k at its corner), or rebuilt with the
    edge it runs on from: a corner at both ends (a chamfer, a notch) or one at a stroke's
    outside (a terminal's flare) is kept; one running smoothly from an inside corner (the
    rounding into a crossing) is part of that edge: kept whole there, it stepped."""
    a, b = bend_at(pts, sg, si), bend_at(pts, sg, (si + 1) % len(sg))
    if min(a, b) >= 10:
        return True
    if max(a, b) < 10:
        return False
    k_ = si if a >= 10 else (si + 1) % len(sg)
    d_in, d_out = tangent(pts, sg[k_ - 1], False), tangent(pts, sg[k_], True)
    return bool(d_in and d_out and L.cross(d_in, d_out) * side > 0)


def edge_runs(pts, ks, steps):
    """Runs of long segments that join smoothly or bend under 10 degrees, as (segment,
    sample) lists; corners, cuts and short pieces end them."""
    sg = segs(pts)
    runs, cur = [], []
    for si in range(len(sg)):
        if ks[si] != "long":
            if cur:
                runs.append(cur)
            cur = []
            continue
        if cur and bend_at(pts, sg, si) > 10:
            runs.append(cur)
            cur = []
        cur += [(si, j) for j in range(steps + 1)]
    if cur:
        if runs and runs[0][0][0] == 0 and ks[-1] == "long" and bend_at(pts, sg, 0) <= 10:
            runs[0] = cur + runs[0]                 # the run through the contour's start
        else:
            runs.append(cur)
    return runs


def op_rebuild_outline(ctx, opt):
    """Every contour of the glyph rebuilt about the master's centre lines at master x k."""
    import numpy as np
    steps = 16
    centre = opt.centre or "ref"
    which = [w for w in (opt.keep_limits or "").split(",") if w]
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        k = ctx.k(w)
        stem = ctx.stems[ctx.near(w)]
        gr, gt = ctx.fonts[ctx.near(w)][name], ctx.fonts[w][name]
        R = [list(c.points) for c in gr.contours]
        T = [list(c.points) for c in gt.contours]
        if [[p.type for p in c] for c in R] != [[p.type for p in c] for c in T]:
            raise SystemExit(f"{name}: the master and {w} don't have the same points")
        s0 = ctx.score(name, w)
        old = [[(p.x, p.y) for p in c] for c in T]
        want = None
        if which:
            box = Outline(T).polys
            want = {"left": min(x for poly in box for x, _ in poly), "right": max(x for poly in box for x, _ in poly),
                    "top": max(y for poly in box for _, y in poly), "bottom": min(y for poly in box for _, y in poly)}
        # what each segment is, from the master: a stroke's end cut (a straight line
        # between two convex corners whose sides run opposite ways), a short piece at a
        # corner (an ink trap, the rounding into a crotch: kept as derived, moved with
        # its corner), or a long edge (rebuilt)
        kept_nodes = {}
        for spec in (opt.keep_nodes.split(",") if opt.keep_nodes and ":" in opt.keep_nodes else []):
            c_, _, rng = spec.partition(":")
            a_, _, b_ = rng.partition("-")
            n_ = len(T[int(c_)])
            a_, b_ = int(a_), int(b_ or a_)
            kept_nodes.setdefault(int(c_), set()).update((a_ + d) % n_ for d in range((b_ - a_) % n_ + 1))
        kind, cut_segs = [], set()
        olr = Outline(R)
        # short: F x the master's stem, but no more than 1.5% of the em (at Bold a quarter
        # stem is 30 units and took ordinary segments of the small Black counters for
        # corner details)
        upm = ctx.fonts[ctx.near(w)].info.unitsPerEm or 1000
        short_len = min(opt.short * stem, 0.015 * upm * opt.short / 0.25)
        for ci, pts in enumerate(R):
            sg = segs(pts)
            side = ink_side(olr, pts)
            ks = []
            for si, s in enumerate(sg):
                a, b = (pts[s[0]].x, pts[s[0]].y), (pts[s[2]].x, pts[s[2]].y)
                chord = L.dist(a, b)
                prev, nxt = sg[si - 1], sg[(si + 1) % len(sg)]
                d_in, d_out = tangent(pts, prev, False), tangent(pts, nxt, True)
                d = tangent(pts, s, True)
                is_cut = (not s[1] and not pts[s[0]].smooth and not pts[s[2]].smooth and chord < 2.2 * stem
                          and d_in and d_out and d and L.dot(d_in, d_out) < -0.7
                          and L.cross(d_in, d) * side > 0 and L.cross(d, d_out) * side > 0)
                if is_cut:
                    ks.append("cut")
                    cut_segs.add((ci, si))
                elif chord < short_len and short_piece(pts, sg, si, side):
                    ks.append("short")
                else:
                    ks.append("long")
            kind.append(ks)
        cap = 2.5 * stem
        br = outline_balls(R, steps, cut_segs, cap, near=0.3 * stem)
        bt = outline_balls(T, steps, cut_segs, cap * k * 1.5, near=0.3 * stem * k)
        # robust half-widths: a straight edge keeps one width (its median); elsewhere a
        # spike over 1.2 x the median of its neighbourhood (a disc swelling into a
        # crossing) is cut back to that
        for ci, rows in enumerate(br):
            seq = [(si, j) for si in range(len(rows)) if kind[ci][si] == "long" for j in range(steps + 1)]
            hs = [rows[si][j][3] for si, j in seq]
            for x, (si, j) in enumerate(seq):
                win = [h for h in (hs[(x + d) % len(hs)] for d in range(-24, 25)) if h is not None]
                med = statistics.median(win) if win else None
                h = rows[si][j][3]
                if med is not None:
                    h = med if h is None else min(h, 1.2 * med)
                rows[si][j] = rows[si][j][:3] + (h,)
            for si, rs in enumerate(rows):
                s = segs(R[ci])[si]
                if not s[1] and kind[ci][si] == "long":
                    vals = [r[3] for r in rs if r[3] is not None]
                    if vals:
                        m = statistics.median(vals)
                        rows[si] = [r[:3] + (m,) for r in rs]
        # at a stroke's end cut the disc runs past the end (the cut doesn't limit it), so
        # it comes out too big there and pulls the edge in: within half a stem of the cut
        # each side keeps the width it has just before (the foot of 9 tapered to 21 units
        # where Light x k gives 27)
        steady_ends(br, R, kind, cut_segs, steps, 0.5 * stem)
        # the widths the edges are drawn at: the master's, or with --fill-crossings no
        # thinner inside a crossing or join than just outside it
        hw = [[[r[3] for r in rs] for rs in rows] for rows in br]
        C0 = [[[L.add(r[0], L.mul(r[2], r[3])) if r[3] is not None else None for r in rs] for rs in rows] for rows in br]
        N0 = [[[r[2] for r in rs] for rs in rows] for rows in br]
        runs = []
        for ci, pts in enumerate(R):
            for run in edge_runs(pts, kind[ci], steps):
                P = [br[ci][si][j][0] for si, j in run]
                S_ = [0.0]
                for a_, b_ in zip(P, P[1:]):
                    S_.append(S_[-1] + L.dist(a_, b_))
                runs.append((ci, run, P, [br[ci][si][j][1] for si, j in run], S_))
        lift_note = ""
        if opt.fill_crossings:
            # an edge that runs into a crossing goes on out of it as another edge (travel
            # directions within 60 degrees, a stroke may turn through the crossing as the
            # bowl of & turns up into its arm; the gap along their mean direction, through
            # ink): over reach either side, its width is filled up to the lower of the
            # widest before and the widest after (a valley across the crossing; at most +20%)
            reach = opt.fill_crossings * stem
            links = []
            for u, (ci, run, P, Tn, S_) in enumerate(runs):
                best = None
                for v, (cj, run2, P2, T2, S2) in enumerate(runs):
                    d = L.sub(P2[0], P[-1])
                    dist = L.norm(d)
                    if v == u or not (1.0 < dist < 2.5 * stem):
                        continue
                    if L.dot(Tn[-1], T2[0]) < math.cos(math.radians(60)):
                        continue
                    mid_dir = L.unit(L.add(Tn[-1], T2[0]))
                    if L.dot(L.unit(d), mid_dir) < math.cos(math.radians(35)):
                        continue
                    if abs(L.cross(mid_dir, d)) > 0.6 * stem or not olr.inside(L.mul(L.add(P2[0], P[-1]), 0.5)):
                        continue
                    if best is None or dist < best[0]:
                        best = (dist, v)
                if best:
                    links.append((u, best[1]))
            if opt.verbose:
                for u, v in links:
                    (ci, run, *_), (cj, run2, *_) = runs[u], runs[v]
                    sgu, sgv = segs(R[ci]), segs(R[cj])
                    print(f"   link c{ci}:..{sgu[run[-1][0]][2]} -> c{cj}:{sgv[run2[0][0]][0]}..")
            worst = (1.0, "")
            for u, v in links:
                ci, run, _, _, S_ = runs[u]
                cj, run2, _, _, S2 = runs[v]
                seq = [(ci, run[z]) for z in range(len(run)) if S_[-1] - S_[z] < reach] + \
                      [(cj, run2[z]) for z in range(len(run2)) if S2[z] < reach]
                vals = [hw[c][si][j] for c, (si, j) in seq]
                pre, suf, m = [], [], -math.inf
                for x_ in vals:
                    m = max(m, -math.inf if x_ is None else x_)
                    pre.append(m)
                m = -math.inf
                for x_ in reversed(vals):
                    m = max(m, -math.inf if x_ is None else x_)
                    suf.append(m)
                suf.reverse()
                for (c, (si, j)), a_, b_ in zip(seq, pre, suf):
                    h0 = br[c][si][j][3]
                    if h0 is None:
                        continue
                    val = max(hw[c][si][j], min(a_, b_, opt.fill_cap * h0))
                    hw[c][si][j] = val
                    if val / h0 > worst[0]:
                        s_ = segs(R[c])[si]
                        worst = (val / h0, f"c{c} {s_[0]}-{s_[2]}")
            lift_note = (f", {len(links)} edges filled through crossings (most x{worst[0]:.2f} at {worst[1]})"
                         if links else ", no crossing to fill")
            # the stroke carried on through the crossing, as if the other stroke weren't
            # there: within 0.75 stem of an inside corner its centre line is dragged into
            # the junction (a disc there is held by the other stroke's edges, and the edge
            # bent in: the arm of & pinched where it meets the leg), so there the centre
            # line and width are one curve fitted to the stroke's clean parts either side;
            # its edges are then cut where they meet the other stroke's (as a union would)
            crotch = []
            for cc, pts in enumerate(R):
                sg_ = segs(pts)
                side = ink_side(olr, pts)
                for si, s in enumerate(sg_):
                    if pts[s[0]].smooth:
                        continue
                    d_in, d_out = tangent(pts, sg_[si - 1], False), tangent(pts, s, True)
                    if d_in and d_out and L.cross(d_in, d_out) * side < -math.sin(math.radians(25)):
                        crotch.append((pts[s[0]].x, pts[s[0]].y))
            r_near, span, bridged = 0.75 * stem, 2.5 * stem, 0
            sides = []
            for u, v in links:
                ci, run, P, Tu, S_ = runs[u]
                cj, run2, P2, Tv, S2 = runs[v]
                if L.dot(Tu[-1], Tv[0]) > math.cos(math.radians(20)):
                    continue        # a stroke going straight through: filling is enough
                sides.append([(ci, run[z], P[z]) for z in range(len(run)) if S_[-1] - S_[z] < span])
                sides.append([(cj, run2[z], P2[z]) for z in range(len(run2)) if S2[z] < span])
            # one stroke turning under another (the bowl of & into its arm, under the leg)
            # is carried through as one: the edge before and after the crossing (a link)
            # and the stroke's two edges (their clean centres lie together) share one
            # centre line, a smooth curve fitted to the clean parts on both sides, so the
            # stroke stays parallel-sided and lines up across the other. Edge by edge it
            # pinched or flared; side by side it stopped lining up across the leg.
            parent = list(range(len(sides)))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x
            for k_ in range(0, len(sides), 2):
                parent[find(k_)] = find(k_ + 1)
            cents = [clean_centres(sd, crotch, r_near, C0) for sd in sides]
            for a in range(len(sides)):
                for b in range(a + 1, len(sides)):
                    if len(cents[a]) < 4 or len(cents[b]) < 4:
                        continue
                    d = statistics.median(min(L.dist(p, q) for q in cents[b]) for p in cents[a])
                    if d < 0.15 * stem:
                        parent[find(a)] = find(b)
            comp = {}
            for a in range(len(sides)):
                comp.setdefault(find(a), []).append(a)
            groups = list(comp.values())
            for group in groups:
                n_ = carry_stroke([sides[g] for g in group], crotch, r_near, C0, N0, hw, stem)
                bridged += n_
                if opt.verbose and n_:
                    names = []
                    for g in group:
                        c_, (si_, _), _ = sides[g][0]
                        s_ = segs(R[c_])[si_]
                        names.append(f"c{c_} {s_[0]}-{s_[2]}")
                    print(f"   carried on together: {' + '.join(names)} ({n_} samples)")
            if bridged:
                lift_note += f", strokes carried through crossings ({bridged} samples)"
        if opt.smooth_centre:
            # the master's centre line and widths along each edge as a local quadratic
            # (tricube weights over smooth_centre x stem of arc): wiggles shorter than
            # that go, curves stay, the ends aren't pulled in
            half = opt.smooth_centre * stem / 2
            for ci, run, _, _, S_ in runs:
                idx = [z for z, (si, j) in enumerate(run) if C0[ci][si][j] is not None]
                if len(idx) < 5:
                    continue
                Sa = np.array([S_[z] for z in idx])
                Cx = np.array([C0[ci][run[z][0]][run[z][1]][0] for z in idx])
                Cy = np.array([C0[ci][run[z][0]][run[z][1]][1] for z in idx])
                Hw = np.array([hw[ci][run[z][0]][run[z][1]] for z in idx])
                out = []
                for z in range(len(idx)):
                    ds = Sa - Sa[z]
                    sel = np.abs(ds) <= half
                    if sel.sum() < 5:
                        out.append(None)
                        continue
                    wts = (1 - (np.abs(ds[sel]) / half) ** 3) ** 3 + 1e-6
                    A = np.vstack([np.ones(sel.sum()), ds[sel], ds[sel] ** 2]).T * np.sqrt(wts)[:, None]
                    fx = np.linalg.lstsq(A, Cx[sel] * np.sqrt(wts), rcond=None)[0]
                    fy = np.linalg.lstsq(A, Cy[sel] * np.sqrt(wts), rcond=None)[0]
                    fh = np.linalg.lstsq(A[:, :2], Hw[sel] * np.sqrt(wts), rcond=None)[0]
                    out.append(((fx[0], fy[0]), (fx[1], fy[1]), fh[0]))
                for z, o in zip(idx, out):
                    if o is None:
                        continue
                    si, j = run[z]
                    if not segs(R[ci])[si][1]:
                        continue        # a straight edge stays as the master has it (smoothed
                                        # with the curve it runs into, B's counters tilted)
                    (cx, cy), tan, hh = o
                    if math.hypot(*tan) < 1e-9:
                        continue
                    t_ = L.unit(tan)
                    n_ = (-t_[1], t_[0])
                    if L.dot(n_, N0[ci][si][j]) < 0:
                        n_ = (t_[1], -t_[0])
                    C0[ci][si][j], N0[ci][si][j], hw[ci][si][j] = (float(cx), float(cy)), n_, float(hh)
        # the master's centre line fitted onto the derived proportions, per axis
        pairs = []
        for ci in range(len(R)):
            for si in range(len(br[ci])):
                if kind[ci][si] != "long":
                    continue
                for (pr, _, nr, hr), (pt_, _, nt, ht) in zip(br[ci][si], bt[ci][si]):
                    if hr is not None and ht is not None:
                        pairs.append((L.add(pr, L.mul(nr, hr)), L.add(pt_, L.mul(nt, ht))))
        fit = []
        for axis in (0, 1):
            xs = np.array([a[axis] for a, _ in pairs])
            ys = np.array([b[axis] for _, b in pairs])
            keep = np.ones(len(xs), bool)
            for _ in range(2):
                a_, b_ = np.polyfit(xs[keep], ys[keep], 1)
                res = np.abs(ys - (a_ * xs + b_))
                keep = res <= max(3 * np.median(res[keep]), 2.0)
            fit.append((a_, b_))
        (ax_, bx_), (ay_, by_) = fit
        S = []
        for ci in range(len(R)):
            S.append([])
            for si in range(len(br[ci])):
                row = []
                for j, ((pr, _, nr, hr), (pt_, _, nt, ht)) in enumerate(zip(br[ci][si], bt[ci][si])):
                    if hr is None:
                        row.append(None)
                        continue
                    if centre == "ref":
                        c, nr = C0[ci][si][j], N0[ci][si][j]
                        c = (ax_ * c[0] + bx_, ay_ * c[1] + by_)
                        n = L.unit((nr[0] / ax_, nr[1] / ay_))
                    else:
                        if ht is None:
                            row.append(None)
                            continue
                        c, n = L.add(pt_, L.mul(nt, ht)), nt
                    row.append(L.sub(c, L.mul(n, hw[ci][si][j] * k)))
                S[ci].append(row)
        moved, notes = 0.0, []
        for ci in range(len(R)):
            pts, sg, ks, S_ = T[ci], segs(R[ci]), kind[ci], S[ci]
            nseg = len(sg)
            if any(ks[si] == "long" and (S_[si][0] is None or S_[si][-1] is None) for si in range(nseg)):
                notes.append(f"c{ci} kept (no width at a node)")
                continue
            new, tin, tout = {}, {}, {}

            def end_dir(si, at_end, S_=S_, second=False):
                # the direction at the segment's end, the way it travels: the chord over its
                # last two sample steps, or (second) to second order from its last three
                # samples, 3 P0 - 4 P1 + P2 (exact for smooth nodes; at corners it folded B)
                row = S_[si]
                if not second:
                    return L.unit(L.sub(row[-1], row[-3])) if at_end else L.unit(L.sub(row[2], row[0]))
                if at_end:
                    a_, b_, c_ = row[-1], row[-2], row[-3]
                    return L.unit((3 * a_[0] - 4 * b_[0] + c_[0], 3 * a_[1] - 4 * b_[1] + c_[1]))
                a_, b_, c_ = row[0], row[1], row[2]
                return L.unit((-3 * a_[0] + 4 * b_[0] - c_[0], -3 * a_[1] + 4 * b_[1] - c_[1]))

            def old_tan(si, at_end, pts=pts, sg=sg):
                return tangent(pts, sg[si], not at_end)
            # nodes between two long edges
            for si in range(nseg):
                pi = (si - 1) % nseg
                i = sg[si][0]
                if ks[si] != "long" or ks[pi] != "long":
                    continue
                e_in, e_out = S_[pi][-1], S_[si][0]
                d_in, d_out = end_dir(pi, True), end_dir(si, False)
                if R[ci][i].smooth or abs(L.cross(d_in, d_out)) < math.sin(math.radians(10)):
                    new[i] = L.mul(L.add(e_in, e_out), 0.5)
                    if not sg[pi][1]:
                        tt = L.unit(L.sub(S_[pi][-1], S_[pi][0]))
                    elif not sg[si][1]:
                        tt = L.unit(L.sub(S_[si][-1], S_[si][0]))
                    else:
                        # each side's own direction at the node, to second order, averaged:
                        # the chord across the node from a sixteenth into each segment
                        # leaned towards the longer one (a C's quarter in one segment above,
                        # two below: the rebuilt bowl came out 15% heavier below)
                        tt = L.unit(L.add(end_dir(pi, True, second=True), end_dir(si, False, second=True)))
                    tin[i] = tout[i] = tt
                else:
                    new[i] = meet(e_in, d_in, e_out, d_out)
                    tin[i], tout[i] = d_in, d_out
            # end cuts: the cut stays where it was derived, the sides meet it
            for si in range(nseg):
                if ks[si] != "cut":
                    continue
                a, b = sg[si][0], sg[si][2]
                dc = L.unit(L.sub(old[ci][b], old[ci][a]))
                pi, ni = (si - 1) % nseg, (si + 1) % nseg
                if ks[pi] == "long":
                    tin[a] = end_dir(pi, True)
                    new[a] = meet(S_[pi][-1], tin[a], old[ci][a], dc)
                if ks[ni] == "long":
                    tout[b] = end_dir(ni, False)
                    new[b] = meet(S_[ni][0], tout[b], old[ci][a], dc)
                notes.append(f"c{ci} end cut {a}-{b} kept")
            # short pieces at a corner: moved whole with the corner of the edges either side
            done = set()
            for start in range(nseg):
                if ks[start] != "short" or ks[(start - 1) % nseg] == "short" or start in done:
                    continue
                run = []
                si = start
                while ks[si] == "short" and len(run) < nseg:
                    run.append(si)
                    done.add(si)
                    si = (si + 1) % nseg
                pi, ni = (run[0] - 1) % nseg, (run[-1] + 1) % nseg
                g0, g1 = sg[run[0]][0], sg[run[-1]][2]
                idx = [g0]
                for r_ in run:
                    idx += list(sg[r_][1]) + [sg[r_][2]]
                ref = [(p.x, p.y) for p in R[ci]]
                lines_new, lines_old, lines_ref = [], [], []
                for nb, at_end, node in ((pi, True, g0), (ni, False, g1)):
                    if ks[nb] == "long":
                        lines_new.append((S_[nb][-1] if at_end else S_[nb][0], end_dir(nb, at_end)))
                        lines_old.append((old[ci][node], old_tan(nb, at_end)))
                        lines_ref.append((ref[node], tangent(R[ci], sg[nb], not at_end)))
                    elif ks[nb] == "cut":
                        c_ = sg[nb]
                        dc = L.unit(L.sub(old[ci][c_[2]], old[ci][c_[0]]))
                        lines_new.append((old[ci][c_[0]], dc))
                        lines_old.append((old[ci][c_[0]], dc))
                        lines_ref.append((ref[c_[0]], L.unit(L.sub(ref[c_[2]], ref[c_[0]]))))
                corner = len(lines_new) == 2 and abs(L.cross(lines_new[0][1], lines_new[1][1])) > math.sin(math.radians(10))
                if corner and not opt.keep_short:
                    # the master's piece, x k about the corner the edges either side make
                    x_new = meet(*lines_new[0], *lines_new[1])
                    x_ref = meet(*lines_ref[0], *lines_ref[1])
                    sx, sy = (ax_ * k, ay_ * k) if centre == "ref" else (k, k)
                    for i in idx:
                        new[i] = (x_new[0] + (ref[i][0] - x_ref[0]) * sx, x_new[1] + (ref[i][1] - x_ref[1]) * sy)
                    delta = None
                elif corner:
                    x_new = meet(*lines_new[0], *lines_new[1])
                    x_old = meet(*lines_old[0], *lines_old[1])
                    delta = L.sub(x_new, x_old)
                else:
                    ds = []
                    if ks[pi] == "long":
                        ds.append(L.sub(S_[pi][-1], old[ci][g0]))
                    if ks[ni] == "long":
                        ds.append(L.sub(S_[ni][0], old[ci][g1]))
                    delta = L.mul(ds[0], 1.0) if len(ds) == 1 else L.mul(L.add(ds[0], ds[1]), 0.5)
                if delta is not None:
                    for i in idx:
                        new[i] = L.add(old[ci][i], delta)
                # where the piece runs on smoothly into a rebuilt edge, its handle there turns
                # onto the edge's direction (a straight piece: the edge leaves along it)
                if ks[pi] == "long":
                    first = sg[run[0]]
                    tin[g0] = end_dir(pi, True)
                    if R[ci][g0].smooth and first[1]:
                        h = first[1][0]
                        new[h] = L.add(new[g0], L.mul(tin[g0], L.dist(old[ci][h], old[ci][g0])))
                    elif R[ci][g0].smooth:
                        tin[g0] = L.unit(L.sub(new[first[2]], new[g0]))
                if ks[ni] == "long":
                    last = sg[run[-1]]
                    tout[g1] = end_dir(ni, False)
                    if R[ci][g1].smooth and last[1]:
                        h = last[1][-1]
                        new[h] = L.sub(new[g1], L.mul(tout[g1], L.dist(old[ci][h], old[ci][g1])))
                    elif R[ci][g1].smooth:
                        tout[g1] = L.unit(L.sub(new[g1], new[last[0]]))
                if delta is None:
                    notes.append(f"c{ci} {g0}-{g1}: the master's x {k:.3f} at the new corner, "
                                 f"moved {max(L.dist(old[ci][i], new[i]) for i in idx):.1f}")
                else:
                    notes.append(f"c{ci} {g0}-{g1} kept as derived, moved {L.norm(delta):.1f}")
            # nodes kept as derived (--keep-nodes): where the rebuild can't follow, as at a
            # crossing of the Black & whose little pieces pass zero; a segment between two
            # kept nodes keeps its handles, one with a kept end leaves it the derived way
            kept_here = kept_nodes.get(ci, set())
            for i in kept_here:
                if pts[i].type:
                    new[i] = old[ci][i]
            # a rebuilt node next to a kept one, or a smooth node next to a corner the
            # rebuilt edges made, may land past it (heavier strokes at a crossing: the arm
            # of the Black & meets the leg above its node 52): it slides back along its own
            # edge until the piece between them points the master's way, at least half the
            # master's length x k (3 units min)
            def anchored(i, ci=ci):
                return i in kept_here or (not R[ci][i].smooth and bend_at(R[ci], sg, next(
                    x for x in range(nseg) if sg[x][0] == i)) > 10)
            for si in range(nseg):
                a, hs, b = sg[si]
                if anchored(a) == anchored(b) or (a in kept_here and b in kept_here):
                    continue
                ra, rb = (R[ci][a].x, R[ci][a].y), (R[ci][b].x, R[ci][b].y)
                if L.dist(ra, rb) < 1e-6:
                    continue
                dm = L.unit(L.sub(rb, ra))
                want_len = max(3.0, 0.5 * k * L.dist(ra, rb))
                along = L.dot(L.sub(new[b], new[a]), dm)
                if along >= 0.3 * want_len:
                    continue        # only a piece that nearly vanished or turned round (one
                                    # merely shorter is the weight's own: B's waist knobbed)
                free = a if anchored(b) else b
                if free in kept_here:
                    continue
                td = tin.get(free) if free == a else tout.get(free)
                if td is None or abs(L.dot(td, dm)) < 0.5:
                    continue        # the edge runs across the piece: sliding along it would
                                    # overshoot (a knob at B's waist at Black)
                push = (want_len - along) / abs(L.dot(td, dm))
                new[free] = L.sub(new[free], L.mul(td, push)) if free == a else L.add(new[free], L.mul(td, push))
                notes.append(f"c{ci} {free} slid {push:.1f} back from {b if free == a else a}")
            # the long edges: lines to their new ends, curves fitted through their samples
            for si in range(nseg):
                a, hs, b = sg[si]
                if a in kept_here and b in kept_here:
                    for h in hs:
                        new[h] = old[ci][h]
                    continue
                if ks[si] != "long" or not hs:
                    continue
                t0, t3 = tout[a], L.mul(tin[b], -1)
                if a in kept_here:
                    t0 = L.unit(L.sub(old[ci][hs[0]], old[ci][a])) if L.dist(old[ci][hs[0]], old[ci][a]) > 1e-6 else t0
                if b in kept_here:
                    t3 = L.unit(L.sub(old[ci][hs[-1]], old[ci][b])) if L.dist(old[ci][hs[-1]], old[ci][b]) > 1e-6 else t3
                inner = [q for q in S_[si][1:-1] if q is not None
                         and L.dot(L.sub(q, new[a]), t0) > 0.5 and L.dot(L.sub(new[b], q), L.mul(t3, -1)) > 0.5]
                c1, c2 = fit_cubic(new[a], new[b], t0, t3, inner)
                new[hs[0]], new[hs[-1]] = c1, c2
            for i, xy in new.items():
                moved = max(moved, L.dist(old[ci][i], xy))
                pts[i].x, pts[i].y = xy
        scale = ""
        if want:
            allpts = [p for c in T for p in c]
            box = Outline(T).polys
            now = {"left": min(x for poly in box for x, _ in poly), "right": max(x for poly in box for x, _ in poly),
                   "top": max(y for poly in box for _, y in poly), "bottom": min(y for poly in box for _, y in poly)}
            parts = []
            for axis, lo, hi in (("x", "left", "right"), ("y", "bottom", "top")):
                if lo in which and hi in which:
                    s_ = (want[hi] - want[lo]) / (now[hi] - now[lo])
                    f_ = (lambda v, s_=s_, lo=lo: want[lo] + (v - now[lo]) * s_)
                elif lo in which or hi in which:
                    e_ = lo if lo in which else hi
                    s_, f_ = 1.0, (lambda v, d_=want[e_] - now[e_]: v + d_)
                else:
                    continue
                for p in allpts:
                    if axis == "x":
                        p.x = f_(p.x)
                    else:
                        p.y = f_(p.y)
                parts.append(f"{axis}{s_:.3f}")
            scale = f", derived {'/'.join(which)} kept ({' '.join(parts)})"
        round_glyph(ctx, gt)
        note = ""
        if opt.realign:
            nodes = {ci: [i for i, p in enumerate(c) if p.type] for ci, c in enumerate(T)}
            rebuilt = ctx.fonts[w][name].copy()

            def attempt(rule, rebuilt=rebuilt, name=name, w=w, nodes=nodes):
                ctx.fonts[w][name] = rebuilt.copy()
                if rule != "none":
                    for ci, c in enumerate(ctx.fonts[w][name].contours):
                        realign(list(c.points), nodes[ci], rule=rule)
            rule, _, _, _ = ctx.best_of(name, w, attempt, ("none", "best", "short"))
            note = f", handles re-lined: {rule}"
        print(f"{name}@{w}: rebuilt about the {'master' if centre == 'ref' else 'derived'} centre lines at "
              f"{ctx.near(w)} x {k:.3f} (x{ax_:.3f}{bx_:+.0f}, y{ay_:.3f}{by_:+.0f}){lift_note}{scale}{note}, largest move {moved:.1f}; "
              f"checks {s0} -> {ctx.score(name, w)}")
        for n_ in notes:
            print("   " + n_)


def straight_band(cs, stem):
    """The straight band through a glyph (the bar of a cent sign, a slash): its long
    straight edges sharing one direction (three or more within 2 degrees), split into
    its two sides, and the short lines joining the sides at its ends (its cuts).
    -> (sides as two lists of (contour, a, b) node pairs, cuts as the same)."""
    lines = []
    for ci, pts in enumerate(cs):
        for s in segs(pts):
            a, b = (pts[s[0]].x, pts[s[0]].y), (pts[s[2]].x, pts[s[2]].y)
            if not s[1]:
                lines.append((ci, s[0], s[2], a, b))
    longs = [ln for ln in lines if L.dist(ln[3], ln[4]) >= 0.5 * stem]
    best = None
    for ln in longs:
        d = L.unit(L.sub(ln[4], ln[3]))
        grp = [m for m in longs if abs(L.cross(d, L.unit(L.sub(m[4], m[3])))) < math.sin(math.radians(2))]
        if best is None or len(grp) > len(best[1]):
            best = (d, grp)
    if best is None or len(best[1]) < 3:
        raise SystemExit("no straight band: needs three long straight edges in one direction")
    d, grp = best
    n = (-d[1], d[0])
    offs = [L.dot(n, L.mul(L.add(m[3], m[4]), 0.5)) for m in grp]
    mid = (max(offs) + min(offs)) / 2
    sides = ([m[:3] for m, o in zip(grp, offs) if o < mid], [m[:3] for m, o in zip(grp, offs) if o >= mid])
    ends = {(m[0], m[1]) for m in grp} | {(m[0], m[2]) for m in grp}
    cuts = [m[:3] for m in lines if m not in grp and (m[0], m[1]) in ends and (m[0], m[2]) in ends]
    return sides, cuts


def band_contour(cs, sides, cuts, width=None):
    """The band as a four-cornered contour (points (x, y)) in glyph cs: its sides fitted
    as two parallel lines (width: their distance, or as given, about their centre line),
    ended by its cuts. -> (corners, width)."""
    def xy(ci, i):
        return (cs[ci][i].x, cs[ci][i].y)
    segs_ = [(xy(ci, a), xy(ci, b)) for side in sides for ci, a, b in side]
    d0 = L.unit(L.sub(*segs_[0][::-1]))
    acc = (0.0, 0.0)
    for a, b in segs_:
        v = L.sub(b, a)
        acc = L.add(acc, v if L.dot(v, d0) >= 0 else L.mul(v, -1))
    d = L.unit(acc)
    n = (-d[1], d[0])

    def offset(side):
        tot = sum(L.dist(xy(ci, a), xy(ci, b)) for ci, a, b in side)
        return sum(L.dot(n, L.mul(L.add(xy(ci, a), xy(ci, b)), 0.5)) * L.dist(xy(ci, a), xy(ci, b))
                   for ci, a, b in side) / tot
    oa, ob = offset(sides[0]), offset(sides[1])
    have = abs(ob - oa)
    if width:
        c, sgn = (oa + ob) / 2, 1 if ob > oa else -1
        oa, ob = c - sgn * width / 2, c + sgn * width / 2
    corners = []
    for ci, a, b in cuts:
        p, q = xy(ci, a), xy(ci, b)
        e = L.unit(L.sub(q, p))
        for o in (oa, ob):
            corners.append(meet(L.mul(n, o), d, p, e))
    if len(corners) != 4:
        raise SystemExit(f"the band needs two cuts, found {len(cuts)}")
    a0, b0, a1, b1 = corners
    ring = [a0, b0, b1, a1]
    area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(ring, ring[1:] + ring[:1]))
    return (ring if area > 0 else ring[::-1]), have


def _ring_contour(ring):
    from ufoLib2.objects import Contour, Point
    return Contour(points=[Point(x, y, "line") for x, y in ring])


def union_outline(part_glyph, offset, ring):
    """The part's contours moved by offset, united with the band ring (booleanOperations)."""
    from copy import deepcopy

    from booleanOperations import BooleanOperationManager
    from ufoLib2.objects import Glyph
    moved = []
    for c in part_glyph.contours:
        cc = deepcopy(c)
        for p in cc.points:
            p.x += offset[0]
            p.y += offset[1]
        moved.append(cc)
    out = Glyph()
    BooleanOperationManager.union(moved + [_ring_contour(ring)], out.getPointPen())
    return [list(c.points) for c in out.contours]


class Boundary:
    """A glyph's outline flattened, with arc length along each contour and its corners
    (nodes turning over 20 degrees)."""

    def __init__(self, cs, per=48):
        self.polys, self.arcs, self.corners = [], [], []
        for pts in cs:
            sg = segs(pts)
            poly, node_at = [], []
            for si, s in enumerate(sg):
                node_at.append(len(poly))
                k = per if s[1] else 1
                for j in range(k):
                    poly.append(seg_at(pts, s, j / k))
            arc = [0.0]
            for a, b in zip(poly, poly[1:] + poly[:1]):
                arc.append(arc[-1] + L.dist(a, b))
            self.polys.append(poly)
            self.arcs.append(arc)            # arc[i]: at poly[i]; arc[-1]: the whole length
            self.corners.append(sorted(arc[node_at[si]] for si in range(len(sg)) if bend_at(pts, sg, si) > 20))

    def length(self, c):
        return self.arcs[c][-1]

    def nearest(self, p):
        best = None
        for c, poly in enumerate(self.polys):
            arc = self.arcs[c]
            for i, a in enumerate(poly):
                b = poly[(i + 1) % len(poly)]
                v = L.sub(b, a)
                ll = L.dot(v, v)
                t = 0.0 if ll < 1e-12 else max(0.0, min(1.0, L.dot(L.sub(p, a), v) / ll))
                q = L.add(a, L.mul(v, t))
                dd = L.dist(p, q)
                if best is None or dd < best[0]:
                    best = (dd, c, arc[i] + t * (arc[i + 1] - arc[i]))
        return best[1], best[2], best[0]

    def at(self, c, s):
        poly, arc = self.polys[c], self.arcs[c]
        total = arc[-1]
        s %= total
        lo, hi = 0, len(poly)
        while hi - lo > 1:
            m = (lo + hi) // 2
            if arc[m] <= s:
                lo = m
            else:
                hi = m
        a, b = poly[lo], poly[(lo + 1) % len(poly)]
        span = arc[lo + 1] - arc[lo]
        t = 0.0 if span < 1e-12 else (s - arc[lo]) / span
        return L.add(a, L.mul(L.sub(b, a), t))

    def piece(self, c, s):
        """(index of the corner before s, fraction of the way to the next corner)."""
        cs_, total = self.corners[c], self.length(c)
        if not cs_:
            return None, s / total
        k = max((i for i, x in enumerate(cs_) if x <= s), default=len(cs_) - 1)
        a, b = cs_[k], cs_[(k + 1) % len(cs_)]
        span = (b - a) % total or total
        return k, ((s - a) % total) / span

    def from_piece(self, c, k, f):
        cs_, total = self.corners[c], self.length(c)
        if k is None:
            return f * total
        a, b = cs_[k % len(cs_)], cs_[(k + 1) % len(cs_)]
        span = (b - a) % total or total
        return (a + f * span) % total


def op_union(ctx, opt):
    """The glyph rebuilt as a part glyph united with its own straight band, its points
    fitted to the result as they sit on the same union in the master."""
    import numpy as np
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        k = ctx.k(w)
        m = ctx.near(w)
        stem = ctx.stems[m]
        part = opt.part
        if not part:
            raise SystemExit("union needs --part GLYPH (the glyph the band is laid over)")
        s0 = ctx.score(name, w)
        # where the part sits in each master (the move that lands most of its nodes on
        # the glyph's), and at w as the masters' trend over weight
        offs = {}
        for mm in ctx.mpaths:
            a = [(p.x, p.y) for c in ctx.fonts[mm][part].contours for p in c.points if p.type]
            b = {(p.x, p.y) for c in ctx.fonts[mm][name].contours for p in c.points if p.type}
            votes = {}
            for ax_, ay_ in a:
                for bx_, by_ in b:
                    key = (bx_ - ax_, by_ - ay_)
                    votes[key] = votes.get(key, 0) + 1
            offs[mm] = max(votes.items(), key=lambda kv: kv[1])[0]
        ws = np.array([float(mm) for mm in offs])
        off_w = []
        for axis in (0, 1):
            vals = np.array([offs[mm][axis] for mm in offs])
            a_, b_ = np.polyfit(ws, vals, 1) if len(set(vals)) > 1 else (0.0, vals[0])
            off_w.append(float(a_ * float(w) + b_))
        if whole_units(ctx):
            off_w = [round(v) for v in off_w]
        gm, gw = ctx.fonts[m][name], ctx.fonts[w][name]
        Cm = [list(c.points) for c in gm.contours]
        Cw = [list(c.points) for c in gw.contours]
        sides, cuts = straight_band(Cm, stem)
        ring_m, width_m = band_contour(Cm, sides, cuts)
        ring_w, _ = band_contour(Cw, sides, cuts, width=width_m * k)
        Um = union_outline(ctx.fonts[m][part], offs[m], ring_m)
        Uw = union_outline(ctx.fonts[w][part], off_w, ring_w)
        bm, bw = Boundary(Um), Boundary(Uw)
        if sorted(len(c) for c in bm.corners) != sorted(len(c) for c in bw.corners):
            raise SystemExit(f"{name}: the unions at {m} and {w} differ in shape "
                             f"({[len(c) for c in bm.corners]} vs {[len(c) for c in bw.corners]} corners)")
        # each master contour of the union to the derived one, corners lined up
        cmap, shift = {}, {}
        for c in range(len(bm.polys)):
            cen = np.mean(bm.polys[c], axis=0)
            c2 = min((x for x in range(len(bw.polys)) if x not in cmap.values() and len(bw.corners[x]) == len(bm.corners[c])),
                     key=lambda x: np.linalg.norm(np.mean(bw.polys[x], axis=0) - cen))
            cmap[c] = c2
            n_ = len(bm.corners[c])
            pm = [bm.at(c, s) for s in bm.corners[c]]
            pw = [bw.at(c2, s) for s in bw.corners[c2]]
            shift[c] = min(range(max(n_, 1)), key=lambda sh: sum(L.dist(pm[i], pw[(i + sh) % n_]) for i in range(n_))) if n_ else 0
        # every node of the glyph: where it sits on the master's union -> the same place
        # on the derived one
        old = [[(p.x, p.y) for p in c] for c in Cw]
        place, worst_off = {}, 0.0
        for ci, pts in enumerate(Cm):
            for i, p in enumerate(pts):
                if not p.type:
                    continue
                c, s, dd = bm.nearest((p.x, p.y))
                worst_off = max(worst_off, dd)
                # a node within a few units of a corner of the union is that corner (the
                # master's join a unit off the exact meeting would land past it, on the
                # other edge, and the piece into it curl round the corner)
                total = bm.length(c)
                near_c = min(bm.corners[c], key=lambda x: min((s - x) % total, (x - s) % total), default=None)
                if near_c is not None and min((s - near_c) % total, (near_c - s) % total) < max(3.0, 2 * dd):
                    s = near_c
                kk, f = bm.piece(c, s)
                c2 = cmap[c]
                s2 = bw.from_piece(c2, None if kk is None else kk + shift[c], f)
                place[(ci, i)] = (c2, s2)
        moved = 0.0
        for ci, pts in enumerate(Cw):
            sg = segs(pts)
            c2s = {place[(ci, s[0])][0] for s in sg}
            if len(c2s) != 1:
                raise SystemExit(f"{name}: contour {ci}'s nodes fall on more than one contour of the union")
            c2 = c2s.pop()
            total = bw.length(c2)
            # does the contour run the union's way round, or against it?
            fwd = sum(1 if (place[(ci, s[2])][1] - place[(ci, s[0])][1]) % total < total / 2 else -1 for s in sg)
            sign = 1 if fwd >= 0 else -1
            for s in sg:
                a, hs, b = s
                sa, sb = place[(ci, a)][1], place[(ci, b)][1]
                pa, pb = bw.at(c2, sa), bw.at(c2, sb)
                pts[a].x, pts[a].y = pa
                pts[b].x, pts[b].y = pb
                if len(hs) != 2:
                    continue
                span = ((sb - sa) * sign) % total
                if span < 1e-6:
                    continue
                samples = [bw.at(c2, sa + sign * span * q / 24) for q in range(1, 24)]
                eps = min(1.0, span / 10)
                ta = L.unit(L.sub(bw.at(c2, sa + sign * eps), pa))
                tb = L.unit(L.sub(pb, bw.at(c2, sb - sign * eps)))
                if span < opt.short * stem * k:
                    # a piece a few units long at a join: handles a third of it along
                    # the outline either end (a fit there turns them round)
                    c1, c2_ = L.add(pa, L.mul(ta, span / 3)), L.sub(pb, L.mul(tb, span / 3))
                else:
                    c1, c2_ = fit_cubic(pa, pb, ta, L.mul(tb, -1), samples)
                (pts[hs[0]].x, pts[hs[0]].y), (pts[hs[1]].x, pts[hs[1]].y) = c1, c2_
            for i, p in enumerate(pts):
                moved = max(moved, L.dist(old[ci][i], (p.x, p.y)))
        round_glyph(ctx, gw)
        print(f"{name}@{w}: {part} moved by ({off_w[0]:g}, {off_w[1]:g}) (masters {', '.join(f'{mm} {offs[mm]}' for mm in offs)}) "
              f"united with its straight band at {m} x {k:.3f} ({width_m:.1f} -> {width_m * k:.1f}); its points as they "
              f"sit on the same union at {m} (furthest off it {worst_off:.1f}); largest move {moved:.1f}; "
              f"checks {s0} -> {ctx.score(name, w)}")


def _blossom(P, us):
    """Blossom of the cubic with control points P at (u1, u2, u3)."""
    pts = list(P)
    for u in us:
        pts = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(pts, pts[1:])]
    return pts[0]


def op_junction(ctx, opt):
    """A straight edge (into node J) meeting a curve (from node K) through a small rounding
    J-K: where extrapolation pushed J past the place the edge really meets the curve, the
    rounding runs backwards (a fold at the inside corner of a crossing, & at Thin). J goes
    onto the edge and K onto the curve, each half the master's rounding x k from where they
    meet, the rounding fitted between them, and the curve from K trimmed or extended so its
    shape stays."""
    for t in opt.targets:
        name, w, ci, (j, kk), _ = parse_target(t)
        k = ctx.k(w)
        g, ref = ctx.fonts[w][name], ctx.fonts[ctx.near(w)][name]
        s0 = ctx.score(name, w)
        pts, rpts = list(g.contours[ci].points), list(ref.contours[ci].points)
        sg = segs(pts)
        into_j = next(s for s in sg if s[2] == j)
        out_j = next(s for s in sg if s[0] == j)
        if not into_j[1] and out_j[2] == kk:
            # forward: straight edge into J, rounding J-K, curve from K
            jk, kl = out_j, next(s for s in sg if s[0] == kk)
            a_node, back = into_j[0], False
        elif not out_j[1] and into_j[0] == kk:
            # backward: curve into K, rounding K-J, straight edge out of J (the joins of a cent sign)
            jk, kl = into_j, next(s for s in sg if s[2] == kk)
            a_node, back = out_j[2], True
        else:
            raise SystemExit(f"{name}: expects a straight edge at {j}, a short segment {j}-{kk}, and a curve beyond {kk}")
        if len(kl[1]) != 2:
            raise SystemExit(f"{name}: the segment beyond {kk} isn't a curve")
        a = (pts[a_node].x, pts[a_node].y)
        jp = (pts[j].x, pts[j].y)
        d = L.unit(L.sub(jp, a))                             # along the edge, toward the junction
        P = [(pts[i].x, pts[i].y) for i in (kl[0], kl[1][0], kl[1][1], kl[2])]
        if back:
            P = P[::-1]                                      # the curve as if it started at K

        def side(tt):
            return L.cross(d, L.sub(_blossom(P, (tt, tt, tt)), a))
        grid = [i / 200 - 1 for i in range(401)]           # t from -1 to 1: the curve and its extension back
        vals = [side(tt) for tt in grid]
        roots = [i for i in range(400) if vals[i] == 0 or vals[i] * vals[i + 1] < 0]
        if not roots:
            raise SystemExit(f"{name}: the edge into {j} doesn't meet the curve from {kk}")
        on_curve = [i for i in roots if grid[i] >= 0]
        # a crossing on the curve itself (the last one: where it comes out of the other
        # stroke), else the nearest on its extension back
        i = max(on_curve) if on_curve else min(roots, key=lambda i: abs(grid[i]))
        lo, hi = grid[i], grid[i + 1]
        for _ in range(50):
            mid = (lo + hi) / 2
            if side(lo) * side(mid) <= 0:
                hi = mid
            else:
                lo = mid
        tx = (lo + hi) / 2
        x = _blossom(P, (tx, tx, tx))
        span = L.dist((rpts[j].x, rpts[j].y), (rpts[kk].x, rpts[kk].y)) * k
        half = span / 2
        # J on the crossing, the corner kept; K along the curve by the master's J-K x k;
        # the piece J-K is cut from the curve itself, so the curve keeps its course
        tk, step, prev, run = tx, 0.001, x, 0.0
        while run < span and tk < 1:
            tk += step
            q = _blossom(P, (tk, tk, tk))
            run += L.dist(prev, q)
            prev = q
        piece = [x, _blossom(P, (tx, tx, tk)), _blossom(P, (tx, tk, tk)), _blossom(P, (tk, tk, tk))]
        rest = [piece[3], _blossom(P, (tk, tk, 1)), _blossom(P, (tk, 1, 1)), P[3]]
        old = (jp, (pts[kk].x, pts[kk].y))
        pts[j].x, pts[j].y = x
        pts[kk].x, pts[kk].y = piece[3]
        hk = kl[1] if not back else kl[1][::-1]               # handles in the order K -> far
        (pts[hk[0]].x, pts[hk[0]].y), (pts[hk[1]].x, pts[hk[1]].y) = rest[1], rest[2]
        if len(jk[1]) == 2:
            hj = jk[1] if not back else jk[1][::-1]           # handles in the order J -> K
            (pts[hj[0]].x, pts[hj[0]].y), (pts[hj[1]].x, pts[hj[1]].y) = piece[1], piece[2]
        round_glyph(ctx, g)
        print(f"{name}@{w}: the edge at {j} meets the curve beyond {kk} at ({x[0]:.0f}, {x[1]:.0f}); {j} {old[0]} -> "
              f"({pts[j].x:g}, {pts[j].y:g}), {kk} {old[1]} -> ({pts[kk].x:g}, {pts[kk].y:g}), rounding {2 * half:.1f} "
              f"({ctx.near(w)} x {k:.3f}); checks {s0} -> {ctx.score(name, w)}")


def _line_fit(pts):
    """A point on and the unit direction of the least-squares line through pts."""
    import numpy as np
    a = np.array(pts, dtype=float)
    c = a.mean(axis=0)
    _, _, vt = np.linalg.svd(a - c)
    return (float(c[0]), float(c[1])), (float(vt[0][0]), float(vt[0][1]))


def _cross_line_cubic(P, o, d, near_end):
    """Parameter t (-0.5..1.5) where the cubic P crosses the line o + s*d, the crossing
    nearest the given end (0 or 1); None when it doesn't."""
    def side(tt):
        return L.cross(d, L.sub(_blossom(P, (tt, tt, tt)), o))
    grid = [i / 200 - 0.5 for i in range(401)]
    vals = [side(tt) for tt in grid]
    roots = [i for i in range(400) if vals[i] == 0 or vals[i] * vals[i + 1] < 0]
    if not roots:
        return None
    i = min(roots, key=lambda i: abs(grid[i] - near_end))
    lo, hi = grid[i], grid[i + 1]
    for _ in range(50):
        mid = (lo + hi) / 2
        if side(lo) * side(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def op_bar(ctx, opt):
    """A straight bar or leg crossing curves (the bar of a cent sign, the leg of &): both
    edges become straight and parallel again, the master's width x k about the derived
    centre line; the bar's end corners slide along their cuts and every join goes to
    where the new edge crosses the curve (or line) it meets, that curve trimmed or
    extended with its shape kept."""
    for t in opt.targets:
        name, w, _, _, _ = parse_target(t)
        k = ctx.k(w)
        g, ref = ctx.fonts[w][name], ctx.fonts[ctx.near(w)][name]
        s0 = ctx.score(name, w)
        edges = []
        for spec in opt.edges.split(","):
            nodes = []
            for item in spec.split("+"):
                c, _, i = item.partition(":")
                nodes.append((int(c.lstrip("c")), int(i)))
            edges.append(nodes)
        if len(edges) != 2:
            raise SystemExit("--edges needs two edges: c0:1+c0:2,c0:3+c1:0")

        def xy(gl, key):
            p = gl.contours[key[0]].points[key[1]]
            return (p.x, p.y)
        # the master's width between its two edge lines, times k
        (mo1, md1), (mo2, md2) = (_line_fit([xy(ref, q) for q in e]) for e in edges)
        width = abs(L.cross(md1, L.sub(mo2, mo1))) * k
        (o1, d1), (o2, d2) = (_line_fit([xy(g, q) for q in e]) for e in edges)
        if L.dot(d1, d2) < 0:
            d2 = L.mul(d2, -1)
        d = L.unit(L.add(d1, d2))
        mid = ((o1[0] + o2[0]) / 2, (o1[1] + o2[1]) / 2)
        n = (-d[1], d[0])
        if L.dot(n, L.sub(o1, mid)) < 0:
            n = L.mul(n, -1)                                     # n points toward edge 1
        lines = [(L.add(mid, L.mul(n, width / 2)), d), (L.sub(mid, L.mul(n, width / 2)), d)]
        before = abs(L.cross(d, L.sub(o2, o1)))
        on_edge = {q: ei for ei, e in enumerate(edges) for q in e}
        moved = []
        for ei, e in enumerate(edges):
            lo_, ld = lines[ei]
            for key in e:
                ci, i = key
                pts = list(g.contours[ci].points)
                sg = segs(pts)
                s_in = next(s for s in sg if s[2] == i)
                s_out = next(s for s in sg if s[0] == i)
                # the neighbour that isn't the bar's own edge
                along_in = not s_in[1] and on_edge.get((ci, s_in[0])) == ei
                along_out = not s_out[1] and on_edge.get((ci, s_out[2])) == ei
                if along_in == along_out:
                    continue                                     # both or neither along the bar: leave it
                other, end = (s_out, 0) if along_in else (s_in, 1)
                old = (pts[i].x, pts[i].y)
                if not other[1]:                                 # a line: a cut, or a straight join
                    far = pts[other[2] if end == 0 else other[0]]
                    od = L.unit(L.sub(old, (far.x, far.y)))
                    new = meet(lo_, ld, (far.x, far.y), od)
                    pts[i].x, pts[i].y = new
                elif len(other[1]) == 2:
                    P = [(pts[j].x, pts[j].y) for j in (other[0], other[1][0], other[1][1], other[2])]
                    tt = _cross_line_cubic(P, lo_, ld, end)      # the crossing nearest the join's end
                    if tt is None:
                        continue
                    if end == 0:                                 # the curve starts at the join
                        c = [_blossom(P, (tt, tt, tt)), _blossom(P, (tt, tt, 1)), _blossom(P, (tt, 1, 1)), P[3]]
                    else:                                        # the curve ends at the join
                        c = [P[0], _blossom(P, (0, 0, tt)), _blossom(P, (0, tt, tt)), _blossom(P, (tt, tt, tt))]
                    for j, q in zip((other[0], other[1][0], other[1][1], other[2]), c):
                        pts[j].x, pts[j].y = q
                moved.append(L.dist(old, (pts[i].x, pts[i].y)))
        round_glyph(ctx, g)
        print(f"{name}@{w}: bar straight and parallel, width {before:.1f} -> {width:.1f} ({ctx.near(w)} x {k:.3f}), "
              f"{len(moved)} corners onto its edges (largest move {max(moved, default=0):.1f}); checks {s0} -> {ctx.score(name, w)}")


OPS = {"copy-shape": op_copy_shape, "junction": op_junction, "bar": op_bar, "min-segment": op_min_segment, "same-part": op_same_part,
       "copy-sync": op_copy_sync, "bar-place": op_bar_place, "inset": op_inset, "chevron": op_chevron,
       "strokes": op_strokes, "upright": op_upright, "follow-edge": op_follow_edge,
       "offset-inner": op_offset_inner, "rebuild-stroke": op_rebuild_stroke, "rebuild-outline": op_rebuild_outline,
       "union": op_union}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("op", choices=sorted(OPS))
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--masters", nargs="+", required=True)
    ap.add_argument("--derived", nargs="+", required=True)
    ap.add_argument("--ref", help="reference master for the checks (default: the middle one, as audit.py)")
    ap.add_argument("--from", dest="source", help="take shapes and thickness from this master instead of the nearest")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--length", type=float, default=4.0, help="min-segment: length in units")
    ap.add_argument("--part", help="same-part: GLYPH:CONTOUR to copy; union: the glyph the band is laid over")
    ap.add_argument("--bar", type=int, default=1, help="bar-place: the bar's contour")
    ap.add_argument("--crossed", type=int, default=0, help="bar-place: the contour it crosses")
    ap.add_argument("--keep-edge", choices=["bottom", "top"], help="inset: keep straight edges on this line")
    ap.add_argument("--seat", choices=["bottom"], help="inset: move the result back onto its old bottom")
    ap.add_argument("--nodes", help="strokes, upright: node indices, comma-separated")
    ap.add_argument("--inner", help="offset-inner: the inside's nodes in contour order")
    ap.add_argument("--outer", help="offset-inner: start nodes of the outside's segments")
    ap.add_argument("--centre", choices=["own", "ref"], default=None,
                    help="rebuild-stroke, rebuild-outline: whose centre line (default own, ref)")
    ap.add_argument("--short", type=float, default=0.25,
                    help="rebuild-outline: pieces at a corner shorter than this x the master's stem aren't rebuilt as "
                         "edges: they take the master's shape x k at the new corner")
    ap.add_argument("--fill-crossings", nargs="?", const=3.0, type=float, default=None,
                    help="rebuild-outline: an edge running through a crossing keeps the width it has on either "
                         "side, over F x the master's stem each way (default 3), where the master thins the stroke "
                         "into the crossing (at most +20%%)")
    ap.add_argument("--verbose", action="store_true", help="say more about what an op found")
    ap.add_argument("--similar", action="store_true",
                    help="copy-shape: turn and scale the master's piece as a whole instead of per axis "
                         "(for a piece whose ends lie at nearly one height or width: the tip of a counter)")
    ap.add_argument("--fill-cap", type=float, default=1.2,
                    help="rebuild-outline: --fill-crossings widens a stroke by at most this factor (default 1.2)")
    ap.add_argument("--smooth-centre", nargs="?", const=1.0, type=float, default=None,
                    help="rebuild-outline: the master's centre lines and widths smoothed along each edge over F x its "
                         "stem (default 1): its wiggles, which a thinner weight shows more, go")
    ap.add_argument("--keep-short", action="store_true",
                    help="rebuild-outline: those short pieces keep their derived shape, moved with the corner")
    ap.add_argument("--smooth", type=int, default=0, help="rebuild-stroke: average the centre line over N samples")
    ap.add_argument("--keep-limits", nargs="?", const=LIMITS_S, default=None,
                    help="rebuild-stroke: keep these derived limits of the contour, from left, right, top, bottom, "
                         f"upper-left, lower-right (alone: {LIMITS_S}, for an S)")
    ap.add_argument("--sides", help="rebuild-stroke: the two sides as node ranges A-B,C-D, a side in several runs "
                                    "A-B+C-D (default: between two straight end cuts)")
    ap.add_argument("--keep-nodes", help="rebuild-stroke: nodes that stay where they are (junctions), i,j; "
                                         "rebuild-outline: points kept as derived, C:A-B,... (a crossing the rebuild folds)")
    ap.add_argument("--edges", help="bar: the nodes on each edge, c0:16+c0:17+c0:33,c0:35+c1:0 (two edges)")
    ap.add_argument("--realign", action="store_true",
                    help="rebuild-stroke: after rounding, line short handles up again with the long ones at each node")
    opt = ap.parse_args(argv)
    ctx = Ctx(opt)
    OPS[opt.op](ctx, opt)
    if opt.write:
        for w in {parse_target(t)[1] if "=" not in t else t.partition("@")[2] for t in opt.targets}:
            ctx.fonts[w].save()
    else:
        print("dry run: nothing saved (use --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
