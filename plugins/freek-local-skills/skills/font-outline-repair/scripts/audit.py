#!/usr/bin/env python3
"""Audit weight masters (and derived extremes) for outline problems that
interpolation and extrapolation turn into wobbles, kinks, curls and barbs.

usage:
  audit.py SOURCES... [--derived 100=Thin.ufo 900=Black.ufo] [--glyphs a b c]
           [--ref 500] [--json report.json] [--md report.md]

SOURCES is one .designspace file or several weight=path.ufo pairs.
Contour and point numbers follow, per glyph, the master that most other masters
already agree with (ties: --ref, default the middle master), after contour order,
direction and start point are matched.
Reads only; never writes a font.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pathops
from scipy.spatial import cKDTree
from fontTools.pens.pointPen import PointToSegmentPen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402
from compat import align_glyph, best_ref, draw_pts, pts_of, signed_area  # noqa: E402

SEVERITY = {
    # structure (stops interpolation)
    "component-mismatch": "blocks", "component-order": "blocks", "contour-count": "blocks",
    "contour-order": "blocks", "direction": "blocks", "point-count": "blocks", "point-type": "blocks",
    "start-point": "slows",
    # shape, any outline
    "kink": "slows", "smooth-mismatch": "slows", "near-smooth": "minor",
    "handle-backward": "slows", "handle-crossing": "minor", "handle-overlong": "slows", "cusp": "slows",
    "self-intersection": "blocks", "counter-breakout": "blocks", "overlap-new": "slows",
    "missing-extreme": "minor", "short-segment": "minor",
    "lump": "slows", "curvature-step": "slows", "scallop": "minor", "converted-quadratic": "minor",
    "corner-flip": "slows", "corner-change": "slows",
    "semi-hv": "minor", "zero-handle": "minor", "flat-curve": "minor", "uneven-handles": "minor",
    "inflection": "minor", "zone-miss": "minor", "tiny-contour": "slows", "excess-nodes": "minor",
    # across masters
    "handle-flip": "slows", "tension-jump": "slows", "alignment-break": "slows", "ratio-mismatch": "slows",
    "motion-bend": "minor", "stroke-progression": "minor",
    # derived outlines vs reference master
    "direction-flip": "blocks", "segment-reversal": "blocks", "segment-collapse": "blocks",
    "handle-reversal": "blocks", "inflection-new": "slows", "not-derived": "slows",
    "thin-stroke": "slows", "counter-tight": "slows", "crossing-shrink": "slows", "overhang": "slows",
    "stroke-ratio": "slows", "parts-close": "slows", "edge-turned": "slows", "stroke-wedge": "slows",
    "stroke-uneven": "slows", "stroke-weight": "slows", "copy-drift": "slows",
}
SCORE = {"blocks": 10, "slows": 3, "minor": 1}


def I(glyph, code, weight, detail, contour=None, point=None, severity=None, **kw):
    return L.issue(glyph, code, severity or SEVERITY[code], weight, detail, contour, point, **kw)


# ------------------------------------------------------------ path helpers

def to_pathops(contours):
    p = pathops.Path()
    pen = PointToSegmentPen(p.getPen())
    for c in contours:
        draw_pts(c, pen)
    return p


def self_intersects(c):
    if c[0].type == "move":
        return False
    p = to_pathops([c])
    try:
        s = pathops.simplify(p)
    except pathops.PathOpsError:
        return True
    a = abs(signed_area(c))
    n = len(list(s.contours))
    return n != 1 or abs(s.area - a) > 1.0 + 1e-3 * a


def crossing(ca, cb):
    """True if two closed contours' outlines cross (not merely nested or apart)."""
    if ca[0].type == "move" or cb[0].type == "move":
        return False
    pa, pb = to_pathops([ca]), to_pathops([cb])
    try:
        inter = pathops.op(pa, pb, pathops.PathOp.INTERSECTION).area
    except pathops.PathOpsError:
        return True
    small = min(pa.area, pb.area)
    return 1.0 < inter < small - 1.0 - 1e-3 * small


def _pieces(pa, pb):
    """Areas of the parts of pa outside pb, as fractions of pa's area, largest first."""
    try:
        d = pathops.op(pa, pb, pathops.PathOp.DIFFERENCE)
    except pathops.PathOpsError:
        return None
    total = abs(pa.area) or 1.0
    return sorted((abs(c.area) / total for c in d.contours), reverse=True)


def crossing_checks(name, wl, cs, ref_cs):
    """A part that crosses another (the bar of eth, the stroke of dollar, a crossbar
    through a stem) should still stick out on each side as it does in the reference.
    Extrapolation can slide it until one end hides inside the stroke it crosses."""
    out = []
    n = len(cs)
    if n < 2 or n > 6 or len(ref_cs) != n:
        return out
    for a in range(n):
        for b in range(n):
            if a == b or not crossing(ref_cs[a], ref_cs[b]) or not crossing(cs[a], cs[b]):
                continue
            ref = _pieces(to_pathops([ref_cs[a]]), to_pathops([ref_cs[b]]))
            mine = _pieces(to_pathops([cs[a]]), to_pathops([cs[b]]))
            if not ref or mine is None:
                continue
            ref = [f for f in ref if f > 0.03]
            mine = mine + [0.0] * len(ref)
            for k, f in enumerate(ref):
                if f > 0.05 and mine[k] < 0.35 * f:
                    out.append(I(name, "crossing-shrink", wl, f"contour {a} sticks out of contour {b} on one side by "
                                 f"{mine[k] * 100:.0f}% of its area where the reference has {f * 100:.0f}%: the crossing part "
                                 "slid into the stroke it crosses", a))
                    break
    return out


def side_bearings(glyph, font):
    try:
        b = glyph.getBounds(font.layers.defaultLayer)
    except Exception:
        return None
    return None if b is None else (b.xMin, glyph.width - b.xMax)


def overhang_checks(name, wl, glyph, font, master_glyphs, tol=10):
    """Derived weights: ink past the origin or the advance width on a side where every
    master keeps a side bearing (heavy T, V, f overhanging in the drawn Bold too are
    the design, not this): the glyph runs into its neighbours."""
    if not glyph.width or not (glyph.contours or glyph.components):
        return []
    mine = side_bearings(glyph, font)
    ms = [side_bearings(g, f) for g, f in master_glyphs if g.width]
    if mine is None or not ms or any(m is None for m in ms):
        return []
    out = []
    for k, side in enumerate(("left", "right")):
        least = min(m[k] for m in ms)
        if mine[k] < -tol and least >= 0:
            out.append(I(name, "overhang", wl, f"ink passes the {side} side bearing by {-mine[k]:.0f} units; every master "
                         f"keeps one (at least {least:.0f}): it runs into the next glyph"))
    return out


def polys(contours, steps=16):
    out = []
    for c in contours:
        if c and c[0].type != "move":
            from fontTools.pens.recordingPen import RecordingPen
            rec = RecordingPen()
            draw_pts(c, PointToSegmentPen(rec))
            out.extend(L.flatten_recording(rec.value, steps))
    return out


def cubic_segments(c):
    closed = c[0].type != "move"
    for (i0, offs, i1, typ) in L.segments(c, closed):
        if typ == "curve" and len(offs) == 2:
            yield i0, offs[0], offs[1], i1


# ------------------------------------------------------------ curvature

FLAT = 1 / 5000  # curvature below this (radius over 5000 units) counts as straight


def seg_kappas(P, n=24):
    return [L.cubic_kappa(*P, 0.02 + 0.96 * k / (n - 1)) for k in range(n)]


def bumps(ks):
    """Significant interior extrema of curvature inside one segment."""
    top = max(abs(k) for k in ks)
    if top < FLAT:
        return 0
    need = max(0.25 * top, FLAT)
    count, last_ext = 0, ks[0]
    rising = None
    for a, b in zip(ks, ks[1:]):
        if b == a:
            continue
        up = b > a
        if rising is not None and up != rising:
            if abs(a - last_ext) >= need:
                count += 1
                last_ext = a
        rising = up
    return count


def curvature_profile(c):
    """Per cubic segment, keyed by its start node: (end node, bumps, curvature at start, middle, end)."""
    out = {}
    for i0, i1, i2, i3 in cubic_segments(c):
        P = [L.xy(c[k]) for k in (i0, i1, i2, i3)]
        out[i0] = (i3, bumps(seg_kappas(P)), L.cubic_kappa(*P, 0.0), L.cubic_kappa(*P, 0.5), L.cubic_kappa(*P, 1.0))
    return out


def node_joins(prof):
    """Nodes where one cubic ends and the next starts: node -> (segment before, segment after)."""
    by_end = {v[0]: v for v in prof.values()}
    return {n: (by_end[n], prof[n]) for n in prof if n in by_end}


def step_ratio(before, after):
    """Curvature step at a smooth node as |k1 - k2| / (k1 + k2), the measure mekkablue's
    Path Problem Finder uses for "green discontinuity" (5% strict, 15% relaxed)."""
    ka, kb = before[4], after[2]
    if ka * kb <= 0 or (abs(ka) < FLAT and abs(kb) < FLAT):
        return None
    return abs(abs(ka) - abs(kb)) / (abs(ka) + abs(kb))


