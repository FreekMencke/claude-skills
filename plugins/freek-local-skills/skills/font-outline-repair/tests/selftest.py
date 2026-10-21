"""Checks for the script bugs found on real families, on small made-up UFOs.
usage: selftest.py [--scripts DIR]   (with the skill's venv Python; prints "ok" or fails)

- fix.py repredict: two ranges in one contour are each measured from their own anchors,
  so giving them together moves the points as giving them one at a time does.
- profile.py: an off-curve A or B, or A equal to B, exits with a message instead of
  hanging or crashing; a segment with one off-curve point or more than two is profiled.
- merge: a node more than --tol past both neighbours is kept even when its tangent is a
  few degrees off the axis (Black f's inner arch).
- fair.py --edge: an edge that is one line segment from TIP to A is an edge of one step.
- between.py: a coordinate halfway between two masters rounds up, as fontmake's otRound.
- corner.py: a brace's inside corner off an edge of direction (65,-3), where fair.py finds
  no layout, comes out with no turn back and no jump at the nodes between.
- reshape.py: copy-shape refuses a stretch whose axes would scale far apart, and an op
  that makes a contour cross itself isn't written without --force.
- straighten.py --between: a run's points go to evenly spaced whole steps; a run with
  more gaps than whole steps is refused.
- reshape.flat_spots: a straight stretch between two bends of a smooth run is found; a
  circle has none."""
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


def make_font(path, glyphs, x_height=500):
    """glyphs: {name: [contour, ...]}, each contour a list of (x, y, type)."""
    font = ufoLib2.Font()
    font.info.unitsPerEm, font.info.xHeight, font.info.capHeight = 1000, x_height, 700
    for name, contours in glyphs.items():
        g = font.newGlyph(name)
        g.width = 600
        pen = g.getPointPen()
        for c in contours:
            pen.beginPath()
            for x, y, t in c:
                pen.addPoint((x, y), segmentType=t)
            pen.endPath()
    font.save(path, overwrite=True)
    return path


def run(*args, timeout=120):
    return subprocess.run([PY, *map(str, args)], capture_output=True, text=True, timeout=timeout)


def test_fair_edge_one_segment():
    d = tmp / "fair"
    d.mkdir()
    # TIP 0 -> A 1 is a single line; a curve from A to B 4, then a line back up
    ufo = make_ufo(d / "F.ufo", [[(0, 400, "line"), (0, 100, "line"), (0, 50, None), (50, 0, None),
                                  (100, 0, "curve"), (100, 400, "line")]])
    r = run(S / "fair.py", ufo, "z", "0:1>4", "--edge", "0:5")
    assert "no straight edge" not in r.stdout + r.stderr, r.stdout + r.stderr
    assert "now:" in r.stdout, r.stdout + r.stderr


def test_between_rounds_half_up():
    d = tmp / "between"
    d.mkdir()
    a = make_ufo(d / "A.ufo", [[(0, 0, "line"), (101, 0, "line"), (101, 3, "line")]])
    b = make_ufo(d / "B.ufo", [[(1, 0, "line"), (104, 0, "line"), (104, 6, "line")]])
    r = run(S / "between.py", f"300={a}", f"700={b}", "--glyphs", "z", "--weights", "500", "--out-dir", d / "out")
    assert r.returncode == 0, r.stderr
    got = points(d / "out" / "500.ufo")
    assert got == [(1, 0), (103, 0), (103, 5)], got     # 0.5, 102.5, 4.5 round up (Python's round: 0, 102, 4)


def test_corner():
    d = tmp / "corner"
    d.mkdir()
    # a Black brace's inside corner: a line of direction (65,-3) into node 2, three curves to
    # node 11, a vertical curve on (as derived, before it was faired)
    brace = [(43, 316, "line"), (43, 175, "line"), (108, 172, "line"), (121, 171, None), (125, 170, None),
             (129, 168, "curve"), (132, 166, None), (136, 162, None), (138, 159, "curve"), (144, 151, None),
             (147, 141, None), (147, 130, "curve"), (147, 117, None), (147, 104, None), (147, 91, "curve")]
    ufo = make_ufo(d / "C.ufo", [brace])
    r = run(S / "fair.py", ufo, "z", "0:2>8", "--edge", "1:12", "--move", "3")
    assert "corner.py" in r.stdout, r.stdout + r.stderr
    r = run(S / "corner.py", ufo, "z", "0:2>11", "--write")
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(x for x in r.stdout.splitlines() if x.strip().startswith("1:"))
    least, peak = (float(line.split(k)[1].split()[0]) for k in ("least", "peak"))
    jumps = [float(v) for v in line.split("jumps")[1].split("off edge")[0].split()]
    assert least > -0.5 and peak < 45 and max(jumps) < 2, line
    pts = points(ufo)
    assert pts[2] == (108, 172) and pts[11] == (147, 130), pts     # A and B stay


