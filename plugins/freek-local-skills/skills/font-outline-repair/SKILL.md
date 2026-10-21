---
name: font-outline-repair
description: Audits and repairs the outlines of a weight family's UFO masters: mismatched or surplus points, kinks, bad corners, lumpy or flat curves, and the curls, barbs and uneven strokes that appear when Thin and Black are extrapolated from the drawn masters. Use to audit, fix, reduce points in, compare or re-derive weight masters from a .designspace or UFOs, to regenerate Thin and Black and check the built statics and variable font, or when derived weights look broken or their letters collide. Not for kerning or spacing design, hinting or drawing new glyphs.
---

# Font outline repair

Hand-drawn weight masters rarely match point for point. Small differences that look
fine in each master grow when you interpolate, and grow much more when you
extrapolate a Thin or a Black from them. This skill finds those differences, fixes
the mechanical ones, proposes the ones that need judgement, re-derives or re-checks
the extreme weights, and repeats until the checks are clean or only design decisions
are left.

Scripts, in `${CLAUDE_SKILL_DIR}/scripts` (each explains itself with `--help`):

| script | does | writes |
|---|---|---|
| `audit.py` | finds structure, shape and motion problems in masters and derived weights | a report (`--json`, `--md`) |
| `fix.py` | applies named fixes the same way in every master, including point reduction | UFOs, only with `--write` or `--out-dir` |
| `derive.py` | builds extra weights (100, 900) from the masters | new UFOs, optionally a designspace |
| `render.py` | draws glyphs across weights with nodes, handles, findings and curvature combs | a PNG |
| `compare.py` | checks that a step changed only what it should: visible shape, corners, contours, widths, anchors, glyph by glyph between two versions | a summary, `--json` |
| `beforeafter.py` | a high-resolution before/after sheet of every changed glyph; `--overlay` puts an old weight and its regeneration on top of each other, and `--ref` adds the nearest drawn master as a green line (which of the two follows its shape); `--overlay-nodes --comb` puts both versions' nodes and curvature combs in one cell (for point reduction: easier to read than side by side) | a PNG |
| `contrast.py` | gives a derived Thin or Black the stroke proportions of its nearest master (Light at Thin, Bold at Black) | UFOs in `--out-dir` |
| `reshape.py` | after the contrast step: repairs single glyphs of a derived weight against its nearest master (a stretch copied from the master, a stroke or a whole glyph with crossings rebuilt about the master's centre lines, the inside of a bend offset from its outside, evenly too heavy marks thinned, drifted copies re-synced, ...); an op that adds blocks or a self-intersection, or a flat spot in `rebuild-stroke`, isn't written without `--force` and exits 1 | the derived UFOs, only with `--write` |
| `solid.py` | glyphs filled black and large, versions or weights side by side, whole or a window on a crossing or join: how a reader sees evenness, pinches, lumps and alignment | a PNG |
| `widths.py` | a derived glyph's stroke widths against the nearest master x k: disc widths per segment (hold at crossings), or widths square to the edge along a stretch | a table |
| `straighten.py` | puts every node and handle of the straight edges running into a point (a counter's tip) on one whole-unit line each, so they stay straight after rounding; `--aim`, `--slide` and `--move` for edges too short for their step, `--dirs` to take the nearest master's steps, `--max-back` refuses edges that turn against the curve they run into; `--between 'C:A>B'` any straight run between two nodes, its points evenly spaced on whole steps (refused when the run has more points than steps) | the UFO, only with `--write` |
| `profile.py` | how much a stretch of outline turns, how much of that turns back against the main turn (a dip, an S) and its sharpest turn per unit, per UFO; `--curves` adds each curve's curvature (start, least, peak, end) and the jump at each node: a knee, a flat spot | a line per UFO |
| `fair.py` | re-places one or two curves' handles (and the node between) in whole units for even curvature, keeping the directions at both ends; `--edge` lets the end of a straight edge move back so the curve starts gently, `--ratio` keeps the node between split as in the other masters | the UFO, only with `--write` |
| `corner.py` | fairs a small round corner of one to four curves where `fair.py` finds no layout (an edge with a long whole-unit step, such as (73,-3); three curves): the handle at the edge may turn a few degrees off it (`--corner`), `--slide` starts the corner further back along the edge | the UFO, only with `--write` |
| `interpolate.py` | rebuilds glyphs of a drawn middle master on the line between its neighbours at the glyph's own weight fraction, keeping width, left side bearing and zone lines | the middle UFO, only with `--write` |
| `between.py` | glyphs at weights between the masters, rounded as in a static instance (halves up, as fontmake) or `--raw` as the variable font draws them, and the bends no master has | UFOs per weight |
| `carry.py` | takes the glyphs a derived Thin/Black can't get right from an earlier version of that weight, when the user says that version can be trusted | UFOs in `--out-dir` |
| `checkbuild.py` | checks built fonts: against the previous build, stems per weight, variable font instances against the statics | a summary |
| `waterfall.py` | every built weight in a line of shaped text, beside the previous build | a PNG |
| `kern_floor.py` | keeps a derived weight's pairs apart: none closer than `--floor` (10) units, or than at the nearest master where that is closer, at the derived weight and at the weights between; adds glyph-pair exceptions to every master, only the derived one's opened | the UFOs, only with `--write` |
| `pairs.py` | every pair shaped with HarfBuzz in each built static: the pairs that touch, and beyond `--ref` the pairs closer than `kern_floor.py` allows | a summary |
| `glyphmap.py` | one HTML page of every glyph at every built static weight for the designer: zoomable, filled or nodes, metric lines, the previous build as an overlay and a "changed" filter | an HTML file |

`audit.py` exits with code 1 when it finds blocks, and `fontTools.varLib.interpolatable`
when it reports anything, so don't chain them with `&&`. In derived weights it also
measures each stroke all along its length against the nearest master times the stem
ratio (`stroke-uneven`, `stroke-weight`, and per straight stroke `stroke-off`), compares the
same stroke across sibling glyphs (`stroke-sibling`), finds inside corners extrapolated onto the
outline (`counter-needle`) and shifted copies that drifted apart (`copy-drift`); `--no-evenness`
skips the first three. `audit.DerivedChecker`, which
`contrast.py` and `reshape.py` use to choose between versions, leaves them out unless
asked (`evenness=True`), so the evenness checks don't steer which version those steps keep. What each finding code means and how to fix
it is in `${CLAUDE_SKILL_DIR}/references/issue-codes.md`; read it before reporting.
Which established tools check what, with their thresholds and sources, is in
`${CLAUDE_SKILL_DIR}/references/checks-and-sources.md`.
What each step did on one typeface project, and the attempts that failed, is in
`${CLAUDE_SKILL_DIR}/references/case-notes.md`; the steps below point to its sections.

## Rules

- The user's own rules for outlines come first. Look for them in the repo's `CLAUDE.md`, `AGENTS.md`, README and docs (files about outlines, findings or defects), and quote them in your report. Without any, use: no jumps in thickness along a stroke, no barbs or curls, curves as smooth as real arcs with no more points than they need, crossing strokes line up on both sides.
- What decides whether a fix stays: `audit.py` before and after, and enlarged renders with curvature combs, checked by the reviewer subagent. A repo's own check scripts (often under `scripts/check/`) are at most a second opinion: run them only if the user wants, and don't keep or revert a fix on their word alone, since such scripts can miss problems or report false ones.
- One master is the shape reference. Use the one the repo's notes name; otherwise ask the user which master is drawn best. Pass it as `--ref` to `audit.py` and `fix.py`. `fix.py` never moves its points.
- Change as few masters as possible. When the extreme masters (Thin, Black) are masters that were derived and the others drawn, fix with `--only 100 900` first; touch drawn masters only for structure fixes or after the user agrees.
- Work on a git branch. Change masters only after the user's go-ahead for that kind of fix, and approve `repredict` per point list after showing a close-up of each point.
- Record each approved hand edit to a drawn master as a script that lists every moved point, old and new, and checks the old values before it writes. The rebuild then starts from the masters as found, and the record says exactly what moved.
- Look at every changed spot in an enlarged render before calling it fixed. The checks find spots; the picture decides.
- Never call an audit block a false positive without a filled, enlarged render of it (`solid.py`, a window on the spot) beside the nearest master. On one family a `segment-reversal` dismissed from the point view was a real fold.
- Check each writing step before the next one: `compare.py` against the version before it (every master within `--tol`, no corner lost, widths and anchors unchanged), then `audit.py`. Trust a clean result only from a check you have seen catch a known case: the first `compare.py` sampled straight lines only at their ends and reported a 25-unit change that wasn't there, and boolean path operations report large differences between outlines that are the same to within a unit.
- Ask how existing extremes were made before relying on them. A Thin or Black in the repo may have been drawn by a person, or extrapolated and patched by scripts; only the first records a designer's decisions. On one family they were an earlier automated attempt, and treating them as hand-edited sent 46 glyphs down the wrong path. Use them to compare against, and as a source (`carry.py`) only when the user says so.
- Tag the masters as found before the first write (`git tag outline-repair-baseline`). Every later comparison, and `carry.py --before`, needs them, and `HEAD~1` stops being the original after a few commits.
- Check the final output. Saving whole units, a build, or a later script pass can undo an earlier fix, so audit again after the last step.
- Do not commit, push or replace the user's build output without a go-ahead.

## Setup

Use a virtual environment; recent Ubuntu and WSL refuse a system-wide pip install.

```bash
python3 -m venv ~/.venvs/fontrepair
~/.venvs/fontrepair/bin/pip install -r "${CLAUDE_SKILL_DIR}/requirements.txt"
```

Skip this when `~/.venvs/fontrepair` exists. If the repo has its own venv with
these packages, use that instead.

## 1. Start

From the repo root:

```bash
git switch -c outline-repair            # or reuse the branch of an earlier round
export PYTHONDONTWRITEBYTECODE=1        # no __pycache__ next to the repo's own scripts
PY=~/.venvs/fontrepair/bin/python
S="${CLAUDE_SKILL_DIR}/scripts"
DS=sources/Family.designspace           # the designspace the build uses
REF=300                                 # the shape reference master (see Rules)
ONLY="--only 100 900"                   # situation B: masters fix.py may move; empty in situation A
mkdir -p outline-repair
```

- Find the designspace the build uses (README, `build.sh`, Makefile, gftools `config.yaml`). Every UFO it lists is a master. When there is no designspace, use `weight=path.ufo` pairs wherever these steps say `"$DS"`.
- Compiled fonts (`.ttf`, `.otf`, variable) are for the final check only. With no UFOs, stop and ask for them: outlines taken from compiled fonts have lost their smooth flags, and TrueType ones their cubic curves. `.glyphs` sources: convert with `glyphs2ufo` into a scratch folder and say that the fixes then live in UFOs.
- Only the weight axis is handled; sources off the default of other axes are skipped.
- If the audit reports `converted-quadratic` (or the repo's history says the sources were rebuilt from compiled fonts), expect dense points and scalloped curves in every master, the reference included. Point reduction (`merge`) is then the first fix after structure; until then, judge the other masters against the reference, not against an ideal.
- Check what the user says against the repo: if they name other weights than the designspace has, say so and go by the designspace.
- To regenerate the extremes from the drawn masters only (Thin and Black already in the designspace): copy the designspace next to the drawn UFOs, drop the 100/900 sources, and clear each kept source's `path` (`s.path = None` in designspaceLib) so its filename resolves next to the new file rather than at the old location. Keep the old Thin/Black to compare against, and the stems they were made at as a first guess for the targets.
- Decide which situation you are in:
  - **A. Extremes not yet masters.** The drawn masters are the masters; earlier 100/900 attempts are separate UFOs. Audit them as `--derived`.
  - **B. Extremes already masters.** Thin and Black are in the designspace, derived once and edited since. The audit of all masters together is the main one: its table and worst glyphs go in the report. Run a second audit with only the drawn masters plus `--derived 100=Thin.ufo 900=Black.ufo` and take only its derived-weight findings from it (blocks there are curls and barbs the extremes added). Ignore its findings on the drawn masters: with three masters, which one is the odd one out is a guess.

## 2. Baseline

```bash
$PY $S/audit.py "$DS" --ref $REF --json outline-repair/round0.json --md outline-repair/round0.md
$PY -m fontTools.varLib.interpolatable "$DS" > outline-repair/interpolatable0.txt
```

In situation A add `--derived 100=path/Thin.ufo 900=path/Black.ufo` to the audit. In
situation B add the second audit described above (`--json outline-repair/round0-extremes.json`).
Add `$ONLY` to the audit too, so the summary's repredict list leaves out the masters
fix.py won't change.
If the user wants their own check scripts as a second opinion, run them too and save the
output as `outline-repair/repo-checks0.txt`.
`interpolatable` is a cross-check of structure only: it tests midpoints between
masters and skips nodes that are not smooth in both, so it cannot see extrapolation
problems.

Render the worst glyphs from the summary, four per sheet so the labels stay readable:

```bash
$PY $S/render.py "$DS" --glyphs S dollar ampersand at --overlay \
    --report outline-repair/round0.json --out outline-repair/round0-worst-1.png
```

Read every sheet yourself (Read tool). For a spot that is too small to judge, zoom
in with curvature combs: `render.py "$DS" --zoom S:0:12 --comb --report ... --out ...`.
A smooth comb edge means a smooth curve; a step or dent in it is a kink, lump or flat spot.
A burst of comb lines at a tiny deliberate corner rounding is normal.

Get the numbers the report needs:

```bash
$PY $S/fix.py "$DS" --ref $REF $ONLY --ops redundant compat smooth-flags collinear   # dry run: "## totals"
$PY $S/fix.py "$DS" --ref $REF --ops merge                                            # dry run: nodes that can go
$PY $S/derive.py "$DS" --targets 100 900 --dry-run                              # situation A: stem guesses
```

## 3. Report and ask

Send this, then wait:

```
Audit of <family>: <N> glyphs, masters <list>, derived <list or "none">, reference <REF>.
Your rules I'm checking against: <quoted, or "none written down; using the defaults">.
Stems (glyph n): <weight=units, ...>

| severity | count | main codes |
| blocks | ... (<k> in derived weights) | ... |
| slows | ... | ... |
| minor | ... | ... |
Points: <N> nodes in the reference; <k> could go within 1 unit in every master (merge dry run).
<If converted-quadratic findings: "Many curves are TrueType quadratics in cubic form: the
outlines were converted from a compiled font, which explains scalloped curves.">
Repo checks (only if run): <name: count per class>.

Worst glyphs: <list>. Renders: <paths>.
What I saw in the renders: <one line per glyph that looks wrong>.

Mechanical fixes possible (from the dry run): <per op: glyphs changed, lines to look at>.
Points one master has wrong (from the audit summary): <up to 10, glyph:master:contour:point code>.

Decisions:
1. Go ahead with the mechanical fixes (redundant, compat, smooth-flags, collinear), limited to <masters>?
2. Reduce points with merge? It removes the same nodes from every master, the reference too,
   moving curves at most 1 unit (or another tolerance), and keeps corners and extremes.
3. Also triplet-ratio (slides nodes to dekink interpolation) and/or extremes (adds nodes)?
4. Situation A only: target stem for 100 and 900 (glyph n): keep your current ones (<a>/<b>),
   the geometric guess (<c>/<d>), or other numbers?
```

When there are no findings, say "No findings" and list what was audited.

Skip decision 4 when the audit marks a derived weight's stem "copied, not derived":
that UFO's `n` was copied from a master, so its stem says nothing; ask for a number.

## 4. Repair loop

Name rounds `roundK` (K = 1, 2, ...) and keep each round's JSON, check output and PNGs
in `outline-repair/`.

1. **Mechanical fixes**, as approved. Structure first, then point reduction (it changes every master, so no `$ONLY`), then the rest:
   ```bash
   $PY $S/fix.py "$DS" --ref $REF --ops redundant compat --write
   $PY $S/fix.py "$DS" --ref $REF --ops merge --write                    # if approved; --tol to change the 1-unit limit
   $PY $S/fix.py "$DS" --ref $REF $ONLY --ops smooth-flags --write
   $PY $S/fix.py "$DS" --ref $REF $ONLY --ops collinear --write          # situation B: --out-dir <scratch>, then the guard below
   ```
   Leave `$ONLY` empty when the user approved changes to every master. Lines marked `<- look` go on the list for step 3. Merging first means the later fixes work on fewer, cleaner curves. `merge` fits each new curve in all masters at once, with shared parameters, against the original outline, so it also stays within `--tol` at every weight in between, not only in the masters; and it rounds handles keeping their direction, since plain rounding kinks short handles. It keeps a node that is an extreme in any master, the derived ones in the designspace included: a tangent along x or y, or the node more than `--tol` past both its neighbours (a derived Black's arch top, its tangent a few degrees off the axis, went and the curve bulged 5.4 units past its ends).
   - **Before `merge`**, look for repo scripts that build glyphs from other glyphs' points by position (`contours[i].points[k]`, an on-curve list indexed by number; often under `scripts/glyphs/`), and list their input glyphs. Merge changes the numbering, so leave those glyphs out (`--glyphs` with every other glyph) or, after the merge, run the repo's regeneration and `compare.py --tol 1` the generated glyphs against before. On one family `Œ` came out 5 units off in every master and Black `ð`'s bar 20, until `O` and `o` were left out.
   - **`collinear` in situation B** needs the same per-glyph guard as in derived weights: run it with `--out-dir <scratch>`, and keep it per glyph and master only where `audit.DerivedChecker(drawn masters, (weight, font)).score(glyph)` doesn't get worse, `compare.py` stays within `--tol` and no corner is lost. Across all of Thin and Black it moved 16 Thin glyphs more than 1 unit (q by 3.4) and smoothed deliberate 10–11° corners away; guarded it kept 20 Thin and 37 Black glyphs, all fine.
2. **Check.** With an old copy of the masters (`git worktree add ../before outline-repair-baseline`):
   ```bash
   $PY $S/compare.py ../before/sources/A.ufo sources/A.ufo ../before/sources/B.ufo sources/B.ufo --tol 1
   $PY $S/beforeafter.py ../before/sources/A.ufo sources/A.ufo --comb --out outline-repair/roundK-A.png
   ```
   Re-run `audit.py` and compare with the previous round per glyph. To check the weights in between, interpolate a few instances (350, 500, 600) from the old and the new masters (`between.py`) and run `compare.py` and `profile.py` on those too. Keep a change only where the after outline is the same shape or smoother; otherwise `git restore` those `.glif` files and note why.
3. **Judgement fixes.** Take the audit summary's "Points one master has wrong", the blocks from the extremes audit and the `<- look` lines. Zoom on each (`--zoom glyph:contour:point --comb`). A curl or barb usually involves several neighbouring points, so give `repredict` a range around the spot and run it without `--write` first:
   ```bash
   $PY $S/fix.py "$DS" --ref $REF $ONLY --ops repredict --points R:900:0:6-9 e:900:0:85-88
   ```
   It moves only points more than `--min-dev` (3) units from where the other masters put them. A range is measured from the two points just outside it (several ranges in one contour each from their own), so the master keeps its own placement of that part and only the shape is restored; a single point follows its own trend; coordinates every other master shares (a baseline, a stem edge) stay exact. Propose the list with one line each on why, get the go-ahead, then add `--write`. It re-lines the handles afterwards. Findings in the reference master are listed separately in the summary: fix.py won't move them, so show them to the user. Structure findings left over (`point-count`, `point-type`, `contour-count`, `component-mismatch`) need a hand edit: say which contour and master differ and ask the user to fix it in their editor, or offer a small script.
4. **Derive or compare.**
   - Situation A: `derive.py "$DS" --targets 100 900 --stems 100=<a> 900=<b> --out-dir outline-repair/derived` (or `--stems-from` the old Thin/Black), then audit with `--derived` on the new UFOs. Masters are placed by measured stem width. Each glyph's outline uses whichever of piecewise (nearest two masters), fit (least squares through all) and wide (the two outermost: least amplification) gives the fewest blocks, then slows; widths, side bearings, kerning and font metrics follow one method across the font (wide), or related glyphs drift apart (on one family the two braces ended 12 units apart at Thin). Coordinates round with handle directions kept (kinks 205 to 148 against plain rounding), and the new UFOs get their names from the designspace's axis labels. On a test family, extrapolating by the weight number instead missed the real ExtraLight and Black by 6 to 16 units on average (43 at worst); placing by stem missed by under 1 unit on average.
   - Choose the target stems by trying a few: derive at each and count the audit's blocks in the derived weights. Report the choice and the alternative. An example with numbers is in `${CLAUDE_SKILL_DIR}/references/case-notes.md`.
   - **Contrast step**, after deriving (situation A):
     ```bash
     $PY $S/contrast.py --masters 300=sources/A.ufo 400=sources/B.ufo 700=sources/C.ufo \
         --derived 100=outline-repair/derived/F-100.ufo 900=outline-repair/derived/F-900.ufo \
         --ref $REF --out-dir outline-repair/contrast
     ```
     Strokes that grow faster than the stem across the masters shrink faster toward Thin (on one family the crossbar of f went to 9 units where Light's proportions give 18), and corners where strokes meet overshoot (v's crotch went below the baseline, N's notch to the baseline, the counter of 4 through the cap height). The contrast step keeps each stroke where extrapolation put it and first sets its thickness from the nearest master times the stem ratio. It then checks the joins on the result: where one is still collapsed it moves the whole stroke that meets it (both sides by the same amount, turning about its far end), or at a crotch both strokes, so the corner gets the master's depth times the ratio without any stroke getting heavier. At Thin that is "Light's contrast", which is what that family's designer had chosen; at Black (mode floor) it only stops strokes from getting thinner than in Bold, since scaling everything up closes dots and counters. Separate parts that closed up (the T and M of ™, the rings of ‰) are moved apart to the master's gap and the glyph widened by as much: a spacing change, so it goes in the report. A part that runs into the counter around it (the R of ® at Black) is scaled down until it clears it as in the master, and a free bar that slid off-centre on the stroke it crosses (ð at Black) slides back to the master's overhangs. Each glyph keeps the change only when the audit's derived checks don't get worse and no stem leans or stroke tapers more than before.
     Each earlier version of this step made glyphs worse in a way the audit now flags (`edge-turned`, `stroke-wedge`, strokes heavier than their neighbours, collapsed crotches); `${CLAUDE_SKILL_DIR}/references/case-notes.md` says which and why. Read it before changing `contrast.py`.
   - **Line up handles in the extremes** after the contrast step: `fix.py ... --only 100 900 --ops collinear --out-dir <scratch>`, then keep it per glyph and weight only where `audit.DerivedChecker(...).score(glyph)` doesn't get worse. On one family it cut kinks from 40 to 32 at Thin and 67 to 46 at Black; applied to every glyph it also added inflections and long handles in some (inflection-new 18 to 22 at Thin), which the per-glyph check keeps out.
   - **What's left, glyph by glyph** (`reshape.py`). After the contrast step the audit's derived findings, the designer's eye and the reviewer still find single glyphs that are off. Fix them in the derived UFOs with `reshape.py`, one call per glyph and spot, and keep the calls in one script (a recipe) that you run again after every derivation, since a new derivation undoes them. Each call measures against the nearest drawn master times the stem ratio k and prints the derived checks before and after; look at every result enlarged (`beforeafter.py --overlay --ref`, `render.py --zoom --comb`) and keep it only when it looks right, even when a slow or two come in (the picture decides; a change that adds blocks goes: `reshape.py` won't write it without `--force`, and exits 1 so a recipe under `set -e` stops there). Ops that move handles try them translated, blended and scaled and keep the best by the checks.

     Organise the recipes by review round: one recipe per round, each run after the ones before it, and a folder per round with its recipe, a zip of the sources after it, the built fonts, the audit, the build check and the sheets the user judged. A rebuild script derives from the drawn masters and runs the contrast step, collinear and every recipe in order, with `kern_floor.py` last since it measures the final outlines; check that it reproduces the last round exactly before trusting it. After any change to `reshape.py` itself, run every recipe again from the start and compare each rebuilt glyph's checks and filled render with the round before: a fix aimed at one glyph can move others.

     | what's wrong | audit | op |
     |---|---|---|
     | a curl or dent a few units deep that `repredict` leaves (each point under its `--min-dev`) | kink, curvature-step at a terminal corner | `copy-shape G@W:C:A-B`: the points between two good nodes take the master's shape there. It refuses a stretch whose two axes would scale over 1.5x apart (ends nearly level: Thin e's bowl bottom went x0.54 up and through the counter); use `--similar` there |
     | a short straight segment turned round (a notch passing zero: the barb of an arrow whose shaft got as heavy as the head) | segment-reversal, corner-flip | `min-segment G@W:C:A-B --length L`: the master's direction, a few units long, the ends sliding along their other edges |
     | the inside corner of a crossing folds, or a bar's join with a bowl runs backwards: the corner where a straight edge meets a curve overshot the real meeting point, or the curve's last node lies inside the thinner stroke (& and ¢ at Thin) | corner-flip, handle-reversal, segment-reversal, segment-collapse, self-intersection | `junction G@W:C:J-K` (J on the straight edge, K the node on the curve side, either order): J onto the crossing with its corner kept, the short piece cut from the curve |
     | a straight bar or leg crossing curves is tapered or off its line, or a bar heavier than master x k | stroke-wedge, stroke-ratio, stroke-off | `bar G@W --edges ...`: both edges straight and parallel at the master's width x k, every join onto them; where a wall runs on across the bar (e's bowl), its straighter side continued places the corner on the other edge |
     | the same joins when they are only a few units off (¢ and $ at Black) | segment-reversal, corner-flip | `fix.py ... --only W --ops repredict --points G:W:C:A-B --min-dev 1`, one range per join. Check the bar afterwards: a join can move sideways and taper the bar, and a range over the bar's end can pull the bar in |
     | a barb or kink where a run of nodes is straight in the master (a node slid past its neighbour: & at Thin, 122 degrees) | kink | `copy-shape` over the run, from the node before to the node after |
     | the tip of a counter stepped or crowded (little pieces scaled with the stroke while the counter shrank: Black &) | kink, lump, by eye | `copy-shape G@W:C:A-B --similar` from a good node before the tip to one after: the master's tip turned and scaled whole |
     | a counter's tip whose straight edges bend or wobble after rounding (a heavy &) | kink, by eye | `straighten.py FONT.ufo G 'C:TIP>END' 'C:TIP<END'` (its own script, one run per edge from the tip): every node and handle of each edge on one whole-unit line; dry run first, then `--write`. An edge too short for its step: `--aim --slide S --move R`, and check the joins with `profile.py` |
     | a straight edge that meets its curve with a knee, a flat spot in a curve | curvature-step, by eye (`profile.py --curves`: a high peak right after the edge, a least near 0) | `fair.py FONT.ufo G 'C:A>B'` over the curve (or two curves and the node between, `--move R`); after a straight edge `--edge TIP:N` (an edge of one line segment too); in a master, `--ratio` as the other masters split that node |
| a small round corner off a straight edge that `fair.py` finds no layout for (every `--move`/`--dev`/`--turn`), or one of three curves | by eye, `profile.py --curves` | `corner.py FONT.ufo G 'C:A>B'`, `--slide N` when the corner is too tight for its turn (a Black {: 8 units back, curvature 8 -> 38 -> 0) |
| a straight run stored as a row of tiny curves, zigzagging at derived and in-between weights | by eye, curvature-step | `straighten.py FONT.ufo G 'C:A>B' --between`, in every master; refused when the run has more points than whole steps: remove points there first |
     | a corner bends the wrong way because the masters disagree there (€ at Black: Light +11°, Bold -1°, extrapolated -8°) | corner-flip | `copy-shape` from the nearest master around that corner |
     | a free bar slid along the stroke it crosses and grew past the advance width (ð) | overhang | `bar-place G@W --bar C --crossed C`: the master's place along the stroke and overhang |
     | parts identical in the master drifted apart (dieresis dots heavier than the i dot) | parts-close, by eye | `same-part G@W --part i:0` |
     | a shifted copy drifted from its base (tabular figures) | copy-drift | `copy-sync COPY=BASE@W` |
     | a mark evenly too heavy (accents, cedilla) | stroke-weight | `inset` (keep the line it sits on with `--keep-edge`, or `--seat bottom`); chevrons `chevron` |
     | a stroke too thin or heavy in places under a zone line (the arm of r, a hook under the ascender) | stroke-uneven | `upright G@W:C --nodes ...` |
     | stroke thickness off in places elsewhere | stroke-uneven | `strokes G@W [--nodes ...]` |
     | a stem's edges wander where the master's are straight | by eye | `follow-edge G@W:C:FIRST-LAST/BASE` |
     | the inside of a bend not parallel to its outside (a pointed counter, a thin shoulder) | stroke-uneven, by eye | `offset-inner G@W:C --inner ... --outer ...`; on a long bowl's inside first `fair.py` over adjacent pairs of its curves (`--move 3 --dev 2`): on Thin e's lower bowl `offset-inner` made it worse (case notes) |
     | weight shifted along a single open stroke and the outline lumpy (S, s) | stroke-uneven, folds | `rebuild-stroke G@W --centre ref --keep-limits`: the master's centre line on the derived proportions. A flat spot it makes between two bends (an arc's ends pulled in) stops the write: keep those nodes (`--keep-nodes`) and fair into them |
     | the same in a stroke with a junction or a second contour (the 3 with its bar, the hook of ? beside its dot) | stroke-uneven, folds, corner-flip | `rebuild-stroke G@W:C --centre ref --realign`, with `--sides A-B,C-D+E-F --keep-nodes ...` when the stroke has a third end: one side the whole outside, the other the inside in runs, the junction's nodes kept |
     | strokes uneven through a crossing or a join, after the spot fixes (&'s main crossing, a cent sign's bowl where the bar meets it, a C barbed at its terminals) | stroke-uneven, lump, curvature-step, by eye | `rebuild-outline G@W`, last in the recipe: the whole glyph about the master's centre lines at master x k, widths from the largest disc in the master's ink (they hold where strokes cross), corners where the rebuilt edges meet, end cuts as derived, the small pieces at corners the master's x k. At Thin add `--smooth-centre` (the master's wiggles, lumps at Thin) and `--fill-crossings` (the master's thinning into a crossing, a pinch at Thin; a stroke turning under another is carried through as one, so it neither pinches nor steps) |
     | a stroke pinched where it meets or passes under another, or out of line across it | by eye (`solid.py` window, `widths.py --along`) | `rebuild-outline G@W --smooth-centre --fill-crossings`, `--verbose` to see which edges it followed and carried through |
     | a glyph that is another glyph with a bar or slash over it (¢ = c + bar) and whose parts don't line up across the bar | stroke-uneven, by eye | `union G@W --part P`, after fixing P: P where the masters put it, united with G's straight band at master x k, G's points fitted onto the result |
     | a notch closed to a slit, or an edge dented where the master runs straight (a notch under a part that runs close to a ring), and `fair.py` finds no layout | kink, inflection-new, by eye | `copy-shape` over each spot, from good node to good node; it beat `rebuild-outline` and `fair.py` there (case notes) |
     | a part shrunk to fit inside another and now lighter than its sibling (the R of ® at a heavy weight) | by eye | design: thicken it to the sibling's weight and fit size and place, or leave it. Show the options with their numbers |

     Results per recipe on one family, and the reshape ops that made things worse (`strokes` at corner nodes, moving corner nodes one by one, `offset-inner` on a heavy hook, smoothing a derived centre line, another extrapolation method per glyph), are in `${CLAUDE_SKILL_DIR}/references/case-notes.md`: read them before trying an op on a stroke. A rebuild that follows the master can move a stroke end: `--keep-limits` keeps the bowls' extremes and overshoots, and the report says what changed.

     **Judging a derived weight by eye**, after the checks are clean (the cases behind each are in `${CLAUDE_SKILL_DIR}/references/case-notes.md`, "Judging by eye"):
     - Give the designer a glyph map of the build (`glyphmap.py BUILD --before PREVIOUS_BUILD --labels <old> <new> --out outline-repair/roundK-map.html`, the build from step 5): every glyph at every weight, zoomable, filled or as nodes, with metrics and the previous release as an overlay. Publish it or send the file, and ask them to go through every glyph. On one family every round had passed the audit and the reviewer and still had about 20 problems the designer found there (a barb at a bar end, joins pinched, a needle of counter, a bar lighter than its siblings); renders of changed glyphs alone miss what never changed.
     - Look at every changed glyph whole and enlarged, filled black (`solid.py`, plus a window on each crossing and join), beside the nearest master. Barbs, crossings too heavy, pinches, lumps and parts out of line show there when combs and point views hide them.
     - Measure what you see (`widths.py`): disc widths per segment for the whole glyph, and widths square to the edge along the stretch in question. Use both: rays read a taper too large near joins, the disc misses a long gentle one.
     - Exactly master x k is not enough at Thin: the master's own thinning into crossings, wiggling centre lines and parts out of line across a bar scale with it and show. At Thin rebuild with `--smooth-centre --fill-crossings`.
     - A stroke that passes under another is one stroke: carry it through as one (both edges on one centre line) and let the other stroke cut it. Do it only where the stroke turns (over 20°).
     - Build a glyph the way it is drawn: a ¢ that is c plus a bar in every master is the derived c, moved by the masters' trend, united with a straight bar (`union`). Fix the part first.
     - When a fix keeps failing, ask the designer how they would draw it: their suggestions became the fixes.
     - Small pieces at corners: the master's piece x k is right for chamfers and terminal flares; a piece running smoothly on from an inside corner is part of that edge.
     - Check symmetry and siblings: mirrored halves of a symmetric glyph, overshoots against sibling glyphs (c with o, C with O; `--keep-limits left,right,top,bottom`).
     - Stroke ends: the foot or terminal should keep its width into the cut, not taper.
     - Straight edges into a curve: an edge must not turn back against the curve it meets (a dip, even at 2°), and the curve must start gently (`fair.py --edge`). Measure each edge with its curve in every weight (`profile.py`, and `--curves` for a knee).
     - An edit to one master must fit the others: keep how the other masters split a smooth node's handles (`fair.py --ratio`), check the weights in between unrounded (`between.py --raw`, then `profile.py`) and built (Medium, SemiBold), and use one construction in every weight.
     - Profile every curve of the glyph before showing a whole-glyph sheet, and say which faults were already in the drawing.
     - Read where a finding is before choosing the tool.
     - Measure strokes and gaps on flattened outlines (`fontlib.contour_polygon`), never on the point list. Fill renders by winding: even-odd shows overlapping parts as holes.
     - Test a recipe change from the state just before that step (`awk '/^r rebuild-outline/{exit} {print}' recipe.sh`): rebuilding an already rebuilt glyph isn't idempotent. Don't edit a recipe while it runs. On case-insensitive drives (Windows, WSL) outputs for c and C overwrite each other. Zip sources with Python's `zipfile`, not PowerShell 5.1's `Compress-Archive`.
   - Situation B: audit the drawn masters with `--derived` set to the current Thin and Black, and render the worst glyphs with `--overlay`.
   **Carry over from an earlier version** (only when the user says that version is trustworthy, for example drawn by hand). Some glyphs come out broken at Thin or Black whatever is done to them: the extremes then need a designer's decision, and an earlier hand-drawn Thin/Black may hold it.
   ```bash
   $PY $S/carry.py --masters 300=sources/A.ufo 400=sources/B.ufo 700=sources/C.ufo \
       --derived 100=outline-repair/derived/F-100.ufo 900=outline-repair/derived/F-900.ufo \
       --old 100=old/Thin.ufo 900=old/Black.ufo --before 300=../before/sources/A.ufo 400=... 700=... \
       --ref $REF --out-dir outline-repair/carried
   ```
   It takes the glyphs with blocks, or with more `crossing-shrink`, `overhang`, `thin-stroke`, `stroke-ratio`, `counter-tight`, `parts-close` or `handle-backward` findings than the old glyph, merges the `--before` masters and the old extremes together for those glyphs (so they stay compatible; they keep fewer points removed), derives them again, and per weight keeps whichever version is cleaner. Then look, and have the reviewer look: `compare.py old/Thin.ufo outline-repair/carried/F-100.ufo --json` lists every glyph's change; draw the ones that moved over 2 units with `beforeafter.py ... --overlay --glyphs ...`, and read the waterfall of the built fonts (step 5). Where the review prefers the old glyph and no check says so, run again with `--keep-old glyph@weight`. Run the other fixes the masters had after `--before` again for the carried glyphs.
   **Ask the reviewer to measure**, not only to look for kinks: strokes against the nearest master times the stem ratio, gaps between parts, the depth of joins. On one family a reviewer's first pass found a dozen glyphs that were lighter, collapsed or tighter than they should be while the audit was silent; that is how `stroke-ratio`, `parts-close` and the contrast step came about.
5. **Trace derived problems to masters.** In the overlay, the master whose point moves against its neighbours is the cause. Fix it there (step 3) and derive again. Never hand-edit a derived UFO that will be rebuilt; what can't be fixed in the masters goes in the `reshape.py` recipe (step 4), which is run again after each derivation.
6. **Review independently.** Give the round's sheets, filled renders and JSON to the `font-outline-reviewer` subagent (see below). Its "still wrong" and "new problem" verdicts are findings for the next round. Show the user the filled renders too, before and after with the nearest master: the designer's eye found what the checks and the combs didn't, and their suggestions became the fixes.

Repeat from step 2 until one of these holds, then go to step 5:

- No blocks, no slows that trace to a master point, and the reviewer sees no "worse" or "new problem".
- Two rounds in a row did not lower the blocks plus slows. Stop and report what is left.

**Optional fixes.** Offer `triplet-ratio`, `harmonize` and `--snap-handles` only as
separate choices, and keep them only where the audit and the renders improve: on one
family `collinear` cut more kinks than `triplet-ratio`, and `harmonize` after merging
made ratio mismatches worse. What each operation did there, with counts, is in `${CLAUDE_SKILL_DIR}/references/case-notes.md`.

**A drawn middle master off the line between its neighbours.** A repo's own check (say a
`masters.py` flagging Regular points off the Light–Bold line) can point at a middle master
whose glyphs drift. Fix it only with the user's go-ahead, and:

- Measure the line at the glyph's own weight fraction, not at the axis location: t = (stroke
  in the middle master − in the lighter) / (heavier − lighter), with `widths.py` on the
  glyph's strokes. On one family the axis said 1/4 and glyphs rebuilt there came out about
  5 units too light; stems wanted 1/3, the diagonals of v and w 0.36 (w at 1/3 came out 4%
  lighter than v).
