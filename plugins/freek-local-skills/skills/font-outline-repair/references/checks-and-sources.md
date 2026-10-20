# Common outline mistakes, who checks them, and what this skill does

Researched 2026-10-19. "Raw" means read from the source code or raw file; "fetch"
means read through a summarising fetch tool, so wording may be trimmed. Thresholds
are in font units at 1000 UPM unless noted.

## Drawing mistakes in one master

| mistake | established checks (threshold) | audit code | fix |
|---|---|---|---|
| no node at an x/y extreme | RedArrow Extremum; Glyph Nanny extremePoints; FontAudit extremum points; Google Fonts guide: hints "can only get hooked on nodes at the extremum" | missing-extreme | `extremes` |
| smooth node not quite smooth | RedArrow "Not quite smooth" (`RedArrowSmoothMaxDistance: 4`); Glyph Nanny unsmoothSmooths (whole degrees); FontAudit incorrect smooth connection | kink, near-smooth, smooth-mismatch | `smooth-flags`, `collinear` |
| line or handle almost horizontal/vertical | RedArrow semi-H/V (length > 30, offset <= 2); mekkablue almostOrthogonalLines (0.1-3) and angledHandles (8°); Glyph Nanny angleNearMiss (<= 5); Google Fonts guide: "off ... from one or two units, it is most likely a mistake" | semi-hv (one master), alignment-break (against the other masters) | repredict, or snap by hand |
| zero-length handle | RedArrow, mekkablue zeroHandles, FontAudit zero-length handles | zero-handle | by hand |
| curve that is really straight | Glyph Nanny unnecessaryHandles; FontAudit flat curves; AFDKO checkoutlinesufo flat curves (`--tolerance` 0) | flat-curve | `merge` turns it into a line when it is straight in every master |
| node on a straight line, or more nodes than the shape needs | Glyph Nanny unnecessaryPoints (refit within 3.5% of the length); AFDKO collinear lines; Glyphs Tidy Up Paths; Ohno: "keep the number of points as small as is necessary" | excess-nodes | `merge` |
| handles unbalanced, or longer than where they meet | Glyph Nanny unevenHandles (ratio > 1.5); FontAudit disproportional; mekkablue largeHandles; Glyphs: type handles run "from just under 60% to something above 70%", 100% is where they meet | uneven-handles, handle-overlong | repredict, or balance by hand (Tunni) |
| crossed handles, loops, cusps | Glyph Nanny crossedHandles; FontAudit loop and cusp; mekkablue cuspingHandles, outwardHandles | handle-crossing, cusp, handle-backward, self-intersection | repredict, or by hand |
| S-bend inside one segment | RedArrow Inflection (`RedArrowInflectionMin: 0.3`); Glyph Nanny complexCurves; Google Fonts guide "suspicious inflection": "divide this segment by adding a node" | inflection | by hand (add a node) |
| a straight edge running into a curve that turns in one spot (a knee), or a flat spot in a curve | FontLab "Fixing the S problem": "Kinks are to G1 continuity, as crimps are to G2 continuity", fixed by moving the handles beside the join while watching the comb; Glyphs 4's star node also works "on curve-to-line transitions" and "expands the curve into the line segment" | curvature-step; `profile.py --curves` | `fair.py` (`--edge` to start the curve earlier) |
| curvature step at a smooth node (comb jumps) | mekkablue greenDiscontinuity: abs(R1-R2)/(R1+R2) >= 11% (5% strict, 15% relaxed); Speed Punk: "If you see a jump in the curvature illustration, curvature is discontinuous" | curvature-step (default 15%), scallop | `merge`; `harmonize` exists but see SKILL.md |
| corners sharper, blunter or turned the other way than in the reference | one typeface repo's own notes flag corners "much sharper than Light's"; research found no established tool test for it (block C: "not found"), so this check is the skill's own | corner-flip, corner-change | repredict, or by hand |
| short or tiny segments, stray points, tiny contours | RedArrow short segment (<= 1); mekkablue shortSegment (8, off by default); Glyph Nanny smallContours (area <= 4), strayPoints; AFDKO `--min-area` 25 | short-segment, tiny-contour | by hand; the Google Fonts guide warns that 1-2 unit segments are often ink traps |
| top/bottom just off a metric or zone | Glyph Nanny pointsNearVerticalMetrics (5); mekkablue Find Near Vertical Misses | zone-miss | by hand, or repredict |
| curves converted from TrueType (handles at exactly 2/3) | none of the above; fontTools `qu2cu` is the tool that turns quadratics back into the fewest cubics ("max_err ... defaults to 0.5") | converted-quadratic, scallop | `merge` |

## Mistakes that grow under interpolation and extrapolation

