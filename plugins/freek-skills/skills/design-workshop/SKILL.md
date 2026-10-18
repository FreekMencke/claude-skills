---
name: "design-workshop"
description: "Works out the look of a new page, site or redesign with the person, who picks from small visual options one choice at a time, and ends with a design brief to build from. Use when asked to design or redesign a page, site or screen, to choose colours, fonts or a look, or when a design looks generic or templated. Not for building a chosen design, brief or mock-up in code: use frontend-design. Not for database, API or system design."
---

# Design workshop

Asked for a whole page, Claude converges on one look per subject, and a banned list or a set of proposed directions
only moves it to another one. A person picking from small visual options, one choice at a time, gets past that. This
skill runs those choices with the person and ends with a design brief. It builds nothing: the five pages it makes at
the end are throwaway prototypes for choosing.

Not this skill:

- Building a design that is already chosen (a brief, a spec, a mock-up): use `frontend-design` or the repo's own build
  workflow, with the brief as a fixed spec.
- A fix inside a design that stays, such as spacing or one colour's contrast.
- Database, API or system design.

## Showing options

- **Where.** When the session can publish artifacts (Claude Code signed in to claude.ai, claude.ai chat), show each
  step as a plain page artifact, not a Design canvas or template. Otherwise write each step as one self-contained HTML
  file and give its path to open in a browser. In a repo, keep these files out of the source tree.
- **No design system from the account.** For a new design it pulls every option toward that one look. On an existing
  site, the site's own CSS takes its place (see "Existing site").
- **A picks file** next to the step pages: for each step, every option shown (number and name) and the picks in the
  person's words. Read it before each step, so a long, compacted or resumed session repeats no option and keeps the
  picks as given.
- **One page per step**, its options side by side, wrapping on a narrow screen. Number options across the step (a
  second batch continues at 6), so the person can answer with numbers and no number means two things.
- **A plain page around the options**: system font, neutral background, no decoration of its own, so only the options
  differ.
- **Plain words.** Under each option, a short name and one line on what it is like. Hex codes and font names may appear
  in small print, but judging an option must never need them.
- **Different and tailored.** The options in a batch differ clearly from each other and fit this subject, audience and
  page; none is a generic page with the name swapped in.
- **Real content.** Use the brief's real names, prices and facts, never lorem ipsum. No images: Claude can't make them
  and artifacts block external ones, so use plain shapes or labelled grey boxes.
- **Stop after each step** and ask which options to keep: several is fine, and so is "3, but warmer". Record each pick
  in the person's words and build on those words, not on your paraphrase.

## Start

Get the subject, the page's one job (sign up, book, buy, learn) and its real facts. Ask only what is missing, at most
three questions at once. For a whole site, run the workshop on its main page; the brief then covers the rest.

For an existing site or app, or a repo that already has a design, start with "Existing site" below. When the brief
already settles a step (fixed brand colours, a named audience), lock it: say so and use it as given.

## The steps