- A whole-glyph rebuild (`interpolate.py LIGHT MID BOLD --glyphs G --t T`) keeps the advance
  width, left side bearing and nodes on zone lines (rebuilt tops landed at 466 against the
  x-height's 467). It worked for z, w, 4 and v.
- On dense, wiggly outlines (braces) a whole-glyph rebuild adds 5–11° rounding kinks: use
  `repredict` on the spot instead.
- Points on the line don't make the shape right. `repredict` on Regular `{` lined its points
  up and opened the notch from 95° to 104°, blunter than either neighbour, and it stopped
  mirroring `}`. Judge by the outline against its neighbours and its mirror or sibling
  glyphs (filled renders, `profile.py`), not by the point distances.

**Extrapolation limits.** Straight-line extrapolation overshoots wherever two edges
meet at a shallow angle (the crotch of v and w, the apex of the counter in 4: the
corner drops below the baseline or through the outline), where a handle or segment
that shrinks with weight passes zero (a curl or barb at a terminal), where a tapered
stroke thins to a hairline (!, the R in ®), where a stroke grows faster than the stem
across the masters and so shrinks faster toward Thin (the crossbar of f went to 9
units where 18 fits the weight), where a crossing part slides into the stroke it
crosses (the bar of ð), and where separate parts grow into each other (™, ‰, the dots
of ¨ at Black). The contrast step handles the thin strokes and the inside corners.

When the masters are clean and a derived weight still breaks after the contrast
step, offer: a less extreme target stem; promoting the derived weight to a master and
fixing those glyphs by hand there; or, if the user trusts an earlier version, `carry.py`.
Deriving the glyph at a closer stem rarely helps: in a line of text the heavier or lighter
glyph shows more than the small fold. The exception is a fold that shows at text size with
a clean stem close by: derive that glyph into a scratch folder (`--glyphs G --stems 900=<stem>`)
and copy it in, keeping the weight's advance width and left side bearing. What else was
tried and failed (crotches rebuilt from predicted angles, smooth flags on small-bend corners,
extrapolating from the nearest two masters, merging corner clusters) is in `${CLAUDE_SKILL_DIR}/references/case-notes.md`.

## 5. Promote and check the build

Situation A, once the user agrees the derived weights are good enough to edit as masters:

```bash
$PY $S/derive.py "$DS" --targets 100 900 --stems 100=<a> 900=<b> \
    --out-dir sources --designspace-out sources/<Family>-5masters.designspace
$PY $S/audit.py sources/<Family>-5masters.designspace --ref $REF --json outline-repair/final.json --md outline-repair/final.md
$PY -m fontTools.varLib.interpolatable sources/<Family>-5masters.designspace
```

After `contrast.py` (or `carry.py`), promote its `--out-dir` instead: copy its 100/900 in as
`Family-Thin.ufo`/`Family-Black.ufo` (and, after `carry.py`, its masters over the drawn
ones), next to a designspace with all five sources and the user's instances.

Keep the user's designspace until they agree to switch the build to the new one. A
variable font does not extrapolate: outside its outermost masters it renders like the
default master, so 100 and 900 must be masters before the axis reaches them.

Both situations: run the repo's build (its `build.sh` or equivalent) or, without one,
`fontmake -m "$DS" -i -o otf ttf --output-dir outline-repair/build` for the named
instances and `fontmake -m "$DS" -o variable` for the variable font. Then the final
audit and `interpolatable` once more on the masters as saved, and check the build
(`checkbuild.py outline-repair/build --before <previous build>`, then
`waterfall.py outline-repair/build --before <previous build> --out outline-repair/waterfall.png`):

- Same glyph order, cmap, names and OS/2 weight classes as the previous build; advance widths changed only where the report says.
- Each named instance of the variable font against its static TTF: densely sampled outline distance (on one family at most 1.6 units, composite rounding). Widths can differ by 1 unit at a weight exactly halfway between two masters, where every value ends in .5 and the two builds round it differently.
- Stems per instance (glyph n at half the x-height), to show the weight progression; the masters fix most of it, so propose an `avar` mapping only when the steps between named instances are clearly uneven.
- A waterfall of all instances before and after, rendered from the built fonts with kerning, read at text size.
- A glyph map of the build for the designer (`glyphmap.py`, step 4's "Judging by eye"), when the derived weights changed.
- Static instances between masters round every point to whole units, so short handles on a straight edge bend there however straight the masters are (an &, handles 5.7 units long: 7.1° at ExtraLight and Medium, 14.0° at ExtraBold). Check every in-between weight, between each pair of masters (`between.py`, rounded and `--raw`); the variable font isn't rounded that way. Say so in the report rather than chasing them in the masters: at a weight exactly halfway between two masters every odd difference rounds from a half (one 4.8° kink at ExtraBold `{`), and keeping coordinates the same parity as the other master to avoid it put 25° of turn back into Black.
- Pairs at a derived weight (`pairs.py BUILD --ref 700`, and `--ref 300 --side below` for Thin). From Bold to an extrapolated Black every gap shrinks by about the same amount (on one family: HH 117 to 102, nn 99 to 85), so letters that reach past their sidebearings and nearly touch in Bold run into each other at Black with no kerning involved (TT, WT, WW, LA, gj: 36 pairs in the regenerated Black, 66 in the release's). Measure clearance, not kern values. `derive.py` extrapolates kerning from the drawn masters only, so extra room a build pipeline gives the derived weight (brackets beside capitals: L before `].case` overlapped by 29) is lost as well. `kern_floor.py` opens them; the user picks the floor (one family chose 10 of 0 and 10 shown, a sheet of words such as LATTE, TWO, WWW, gjuha at each). A pair that touches in the master (WT, jj) stays as there. A gap isn't linear between two weights: outlines change shape (L's bar thickens up to a bracket's arm), so check the weights between too; it does. A static instance still rounds a pair a unit or two under the floor. Run it last in a recipe chain: it measures the final outlines.

## 6. Final report

```
Outline repair of <family>, <K> rounds, reference <REF>.

| | blocks | slows | minor | nodes |
| before (round0) | ... | ... | ... | ... |
| after (final) | ... | ... | ... | ... |

Changed: <masters touched, glyph count, ops used, repredicted points, glyphs reverted and why>.
New masters: <paths and target stems>, or "none". Carried from the old extremes: <glyphs, and why>.
Build: <statics and variable font, checks run, stems per instance>.
Left for a designer: <glyph: what and where, with render path>, or "nothing".
Renders: <before/after sheets>.
Branch <name>, not committed. Commit?
```

## Reviewer subagent

The reviewer judges the render sheets without your reasoning, so the fixes are not
graded by the session that made them. This plugin installs it as the subagent
`freek-local-skills:font-outline-reviewer`. If that type isn't available, start a
general-purpose subagent with the body of
`${CLAUDE_PLUGIN_ROOT}/agents/font-outline-reviewer.md` as its instructions.

Give it, besides the `render.py` sheet with combs and the audit JSON: `solid.py` renders
of each changed glyph (before, now, nearest master) with a window on every crossing and
join, the user's rules and remarks so far, the scripts folder (`${CLAUDE_SKILL_DIR}/scripts`)
and the Python to run them with, and a folder of its own to write close-ups in. It shares
your scratch space: on one family it overwrote two of the session's helper scripts with its
own of the same name. Run it in the background and keep working: a review of four glyphs
in five weights ran for a long time. Its verdicts are about the renders it was given,
so say which state they show when you relay them, and render again for it after later
changes.

## Not covered

- Spacing and kerning design (`kern_floor.py` only keeps a derived weight's pairs from colliding), hinting, OpenType features and naming.
- Axes other than weight.
- Designing glyphs; the skill repairs outlines that exist in every master.
