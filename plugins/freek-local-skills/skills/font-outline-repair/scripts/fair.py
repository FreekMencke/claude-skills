#!/usr/bin/env python3
"""Fair one or two curves of a contour: re-place their handles (and the node between
them) in whole units for even curvature, keeping the directions at both ends, so a
straight edge runs into its curve without a knee and a curve has no flat spot.

usage:
  fair.py FONT.ufo GLYPH RUN [--move R] [--turn DEG] [--ratio R] [--edge TIP:N]
          [--dev D] [--top N] [--pick K] [--write]

RUN is CONTOUR:A>B (forward from node A to node B) or CONTOUR:A<B (backward): one
curve, or two with one node between. A and B stay, and so do the directions the
outline has into A and out of B; the handles next to them slide along those lines
(whole-unit points within 0.3 degrees of the line), so a corner at A or B becomes
smooth. Two curves that share a node with two others (a shoulder: 15>21, then 18>24)
take two runs, the second holding what the first set (--ratio-a/--ratio-b); run them
twice in turn.
  --move R      the node between may move up to R units (default 0). Its tangent turns
                to a whole-unit step within --turn degrees (8) of its own, and its
                handles sit at whole steps on that line, so it stays smooth after rounding.
  --ratio R     the node between splits its handles R:1 (the handle after it along the
                run against the one before it), as in the other masters: a different
                split in each master kinks the weights in between (audit.py's
                ratio-mismatch). Without it the split is free (1/3 to 3).
  --ratio-a R, --ratio-b R
                hold the split at A or B (the handle after the node against the one
                before it, along the run): when two runs share a smooth node, the second
                keeps what the first set there.
  --edge TIP:N  A ends a straight edge that starts at node TIP, with every point of it
                at whole steps of one direction from TIP (straighten.py first). A may
                move back along the edge up to N steps, so the curve starts earlier and
                more gently; the handles of the edge's last curve move to whole steps
                with it, and A's handle stays on the edge's line.
  --dev D       the new outline stays within D units of the current one (1.5).
It prints the curvature (1/radius, x1000, positive with the run's turn) of the run now
and of the --top (5) best layouts: least (a flat spot), peak, the jumps at A, at the node
between and at B, and the largest distance from the current outline. Layouts with any
curvature against the turn are refused. --write saves layout --pick (1). When the edge
into A has a long whole-unit step ((73,-3)) or the corner has more than two curves, use
corner.py. Look at the
result filled (solid.py) beside the other masters, and measure it with profile.py.
"""
import argparse
import heapq
import itertools
import math
import sys

import ufoLib2


def bez(p, t):
    mt = 1 - t
    return (mt**3 * p[0][0] + 3 * mt * mt * t * p[1][0] + 3 * mt * t * t * p[2][0] + t**3 * p[3][0],
            mt**3 * p[0][1] + 3 * mt * mt * t * p[1][1] + 3 * mt * t * t * p[2][1] + t**3 * p[3][1])


def curv(p, t):
    """signed curvature of a cubic at t (left turn positive)"""
    mt = 1 - t
    d1 = [3 * mt * mt * (p[1][k] - p[0][k]) + 6 * mt * t * (p[2][k] - p[1][k]) + 3 * t * t * (p[3][k] - p[2][k]) for k in (0, 1)]
    d2 = [6 * mt * (p[2][k] - 2 * p[1][k] + p[0][k]) + 6 * t * (p[3][k] - 2 * p[2][k] + p[1][k]) for k in (0, 1)]
    v = math.hypot(*d1)
    if v < 1e-9:
        return 0.0
    return (d1[0] * d2[1] - d1[1] * d2[0]) / v**3


SAMPLES = 16


def profile(p, sgn):
    return [sgn * 1000 * curv(p, i / SAMPLES) for i in range(SAMPLES + 1)]


def angle(v):
    return math.degrees(math.atan2(v[1], v[0]))


def adiff(a, b):
    return abs((a - b + 180) % 360 - 180)


def parse_run(s):
    c, rest = s.split(":")
    sep = ">" if ">" in rest else "<"
    a, b = rest.split(sep)
    return int(c), int(a), int(b), 1 if sep == ">" else -1


