# Issue codes

Every finding from `audit.py` has a code, a severity and a weight. "Weight" is the
master or derived weight it was seen in; `all` means it is a pattern across the
masters rather than one master's fault. Contour and point numbers follow the
reference master after matching.

Severity, in font terms:

- **blocks**: the masters will not interpolate, or the outline is visibly broken at
  that weight (inside out, a loop, a barb). Fix before anything else.
- **slows**: visible at display sizes, or it grows when you extrapolate (kinks,
  wobbles, uneven tension). Fix before promoting 100 and 900 to masters.
- **minor**: cleanup that helps editing and hinting, or something that may be a
  deliberate design choice. Fix when convenient, or leave with a note.

Fix names in `code` font are `fix.py --ops` operations. `merge` reduces points: it removes a smooth node when one curve can replace the
two around it within `--tol` units of the original outline in every master, and
keeps corners and extremes. "Repredict" means
`fix.py --ops repredict --points glyph:master:contour:point` (or a range,
`glyph:master:contour:6-9`), which moves points of one master to where the other
masters put them, relative to the points just outside the group. "By hand" means the user or a
designer edits the outline in a font editor.

## Structure: masters must match point for point

| code | what is wrong | fix |
|---|---|---|
| contour-order | contours are stored in a different order in one master | `compat` |
| direction | a contour runs clockwise in one master and counter-clockwise in another | `compat` |
| start-point | a contour starts at a different node in one master | `compat` |
| component-order | the same components in a different order | `compat` |
| component-mismatch | different components | by hand |
| contour-count | a master has more or fewer contours | by hand: add or remove the contour so every master has it |
| point-count | a contour has more or fewer points in one master | `redundant` when the extra point sits on a straight line or on top of its neighbour; otherwise by hand |
| point-type | a segment is a line in one master and a curve in another | by hand: make it a curve everywhere (handles on the line where it should look straight) |

## Shape: any single outline

| code | looks like | likely cause | fix |
|---|---|---|---|
| kink | a small corner in what should be a smooth curve | handles at a smooth node not in line, or a corner node that is straight in the reference master but bends here | `collinear` for smooth nodes; if it says the masters don't agree which handle is wrong, or the node isn't flagged smooth, repredict or fix by hand |
| smooth-mismatch | a node is smooth in some masters, a corner in others | drawn separately per master | `smooth-flags`, then `collinear` |
| near-smooth | corners in the reference master that are within 3° of straight (one finding per glyph, listing them) | smooth nodes drawn as corners | decide per node: make it smooth (set the flag in every master, then `collinear`) or make it a clear corner |
| handle-backward | a handle points away from the curve it controls | a dragged or flipped handle | repredict the handle in the master that has it |
| handle-overlong | a handle reaches past the point where the two handles' lines meet | over-pulled handle; above 1.0 the curve bends back on itself | shorten it below the meeting point (Tunni line); repredict if only one master has it |
| handle-crossing | the two handles of one curve cross each other | over-tense curve | shorten the handles by hand |
| cusp | a sharp point inside a curve | handles collapse onto each other | redraw the segment |
| self-intersection | the contour crosses itself (a loop or curl) | in a master: an overlap drawn on purpose, or a curl. In a derived weight: points moved past each other | master: check the render. derived: find the point with handle-reversal or segment-reversal and trace it to a master |
| counter-breakout | a counter pokes through its outer contour, or a part inside a counter runs into it (the R of ®) | target weight heavier than the masters support | a part inside a counter: `contrast.py` scales it down until it clears as in the master (at most 15%); otherwise lower the target stem, or fix the promoted 900 master by hand |
| overlap-new | two contours that are apart in the reference now cross: parts run into each other (the T and M of ™, the rings of ‰ at Black). Blocks in a derived weight, slows in a master | strokes grew into each other | removing overlaps at build fuses them, so it stays visible: widen the glyph or redraw the parts (by hand); with an earlier hand-drawn Thin/Black the user trusts, `carry.py` |
| corner-flip | a corner turns the other way than in the reference master: a notch, barb or spike | points of a join or terminal crossed over in this master | repredict a range around it; in a derived weight, trace it to the master |
| corner-change | a corner much sharper or blunter (over `--corner-tol`, 25°) than in the reference | a terminal or join drawn differently in this master | repredict, or redraw the corner by hand |
| missing-extreme | a curve's leftmost/rightmost/top/bottom point has no node | in every master: drawn without extremes. In one master only: that curve bulges past its end node (a dent or dimple) | every master: `extremes` (adds nodes everywhere). One master: repredict or fix that curve's handles |
| short-segment | a segment under 2 units long | a stray node, or an ink trap on purpose | delete the node in every master by hand, unless it is an ink trap |
| tiny-contour | a contour with under 3 nodes or under 25 square units | a stray or leftover | delete it in every master by hand |
| semi-hv | a line or handle 1-2 units off horizontal or vertical (one finding per glyph, listing them) | a drawing slip | repredict when the other masters have it straight; otherwise snap by hand |
| zero-handle | a handle on top of its node | a dragged or deleted handle | by hand: give it a length, or make the segment a line |
| flat-curve | a curve whose handles lie on its chord | a straight segment drawn as a curve | `merge` turns it into a line when it is straight in every master |
| uneven-handles | the two handles of a curve are very unbalanced (Tunni ratio over 1.5) | one handle dragged | balance by hand (Tunni line), or repredict in one master |
| inflection | a curve bends both ways inside one segment | an S-curve drawn as one segment, or a slip near its end | by hand: add a node at the inflection |
| zone-miss | a top or bottom extreme 1-5 units off a blue zone or metric line | a drawing slip | snap by hand, or repredict |

