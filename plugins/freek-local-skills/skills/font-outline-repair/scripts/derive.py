#!/usr/bin/env python3
"""Derive extra weights (for example 100 and 900) from existing masters.

usage:
  derive.py SOURCES... --targets 100 900 --out-dir derived/
            [--method fit|piecewise] [--axis stem|weight|design]
            [--stems 100=22 900=190 | --stems-from 100=old/Thin.ufo 900=old/Black.ufo]
            [--designspace-out family-5masters.designspace]

SOURCES is one .designspace file or several weight=path.ufo pairs.

--method auto       (default) tries piecewise, fit and wide for every glyph's outline and
                    keeps the one with the fewest blocks, then slows (ties go to the one
                    that amplifies the masters' errors least). Advance widths, side
                    bearings, kerning and font metrics use wide for the whole font, so
                    related glyphs keep their spacing.
--method wide       extends the two outermost masters: the widest base, so the
                    least amplification when the target lies far outside.
--method piecewise  extends the nearest pair of masters, like most tools do. Faithful
                    when masters are clean; a defect in either of those two masters
                    is magnified at that end.
--method fit        fits a straight line through all masters for every coordinate.
                    Damps noise spread over the masters, but spreads one bad master
                    to both ends and flattens deliberate non-linear progressions.
--axis stem         (default) places masters by their measured stem width, so the
                    fit follows stem thickness rather than the weight number.
                    Needs target stems: --stems, or --stems-from earlier derived UFOs,
                    otherwise a geometric guess is printed and used.

Coordinates are rounded to whole units (when the masters are) keeping each handle's
direction, and the new UFOs are named from the designspace's axis labels (Thin, Black).

Glyphs whose masters are not point-compatible are copied from the nearest master
unchanged and listed, so fix compatibility first. Writes only to --out-dir and
--designspace-out.
"""
from __future__ import annotations

import argparse
import copy
import shutil
import sys
from pathlib import Path

import ufoLib2
from fontMath import MathInfo, MathKerning

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fontlib as L  # noqa: E402
from compat import align_glyph  # noqa: E402


ROUND = False


def _xmin(g):
    xs = [p.x for c in g.contours for p in c.points]
    return min(xs) if xs else None


def blend_glyph(glyphs, coeffs, out, metrics=None):
    """out = sum(c_i * glyph_i), point by point; structure taken from glyphs[0].
    metrics: coefficients for the advance width and left side bearing, when the
    outline uses other ones (method auto picks the outline's method per glyph, but
    spacing must follow one method across the font, or related glyphs drift apart)."""
    out.clearContours()
    out.clearComponents()
    out.clearAnchors()
    wc = metrics or coeffs
    w = sum(c * g.width for c, g in zip(wc, glyphs))
    h = sum(c * (g.height or 0) for c, g in zip(coeffs, glyphs))
    out.width = round(w) if ROUND else round(w, 2)
    out.height = round(h) if ROUND else round(h, 2)
    pen = out.getPointPen()
    for ci, contour in enumerate(glyphs[0].contours):
        pen.beginPath()
        for pi, p in enumerate(contour.points):
            x = sum(c * g.contours[ci].points[pi].x for c, g in zip(coeffs, glyphs))
            y = sum(c * g.contours[ci].points[pi].y for c, g in zip(coeffs, glyphs))
            pen.addPoint((round(x, 2), round(y, 2)), segmentType=p.type, smooth=p.smooth)
        pen.endPath()
    shift = 0.0
    if metrics and metrics != coeffs and _xmin(out) is not None and all(_xmin(g) is not None for g in glyphs):
        # keep the left side bearing the metrics method gives; the whole glyph moves
        shift = sum(c * _xmin(g) for c, g in zip(metrics, glyphs)) - _xmin(out)
        if ROUND:
            shift = round(shift)
    if ROUND:
        # plain rounding turns short handles by tens of degrees (kinks, even curls at
        # Thin/Black); keep each handle's direction instead, as fix.py does
        from fix import round_keeping_directions
        round_keeping_directions(out)
    # shift after rounding: shifting first changes how x.5 values round, and with it
    # the direction of short handles
    for c in out.contours:
        for p in c.points:
            p.x += shift
    for k, comp in enumerate(glyphs[0].components):
        t = [sum(c * g.components[k].transformation[j] for c, g in zip(coeffs, glyphs)) for j in range(6)]
        t[4] += shift
        t = [round(v, 4) for v in t[:4]] + [round(v) if ROUND else round(v, 2) for v in t[4:]]
        pen.addComponent(comp.baseGlyph, tuple(t))
    names = [a.name for a in glyphs[0].anchors]
    for n in names:
        found = [next((a for a in g.anchors if a.name == n), None) for g in glyphs]
        if all(found):
            ax = sum(c * a.x for c, a in zip(coeffs, found)) + shift
            ay = sum(c * a.y for c, a in zip(coeffs, found))
            out.appendAnchor({"name": n, "x": round(ax) if ROUND else round(ax, 2), "y": round(ay) if ROUND else round(ay, 2)})


