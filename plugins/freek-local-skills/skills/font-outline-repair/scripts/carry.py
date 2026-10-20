#!/usr/bin/env python3
"""Carry over the glyphs a derived Thin or Black can't get right from an earlier
version of that weight, one the user trusts (drawn or corrected by a person).

Ask first how that version was made: an earlier automated attempt holds no designer
decisions, only its own patches. For thin strokes and inside corners use contrast.py.

usage:
  carry.py --masters 300=L.ufo 400=R.ufo 700=B.ufo --derived 100=Thin.ufo 900=Black.ufo
           --old 100=old/Thin.ufo 900=old/Black.ufo [--before 300=base/L.ufo ...]
           --out-dir carried/ [--glyphs a b] [--keep-old ae@900 eth] [--ref 300] [--tol 1.0]

Some glyphs block at a derived extreme whatever the method, or come out worse than
an earlier version in ways that don't block: a crossing bar slid into the
stroke it crosses (crossing-shrink), ink past the side bearings (overhang), a tapered
stroke extrapolated to a hairline (thin-stroke) or thinner than the weight
(stroke-ratio), a gap or separate parts closing up (counter-tight, parts-close), a
handle pointing backward (handle-backward). Where two edges meet at a
shallow angle (the crotch of v, the apex of the counter in 4) or a handle that shrinks
with weight passes zero, straight-line extrapolation overshoots, and no point-moving
fix gives a good shape: a designer has to decide. When an earlier Thin/Black exists in
which someone already made those decisions, this carries them over:

1. audit the derived weights; carried are the glyphs with blocks, or with more
   findings of those kinds than the old glyph (or the --glyphs given)
2. for those glyphs, put the --before masters (the masters as they were when the old
   extremes were made, so their points match; default: --masters) together with the
   old extremes and run fix.py merge over all of them, so the point reduction holds in
   every one and they stay compatible
3. derive those glyphs again from the merged masters
4. per glyph and weight, keep the new derivation when it has no such findings (or
   fewer than the old glyph, blocks counted first), otherwise the old glyph

--keep-old glyph@weight (or glyph, for every weight) carries that glyph and keeps the
old version whatever the checks say: for what a review of the overlays finds and no
check sees (a part covering a counter that belongs to a component, a terminal or bar
placed better by hand).

Writes all masters and extremes to --out-dir (only the carried glyphs differ) and
carry.json there. Other fixes made to the masters for these glyphs after --before
(collinear, repredict) are undone by step 2: run them again, then audit.
Reads the inputs only.
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ufoLib2

HERE = Path(__file__).resolve().parent
PY = sys.executable


def pairs(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        if not v:
            sys.exit(f"expected weight=path.ufo, got {it}")
        out[k] = Path(v)
    return out


def run(*args, quiet=True):
    r = subprocess.run([PY, *map(str, args)], capture_output=True, text=True)
    if r.returncode not in (0, 1):  # audit exits 1 when it finds blocks
        sys.exit(f"{Path(str(args[0])).name} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


REGRESSIONS = ("crossing-shrink", "overhang", "thin-stroke", "counter-tight", "stroke-ratio", "parts-close",
               "handle-backward")


def blocks(masters, derived, ref, glyphs=None):
    """{(glyph, weight): (blocks, crossing-shrink + overhang findings)} in the derived weights."""
    with tempfile.TemporaryDirectory() as t:
        js = Path(t) / "a.json"
        args = [HERE / "audit.py", *[f"{k}={v}" for k, v in masters.items()], "--derived",
                *[f"{k}={v}" for k, v in derived.items()], "--ref", ref, "--no-merge-count", "--json", js]
        if glyphs:
            args += ["--glyphs", *glyphs]
        run(*args)
        issues = json.loads(js.read_text())["issues"]
    b, r = collections.Counter(), collections.Counter()
    for f in issues:
        if str(f["weight"]) in derived:
            if f["severity"] == "blocks":
                b[(f["glyph"], str(f["weight"]))] += 1
            elif f["code"] in REGRESSIONS:
                r[(f["glyph"], str(f["weight"]))] += 1
    return collections.defaultdict(lambda: (0, 0), {k: (b[k], r[k]) for k in set(b) | set(r)})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--masters", nargs="+", required=True)
    ap.add_argument("--derived", nargs="+", required=True)
    ap.add_argument("--old", nargs="+", required=True)
    ap.add_argument("--before", nargs="*")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--keep-old", nargs="*", default=[], help="glyph@weight or glyph: carry it and keep the old version")
    ap.add_argument("--ref")
    ap.add_argument("--tol", type=float, default=1.0)
    opt = ap.parse_args(argv)

    masters, derived, old = pairs(opt.masters), pairs(opt.derived), pairs(opt.old)
    before = pairs(opt.before) or masters
    if set(old) != set(derived) or set(before) != set(masters):
        sys.exit("--old needs the same weights as --derived, --before the same as --masters")
    ref = opt.ref or sorted(masters, key=float)[len(masters) // 2]
    out = Path(opt.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dst = {}
    for k, p in {**masters, **derived}.items():
        d = out / p.name
        if d in dst.values():
            d = out / f"{k}-{p.name}"
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(p, d)
        dst[k] = d
    m_out = {k: dst[k] for k in masters}
    d_out = {k: dst[k] for k in derived}

    first = blocks(m_out, d_out, ref, opt.glyphs)
    before_old = blocks(before, old, ref, opt.glyphs)  # the old extremes against the masters they were made from
    keep = {(k.partition("@")[0], k.partition("@")[2] or w) for k in opt.keep_old for w in derived}
    names = sorted(set(opt.glyphs or {g for (g, w), (nb, nr) in first.items() if nb or nr > before_old[(g, w)][1]})
                   | {g for g, _ in keep})
    if not names:
        print("No derived glyph has blocks: nothing to carry.")
        return 0
    print(f"carrying {len(names)} glyphs: {' '.join(names)}")

    # 2. the before-masters and the old extremes for these glyphs, merged together
    nodes0 = {}
    for k in {**masters, **derived}:
        src = ufoLib2.Font.open(before[k] if k in masters else old[k])
        f = ufoLib2.Font.open(dst[k])
        for g in names:
            if g not in src:
                sys.exit(f"{g} is missing from {before[k] if k in masters else old[k]}")
            if k == ref:
                nodes0[g] = sum(1 for c in f[g].contours for p in c.points if p.type)
            f[g] = src[g].copy()
        f.save()
    log = run(HERE / "fix.py", *[f"{k}={dst[k]}" for k in sorted(dst, key=float)], "--ref", ref,
              "--ops", "merge", "--glyphs", *names, "--tol", opt.tol, "--write")
    skipped = [ln for ln in log.splitlines() if "skipped" in ln]
    for ln in skipped:
        print("  " + ln.strip())

    # 3. derive them again from the merged masters
    with tempfile.TemporaryDirectory() as t:
        run(HERE / "derive.py", *[f"{k}={v}" for k, v in m_out.items()], "--targets", *derived,
            "--stems-from", *[f"{k}={v}" for k, v in derived.items()], "--glyphs", *names, "--out-dir", t)
        fresh = {}
        for k in derived:
            hits = sorted(Path(t).glob(f"*-{float(k):g}.ufo"))
            if not hits:
                sys.exit(f"derive.py wrote no UFO for {k}")
            # derive.py copies every glyph it wasn't asked for from the nearest master, so
            # put the new glyphs into a copy of the derived weight: checks that measure
            # the weight's stem (stroke-ratio) need the rest of the font to be that weight
            fresh[k] = Path(t) / f"fresh-{k}.ufo"
            shutil.copytree(derived[k], fresh[k])
            ff, src = ufoLib2.Font.open(fresh[k]), ufoLib2.Font.open(hits[0])
            for g in names:
                ff[g] = src[g].copy()
            ff.save()
        new_b = blocks(m_out, fresh, ref, names)
        old_b = blocks(m_out, d_out, ref, names)
        # 4. pick per glyph and weight
        report = []
        for k in derived:
            f = ufoLib2.Font.open(d_out[k])
            nf = ufoLib2.Font.open(fresh[k])
            for g in names:
                a, b = new_b[(g, k)], old_b[(g, k)]
                use_new = (g, k) not in keep and (a == (0, 0) or a < b)
                if use_new:
                    f[g] = nf[g].copy()
                report.append({"glyph": g, "weight": k, "was": list(first[(g, k)]),
                               "choice": "derived" if use_new else ("old (kept)" if (g, k) in keep else "old"),
                               "left": list(a if use_new else b)})
            f.save()
    mf = ufoLib2.Font.open(dst[ref])
    for r in report:
        r["nodes"] = [nodes0[r["glyph"]], sum(1 for c in mf[r["glyph"]].contours for p in c.points if p.type)]
    (out / "carry.json").write_text(json.dumps(report, indent=1))

    print(f"\n{'glyph':18s}{'weight':>7s}  blocks   other    choice   nodes in {ref}")
    for r in report:
        (b0, r0), (b1, r1) = r["was"], r["left"]
        note = "   <- still blocks: by hand" if b1 else ("   <- check the render" if r1 else "")
        print(f"{r['glyph']:18s}{r['weight']:>7s}  {b0:>2d} -> {b1:<2d}  {r0:>2d} -> {r1:<2d}  {r['choice']:8s} "
              f"{r['nodes'][0]} -> {r['nodes'][1]}{note}")
    left = sum(r["left"][0] for r in report)
    print(f"\n{sum(r['was'][0] for r in report)} blocks -> {left}; other findings "
          f"{sum(r['was'][1] for r in report)} -> {sum(r['left'][1] for r in report)}. Wrote {out}. Fixes made to the "
          "masters after --before for these glyphs are undone: run them again, then audit.py.")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
