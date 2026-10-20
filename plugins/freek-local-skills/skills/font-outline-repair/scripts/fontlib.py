"""Shared helpers for the font-outline-repair scripts.

Loads weight masters from a .designspace file or from label=path.ufo pairs,
and provides the geometry used by audit.py, derive.py, fix.py and render.py.
Coordinates are font units. Contours are read from UFO point lists, so point
indices match what a font editor shows.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import ufoLib2
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.basePen import decomposeQuadraticSegment, decomposeSuperBezierSegment
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen


# ---------------------------------------------------------------- loading

@dataclass
class Master:
    label: str      # how reports name it, e.g. "300"
    weight: float   # user-space weight (the number people say)
    loc: float      # design-space location on the weight axis
    path: Path
    font: ufoLib2.Font


def _num(s: str) -> float:
    v = float(s)
    return int(v) if v.is_integer() else v


def load_sources(specs: list[str], axis_tag: str = "wght") -> tuple[list[Master], DesignSpaceDocument | None]:
    """specs: one .designspace path, or several 'weight=path.ufo' strings.
    Returns masters sorted by weight, plus the designspace document if any."""
    if len(specs) == 1 and specs[0].endswith(".designspace"):
        ds_path = Path(specs[0]).resolve()
        doc = DesignSpaceDocument.fromfile(ds_path)
        axes = [a for a in doc.axes if getattr(a, "tag", None) == axis_tag] or doc.axes[:1]
        if not axes:
            sys.exit(f"{ds_path}: no axes")
        axis = axes[0]
        others = [a for a in doc.axes if a is not axis]
        masters = []
        for s in doc.sources:
            if s.layerName:
                print(f"note: skipping sparse layer source {s.filename}:{s.layerName}", file=sys.stderr)
                continue
            if any(abs(s.location.get(a.name, a.map_forward(a.default)) - a.map_forward(a.default)) > 1e-6 for a in others):
                print(f"note: skipping {s.filename}: not at the default of the other axes", file=sys.stderr)
                continue
            design = s.location.get(axis.name, axis.map_forward(axis.default))
            user = axis.map_backward(design)
            p = Path(s.path) if s.path else (ds_path.parent / s.filename)
            masters.append(Master(str(_num(round(user, 2))), user, design, p.resolve(), ufoLib2.Font.open(p)))
        masters.sort(key=lambda m: m.weight)
        return masters, doc
    masters = []
    for spec in specs:
        if "=" not in spec:
            sys.exit(f"expected weight=path.ufo, got {spec!r}")
        w, p = spec.split("=", 1)
        masters.append(Master(w, float(w), float(w), Path(p).resolve(), ufoLib2.Font.open(p)))
    masters.sort(key=lambda m: m.weight)
    return masters, None


def common_glyphs(fonts, only=None):
    names = [n for n in fonts[0].keys() if all(n in f for f in fonts[1:])]
    if only:
        wanted = set(only)
        names = [n for n in names if n in wanted]
    order = {n: i for i, n in enumerate(fonts[0].glyphOrder or [])}
    return sorted(names, key=lambda n: (order.get(n, 1e9), n))


# ---------------------------------------------------------------- vectors

def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def add(a, b): return (a[0] + b[0], a[1] + b[1])
def mul(a, k): return (a[0] * k, a[1] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1]
def cross(a, b): return a[0] * b[1] - a[1] * b[0]
def norm(a): return math.hypot(a[0], a[1])
def dist(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(a):
    n = norm(a)
    return (a[0] / n, a[1] / n) if n > 1e-9 else (0.0, 0.0)


def angle_deg(a, b):
    """Unsigned angle between two vectors, 0..180."""
    na, nb = norm(a), norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    c = max(-1.0, min(1.0, dot(a, b) / (na * nb)))
    return math.degrees(math.acos(c))


def signed_angle_deg(a, b):
    return math.degrees(math.atan2(cross(a, b), dot(a, b)))


# ---------------------------------------------------------------- contours

def xy(p):
    return (p.x, p.y)


def on_curve(p):
    return p.type is not None


def segments(points, closed=True):
    """Yield (i0, [offcurve indices], i1, segtype) over a UFO point list."""
    n = len(points)
    ons = [i for i, p in enumerate(points) if on_curve(p)]
    if not ons:
        return []
    out = []
    if not closed:
        for a, b in zip(ons, ons[1:]):
            out.append((a, list(range(a + 1, b)), b, points[b].type))
        return out
    for k, a in enumerate(ons):
        b = ons[(k + 1) % len(ons)]
        offs = []
        j = (a + 1) % n
        while j != b:
            offs.append(j)
            j = (j + 1) % n
        out.append((a, offs, b, points[b].type))
    return out


def is_closed(contour):
    return not (contour.points and contour.points[0].type == "move")


def neighbors(points, i, closed=True):
    n = len(points)
    if closed:
        return (i - 1) % n, (i + 1) % n
    return (i - 1 if i > 0 else None), (i + 1 if i < n - 1 else None)


def node_tangents(points, i, closed=True):
    """Incoming and outgoing direction at on-curve point i (None if missing).
    A zero-length handle falls back to the next point along."""
    n = len(points)
    P = xy(points[i])
    t_in = t_out = None
    pi, ni = neighbors(points, i, closed)
    k = pi
    for _ in range(3):
        if k is None:
            break
        v = sub(P, xy(points[k]))
        if norm(v) > 1e-6:
            t_in = v
            break
        k = (k - 1) % n if closed else (k - 1 if k > 0 else None)
    k = ni
    for _ in range(3):
        if k is None:
            break
        v = sub(xy(points[k]), P)
        if norm(v) > 1e-6:
            t_out = v
            break
        k = (k + 1) % n if closed else (k + 1 if k < n - 1 else None)
    return t_in, t_out


def contour_signed_area(contour):
    pen = AreaPen()
    contour.draw(pen)
    return pen.value  # fontTools: negative for counter-clockwise? see orientation()


def glyph_signed_areas(glyph):
    return [contour_signed_area(c) for c in glyph.contours]


# ---------------------------------------------------------------- beziers

def cubic_at(p0, p1, p2, p3, t):
    mt = 1 - t
    a, b, c, d = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


def cubic_d1(p0, p1, p2, p3, t):
    mt = 1 - t
    return (3 * mt * mt * (p1[0] - p0[0]) + 6 * mt * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0]),
            3 * mt * mt * (p1[1] - p0[1]) + 6 * mt * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1]))


def cubic_d2(p0, p1, p2, p3, t):
    mt = 1 - t
    return (6 * mt * (p2[0] - 2 * p1[0] + p0[0]) + 6 * t * (p3[0] - 2 * p2[0] + p1[0]),
            6 * mt * (p2[1] - 2 * p1[1] + p0[1]) + 6 * t * (p3[1] - 2 * p2[1] + p1[1]))


def cubic_split(p0, p1, p2, p3, t):
    def lerp(a, b): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    a, b, c = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    d, e = lerp(a, b), lerp(b, c)
    f = lerp(d, e)
    return (p0, a, d, f), (f, e, c, p3)


def _quad_roots(a, b, c):
    if abs(a) < 1e-12:
        return [] if abs(b) < 1e-12 else [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    s = math.sqrt(disc)
    return [(-b - s) / (2 * a), (-b + s) / (2 * a)]


def cubic_extrema_ts(p0, p1, p2, p3, axis):
    """t values in (0,1) where the curve has a local extreme along axis (0=x, 1=y)."""
    a0, a1, a2, a3 = p0[axis], p1[axis], p2[axis], p3[axis]
    # derivative/3 = A t^2 + B t + C
    A = -a0 + 3 * a1 - 3 * a2 + a3
    B = 2 * (a0 - 2 * a1 + a2)
    C = a1 - a0
    return sorted(t for t in _quad_roots(A, B, C) if 0 < t < 1)


def cubic_inflection_ts(p0, p1, p2, p3):
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    bx, by = p2[0] - 2 * p1[0] + p0[0], p2[1] - 2 * p1[1] + p0[1]
    cx, cy = p3[0] - 3 * p2[0] + 3 * p1[0] - p0[0], p3[1] - 3 * p2[1] + 3 * p1[1] - p0[1]
    # cross(B'(t), B''(t)) ∝ (b×c) t^2 + (a×c) t + (a×b)
    A = bx * cy - by * cx
    B = ax * cy - ay * cx
    C = ax * by - ay * bx
    return sorted(t for t in _quad_roots(A, B, C) if 0.02 < t < 0.98)


def line_intersection(p, r, q, s):
    """Intersection of p + t r and q + u s; returns (t, u) or None if parallel."""
    rxs = cross(r, s)
    if abs(rxs) < 1e-9:
        return None
    qp = sub(q, p)
    return cross(qp, s) / rxs, cross(qp, r) / rxs


# ---------------------------------------------------------------- flattening

def flatten_recording(value, steps=16):
    """RecordingPen value -> list of closed polygons [(x, y), ...]."""
    polys, cur, start = [], [], None
    for op, args in value:
        if op == "moveTo":
            cur = [args[0]]
            start = args[0]
        elif op == "lineTo":
            cur.append(args[0])
        elif op == "curveTo":
            pts = list(args)
            p0 = cur[-1]
            for (a, b, c) in ([tuple(pts)] if len(pts) == 3 else decomposeSuperBezierSegment(pts)):
                for k in range(1, steps + 1):
                    cur.append(cubic_at(p0, a, b, c, k / steps))
                p0 = c
        elif op == "qCurveTo":
            pts = list(args)
            if pts[-1] is None:  # all off-curve TrueType contour
                pts = pts[:-1]
                first = ((pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2)
                cur = [first]
                start = first
                pts = pts + [first]
            p0 = cur[-1]
            for (a, b) in decomposeQuadraticSegment(pts):
                for k in range(1, steps + 1):
                    t = k / steps
                    mt = 1 - t
                    cur.append((mt * mt * p0[0] + 2 * mt * t * a[0] + t * t * b[0],
                                mt * mt * p0[1] + 2 * mt * t * a[1] + t * t * b[1]))
                p0 = b
        elif op in ("closePath", "endPath"):
            if cur:
                if op == "closePath" and start is not None and cur[-1] != start:
                    cur.append(start)
                polys.append(cur)
            cur, start = [], None
    return polys


def glyph_polygons(glyph, font, steps=16):
    pen = DecomposingRecordingPen(font)
    glyph.draw(pen)
    return flatten_recording(pen.value, steps)


def contour_polygon(contour, steps=16):
    pen = RecordingPen()
    contour.draw(pen)
    polys = flatten_recording(pen.value, steps)
    return polys[0] if polys else []


def ink_runs(polys, coord, horizontal=True):
    """Ink intervals along a scanline (nonzero winding).
    horizontal=True: scanline y=coord, returns x-intervals."""
    xs = []
    for poly in polys:
        for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
            if not horizontal:
                x1, y1, x2, y2 = y1, x1, y2, x2
            if (y1 <= coord < y2) or (y2 <= coord < y1):
                t = (coord - y1) / (y2 - y1)
                xs.append((x1 + t * (x2 - x1), 1 if y2 > y1 else -1))
    xs.sort()
    runs, w, start = [], 0, None
    for x, d in xs:
        prev = w
        w += d
        if prev == 0 and w != 0:
            start = x
        elif prev != 0 and w == 0 and start is not None:
            runs.append((start, x))
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < 1e-6:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def ref_stem(font, glyph_names=("n", "l", "I", "H", "o")):
    """Width of the first vertical stem at mid x-height/cap-height. Returns (glyph, width) or (None, None)."""
    xh = font.info.xHeight or 500
    ch = font.info.capHeight or 700
    for name in glyph_names:
        if name in font:
            y = (ch if name[:1].isupper() else xh) / 2
            if name == "l":
                y = xh / 2
            runs = ink_runs(glyph_polygons(font[name], font), y)
            if runs:
                return name, runs[0][1] - runs[0][0]
    return None, None


# ---------------------------------------------------------------- weights

def blend_weights(locs, target, method="fit"):
    """Coefficients c_i so that derived = sum c_i * master_i.
    piecewise: extend the nearest pair of masters (what most tools do).
    fit: least-squares line through all masters along the axis (damps noise).
    wide: extend the two outermost masters (the widest base; least amplification).
    The sum of |c_i| is how much an error in the masters can grow in the result."""
    n = len(locs)
    if method == "wide" and n > 2:
        # the two outermost masters: the widest base, so the least amplification
        u = (target - locs[0]) / (locs[-1] - locs[0])
        c = [0.0] * n
        c[0], c[-1] = 1 - u, u
        return c
    if method in ("piecewise", "wide") or n == 2:
        if target <= locs[0]:
            i, j = 0, 1
        elif target >= locs[-1]:
            i, j = n - 2, n - 1
        else:
            j = next(k for k in range(1, n) if locs[k] >= target)
            i = j - 1
        u = (target - locs[i]) / (locs[j] - locs[i])
        c = [0.0] * n
        c[i], c[j] = 1 - u, u
        return c
    if method == "fit":
        mean = sum(locs) / n
        ss = sum((a - mean) ** 2 for a in locs)
        return [1 / n + (target - mean) * (a - mean) / ss for a in locs]
    raise ValueError(method)


def issue(glyph, code, severity, weight, detail, contour=None, point=None, **extra):
    d = {"glyph": glyph, "code": code, "severity": severity, "weight": weight,
         "contour": contour, "point": point, "detail": detail}
    d.update(extra)
    return d


# ---------------------------------------------------------------- curvature

def cubic_kappa(p0, p1, p2, p3, t):
    d1 = cubic_d1(p0, p1, p2, p3, t)
    d2 = cubic_d2(p0, p1, p2, p3, t)
    sp = norm(d1)
    return cross(d1, d2) / sp ** 3 if sp > 1e-9 else 0.0


# ---------------------------------------------------------------- merging

def _bern(u):
    mu = 1 - u
    return mu * mu * mu, 3 * mu * mu * u, 3 * mu * u * u, u * u * u


def fit_cubic_fixed_tangents(p0, t0, p3, t3, samples, iters=6):
    """Least-squares cubic from p0 to p3 whose handles leave p0 along unit t0 and
    arrive at p3 along unit t3 (t3 points from p3 back into the curve), fitted to
    `samples` (ordered points from p0 to p3). Keeping the end tangents means the
    neighbouring curves still join smoothly. Returns (curve, max_error) or None."""
    # chord-length parameters
    d = [0.0]
    for a, b in zip(samples, samples[1:]):
        d.append(d[-1] + dist(a, b))
    if d[-1] < 1e-9:
        return None
    us = [x / d[-1] for x in d]
    alpha = beta = d[-1] / 3
    for _ in range(iters):
        c11 = c12 = c22 = x1 = x2 = 0.0
        for u, s in zip(us, samples):
            b0, b1, b2, b3 = _bern(u)
            a1 = mul(t0, b1)
            a2 = mul(t3, b2)
            r = sub(s, add(mul(p0, b0 + b1), mul(p3, b2 + b3)))
            c11 += dot(a1, a1); c12 += dot(a1, a2); c22 += dot(a2, a2)
            x1 += dot(a1, r); x2 += dot(a2, r)
        det = c11 * c22 - c12 * c12
        if abs(det) < 1e-12:
            return None
        alpha = (x1 * c22 - x2 * c12) / det
        beta = (c11 * x2 - c12 * x1) / det
        if alpha <= 0 or beta <= 0:
            return None
        p1 = add(p0, mul(t0, alpha))
        p2 = add(p3, mul(t3, beta))
        # Newton step: move each parameter to the nearest point on the curve
        new = []
        for u, s in zip(us, samples):
            c = cubic_at(p0, p1, p2, p3, u)
            d1 = cubic_d1(p0, p1, p2, p3, u)
            d2 = cubic_d2(p0, p1, p2, p3, u)
            diff = sub(c, s)
            den = dot(d1, d1) + dot(diff, d2)
            new.append(min(1.0, max(0.0, u - dot(diff, d1) / den)) if abs(den) > 1e-12 else u)
        us = new
    p1 = add(p0, mul(t0, alpha))
    p2 = add(p3, mul(t3, beta))
    err = max(dist(cubic_at(p0, p1, p2, p3, u), s) for u, s in zip(us, samples))
    return (p0, p1, p2, p3), err


def merge_candidate(c, i, closed=True):
    """If on-curve point i joins two cubic segments, return the point indices
    (A, a1, a2, N, b1, b2, B), else None."""
    n = len(c)
    if c[i].type != "curve" or n < 7:
        return None
    idx = [(i + k) % n for k in range(-3, 4)] if closed else [i + k for k in range(-3, 4)]
    if not closed and (idx[0] < 0 or idx[-1] >= n):
        return None
    A, a1, a2, N, b1, b2, B = (c[k] for k in idx)
    if A.type is None or a1.type is not None or a2.type is not None or b1.type is not None or b2.type is not None or B.type != "curve":
        return None
    return idx


def segment_samples(c, i0, offs, i1, per=16):
    """Points along one segment of contour c (start included, end included)."""
    P0, P1 = xy(c[i0]), xy(c[i1])
    if len(offs) == 2:
        H1, H2 = xy(c[offs[0]]), xy(c[offs[1]])
        return [cubic_at(P0, H1, H2, P1, k / per) for k in range(per + 1)]
    return [P0, P1]


def try_merge(c, idx, tol, keep_extremes=True, samples_per=16, max_bend=5.0, samples=None):
    """Fit one cubic over the two segments around node idx[3] of contour c (a list of
    points with .x/.y). `samples` are the points the result must stay within tol of
    (the original outline over this span); by default the two current segments.
    Returns (h1, h2, err) or None when it doesn't fit."""
    A, a1, a2, N, b1, b2, B = (xy(c[k]) for k in idx)
    t0, t3 = sub(a1, A), sub(b2, B)
    if norm(t0) < 1e-6 or norm(t3) < 1e-6:
        return None
    t_in, t_out = sub(N, a2), sub(b1, N)
    if norm(t_in) < 1e-6 or norm(t_out) < 1e-6 or angle_deg(t_in, t_out) > max_bend:
        return None  # a real corner, not a smooth join with a rounding kink
    if keep_extremes:
        ang = math.degrees(math.atan2(t_out[1], t_out[0])) % 90
        if min(ang, 90 - ang) < 0.5:
            return None  # an extreme (axis-aligned tangent): keep it
    turn = angle_deg(t0, sub(B, b2))
    if turn > 120:
        return None
    pts = samples or ([cubic_at(A, a1, a2, N, k / samples_per) for k in range(samples_per)] +
                      [cubic_at(N, b1, b2, B, k / samples_per) for k in range(samples_per + 1)])
    fit = fit_cubic_fixed_tangents(A, unit(t0), B, unit(t3), pts)
    if fit is None:
        return None
    (p0, p1, p2, p3), err = fit
    if err > tol:
        return None
    # no handle past where the handles meet (curve would bend back), no new S-bends
    hit = line_intersection(p0, sub(p1, p0), p3, sub(p2, p3))
    if hit is not None and hit[0] > 0 and hit[1] > 0 and (hit[0] < 1 or hit[1] < 1):
        return None
    before = len(cubic_inflection_ts(A, a1, a2, N)) + len(cubic_inflection_ts(N, b1, b2, B))
    if cubic_kappa(A, a1, a2, N, 0.99) * cubic_kappa(N, b1, b2, B, 0.01) < 0:
        before += 1
    # never add an S-bend; removing a wobble (two S-bends become one or none) is fine
    after = len(cubic_inflection_ts(p0, p1, p2, p3))
    if after > 1 or after > before:
        return None
    return p1, p2, err