def curvature_checks(name, wl, cs, ref_cs, is_ref, opt):
    """Lumps and comb steps against the reference master, and scallops in any master."""
    out = []
    scallops, steps = [], []
    for ci, c in enumerate(cs):
        if not c or c[0].type == "move":
            continue
        prof = curvature_profile(c)
        rprof = prof if is_ref else curvature_profile(ref_cs[ci])
        if not is_ref:
            for st, seg in prof.items():
                if st in rprof and seg[1] > rprof[st][1]:
                    out.append(I(name, "lump", wl, f"curvature rises and falls inside this curve ({seg[1]} bump(s) where the reference has {rprof[st][1]})", ci, seg[0],
                                 severity="slows" if seg[1] >= rprof[st][1] + 2 else "minor"))
        rjoins = node_joins(rprof)
        for n, (before, after) in node_joins(prof).items():
            if not (c[n].smooth or (ci, n) in opt.straight_in_ref):
                continue
            r = step_ratio(before, after)
            if r is not None and r > opt.g2_tol:
                rr = step_ratio(*rjoins[n]) if n in rjoins else None
                if is_ref:
                    steps.append(f"{ci}:{n} {r:.0%}")
                elif rr is None or r > rr + 0.15:
                    out.append(I(name, "curvature-step", wl, f"curvature jumps {r:.0%} across this smooth node" +
                                 ("" if rr is None else f" ({rr:.0%} in the reference)"), ci, n,
                                 severity="slows" if r > 0.4 and (rr is None or r > rr + 0.2) else "minor"))
            # scallop: curvature dips or peaks right at the node compared with both curves' middles
            mids = (abs(before[3]), abs(after[3]))
            kn = (abs(before[4]) + abs(after[2])) / 2
            trend = (mids[0] + mids[1]) / 2
            t_in, t_out = L.node_tangents(c, n, True)
            ang = math.degrees(math.atan2(t_out[1], t_out[0])) % 90 if t_out else 45
            at_extreme = min(ang, 90 - ang) < 0.5   # curvature peaks or dips at extremes by design
            if not at_extreme and min(mids) > FLAT and before[3] * after[3] > 0 and abs(kn - trend) > opt.scallop_tol * trend:
                scallops.append(f"{ci}:{n} {100 * (kn - trend) / trend:+.0f}%")
    if is_ref:
        quad = total = 0
        for c in cs:
            if not c or c[0].type == "move":
                continue
            for i0, i1, i2, i3 in cubic_segments(c):
                P = [L.xy(c[k]) for k in (i0, i1, i2, i3)]
                total += 1
                hit = L.line_intersection(P[0], L.sub(P[1], P[0]), P[3], L.sub(P[2], P[3]))
                if hit and hit[0] > 0 and hit[1] > 0 and abs(1 / hit[0] - 2 / 3) < 0.03 and abs(1 / hit[1] - 2 / 3) < 0.03:
                    quad += 1
        if total >= 4 and quad >= total / 3:
            out.append(I(name, "converted-quadratic", wl, f"{quad} of {total} curves have both handles at exactly 2/3: TrueType "
                         "quadratics in cubic form, so the outline was converted from a compiled font and has about twice the points it needs"))
    if steps:
        out.append(I(name, "curvature-step", wl, f"curvature jumps at {len(steps)} smooth node(s) in the reference master: " +
                     ", ".join(steps[:8]) + (" …" if len(steps) > 8 else ""), severity="minor"))
    if scallops:
        sev = "slows" if len(scallops) >= 6 else "minor"
        out.append(I(name, "scallop", wl, f"curvature dips or peaks at {len(scallops)} smooth node(s) against the curves either side, a scalloped comb "
                     "(too many points, or curves converted from TrueType; try fix.py --ops merge): " + ", ".join(scallops[:8]) +
                     (" …" if len(scallops) > 8 else ""), severity=sev))
    return out


def zones_of(font):
    """Alignment zones: blue zone pairs when the font has them, else its metric lines."""
    info = font.info
    zs = []
    for key in ("postscriptBlueValues", "postscriptOtherBlues"):
        v = list(getattr(info, key, None) or [])
        zs += [(min(a, b), max(a, b)) for a, b in zip(v[0::2], v[1::2])]
    if not zs:
        for key in ("xHeight", "capHeight", "ascender", "descender"):
            v = getattr(info, key, None)
            if v is not None:
                zs.append((v, v))
        zs.append((0, 0))
    return zs


def corner_angles(c):
    """Signed turn (degrees) at every corner node: on-curve, not flagged smooth."""
    closed = c[0].type != "move"
    out = {}
    for i, p in enumerate(c):
        if p.type is None or p.smooth:
            continue
        t_in, t_out = L.node_tangents(c, i, closed)
        if t_in and t_out:
            out[i] = L.signed_angle_deg(t_in, t_out)
    return out


def corner_checks(name, wl, cs, ref_cs, derived, opt):
    """Corners that turn the other way than in the reference master, or turn much more or less."""
    out = []
    for ci, c in enumerate(cs):
        if not c:
            continue
        mine, ref = corner_angles(c), corner_angles(ref_cs[ci])
        for i, ra in ref.items():
            if i not in mine or abs(ra) < 10:
                continue
            a = mine[i]
            if a * ra < 0 and abs(a) > 5:
                out.append(I(name, "corner-flip", wl, f"corner turns the other way ({a:+.0f}° where the reference turns {ra:+.0f}°): a barb or notch",
                             ci, i, severity="blocks" if derived else "slows"))
            elif abs(a - ra) > opt.corner_tol:
                out.append(I(name, "corner-change", wl, f"corner {'sharper' if abs(a) > abs(ra) else 'blunter'} than in the reference "
                             f"({a:+.0f}° against {ra:+.0f}°)", ci, i))
    return out


def drawing_checks(name, wl, cs, font, opt):
    """Drawing mistakes in one master, with the thresholds of RedArrow, Glyph Nanny and
    mekkablue's Path Problem Finder (see references/checks-and-sources.md)."""
    out = []
    semi, zero, flat, uneven, zone = [], [], [], [], []
    zs = zones_of(font)
    for ci, c in enumerate(cs):
        if not c:
            continue
        closed = c[0].type != "move"
        ons = [p for p in c if p.type]
        xs, ys = [p.x for p in c], [p.y for p in c]
        if closed and (len(ons) < 3 or (max(xs) - min(xs)) * (max(ys) - min(ys)) < 25):
            out.append(I(name, "tiny-contour", wl, "contour with under 3 nodes or under 25 square units: a stray or leftover", ci))
            continue
        for (i0, offs, i1, typ) in L.segments(c, closed):
            P0, P3 = L.xy(c[i0]), L.xy(c[i1])
            if not offs:
                v = L.sub(P3, P0)
                off = min(abs(v[0]), abs(v[1]))
                if L.norm(v) > 30 and 0.25 < off <= 2:
                    semi.append(f"{ci}:{i1} line {off:.0f}")
                continue
            if len(offs) != 2:
                continue
            P1, P2 = L.xy(c[offs[0]]), L.xy(c[offs[1]])
            for k, h, base in ((offs[0], P1, P0), (offs[1], P2, P3)):
                v = L.sub(h, base)
                if L.norm(v) < 0.5:
                    zero.append(f"{ci}:{k}")
                elif L.norm(v) > 8 and 0.25 < min(abs(v[0]), abs(v[1])) <= 2:
                    semi.append(f"{ci}:{k} handle {min(abs(v[0]), abs(v[1])):.0f}")
            ch = L.sub(P3, P0)
            ln = L.norm(ch)
            if ln > 2:
                u = L.unit(ch)
                d1, d2 = abs(L.cross(u, L.sub(P1, P0))), abs(L.cross(u, L.sub(P2, P0)))
                inside = 0 <= L.dot(L.sub(P1, P0), u) <= ln and 0 <= L.dot(L.sub(P2, P0), u) <= ln
                if d1 < 0.5 and d2 < 0.5 and inside:
                    flat.append(f"{ci}:{i1}")
                    continue
                for t in L.cubic_inflection_ts(P0, P1, P2, P3):
                    if max(d1, d2) > 2:
                        near_end = t < 0.1 or t > 0.9
                        out.append(I(name, "inflection", wl, f"curve bends both ways inside one segment (t={t:.2f}" +
                                     (", near its end: likely a mistake)" if near_end else "; a node there makes it easier to control)"),
                                     ci, i1, severity="minor"))
                tn = tension(P0, P1, P2, P3)
                if tn and min(tn) > 0 and max(tn) / min(tn) > 1.5:
                    uneven.append(f"{ci}:{i1} {tn[0]:.2f}/{tn[1]:.2f}")
        # top and bottom extremes just off an alignment zone
        if closed:
            for p in ons:
                for lo, hi in zs:
                    d = lo - p.y if p.y < lo else (p.y - hi if p.y > hi else 0)
                    if 0 < d <= 5 and (p.y == max(ys) or p.y == min(ys)):
                        zone.append(f"{ci}:{c.index(p)} y={p.y:g}")
                        break
    for code, lst, text in (("semi-hv", semi, "nearly but not exactly horizontal/vertical (1-2 units off)"),
                            ("zero-handle", zero, "handle sitting on its node"),
                            ("flat-curve", flat, "curve with both handles on its chord: should be a straight line"),
                            ("uneven-handles", uneven, "the two handles of a curve are very unbalanced (Tunni ratio over 1.5)"),
                            ("zone-miss", zone, "top or bottom extreme 1-5 units off an alignment zone or metric line")):
        if lst:
            out.append(I(name, code, wl, f"{len(lst)} x {text}: " + ", ".join(lst[:8]) + (" …" if len(lst) > 8 else "")))
    return out


# ------------------------------------------------------------ per outline