def walk(pts, a, b, s):
    """on-curve nodes from a to b and the two handles of each curve, in run order"""
    n = len(pts)
    nodes, handles = [a], []
    i = a
    while i != b:
        j = (i + s) % n
        offs = []
        while pts[j].type is None:
            offs.append(j)
            j = (j + s) % n
        if len(offs) != 2:
            sys.exit(f"the segment from node {i} to {j} is not a cubic curve")
        nodes.append(j)
        handles.append(tuple(offs))
        i = j
        if len(nodes) > 3:
            sys.exit("RUN has more than two curves; fair them two at a time")
    return nodes, handles


def segment_before(pts, a, s):
    """the segment arriving at node a along the run's direction: its points in run order"""
    n = len(pts)
    i = (a - s) % n
    offs = []
    while pts[i].type is None:
        offs.append(i)
        i = (i - s) % n
    return [i] + offs[::-1] + [a]


def segment_after(pts, b, s):
    n = len(pts)
    i = (b + s) % n
    offs = []
    while pts[i].type is None:
        offs.append(i)
        i = (i + s) % n
    return [b] + offs + [i]


def end_curvature(pts, idx, at_end, sgn):
    P = [(pts[i].x, pts[i].y) for i in idx]
    if len(P) == 4:
        return sgn * 1000 * curv(P, 1.0 if at_end else 0.0)
    return 0.0


def on_line(o, d, lo, hi, maxdeg=0.3):
    """whole-unit points q with q - o along d (within maxdeg), lo <= distance <= hi"""
    L = math.hypot(*d)
    u = (d[0] / L, d[1] / L)
    out = []
    for k in range(int(math.floor(lo)), int(math.ceil(hi)) + 1):
        c = (o[0] + u[0] * k, o[1] + u[1] * k)
        for q in {(math.floor(c[0]), math.floor(c[1])), (math.ceil(c[0]), math.ceil(c[1])),
                  (math.floor(c[0]), math.ceil(c[1])), (math.ceil(c[0]), math.floor(c[1]))}:
            v = (q[0] - o[0], q[1] - o[1])
            dist = math.hypot(*v)
            if lo <= dist <= hi and adiff(angle(v), angle(d)) <= maxdeg:
                out.append(q)
    return sorted(set(out))


def primitive(v):
    g = math.gcd(int(abs(v[0])), int(abs(v[1])))
    return (int(v[0]) // g, int(v[1]) // g) if g else None


def steps_near(d, maxdeg):
    out = []
    for a, b in itertools.product(range(-12, 13), repeat=2):
        if (a, b) != (0, 0) and math.gcd(a, b) == 1 and adiff(angle((a, b)), angle(d)) <= maxdeg:
            out.append((a, b))
    return out


def dist_to_poly(q, poly):
    best = math.inf
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((q[0] - x0) * dx + (q[1] - y0) * dy) / L2))
        best = min(best, math.hypot(q[0] - x0 - t * dx, q[1] - y0 - t * dy))
    return best


