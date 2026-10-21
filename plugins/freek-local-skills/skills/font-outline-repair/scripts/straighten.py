#!/usr/bin/env python3
"""Make the straight edges running into a point (a counter's tip) truly straight in whole units.

usage:
  straighten.py FONT.ufo GLYPH RUN [RUN ...] [--move R] [--slide S] [--aim]
                [--dirs=A,B/A,B] [--max-back DEG] [--top N] [--write]

RUN is CONTOUR:TIP>END (the edge follows the contour forward from TIP to END) or
CONTOUR:TIP<END (backward). Every run starts at the same TIP node. Each edge's nodes
and handles are put on one line through the tip whose direction is a whole-unit step
(a, b), nodes on whole steps, each curve's handles at whole steps inside it (a curve
of two steps has both at its midpoint), so the edge is straight after rounding: no
node bends and no handle sits off the line. END may lie up to 0.5 units off the line;
the last handle before it then sits on the line.

Whole-unit points on a line are a step |(a, b)| apart, and every curve between two
nodes needs one inside it for its handles: an edge of n curves needs 2n steps. A short
edge therefore gets a direction a few degrees off, or:
  --move R    the tip may move up to R units;
  --slide S   END may slide up to S units along the outline it joins (never more than
              0.75 across it: moving END across bends the curve beyond, a dip);
  --aim       END's outer handle (and the curve's other handle, along its own direction)
              is turned into the edge's line, so the edge runs into the curve without a
              bend and the curve does not turn harder where it leaves the edge than it
              did; it prints how far that curve moved;
  --dirs      the step for each run in RUN order, separated by /, instead of the
              cheapest (auto keeps the cheapest for that run), e.g. --dirs=-1,2/3,1
              (write it with = when a step starts with a minus). To follow the nearest
              master, give the steps this script chose there, if this edge is long
              enough for them.
Edges that turn against the curve they run into (an S, which reads as a dip) by more
than --max-back degrees (0.5) are refused. The choice weighs: direction change (per
degree), the tip's move (per unit), END sliding (0.3 per unit) and across (3), nodes
sliding along the edge (0.2), the turn into the curve (0.5 per degree, 4 against it),
END's distance off the line (3) and, with --aim, how far the curve beyond moves (3).

Without --write it prints the choice and the bends before and after; --top N also
prints the next best choices.

  --between   RUN is CONTOUR:A>B (or A<B), any straight run between two nodes that both
              stay (a terminal's edge stored as a row of tiny curves, which zigzags at
              derived and in-between weights because every point rounds on its own):
              every point between them goes to whole steps of the small step nearest the
              run's direction (--dirs to choose it), as evenly spaced as the steps allow.
              B may move up to --slide units (1) to land on a whole step. A run with fewer
              whole steps than gaps between its points is refused rather than stacking
              points on one spot: it needs fewer points, in every master.
"""
import argparse
import itertools
import math
import sys

import ufoLib2


def angle(v):
    return math.degrees(math.atan2(v[1], v[0]))


def adiff(a, b):
    return abs((a - b + 180) % 360 - 180)


def bends(pts):
    """bend in degrees at each node between the directions to its two neighbours"""
    n, out = len(pts), {}
    for i, p in enumerate(pts):
        if not p.type:
            continue
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        if (a.x, a.y) == (p.x, p.y) or (b.x, b.y) == (p.x, p.y):
            continue
        out[i] = adiff(angle((b.x - p.x, b.y - p.y)), angle((p.x - a.x, p.y - a.y)))
    return out


def parse_run(s):
    c, rest = s.split(":")
    if ">" in rest:
        t, e = rest.split(">")
        return int(c), int(t), int(e), +1
    t, e = rest.split("<")
    return int(c), int(t), int(e), -1


