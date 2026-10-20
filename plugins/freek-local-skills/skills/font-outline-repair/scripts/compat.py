"""Point-structure matching between masters.

align_glyph() compares every master's glyph with the reference master and works
out the contour order, contour direction and start point that make them match.
It returns aligned point lists (in the reference master's order) plus the
issues found. fix.py applies the same corrections to the real UFO contours.
"""
from __future__ import annotations

from collections import namedtuple

from fontTools.pens.pointPen import ReverseContourPointPen

import fontlib as L

Pt = namedtuple("Pt", "x y type smooth")


class _Capture:
    """Point pen that records one contour as a list of Pt."""

    def __init__(self):
        self.contours = []

    def beginPath(self, identifier=None, **kw):
        self.cur = []

    def addPoint(self, pt, segmentType=None, smooth=False, name=None, identifier=None, **kw):
        self.cur.append(Pt(pt[0], pt[1], segmentType, bool(smooth)))

    def endPath(self):
        self.contours.append(self.cur)

    def addComponent(self, *a, **kw):
        pass


def pts_of(contour):
    return [Pt(p.x, p.y, p.type, bool(p.smooth)) for p in contour.points]


def reversed_pts(pts):
    cap = _Capture()
    pen = ReverseContourPointPen(cap)
    pen.beginPath()
    for p in pts:
        pen.addPoint((p.x, p.y), segmentType=p.type, smooth=p.smooth)
    pen.endPath()
    return cap.contours[0]


def signed_area(pts):
    """Exact signed area of a point list (positive = counter-clockwise)."""
    from fontTools.pens.areaPen import AreaPen
    from fontTools.pens.pointPen import PointToSegmentPen
    pen = AreaPen()
    draw_pts(pts, PointToSegmentPen(pen))
    return pen.value


def draw_pts(pts, pointpen):
    pointpen.beginPath()
    for p in pts:
        pointpen.addPoint((p.x, p.y), segmentType=p.type, smooth=p.smooth)
    pointpen.endPath()


