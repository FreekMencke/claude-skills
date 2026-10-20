#!/usr/bin/env python3
"""Apply mechanical outline fixes to weight masters, the same way in every master.

usage:
  fix.py SOURCES... --ops compat smooth-flags collinear triplet-ratio extremes
         [--glyphs a b] [--ref 500] [--write | --out-dir DIR]
  fix.py SOURCES... --ops repredict --points "g:300:0:1" "g:300:0:2" --write

Without --write or --out-dir it only prints what it would change (dry run).
The reference master (--ref, default the middle one) is the shape reference:
collinear and triplet-ratio never move its points unless --touch-ref is given,
and kinks in it are left for you to fix by hand.
--write changes the UFOs in place (work on a git branch); --out-dir writes
fixed copies there and leaves the sources alone.

Operations run in this order, whatever order you list them in:
  redundant      remove an extra on-curve point that sits on a straight line (or on
                 top of its neighbour) in one master, when that makes it match the others
  compat         copy contour order, contour direction and start point from the reference
  smooth-flags   make a node smooth in every master when it is smooth in most of them,
                 straight (under 2°) wherever it is flagged smooth, and under 30° elsewhere.
                 A corner every master draws (even one bending only a few degrees) is
                 left a corner: see the SKILL.md note on small-bend corners
  merge          reduce points: remove a smooth node when one curve can replace the two
                 around it within --tol units in every master (end tangents kept, so the
                 neighbours still join smoothly), and drop nodes that sit on a straight
                 line. Keeps corners, extremes (unless --merge-extremes) and inflections.
                 Changes every master, the reference too, so it can't run with --only
  collinear      line up both handles of every smooth node, keeping handle lengths; turns
                 the handle the other masters disagree with; leaves bends over 30° alone
                 (those are flipped handles: use repredict)
  harmonize      make curvature continuous at smooth nodes (no step in the comb) by
                 sliding each node between its handle tips, per master; the in/out
                 ratio may then differ between masters (audit: ratio-mismatch)
  triplet-ratio  give every smooth handle-node-handle triplet the same in/out ratio in
                 all masters, by sliding the node between its handle tips (dekinks
                 interpolation and extrapolation)
  extremes       add a node at x/y extremes that every master has on the same segment
  repredict      replace the listed points in one master with where the other masters
                 say they should be (glyph:master:contour:point, numbering as in audit.py).
                 A curl or barb usually involves several points: give a range around the
                 spot (glyph:master:contour:6-10) and run without --write first; only points
                 more than --min-dev units off are moved
When the masters use whole units, changed glyphs are rounded back to whole units
and moves under 0.75 units are skipped (rounding would undo them); --round no keeps
decimals. Run audit.py and the repo's own checks after: rounding can bring kinks back.
Rebuilt contours lose point identifiers and names; plain coordinates are kept.
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402
from compat import Pt, align_glyph, best_ref, pts_of, reversed_pts  # noqa: E402

ORDER = ["redundant", "compat", "smooth-flags", "merge", "collinear", "harmonize", "triplet-ratio", "extremes", "repredict"]
KINK_TOL = 0.5  # degrees, matches audit.py --kink-tol default
ONLY = None      # labels of the masters fixes may move points in (None: all)
SNAP = False     # --snap-handles: after rounding, nudge short handles 1 unit to cut kinks
MIN_MOVE = 0.0   # with whole-unit rounding: skip moves under 0.75 units, rounding would undo them
KEEP_REF = True  # the reference master is the shape reference: fixes never move its points (--touch-ref to allow)


def set_contours(glyph, contours):
    glyph.clearContours()
    pen = glyph.getPointPen()
    for c in contours:
        pen.beginPath()
        for p in c:
            pen.addPoint((round(p.x, 2), round(p.y, 2)), segmentType=p.type, smooth=p.smooth)
        pen.endPath()


def contours_of(glyph):
    return [pts_of(c) for c in glyph.contours]


# ------------------------------------------------------------ operations

def op_redundant(name, glyphs, labels, ref_i, log):
    all_cs = [contours_of(g) for g in glyphs]
    if len({len(cs) for cs in all_cs}) != 1:
        return
    for mi, g in enumerate(glyphs):
        if ONLY is not None and labels[mi] not in ONLY:
            continue
        cs = all_cs[mi]
        changed = False
        for ci in range(len(cs)):
            # the point count most masters have for this contour (contours in stored order)
            counts = Counter(len(other[ci]) for other in all_cs)
            target, votes = counts.most_common(1)[0]
            if votes * 2 <= len(glyphs):
                continue
            while len(cs[ci]) > target:
                c = cs[ci]
                n = len(c)
                drop = None
                for i, p in enumerate(c):
                    if p.type not in ("line", "curve"):
                        continue
                    a, b = c[(i - 1) % n], c[(i + 1) % n]
                    if p.type == "line" and a.type is not None and b.type == "line":
                        ab = L.sub(L.xy(b), L.xy(a))
                        off = abs(L.cross(L.unit(ab), L.sub(L.xy(p), L.xy(a)))) if L.norm(ab) > 0 else 0
                        if off < 0.5:
                            drop = i
                            break
                    if p.type == "line" and a.type is not None and L.dist(L.xy(a), L.xy(p)) < 0.5:
                        drop = i
                        break
                if drop is None:
                    break
                del c[drop]
                changed = True
                log[name].append(f"{labels[mi]}: removed redundant point {drop} in contour {ci}")
        if changed:
            set_contours(g, cs)


def op_compat(name, glyphs, labels, ref_i, log):
    ref_i = best_ref(name, glyphs, labels, ref_i)
    aligned, corr, iss = align_glyph(name, glyphs, labels, ref_i)
    for mi, g in enumerate(glyphs):
        if mi == ref_i or corr[mi] is None:
            continue
        if ONLY is not None and labels[mi] not in ONLY:
            c = corr[mi]
            if c["perm"] != list(range(len(c["perm"]))) or c["reverse"] or c["rotate"]:
                log[name].append(f"{labels[mi]}: needs contour order/direction/start point fixed, but it is not in --only; left alone")
            continue
        c = corr[mi]
        refcomps = [x.baseGlyph for x in glyphs[ref_i].components]
        comps = [x.baseGlyph for x in g.components]
        if comps != refcomps and sorted(comps) == sorted(refcomps):
            pool = list(g.components)
            g.components[:] = [pool.pop(next(k for k, x in enumerate(pool) if x.baseGlyph == b)) for b in refcomps]
            log[name].append(f"{labels[mi]}: component order matched to {labels[ref_i]}")
        if c["perm"] == list(range(len(c["perm"]))) and not c["reverse"] and not c["rotate"]:
            continue
        cs = contours_of(g)
        out = []
        for ci in range(len(cs)):
            pts = cs[c["perm"][ci]]
            if ci in c["reverse"]:
                pts = reversed_pts(pts)
            r = c["rotate"].get(ci)
            if r:
                pts = pts[r:] + pts[:r]
            out.append(pts)
        set_contours(g, out)
        what = []
        if c["perm"] != list(range(len(c["perm"]))):
            what.append(f"contour order {c['perm']}")
        if c["reverse"]:
            what.append(f"reversed contours {sorted(c['reverse'])}")
        if c["rotate"]:
            what.append(f"start points {c['rotate']}")
        log[name].append(f"{labels[mi]}: " + ", ".join(what))


def _aligned_or_none(name, glyphs, labels, ref_i, log, op):
    aligned, corr, iss = align_glyph(name, glyphs, labels, ref_i)
    if aligned is None or any(i["code"] in ("contour-order", "direction", "start-point") for i in iss):
        log[name].append(f"skipped {op}: not compatible yet (run compat / fix point counts first)")
        return None
    return aligned


def plan_merges(cs_by_master, ci, tol, keep_extremes=True, cache=None, greedy=True):
    """Nodes that can go from contour ci in every master: each removal replaces the two
    curves around a smooth node by one curve that stays within tol units of the
    ORIGINAL outline over that span in every master (so errors don't pile up over
    successive merges; end tangents kept, so the neighbours still join smoothly), or
    drops a node that sits on a straight line. Greedy: the best-fitting merge first.
    Returns (new contours per master, removed count, worst error). With greedy=False
    it only counts the single removals that would pass."""
    cache = {} if cache is None else cache
    n = len(cs_by_master)
    cs = [list(c[ci]) for c in cs_by_master]
    closed = cs[0][0].type != "move"
    # original samples of each segment, keyed by the identity of its start node
    spans = []
    for c in cs:
        d = {}
        for (i0, offs, i1, typ) in L.segments(c, closed):
            d[id(c[i0])] = L.segment_samples(c, i0, offs, i1)
        spans.append(d)
    removed, worst = 0, 0.0
    while True:
        ref = cs[0]
        ok = []
        for i, p in enumerate(ref):
            if p.type == "curve" and i >= 2 and ref[i - 1].type is None and ref[i - 2].type is None:
                # a curve whose handles lie on its chord in every master: make it a line
                a = (i - 3) % len(ref)
                if ref[a].type is not None:
                    flat_all = True
                    for c in cs:
                        P0, P1, P2, P3 = (L.xy(c[k]) for k in (a, i - 2, i - 1, i))
                        ch = L.sub(P3, P0)
                        ln = L.norm(ch)
                        if ln < 2:
                            flat_all = False
                            break
                        u = L.unit(ch)
                        if max(abs(L.cross(u, L.sub(P1, P0))), abs(L.cross(u, L.sub(P2, P0)))) >= min(0.5, tol) or not (
                                0 <= L.dot(L.sub(P1, P0), u) <= ln and 0 <= L.dot(L.sub(P2, P0), u) <= ln):
                            flat_all = False
                            break
                    if flat_all:
                        # the joins at both ends must keep their angle once the handles go
                        for c in cs:
                            line = L.sub(L.xy(c[i]), L.xy(c[a]))
                            for node, hnd, sign in ((a, i - 2, 1), (i, i - 1, -1)):
                                tin, tout = L.node_tangents(c, node, closed)
                                if not tin or not tout:
                                    continue
                                before = L.angle_deg(tin, tout)
                                after = L.angle_deg(tin, line) if node == i else L.angle_deg(line, tout)
                                if abs(after - before) > 2:
                                    flat_all = False
                    if flat_all:
                        ok.append((0.0, "flat", i, None))
                        continue
            if p.type == "line":
                # a node on a straight line between two straight segments
                a, b = L.neighbors(ref, i, closed)
                if a is None or b is None or ref[a].type is None or ref[b].type != "line":
                    continue
                errs = []
                for m, c in enumerate(cs):
                    A, N, B = L.xy(c[a]), L.xy(c[i]), L.xy(c[b])
                    ab = L.sub(B, A)
                    if L.norm(ab) < 1e-6 or L.dot(L.sub(N, A), ab) <= 0 or L.dot(L.sub(B, N), ab) <= 0:
                        break
                    u = L.unit(ab)
                    span = spans[m].get(id(c[a]), []) + spans[m].get(id(c[i]), [])
                    errs.append(max(abs(L.cross(u, L.sub(q, A))) for q in span) if span else abs(L.cross(u, L.sub(N, A))))
                else:
                    e = max(errs)
                    if e <= min(tol, 0.5):
                        ok.append((e, "line", (a, i, b), None))
                continue
            idx = L.merge_candidate(ref, i, closed)
            if idx is None:
                continue
            cases = []
            for mi, c in enumerate(cs):
                # the reference (cs[0]) must be nearly straight there; other masters may
                # carry the small kinks whole-unit rounding leaves (the node goes anyway)
                pre = L.merge_preconditions(c, idx, keep_extremes, max_bend=3.0 if mi == 0 else 5.0)
                if pre is None:
                    break
                samples = spans[mi][id(c[idx[0]])] + spans[mi][id(c[idx[3]])][1:]
                cases.append(pre[:2] + pre[2:] + (samples,))
            else:
                key = tuple((c[k].x, c[k].y) for c in cs for k in idx) + tuple(len(x[4]) for x in cases)
                if key not in cache:
                    fit = L.fit_joint_fixed_tangents([(A, t0, B, t3, S) for (A, t0, B, t3, S) in cases])
                    if fit is not None and fit[1] <= tol and all(
                            L.merge_postconditions(c, idx, p1, p2) for c, (p1, p2) in zip(cs, fit[0])):
                        cache[key] = fit
                    else:
                        cache[key] = None
                fit = cache[key]
                if fit is not None:
                    ok.append((fit[1], "curve", idx, [(p1, p2, fit[1]) for p1, p2 in fit[0]]))
        if not greedy:
            return cs, len(ok), min((o[0] for o in ok), default=0.0)
        if not ok:
            break
        e, kind, where, res = min(ok, key=lambda o: o[0])
        for m in range(n):
            c = cs[m]
            if kind == "flat":
                i = where
                node = c[i]
                line_node = Pt(node.x, node.y, "line", node.smooth)
                if id(node) in spans[m]:
                    spans[m][id(line_node)] = spans[m].pop(id(node))
                cs[m] = [q for k, q in enumerate(c) if k not in (i - 1, i - 2)]
                cs[m][cs[m].index(node)] = line_node
                continue
            if kind == "line":
                a, i, b = where
                spans[m][id(c[a])] = spans[m].get(id(c[a]), []) + spans[m].pop(id(c[i]), [])[1:]
                cs[m] = c[:i] + c[i + 1:]
                continue
            h1, h2, _ = res[m]
            A, N = c[where[0]], c[where[3]]
            spans[m][id(A)] = spans[m][id(A)] + spans[m].pop(id(N))[1:]
            dropped = set(where[1:6])
            new = []
            for k, p in enumerate(c):
                if k == where[1]:
                    new.append(Pt(h1[0], h1[1], None, False))
                    new.append(Pt(h2[0], h2[1], None, False))
                elif k not in dropped:
                    new.append(p)
            cs[m] = new
        removed += 1
        worst = max(worst, e)
    return cs, removed, worst


def op_merge(name, glyphs, labels, ref_i, log, tol, keep_extremes=True):
    # rounding to whole units afterwards moves curves by up to about 0.25 more
    fit_tol = max(tol - 0.25, 0.1) if MIN_MOVE > 0 else tol
    if ONLY is not None:
        log[name].append("skipped merge: it removes the same nodes from every master, so it can't run with --only")
        return
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "merge")
    if aligned is None:
        return
    order = [ref_i] + [m for m in range(len(glyphs)) if m != ref_i]
    new = [[list(c) for c in a] for a in aligned]
    total, worst, cache = 0, 0.0, {}
    for ci in range(len(aligned[ref_i])):
        cs, removed, w = plan_merges([aligned[m] for m in order], ci, fit_tol, keep_extremes, cache)
        if removed:
            for k, m in enumerate(order):
                new[m][ci] = cs[k]
            total += removed
            worst = max(worst, w)
    if total:
        for m in range(len(glyphs)):
            set_contours(glyphs[m], new[m])
        before = sum(1 for c in aligned[ref_i] for p in c if p.type)
        log[name].append(f"removed {total} of {before} nodes in every master; curves moved at most {worst:.2f} units")


def op_smooth_flags(name, glyphs, labels, ref_i, log):
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "smooth-flags")
    if aligned is None:
        return
    n = len(glyphs)
    for ci, rc in enumerate(aligned[ref_i]):
        closed = rc[0].type != "move"
        for i, p in enumerate(rc):
            if p.type is None:
                continue
            flags = [aligned[m][ci][i].smooth for m in range(n)]
            if all(flags) or not any(flags):
                continue
            devs = []
            for m in range(n):
                t_in, t_out = L.node_tangents(aligned[m][ci], i, closed)
                devs.append(L.angle_deg(t_in, t_out) if t_in and t_out else 180)
            straight_where_smooth = all(devs[m] < 2 for m in range(n) if flags[m])
            if sum(flags) * 2 > n and straight_where_smooth and max(devs) < 30:
                for m in range(n):
                    glyphs[m].contours[ci].points[i].smooth = True
                odd = ", ".join(f"{labels[m]} bends {devs[m]:.1f}°" for m in range(n) if not flags[m])
                log[name].append(f"node {ci}:{i} set smooth in all masters ({odd}; collinear will straighten it, check the render)")
            else:
                log[name].append(f"node {ci}:{i} left alone: smooth in {sum(flags)}/{n} masters, bends up to {max(devs):.1f}°")


def op_collinear(name, glyphs, labels, ref_i, log):
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "collinear")
    if aligned is None:
        return
    count = 0
    n_m = len(glyphs)
    locs = [float(l) if l.replace(".", "", 1).isdigit() else k for k, l in enumerate(labels)]

    def handle_angle(m, ci, k, i):
        c = glyphs[m].contours[ci].points
        v = (c[k].x - c[i].x, c[k].y - c[i].y) if k != i else (0, 0)
        return math.degrees(math.atan2(v[1], v[0]))

    def predicted_error(mi, ci, k, i):
        """How far handle k of node i in master mi is from where the other masters point it."""
        others = [m for m in range(n_m) if m != mi]
        angs = [handle_angle(m, ci, k, i) for m in others]
        base = angs[0]
        angs = [base + ((x - base + 180) % 360 - 180) for x in angs]
        if len(others) >= 2:
            xs = [locs[m] for m in others]
            mx, my = sum(xs) / len(xs), sum(angs) / len(angs)
            ss = sum((x - mx) ** 2 for x in xs) or 1
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, angs)) / ss
            pred = my + slope * (locs[mi] - mx)
        else:
            pred = angs[0]
        mine = handle_angle(mi, ci, k, i)
        return abs((mine - pred + 180) % 360 - 180)

    for mi, g in enumerate(glyphs):
        if (KEEP_REF and mi == ref_i) or (ONLY is not None and labels[mi] not in ONLY):
            continue
        for ci, contour in enumerate(g.contours):
            pts = contour.points
            closed = pts[0].type != "move"
            for i, p in enumerate(pts):
                if p.type is None or not p.smooth:
                    continue
                a, b = L.neighbors(pts, i, closed)
                if a is None or b is None:
                    continue
                A, B, N = pts[a], pts[b], (p.x, p.y)
                va, vb = L.sub(N, (A.x, A.y)), L.sub((B.x, B.y), N)
                if L.norm(va) < 1e-6 or L.norm(vb) < 1e-6:
                    continue
                # same threshold as audit.py: leave bends that integer rounding explains
                rounding = 2 * math.degrees(math.atan(0.71 / max(min(L.norm(va), L.norm(vb)), 0.71)))
                dev = L.angle_deg(va, vb)
                if dev <= max(KINK_TOL, rounding):
                    continue
                if A.type is None and B.type is None:
                    la, lb = L.norm(va), L.norm(vb)
                    if dev > 30:
                        log[name].append(f"{labels[mi]}: node {ci}:{i} bends {dev:.1f}°: not a kink but a flipped handle; repredict it")
                        continue
                    ea = predicted_error(mi, ci, a, i) if n_m > 1 else 0
                    eb = predicted_error(mi, ci, b, i) if n_m > 1 else 0
                    if ea > eb + 2:      # the in-handle is the odd one: turn it onto the out-handle
                        t = L.unit(vb)
                    elif eb > ea + 2:    # the out-handle is the odd one
                        t = L.unit(va)
                    elif dev <= 10:      # unclear which: length-weighted average, the longer handle moves less
                        t = L.unit(L.add(L.mul(L.unit(va), la), L.mul(L.unit(vb), lb)))
                    else:
                        log[name].append(f"{labels[mi]}: node {ci}:{i} bends {dev:.1f}° and the masters don't say which handle is wrong; fix by hand or repredict")
                        continue
                    nA = (N[0] - t[0] * la, N[1] - t[1] * la)
                    nB = (N[0] + t[0] * lb, N[1] + t[1] * lb)
                    if max(L.dist(nA, (A.x, A.y)), L.dist(nB, (B.x, B.y))) < MIN_MOVE:
                        continue  # whole-unit rounding would undo it
                    A.x, A.y = nA
                    B.x, B.y = nB
                    if dev > 3:
                        log[name].append(f"{labels[mi]}: node {ci}:{i} straightened from {dev:.1f}° (check the render)")
                elif A.type is not None and B.type is None:   # line in, handle out
                    t, lb = L.unit(va), L.norm(vb)
                    nB = (N[0] + t[0] * lb, N[1] + t[1] * lb)
                    if L.dist(nB, (B.x, B.y)) < MIN_MOVE:
                        continue
                    B.x, B.y = nB
                elif B.type is not None and A.type is None:   # handle in, line out
                    t, la = L.unit(vb), L.norm(va)
                    nA = (N[0] - t[0] * la, N[1] - t[1] * la)
                    if L.dist(nA, (A.x, A.y)) < MIN_MOVE:
                        continue
                    A.x, A.y = nA
                else:
                    continue
                count += 1
    if count:
        log[name].append(f"lined up handles at {count} smooth nodes")


def op_harmonize(name, glyphs, labels, ref_i, log):
    """Curvature-continuous (G2) smooth nodes: slide each smooth node between its two
    handle tips to where the curvature is the same on both sides. The end curvature of
    a cubic is 2/3 * h / d**2 (h: distance of the far handle from the tangent line, d:
    near handle length), so equal curvature puts the node at sqrt(h1) : sqrt(h2)."""
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "harmonize")
    if aligned is None:
        return
    moved = 0
    for mi, g in enumerate(glyphs):
        if (KEEP_REF and mi == ref_i) or (ONLY is not None and labels[mi] not in ONLY):
            continue
        for c in g.contours:
            pts = c.points
            n = len(pts)
            if n < 7 or pts[0].type == "move":
                continue
            for i, p in enumerate(pts):
                idx = L.merge_candidate(pts, i)
                if idx is None or not p.smooth:
                    continue
                A, a1, a2, N, b1, b2, B = (L.xy(pts[k]) for k in idx)
                line = L.sub(b1, a2)
                ln = L.norm(line)
                if ln < 1e-6 or L.angle_deg(L.sub(N, a2), L.sub(b1, N)) > 1.0:
                    continue  # handles not in line: run collinear first
                u = L.unit(line)
                h1 = L.cross(u, L.sub(a1, a2))
                h2 = L.cross(u, L.sub(b2, a2))
                if h1 * h2 <= 0 or abs(h1) < 0.5 or abs(h2) < 0.5:
                    continue  # an inflection at the node, or a nearly straight side
                r = math.sqrt(abs(h1)) / (math.sqrt(abs(h1)) + math.sqrt(abs(h2)))
                new = (a2[0] + r * line[0], a2[1] + r * line[1])
                if L.dist(new, N) < max(MIN_MOVE, 0.05):
                    continue
                pts[i].x, pts[i].y = new
                moved += 1
    if moved:
        log[name].append(f"harmonized {moved} smooth node(s) (node slid between its handle tips to even out the curvature)")


def op_triplet_ratio(name, glyphs, labels, ref_i, log, tol=0.01):
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "triplet-ratio")
    if aligned is None:
        return
    n = len(glyphs)
    moved = 0
    for ci, rc in enumerate(aligned[ref_i]):
        closed = rc[0].type != "move"
        for i, p in enumerate(rc):
            if p.type is None or not all(aligned[m][ci][i].smooth for m in range(n)):
                continue
            a, b = L.neighbors(rc, i, closed)
            if a is None or b is None or rc[a].type is not None or rc[b].type is not None:
                continue
            ratios, tips = [], []
            for m in range(n):
                c = glyphs[m].contours[ci].points
                A, N, B = (c[a].x, c[a].y), (c[i].x, c[i].y), (c[b].x, c[b].y)
                ab = L.dist(A, B)
                if ab < 1e-6:
                    break
                ratios.append(L.dist(A, N) / ab)
                tips.append((A, B))
            else:
                angles = [math.degrees(math.atan2(B[1] - A[1], B[0] - A[0])) for A, B in tips]
                spread = max(abs(((x - angles[0]) + 180) % 360 - 180) for x in angles)
                if max(ratios) - min(ratios) <= tol or spread < 0.5:
                    continue  # same ratio, or the tangent never turns: no kink either way
                r = ratios[ref_i] if KEEP_REF else sorted(ratios)[n // 2]
                for m in range(n):
                    if (KEEP_REF and m == ref_i) or (ONLY is not None and labels[m] not in ONLY):
                        continue
                    (A, B) = tips[m]
                    pt = glyphs[m].contours[ci].points[i]
                    new = (A[0] + r * (B[0] - A[0]), A[1] + r * (B[1] - A[1]))
                    if L.dist(new, (pt.x, pt.y)) < MIN_MOVE:
                        continue  # whole-unit rounding would undo it
                    pt.x, pt.y = new
                    moved += 1
    if moved:
        log[name].append(f"matched handle ratios at {moved} node(s) (node slid between its handle tips)")


def op_extremes(name, glyphs, labels, ref_i, log):
    if ONLY is not None:
        log[name].append("skipped extremes: it adds nodes to every master, so it can't run with --only")
        return
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "extremes")
    if aligned is None:
        return
    n = len(glyphs)
    new = [[list(c) for c in a] for a in aligned]
    added = 0
    for ci in range(len(aligned[ref_i])):
        rc = aligned[ref_i][ci]
        closed = rc[0].type != "move"
        segs = [s for s in L.segments(rc, closed) if s[3] == "curve" and len(s[1]) == 2]
        # work from the end so earlier indices stay valid
        plan = []
        for (i0, offs, i1, typ) in segs:
            per = []
            for m in range(n):
                c = aligned[m][ci]
                P = [L.xy(c[k]) for k in (i0, offs[0], offs[1], i1)]
                ts = []
                for axis in (0, 1):
                    for t in L.cubic_extrema_ts(*P, axis):
                        if 0.03 < t < 0.97:
                            v = L.cubic_at(*P, t)[axis]
                            if v > max(P[0][axis], P[3][axis]) + 1 or v < min(P[0][axis], P[3][axis]) - 1:
                                ts.append((t, axis))
                per.append(sorted(ts))
            if not per[0] or any([a for _, a in p] != [a for _, a in per[0]] for p in per):
                if any(per):
                    log[name].append(f"extreme on segment ending {ci}:{i1} not in every master the same way; add it by hand")
                continue
            plan.append((i0, offs, i1, per))
        for (i0, offs, i1, per) in sorted(plan, key=lambda x: (x[0] > x[2], -x[0])):  # wrapping segment last
            for m in range(n):
                c = new[m][ci]
                P = [L.xy(c[k]) for k in (i0, offs[0], offs[1], i1)]
                pieces, rest, t_done = [], P, 0.0
                for t, axis in per[m]:
                    lt = (t - t_done) / (1 - t_done)
                    left, rest = L.cubic_split(*rest, lt)
                    # snap the new node's handles to the axis of the extreme
                    pieces.append((left, axis))
                    t_done = t
                pts = []
                for (left, axis) in pieces:
                    h1, h2, node = left[1], left[2], left[3]
                    pts.append((h1, None, False, None))
                    pts.append((h2, None, False, axis))
                    pts.append((node, "curve", True, axis))
                pts.append((rest[1], None, False, None))
                pts.append((rest[2], None, False, None))
                # snap: handles either side of an extreme share the node's x (x-extreme) or y
                for k, (pt, typ, sm, axis) in enumerate(pts):
                    if typ == "curve":
                        node = pt
                        for kk in (k - 1, k + 1):
                            q = list(pts[kk][0])
                            q[axis] = node[axis]
                            pts[kk] = (tuple(q),) + pts[kk][1:]
                repl = [Pt(pt[0], pt[1], typ, sm) for pt, typ, sm, _ in pts]
                end_type = c[i1]
                seg_pts = repl + [end_type]
                if i0 < i1:
                    c[i0 + 1:i1 + 1] = seg_pts
                else:  # segment wraps past the contour start
                    c[i0 + 1:] = []
                    c[:i1 + 1] = seg_pts
            added += len(per[0])
    if added:
        for m in range(n):
            set_contours(glyphs[m], new[m])
        log[name].append(f"added {added} extreme point(s) in every master")


def _loo(xs, vals, x):
    if len(vals) == 1:
        return vals[0]
    mean = sum(xs) / len(xs)
    vm = sum(vals) / len(vals)
    ss = sum((a - mean) ** 2 for a in xs) or 1.0
    slope = sum((a - mean) * (v - vm) for a, v in zip(xs, vals)) / ss
    return vm + slope * (x - mean)


def op_repredict(name, glyphs, labels, ref_i, log, points, locs):
    """Move points of one master to where the other masters put them. A single point
    follows its own trend across the masters. A range is measured relative to the
    two points just outside it, so the master keeps its own placement of that part
    of the glyph and only the shape is restored. Coordinates all other masters share
    exactly (baselines, stem edges) are kept exact."""
    aligned = _aligned_or_none(name, glyphs, labels, ref_i, log, "repredict")
    if aligned is None:
        return
    groups = defaultdict(list)  # (master, contour) -> point indices
    for (mlabel, ci, pi, min_dev) in points:
        groups[(mlabel, ci)].append((pi, min_dev))
    for (mlabel, ci), plist in groups.items():
        m = labels.index(mlabel)
        if ONLY is not None and mlabel not in ONLY:
            log[name].append(f"{mlabel}: contour {ci} points {[p for p, _ in plist]} not moved: {mlabel} is not in --only")
            continue
        n = len(aligned[m][ci])
        bad = [p for p, _ in plist if not 0 <= p < n]
        if bad:
            log[name].append(f"{mlabel}: contour {ci} has {n} points; ignored point numbers {bad}")
        plist = [(p, d) for p, d in plist if 0 <= p < n]
        if not plist:
            continue
        idx = sorted(p for p, _ in plist)
        # anchors: the nearest points before and after the group that are not in it
        a = (idx[0] - 1) % n
        while a in idx:
            a = (a - 1) % n
        b = (idx[-1] + 1) % n
        while b in idx:
            b = (b + 1) % n
        others = [k for k in range(len(glyphs)) if k != m]
        xs = [locs[k] for k in others]

        def frame(k):
            A, B = L.xy(aligned[k][ci][a]), L.xy(aligned[k][ci][b])
            d = L.sub(B, A)
            return A, d, (-d[1], d[0]), L.norm(d)

        Am, dm, pm, lm = frame(m)
        for pi, min_dev in plist:
            absolute = (_loo(xs, [aligned[k][ci][pi][0] for k in others], locs[m]),
                        _loo(xs, [aligned[k][ci][pi][1] for k in others], locs[m]))
            if len(plist) > 1 and lm > 1 and all(frame(k)[3] > 1 for k in others):
                us, vs = [], []
                for k in others:
                    A, d, pp, ln = frame(k)
                    rel = L.sub(L.xy(aligned[k][ci][pi]), A)
                    us.append(L.dot(rel, d) / ln ** 2)
                    vs.append(L.dot(rel, pp) / ln ** 2)
                u, v = _loo(xs, us, locs[m]), _loo(xs, vs, locs[m])
                pred = (Am[0] + u * dm[0] + v * pm[0], Am[1] + u * dm[1] + v * pm[1])
            else:  # a single point (or anchors on top of each other): its own trend
                pred = absolute
            # a coordinate every other master shares exactly (a baseline, a stem edge) stays exact
            pred = tuple(aligned[others[0]][ci][pi][ax] if max(aligned[k][ci][pi][ax] for k in others) -
                         min(aligned[k][ci][pi][ax] for k in others) < 0.5 else pred[ax] for ax in (0, 1))
            p = glyphs[m].contours[ci].points[pi]
            dev = L.dist((p.x, p.y), pred)
            if dev < min_dev:
                log[name].append(f"{mlabel}: point {ci}:{pi} kept: only {dev:.1f} units from where the other masters put it")
                continue
            how = f"relative to points {a} and {b}" if len(plist) > 1 else "following its own trend"
            log[name].append(f"{mlabel}: point {ci}:{pi} ({p.x:.1f}, {p.y:.1f}) -> ({pred[0]:.1f}, {pred[1]:.1f}), {dev:.1f} units, "
                             f"from the other masters ({how})")
            p.x, p.y = round(pred[0], 2), round(pred[1], 2)


def round_keeping_directions(glyph):
    """Round a glyph to whole units. Nodes round normally; each handle takes whichever
    of its four neighbouring whole-unit positions keeps its direction from its node
    closest to the unrounded direction, so rounding doesn't put kinks in short handles."""
    for c in glyph.contours:
        pts = c.points
        n = len(pts)
        exact = [(p.x, p.y) for p in pts]
        for p in pts:
            if p.type is not None:
                p.x, p.y = round(p.x), round(p.y)
        for i, p in enumerate(pts):
            if p.type is not None:
                continue
            # the node this handle belongs to: the on-curve neighbour on its side
            k = None
            for j in ((i - 1) % n, (i + 1) % n):
                if pts[j].type is not None:
                    k = j
                    break
            if k is None:
                p.x, p.y = round(p.x), round(p.y)
                continue
            want = L.sub(exact[i], exact[k])
            if L.norm(want) < 1e-6:
                p.x, p.y = pts[k].x, pts[k].y
                continue
            fx, fy = math.floor(exact[i][0]), math.floor(exact[i][1])
            best = None
            for cx in (fx, fx + 1):
                for cy in (fy, fy + 1):
                    v = (cx - pts[k].x, cy - pts[k].y)
                    if L.norm(v) < 1e-6:
                        continue
                    score = (round(L.angle_deg(v, want), 3), L.dist((cx, cy), exact[i]))
                    if best is None or score < best[0]:
                        best = (score, cx, cy)
            p.x, p.y = (best[1], best[2]) if best else (round(p.x), round(p.y))