def run_layout(pts, tip, end, step):
    """nodes from tip to end (contour indices) and per segment (h_near, h_far) or None for a line"""
    n = len(pts)
    nodes, segs = [tip], []
    i = tip
    while i != end:
        j = (i + step) % n
        offs = []
        while not pts[j].type:
            offs.append(j)
            j = (j + step) % n
        # the segment's type is stored on its end point in contour order
        seg_end = j if step > 0 else i
        if pts[seg_end].type == "line":
            segs.append(None)
        else:
            assert len(offs) == 2, (i, j, offs)
            segs.append((offs[0], offs[1]))
        nodes.append(j)
        i = j
        if len(nodes) > n:
            sys.exit("END not reached from TIP")
    far = (end + step) % n
    far_h = far if not pts[far].type else None
    return nodes, segs, far_h


def primitive_steps(vec, max_len, max_deg):
    out = []
    ang = angle(vec)
    for a in range(-12, 13):
        for b in range(-12, 13):
            if (a, b) == (0, 0) or math.gcd(a, b) != 1:
                continue
            L = math.hypot(a, b)
            if L > max_len or adiff(angle((a, b)), ang) > max_deg:
                continue
            out.append((a, b))
    return out


def cubic(p0, p1, p2, p3, n=48):
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        out.append((mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
                    mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]))
    return out


def dist_to_poly(q, poly):
    best = math.inf
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((q[0] - x0) * dx + (q[1] - y0) * dy) / L2))
        best = min(best, math.hypot(q[0] - x0 - t * dx, q[1] - y0 - t * dy))
    return best


