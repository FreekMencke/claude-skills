#!/usr/bin/env python3
"""Check a built family: static fonts against a previous build, the variable font's
named instances against the statics, and the stem of each weight.

usage:
  checkbuild.py AFTER_DIR [--before BEFORE_DIR] [--stem-glyph n]

AFTER_DIR (and BEFORE_DIR) hold the build: static .otf/.ttf files anywhere below,
and a variable .ttf (one with an fvar table). Static fonts are matched by file name.
It reports:
  per static   weight class, fsSelection, names 1/2/16/17/6, glyph count and cmap
               size; with --before, glyph order, cmap, names, OS/2 and advance
               widths compared with the same file in the previous build
  stems        the stem of --stem-glyph at half the x-height in each static, with the
               ratio to the weight before it: the weight progression
  variable     axes, named instances, STAT and avar; each named instance against the
               static TTF of the same style: advance widths, and how far the static's
               outline lies from the instance's (densely sampled, both drawn with
               overlaps, so a boolean comparison isn't needed: those report large
               differences between outlines that agree to within a unit)
A width can differ by 1 unit at a weight exactly halfway between two masters, where
every value ends in .5 and the two builds round it differently. Reads only. Exits 1
when it finds problems other than those.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from scipy.spatial import cKDTree


class SamplePen(BasePen):
    """Points every half unit along the outline, curves flattened."""

    def __init__(self, gs):
        super().__init__(gs)
        self.pts, self.cur, self.start = [], None, None

    def _seg(self, a, b):
        n = max(1, int(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 / 0.5))
        self.pts += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]

    def _moveTo(self, p):
        self.cur = self.start = p

    def _lineTo(self, p):
        self._seg(self.cur, p)
        self.cur = p

    def _curveToOne(self, p1, p2, p3):
        p0, prev = self.cur, self.cur
        for k in range(1, 33):
            t = k / 32
            u = 1 - t
            q = tuple(u ** 3 * p0[i] + 3 * u * u * t * p1[i] + 3 * u * t * t * p2[i] + t ** 3 * p3[i] for i in (0, 1))
            self._seg(prev, q)
            prev = q
        self.cur = p3

    def _qCurveToOne(self, p1, p2):
        p0, prev = self.cur, self.cur
        for k in range(1, 33):
            t = k / 32
            u = 1 - t
            q = tuple(u * u * p0[i] + 2 * u * t * p1[i] + t * t * p2[i] for i in (0, 1))
            self._seg(prev, q)
            prev = q
        self.cur = p2

    def _closePath(self):
        if self.cur and self.start and self.cur != self.start:
            self._seg(self.cur, self.start)
        self.cur = None


def samples(font, g):
    gs = font.getGlyphSet()
    pen = SamplePen(gs)
    gs[g].draw(pen)
    return pen.pts


def stem(font, g):
    """Width of the first ink run at half the x-height."""
    if g not in font.getGlyphOrder():
        return None
    gs = font.getGlyphSet()
    y = (getattr(font["OS/2"], "sxHeight", 0) or font["head"].unitsPerEm * 0.5) / 2
    w = font["hmtx"][g][0]
    run, x = None, -50.0
    while x <= w + 50:
        pen = PointInsidePen(gs, (x, y))
        gs[g].draw(pen)
        if pen.getResult():
            run = [x, x] if run is None else [run[0], x]
        elif run is not None:
            return run[1] - run[0] + 0.25
        x += 0.25
    return None


def name(f, i):
    return f["name"].getDebugName(i)


def fonts_in(d):
    out = {}
    for p in sorted(Path(d).rglob("*")):
        if p.suffix.lower() in (".otf", ".ttf"):
            f = TTFont(p, lazy=True)
            out[p.name] = (p, "fvar" in f)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("after")
    ap.add_argument("--before")
    ap.add_argument("--stem-glyph", default="n")
    opt = ap.parse_args(argv)

    after = fonts_in(opt.after)
    before = fonts_in(opt.before) if opt.before else {}
    statics = {k: p for k, (p, var) in after.items() if not var}
    variables = [p for p, var in after.values() if var]
    probs, rounding = [], []

    rows = []
    for fname, p in statics.items():
        b = TTFont(p)
        rows.append((b["OS/2"].usWeightClass, p.suffix, fname, b))
    rows.sort()
    print(f"{'file':28s} {'class':>5s} {'fsSel':>6s} {'glyphs':>6s} {'cmap':>5s}  names 1 / 2 / 16 / 17 / 6   widths changed")
    for cls, suf, fname, b in rows:
        changed = ""
        if fname in before and not before[fname][1]:
            a = TTFont(before[fname][0])
            if a.getGlyphOrder() != b.getGlyphOrder():
                probs.append(f"{fname}: glyph order differs from the previous build")
            if a.getBestCmap() != b.getBestCmap():
                probs.append(f"{fname}: cmap differs from the previous build")
            for i in (1, 2, 4, 6, 16, 17):
                if name(a, i) != name(b, i):
                    probs.append(f"{fname}: name {i} {name(a, i)!r} -> {name(b, i)!r}")
            if (a["OS/2"].usWeightClass, a["OS/2"].fsSelection) != (cls, b["OS/2"].fsSelection):
                probs.append(f"{fname}: OS/2 weight class or fsSelection changed")
            wa, wb = a["hmtx"].metrics, b["hmtx"].metrics
            ch = [(g, wa[g][0], wb[g][0]) for g in wa if g in wb and wa[g][0] != wb[g][0]]
            if ch:
                g, x, y = max(ch, key=lambda c: abs(c[1] - c[2]))
                changed = f"{len(ch)} (most: {g} {x} -> {y})"
            else:
                changed = "0"
        elif before:
            changed = "(not in the previous build)"
        print(f"{fname:28s} {cls:5d} {b['OS/2'].fsSelection:#06x} {len(b.getGlyphOrder()):6d} {len(b.getBestCmap()):5d}  "
              f"{name(b, 1)} / {name(b, 2)} / {name(b, 16)} / {name(b, 17)} / {name(b, 6)}   {changed}")

    print(f"\nstems ({opt.stem_glyph} at half the x-height):")
    prev = None
    for cls, suf, fname, b in rows:
        if suf != rows[0][1]:
            continue
        s = stem(b, opt.stem_glyph)
        if s is None:
            continue
        ratio = f"x{s / prev:.2f}" if prev else ""
        print(f"  {cls:4d} {fname:28s} {s:6.1f} {ratio}")
        prev = s

    for vp in variables:
        v = TTFont(vp)
        axes = ", ".join(f"{a.axisTag} {a.minValue:g}-{a.maxValue:g} (default {a.defaultValue:g})" for a in v["fvar"].axes)
        insts = v["fvar"].instances
        print(f"\nvariable {vp.name}: {axes}; {len(insts)} named instances; "
              f"{'STAT' if 'STAT' in v else 'no STAT'}; {'avar' if 'avar' in v else 'no avar'}")
        if "STAT" not in v:
            probs.append(f"{vp.name}: no STAT table")
        worst = (0.0, None)
        by_style = {}
        for cls, suf, fname, b in rows:
            if suf == ".ttf":
                by_style[(name(b, 17) or name(b, 2))] = (fname, b)
        for inst in insts:
            style = name(v, inst.subfamilyNameID)
            if style not in by_style:
                print(f"  {style}: no static TTF of that style to compare with")
                continue
            fname, st = by_style[style]
            vi = instantiateVariableFont(TTFont(vp), dict(inst.coordinates), updateFontNames=False)
            far = 0
            for g in st.getGlyphOrder():
                if g not in vi.getGlyphOrder():
                    probs.append(f"{vp.name} {style}: {g} missing")
                    continue
                if vi["hmtx"][g][0] != st["hmtx"][g][0]:
                    d = abs(vi["hmtx"][g][0] - st["hmtx"][g][0])
                    (rounding if d <= 1 else probs).append(f"{style} {g}: width {vi['hmtx'][g][0]} in the variable font, {st['hmtx'][g][0]} static")
                a, b2 = samples(vi, g), samples(st, g)
                if a and b2:
                    # the static has overlaps removed: every point of its outline should lie
                    # on the variable font's outline, not the other way round
                    d = float(cKDTree(a).query(b2)[0].max())
                    if d > worst[0]:
                        worst = (d, f"{style} {g}")
                    if d > 2.0:
                        far += 1
            if far:
                probs.append(f"{vp.name} {style}: {far} glyphs whose static outline is over 2 units from the instance's")
        print(f"  instances vs statics: outlines at most {worst[0]:.2f} units apart ({worst[1]})")
        if rounding:
            by = collections.Counter(r.split()[0] for r in rounding)
            print(f"  widths 1 unit apart (rounding at a weight halfway between masters): {dict(by)}")

    print("\nProblems:" if probs else "\nNo problems.")
    for p in probs[:50]:
        print("  " + p)
    if len(probs) > 50:
        print(f"  … {len(probs) - 50} more")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