| mistake | established checks | audit code | fix |
|---|---|---|---|
| wrong start point, contour order, direction, node count or type | fontTools interpolatable; Glyphs: "The first and foremost reason for incompatibility is a wrong start point" | start-point, contour-order, direction, point-count, point-type | `compat`, `redundant`, or by hand |
| kinks between masters: three points in line whose ratio differs while the angle turns | Glyphs Multiple Masters part 2; mekkablue Kink Finder (0.9), Dekink Master Layers, HOI Dekinker (0.92) | ratio-mismatch; `between.py --raw` | `triplet-ratio` (see SKILL.md for the cost); when editing one master by hand, `fair.py --ratio` |
| handle behaviour that jumps between masters | mekkablue "New Tab with Uneven Handle Distributions" (factor 2.5) | tension-jump, handle-flip | repredict |
| a point that moves against its neighbours | mekkablue Travel Tracker; extrapolation "continue[s] the linear movement of points" (mekkablue, Glyphs forum) | motion-bend; derived: segment-reversal, handle-reversal | repredict |
| strokes or counters collapsing at the extremes | de Groot: at Black "the horizontals cannot get any thicker, because then the letter will disappear"; practitioners extrapolate a rough Thin/Black, then redraw it | direction-flip, counter-breakout, thin-stroke, counter-tight | lower the target stem, or fix the promoted master by hand |
| a crossing part sliding into the stroke it crosses (the bar of ð), parts running into each other (™, ‰), ink past the side bearings, tapered strokes going to hairlines | no tool test found; on one family an earlier automated Thin/Black had patched several of these (a wider ð and ™, a thicker R in ®) | crossing-shrink, overlap-new, overhang, thin-stroke | `contrast.py` for thin strokes; by hand in the promoted master for collisions |
| overlaps removed in sources | Glyphs: "Keeping the leg and the bowl separate ensures interpolation"; fontmake removes overlaps "except when producing interpolatable or variable fonts" | overlap-new (derived) | keep overlaps in the sources |

## Where the experts disagree

- Extremes: Glyphs, FontLab and the Google Fonts guide say to put nodes on extremes;
  TypeDrawers voices accept leaving them out on short, shallow or slanted curves.
  This skill keeps extremes when merging (`--merge-extremes` to override).
- Weight progression: linear stems versus de Groot's "hollow curve" (in-between
  weights lighter than the linear midpoint). `derive.py --axis stem` lets the user
  pick the target stems instead of assuming either.

## Sources

- RedArrow for Glyphs, `outlineTestGlyphs.py`, `defaults.py` (raw, commit 62d513b): https://github.com/jenskutilek/RedArrow-Glyphs
- Glyph Nanny tests (raw, commit b45e806): https://github.com/typesupply/glyph-nanny
- mekkablue Glyphs-Scripts, `Paths/Path Problem Finder.py` and README (raw, commit 21c9165): https://github.com/mekkablue/Glyphs-Scripts
- AFDKO `checkoutlinesufo.py` (raw): https://github.com/adobe-type-tools/afdko
- fontTools `qu2cu` and `cu2qu` (raw, installed 4.65.0): https://github.com/fonttools/fonttools
- Speed Punk README (raw): https://github.com/yanone/speedpunk
- fontmake USAGE.md (raw): https://github.com/googlefonts/fontmake
- FontLab FontAudit (fetch): https://help.fontlab.com/fontlab-vi/FontAudit/
- Glyphs, "Drawing good paths" (fetch): https://glyphsapp.com/learn/drawing-good-paths
- Glyphs, "Multiple Masters, part 2" (fetch): https://glyphsapp.com/learn/multiple-masters-part-2-keeping-your-outlines-compatible
- Google Fonts guide, "Outline quality" (fetch): https://googlefonts.github.io/gf-guide/outlines.html
- Ohno, "Drawing vectors" (fetch): https://ohnotype.co/blog/drawing-vectors
- Lucas de Groot, "Interpolation theory" (fetch; the formula itself is an image and was not read): https://www.lucasfonts.com/learn/interpolation-theory
- FontLab 8 tutorial, "PROJECT: Fixing the S problem" (fetch, 2026-10-19): https://help.fontlab.com/fontlab/8/tutorials/calfonts/2.%20Honing/2c-0a%20PROJECT%20Fixing%20the%20S%20Problem/
- Glyphs 4 announcement, star nodes and the squircle transition (fetch, 2026-10-19): https://glyphsapp.com/news/glyphs-4-create-love-the-process
- TypeDrawers, node placement and extrapolation threads (fetch): https://typedrawers.com/discussion/5150/correct-node-placement, https://typedrawers.com/discussion/comment/35730