## Curvature: how smooth the curves are

Combs make these visible: `render.py --comb`.

| code | looks like | likely cause | fix |
|---|---|---|---|
| curvature-step | the comb jumps at a smooth node: abs(k1-k2)/(k1+k2) over `--g2-tol` (15%). In the reference master it is one finding per glyph | handles of different tension either side of the node | `merge` often removes the node; `harmonize` evens it per master but costs `ratio-mismatch`; for one spot, `fair.py` over the two curves with `--ratio` as in the other masters |
| scallop | curvature dips or peaks at many smooth nodes (not at extremes) against the curves either side: a scalloped comb | too many points, or curves converted from TrueType | `merge` |
| lump | a curve whose curvature rises and falls more than the same curve in the reference master | a misplaced handle in this master | repredict, or `merge` |
| converted-quadratic | many curves have both handles at exactly 2/3 of the way to where they meet | the outline was converted from a compiled TrueType font | `merge` |
| excess-nodes | nodes that could each go with the curves moving under `--merge-tol` (1 unit) in every master | too many points | `merge` |

## Across masters: how points move from weight to weight

| code | what it means | fix |
|---|---|---|
| handle-flip | a handle swings to the other side of its curve in one master, against the trend of the others (a steady rotation across weights is not reported) | repredict that handle in the master named |
| tension-jump | one master's handles are much longer or shorter than the trend of the others (the weight named is the odd one) | repredict both handles of that segment in that master, or balance them by hand |
| alignment-break | a line or handle that is exactly vertical or horizontal in the other masters is slanted in this one | repredict the point, or snap it by hand |
| ratio-mismatch | a smooth node sits at a different point between its handle tips in each master while the curve turns: interpolation kinks there (see it with `between.py --raw`) | `triplet-ratio`; in a master being edited by hand, `fair.py --ratio` with the other masters' split |
| motion-bend | a point's path through the masters bends more than its neighbours' paths | look at `render.py --overlay`. One master's point off: repredict it. Many points bend together: that is the design's progression, leave it. After `merge` it rises (on one family 81 to about 300): the handles of the longer curves are fitted per master, so their paths bend more while every weight stays smooth. Judge those by the derived weights' audit and combs |
| stroke-progression | a stroke gets thinner as the weight goes up | check the render; often a scan hitting a different part of the glyph |

## Derived weights compared with the reference master

These appear only for UFOs passed with `--derived`. They name what extrapolation
broke. Trace each one back: render with `--overlay`, find the master whose point
moves against its neighbours, and fix that master. Only when every master is
clean and the problem stays is it a limit of extrapolation (see SKILL.md).

