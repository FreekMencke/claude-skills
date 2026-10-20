#!/usr/bin/env python3
"""Draw glyphs across weights with nodes, handles and audit findings marked.

usage:
  render.py SOURCES... [--derived 100=Thin.ufo 900=Black.ufo] --glyphs a g s
            [--report report.json] [--out sheet.png] [--overlay] [--zoom G:C:P]

One row per glyph, one column per weight. Keep it to 4 glyphs per sheet so the
labels stay readable when the PNG is viewed. Grey fill, black outline, squares for
corner nodes, circles for smooth nodes, small hollow dots for handles. Points named in the report
(blocks and slows; --minor for all) are ringed in red with their code ("+N" when
there are more); a contour the report names as a whole is drawn in red.
--overlay adds a column with every weight's outline on top of each other and
each on-curve point's path through the weights, which shows uneven motion.
--zoom glyph:contour:point crops every cell around that point (--zoom-size, default
30% of the em). --comb adds curvature combs: the pink comb edge should run smoothly;
a step or dent in it is a kink, lump or flat spot that the outline alone hides.
Reads only; writes the PNG.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from fontTools.pens.basePen import BasePen  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402

RED = "#d62728"
BLUE = "#1f77b4"


class MplPen(BasePen):
    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.verts, self.codes = [], []

    def _moveTo(self, p):
        self.verts.append(p); self.codes.append(MPath.MOVETO)

    def _lineTo(self, p):
        self.verts.append(p); self.codes.append(MPath.LINETO)

    def _curveToOne(self, a, b, c):
        self.verts += [a, b, c]; self.codes += [MPath.CURVE4] * 3

    def _qCurveToOne(self, a, b):
        self.verts += [a, b]; self.codes += [MPath.CURVE3] * 2

    def _closePath(self):
        self.verts.append((0, 0)); self.codes.append(MPath.CLOSEPOLY)

    def path(self):
        return MPath(self.verts, self.codes) if self.verts else None


def glyph_path(font, glyph):
    pen = MplPen(font)
    glyph.draw(pen)
    return pen.path()


def contour_path(contour):
    pen = MplPen(None)
    contour.draw(pen)
    return pen.path()


def comb_scale(glyph, length):
    """Scale so the comb's typical tall teeth (90th percentile) are `length` units long."""
    ks = []
    for c in glyph.contours:
        pts = c.points
        for (i0, offs, i1, typ) in L.segments(pts, pts[0].type != "move"):
            if typ == "curve" and len(offs) == 2:
                P = [(pts[k].x, pts[k].y) for k in (i0, offs[0], offs[1], i1)]
                ks += [abs(L.cubic_kappa(*P, k / 12)) for k in range(13)]
    ks = sorted(k for k in ks if k > 0)
    return length / ks[int(0.9 * (len(ks) - 1))] if ks else 1.0


def draw_comb(ax, glyph, scale, max_len=None, color="#e377c2", alpha=1.0):
    """Curvature comb: a line normal to the outline, as long as the curvature, at
    every sample. Smooth curves give a smooth comb; a jump or a dent in the comb's
    edge is a kink, a lump or a flat spot."""
    for c in glyph.contours:
        pts = c.points
        closed = pts[0].type != "move"
        for (i0, offs, i1, typ) in L.segments(pts, closed):
            if typ != "curve" or len(offs) != 2:
                continue
            P = [(pts[k].x, pts[k].y) for k in (i0, offs[0], offs[1], i1)]
            tips = []
            for k in range(25):
                t = k / 24
                x, y = L.cubic_at(*P, t)
                d1 = L.cubic_d1(*P, t)
                d2 = L.cubic_d2(*P, t)
                sp = L.norm(d1)
                if sp < 1e-6:
                    continue
                kappa = L.cross(d1, d2) / sp ** 3
                nx, ny = -d1[1] / sp, d1[0] / sp
                ln = kappa * scale
                if max_len is not None:  # tiny tight curves would draw teeth across the whole view
                    ln = max(-max_len, min(max_len, ln))
                tx, ty = x - nx * ln, y - ny * ln
                ax.plot([x, tx], [y, ty], color=color, lw=0.4, alpha=alpha)
                tips.append((tx, ty))
            if tips:
                ax.plot([p[0] for p in tips], [p[1] for p in tips], color=color, lw=0.6, alpha=alpha)