STANDARD_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                  600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}


def style_name(t, doc):
    """The designspace's axis label for weight t, else the usual name, else the number."""
    if doc is not None:
        for axis in doc.axes:
            if axis.tag == "wght":
                for lab in getattr(axis, "axisLabels", []) or []:
                    if abs(lab.userValue - t) < 1e-6:
                        return lab.name
    return STANDARD_NAMES.get(int(t), f"{t:g}") if float(t).is_integer() else f"{t:g}"


def name_font(font, style):
    """Names for a derived weight. The UFO starts as a copy of the nearest master, so
    without this it keeps that master's PostScript name (two fonts called Family-Light)
    and style linking (a Black marked as the bold of the family)."""
    i = font.info
    fam = i.familyName or ""
    i.styleName = style
    i.styleMapStyleName = {"Regular": "regular", "Bold": "bold", "Italic": "italic", "Bold Italic": "bold italic"}.get(style, "regular")
    i.styleMapFamilyName = fam if style in ("Regular", "Bold", "Italic", "Bold Italic") else f"{fam} {style}"
    i.postscriptFontName = f"{fam}-{style}".replace(" ", "")
    i.postscriptFullName = f"{fam} {style}"
    for attr in ("openTypeNamePreferredSubfamilyName", "openTypeNameUniqueID", "openTypeNameCompatibleFullName",
                 "postscriptUniqueID", "macintoshFONDName"):
        setattr(i, attr, None)


_CHECK_OPT = None


def shape_score(name, glyph, aligned, ref_i):
    """Score a derived glyph with the audit's derived-outline and corner checks:
    (blocks, slows, minor), compared in that order (lower is better)."""
    import types
    import audit
    from compat import pts_of
    global _CHECK_OPT
    if _CHECK_OPT is None:
        _CHECK_OPT = types.SimpleNamespace(kink_tol=0.5, ref_label=None, straight_in_ref=set(), ref_bend={}, corner_tol=25.0)
    cs = [pts_of(c) for c in glyph.contours]
    smooth_any = {(ci, i) for a in aligned for ci, c in enumerate(a) for i, p in enumerate(c) if p.smooth}
    found = audit.shape_checks(name, "x", cs, aligned[ref_i], smooth_any, _CHECK_OPT, derived=True)
    found += audit.corner_checks(name, "x", cs, aligned[ref_i], True, _CHECK_OPT)
    # blocks first: no number of small problems outweighs a barb or a curl
    sev = [i["severity"] for i in found]
    return (sev.count("blocks"), sev.count("slows"), sev.count("minor"))