| Step | Five options, each shown as |
|---|---|
| 1. Audience | A card: a name, who they are, what they want from this page, and what would put them off |
| 2. Feel | A word (fancy, sporty, artisanal, calm), one line on what it means here, and a small hint made of plain shapes, in the system font |
| 3. Tone of voice | The same content written in that voice: a headline, a short paragraph, a button label and one key fact such as a price. System font and no colour, so only the words differ |
| 4. Colour | A palette of 4 to 8 colours as a row of plain squares, background first, with only its number and a plain-words name: no mock-up, sample text or labels |
| 5. Type | A font pairing (Google Fonts, or the brand's own fonts) in the picked colours, with the picked tone's headline, paragraph, key fact and button, and a plain-words line on its character. The key fact is a number in a short aligned column (two or three prices or stats) set with `tabular-nums`, so a pairing without tabular figures shows it |
| 6. Layout | A grey wireframe of the whole page, top to bottom, every section labelled. The five differ in structure and section order, not only in the top section. No colour or fonts from earlier steps, so only the structure differs |
| 7. Combine | Five variants of the full page: see "The final step" |

Each step builds on the picks so far: feels for the picked audiences, tones for those feels, palettes that fit, fonts
set in the picked colours.

## Keeping options

- **Rotate until three are kept.** When fewer than 3 are kept, show 5 new options, never one already shown at this
  step; kept options carry over. Move on once at least 3 are kept, or when the person says one is enough. With each
  new batch, say that the ones already kept can be enough.
- **At most five per step.** Past 5, ask which to drop.
- **Spread the picks, don't blend them.** Each later option and each variant uses one kept option per step: never two
  kept tones, palettes or feels inside one page. When a step kept several, spread them over the next step's options.

## The final step

Make five variants of the full page, each as its own page, with all copy written for its audience in its tone, using
the brief's real facts.

- Use every kept option in at least one variant, paired so each variant hangs together.
- Keep the picks; vary the details: spacing and density, corner shapes, how the accent is used, decoration, and the
  headline treatment. On an existing site, vary only the details its locked steps leave open.
- One self-contained HTML file each, CSS inline, fonts from Google Fonts or the brand's own fonts inlined. They are
  prototypes for choosing: no framework, nothing in the source tree.

Ask the person to pick one, with any changes ("2, with 4's headline"); apply them and show it again. If none works, ask
which step it goes back to, reopen that step, then make five new variants.

## Hand over: the design brief

Once a variant is picked, write the brief and stop. Building it is a separate job, for `frontend-design` or any other
build, which keeps the brief's choices and adds its own craft: type scale, line length, responsiveness, keyboard focus,
reduced motion and contrast. Write every line as a decision, not a suggestion: `frontend-design` follows a brief exactly
where it pins the direction down.

```markdown
# Design brief: <subject>, <page>

Reference prototype: <path or link to the picked variant>

## Audience
Who they are, what they want from the page, and what would put them off.

## Feel
The word, and what it means for this page.

## Tone of voice
Two or three lines on the voice, then the prototype's headline, paragraph, button label and key fact as samples.

## Colour
| Role | Value | Used for |
|---|---|---|
| Background | | |
| Surface | | |
| Text | | |
| Muted text | | |
| Accent | | Links and primary actions |
| Border | | |

## Type
Each typeface and its role (headlines, body), its weights, and where it loads from.
The figure style per role (for example tabular for prices and stats, default elsewhere), and any OpenType feature the
design relies on (`case` on all-caps labels, `slashed-zero` for codes): a Google Fonts link strips these, so say if it
needs a self-hosted file. Name `opsz` in the load URL when the family has the axis and the design uses both small and
large sizes: the API serves only the axes the URL names.

## Layout
The sections from top to bottom, one line each on what it holds.

## Details
Spacing and density, corner shapes, how the accent is used, decoration, and the headline treatment, as in the
prototype.

## Not decided
What the workshop left open, such as dark mode, motion, images or other pages.
```

Check each text colour against the colour behind it (WCAG AA: 4.5:1 for body text, 3:1 for large text and UI parts),
and note any pair that fails in the Colour table, with the nearest shade that passes.

**Where it goes:**

- No repo: a `design-brief.md` (or an artifact), with the picked variant saved next to it.
- A repo: the colours by role, fonts, spacing and corner values go into its token file (theme CSS custom properties, a
  Tailwind theme, a tokens JSON); the rest of the brief goes into its design skill, or wherever its agent instructions
  keep design rules, with the picked variant saved next to it. Later sessions then build from these instead of
  deciding again. Changing a token file restyles the running site, so show the change and write it after a go-ahead.
  If the repo has neither, propose where they go and wait.

## Existing site

1. **Extract first.** Read the theme files, CSS custom properties, components and real pages, and the running app or
   its URL where you can reach it. Write down the current audience, feel, tone (quoted from real copy), colour roles,
   fonts and layouts in use, and show this to the person.
2. **Lock, nudge or open each step**, agreed with the person:

   | Job | Steps to run |
   |---|---|
   | A new page on the site | Layout, plus tone for new copy. The rest is locked |
   | A refresh | Only the steps that should move. Option 1 is the current choice; the others stay near it |
   | A redesign | All seven, with the current choice among each step's options |

3. **Show options in the site's own CSS and components**, inlined into the option page, not on a generic mock-up:
   wireframes from its real sections, variants in its tokens. Locked steps go into every option unchanged.
4. **Write the picks back** into the tokens and the repo's design skill, as in the hand-over.