def draw_cell(ax, font, glyph, marks, whole, zoom, upm, comb=None, zoom_size=0.15, comb_max=None):
    p = glyph_path(font, glyph)
    if p is not None:
        ax.add_patch(PathPatch(p, facecolor="#e6e6e6", edgecolor="none"))
    for ci, c in enumerate(glyph.contours):
        cp = contour_path(c)
        if cp is not None:
            ax.add_patch(PathPatch(cp, facecolor="none", edgecolor=RED if ci in whole else "black", lw=1.6 if ci in whole else 0.8))
        pts = c.points
        n = len(pts)
        for i, pt in enumerate(pts):
            if pt.type is None:
                for k in ((i - 1) % n, (i + 1) % n):
                    if pts[k].type is not None:
                        ax.plot([pt.x, pts[k].x], [pt.y, pts[k].y], color=BLUE, lw=0.6)
        for i, pt in enumerate(pts):
            if pt.type is None:
                ax.plot(pt.x, pt.y, "o", ms=2.5, mfc="white", mec=BLUE, mew=0.7)
            else:
                ax.plot(pt.x, pt.y, "o" if pt.smooth else "s", ms=3.2, color="black")
        for i in range(n):
            if (ci, i) in marks:
                ax.plot(pts[i].x, pts[i].y, "o", ms=11, mfc="none", mec=RED, mew=1.4)
                codes = sorted(marks[(ci, i)])
                label = codes[0] + (f" +{len(codes) - 1}" if len(codes) > 1 else "")
                ax.annotate(label, (pts[i].x, pts[i].y), xytext=(6, 6),
                            textcoords="offset points", fontsize=6, color=RED)
    if comb:
        draw_comb(ax, glyph, comb, comb_max)
    ax.set_aspect("equal")
    if zoom:
        x, y = zoom
        r = zoom_size * upm / 2
        ax.set_xlim(x - r, x + r)
        ax.set_ylim(y - r, y + r)
    else:
        info = font.info
        ax.set_xlim(-0.05 * upm, max(glyph.width, 0.3 * upm) + 0.05 * upm)
        ax.set_ylim((info.descender or -0.25 * upm) - 0.05 * upm, (info.ascender or 0.8 * upm) + 0.05 * upm)
    ax.axhline(0, color="#bbbbbb", lw=0.4)
    ax.set_xticks([]); ax.set_yticks([])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--derived", nargs="*", default=[])
    ap.add_argument("--glyphs", nargs="+", help="glyphs to draw (not needed with --zoom)")
    ap.add_argument("--report")
    ap.add_argument("--out", default="sheet.png")
    ap.add_argument("--overlay", action="store_true")
    ap.add_argument("--zoom", help="glyph:contour:point to crop around")
    ap.add_argument("--cell", type=float, default=2.6, help="cell size in inches")
    ap.add_argument("--comb", nargs="?", const=-1, type=float,
                    help="draw curvature combs; optional scale (default: typical teeth 6%% of the view)")
    ap.add_argument("--zoom-size", type=float, default=0.3, help="width of a --zoom crop as a fraction of the em (default 0.3)")
    ap.add_argument("--minor", action="store_true", help="also mark minor findings (default: blocks and slows only)")
    opt = ap.parse_args(argv)

    import ufoLib2
    masters, _ = L.load_sources(opt.sources)
    cols = [(m.label, m.weight, m.font, False) for m in masters]
    for spec in opt.derived:
        w, p = spec.split("=", 1)
        cols.append((w, float(w), ufoLib2.Font.open(p), True))
    cols.sort(key=lambda c: c[1])
    upm = masters[0].font.info.unitsPerEm or 1000

    marks = defaultdict(lambda: defaultdict(set))   # (glyph, weight) -> (contour, point) -> codes
    whole = defaultdict(set)                        # (glyph, weight) -> contours
    if opt.report:
        for i in json.load(open(opt.report))["issues"]:
            if i["severity"] == "minor" and not opt.minor:
                continue
            weights = [c[0] for c in cols] if i["weight"] in ("all", None) else i["weight"].split(",")
            for w in weights:
                if i["contour"] is None:
                    continue
                if i["point"] is None:
                    whole[(i["glyph"], w)].add(i["contour"])
                else:
                    marks[(i["glyph"], w)][(i["contour"], i["point"])].add(i["code"])

    zoom_pt = None
    if not opt.glyphs and not opt.zoom:
        ap.error("give --glyphs or --zoom")
    if opt.zoom:
        zg, zc, zp = opt.zoom.rsplit(":", 2)
        opt.glyphs = [zg]
        zoom_pt = (int(zc), int(zp))

    ncol = len(cols) + (1 if opt.overlay else 0)
    fig, axes = plt.subplots(len(opt.glyphs), ncol, figsize=(opt.cell * ncol, opt.cell * 1.15 * len(opt.glyphs)), squeeze=False)
    for r, name in enumerate(opt.glyphs):
        for c, (label, w, font, is_derived) in enumerate(cols):
            ax = axes[r][c]
            if name not in font:
                ax.set_axis_off()
                continue
            g = font[name]
            zoom = None
            if zoom_pt and zoom_pt[0] < len(g.contours) and zoom_pt[1] < len(g.contours[zoom_pt[0]].points):
                pt = g.contours[zoom_pt[0]].points[zoom_pt[1]]
                zoom = (pt.x, pt.y)
            comb = None
            if opt.comb is not None:
                comb = opt.comb if opt.comb > 0 else comb_scale(g, 0.06 * upm * (opt.zoom_size if zoom else 1.0))
            draw_cell(ax, font, g, marks[(name, label)], whole[(name, label)], zoom, upm, comb, opt.zoom_size,
                      comb_max=0.15 * upm * (opt.zoom_size if zoom else 1.0))
            ax.set_title(f"{name}  {label}{' (derived)' if is_derived else ''}", fontsize=8, color=RED if is_derived else "black")
        if opt.overlay:
            ax = axes[r][-1]
            fonts = [(label, font) for label, w, font, _ in cols if name in font]
            cmap = plt.get_cmap("viridis")
            for k, (label, font) in enumerate(fonts):
                p = glyph_path(font, font[name])
                if p is not None:
                    ax.add_patch(PathPatch(p, facecolor="none", edgecolor=cmap(k / max(len(fonts) - 1, 1)), lw=0.7))
            same = all(len(f[name].contours) == len(fonts[0][1][name].contours) and
                       all(len(a.points) == len(b.points) for a, b in zip(f[name].contours, fonts[0][1][name].contours)) for _, f in fonts)
            if same:
                for ci, contour in enumerate(fonts[0][1][name].contours):
                    for pi, pt in enumerate(contour.points):
                        if pt.type is None:
                            continue
                        xs = [f[name].contours[ci].points[pi].x for _, f in fonts]
                        ys = [f[name].contours[ci].points[pi].y for _, f in fonts]
                        ax.plot(xs, ys, "-", color="#888888", lw=0.5)
                        ax.plot(xs, ys, ".", color="#555555", ms=1.5)
            ax.set_aspect("equal")
            info = fonts[0][1].info
            ax.set_xlim(-0.05 * upm, max(f[name].width for _, f in fonts) + 0.05 * upm)
            ax.set_ylim((info.descender or -0.25 * upm) - 0.05 * upm, (info.ascender or 0.8 * upm) + 0.05 * upm)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"{name}  overlay {fonts[0][0]}→{fonts[-1][0]}", fontsize=8)
    fig.tight_layout()
    fig.savefig(opt.out, dpi=110)
    print(opt.out)


if __name__ == "__main__":
    sys.exit(main())