def target_stems(masters, stems, targets, given, from_ufos):
    out = {}
    for spec in from_ufos:
        w, p = spec.split("=", 1)
        g, s = L.ref_stem(ufoLib2.Font.open(p))
        out[float(w)] = s
    for spec in given:
        w, s = spec.split("=", 1)
        out[float(w)] = float(s)
    ws = [m.weight for m in masters]
    for t in targets:
        if t in out:
            continue
        # geometric guess from the nearest step: same stem ratio per weight unit
        if t < ws[0]:
            a, b = 0, 1
        else:
            a, b = len(ws) - 1, len(ws) - 2
        ratio = stems[a] / stems[b]
        out[t] = stems[a] * ratio ** ((t - ws[a]) / (ws[a] - ws[b]))
        print(f"note: no target stem for {t:g}; using a geometric guess of {out[t]:.0f} units. "
              f"Confirm it, or pass --stems {t:g}=N", file=sys.stderr)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--targets", nargs="+", type=float, required=True)
    ap.add_argument("--out-dir", help="where the new UFOs go (required unless --dry-run)")
    ap.add_argument("--method", choices=["auto", "piecewise", "fit", "wide"], default="auto")
    ap.add_argument("--axis", choices=["stem", "weight", "design"], default="stem")
    ap.add_argument("--stems", nargs="*", default=[], help="weight=units target stem widths")
    ap.add_argument("--stems-from", nargs="*", default=[], help="weight=path.ufo to measure target stems from")
    ap.add_argument("--stem-glyph", default=None, help="glyph to measure stems on (default: n, l, I, H, o)")
    ap.add_argument("--glyphs", nargs="*")
    ap.add_argument("--designspace-out")
    ap.add_argument("--round", choices=["auto", "yes", "no"], default="auto",
                    help="whole-unit coordinates (auto: when 99%% of the masters' points already are)")
    ap.add_argument("--dry-run", action="store_true", help="print stems and coefficients only; write nothing")
    opt = ap.parse_args(argv)

    if not opt.out_dir and not opt.dry_run:
        ap.error("--out-dir is required unless --dry-run")
    masters, doc = L.load_sources(opt.sources)
    if len(masters) < 2:
        sys.exit("need at least two masters")
    names = L.common_glyphs([m.font for m in masters])
    labels = [m.label for m in masters]
    ref_i = len(masters) // 2

    glyph_choice = (opt.stem_glyph,) if opt.stem_glyph else ("n", "l", "I", "H", "o")
    stems = []
    for m in masters:
        g, s = L.ref_stem(m.font, glyph_choice)
        stems.append(s)
    if opt.axis == "stem":
        if any(s is None for s in stems):
            sys.exit("could not measure stems; pass --stem-glyph or use --axis weight")
        locs = stems
        tstems = target_stems(masters, stems, opt.targets, opt.stems, opt.stems_from)
        tlocs = {t: tstems[t] for t in opt.targets}
    elif opt.axis == "weight":
        locs = [m.weight for m in masters]
        tlocs = {t: t for t in opt.targets}
    else:
        locs = [m.loc for m in masters]
        if doc is None:
            sys.exit("--axis design needs a .designspace")
        axis = [a for a in doc.axes if a.tag == "wght"][0]
        tlocs = {t: extend_map(axis, t) for t in opt.targets}
    print("masters: " + ", ".join(f"{m.label} (stem {s:.0f}, axis {a:.1f})" for m, s, a in zip(masters, stems, locs)))

    if opt.dry_run:
        if opt.method == "auto":
            print("method auto: each glyph's outline from piecewise, fit or wide, whichever has the fewest problems; "
                  f"spacing, kerning and metrics with {'wide' if len(masters) > 2 else 'piecewise'} (shown below)")
        for t in opt.targets:
            coeffs = L.blend_weights(locs, tlocs[t], ("wide" if len(masters) > 2 else "piecewise") if opt.method == "auto" else opt.method)
            tgt = f", target stem {tlocs[t]:.0f}" if opt.axis == "stem" else ""
            print(f"{t:g}: coefficients {', '.join(f'{l}×{c:+.3f}' for l, c in zip(labels, coeffs))}{tgt}")
        return 0
    global ROUND
    pts = [p for m in masters for g in m.font for c in g.contours for p in c.points]
    ROUND = opt.round == "yes" or (opt.round == "auto" and bool(pts) and
                                   sum(float(p.x).is_integer() and float(p.y).is_integer() for p in pts) >= 0.99 * len(pts))
    outdir = Path(opt.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = {}
    for t in opt.targets:
        coeffs = L.blend_weights(locs, tlocs[t], "piecewise" if opt.method == "auto" else opt.method)
        nearest = min(range(len(masters)), key=lambda i: abs(masters[i].weight - t))
        src = masters[nearest]
        dst = outdir / f"{src.path.stem.rsplit('-', 1)[0]}-{t:g}.ufo"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src.path, dst)
        font = ufoLib2.Font.open(dst)
        methods = ("piecewise", "fit", "wide") if len(masters) > 2 else ("piecewise",)
        skipped, picked = [], {m: 0 for m in methods}
        alt = {m: L.blend_weights(locs, tlocs[t], m) for m in methods}
        amp = {m: sum(abs(c) for c in alt[m]) for m in methods}
        # spacing, kerning and font metrics follow one method across the font: the one
        # given, or with auto the one that amplifies least
        mmethod = opt.method if opt.method != "auto" else min(methods, key=lambda m: amp[m])
        coeffs = alt.get(mmethod, coeffs)
        for name in names:
            if opt.glyphs and name not in opt.glyphs:
                continue
            gl = [m.font[name] for m in masters]
            aligned, _, iss = align_glyph(name, gl, labels, ref_i)
            if aligned is None or any(i["code"] in ("start-point", "contour-order", "direction", "component-order") for i in iss):
                skipped.append(name)
                continue
            if opt.method == "auto":
                best = None
                for meth in methods:
                    blend_glyph(gl, alt[meth], font[name])
                    s = shape_score(name, font[name], aligned, ref_i)
                    if best is None or (s, amp[meth]) < best[0]:
                        best = ((s, amp[meth]), meth)
                picked[best[1]] += 1
                blend_glyph(gl, alt[best[1]], font[name], metrics=coeffs)
            else:
                blend_glyph(gl, coeffs, font[name])
        try:
            mk = [MathKerning(m.font.kerning, m.font.groups) for m in masters]
            k = sum((mk_i * c for mk_i, c in zip(mk[1:], coeffs[1:])), mk[0] * coeffs[0])
            if ROUND:
                k.round()
            k.extractKerning(font)
            mi = [MathInfo(m.font.info) for m in masters]
            info = sum((mi_i * c for mi_i, c in zip(mi[1:], coeffs[1:])), mi[0] * coeffs[0])
            # metrics come out as 869.9999999999998 without this
            info = info.round() if ROUND else info.round(2)
            info.extractInfo(font.info)
        except Exception as e:  # kerning/info mismatch should not stop outline work
            print(f"note: kerning/info not blended ({e}); copied from {src.label}", file=sys.stderr)
        font.info.openTypeOS2WeightClass = int(round(t))
        name_font(font, style_name(t, doc))
        font.lib["com.github.font-outline-repair.derived"] = {
            "from": labels, "method": opt.method, "metrics_method": mmethod, "axis": opt.axis,
            "coefficients": [round(c, 4) for c in coeffs],
            "axis_value": round(tlocs[t], 2)}
        font.save()
        written[t] = dst
        tgt = f", target stem {tlocs[t]:.0f}" if opt.axis == "stem" else ""
        print(f"{t:g}: {dst}  coefficients {', '.join(f'{l}×{c:+.3f}' for l, c in zip(labels, coeffs))}{tgt}")
        if opt.method == "auto":
            print("  per glyph: " + ", ".join(f"{m} {picked[m]} (amplification {amp[m]:.1f})" for m in methods) +
                  f"; fewest shape problems wins, ties go to the least amplification. Widths, side bearings, "
                  f"kerning and metrics: {mmethod}")
        if skipped:
            print(f"  copied unchanged from {src.label} (not compatible yet): {' '.join(skipped)}")

    if opt.designspace_out:
        if doc is None:
            sys.exit("--designspace-out needs a .designspace source")
        write_designspace(doc, written, Path(opt.designspace_out))
    return 0


