#!/usr/bin/env python3
"""Keep a derived weight's pairs from running into each other: no pair at the derived
weight comes closer than --floor units, or than at the reference master where that is
closer, and none at the weights between them either.

From a drawn Bold to an extrapolated Black every gap between two letters shrinks by
about the same amount. Letters that reach past their sidebearings (T, V, W, Y, L, f, j)
nearly touch in Bold already, so at Black they run into each other although none of
those pairs is kerned (on one family: TT, WT, WW, LA, gj; 66 touching pairs in its released Black).
A pair that touches in the reference master stays as it is there. derive.py extrapolates
kerning from the drawn masters only, so room a build pipeline gave the derived weight
(brackets beside capitals) is lost too; this puts it back.

usage:
  kern_floor.py --ref 700=Bold.ufo --derived 900=Black.ufo [--others Thin.ufo Light.ufo ...]
                [--floor 10] [--steps 0.25 0.5 0.75 1] [--chars "..."] [--write]

Clearance is the shortest distance between the two glyphs' edges, set side by side with
kerning (negative where they overlap in a row), over every pair of --chars (default:
Latin-1 letters, figures, punctuation) and their bracket .case forms, which meet
capitals, figures and punctuation only. The outlines change shape between the reference
and the derived weight, so a pair can come closer in between than at either end: the
rule holds at every --steps fraction of the way, and the derived value opens further
where a weight in between needs it. Each opened pair goes into every UFO given as a
glyph-pair exception, the derived one opened and the others at their current value, so
the static instances and the variable font interpolate it. Run it after every new
derivation and after any other kerning step; it only adds what is missing. Static
instances round every point, so a pair can measure a unit or two under the floor there
(check the build with pairs.py).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ufoLib.kerning import lookupKerningValue
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fontlib import flatten_recording  # noqa: E402

CHARS = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
         "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿıŒœŸ"
         "'\"()[]{}!?¡¿.,:;-/&@«»")
RES, REACH = 2, 60            # units per row; rows this far apart still count (diagonals)
X0, Y0, W, H = -500, -500, 2200, 1700


def recording(font, name):
    pen = DecomposingRecordingPen(font); font[name].draw(pen)
    return pen.value


def blend(a, b, t):
    """The outline at fraction t from recording a to b (compatible masters)."""
    return [(op, tuple((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])) for p, q in zip(pa, pb)))
            for (op, pa), (_, pb) in zip(a, b)]


def silhouette(value):
    """Per row: leftmost and rightmost ink (counters don't matter for these)."""
    im = Image.new("1", (W // RES, H // RES), 0); d = ImageDraw.Draw(im)
    for p in flatten_recording(value, 16):
        if len(p) > 2:
            d.polygon([((x - X0) / RES, (Y0 + H - y) / RES) for x, y in p], fill=1)
    ink = np.asarray(im, bool); has = ink.any(axis=1)
    left = np.where(has, ink.argmax(axis=1) * RES + X0, np.inf)
    right = np.where(has, (ink.shape[1] - 1 - ink[:, ::-1].argmax(axis=1)) * RES + X0, -np.inf)
    return left.astype(float), right.astype(float)


def clearance(right, lefts, offset):
    """Shortest distance from one glyph's right edge to the left edges of others set
    `offset` further right; negative is overlap within a row."""
    offset = np.asarray(offset, float)[..., None]
    best = None
    for s in range(-(REACH // RES), REACH // RES + 1):
        shifted = np.roll(lefts, s, axis=-1)
        if s > 0: shifted[..., :s] = np.inf
        if s < 0: shifted[..., s:] = np.inf
        gap = shifted + offset - right
        d = gap.min(axis=-1) if s == 0 else np.sqrt(np.maximum(gap, 0) ** 2 + (s * RES) ** 2).min(axis=-1)
        best = d if best is None else np.minimum(best, d)
    return best


def kern(font, l, r):
    return lookupKerningValue((l, r), font.kerning, font.groups)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True, help="LABEL=UFO, the drawn master next to the derived weight")
    ap.add_argument("--derived", required=True, help="LABEL=UFO, the derived weight")
    ap.add_argument("--others", nargs="*", default=[], help="the other masters' UFOs, to carry the pairs")
    ap.add_argument("--floor", type=float, default=10)
    ap.add_argument("--steps", type=float, nargs="+", default=[0.25, 0.5, 0.75, 1.0])
    ap.add_argument("--chars", default=CHARS)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    ref_path, der_path = a.ref.split("=", 1)[1], a.derived.split("=", 1)[1]
    fr, fd = ufoLib2.Font.open(ref_path), ufoLib2.Font.open(der_path)
    others = [ufoLib2.Font.open(p.split("=", 1)[-1]) for p in a.others]
    steps = tuple(sorted(set(a.steps) | {1.0}))

    cmap = {u: g.name for g in fd for u in g.unicodes}
    names = [cmap[ord(c)] for c in a.chars if ord(c) in cmap]
    lower = {cmap[ord(c)] for c in a.chars if c.islower() and ord(c) in cmap}
    case = [n + ".case" for n in names if n + ".case" in fd and n + ".case" in fr]
    names += case
    skip = np.array([[(l in case and r in lower) or (r in case and l in lower) for r in names] for l in names])

    rec = {n: (recording(fr, n), recording(fd, n)) for n in names}
    off0 = np.array([[fr[l].width + kern(fr, l, r) for r in names] for l in names], float)
    off1 = np.array([[fd[l].width + kern(fd, l, r) for r in names] for l in names], float)
    sil, clr = {}, {}
    for t in (0.0,) + steps:
        S = [silhouette(blend(*rec[n], t)) for n in names]
        sil[t] = (np.stack([x[0] for x in S]), np.stack([x[1] for x in S]))
        o = off0 + t * (off1 - off0)       # widths and kerning interpolate linearly
        clr[t] = np.stack([clearance(sil[t][1][i], sil[t][0], o[i]) for i in range(len(names))])

    target = np.minimum(a.floor, clr[0.0])
    low = np.stack([clr[t] < target - 0.5 for t in steps]).any(axis=0) & ~skip
    opened = {}
    for i, j in zip(*np.nonzero(low)):
        def short(add):                    # how far the closest weight falls short
            o = off0[i, j] + np.array(steps) * (off1[i, j] + add - off0[i, j])
            return max(target[i, j] - clearance(sil[t][1][i], sil[t][0][j], o[k]) for k, t in enumerate(steps))
        add = 0
        while short(add) > 0.5:            # a diagonal approach opens slower than the offset
            add += max(1, math.floor(short(add)))
        worst = min(steps, key=lambda t: clr[t][i, j])
        opened[(names[i], names[j])] = (clr[0.0][i, j], clr[1.0][i, j], worst, clr[worst][i, j], add)

    label = {cmap[ord(c)]: c for c in a.chars if ord(c) in cmap}
    lab = lambda n: label.get(n, n)
    print(f"{len(opened)} pairs closer than min({a.floor:g}, the reference) at the derived weight or between")
    print("  pair      ref  derived  closest (fraction)  +kern")
    for (l, r), (cr, cd, wt, cw, add) in sorted(opened.items(), key=lambda kv: -kv[1][4]):
        print(f"  {lab(l)}{lab(r):<6} {cr:6.1f} {cd:8.1f} {cw:8.1f} ({wt:g})  +{add}")
    if a.write and opened:
        for f in [fr, fd, *others]:
            for (l, r), (*_, add) in opened.items():
                f.kerning[(l, r)] = kern(f, l, r) + (add if f is fd else 0)
            f.save()
        print("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
