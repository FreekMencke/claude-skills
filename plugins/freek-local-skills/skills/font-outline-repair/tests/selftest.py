"""Checks for the script bugs found on real families, on small made-up UFOs.
usage: selftest.py [--scripts DIR]   (with the skill's venv Python; prints "ok" or fails)

- fix.py repredict: two ranges in one contour are each measured from their own anchors,
  so giving them together moves the points as giving them one at a time does.
- profile.py: an off-curve A or B, or A equal to B, exits with a message instead of
  hanging or crashing; a segment with one off-curve point or more than two is profiled.
- merge: a node more than --tol past both neighbours is kept even when its tangent is a
  few degrees off the axis (Black f's inner arch)."""
import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ufoLib2

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--scripts", default=str(Path(__file__).resolve().parent.parent / "scripts"))
args = ap.parse_args()
S = Path(args.scripts)
sys.path.insert(0, str(S))
import fontlib as L  # noqa: E402
from compat import Pt  # noqa: E402

PY = sys.executable
tmp = Path(tempfile.mkdtemp(prefix="outline-selftest-"))


def make_ufo(path, contours):
    """contours: lists of (x, y, type) with type None for an off-curve point."""
    font = ufoLib2.Font()
    g = font.newGlyph("z")
    g.width = 600
    pen = g.getPointPen()
    for c in contours:
        pen.beginPath()
        for x, y, t in c:
            pen.addPoint((x, y), segmentType=t)
        pen.endPath()
    font.save(path, overwrite=True)
    return path


def ring(loc, bumps=None):
    """16 line points round an ellipse that widens with weight; bumps moves point ranges
    of this master outward, a shift moves points 6-9 up (the master's own placement)."""
    rx, ry = 100 + (loc - 300) * 0.6, 100 + (loc - 300) * 0.1
    pts = []
    for k in range(16):
        a = 2 * math.pi * k / 16
        x, y = 300 + rx * math.cos(a), 300 + ry * math.sin(a)
        if bumps:
            if k in (3, 4, 5):
                x, y = x + 9 * math.cos(a), y + 9 * math.sin(a)
            if k in (10, 11, 12):
                x, y = x + 14 * math.cos(a), y + 14 * math.sin(a)
            if k in (6, 7, 8, 9):
                y += 15
        pts.append((round(x, 2), round(y, 2), "line"))
    return [pts]


def points(path):
    return [(p.x, p.y) for p in ufoLib2.Font.open(path)["z"].contours[0].points]


def repredict(srcs, specs, out):
    cmd = [PY, str(S / "fix.py"), *srcs, "--ops", "repredict", "--round", "no", "--ref", "300",
           "--min-dev", "0.5", "--out-dir", str(out), "--points", *specs]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_repredict_ranges():
    d = tmp / "repredict"
    d.mkdir()
    srcs = [f"{w}={make_ufo(d / f'M{w}.ufo', ring(w, bumps=w == 400))}" for w in (300, 400, 700)]
    both = repredict(srcs, ["z:400:0:3-5", "z:400:0:10-12"], d / "both")
    repredict(srcs, ["z:400:0:3-5"], d / "one")
    repredict([srcs[0], f"400={d / 'one' / 'M400.ufo'}", srcs[2]], ["z:400:0:10-12"], d / "two")
    got, want = points(d / "both" / "M400.ufo"), points(d / "two" / "M400.ufo")
    worst = max(L.dist(a, b) for a, b in zip(got, want))
    assert worst < 0.01, f"two ranges together moved points {worst:.2f} units off one at a time:\n{both}"
    assert "relative to points 2 and 6" in both and "relative to points 9 and 13" in both, both
    # single points stand alone too
    out = repredict(srcs, ["z:400:0:4", "z:400:0:9"], d / "single")
    assert out.count("following its own trend") >= 1 and "relative to" not in out, out


def profile(spec, ufo):
    return subprocess.run([PY, str(S / "profile.py"), "z", spec, str(ufo), "--curves"],
                          capture_output=True, text=True, timeout=30)


def test_profile():
    d = tmp / "profile"
    d.mkdir()
    # node 0, a curve with one off-curve point (quadratic), node 2, a qcurve with three, node 6, a line back
    ufo = make_ufo(d / "P.ufo", [[(0, 0, "line"), (100, 100, None), (200, 0, "curve"),
                                  (250, -50, None), (300, -60, None), (350, -40, None), (400, 0, "qcurve")]])
    for spec in ("0:1>6", "0:0>3", "0:2>2"):
        r = profile(spec, ufo)
        assert r.returncode != 0 and ("not an on-curve point" in r.stderr or "same node" in r.stderr), (spec, r)
    for spec in ("0:0>6", "0:6<0", "0:6>2"):
        r = profile(spec, ufo)
        assert r.returncode == 0 and "turns" in r.stdout, (spec, r.stderr)
    r = profile("0:0>2", ufo)
    # the quadratic arch y = x - x^2/200: radius 100 at its top, so curvature 10 (x1000)
    assert r.returncode == 0 and "peak 10.00" in r.stdout, r.stdout


def test_merge_keeps_tilted_extreme():
    # an arch whose top node N is 6 units above both neighbours, its tangent 3 degrees off
    t = math.radians(3)
    A, B, N = (0, 0), (200, 0), (100, 6)
    pts = [(A, "curve"), ((30, 4), None), (L.sub(N, (40 * math.cos(t), 40 * math.sin(t))), None), (N, "curve"),
           (L.add(N, (40 * math.cos(t), 40 * math.sin(t))), None), ((170, 4), None), (B, "curve")]
    c = [Pt(x, y, typ, typ is not None) for (x, y), typ in pts]
    idx = [0, 1, 2, 3, 4, 5, 6]
    assert L.merge_preconditions(c, idx, keep_extremes=True, tol=1.0) is None, "tilted extreme node would be merged"
    assert L.merge_preconditions(c, idx, keep_extremes=False, tol=1.0) is not None


for test in (test_repredict_ranges, test_profile, test_merge_keeps_tilted_extreme):
    test()
    print(f"{test.__name__}: ok")
shutil.rmtree(tmp)
print("ok")