def extend_map(axis, user):
    """Design value for a user value, extending the axis map in a straight line past its ends."""
    if not axis.map:
        return user
    pts = sorted(axis.map)
    if pts[0][0] <= user <= pts[-1][0]:
        return axis.map_forward(user)
    (a, b) = (pts[0], pts[1]) if user < pts[0][0] else (pts[-2], pts[-1])
    return a[1] + (user - a[0]) * (b[1] - a[1]) / (b[0] - a[0])


def write_designspace(doc, written, out):
    from fontTools.designspaceLib import SourceDescriptor
    doc = copy.deepcopy(doc)
    axis = [a for a in doc.axes if a.tag == "wght"][0]
    for t, path in sorted(written.items()):
        design = extend_map(axis, t)
        if axis.map:
            axis.map = sorted(set(list(axis.map) + [(t, design)]))
        axis.minimum = min(axis.minimum, t)
        axis.maximum = max(axis.maximum, t)
        s = SourceDescriptor()
        s.path = str(path.resolve())
        s.filename = str(Path(path).resolve().relative_to(out.resolve().parent)) if Path(path).resolve().is_relative_to(out.resolve().parent) else str(path.resolve())
        s.familyName = doc.sources[0].familyName
        s.styleName = style_name(t, doc)
        s.location = dict(doc.sources[0].location)
        s.location[axis.name] = design
        doc.sources = [x for x in doc.sources if abs(x.location.get(axis.name, 1e9) - design) > 1e-6] + [s]
    doc.sources.sort(key=lambda s: s.location.get(axis.name, 0))
    for s in doc.sources:
        if s.path and not s.filename.startswith("/"):
            try:
                s.filename = str(Path(s.path).resolve().relative_to(out.resolve().parent))
            except ValueError:
                s.filename = str(Path(s.path).resolve())
    doc.write(out)
    print(f"designspace with {len(doc.sources)} masters: {out}")


if __name__ == "__main__":
    sys.exit(main())