def shape_checks(name, wl, cs, ref_cs, smooth_any, opt, derived):
    """Checks on one outline. Derived outlines report only what the reference lacks."""
    out = []
    near = []
    for ci, c in enumerate(cs):
        if not c:
            continue
        rc = ref_cs[ci]
        closed = c[0].type != "move"
        # kinks at smooth nodes
        for i, p in enumerate(c):
            if p.type is None:
                continue
            t_in, t_out = L.node_tangents(c, i, closed)
            if t_in is None or t_out is None:
                continue
            dev = L.angle_deg(t_in, t_out)
            # integer coordinates alone bend a short handle by up to ~atan(0.71/len)
            rounding = 2 * math.degrees(math.atan(0.71 / max(min(L.norm(t_in), L.norm(t_out)), 0.71)))
            if (ci, i) in smooth_any or p.smooth:
                if dev > max(opt.kink_tol, rounding):
                    out.append(I(name, "kink", wl, f"smooth node bends {dev:.2f}°", ci, i, deg=round(dev, 2),
                                 severity="slows" if dev > 1.0 else "minor"))
            elif (ci, i) in opt.straight_in_ref and dev > opt.ref_bend.get((ci, i), 0) + 2 * opt.kink_tol + rounding + 2:
                out.append(I(name, "kink", wl, f"corner bends {dev:.1f}° where the reference master is straight ({opt.ref_bend[(ci, i)]:.1f}°)",
                             ci, i, deg=round(dev, 2), severity="slows"))
            elif not derived and wl == opt.ref_label and 0.05 < dev < 3 and any(c[k].type is None for k in L.neighbors(c, i, closed) if k is not None):
                near.append(f"{ci}:{i} {dev:.1f}°")
        # cubic segment checks
        for i0, i1, i2, i3 in cubic_segments(c):
            p0, p1, p2, p3 = (L.xy(c[k]) for k in (i0, i1, i2, i3))
            chord = L.sub(p3, p0)
            ln = L.norm(chord)
            h1, h2 = L.sub(p1, p0), L.sub(p2, p3)
            r0, r1, r2, r3 = (L.xy(rc[k]) for k in (i0, i1, i2, i3))
            rchord = L.sub(r3, r0)
            rh1, rh2 = L.sub(r1, r0), L.sub(r2, r3)

            def backward(h, ch, length):
                return L.norm(h) > 1 and length > 1 and L.dot(h, ch) < -0.05 * L.norm(h) * length

            bw = backward(h1, chord, ln) or backward(h2, L.mul(chord, -1), ln)
            rbw = backward(rh1, rchord, L.norm(rchord)) or backward(rh2, L.mul(rchord, -1), L.norm(rchord))
            if bw and not (derived and rbw):
                out.append(I(name, "handle-backward", wl, "handle points away from the segment's other end (loop risk)", ci, i1 if backward(h1, chord, ln) else i2))
            # handles crossing each other
            hit = L.line_intersection(p0, h1, p3, h2)
            cr = hit is not None and 0 < hit[0] < 1 and 0 < hit[1] < 1
            rhit = L.line_intersection(r0, rh1, r3, rh2)
            rcr = rhit is not None and 0 < rhit[0] < 1 and 0 < rhit[1] < 1
            if cr and not (derived and rcr):
                out.append(I(name, "handle-crossing", wl, "the two handles of this curve cross", ci, i1,
                             severity="slows" if derived else None))
            # handle longer than the distance to where the handles meet ("past 100%"):
            # the curve inflects there and extrapolation turns it into a curl
            if hit is not None and 0 < hit[0] < 1 and 0 < hit[1] < 1:
                pass  # crossing handles, reported above
            elif (hit is not None and hit[0] > 0 and hit[1] > 0 and not L.cubic_inflection_ts(r0, r1, r2, r3)
                  and max(abs(L.cross(L.unit(chord), h1)), abs(L.cross(L.unit(chord), L.sub(p2, p0)))) > max(2.0, 0.03 * ln)):
                # C-shaped curve with a real bulge (S-curves and near-straight curves have no Tunni point)
                over = 1 / hit[0] > 1.0 or 1 / hit[1] > 1.0
                r_over = rhit is not None and rhit[0] > 0 and rhit[1] > 0 and (1 / rhit[0] > 1.0 or 1 / rhit[1] > 1.0)
                if over and not (derived and r_over):
                    tmax = max(1 / hit[0], 1 / hit[1])
                    out.append(I(name, "handle-overlong", wl, f"handle reaches past where the handles meet (tension {tmax:.2f}; above 1.0 the curve bends back)",
                                 ci, i1 if 1 / hit[0] > 1.0 else i2, severity="slows" if tmax > 1.1 or derived else "minor"))
            # cusp: speed drops to ~0 inside the segment
            if ln > 5:
                vmin = min(L.norm(L.cubic_d1(p0, p1, p2, p3, k / 40)) for k in range(2, 39))
                rln = L.norm(rchord)
                rvmin = min(L.norm(L.cubic_d1(r0, r1, r2, r3, k / 40)) for k in range(2, 39)) if rln > 5 else 1e9
                if vmin < 0.03 * ln and not (derived and rvmin < 0.03 * rln):
                    out.append(I(name, "cusp", wl, "curve has a cusp (sharp point) inside the segment", ci, i3))
            if derived:
                rl = L.norm(rchord)
                if rl > 2 and L.dot(chord, rchord) < 0:
                    out.append(I(name, "segment-reversal", wl, "segment runs backwards compared with the reference master (barb/fold)", ci, i3))
                elif rl > 3 and ln < 0.5:
                    out.append(I(name, "segment-collapse", wl, "segment shrank to nothing", ci, i3))
                for hk, hv, rhv in ((i1, h1, rh1), (i2, h2, rh2)):
                    if L.norm(hv) > 2 and L.norm(rhv) > 2 and L.dot(hv, rhv) < 0:
                        out.append(I(name, "handle-reversal", wl, "handle flipped direction compared with the reference master (curl)", ci, hk))
                ni = len(L.cubic_inflection_ts(p0, p1, p2, p3))
                nr = len(L.cubic_inflection_ts(r0, r1, r2, r3))
                u = L.unit(chord)
                bulge = max(abs(L.cross(u, h1)), abs(L.cross(u, L.sub(p2, p0))))
                if ni > nr and bulge > max(2.0, 0.02 * ln):
                    out.append(I(name, "inflection-new", wl, "curve gained an S-bend the reference master doesn't have (wobble)", ci, i3))
            else:
                for axis in (0, 1):
                    for t in L.cubic_extrema_ts(p0, p1, p2, p3, axis):
                        if 0.03 < t < 0.97:
                            v = L.cubic_at(p0, p1, p2, p3, t)[axis]
                            if v > max(p0[axis], p3[axis]) + 1 or v < min(p0[axis], p3[axis]) - 1:
                                out.append(I(name, "missing-extreme", wl, f"curve has an {'xy'[axis]} extreme at t={t:.2f} without a node", ci, i3, axis="xy"[axis], t=round(t, 3)))
        # line segments: collapse/reversal in derived
        if derived:
            for (i0, offs, i1, typ) in L.segments(c, closed):
                if offs:
                    continue
                v, rv = L.sub(L.xy(c[i1]), L.xy(c[i0])), L.sub(L.xy(rc[i1]), L.xy(rc[i0]))
                if L.norm(rv) > 2 and L.dot(v, rv) < 0:
                    out.append(I(name, "segment-reversal", wl, "straight segment runs backwards compared with the reference master (barb)", ci, i1))
        else:
            for (i0, offs, i1, typ) in L.segments(c, closed):
                d = L.dist(L.xy(c[i0]), L.xy(c[i1]))
                if d < 2 and all(L.dist(L.xy(c[k]), L.xy(c[i0])) < 3 for k in offs):
                    out.append(I(name, "short-segment", wl, f"segment only {d:.1f} units long", ci, i1))
        # self-intersection
        if closed and len(c) > 2 and self_intersects(c):
            ref_si = self_intersects(rc)
            if derived and not ref_si:
                out.append(I(name, "self-intersection", wl, "contour crosses itself where the reference master doesn't (curl or loop)", ci))
            elif not derived and not ref_si:
                out.append(I(name, "self-intersection", wl, "contour crosses itself in this master only (curl or loop, or an overlap drawn on purpose)", ci, severity="slows"))
            elif not derived and wl == opt.ref_label:
                out.append(I(name, "self-intersection", wl, "contour overlaps itself in the reference master; check whether that is a deliberate overlap", ci, severity="minor"))
        # direction flip
        if derived:
            a, ra = signed_area(c), signed_area(rc)
            if a * ra < 0 and abs(ra) > 4:
                out.append(I(name, "direction-flip", wl, "contour turned inside out (collapsed stroke or counter)", ci))
    if near:
        out.append(I(name, "near-smooth", wl, f"{len(near)} corner node(s) within 3° of straight, not flagged smooth: " + ", ".join(near[:8]) + (" …" if len(near) > 8 else "")))
    # contour pairs
    if len(cs) > 1 and len(cs) <= 12:
        for a in range(len(cs)):
            for b in range(a + 1, len(cs)):
                if crossing(cs[a], cs[b]) and not crossing(ref_cs[a], ref_cs[b]):
                    counter = signed_area(cs[a]) * signed_area(cs[b]) < 0
                    if counter:
                        out.append(I(name, "counter-breakout", wl, f"contours {a} and {b} now cross (a counter breaks through its outline)", a))
                    else:
                        # parts drawn apart (the letters of a trademark sign, the rings of a
                        # per-mille sign) run into each other: removing overlaps fuses them
                        out.append(I(name, "overlap-new", wl, f"contours {a} and {b} now cross: parts that are apart in the "
                                     "reference run into each other", a, severity="blocks" if derived else "slows"))
    return out


# ------------------------------------------------------------ across masters

SCAN_FRACTIONS = (0.2, 0.35, 0.5, 0.65, 0.8)
SCAN_LINES = [("h", f) for f in SCAN_FRACTIONS] + [("v", f) for f in SCAN_FRACTIONS]


DENSE_LINES = [(k, f / 10) for k in ("h", "v") for f in range(1, 10)]


def scan(cs, lines=None):
    """Ink runs on scanlines placed at fractions of this outline's own bounding box,
    so the same stroke is hit in every weight. Runs are (start, end, centre_fraction)."""
    lines = lines or SCAN_LINES
    pl = polys(cs)
    allp = [p for poly in pl for p in poly]
    if not allp:
        return [[] for _ in lines]
    x0, y0 = min(p[0] for p in allp), min(p[1] for p in allp)
    x1, y1 = max(p[0] for p in allp), max(p[1] for p in allp)
    out = []
    for k, f in lines:
        if k == "h":
            v, lo, span = y0 + f * (y1 - y0), x0, max(x1 - x0, 1)
        else:
            v, lo, span = x0 + f * (x1 - x0), y0, max(y1 - y0, 1)
        out.append([(a, b, ((a + b) / 2 - lo) / span, v) for a, b in L.ink_runs(pl, v, horizontal=(k == "h"))])
    return out