def test_reshape_guards():
    d = tmp / "reshape"
    d.mkdir()

    def stem(w):
        return [[(100, 0, "line"), (100 + w, 0, "line"), (100 + w, 600, "line"), (100, 600, "line")]]

    def bar(top, dip):
        # a bar whose top edge (nodes 2 to 5) dips toward the bottom edge in a curve
        return [[(0, 0, "line"), (300, 0, "line"), (300, top, "line"), (200, dip, None), (100, dip, None), (0, top, "curve")]]

    def flat(h, w=300):
        # a contour whose bottom stretch (nodes 1 to 4) runs nearly level: h units high
        return [[(0, 200, "line"), (0, h, "line"), (w / 3, 0, None), (2 * w / 3, 0, None), (w, 0, "curve"), (w, 200, "line")]]
    fonts = {"300": (60, bar(60, 20), flat(13)), "700": (100, bar(100, 40), flat(20)), "100": (28, bar(10, 10), flat(7))}
    paths = {w: make_font(d / f"F{w}.ufo", {"l": stem(sw), "z": b, "y": f}) for w, (sw, b, f) in fonts.items()}
    base = [S / "reshape.py", "--masters", f"300={paths['300']}", f"700={paths['700']}", "--derived", f"100={paths['100']}"]
    # per axis, y would scale 7/13 = x0.54 against x1.0 across: refused, nothing saved
    r = run(base[0], "copy-shape", "y@100:0:1-4", *base[1:], "--write")
    assert r.returncode == 1 and "use --similar" in r.stdout, r.stdout + r.stderr
    # the master's dip, shifted onto a bar 10 units thick, runs out through its bottom: not
    # written without --force
    before = [(p.x, p.y) for p in ufoLib2.Font.open(paths["100"])["z"].contours[0].points]
    r = run(base[0], "copy-shape", "z@100:0:2-5", *base[1:], "--write")
    assert r.returncode == 1 and "not saved" in r.stdout and "self-intersecting contours 0 -> 1" in r.stdout, r.stdout + r.stderr
    assert [(p.x, p.y) for p in ufoLib2.Font.open(paths["100"])["z"].contours[0].points] == before
    r = run(base[0], "copy-shape", "z@100:0:2-5", *base[1:], "--write", "--force")
    assert r.returncode == 0, r.stdout + r.stderr


def test_straighten_between():
    d = tmp / "straighten"
    d.mkdir()

    def run_of(end, n):
        # n curves from (0,0) to end, every point a little off the straight line
        pts, k = [(0, 0, "line")], 3 * n
        for j in range(1, k + 1):
            t = j / k
            pts.append((round(end[0] * t + 0.4 * (-1) ** j, 1), round(end[1] * t, 1), "curve" if j % 3 == 0 else None))
        return pts + [(end[0], end[1] + 100, "line"), (0, 100, "line")]
    ufo = make_ufo(d / "S.ufo", [run_of((40, -30), 2)])
    r = run(S / "straighten.py", ufo, "z", "0:0>6", "--between", "--write")
    assert r.returncode == 0 and "(4, -3)" in r.stdout, r.stdout + r.stderr
    got = points(ufo)[:7]
    steps = [x // 4 for x, _ in got]
    assert all(x % 4 == 0 and y == -3 * (x // 4) for x, y in got) and steps == sorted(set(steps)), got
    ufo = make_ufo(d / "T.ufo", [run_of((20, -15), 2)])          # 6 gaps, 5 whole steps of (4,-3)
    r = run(S / "straighten.py", ufo, "z", "0:0>6", "--between", "--write")
    assert r.returncode == 1 and "stack" in r.stdout, r.stdout + r.stderr


def test_flat_spots():
    import reshape
    k = 0.5523
    c = [Pt(0, 0, "line", False), Pt(20 * k, 0, None, False), Pt(20, 20 - 20 * k, None, False), Pt(20, 20, "curve", True),
         Pt(20, 28, None, False), Pt(20, 37, None, False), Pt(20, 45, "curve", True),
         Pt(20, 45 + 40 * k, None, False), Pt(-20 + 40 * k, 85, None, False), Pt(-20, 85, "curve", False)]
    flats = reshape.flat_spots(c)
    assert len(flats) == 1 and flats[0][:2] == (1, 1), flats       # segment 1: the straight curve 3-6
    circle = []
    for q in range(4):
        a0, a1 = q * math.pi / 2, (q + 1) * math.pi / 2
        p0 = (100 * math.cos(a0), 100 * math.sin(a0))
        p3 = (100 * math.cos(a1), 100 * math.sin(a1))
        circle += [Pt(*p0, "curve", True), Pt(p0[0] - 55.23 * math.sin(a0), p0[1] + 55.23 * math.cos(a0), None, False),
                   Pt(p3[0] + 55.23 * math.sin(a1), p3[1] - 55.23 * math.cos(a1), None, False)]
    assert reshape.flat_spots(circle) == []


for test in (test_repredict_ranges, test_profile, test_merge_keeps_tilted_extreme, test_fair_edge_one_segment,
             test_between_rounds_half_up, test_corner, test_reshape_guards, test_straighten_between, test_flat_spots):
    test()
    print(f"{test.__name__}: ok")
shutil.rmtree(tmp)
print("ok")
