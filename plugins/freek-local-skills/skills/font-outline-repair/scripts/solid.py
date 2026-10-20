#!/usr/bin/env python3
"""Glyphs filled black, large, side by side: how a reader sees them.

usage:
  solid.py OUT.png GLYPH LABEL=FONT.ufo[@X0,Y0,X1,Y1] ...

Each LABEL=UFO is one column (a version or a weight); @X0,Y0,X1,Y1 crops it to a
window in font units (a crossing, a join, a terminal), else the whole glyph is shown
from -60 to 760 units high. Judge evenness, pinches at crossings, lumps and whether
strokes line up across a crossing on these: point views and curvature combs hide them.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import ufoLib2  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import glyph_path  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 3 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    out, name = argv[0], argv[1]
    items = []
    for a in argv[2:]:
        label, _, rest = a.partition("=")
        path, _, box = rest.partition("@")
        items.append((label, path, [float(v) for v in box.split(",")] if box else None))
    fig, axes = plt.subplots(1, len(items), figsize=(7 * len(items), 9 if not items[0][2] else 6), squeeze=False)
    for ax, (label, path, box) in zip(axes[0], items):
        f = ufoLib2.Font.open(path)
        g = f[name]
        ax.add_patch(PathPatch(glyph_path(f, g), facecolor="black", edgecolor="none"))
        x0, y0, x1, y1 = box or (-20, -60, g.width + 20, 760)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.set_title(label, fontsize=14)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