def runs_correspond(per_line):
    """Same run count in every outline and each run's centre stays put (within 12% of the box)."""
    counts = {len(r) for r in per_line}
    if len(counts) != 1 or not per_line[0]:
        return False
    return all(abs(r[k][2] - per_line[0][k][2]) < 0.12 for r in per_line for k in range(len(r)))


def tension(p0, p1, p2, p3):
    """Handle tension per side: handle length over distance to where the handles meet,
    or handle length over chord when they don't meet sensibly. None for tiny handles."""
    h1, h2 = L.sub(p1, p0), L.sub(p2, p3)
    ln = L.dist(p0, p3)
    if ln < 10 or L.norm(h1) < 8 or L.norm(h2) < 8:
        return None
    ch = L.unit(L.sub(p3, p0))
    bulge = max(abs(L.cross(ch, L.sub(p1, p0))), abs(L.cross(ch, L.sub(p2, p0))))
    if bulge < max(2.0, 0.03 * ln):
        return None  # nearly straight: tension means nothing here
    hit = L.line_intersection(p0, h1, p3, h2)
    if hit and 0.5 < hit[0] < 10 and 0.5 < hit[1] < 10:
        return 1 / hit[0], 1 / hit[1]
    return L.norm(h1) / ln, L.norm(h2) / ln


def loo_predict(locs, vals):
    """For each master, the value a straight line through the other masters predicts there
    (with two masters, the other master's value)."""
    n = len(vals)
    out = []
    for m in range(n):
        xs = [locs[k] for k in range(n) if k != m]
        ys = [vals[k] for k in range(n) if k != m]
        if len(xs) == 1:
            out.append(ys[0])
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        ss = sum((x - mx) ** 2 for x in xs) or 1.0
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / ss
        out.append(my + slope * (locs[m] - mx))
    return out


def master_checks(name, labels, locs, aligned, opt, ref_i):
    out = []
    ref = aligned[ref_i]
    n = len(aligned)
    for ci, rc in enumerate(ref):
        closed = rc[0].type != "move"
        # smooth flags
        for i, p in enumerate(rc):
            if p.type is None:
                continue
            flags = [aligned[m][ci][i].smooth for m in range(n)]
            if any(flags) and not all(flags):
                off = [labels[m] for m in range(n) if not flags[m]]
                out.append(I(name, "smooth-mismatch", ",".join(off), f"node is smooth in some masters but not in {', '.join(off)}", ci, i))
        # handle-node-handle ratio differs between masters while the tangent turns:
        # interpolation and extrapolation then kink at this node
        for i, p in enumerate(rc):
            if p.type is None or not all(aligned[m][ci][i].smooth for m in range(n)):
                continue
            a, b = L.neighbors(rc, i, closed)
            if a is None or b is None or rc[a].type is not None or rc[b].type is not None:
                continue
            ratios, angles = [], []
            for m in range(n):
                c = aligned[m][ci]
                A, N, B = L.xy(c[a]), L.xy(c[i]), L.xy(c[b])
                ab = L.dist(A, B)
                if ab < 1e-6:
                    break
                ratios.append(L.dist(A, N) / ab)
                angles.append(math.degrees(math.atan2(B[1] - A[1], B[0] - A[0])))
            else:
                spread = max(abs(((x - angles[0]) + 180) % 360 - 180) for x in angles)
                if max(ratios) - min(ratios) > 0.05 and spread > 2:
                    out.append(I(name, "ratio-mismatch", "all", "smooth node sits at a different point between its handles in each master (" +
                                 ", ".join(f"{labels[m]} {ratios[m]:.2f}" for m in range(n)) + f") while the tangent turns {spread:.0f}°", ci, i))
        for i0, i1, i2, i3 in cubic_segments(rc):
            # handle side flips: a handle that crosses to the other side of its curve in
            # one master, against the trend of the others (a gradual rotation is design)
            for hk, base in ((i1, i0), (i2, i3)):
                other = i3 if base == i0 else i0
                angs = []
                for m in range(n):
                    c = aligned[m][ci]
                    h = L.sub(L.xy(c[hk]), L.xy(c[base]))
                    ch = L.sub(L.xy(c[other]), L.xy(c[base]))
                    angs.append(L.signed_angle_deg(ch, h) if L.norm(h) > 1 else 0.0)
                pred = loo_predict(locs, angs)
                worst = max(range(n), key=lambda m: abs(angs[m] - pred[m]))
                off = abs(angs[worst] - pred[worst])
                others = [angs[k] for k in range(n) if k != worst]
                opposite = all(a * angs[worst] < 0 and abs(a) > 3 for a in others)
                if off > opt.flip_tol and opposite and abs(angs[worst]) > 3:
                    out.append(I(name, "handle-flip", labels[worst], f"handle swings to the other side of its curve in {labels[worst]} "
                                 f"({angs[worst]:+.0f}° where the other masters predict {pred[worst]:+.0f}°): " +
                                 ", ".join(f"{labels[m]} {angs[m]:+.0f}°" for m in range(n)), ci, hk))
            # tension: a steady change across weights is design; a jump in one master is not
            ts = [tension(*(L.xy(aligned[m][ci][k]) for k in (i0, i1, i2, i3))) for m in range(n)]
            if all(t is not None for t in ts):
                for side, hk in ((0, i1), (1, i2)):
                    vals = [t[side] for t in ts]
                    if n >= 3:
                        mean = sum(locs) / n
                        ss = sum((a - mean) ** 2 for a in locs)
                        vm = sum(vals) / n
                        slope = sum((locs[m] - mean) * (vals[m] - vm) for m in range(n)) / ss
                        dev = [vals[m] - (vm + slope * (locs[m] - mean)) for m in range(n)]
                        bad = max(abs(d) for d in dev) > opt.tension_tol / 2
                    else:
                        bad = max(vals) - min(vals) > opt.tension_tol
                    if bad:
                        med = sorted(vals)[n // 2]
                        worst = max(range(n), key=lambda m: abs(vals[m] - med))
                        out.append(I(name, "tension-jump", labels[worst], "curve tension jumps between masters: " +
                                     ", ".join(f"{labels[m]} {vals[m]:.2f}" for m in range(n)), ci, hk))
        # alignment breaks: vertical/horizontal lines and handles in most masters but not one
        seen = set()
        for i, p in enumerate(rc):
            for k in L.neighbors(rc, i, closed):
                if k is None or (p.type is None and rc[k].type is None):
                    continue
                if (min(i, k), max(i, k)) in seen:
                    continue
                seen.add((min(i, k), max(i, k)))
                for axis, label in ((0, "vertical"), (1, "horizontal")):
                    offs = [abs(aligned[m][ci][i][axis] - aligned[m][ci][k][axis]) for m in range(n)]
                    lens = [L.dist(L.xy(aligned[m][ci][i]), L.xy(aligned[m][ci][k])) for m in range(n)]
                    good = [m for m in range(n) if offs[m] < 0.5 and lens[m] > 3]
                    bad = [m for m in range(n) if 0.5 <= offs[m] <= 25 and lens[m] > 3]
                    if len(good) >= max(2, n - 1) and bad:
                        for m in bad:
                            out.append(I(name, "alignment-break", labels[m], f"{label} in other masters, {offs[m]:.1f} units off here", ci, i, other=k,
                                         severity="slows" if offs[m] > 1.0 else "minor"))
    # motion bends: a point's path across masters bends more than its neighbours'
    if n >= 3:
        mean = sum(locs) / n
        ss = sum((a - mean) ** 2 for a in locs)
        for ci, rc in enumerate(ref):
            closed = rc[0].type != "move"
            res = []
            for i in range(len(rc)):
                r = []
                for axis in (0, 1):
                    vals = [aligned[m][ci][i][axis] for m in range(n)]
                    vm = sum(vals) / n
                    slope = sum((locs[m] - mean) * (vals[m] - vm) for m in range(n)) / ss
                    r.append([vals[m] - (vm + slope * (locs[m] - mean)) for m in range(n)])
                res.append(r)
            for i, p in enumerate(rc):
                nb = [k for k in L.neighbors(rc, i, closed) if k is not None]
                if not nb:
                    continue
                worst = 0.0
                for m in range(n):
                    dx = res[i][0][m] - sum(res[k][0][m] for k in nb) / len(nb)
                    dy = res[i][1][m] - sum(res[k][1][m] for k in nb) / len(nb)
                    d = math.hypot(dx, dy)
                    worst = max(worst, d)
                if worst > opt.motion_tol:
                    out.append(I(name, "motion-bend", "all", f"point's path across masters bends {worst:.1f} units more than its neighbours'",
                                 ci, i, units=round(worst, 1), severity="slows" if worst > 3 * opt.motion_tol else "minor"))
    # stroke progression along scanlines
    per = [scan(aligned[m]) for m in range(n)]
    for li, (kind, f) in enumerate(SCAN_LINES):
        if not runs_correspond([per[m][li] for m in range(n)]):
            continue
        for k in range(len(per[0][li])):
            widths = [per[m][li][k][1] - per[m][li][k][0] for m in range(n)]
            for m in range(1, n):
                if widths[m] < widths[m - 1] - max(2, 0.05 * widths[m - 1]):
                    out.append(I(name, "stroke-progression", labels[m], f"stroke {k} on the {'horizontal' if kind == 'h' else 'vertical'} scan at {f:.0%} of the box gets thinner as weight goes up: " +
                                 ", ".join(f"{labels[j]} {widths[j]:.0f}" for j in range(n))))
                    break
    return out, SCAN_LINES, per


def grazes_tip(cs, kind, v, a, b, width):
    """A short run is a scan grazing a terminal tip or a corner, not a thin stroke,
    when the stroke is not there a little to either side of the scan."""
    pl = polys(cs)
    mid = (a + b) / 2
    for dv in (-2 * width, 2 * width):
        runs = L.ink_runs(pl, v + dv, horizontal=(kind == "h"))
        if not any(r0 - width <= mid <= r1 + width for r0, r1 in runs):
            return True
    return False


def grazes_gap(cs, kind, v, a, b, width):
    """A short gap is a scan grazing the tip of a V or of a counter, not a tight counter,
    when the gap closes a little to one side of the scan and opens wider to the other
    (a slit that stays narrow on both sides is a real tight counter)."""
    pl = polys(cs)
    mid = (a + b) / 2
    closed, wider = False, False
    for dv in (-2 * width, 2 * width):
        runs = L.ink_runs(pl, v + dv, horizontal=(kind == "h"))
        if any(r0 <= mid <= r1 for r0, r1 in runs):
            closed = True
        else:
            gaps = [(r1[0] - r0[1]) for r0, r1 in zip(runs, runs[1:]) if r0[1] <= mid <= r1[0]]
            if gaps and gaps[0] > (b - a) + width / 2:
                wider = True
    return closed and wider


def scan_checks(name, wl, cs, opt):
    out = []
    mine = scan(cs)
    for li, (kind, f) in enumerate(SCAN_LINES):
        runs = mine[li]
        where = f"{'horizontal' if kind == 'h' else 'vertical'} scan at {f:.0%} of the box"
        for a, b, _, v in runs:
            if b - a < opt.min_stroke and not grazes_tip(cs, kind, v, a, b, opt.min_stroke):
                out.append(I(name, "thin-stroke", wl, f"{where} ({v:.0f}): stroke only {b - a:.1f} units"))
        for r0, r1 in zip(runs, runs[1:]):
            if r1[0] - r0[1] < opt.min_counter and not grazes_gap(cs, kind, r0[3], r0[1], r1[0], opt.min_counter):
                out.append(I(name, "counter-tight", wl, f"{where} ({r0[3]:.0f}): gap only {r1[0] - r0[1]:.1f} units"))
    return out


# ------------------------------------------------------------ stroke evenness

def _segments(pts):
    """[(i0, [handle indices], i1)] of a closed contour of points with .type."""
    n = len(pts)
    ons = [i for i, p in enumerate(pts) if p.type]
    out = []
    for k, i0 in enumerate(ons):
        i1 = ons[(k + 1) % len(ons)]
        hs, j = [], (i0 + 1) % n
        while j != i1:
            hs.append(j)
            j = (j + 1) % n
        out.append((i0, hs, i1))
    return out


def _seg_at(pts, s, u):
    P = [(pts[s[0]].x, pts[s[0]].y)] + [(pts[h].x, pts[h].y) for h in s[1]] + [(pts[s[2]].x, pts[s[2]].y)]
    while len(P) > 1:
        P = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(P, P[1:])]
    return P[0]