def fit_joint_fixed_tangents(cases, iters=6):
    """Fit one cubic per master over corresponding samples, with SHARED parameters.

    cases: per master (p0, t0, p3, t3, samples); every samples list has the same length
    and sample k corresponds across masters. Because the parameters are shared, the
    error at sample k of any blend of the masters (weights >= 0 summing to 1) is at
    most the largest per-master error, so interpolated weights stay within it too.
    Returns ([(p1, p2) per master], max correspondence error) or None."""
    n = len(cases[0][4])
    if any(len(c[4]) != n for c in cases) or n < 3:
        return None
    ref = cases[0][4]
    d = [0.0]
    for a, b in zip(ref, ref[1:]):
        d.append(d[-1] + dist(a, b))
    if d[-1] < 1e-9:
        return None
    us = [x / d[-1] for x in d]
    sols = None
    for it in range(iters + 1):
        sols = []
        for (p0, t0, p3, t3, S) in cases:
            c11 = c12 = c22 = x1 = x2 = 0.0
            for u, s in zip(us, S):
                b0, b1, b2, b3 = _bern(u)
                a1, a2 = mul(t0, b1), mul(t3, b2)
                r = sub(s, add(mul(p0, b0 + b1), mul(p3, b2 + b3)))
                c11 += dot(a1, a1); c12 += dot(a1, a2); c22 += dot(a2, a2)
                x1 += dot(a1, r); x2 += dot(a2, r)
            det = c11 * c22 - c12 * c12
            if abs(det) < 1e-12:
                return None
            al = (x1 * c22 - x2 * c12) / det
            be = (c11 * x2 - c12 * x1) / det
            if al <= 0 or be <= 0:
                return None
            sols.append((add(p0, mul(t0, al)), add(p3, mul(t3, be))))
        if it == iters:
            break
        # one Newton step per sample on the summed squared error over all masters
        new = []
        for k, u in enumerate(us):
            num = den = 0.0
            for (p0, t0, p3, t3, S), (p1, p2) in zip(cases, sols):
                c = cubic_at(p0, p1, p2, p3, u)
                d1 = cubic_d1(p0, p1, p2, p3, u)
                d2 = cubic_d2(p0, p1, p2, p3, u)
                diff = sub(c, S[k])
                num += dot(diff, d1)
                den += dot(d1, d1) + dot(diff, d2)
            new.append(min(1.0, max(0.0, u - num / den)) if abs(den) > 1e-12 else u)
        new[0], new[-1] = 0.0, 1.0
        us = new
    err = 0.0
    for (p0, t0, p3, t3, S), (p1, p2) in zip(cases, sols):
        for u, s in zip(us, S):
            err = max(err, dist(cubic_at(p0, p1, p2, p3, u), s))
    return sols, err


