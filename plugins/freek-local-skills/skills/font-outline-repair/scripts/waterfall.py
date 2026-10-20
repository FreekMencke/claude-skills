#!/usr/bin/env python3
"""A waterfall of every static weight in a build, shaped with HarfBuzz (kerning on),
optionally side by side with a previous build.

usage:
  waterfall.py AFTER_DIR [--before BEFORE_DIR] --out waterfall.png
               [--text "Hamburgefonstiv 0123456789"] [--text2 "& @ $ ? v w 4"] [--ext otf] [--dpi 150]
               [--labels "before" "after"]

Fonts are the static .otf (or --ext ttf) files below each folder, ordered by weight
class and matched by file name. Read it at text size: a glyph that looks wrong there
looks wrong to readers. Needs uharfbuzz (pip install uharfbuzz). Writes the PNG only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from fontTools.pens.basePen import BasePen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

try:
    import uharfbuzz as hb
except ImportError:
    sys.exit("waterfall.py needs uharfbuzz: pip install uharfbuzz")


class MplPen(BasePen):
    def __init__(self, gs):
        super().__init__(gs)
        self.v, self.c = [], []
        self.dx = self.dy = 0.0
        self.k = 1.0

    def t(self, p):
        return (self.dx + p[0] * self.k, self.dy + p[1] * self.k)

    def _moveTo(self, p):
        self.v.append(self.t(p))
        self.c.append(MPath.MOVETO)

    def _lineTo(self, p):
        self.v.append(self.t(p))
        self.c.append(MPath.LINETO)

    def _curveToOne(self, a, b, p):
        self.v += [self.t(a), self.t(b), self.t(p)]
        self.c += [MPath.CURVE4] * 3

    def _qCurveToOne(self, a, p):
        self.v += [self.t(a), self.t(p)]
        self.c += [MPath.CURVE3] * 2

    def _closePath(self):
        self.v.append((0, 0))
        self.c.append(MPath.CLOSEPOLY)


def draw_line(ax, path, text, x, y, size):
    f = TTFont(path)
    gs, order, upm = f.getGlyphSet(), f.getGlyphOrder(), f["head"].unitsPerEm
    face = hb.Face(hb.Blob.from_file_path(str(path)))
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    pen = MplPen(gs)
    pen.k = size / upm
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen.dx, pen.dy = x + pos.x_offset * pen.k, y + pos.y_offset * pen.k
        gs[order[info.codepoint]].draw(pen)
        x += pos.x_advance * pen.k
    if pen.v:
        ax.add_patch(PathPatch(MPath(pen.v, pen.c), facecolor="black", edgecolor="none"))


def statics(d, ext):
    out = []
    for p in Path(d).rglob(f"*.{ext}"):
        f = TTFont(p, lazy=True)
        if "fvar" not in f:
            out.append((f["OS/2"].usWeightClass, p.name, p))
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("after")
    ap.add_argument("--before")
    ap.add_argument("--out", required=True)
    ap.add_argument("--text", default="Hamburgefonstiv 0123456789")
    ap.add_argument("--text2", default="& @ $ ¢ € ® ™ % ?¿ ð v w 4 < > , ; S")
    ap.add_argument("--ext", default="otf")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--labels", nargs="+", help="column headings (default: the folder names)")
    opt = ap.parse_args(argv)
    rows = statics(opt.after, opt.ext)
    if not rows:
        sys.exit(f"no static .{opt.ext} fonts under {opt.after}")
    old = {name: p for _, name, p in statics(opt.before, opt.ext)} if opt.before else {}
    cols = 2 if opt.before else 1
    W, size, gap = 1000 * cols, 44, 128
    top = len(rows) * gap + 150
    fig = plt.figure(figsize=(W / 100, top / 100))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, top)
    ax.axis("off")
    heads = opt.labels or ([f"before: {opt.before}", f"after: {opt.after}"] if opt.before else [str(opt.after)])
    for c, h in enumerate(heads):
        ax.text(40 + c * 1000, top - 40, h, fontsize=12, va="center")
    if cols == 2:
        ax.plot([1000, 1000], [10, top - 70], color="#cccccc", lw=1)
    for r, (cls, name, p) in enumerate(rows):
        y = top - 120 - r * gap
        ax.text(40, y + 62, f"{cls}  {name}", fontsize=8, color="#777777")
        for c, path in enumerate([old.get(name), p] if cols == 2 else [p]):
            if path is None:
                continue
            x0 = 40 + c * 1000
            draw_line(ax, path, opt.text, x0, y + 12, size)
            draw_line(ax, path, opt.text2, x0, y - 40, size * 0.9)
    fig.savefig(opt.out, dpi=opt.dpi)
    print(f"{opt.out}: {len(rows)} weights")
    return 0


if __name__ == "__main__":
    sys.exit(main())