def is_dot(pts, stem):
    """A dot (of i, j, !, :, a dieresis): about as wide as high and under about two stems
    across. The contrast step leaves dots as extrapolated; so do the evenness checks."""
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    return h > 0 and 0.6 < w / h < 1.6 and max(w, h) < 2.2 * stem


def stroke_samples(glyph, maxt, flat=24, skip=()):
    """Thickness across the stroke at every node and every segment's middle of a
    ufoLib2 glyph: {(contour, "n<node>" or "m<node>"): units}. A ray goes inward along
    the outline's normal to where it leaves the ink; it counts only when it leaves
    through an edge within 35 degrees of the outline where it started (else it ran
    along a stroke or into a join) and is under maxt. Contours in skip get no samples
    (their edges still stop rays)."""
    import numpy as np
    cs = [list(c.points) for c in glyph.contours]
    edges, starts = [], []
    for pts in cs:
        if not any(p.type for p in pts):
            continue
        for s in _segments(pts):
            steps = flat if s[1] else 1
            prev = _seg_at(pts, s, 0.0)
            for j in range(1, steps + 1):
                q = _seg_at(pts, s, j / steps)
                edges.append((prev[0], prev[1], q[0], q[1]))
                prev = q
        starts.append(len(edges))
    if not edges:
        return {}
    E = np.array(edges)
    keys, P, T = [], [], []
    for ci, pts in enumerate(cs):
        if not any(p.type for p in pts) or ci in skip:
            continue
        for s in _segments(pts):
            for u, tag in ((0.0, "n"), (0.5, "m")):
                a = _seg_at(pts, s, max(u - 0.01, 0.0))
                b = _seg_at(pts, s, min(u + 0.01, 1.0) if u else 0.02)
                d = (b[0] - a[0], b[1] - a[1])
                ln = math.hypot(*d)
                if ln < 1e-9:
                    continue
                keys.append((ci, f"{tag}{s[0]}"))
                P.append(_seg_at(pts, s, u))
                T.append((d[0] / ln, d[1] / ln))
    if not keys:
        return {}
    P, T = np.array(P), np.array(T)
    N = np.stack([-T[:, 1], T[:, 0]], axis=1)
    e = E[:, 2:] - E[:, :2]

    def winding(Q):
        x0, y0, x1, y1 = E[:, 0][None], E[:, 1][None], E[:, 2][None], E[:, 3][None]
        qx, qy = Q[:, 0][:, None], Q[:, 1][:, None]
        up, down = (y0 <= qy) & (qy < y1), (y1 <= qy) & (qy < y0)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = x0 + (qy - y0) * (x1 - x0) / (y1 - y0)
        return (np.where(up & (xi > qx), 1, 0) - np.where(down & (xi > qx), 1, 0)).sum(axis=1)
    flip = winding(P + N) == 0
    N[flip] *= -1
    w = E[None, :, :2] - P[:, None, :]
    den = N[:, None, 0] * e[None, :, 1] - N[:, None, 1] * e[None, :, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (w[..., 0] * e[None, :, 1] - w[..., 1] * e[None, :, 0]) / den
        uu = (w[..., 0] * N[:, None, 1] - w[..., 1] * N[:, None, 0]) / den
    ok = (np.abs(den) > 1e-12) & (t > 0.75) & (uu >= -1e-9) & (uu <= 1 + 1e-9)
    t = np.where(ok, t, np.inf)
    idx = t.argmin(axis=1)
    tmin = t[np.arange(len(keys)), idx]
    out = {}
    for k, key in enumerate(keys):
        if not np.isfinite(tmin[k]) or tmin[k] > maxt:
            continue
        ev = e[idx[k]]
        el = math.hypot(*ev)
        if el < 1e-9 or abs(ev[0] / el * T[k][1] - ev[1] / el * T[k][0]) > math.sin(math.radians(35)):
            continue
        out[key] = float(tmin[k])
    return out


def evenness_checks(name, wl, dglyph, mglyph, k, near_label, near_stem, cache):
    """A derived weight's stroke thickness all along each stroke against the nearest
    master's at the same place times the stem ratio k (dots left out). stroke-uneven:
    spots off the glyph's own median ratio by over 20% (and 3 units), at least 3 of them
    and a tenth of the glyph's spots, where weight shifted along a stroke (an S's spine
    heavy and its curves thin, an arm thinning toward its end); a single spot is usually
    a ray into a join or across a counter. stroke-weight, lighter weights only: the
    median itself over 20% off (accents and cedillas, whose strokes grow slower than the
    stem, stay evenly too heavy at Thin; at Black the contrast step leaves dots and
    counters as extrapolated on purpose)."""
    import statistics
    if [p.type for c in dglyph.contours for p in c.points] != [p.type for c in mglyph.contours for p in c.points]:
        return []
    dots = {ci for ci, c in enumerate(mglyph.contours) if c.points and is_dot(c.points, near_stem)}
    if (name, near_label) not in cache:
        cache[(name, near_label)] = stroke_samples(mglyph, 2 * near_stem, skip=dots)
    sm = cache[(name, near_label)]
    sd = stroke_samples(dglyph, 2 * near_stem * max(k, 1.0), skip=dots)
    pairs = [(key, sm[key], sd[key]) for key in sm if key in sd]
    if len(pairs) < 4:
        return []
    cap = 1.6 * statistics.median(tm for _, tm, _ in pairs)
    pairs = [(key, tm, td) for key, tm, td in pairs if tm < cap]
    if len(pairs) < 4:
        return []
    rs = [(key, td / (tm * k), tm, td) for key, tm, td in pairs]
    med = statistics.median(r for _, r, _, _ in rs)
    out = []
    if k < 1 and abs(med - 1) > 0.2 and abs(statistics.median(td - tm * k for _, _, tm, td in rs)) > 3:
        out.append(I(name, "stroke-weight", wl, f"strokes x{med:.2f} of {near_label} x {k:.3f} (median of {len(rs)} spots): "
                     f"evenly too {'heavy' if med > 1 else 'light'}"))
    off = [(key, r, tm, td) for key, r, tm, td in rs if abs(r / med - 1) > 0.2 and abs(td - tm * k * med) > 3]
    if len(off) >= 3 and len(off) >= 0.1 * len(rs):
        off.sort(key=lambda x: -abs(x[1] / med - 1))
        (ci, tag), r, _, _ = off[0]
        spots = ", ".join(f"c{t[0][0]} {t[0][1]} x{t[1] / med:.2f} ({t[3]:.0f}, want {t[2] * k * med:.0f})" for t in off[:4])
        out.append(I(name, "stroke-uneven", wl, f"{len(off)} of {len(rs)} spots off the glyph's own median by over 20% "
                     f"(against {near_label} x {k:.3f}): {spots}" + (" …" if len(off) > 4 else ""),
                     contour=ci, point=int(tag[1:]), severity="slows" if len(off) >= 0.15 * len(rs) else "minor"))
    return out


# ------------------------------------------------------------ copies

def shifted_map(a, b):
    """If glyph b is glyph a moved sideways (same points, perhaps in another order):
    (index map b -> a over all points, dx); else None."""
    pa = [p for c in a.contours for p in c.points]
    pb = [p for c in b.contours for p in c.points]
    if not pa or len(pa) != len(pb) or len(a.contours) != len(b.contours):
        return None
    dx = min(p.x for p in pb) - min(p.x for p in pa)
    where = {(round(p.x, 3), round(p.y, 3), bool(p.type)): i for i, p in enumerate(pa)}
    m = [where.get((round(p.x - dx, 3), round(p.y, 3), bool(p.type))) for p in pb]
    return (m, dx) if None not in m and len(set(m)) == len(m) else None


def copy_drift_checks(names, masters, derived, tol=3.0):
    """Glyphs that are another glyph moved sideways in every master (tabular figures,
    .case forms) and are not, beyond tol units (rounding makes 1-2), in a derived weight:
    the two were extrapolated differently and drifted apart (on one family two.tf against two at
    Thin, 27 units)."""
    from itertools import combinations
    out = []
    if not masters or not derived:
        return out
    groups = defaultdict(list)
    for n in names:
        g = masters[0].font[n]
        if g.contours and not g.components:
            groups[(len(g.contours), sum(len(c.points) for c in g.contours))].append(n)
    for group in groups.values():
        for a, b in combinations(group, 2):
            maps = [shifted_map(m.font[a], m.font[b]) for m in masters]
            if any(x is None for x in maps) or len({tuple(x[0]) for x in maps}) != 1:
                continue
            idx = maps[0][0]
            copy, base = (b, a) if ("." in b) > ("." in a) or (("." in b) == ("." in a) and len(b) >= len(a)) else (a, b)
            if copy == a:
                idx = [maps[0][0].index(i) for i in range(len(idx))]
            for d in derived:
                if copy not in d.font or base not in d.font:
                    continue
                pc = [p for c in d.font[copy].contours for p in c.points]
                pbase = [p for c in d.font[base].contours for p in c.points]
                if len(pc) != len(idx) or len(pbase) != len(idx):
                    continue
                dxs = sorted(pc[i].x - pbase[idx[i]].x for i in range(len(idx)))
                dx = dxs[len(dxs) // 2]
                dev = max(math.hypot(pc[i].x - dx - pbase[idx[i]].x, pc[i].y - pbase[idx[i]].y) for i in range(len(idx)))
                if dev > tol:
                    out.append(I(copy, "copy-drift", d.label, f"{base} moved sideways in every master, but at {d.label} its "
                                 f"outline is up to {dev:.0f} units off that (reshape.py copy-sync)"))
    return out


def proportion_checks(name, wl, cs, near_cs, stem, near_stem, near_label):
    """A derived weight's strokes and gaps against the nearest master's, on a dense grid
    of scanlines. Lighter weight: a stroke under 70% of the nearest master's scaled by
    the stem ratio (stroke-ratio: a crossbar or terminal that extrapolated thinner than
    the weight; strokes that grow faster than the stem across the masters do this).
    Heavier weight: a stroke thinner than in the nearest master (stroke-progression).
    (Gaps are not compared: at Black nearly every counter closes faster than the
    weight grows, in earlier Blacks too; parts_close_checks covers separate parts.)"""
    out = []
    if not stem or not near_stem or not cs or not near_cs:
        return out
    mine, near = scan(cs, DENSE_LINES), scan(near_cs, DENSE_LINES)
    k = stem / near_stem
    seen = set()
    for li, (kind, f) in enumerate(DENSE_LINES):
        a, b = mine[li], near[li]
        if not runs_correspond([b, a]):
            continue
        where = f"{'horizontal' if kind == 'h' else 'vertical'} scan at {f:.0%} of the box"
        for j, (ra, rb) in enumerate(zip(a, b)):
            wa, wb = ra[1] - ra[0], rb[1] - rb[0]
            if k < 1:
                want = wb * k
                if wa < 0.7 * want and want - wa > 3 and not grazes_tip(cs, kind, ra[3], ra[0], ra[1], max(wa, 2)):
                    key = ("stroke-ratio", kind, round(ra[2], 1))
                    if key not in seen:
                        seen.add(key)
                        out.append(I(name, "stroke-ratio", wl, f"{where} ({ra[3]:.0f}): stroke {wa:.0f} units where the stem "
                                     f"ratio predicts {want:.0f} ({near_label} {wb:.0f}): thinner than the weight"))
            elif wa < wb - max(2.0, 0.05 * wb):
                key = ("stroke-progression", kind, round(ra[2], 1))
                if key not in seen:
                    seen.add(key)
                    out.append(I(name, "stroke-progression", wl, f"{where} ({ra[3]:.0f}): stroke {wa:.0f} units, thinner than in "
                                 f"{near_label} ({wb:.0f})", severity="slows"))
    return out


def parts_close_checks(name, wl, cs, near_cs, near_label, upm):
    """Separate parts (the dots of a dieresis, the dot of i, the letters of ™) that end up
    under 3% of the em apart in a derived weight, when the nearest master keeps them at
    least half as far again apart: they read as one blob at text sizes."""
    out = []
    n = len(cs)
    if n < 2 or n > 8 or len(near_cs) != n:
        return out
    pl, npl = polys(cs), polys(near_cs)
    if len(pl) != n or len(npl) != n:
        return out
    limit = 0.03 * upm

    def inside(pt, poly):
        x, y = pt
        hit = False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
        return hit

    def apart(P, i, j):
        # neither contains the other (a counter) and they don't cross
        return not (inside(P[j][0], P[i]) or inside(P[i][0], P[j]))

    # only parts at the top level: a counter inside an outline is not a separate part
    top = [i for i in range(n) if not any(k != i and inside(npl[i][0], npl[k]) for k in range(n))]
    for i in top:
        for j in top:
            if j <= i or not apart(pl, i, j) or not apart(npl, i, j) or crossing(cs[i], cs[j]):
                continue
            d = float(cKDTree(pl[i]).query(pl[j])[0].min())
            dn = float(cKDTree(npl[i]).query(npl[j])[0].min())
            if d < limit and dn >= 1.5 * d:
                out.append(I(name, "parts-close", wl, f"contours {i} and {j} are {d:.0f} units apart, {near_label} has {dn:.0f}: "
                             "separate parts closing up", i))
    return out


def straight_segs(c):
    """(i, j) for each straight segment of a closed contour (consecutive on-curve points)."""
    n = len(c)
    if not n or c[0].type == "move":
        return []
    ons = [i for i, p in enumerate(c) if p.type]
    return [(i, ons[(k + 1) % len(ons)]) for k, i in enumerate(ons)
            if len(ons) > 1 and (ons[(k + 1) % len(ons)] - i) % n == 1]


def _winding(pt, pl):
    x, y = pt
    w = 0
    for poly in pl:
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 <= y < y1 or y1 <= y < y0) and x0 + (y - y0) * (x1 - x0) / (y1 - y0) > x:
                w += 1 if y1 > y0 else -1
    return w


def edge_measures(cs, aligned, upm):
    """The geometry edge_checks judges, as numbers: {("turn", contour, i, j): (units off
    upright or level, edge length, "upright" or "level")} and {("wedge", (contour, i, j),
    (contour, i, j)): (thickness at one end, at the other)}. Straight edges whose geometry every master agrees on, changed in a derived weight.
    Extrapolation keeps upright and level edges so by construction and seldom makes a
    wedge, so these mostly flag a later fix that moved one end of an edge and not the
    other:
      edge-turned   an edge upright or level in every master (a stem's side, a bar's
                    top) isn't any more: a leaning stem, a tilted bar (other edges may
                    turn: carrying a master's taper to an extreme turns them a little)
      stroke-wedge  the two sides of a straight stroke are parallel in every master but
                    not here: the stroke thickens toward one end (by over 3 units
                    and 12%)"""
    out = {}
    if not aligned or any(len(a) != len(cs) for a in aligned):
        return out
    sg = []  # (ci, i, j, [master unit vectors], [master endpoints], derived endpoints)
    for ci, c in enumerate(cs):
        if any(len(a[ci]) != len(c) for a in aligned):
            continue
        for i, j in straight_segs(c):
            ends = [((a[ci][i].x, a[ci][i].y), (a[ci][j].x, a[ci][j].y)) for a in aligned]
            if min(L.dist(*e) for e in ends) < 8:
                continue
            us = [L.unit(L.sub(e[1], e[0])) for e in ends]
            de = ((c[i].x, c[i].y), (c[j].x, c[j].y))
            sg.append((ci, i, j, us, ends, de))
            dv = L.sub(de[1], de[0])
            upright = all(abs(e[0][0] - e[1][0]) < 0.01 for e in ends) or all(abs(e[0][1] - e[1][1]) < 0.01 for e in ends)
            if L.norm(dv) < 8 or not upright or min(L.dot(us[0], u) for u in us) < 0 or L.dot(us[0], dv) <= 0:
                continue
            out[("turn", ci, i, j)] = (abs(L.cross(us[0], dv)), L.norm(dv), "upright" if abs(us[0][0]) < 0.01 else "level")
    pls = None
    sin1 = math.sin(math.radians(1.0))
    for x in range(len(sg)):
        for y in range(x + 1, len(sg)):
            A, B = sg[x], sg[y]
            ok, spans = True, []
            for m in range(len(aligned)):
                ua, ub = A[3][m], B[3][m]
                if abs(L.cross(ua, ub)) > sin1 or L.dot(ua, ub) > -0.99:
                    ok = False
                    break
                a0, a1 = A[4][m]
                b0, b1 = B[4][m]
                d = abs(L.cross(ua, L.sub(b0, a0)))
                la = L.dist(a0, a1)
                tb = sorted((L.dot(L.sub(b0, a0), ua), L.dot(L.sub(b1, a0), ua)))
                lo, hi = max(0.0, tb[0]), min(la, tb[1])
                if not 2 <= d <= 0.2 * upm or hi - lo < 0.5 * min(la, tb[1] - tb[0]):
                    ok = False
                    break
                spans.append((lo / la, hi / la))
            if not ok:
                continue
            if pls is None:
                pls = [polys(a) for a in aligned]
            m0 = aligned[0]
            a0, a1 = A[4][0]
            ua = A[3][0]
            b0 = B[4][0][0]
            mid_u = (spans[0][0] + spans[0][1]) / 2
            pa = L.add(a0, L.mul(L.sub(a1, a0), mid_u))
            nrm = (-ua[1], ua[0])
            d0 = L.cross(ua, L.sub(b0, a0))
            probe = L.add(pa, L.mul(nrm, d0 / 2))
            if not m0 or _winding(probe, pls[0]) == 0:
                continue  # a counter or the space between parts, not a stroke
            # thickness at both ends of the shared stretch, in the masters and here
            lo = max(s_[0] for s_ in spans)
            hi = min(s_[1] for s_ in spans)
            if hi - lo < 0.2:
                continue

            def thick(ae, be, f):
                p_ = L.add(ae[0], L.mul(L.sub(ae[1], ae[0]), f))
                ub_ = L.unit(L.sub(be[1], be[0]))
                return abs(L.cross(ub_, L.sub(p_, be[0])))
            mt = [(thick(A[4][m], B[4][m], lo), thick(A[4][m], B[4][m], hi)) for m in range(len(aligned))]
            if max(abs(t0 - t1) for t0, t1 in mt) > 1.0:
                continue
            if L.dist(*A[5]) < 8 or L.dist(*B[5]) < 8:
                continue
            out[("wedge", A[:3], B[:3])] = (thick(A[5], B[5], lo), thick(A[5], B[5], hi))
    return out


def edge_checks(name, wl, cs, aligned, upm):
    """edge-turned (over 1.5 units off) and stroke-wedge (ends over 3 units and 12% apart)
    from edge_measures."""
    out = []
    for key, v in edge_measures(cs, aligned, upm).items():
        if key[0] == "turn" and v[0] > 1.5:
            ci, i, j = key[1:]
            out.append(I(name, "edge-turned", wl, f"contour {ci}, edge {i}-{j}: {v[2]} in every master, "
                         f"turned {math.degrees(math.asin(min(1.0, v[0] / v[1]))):.1f}\u00b0 here "
                         f"({v[0]:.1f} units over its length): a leaning stem or tilted bar", ci, i))
        elif key[0] == "wedge" and abs(v[0] - v[1]) > max(3.0, 0.12 * (v[0] + v[1]) / 2):
            A, B = key[1], key[2]
            out.append(I(name, "stroke-wedge", wl, f"contour {A[0]} edge {A[1]}-{A[2]} and contour {B[0]} edge "
                         f"{B[1]}-{B[2]}: parallel in every master, {v[0]:.0f} and {v[1]:.0f} units apart at the two ends "
                         "here: the stroke turns into a wedge", A[0], A[1]))
    return out



# ------------------------------------------------------------ driver

def reference_state(aligned, r, labels, opt):
    """Per glyph: the reference contours and smooth nodes, and on opt the reference
    master's corner bends the shape checks compare with."""
    opt.ref_label = labels[r]
    ref_cs = aligned[r]
    opt.ref_bend, opt.straight_in_ref = {}, set()
    for ci, c in enumerate(ref_cs):
        closed = c[0].type != "move"
        for i, p in enumerate(c):
            if p.type is None or p.smooth:
                continue
            t_in, t_out = L.node_tangents(c, i, closed)
            if t_in and t_out:
                b = L.angle_deg(t_in, t_out)
                opt.ref_bend[(ci, i)] = b
                if b < 3 and any(c[k].type is None for k in L.neighbors(c, i, closed) if k is not None):
                    opt.straight_in_ref.add((ci, i))
    smooth_any = {(ci, i) for a in aligned for ci, c in enumerate(a) for i, p in enumerate(c) if p.smooth}
    return ref_cs, smooth_any


def derived_glyph_issues(name, d, gl, masters, labels, r, aligned, st, ref_cs, smooth_any, stem_of, opt):
    """Every derived-weight check for one glyph of derived font d."""
    issues = []
    dg = d.font[name]
    dcs = [pts_of(c) for c in dg.contours]
    same_as = next((m.label for m, g in zip(masters, gl) if g.contours and
                    [[(p.x, p.y) for p in c] for c in dcs] == [[(p.x, p.y) for p in c.points] for c in g.contours]), None)
    if same_as:
        return [I(name, "not-derived", d.label, f"identical to master {same_as}: copied, not derived (often because the masters were not compatible)")]
    rg = [pts_of(c) for c in gl[r].contours]
    same = len(dcs) == len(rg) and all([p.type for p in a] == [p.type for p in b] for a, b in zip(dcs, rg))
    if not same or len(dcs) != len(ref_cs) or st:
        # not built point by point from these masters: match it like a master
        da, _, dst = align_glyph(name, [gl[r], dg], [labels[r], d.label], 0)
        issues += [x for x in dst if x["weight"] == d.label]
        if da is None:
            return issues
        dcs = da[1]
    # else: same point structure as the reference master, so indices match
    # already and inside-out contours show up as direction-flip
    issues += shape_checks(name, d.label, dcs, ref_cs, smooth_any, opt, derived=True)
    issues += curvature_checks(name, d.label, dcs, ref_cs, False, opt)
    issues += corner_checks(name, d.label, dcs, ref_cs, True, opt)
    issues += scan_checks(name, d.label, dcs, opt)
    issues += crossing_checks(name, d.label, dcs, ref_cs)
    issues += overhang_checks(name, d.label, dg, d.font, [(g, m.font) for g, m in zip(gl, masters)])
    issues += edge_checks(name, d.label, dcs, aligned, d.font.info.unitsPerEm or 1000)
    sd = stem_of.get(d.label)
    if sd:
        ni = min((k for k in range(len(masters)) if stem_of.get(masters[k].label)),
                 key=lambda k: abs(stem_of[masters[k].label] - sd), default=None)
        if ni is not None:
            issues += proportion_checks(name, d.label, dcs, aligned[ni], sd, stem_of[masters[ni].label], masters[ni].label)
            issues += parts_close_checks(name, d.label, dcs, aligned[ni], masters[ni].label, d.font.info.unitsPerEm or 1000)
            if getattr(opt, "evenness", False):
                ns = stem_of[masters[ni].label]
                issues += evenness_checks(name, d.label, dg, gl[ni], sd / ns, masters[ni].label, ns,
                                          opt.__dict__.setdefault("even_cache", {}))
    return issues


class DerivedChecker:
    """The audit's derived-weight checks for one glyph at a time, for scripts that
    change a derived weight and want to know whether a change made it worse.
    masters: [(label, ufoLib2.Font)]; derived: (label, font) as it is being edited.
    evenness=True adds stroke-uneven and stroke-weight (off by default, so the steps that
    choose between variants with this, contrast.py and reshape.py, keep their results)."""

    def __init__(self, masters, derived, ref=None, evenness=False):
        import types
        self.masters = [L.Master(lab, float(lab), float(lab), Path("."), f) for lab, f in masters]
        self.labels = [m.label for m in self.masters]
        self.d = L.Master(derived[0], float(derived[0]), float(derived[0]), Path("."), derived[1])
        upm = self.masters[0].font.info.unitsPerEm or 1000
        self.opt = types.SimpleNamespace(kink_tol=0.5, tension_tol=0.15, scallop_tol=0.12, corner_tol=25.0, g2_tol=0.15,
                                         merge_tol=1.0, flip_tol=8.0, motion_tol=3.0, min_stroke=0.008 * upm,
                                         min_counter=0.01 * upm, only=None, evenness=evenness)
        self.opt.ref_i = self.labels.index(ref) if ref in self.labels else len(self.masters) // 2
        self.stem_of = {m.label: L.ref_stem(m.font)[1] for m in self.masters + [self.d]}

    def issues(self, name):
        gl = [m.font[name] for m in self.masters]
        r = best_ref(name, gl, self.labels, self.opt.ref_i)
        aligned, _, st = align_glyph(name, gl, self.labels, r)
        if aligned is None or not any(g.contours for g in gl):
            return []
        ref_cs, smooth_any = reference_state(aligned, r, self.labels, self.opt)
        return derived_glyph_issues(name, self.d, gl, self.masters, self.labels, r, aligned, st, ref_cs, smooth_any,
                                    self.stem_of, self.opt)

    def score(self, name):
        sev = [i["severity"] for i in self.issues(name)]
        return (sev.count("blocks"), sev.count("slows"))

    def geometry(self, name):
        """edge_measures of the derived glyph (empty when its points don't match the
        masters'): how far upright edges lean and parallel strokes taper, in units."""
        gl = [m.font[name] for m in self.masters]
        r = best_ref(name, gl, self.labels, self.opt.ref_i)
        aligned, _, st = align_glyph(name, gl, self.labels, r)
        if aligned is None or st:
            return {}
        dcs = [pts_of(c) for c in self.d.font[name].contours]
        if len(dcs) != len(aligned[r]) or any([p.type for p in a] != [p.type for p in b] for a, b in zip(dcs, aligned[r])):
            return {}
        return edge_measures(dcs, aligned, self.d.font.info.unitsPerEm or 1000)

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--derived", nargs="*", default=[], help="weight=path.ufo for derived/extrapolated outlines")
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--ref", help="label of the reference master (default: middle)")
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--md", help="write the summary here (also printed)")
    ap.add_argument("--kink-tol", type=float, default=0.5, help="degrees (default 0.5)")
    ap.add_argument("--tension-tol", type=float, default=0.15)
    ap.add_argument("--scallop-tol", type=float, default=0.12, help="curvature at a smooth node may differ this much from the curves either side (default 0.12 = 12%%)")
    ap.add_argument("--corner-tol", type=float, default=25.0, help="degrees a corner may differ from the reference (default 25)")
    ap.add_argument("--g2-tol", type=float, default=0.15, help="curvature step at a smooth node, |k1-k2|/(k1+k2) (default 0.15)")
    ap.add_argument("--merge-tol", type=float, default=1.0, help="units a merged curve may move when counting excess nodes (default 1)")
    ap.add_argument("--no-merge-count", action="store_true", help="skip counting removable nodes (faster)")
    ap.add_argument("--flip-tol", type=float, default=8.0, help="degrees a handle may swing off the other masters' trend (default 8)")
    ap.add_argument("--motion-tol", type=float, default=3.0, help="font units (default 3)")
    ap.add_argument("--min-stroke", type=float, help="font units (default 0.8%% of UPM)")
    ap.add_argument("--min-counter", type=float, help="font units (default 1%% of UPM)")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--only", nargs="+", help="masters fix.py may change (limits the repredict candidate list)")
    ap.add_argument("--axis", choices=["stem", "design"], default="stem",
                    help="where masters sit when judging motion and tension trends (default: measured stem width)")
    ap.add_argument("--no-evenness", dest="evenness", action="store_false",
                    help="skip stroke-uneven and stroke-weight in derived weights")
    opt = ap.parse_args(argv)

    masters, _ = L.load_sources(opt.sources)
    derived = []
    for spec in opt.derived:
        w, p = spec.split("=", 1)
        import ufoLib2
        derived.append(L.Master(w, float(w), float(w), Path(p).resolve(), ufoLib2.Font.open(p)))
    labels = [m.label for m in masters]
    opt.ref_i = labels.index(opt.ref) if opt.ref else len(masters) // 2
    opt.ref_label = labels[opt.ref_i]
    upm = masters[0].font.info.unitsPerEm or 1000
    opt.min_stroke = opt.min_stroke if opt.min_stroke is not None else 0.008 * upm
    opt.min_counter = opt.min_counter if opt.min_counter is not None else 0.01 * upm
    fonts = [m.font for m in masters] + [d.font for d in derived]
    names = L.common_glyphs(fonts, opt.glyphs)
    # place masters by measured stem width when every master has one (matches derive.py --axis stem)
    stem_locs = [L.ref_stem(m.font)[1] for m in masters]
    locs = stem_locs if opt.axis == "stem" and all(stem_locs) and len(set(stem_locs)) == len(stem_locs) else [m.loc for m in masters]

    issues, incompatible = [], []
    stem_of = {m.label: L.ref_stem(m.font)[1] for m in masters + derived}
    for name in names:
        gl = [m.font[name] for m in masters]
        # per glyph, measure against the master most others agree with, so
        # structural findings name the odd one out
        r = best_ref(name, gl, labels, opt.ref_i)
        aligned, corr, st = align_glyph(name, gl, labels, r)
        issues += st
        if not any(g.contours for g in gl):
            continue
        if aligned is None:
            incompatible.append(name)
            continue
        ref_cs, smooth_any = reference_state(aligned, r, labels, opt)
        for mi, (m, a) in enumerate(zip(masters, aligned)):
            issues += shape_checks(name, m.label, a, ref_cs, smooth_any, opt, derived=False)
            issues += curvature_checks(name, m.label, a, ref_cs, mi == r, opt)
            issues += drawing_checks(name, m.label, a, m.font, opt)
            if mi != r:
                issues += corner_checks(name, m.label, a, ref_cs, False, opt)
                issues += crossing_checks(name, m.label, a, ref_cs)
        if not opt.no_merge_count:
            import fix
            order = [r] + [k for k in range(len(aligned)) if k != r]
            can = sum(fix.plan_merges([aligned[k] for k in order], ci, opt.merge_tol, greedy=False)[1]
                      for ci in range(len(ref_cs)))
            if can:
                total = sum(1 for c in ref_cs for p in c if p.type)
                issues.append(I(name, "excess-nodes", "all", f"{can} of {total} nodes could each go with the curves moving under "
                                f"{opt.merge_tol:g} units in every master (fix.py --ops merge)", severity="slows" if can >= total / 4 else "minor"))
        mc, _, per = master_checks(name, labels, locs, aligned, opt, r)
        issues += mc
        for d in derived:
            issues += derived_glyph_issues(name, d, gl, masters, labels, r, aligned, st, ref_cs, smooth_any, stem_of, opt)
    issues += copy_drift_checks(names, masters, derived)

    stems = []
    copied = {(i["glyph"], i["weight"]) for i in issues if i["code"] == "not-derived"}
    for m in masters + derived:
        g, w = L.ref_stem(m.font)
        stems.append({"weight": m.label, "path": str(m.path), "stem_glyph": g, "stem": None if w is None else round(w, 1),
                      "derived": m in derived, "copied": (g, m.label) in copied})
    report = {"masters": [m.label for m in masters], "derived": [d.label for d in derived], "reference": labels[opt.ref_i],
              "glyphs_checked": len(names), "incompatible": incompatible, "stems": stems, "issues": issues,
              "only": opt.only}
    report["issues"] = issues = collapse_scans(issues)
    if opt.json:
        Path(opt.json).write_text(json.dumps(report, indent=1))
    md = summary(report, opt.top)
    if opt.md:
        Path(opt.md).write_text(md)
    print(md)
    return 1 if any(i["severity"] == "blocks" for i in issues) else 0  # exit 1 only on blocks


def collapse_scans(issues):
    """One thin-stroke / counter-tight finding per glyph and weight, listing the scans."""
    keep, grouped = [], defaultdict(list)
    for i in issues:
        if i["code"] in ("thin-stroke", "counter-tight"):
            grouped[(i["glyph"], i["weight"], i["code"])].append(i)
        else:
            keep.append(i)
    for (g, w, code), lst in grouped.items():
        first = dict(lst[0])
        first["detail"] = f"{len(lst)} scans; " + "; ".join(x["detail"] for x in lst[:3]) + (" …" if len(lst) > 3 else "")
        keep.append(first)
    return keep


def summary(r, top):
    iss = r["issues"]
    der = set(r["derived"])
    out = [f"# Outline audit: {r['glyphs_checked']} glyphs, masters {', '.join(r['masters'])}"
           + (f", derived {', '.join(r['derived'])}" if r["derived"] else "") + f", reference {r['reference']}", ""]
    out.append("Stems: " + ", ".join(f"{s['weight']}={s['stem']}" + ("*" if s["derived"] else "") + (" (copied, not derived)" if s.get("copied") else "")
                                     for s in r["stems"]) + f" (glyph {r['stems'][0]['stem_glyph']}, * = derived)")
    sev = Counter(i["severity"] for i in iss)
    in_der = Counter(i["severity"] for i in iss if i["weight"] in der)
    line = f"Issues: {sev.get('blocks', 0)} blocks, {sev.get('slows', 0)} slows, {sev.get('minor', 0)} minor"
    if der:
        line += f" ({in_der.get('blocks', 0)} / {in_der.get('slows', 0)} / {in_der.get('minor', 0)} of them in derived weights)"
    out.append(line)
    struct = {i["glyph"] for i in iss if i["code"] in ("contour-order", "direction", "start-point", "component-order") and i["weight"] not in der}
    hand = set(r["incompatible"])
    out.append(f"Structure: {len(hand)} glyph(s) need a fix by hand before they interpolate" + (f" ({' '.join(sorted(hand)[:12])})" if hand else "")
               + f"; {len(struct - hand)} more are fixed by fix.py --ops compat")
    if not iss:
        out += ["", "No findings."]
        return "\n".join(out) + "\n"
    out += ["", "| code | severity | count | glyphs |", "|---|---|---|---|"]
    byc = defaultdict(list)
    for i in iss:
        byc[i["code"]].append(i)
    order = {"blocks": 0, "slows": 1, "minor": 2}

    def worst(lst):
        return min((i["severity"] for i in lst), key=lambda s: order[s])
    for code, lst in sorted(byc.items(), key=lambda kv: (order[worst(kv[1])], -len(kv[1]))):
        gs = sorted({i["glyph"] for i in lst})
        sevs = Counter(i["severity"] for i in lst)
        sev_s = ", ".join(f"{sevs[s]} {s}" for s in ("blocks", "slows", "minor") if s in sevs)
        out.append(f"| {code} | {sev_s} | {len(lst)} | {' '.join(gs[:12])}{' …' if len(gs) > 12 else ''} |")
    score = Counter()
    for i in iss:
        score[i["glyph"]] += SCORE[i["severity"]]
    out += ["", "Worst glyphs: " + ", ".join(f"{g} ({s})" for g, s in score.most_common(top))]
    movable = set(r.get("only") or r["masters"]) - {r["reference"]}
    one = [i for i in iss if i["severity"] != "minor" and i["point"] is not None and i["weight"] in movable
           and i["code"] in ONE_MASTER_CODES]
    in_ref = sum(1 for i in iss if i["severity"] != "minor" and i["point"] is not None and i["weight"] == r["reference"]
                 and i["code"] in ONE_MASTER_CODES)
    if one:
        out += ["", "Points one master has wrong (repredict candidates in " + ", ".join(sorted(movable, key=lambda x: (not x.replace(".", "", 1).isdigit(), float(x) if x.replace(".", "", 1).isdigit() else 0, x))) +
                "; look at a --zoom render of each first):"]
        seen = set()
        prio = ["corner-flip", "handle-backward", "handle-flip", "handle-overlong", "corner-change", "tension-jump", "kink",
                "handle-crossing", "alignment-break"]
        for i in sorted(one, key=lambda i: (-SCORE[i["severity"]], prio.index(i["code"]), -(i.get("deg") or 0), i["glyph"])):
            key = f"{i['glyph']}:{i['weight']}:{i['contour']}:{i['point']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(f"- {key}  {i['code']}: {i['detail'][:160]}")
            if len(seen) >= top:
                out.append(f"- … {len(one) - len(seen)} more in the JSON")
                break
    if in_ref:
        out += ["", f"{in_ref} such finding(s) are in the reference master {r['reference']}: fix.py doesn't move it; review them by hand."]
    if len(r["masters"]) == 3:
        out += ["", "With three masters, which one is 'the odd one' is a guess: confirm each candidate in a zoom."]
    return "\n".join(out) + "\n"


ONE_MASTER_CODES = {"tension-jump", "alignment-break", "handle-backward", "handle-flip", "handle-overlong", "kink", "handle-crossing",
                    "corner-flip", "corner-change"}


if __name__ == "__main__":
    sys.exit(main())