def merge_preconditions(c, idx, keep_extremes=True, max_bend=5.0):
    """The checks try_merge does before fitting. Returns (A, unit t0, B, unit t3) or None."""
    A, a1, a2, N, b1, b2, B = (xy(c[k]) for k in idx)
    t0, t3 = sub(a1, A), sub(b2, B)
    if norm(t0) < 1e-6 or norm(t3) < 1e-6:
        return None
    t_in, t_out = sub(N, a2), sub(b1, N)
    if norm(t_in) < 1e-6 or norm(t_out) < 1e-6 or angle_deg(t_in, t_out) > max_bend:
        return None
    if keep_extremes:
        ang = math.degrees(math.atan2(t_out[1], t_out[0])) % 90
        if min(ang, 90 - ang) < 0.5:
            return None
    if angle_deg(t0, sub(B, b2)) > 120:
        return None
    return A, unit(t0), B, unit(t3)


def merge_postconditions(c, idx, p1, p2):
    """No handle near or past where the handles meet (a margin, since rounding to whole
    units can push it over), no new S-bend, and no S-bend near either end."""
    A, a1, a2, N, b1, b2, B = (xy(c[k]) for k in idx)
    hit = line_intersection(A, sub(p1, A), B, sub(p2, B))
    if hit is not None and hit[0] > 0 and hit[1] > 0 and (hit[0] < 1.03 or hit[1] < 1.03):
        return False
    if any(t < 0.1 or t > 0.9 for t in cubic_inflection_ts(A, p1, p2, B)):
        return False
    before = len(cubic_inflection_ts(A, a1, a2, N)) + len(cubic_inflection_ts(N, b1, b2, B))
    if cubic_kappa(A, a1, a2, N, 0.99) * cubic_kappa(N, b1, b2, B, 0.01) < 0:
        before += 1
    after = len(cubic_inflection_ts(A, p1, p2, B))
    return not (after > 1 or after > before)
