#!/usr/bin/env python3
"""Pairs in built fonts: every pair of --chars shaped with HarfBuzz (kerning on, and the
case feature for capital brackets), its clearance measured on the font's own outlines as
kern_floor.py measures it. Per static weight: the pairs that touch, and beyond the
reference weight the pairs closer than min(--floor, at the reference). Reads only.

usage:
  pairs.py BUILD_DIR [--ref 700] [--side above|below] [--floor 10] [--chars "..."]

The static .otf files below BUILD_DIR, ordered by usWeightClass. Characters the font
lacks are skipped (HarfBuzz gives .notdef). Compare two builds by running it on each.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kern_floor import CHARS, clearance, silhouette  # noqa: E402


def measure(path, chars):
    """{(text, case): clearance} for every pair, shaped as a reader's app would."""
    tt = TTFont(path); gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    cache, out = {}, {}
    caps = [c for c in chars if not c.islower()]
    for feats, cs in (({"kern": True}, chars), ({"kern": True, "case": True}, caps)):
        for l in cs:
            for r in cs:
                buf = hb.Buffer(); buf.add_str(l + r); buf.guess_segment_properties()
                hb.shape(font, buf, feats)
                if len(buf.glyph_infos) != 2:
                    continue
                gl, gr = (order[i.codepoint] for i in buf.glyph_infos)
                if ".notdef" in (gl, gr):
                    continue            # not in the font
                if "case" in feats and not (gl.endswith(".case") or gr.endswith(".case")):
                    continue            # measured already without the feature
                for n in (gl, gr):
                    if n not in cache:
                        pen = DecomposingRecordingPen(gs); gs[n].draw(pen)
                        cache[n] = silhouette(pen.value)
                out[(l + r, "case" in feats)] = float(clearance(cache[gl][1], cache[gr][0],
                                                                buf.glyph_positions[0].x_advance))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build")
    ap.add_argument("--ref", type=int, default=700, help="weight class of the drawn master to compare with")
    ap.add_argument("--side", choices=("above", "below"), default="above")
    ap.add_argument("--floor", type=float, default=10)
    ap.add_argument("--chars", default=CHARS)
    a = ap.parse_args(argv)
    fonts = sorted(Path(a.build).rglob("*.otf"), key=lambda p: TTFont(p)["OS/2"].usWeightClass)
    res = {TTFont(p)["OS/2"].usWeightClass: measure(p, a.chars) for p in fonts}
    if a.ref not in res:
        sys.exit(f"no static font of weight {a.ref} under {a.build}")
    ref = res[a.ref]
    beyond = (lambda w: w > a.ref) if a.side == "above" else (lambda w: w < a.ref)
    print(f"weight  touching (<0)   closer than min({a.floor:g}, {a.ref})")
    for wt, m in res.items():
        touch = sorted(k[0] for k, v in m.items() if v < -0.5)
        print(f"{wt:6}  {len(touch):4} {' '.join(touch[:14])}{' ...' if len(touch) > 14 else ''}")
        if beyond(wt):
            close = sorted(k[0] for k, v in m.items() if k in ref and v < min(a.floor, ref[k]) - 0.5)
            print(f"{'':6}  {len(close):4} closer: {' '.join(close[:20])}{' ...' if len(close) > 20 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