def solve_run(pts, nodes, segs, far_h, A, B0, S, orig_dir, A0, max_back=0.5, aim=False, force=None):
    """best layout of one run for tip A (tuple); returns (cost, plan).
    END may slide up to S units along the outline it joins (towards or away from its outer
    handle, which stays where it is, so the curve beyond keeps its direction at END), and
    at most 0.75 units across it: moving it across bends that curve (a dip in Black &)."""
    best = None
    s_orig = [(pts[k].x, pts[k].y) for k in nodes[1:-1]]
    fh = (pts[far_h].x, pts[far_h].y) if far_h is not None else None
    if fh is not None and math.hypot(fh[0] - B0[0], fh[1] - B0[1]) > 1e-9:
        tv = (fh[0] - B0[0], fh[1] - B0[1])
        hlen = math.hypot(*tv)
    else:
        tv = (B0[0] - A0[0], B0[1] - A0[1])
        hlen = math.inf
    tl = math.hypot(*tv)
    t = (tv[0] / tl, tv[1] / tl)
    # which way the curve beyond END turns (its outer handle, then the next point on)
    n = len(pts)
    turn = 0.0
    old_curve = None
    if fh is not None:
        step = 1 if (far_h - nodes[-1]) % n == 1 else -1
        nxt = pts[(far_h + step) % n]
        turn = (fh[0] - B0[0]) * (nxt.y - fh[1]) - (fh[1] - B0[1]) * (nxt.x - fh[0])
        g2 = (nxt.x, nxt.y)
        fnode = pts[(far_h + 2 * step) % n]
        F = (fnode.x, fnode.y)
        # the curve beyond END as it is, with its tangent carried back past END (for slides)
        old_curve = [(B0[0] - t[0] * (S + 2), B0[1] - t[1] * (S + 2))] + cubic(B0, fh, g2, F)

    aim_cache = {}

    def aim_handle(B, u):
        key = (B, u)
        if key not in aim_cache:
            aim_cache[key] = _aim_handle(B, u)
        return aim_cache[key]

    def start_curvature(P0, P1, P2):
        """curvature at a cubic's start, in degrees per unit"""
        a = (P1[0] - P0[0], P1[1] - P0[1])
        b = (P2[0] - P1[0], P2[1] - P1[1])
        la = math.hypot(*a)
        if la < 1e-9:
            return math.inf
        return math.degrees(abs(a[0] * b[1] - a[1] * b[0]) * 2 / 3 / la**3)

    def _aim_handle(B, u):
        """END's outer handle turned into the edge's last direction u (whole steps of u), and
        the curve's other handle lengthened or shortened along its own direction: the pair
        that keeps the curve beyond closest to what it was without turning harder where it
        leaves the edge than the curve did (a knee). Returns (score, outer handle, other
        handle, distance moved)."""
        g = math.gcd(int(u[0]), int(u[1])) or 1
        up = (u[0] // g, u[1] // g)
        old_len = hlen if hlen < math.inf else 10
        k_old = start_curvature(B0, fh, g2)
        gv = (g2[0] - F[0], g2[1] - F[1])
        gg = math.gcd(int(gv[0]), int(gv[1])) or 1
        gp = (gv[0] // gg, gv[1] // gg)
        best_h = None
        for m in range(1, 40):
            h = (B[0] + m * up[0], B[1] + m * up[1])
            L = math.hypot(h[0] - B[0], h[1] - B[1])
            if L < 0.4 * old_len:
                continue
            if L > 1.8 * old_len:
                break
            for j in range(-3, 4):
                h2 = (g2[0] + j * gp[0], g2[1] + j * gp[1])
                if (h2[0] - F[0]) * gv[0] + (h2[1] - F[1]) * gv[1] <= 0:
                    continue
                dev = max(dist_to_poly(q, old_curve) for q in cubic(B, h, h2, F, 24))
                k0 = start_curvature(B, h, h2)
                score = dev + 2 * max(0.0, k0 - max(k_old, 0.5))
                if best_h is None or score < best_h[0]:
                    best_h = (score, h, h2, dev)
        return best_h

    def signed(u, v):
        return ((angle(v) - angle(u) + 180) % 360) - 180

    def end_bend_cost(P, B, p):
        """the turn from the straight edge into the curve beyond END: from the line to the
        last handle's direction (inside the last segment, when END is off the line) and from
        there to the curve's (at END). Turning the same way as the curve reads as the curve
        starting a little sooner; the other way it is an S, a dip (4 per degree)."""
        if fh is None:
            return 0.0, 0.0, 0.0, None, 0.0
        u = (B[0] - P[0], B[1] - P[1])
        new_h, dev, score = None, 0.0, 0.0
        if aim:
            r = aim_handle(B, u)
            if r is None:
                return 0.0, math.inf, math.inf, None, 0.0
            score, h1, h2, dev = r
            new_h = (h1, h2)
            w = (h1[0] - B[0], h1[1] - B[1])
        else:
            w = (fh[0] - B[0], fh[1] - B[1])
        d1, d2 = signed(p, u), signed(u, w)
        cost = 3 * score
        back_deg = 0.0
        for dd in (d1, d2):
            back = turn and dd and (dd > 0) != (turn > 0)
            cost += abs(dd) * (4.0 if back else 0.5)
            back_deg += abs(dd) if back else 0.0
        return abs(d2), cost, back_deg, new_h, dev
    for dx, dy in itertools.product(range(-S, S + 1), repeat=2):
        along = dx * t[0] + dy * t[1]
        across = abs(dx * t[1] - dy * t[0])
        if abs(along) > S + 1e-9 or across > 0.75 or along > hlen - 1:
            continue
        B = (B0[0] + dx, B0[1] + dy)
        v = (B[0] - A[0], B[1] - A[1])
        L = math.hypot(*v)
        if L < 1:
            continue
        for p in ([force] if force else primitive_steps(v, L / 2, 8)):
            pl2 = p[0] ** 2 + p[1] ** 2
            pl = math.sqrt(pl2)
            d = abs(v[0] * p[1] - v[1] * p[0]) / pl
            if d > 0.5:
                continue
            Kf = (v[0] * p[0] + v[1] * p[1]) / pl2
            on = d < 1e-9 and abs(Kf - round(Kf)) < 1e-9
            # last whole step strictly before B that may hold a handle or node
            kmax = int(round(Kf)) - 1 if on else math.floor(Kf - 1e-9)
            s = [((x - A[0]) * p[0] + (y - A[1]) * p[1]) / pl2 for x, y in s_orig]
            m = len(s)
            gaps = [2 if sg else 1 for sg in segs]
            # dp over intermediate node steps
            Kend = int(round(Kf)) if on else None

            def ok_last(k):
                if segs[-1] is None:
                    return (Kend - k >= 1) if on else (Kf - k >= 0.999)
                return (Kend - k >= 2) if on else (kmax - k >= 1)

            if m == 0:
                choices = [()] if ok_last(0) else []
            else:
                choices = []
                rng = range(1, kmax + 1)
                # small search: m is at most a handful
                for ks in itertools.combinations(rng, m):
                    prev, good = 0, True
                    for j, k in enumerate(ks):
                        if k - prev < gaps[j]:
                            good = False
                            break
                        prev = k
                    if good and ok_last(ks[-1]):
                        choices.append(ks)
            for ks in choices:
                disp = sum(abs(k - si) * pl for k, si in zip(ks, s))
                steps = [0] + list(ks)
                handles, ok = [], True
                cornerB = cornerCost = backB = aimDev = 0.0
                newH = None
                for j, sg in enumerate(segs):
                    if sg is None:
                        handles.append(None)
                        continue
                    ku = steps[j]
                    last = j == len(segs) - 1
                    kv = (Kend if on else Kf) if last else steps[j + 1]
                    hi = (kv - 1) if (not last or on) else kmax
                    lo = ku + 1
                    if hi < lo:
                        ok = False
                        break
                    third = (kv - ku) / 3
                    hu = min(max(lo, ku + max(1, round(third))), hi)
                    if last and not on:
                        # the handle at B: the inner step that leaves the least bend at B
                        cand = []
                        for k in range(lo, hi + 1):
                            P = (A[0] + k * p[0], A[1] + k * p[1])
                            c, cc, bk, nh, dv = end_bend_cost(P, B, p)
                            cand.append((cc + 0.5 * abs(k - (kv - third)), k, c, cc, bk, nh, dv))
                        _, hv, cornerB, cornerCost, backB, newH, aimDev = min(cand, key=lambda c: c[:2])
                    else:
                        hv = min(max(lo, round(kv - max(1, third))), hi)
                        if last:
                            P = (A[0] + hv * p[0], A[1] + hv * p[1])
                            cornerB, cornerCost, backB, newH, aimDev = end_bend_cost(P, B, p)
                    if hu > hv:
                        hu = hv = round((ku + kv) / 2) if (not last or on) else hv
                        hu = min(hu, hv)
                    handles.append((hu, hv))
                if not ok:
                    continue
                if segs[-1] is None:
                    prevk = steps[-1]
                    P = (A[0] + prevk * p[0], A[1] + prevk * p[1])
                    cornerB, cornerCost, backB, newH, aimDev = end_bend_cost(P, B, p)
                if backB > max_back:
                    continue
                cost = (adiff(angle(p), orig_dir) + 0.3 * abs(along) + 3 * across + 0.2 * disp
                        + cornerCost + 3 * d)
                plan = dict(p=p, B=B, dB=(dx, dy), along=along, across=across, steps=steps,
                            handles=handles, d=d, Kf=Kf, cornerB=cornerB, disp=disp, cost=cost,
                            back=backB, s_bend=backB > 1e-9, new_h=newH, aim_dev=aimDev)
                if best is None or cost < best[0]:
                    best = (cost, plan)
    return best


def between(pts, a, b, step, force=None, slide=1):
    """--between: (plan, message). plan is {index: (x, y)} or None when refused."""
    n = len(pts)
    idx, i = [], a
    while i != b:
        i = (i + step) % n
        idx.append(i)
        if len(idx) > n:
            sys.exit("B not reached from A")
    inner = idx[:-1]
    A, B = (pts[a].x, pts[a].y), (pts[b].x, pts[b].y)
    v = (B[0] - A[0], B[1] - A[1])
    L = math.hypot(*v)
    off = max((abs((pts[j].x - A[0]) * v[1] - (pts[j].y - A[1]) * v[0]) / L for j in inner), default=0.0)
    if off > max(2.0, 0.06 * L):
        return None, f"not a straight run: a point lies {off:.1f} units off the line from {a} to {b}"
    cands = [force] if force else primitive_steps(v, 13, 8)
    best = None
    for p in cands:
        pl2 = p[0] ** 2 + p[1] ** 2
        K = round((v[0] * p[0] + v[1] * p[1]) / pl2)
        if K < 1:
            continue
        B2 = (A[0] + K * p[0], A[1] + K * p[1])
        miss = math.hypot(B2[0] - B[0], B2[1] - B[1])
        # the smallest step that reaches B: the most whole steps for the points
        key = (miss > slide + 1e-9, math.hypot(*p) if miss <= slide + 1e-9 else miss, miss)
        if best is None or key < best[0]:
            best = (key, p, K, B2, miss)
    if best is None:
        return None, "no small whole step runs this way"
    if best[0][0]:
        return None, (f"no small whole step reaches {b} within --slide {slide} of where it is (nearest: "
                      f"{best[2]} x {best[1]}, {best[4]:.1f} units off)")
    _, p, K, B2, miss = best
    gaps = len(idx)
    if K < gaps:
        return None, (f"{gaps} gaps between {gaps + 1} points but only {K} whole steps of {p}: points would "
                      f"stack on one spot. This run needs at most {K + 1} points (remove {gaps - K}), in every master")
    plan = {j: (A[0] + round(K * (q + 1) / gaps) * p[0], A[1] + round(K * (q + 1) / gaps) * p[1])
            for q, j in enumerate(inner)}
    plan[b] = B2
    return plan, (f"{len(inner)} points between {a} and {b} at whole steps of {p} ({angle(p):.1f} deg, the run "
                  f"{angle(v):.1f}), {K} steps for {gaps} gaps" + (f"; {b} moved {miss:.1f} onto a step" if miss else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ufo")
    ap.add_argument("glyph")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--move", type=int, default=0, help="the tip may move up to R units (default 0)")
    ap.add_argument("--slide", type=int, default=0,
                    help="end nodes may slide up to S units along the outline they join (default 0)")
    ap.add_argument("--top", type=int, default=1, help="also print the next best choices")
    ap.add_argument("--aim", action="store_true",
                    help="turn each end's outer handle into the edge's line, so the edge runs into the "
                         "curve beyond without a bend (that curve moves by the printed amount)")
    ap.add_argument("--dirs", metavar="A,B/A,B",
                    help="the whole-unit step for each run in order, separated by /, or auto "
                         "for the cheapest (e.g. --dirs=-1,2/3,1, or the steps chosen in the "
                         "nearest master)")
    ap.add_argument("--max-back", type=float, default=0.5,
                    help="degrees an edge may turn against the curve it runs into (an S, a dip); default 0.5")
    ap.add_argument("--between", action="store_true",
                    help="RUN is A>B, a straight run whose ends both stay: its points at evenly spaced whole steps")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    font = ufoLib2.Font.open(a.ufo)
    runs = [parse_run(r) for r in a.runs]
    if a.between:
        forced = [None if d == "auto" else tuple(int(v) for v in d.split(",")) for d in a.dirs.split("/")] \
            if a.dirs else [None] * len(runs)
        refused = 0
        for (ci, ra, rb, st), force in zip(runs, forced):
            pts = list(font[a.glyph].contours[ci].points)
            plan, msg = between(pts, ra, rb, st, force, a.slide or 1)
            print(f"{a.glyph} {ci}:{ra}{'>' if st > 0 else '<'}{rb}: {msg}")
            if plan is None:
                refused += 1
                continue
            for j, (x, y) in plan.items():
                pts[j].x, pts[j].y = x, y
        if refused:
            print("  nothing written")
            sys.exit(1)
        if a.write:
            font.save()
            print(f"  written: {a.ufo}")
        else:
            print("  dry run: nothing written")
        return
    cidx = runs[0][0]
    tip = runs[0][1]
    assert all(r[0] == cidx and r[1] == tip for r in runs), "all runs start at one tip in one contour"
    pts = list(font[a.glyph].contours[cidx].points)
    before = bends(pts)
    layouts = [run_layout(pts, tip, end, step) for _, _, end, step in runs]
    A0 = (pts[tip].x, pts[tip].y)
    dirs = [None] * len(runs)
    if a.dirs:
        ds = a.dirs.split("/")
        assert len(ds) == len(runs), "one --dirs entry per run"
        dirs = [None if d == "auto" else tuple(int(v) for v in d.split(",")) for d in ds]
    found = []
    R = a.move
    for dx, dy in itertools.product(range(-R, R + 1), repeat=2):
        if math.hypot(dx, dy) > R + 1e-9:
            continue
        A = (A0[0] + dx, A0[1] + dy)
        total, plans = math.hypot(dx, dy), []
        for nodes, segs, far_h in layouts:
            end = nodes[-1]
            od = angle((pts[end].x - A0[0], pts[end].y - A0[1]))
            force = dirs[len(plans)]
            r = solve_run(pts, nodes, segs, far_h, A, (pts[end].x, pts[end].y), a.slide, od, A0, a.max_back, a.aim, force)
            if r is None:
                total = None
                break
            total += r[0]
            plans.append(r[1])
        if total is not None:
            found.append((total, A, plans))
    if not found:
        sys.exit(f"{a.glyph}: no whole-unit line fits; try a larger --move or --slide")
    found.sort(key=lambda f: f[0])
    for total, A_, plans_ in found[1:a.top]:
        print(f"  also: cost {total:.1f}, tip {A_}: " + "; ".join(
            f"{pl['p']} {angle(pl['p']):.1f} deg, end slides {pl['along']:+.1f} across {pl['across']:.1f}, "
            f"bend at end {pl['cornerB']:.1f}{' S' if pl['s_bend'] else ''}" for pl in plans_))
    _, A, plans = found[0]
    moved = []
    was = [angle((pts[r[2]].x - A0[0], pts[r[2]].y - A0[1])) for r in runs]
    pts[tip].x, pts[tip].y = A
    for (nodes, segs, far_h), plan, (_, _, end, _), was_dir in zip(layouts, plans, runs, was):
        p, steps = plan["p"], plan["steps"]
        at = lambda k: (A[0] + k * p[0], A[1] + k * p[1])
        for k, ni in zip(steps[1:], nodes[1:-1]):
            pts[ni].x, pts[ni].y = at(k)
        B = plan["B"]
        dx, dy = plan["dB"]
        pts[end].x, pts[end].y = B   # its outer handle stays (the curve beyond keeps its direction) ...
        if plan["new_h"] is not None:  # ... unless --aim turned it into the edge's line
            n_ = len(pts)
            stp = 1 if (far_h - end) % n_ == 1 else -1
            (pts[far_h].x, pts[far_h].y), (pts[(far_h + stp) % n_].x, pts[(far_h + stp) % n_].y) = plan["new_h"]
        for sg, h in zip(segs, plan["handles"]):
            if sg is None:
                continue
            (iu, iv), (hu, hv) = sg, h
            pts[iu].x, pts[iu].y = at(hu)
            pts[iv].x, pts[iv].y = at(hv)
        moved.append(f"edge {cidx}:{tip}->{end}: step {p} ({angle(p):.1f} deg, edge was {was_dir:.1f}), "
                     f"nodes at steps {steps[1:]}, end {end} slid {plan['along']:+.1f} along the outline "
                     f"and {plan['across']:.1f} across, {plan['d']:.2f} off the line, bend at end {plan['cornerB']:.1f} deg"
                     + (" (against the curve's turn: an S)" if plan["s_bend"] else "")
                     + (f"; its outer handle aimed along the edge, the curve beyond moves {plan['aim_dev']:.2f}"
                        if plan["new_h"] is not None else ""))
    after = bends(pts)
    print(f"{a.glyph}: tip {cidx}:{tip} at {A} (moved {math.hypot(A[0]-A0[0], A[1]-A0[1]):.1f})")
    for m in moved:
        print("  " + m)
    ids = [i for lay in layouts for i in lay[0][1:]]
    print("  bend at node  " + " ".join(f"{i:>5}" for i in ids))
    print("  before (deg)  " + " ".join(f"{before.get(i, 0):5.1f}" for i in ids))
    print("  after  (deg)  " + " ".join(f"{after.get(i, 0):5.1f}" for i in ids))
    if a.write:
        font.save()
        print(f"  written: {a.ufo}")
    else:
        print("  dry run: nothing written")


if __name__ == "__main__":
    main()