def snap_smooth(glyph):
    """After rounding: at each smooth node between two handles, try the shorter handle's
    tip one unit either way and keep the position that bends least."""
    for c in glyph.contours:
        pts = c.points
        closed = pts[0].type != "move"
        for i, p in enumerate(pts):
            if p.type is None or not p.smooth:
                continue
            a, b = L.neighbors(pts, i, closed)
            if a is None or b is None or pts[a].type is not None or pts[b].type is not None:
                continue
            A, B, N = pts[a], pts[b], (p.x, p.y)
            short, other = (A, B) if L.dist((A.x, A.y), N) <= L.dist((B.x, B.y), N) else (B, A)
            if L.dist((short.x, short.y), N) < 1:
                continue

            def bend(sx, sy):
                v1 = L.sub(N, (other.x, other.y)) if other is A else L.sub(N, (sx, sy))
                v2 = L.sub((sx, sy), N) if other is A else L.sub((other.x, other.y), N)
                return L.angle_deg(v1, v2)
            best = (bend(short.x, short.y), short.x, short.y)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cand = (bend(short.x + dx, short.y + dy), short.x + dx, short.y + dy)
                    if cand[0] < best[0] - 0.05:
                        best = cand
            short.x, short.y = best[1], best[2]


def all_integer(masters):
    """True when the masters use whole units (99% of points or more): the repo's convention."""
    tot = whole = 0
    for m in masters:
        for g in m.font:
            for c in g.contours:
                for p in c.points:
                    tot += 1
                    whole += float(p.x).is_integer() and float(p.y).is_integer()
    return tot > 0 and whole >= 0.99 * tot