def _bbox(pts):
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _normed(pts):
    x0, y0, x1, y1 = _bbox(pts)
    s = max(x1 - x0, y1 - y0, 1.0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [((p.x - cx) / s, (p.y - cy) / s) for p in pts]


def rotation_options(ref, cand):
    """Rotations r (cand[r:] + cand[:r]) whose point types match ref, with a shape cost."""
    n = len(ref)
    if len(cand) != n or n == 0:
        return []
    if cand[0].type == "move" or ref[0].type == "move":  # open contour: no rotation
        same = [p.type for p in ref] == [p.type for p in cand]
        return [(0, 0.0)] if same else []
    rt = [p.type for p in ref]
    ct = [p.type for p in cand]
    nr = _normed(ref)
    nc = _normed(cand)
    out = []
    for r in range(n):
        if ct[r:] + ct[:r] == rt:
            rot = nc[r:] + nc[:r]
            cost = sum((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 for a, b in zip(nr, rot))
            out.append((r, cost))
    return out


def _contour_key(pts, gscale):
    x0, y0, x1, y1 = _bbox(pts)
    return ((x0 + x1) / 2 / gscale, (y0 + y1) / 2 / gscale, abs(signed_area(pts)) ** 0.5 / gscale, len(pts))


def match_contours(ref_cs, cs, gscale):
    """Permutation perm so that cs[perm[i]] corresponds to ref_cs[i]."""
    from scipy.optimize import linear_sum_assignment
    kr = [_contour_key(c, gscale) for c in ref_cs]
    kc = [_contour_key(c, gscale) for c in cs]
    cost = [[abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) + (0 if a[3] == b[3] else 5)
             for b in kc] for a in kr]
    rows, cols = linear_sum_assignment(cost)
    perm = [0] * len(ref_cs)
    for r, c in zip(rows, cols):
        perm[r] = int(c)
    ident = sum(cost[i][i] for i in range(len(ref_cs)))
    best = sum(cost[i][perm[i]] for i in range(len(ref_cs)))
    if perm != list(range(len(ref_cs))) and best < ident - 0.02:
        return perm
    return list(range(len(ref_cs)))


def best_ref(name, glyphs, labels, default_i):
    """The master that the most other masters already agree with structurally,
    so a fix changes the odd one out rather than the majority."""
    best = (None, default_i)
    for cand in [default_i] + [i for i in range(len(glyphs)) if i != default_i]:
        _, corr, iss = align_glyph(name, glyphs, labels, cand)
        bad = {i["weight"] for i in iss if i["code"] in ("contour-order", "direction", "start-point", "component-order")}
        if best[0] is None or len(bad) < best[0]:
            best = (len(bad), cand)
    return best[1]


def align_glyph(name, glyphs, labels, ref_i):
    """glyphs: one glyph object per master. Returns (aligned, corrections, issues).
    aligned: per master a list of contours (lists of Pt) in ref order, or None
    when the glyph cannot be made compatible automatically.
    corrections: per master {'perm': [...], 'reverse': {ci,...}, 'rotate': {ci: r}}."""
    issues = []
    ref = glyphs[ref_i]
    ref_cs = [pts_of(c) for c in ref.contours]
    allpts = [p for c in ref_cs for p in c]
    if allpts:
        x0, y0, x1, y1 = _bbox(allpts)
        gscale = max(x1 - x0, y1 - y0, 1.0)
    else:
        gscale = 1.0
    aligned = [None] * len(glyphs)
    corrections = [None] * len(glyphs)
    ok = True
    ref_comps = [c.baseGlyph for c in ref.components]
    for mi, g in enumerate(glyphs):
        comps = [c.baseGlyph for c in g.components]
        if comps != ref_comps:
            if sorted(comps) == sorted(ref_comps):
                issues.append(L.issue(name, "component-order", "blocks", labels[mi], f"components {comps} vs {ref_comps} in {labels[ref_i]}"))
            else:
                issues.append(L.issue(name, "component-mismatch", "blocks", labels[mi], f"components {comps} vs {ref_comps} in {labels[ref_i]}"))
                ok = False
        if mi == ref_i:
            aligned[mi] = ref_cs
            corrections[mi] = {"perm": list(range(len(ref_cs))), "reverse": set(), "rotate": {}}
            continue
        cs = [pts_of(c) for c in g.contours]
        if len(cs) != len(ref_cs):
            issues.append(L.issue(name, "contour-count", "blocks", labels[mi], f"{len(cs)} contours vs {len(ref_cs)} in {labels[ref_i]}"))
            ok = False
            continue
        perm = match_contours(ref_cs, cs, gscale) if len(cs) > 1 else [0] * len(cs)
        if perm != list(range(len(cs))):
            issues.append(L.issue(name, "contour-order", "blocks", labels[mi], f"contour order {perm} matches {labels[ref_i]}", perm=perm))
        out, corr = [], {"perm": perm, "reverse": set(), "rotate": {}}
        for ci, rc in enumerate(ref_cs):
            c = cs[perm[ci]]
            ar, ac = signed_area(rc), signed_area(c)
            if ar * ac < 0 and abs(ar) > 1 and abs(ac) > 1:
                issues.append(L.issue(name, "direction", "blocks", labels[mi], f"contour runs the other way than in {labels[ref_i]}", contour=ci))
                c = reversed_pts(c)
                corr["reverse"].add(ci)
            if len(c) != len(rc):
                extra = len(c) - len(rc)
                issues.append(L.issue(name, "point-count", "blocks", labels[mi],
                                      f"{len(c)} points vs {len(rc)} in {labels[ref_i]} ({'+' if extra > 0 else ''}{extra})", contour=ci))
                ok = False
                out.append(None)
                continue
            opts = rotation_options(rc, c)
            if not opts:
                issues.append(L.issue(name, "point-type", "blocks", labels[mi], f"point types differ from {labels[ref_i]} at every start point", contour=ci))
                ok = False
                out.append(None)
                continue
            r, cost = min(opts, key=lambda o: o[1])
            zero = next((o for o in opts if o[0] == 0), None)
            if r != 0 and (zero is None or zero[1] > cost * 1.5 + 0.02):
                sev = "blocks" if zero is None else "slows"
                issues.append(L.issue(name, "start-point", sev, labels[mi], f"start point is {r} points off from {labels[ref_i]}", contour=ci, rotate=r))
                c = c[r:] + c[:r]
                corr["rotate"][ci] = r
            out.append(c)
        if any(c is None for c in out):
            continue
        aligned[mi] = out
        corrections[mi] = corr
    if not ok or any(a is None for a in aligned):
        return None, corrections, issues
    return aligned, corrections, issues