def outline_poly(pts, a, b, s, n_per=40):
    """the current outline from node a to node b along s, densely sampled"""
    n = len(pts)
    poly, i = [], a
    while i != b:
        j = (i + s) % n
        offs = []
        while pts[j].type is None:
            offs.append(j)
            j = (j + s) % n
        P = [(pts[k].x, pts[k].y) for k in [i] + offs + [j]]
        if len(P) == 4:
            seg = [bez(P, t / n_per) for t in range(n_per + 1)]
        else:
            seg = [P[0], P[-1]]
        poly += seg if not poly else seg[1:]
        i = j
    return poly


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ufo")
    ap.add_argument("glyph")
    ap.add_argument("run", metavar="C:A>B|C:A<B")
    ap.add_argument("--move", type=float, default=0.0)
    ap.add_argument("--turn", type=float, default=8.0)
    ap.add_argument("--ratio", type=float)
    ap.add_argument("--ratio-a", type=float)
    ap.add_argument("--ratio-b", type=float)
    ap.add_argument("--edge", metavar="TIP:N")
    ap.add_argument("--dev", type=float, default=1.5)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--pick", type=int, default=1)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    font = ufoLib2.Font.open(args.ufo)
    c, A, B, s = parse_run(args.run)
    contour = font[args.glyph].contours[c]
    pts = contour.points
    n = len(pts)
    P = lambda i: (pts[i].x, pts[i].y)
    nodes, handles = walk(pts, A, B, s)
    two = len(nodes) == 3
    M = nodes[1] if two else None

    # directions into A and out of B, and the curvature of the neighbouring segments
    before, after = segment_before(pts, A, s), segment_after(pts, B, s)
    q = before[-2]
    if P(q) == P(A):
        q = before[0]
    tA = (P(A)[0] - P(q)[0], P(A)[1] - P(q)[1])
    r = after[1] if P(after[1]) != P(B) else after[-1]
    tB = (P(r)[0] - P(B)[0], P(r)[1] - P(B)[1])

    # which way the run turns now: positive curvature means turning with it
    now_curves = [[P(A), P(handles[0][0]), P(handles[0][1]), P(nodes[1])]]
    if two:
        now_curves.append([P(M), P(handles[1][0]), P(handles[1][1]), P(B)])
    total = sum(curv(cv, i / SAMPLES) for cv in now_curves for i in range(SAMPLES + 1))
    sgn = 1 if total >= 0 else -1
    k_in = end_curvature(pts, before, True, sgn)
    k_out = end_curvature(pts, after, False, sgn)

    # the edge: A may move back along it
    edge_opts = [(P(A), None)]  # (A position, (edge handle indices, positions) or None)
    ref_from = before[0]
    if args.edge:
        tip_s, nsteps = args.edge.split(":")
        tip, nsteps = int(tip_s), int(nsteps)
        T = P(tip)
        idx, i = [], (A - s) % n
        while i != tip:
            idx.append(i)
            i = (i - s) % n
            if len(idx) > n:
                sys.exit("--edge: TIP not reached going back from A")
        offsets = [(P(k)[0] - T[0], P(k)[1] - T[1]) for k in idx if P(k) != T]
        if not offsets and P(A) != T:
            offsets = [(P(A)[0] - T[0], P(A)[1] - T[1])]   # one line segment TIP->A: A's own offset
        st = primitive(offsets[-1]) if offsets else None
        if not st:
            sys.exit("--edge: no straight edge between TIP and A")
        L2 = st[0] ** 2 + st[1] ** 2
        for o in offsets:
            if o[0] * st[1] - o[1] * st[0] != 0 or (o[0] * st[0] + o[1] * st[1]) % L2:
                sys.exit(f"--edge: the edge isn't at whole steps of {st} from node {tip}; run straighten.py first")
        stepnum = lambda v: round(((v[0] - T[0]) * st[0] + (v[1] - T[1]) * st[1]) / L2)
        kA = stepnum(P(A))
        prev_node = before[0]
        kP = stepnum(P(prev_node))
        eh = before[1:-1]  # the edge's last curve's handles, in run order (empty for a line)
        edge_opts = []
        for k in range(kA - nsteps, kA + 1):
            if k - kP < (2 if eh else 1):
                continue
            pos = (T[0] + k * st[0], T[1] + k * st[1])
            if eh:
                gap = max(1, round((k - kP) / 3))
                hp = [(T[0] + (kP + gap) * st[0], T[1] + (kP + gap) * st[1]),
                      (T[0] + (k - gap) * st[0], T[1] + (k - gap) * st[1])]
                edge_opts.append((pos, (eh, hp)))
            else:
                edge_opts.append((pos, None))
        tA = st
        ref_from = tip
    ref = outline_poly(pts, ref_from, after[-1], s)

    # a split held at A or B: the handle beside it must have this length (within 8%)
    len_in_A = math.hypot(P(A)[0] - P(before[-2])[0], P(A)[1] - P(before[-2])[1]) if len(before) == 4 else None
    len_out_B = math.hypot(P(after[1])[0] - P(B)[0], P(after[1])[1] - P(B)[1]) if len(after) == 4 else None
    if (args.ratio_a and not len_in_A) or (args.ratio_b and not len_out_B):
        sys.exit("--ratio-a/--ratio-b need a curve on the other side of that node")

    def held(q, node, want):
        return want is None or abs(math.hypot(q[0] - node[0], q[1] - node[1]) - want) <= 0.08 * want

    want_A = args.ratio_a * len_in_A if args.ratio_a else None
    want_B = len_out_B / args.ratio_b if args.ratio_b else None

    # the node between: positions and whole-unit tangents
    if two:
        M0 = P(M)
        tM = (P(handles[1][0])[0] - P(handles[0][1])[0], P(handles[1][0])[1] - P(handles[0][1])[1])
        R = args.move
        mids = [(M0[0] + dx, M0[1] + dy) for dx in range(-int(R), int(R) + 1) for dy in range(-int(R), int(R) + 1)
                if math.hypot(dx, dy) <= R + 1e-9]
        dirs = steps_near(tM, args.turn)
        if not dirs:
            sys.exit("no whole-unit tangent within --turn of the node between; raise --turn")

    def score(curves, Apos, Mpos):
        ks = [profile(cv, sgn) for cv in curves]
        flat = [v for k in ks for v in k]
        if min(flat) < -0.3:
            return None
        least, peak = min(flat), max(flat)
        jA = abs(ks[0][0] - k_in)
        jM = abs(ks[0][-1] - ks[1][0]) if two else 0.0
        jB = abs(ks[-1][-1] - k_out)
        move = (math.hypot(Mpos[0] - M0[0], Mpos[1] - M0[1]) if two else 0.0) + 0.1 * math.hypot(Apos[0] - P(A)[0], Apos[1] - P(A)[1])
        cost = 0.5 * peak + 0.4 * (peak - least) + 0.3 * jA + 0.5 * (jM + jB) + 0.5 * move
        return cost, least, peak, jA, jM, jB

    heap, count = [], 0

    def push(item):
        nonlocal count
        count += 1
        entry = (-item[0], count, item)
        if len(heap) < 3000:
            heapq.heappush(heap, entry)
        elif entry[0] > heap[0][0]:
            heapq.heapreplace(heap, entry)

    for Apos, eplan in edge_opts:
        mid_targets = mids if two else [P(B)]
        for Mpos in mid_targets:
            ch1 = math.hypot(Mpos[0] - Apos[0], Mpos[1] - Apos[1])
            if args.edge:
                Ls = math.hypot(*tA)
                hAs = [(Apos[0] + j * tA[0], Apos[1] + j * tA[1]) for j in range(1, 40) if 0.15 * ch1 <= j * Ls <= 0.75 * ch1]
            else:
                hAs = on_line(Apos, tA, 0.15 * ch1, 0.75 * ch1)
            hAs = [h for h in hAs if held(h, Apos, want_A)]
            if not two:
                hBs = [h for h in on_line(P(B), (-tB[0], -tB[1]), 0.15 * ch1, 0.75 * ch1) if held(h, P(B), want_B)]
                for hA, hB in itertools.product(hAs, hBs):
                    sc = score([[Apos, hA, hB, P(B)]], Apos, Mpos)
                    if sc:
                        push((sc[0], sc, Apos, eplan, hA, None, None, None, hB))
                continue
            ch2 = math.hypot(P(B)[0] - Mpos[0], P(B)[1] - Mpos[1])
            hBs = [h for h in on_line(P(B), (-tB[0], -tB[1]), 0.15 * ch2, 0.75 * ch2) if held(h, P(B), want_B)]
            for d in dirs:
                Ld = math.hypot(*d)
                ms = [m for m in range(1, 40) if 0.15 * ch1 <= m * Ld <= 0.75 * ch1]
                ns = [k for k in range(1, 40) if 0.15 * ch2 <= k * Ld <= 0.75 * ch2]
                # per handle length beside the node, the two best end handles; then pair them
                side1 = {}
                for m, hA in itertools.product(ms, hAs):
                    hin = (Mpos[0] - m * d[0], Mpos[1] - m * d[1])
                    k1 = profile([Apos, hA, hin, Mpos], sgn)
                    if min(k1) < -0.3:
                        continue
                    side1.setdefault(m, []).append((0.5 * max(k1) + 0.4 * (max(k1) - min(k1)) + 0.3 * abs(k1[0] - k_in), hA, hin))
                side2 = {}
                for k, hB in itertools.product(ns, hBs):
                    hout = (Mpos[0] + k * d[0], Mpos[1] + k * d[1])
                    k2 = profile([Mpos, hout, hB, P(B)], sgn)
                    if min(k2) < -0.3:
                        continue
                    side2.setdefault(k, []).append((0.5 * max(k2) + 0.4 * (max(k2) - min(k2)) + 0.5 * abs(k2[-1] - k_out), hB, hout))
                pairs = [(m, k, a1, a2) for m in side1 for k in side2
                         for a1 in sorted(side1[m])[:2] for a2 in sorted(side2[k])[:2]]
                for m, k, (_, hA, hin), (_, hB, hout) in pairs:
                    ratio = k / m
                    if args.ratio:
                        if abs(ratio - args.ratio) > 0.08 * args.ratio:
                            continue
                    elif not 1 / 3 <= ratio <= 3:
                        continue
                    sc = score([[Apos, hA, hin, Mpos], [Mpos, hout, hB, P(B)]], Apos, Mpos)
                    if sc:
                        push((sc[0], sc, Apos, eplan, hA, hin, Mpos, hout, hB, d, ratio))
    rows = []
    for _, _, item in heap:
        Apos, hA, hin, Mpos, hout, hB = item[2], item[4], item[5], item[6], item[7], item[8]
        curves = [[Apos, hA, hin, Mpos], [Mpos, hout, hB, P(B)]] if two else [[Apos, hA, hB, P(B)]]
        samples = [bez(cv, i / 12) for cv in curves for i in range(13)]
        if item[3]:
            samples += item[3][1]
        dev = max(dist_to_poly(q, ref) for q in samples)
        if dev > args.dev:
            continue
        rows.append((item[0] + 2 * dev, dev, item))
    rows.sort(key=lambda r: r[0])

    sc_now = score(now_curves, P(A), P(M) if two else P(B))
    ks_now = [profile(cv, sgn) for cv in now_curves]
    flat_now = [v for k in ks_now for v in k]
    jm_now = abs(ks_now[0][-1] - ks_now[1][0]) if two else 0.0
    print(f"{args.glyph} {args.run}: curvature x1000, positive with the run's turn; into A {k_in:.1f}, out of B {k_out:.1f}")
    mid = lambda v: f"  between {v:5.2f}" if two else ""
    print(f"  now:  least {min(flat_now):6.2f}  peak {max(flat_now):6.2f}  jumps A {abs(ks_now[0][0] - k_in):5.2f}"
          f"{mid(jm_now)}  B {abs(ks_now[-1][-1] - k_out):5.2f}" + ("" if sc_now else "  (turns against the run)"))
    if not rows:
        print("  no layout within --dev without curvature against the turn; try a larger --move, --turn or --dev")
        st = primitive((round(tA[0]), round(tA[1])))
        if st and max(abs(st[0]), abs(st[1])) > 12:
            print(f"  the edge into A runs in whole steps of {st}, too long for handles on its line: "
                  "corner.py lets A's handle turn a few degrees off it")
        return 1
    for rank, (cost, dev, item) in enumerate(rows[: args.top], 1):
        sc = item[1]
        desc = f"A {item[2]} " if args.edge else ""
        desc += f"handle {item[4]}"
        if two:
            desc += f" | {item[5]} node {item[6]} {item[7]} step {item[9]} ratio {item[10]:.2f}"
        desc += f" | {item[8]}"
        print(f"  {rank}: least {sc[1]:6.2f}  peak {sc[2]:6.2f}  jumps A {sc[3]:5.2f}{mid(sc[4])}  B {sc[5]:5.2f}  dev {dev:.2f} | {desc}")
    if not args.write:
        print("  dry run: nothing written")
        return 0
    cost, dev, item = rows[args.pick - 1]
    Apos, eplan, hA, hin, Mpos, hout, hB = item[2], item[3], item[4], item[5], item[6], item[7], item[8]
    moves = [(A, Apos), (handles[0][0], hA)]
    if eplan:
        moves += list(zip(eplan[0], eplan[1]))
    if two:
        moves += [(handles[0][1], hin), (M, Mpos), (handles[1][0], hout), (handles[1][1], hB)]
    else:
        moves += [(handles[0][1], hB)]
    for i, pos in moves:
        pts[i].x, pts[i].y = pos
    font.save()
    print(f"  written layout {args.pick}: {', '.join(f'{i}:{p[0]:g},{p[1]:g}' for i, p in moves)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