| code | looks like | fix |
|---|---|---|
| direction-flip | a stroke or counter turned inside out (thin weights: stroke width went below zero; heavy: counter closed) | target stem too far: lower it, or draw that part by hand in the promoted master |
| segment-reversal | a barb or spike: a segment runs backwards | trace to the master points at both ends; repredict, or fix the promoted master by hand |
| segment-collapse | a segment shrank to nothing | as segment-reversal |
| not-derived | the derived glyph is identical to one master: it was copied, usually because the masters were not compatible | fix the masters' structure, then derive again |
| handle-reversal | a curl: a handle flipped direction | trace to the master whose handle moves against the others |
| inflection-new | a wobble: a curve gained an S-bend | as handle-reversal; check tension-jump in the masters |
| thin-stroke | a stroke thinner than `--min-stroke` (default 0.8% of the em): usually a tapered stroke (the stem of !, the R inside ®) extrapolated to a hairline | `contrast.py` (Light's proportions at Thin), else thicken it by hand in the promoted 100 master |
| crossing-shrink | a part that crosses another (the bar of ð, the stroke of $, a crossbar) sticks out on one side by under a third of what it does in the reference: it slid into the stroke it crosses | a free bar crossing one stroke: `contrast.py` slides it back to the master's overhangs; otherwise move the part back by hand in the promoted master; with an earlier hand-drawn extreme the user trusts, `carry.py` |
| stroke-ratio | a lighter derived weight (Thin): a stroke under 70% of the nearest master's scaled by the stem ratio, on a grid of scanlines. The crossbar of f and t, the bars of € and $, the end of the stem of ! | strokes that grow faster than the stem across the masters (a Bold crossbar 2.3 times Light's while the stem grows 1.9 times) extrapolate to almost nothing | `contrast.py` (sets each stroke to the nearest master's times the stem ratio), else by hand in the promoted master |
| stroke-progression (derived) | a heavier derived weight (Black): a stroke thinner than in the nearest master | the spine of s, a bar whose master trend turns over | by hand in the promoted master; `carry.py` when the old glyph is better |
| parts-close | separate parts (the dots of a dieresis, the letters of ™) under 3% of the em apart in a derived weight, when the nearest master keeps them at least half as far again apart | the parts grow toward each other with weight | side by side: `contrast.py` moves them apart and widens the glyph; otherwise by hand |
| edge-turned | a straight edge that is upright or level in every master (a stem's side, a bar's top) isn't any more in a derived weight: a leaning stem, a tilted bar. Extrapolation keeps such edges as they are, so the cause is a later step that moved one end of the edge | a step that moved points in the derived weight (on one family the first contrast step: N, M and 4 leaned) | undo that step for the glyph; `contrast.py` rejects any change that adds one |
| stroke-wedge | the two sides of a straight stroke are parallel in every master but not in a derived weight: the stroke thickens toward one end (by over 3 units and 12%) | a step that moved one side of a stroke at one end (on one family the first contrast step: the bars of Z, 2, z, 7); now and then extrapolation itself, where the stroke turns between the masters (the arms of * at Thin) | undo the step for the glyph; from extrapolation, by hand in the promoted master |
| overhang | ink passes the origin or the advance width by over 10 units on a side where every master keeps a side bearing: it runs into the next glyph | a free bar that slid along the stroke it crosses and grew longer (the bar of ð at Thin, 29 units past): `reshape.py bar-place`; otherwise widen the glyph or move the part by hand; with an earlier hand-drawn extreme the user trusts, `carry.py` |
| counter-tight | a counter narrower than `--min-counter` (default 1% of the em). A scan that only grazes the tip of a V or of a counter (the gap closes a little to one side and opens wider to the other) doesn't count | open the counter by hand in the promoted 900 master; with an earlier hand-drawn extreme the user trusts, `carry.py` |
| stroke-uneven | weight shifted along a stroke: measured across the stroke at every node and curve middle against the nearest master's same spot times the stem ratio, at least 3 spots and a tenth of the glyph off its own median by over 20% (and 3 units); slows from 15% of the spots. Dots are left out. On one family at Thin: the S's spine x1.3-1.9 and its upper-left curve x0.53, the arm of r x0.6, the bowls of 3 | the drawn masters' nodes sit at different places along the curves (extrapolation moves weight along the stroke), or a stroke that grows faster or slower than the stem in places | a single open stroke (S, s): `reshape.py rebuild-stroke --centre ref --keep-limits`; a stroke under a zone line (the arm of r, a hook under the ascender): `reshape.py upright`; the inside of a bend not parallel to its outside: `reshape.py offset-inner`; elsewhere `reshape.py strokes` on the spots; the lasting fix: the same nodes in the same places in every drawn master |
| stroke-weight | a lighter derived weight (Thin): a glyph's strokes evenly too heavy or light, the median of its spots over 20% off the nearest master times the stem ratio. Dots are left out | accents, cedillas and other marks whose strokes grow slower than the stem in the masters, so extrapolation thins them less (one family's Thin: circumflex.case, tilde.case and cedilla x1.42) | `reshape.py inset` (single strokes; `--keep-edge` for the line the mark sits on); chevrons (circumflex, caron) `reshape.py chevron`, since inset thins the apex too much |
| copy-drift | a glyph that is another glyph moved sideways in every master (tabular figures, .case forms) is not, by over 3 units, in a derived weight | the two were extrapolated by different methods (derive.py picks one per glyph): one family's two.tf at Thin, its foot 27 units off two's | `reshape.py copy-sync COPY=BASE@WEIGHT` |