# ------------------------------------------------------------ driver

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--ops", nargs="+", required=True, choices=ORDER)
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--ref")
    ap.add_argument("--points", nargs="*", default=[],
                    help="glyph:master:contour:point for repredict; a range (R:900:0:6-10) moves only points more than --min-dev off")
    ap.add_argument("--min-dev", type=float, default=3.0, help="for point ranges: leave points closer than this to the prediction (default 3 units)")
    ap.add_argument("--tol", type=float, default=1.0, help="merge: how far a merged curve may move, in units (default 1.0)")
    ap.add_argument("--merge-extremes", action="store_true", help="merge: also remove nodes at x/y extremes (kept by default)")
    ap.add_argument("--round", choices=["auto", "yes", "no"], default="auto",
                    help="round changed glyphs to whole units (auto: when 99%% of the masters' points already are)")
    ap.add_argument("--snap-handles", action="store_true",
                    help="after rounding, nudge handles one unit where that bends a smooth node less (fewer kinks, but on one test font more lumps)")
    ap.add_argument("--only", nargs="+", help="masters (labels) whose points may be moved; others stay as drawn (smooth flags excepted)")
    ap.add_argument("--touch-ref", action="store_true", help="let collinear and triplet-ratio move the reference master's points too")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="change the UFOs in place")
    g.add_argument("--out-dir", help="write fixed copies here")
    opt = ap.parse_args(argv)

    if opt.out_dir:
        # copy first, then load the copies
        out = Path(opt.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        masters, doc = L.load_sources(opt.sources)
        specs = []
        for m in masters:
            dst = out / m.path.name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(m.path, dst)
            specs.append(f"{m.label}={dst}")
        masters, _ = L.load_sources(specs)
    else:
        masters, doc = L.load_sources(opt.sources)
    labels = [m.label for m in masters]
    ref_i = labels.index(opt.ref) if opt.ref else len(masters) // 2
    # place masters by measured stem width, like audit.py and derive.py
    stem_locs = [L.ref_stem(m.font)[1] for m in masters]
    locs = stem_locs if all(stem_locs) and len(set(stem_locs)) == len(stem_locs) else [m.loc for m in masters]
    global KEEP_REF, ONLY
    KEEP_REF = not opt.touch_ref
    ONLY = set(opt.only) if opt.only else None
    names = L.common_glyphs([m.font for m in masters], opt.glyphs)
    pts_by_glyph = defaultdict(list)
    for spec in opt.points:
        gname, ml, ci, pi = spec.rsplit(":", 3)
        if "-" in pi:  # a range of point numbers, e.g. 6-10
            lo, hi = (int(x) for x in pi.split("-"))
            for k in range(lo, hi + 1):
                pts_by_glyph[gname].append((ml, int(ci), k, opt.min_dev))
        else:
            pts_by_glyph[gname].append((ml, int(ci), int(pi), 0.0))
    if "repredict" in opt.ops and not opt.points:
        sys.exit("repredict needs --points")

    # decide before any change: the masters as they are now show the repo's convention
    do_round = opt.round == "yes" or (opt.round == "auto" and all_integer(masters))
    global MIN_MOVE, SNAP
    MIN_MOVE = 0.75 if do_round else 0.0
    SNAP = opt.snap_handles
    log = defaultdict(list)
    tagged = []   # (op, glyph, line)
    touched = set()   # (glyph, master index) whose points changed
    for name in names:
        glyphs = [m.font[name] for m in masters]
        snap = [[(p.x, p.y, p.type) for c in g.contours for p in c.points] for g in glyphs]
        for op in [o for o in ORDER if o in opt.ops]:
            before = len(log[name])
            if op == "redundant":
                op_redundant(name, glyphs, labels, ref_i, log)
            elif op == "compat":
                op_compat(name, glyphs, labels, ref_i, log)
            elif op == "smooth-flags":
                op_smooth_flags(name, glyphs, labels, ref_i, log)
            elif op == "merge":
                op_merge(name, glyphs, labels, ref_i, log, opt.tol, not opt.merge_extremes)
            elif op == "collinear":
                op_collinear(name, glyphs, labels, ref_i, log)
            elif op == "harmonize":
                op_harmonize(name, glyphs, labels, ref_i, log)
            elif op == "triplet-ratio":
                op_triplet_ratio(name, glyphs, labels, ref_i, log)
            elif op == "extremes":
                op_extremes(name, glyphs, labels, ref_i, log)
            elif op == "repredict" and name in pts_by_glyph:
                op_repredict(name, glyphs, labels, ref_i, log, pts_by_glyph[name], locs)
                # a moved handle or node no longer lines up with its neighbour
                op_collinear(name, glyphs, labels, ref_i, log)
            tagged += [(op, name, line) for line in log[name][before:]]
        for mi, g in enumerate(glyphs):
            if [(p.x, p.y, p.type) for c in g.contours for p in c.points] != snap[mi]:
                touched.add((name, mi))

    if not tagged:
        print("No changes.")
    attention = ("check the render", "by hand", "repredict", "left alone", "skipped")
    for op in ORDER:
        lines = [(g, t) for o, g, t in tagged if o == op]
        if not lines:
            continue
        print(f"## {op}")
        for g, t in lines:
            flag = "  <- look" if any(a in t for a in attention) else ""
            print(f"{g}: {t}{flag}")
    print("\n## totals")
    for op in [o for o in ORDER if o in opt.ops]:
        lines = [(g, t) for o, g, t in tagged if o == op]
        if not lines:
            print(f"{op}: nothing to change")
        else:
            changed = {g for g, t in lines if not any(a in t for a in ("left alone", "skipped", "by hand", "repredict it", "add it by hand"))}
            look = sum(1 for g, t in lines if any(a in t for a in attention))
            print(f"{op}: {len(changed)} glyphs changed, {look} lines to look at")
    if opt.write or opt.out_dir:
        if do_round:
            # round exactly what changed: every master merge touched, only the movable ones otherwise
            for name, mi in sorted(touched):
                g = masters[mi].font[name]
                round_keeping_directions(g)
                if SNAP:
                    snap_smooth(g)
            print("rounded changed glyphs to whole units; run audit.py again: rounding short handles can bring kinks back")
        for m in masters:
            m.font.save()
        print(f"saved {len(masters)} masters" + (f" to {opt.out_dir}" if opt.out_dir else " in place"))
    else:
        print("dry run: nothing saved (use --write or --out-dir)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