## By eye: what no code flags

A designer found these in one family's Thin after the audit was clean (0 blocks), the last
two in the tip of &'s counter in Bold and Black. Look for them in filled renders
(`solid.py`, with a window on each crossing and join) and measure with `widths.py`, or
`profile.py` where a straight edge meets a curve; `stroke-uneven` catches only the larger
ones.

| what you see | usually | fix |
|---|---|---|
| a stroke narrows (pinches) as it runs into a crossing or join | the master thins it there (Light's & loop, 53 to 47 into its crossing): fine at Light, a pinch at Thin; at a three-way join the master's centre line, seen from one edge, is dragged into the junction | `reshape.py rebuild-outline G@W --smooth-centre --fill-crossings` |
| a stroke that passes under another doesn't line up on both sides of it (steps), or flares or bends just before it | each side of the crossing rebuilt on its own | `rebuild-outline --fill-crossings` carries a turning stroke through as one (one centre line both sides, bridged by a curve matching both) |
| small lumps on an edge near a crossing | the master's centre line bends a few degrees there (& in Light: 5° and 9°); at Thin the same bends show | `rebuild-outline --smooth-centre` |
| a lump or blunt step at the inside corner of a crossing | a short piece at the corner placed whole when it is part of the edge it runs on | `rebuild-outline` rebuilds such pieces with their edge |
| the parts of a glyph don't line up across a bar or slash (¢'s bowl either side of its bar) | the master's own parts don't quite line up there either | `reshape.py union G@W --part P` when the glyph is drawn as another glyph plus a band (¢ = c + bar), after fixing P |
| a barb or curl at a terminal of a C-like stroke | extrapolated terminal pieces | `rebuild-outline G@W --smooth-centre` |
| a stroke tapers or curls into its end cut (the foot of 9) | extrapolation, or a rebuild measuring past the stroke's end | `rebuild-outline` (keeps the width from just before the cut) |
| a symmetric glyph heavier on one side (C lower-left), or overshooting its sibling (c past o) | a rebuild's direction estimates at nodes, or its proportions fitted to the derived glyph | `rebuild-outline ... --keep-limits left,right,top,bottom`; check mirrored ink runs |
| a dip or S-bend where a straight edge meets a curve (a counter's tip at a heavy weight) | an end node of the edge moved across it, with its handle, so the curve beyond bends; about 2° against the curve read as a dip in Black & | measure the edge with its curve with `profile.py` (any turn back is a dip); fix with `straighten.py --aim`, the ends sliding only along the outline (`--slide`) |
| a straight edge whose nodes or short handles bend after rounding (Bold &'s tip: 12° and 18°) | nodes and handles a fraction of a unit off the line; a copy scaled with `copy-shape --similar` and rounded to whole units brings 8–10° bends back | `straighten.py`: every node and handle of the edge on one whole-unit line |
