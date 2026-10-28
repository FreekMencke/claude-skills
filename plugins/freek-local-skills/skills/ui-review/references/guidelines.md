# Interface guidelines for a running-page review

An edited copy of the rules in Vercel's Web Interface Guidelines `command.md`:

- Source: <https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md>
- Commit `434b7f91364665f2f733b310ec54809bf8f37937`, read 2026-10-23. `command.md` last changed in `4ecfb9fb8d1d`
  (2026-10-05). MIT, notice at the end.
- Edited as claude-kb UIREV-002, UIREV-003 and UIREV-005 say; the edits are listed under "Changes from upstream". To
  update: diff upstream's `command.md` against this commit
  (`gh api "repos/vercel-labs/web-interface-guidelines/commits?path=command.md"`), adopt changes on purpose, and move
  the commit above.

Each rule says how it's checked:

- **script**: `check.mjs` measures it; the JSON key is named. The reviewer reads the value, doesn't re-measure it.
- **walk**: the keyboard walks in the JSON, plus a look at the page.
- **judge**: the reviewer judges it on the page (snapshot, a screenshot, `browser_evaluate`).
- **source**: needs the code; check with Grep when the review runs in the app's repo, else list it as not checked.

The repo's own rules (its design skill, tokens, style guide) win over any rule here.

## Accessibility

- Icon-only buttons have an accessible name (`aria-label` or visible text). **script** (axe `button-name`)
- Form controls have a `<label>` or `aria-label`. **script** (axe `label`)
- Custom widgets (a `div` or `span` acting as a control) handle Enter and Space; native `<button>` and `<a href>`
  already do, so don't flag them. **walk**
- `<button>` for actions, `<a href>` for navigation (not a click handler on a `div`). **judge** (snapshot roles)
- Images have `alt`, or `alt=""` when decorative; whether the text means anything is a person's call. **script** (axe
  `image-alt`) for presence
- Decorative icons have `aria-hidden="true"`. **judge**
- One status region (`role="status"`) is in the page before it changes, and only its text changes: results arrived,
  failed, came back empty, saved. Errors that block the task use `role="alert"`. Never wrap a list or a whole view in a
  live region. **script** (`states[].status`) and **judge**
- Headings in order, `<h1>` to `<h6>`; a skip link to the main content. **script** (axe `heading-order`, `bypass`) and
  **judge**
- `scroll-margin-top` on heading anchors under a sticky header. **walk**
- Meaningful media has captions, transcripts or descriptions; media controls work by keyboard; decorative media is
  hidden from assistive tech. **judge**
- Text contrast passes on WCAG 2 ratios: 4.5:1, 3:1 for large text (24px, or 18.66px bold) and for UI parts and focus
  indicators (1.4.3, 1.4.11). APCA is a second opinion, never the pass. **script** (axe `color-contrast`; its
  `incomplete` list names what it couldn't decide, such as text over images: judge those)
- Targets are at least 24×24 CSS px or spaced as 2.5.8 allows; 44px is AAA, a goal and not a failure. **script** (axe
  `target-size`)
- Zoom isn't disabled: no `maximum-scale` under 2 or `user-scalable=no`. Inputs at 16px or more stop iOS zooming on
  focus. **script** (axe `meta-viewport`)

## Focus

- Every focusable element shows a visible change on keyboard focus. **walk** (`stops`: `NO INDICATOR` is a finding;
  the indicator's own contrast is judged)
- No `outline: none` without a replacement. **walk**, and **source** for the CSS
- `:focus-visible` rather than `:focus`, so a click doesn't draw the ring. **walk** (`(not :focus-visible)`) and
  **source**
- Compound controls show focus on the group with `:focus-within`. **judge**
- Sticky headers, footers and overlays don't cover the focused element (2.4.11). **walk**
  (`partlyOrFullyCoveredWhenScrolled`: 0/5 is a finding, a partial cover a note; the fix is `scroll-padding-top` on
  `html` matching the header)
- Tab order follows the layout; Tab never stops on hidden elements or gets stuck. **walk**
- When the focused element goes away (Retry, delete, submit, a re-render), focus moves to something sensible, never
  `<body>`. **script** (`states[].afterRetry.focus`, `forms[].afterSubmit.focus`)

## Forms

- Fields about the user have `autocomplete` tokens and a meaningful `name` (WCAG 1.3.5); `autocomplete="off"` only
  where autofill would be wrong. **judge** (`browser_evaluate`)
- The right `type` (`email`, `tel`, `url`, `number`) and `inputmode`. **judge**
- Paste is never blocked. **source**
- Labels are clickable (`for`, or wrapping the control); a checkbox or radio and its label are one target with no dead
  zone. **judge**
- `spellcheck="false"` on emails, codes and usernames. **judge**
- No error on passing through an empty field; check on leaving a field that has a value, all on submit. **script**
  (`forms[].afterLeavingEmptyField`)
- Submit stays enabled until the request starts; while it runs, `aria-disabled="true"` with a guard and a "Saving…"
  label rather than `disabled` (which drops focus to `<body>`). **script** (`forms[].submitDisabledBeforeSubmit`)
- Errors sit next to their fields, tied by `aria-describedby` with `aria-invalid="true"`; submit moves focus to the
  first error or an error summary. **script** (`forms[].afterSubmit`)
- Placeholders show an example, never the label. **judge**
- Leaving with unsaved changes warns first. **judge**, when the review covers that flow

## States of a data view

- Each view has its loading, empty, error, network-failure, partial and long-content states designed: a visible
  message and a next action, with the view's frame kept. **script** (`states[]`: text and screenshot per state) and
  **judge**
- No empty message while loading. **script** (`states[].emptyMessageWhileLoading`)
- A loader shows only after a short delay and stays long enough not to flash. **judge**
- An error never lives only in a toast that hides itself. **judge**
- Long content wraps or truncates with the full text reachable; flex and grid children get `min-width: 0`. **script**
  (`states[]` long: `overflow`) and **judge**

## Animation

- `prefers-reduced-motion` is honoured: vestibular motion becomes a fade or nothing, infinite loops stop.
  **script** (`motion[].reduce.infinite`: anything there is a finding; `finite` and `smoothScroll` are judged)
- Animate `transform` and `opacity` only. **judge** (`browser_evaluate` on the animations) and **source**
- Never `transition: all`; list the properties. **script** (`pages[].transitionAll`)
- `transform-origin` fits the motion (a menu grows from its trigger); SVG transforms on a `<g>` with
  `transform-box: fill-box`. **judge**
- Animations can be interrupted by input. **judge**
- Motion that autoplays for more than 5 seconds next to other content has a pause, stop or hide control (2.2.2).
  **judge**

## Typography

The repo's style guide wins on all of these.

- `…` rather than `...`; curly quotes; non-breaking spaces in `10 MB`, `⌘ K` and brand names. **judge**
- Loading labels end with `…`: "Loading…", "Saving…". **judge**
- `font-variant-numeric: tabular-nums` on number columns and compared figures. **judge** (`browser_evaluate`)
- `text-wrap: balance` or `pretty` on headings. **judge**

## Content

- No overflow at any width: nothing past the viewport at 320 CSS px except content that needs two dimensions (1.4.10).
  **script** (`pages[].overflow`)
- Text containers handle long content (`overflow-wrap: anywhere`, truncation, line clamps); flex children need
  `min-width: 0` to truncate. **script** (long state) and **judge**
- Empty strings and arrays don't render broken UI. **script** (empty state) and **judge**
- Button labels are specific ("Save key", not "Continue"); error messages say what to do next; active voice. **judge**

## Images

- `<img>` has `width` and `height` (or an `aspect-ratio`), against layout shift. **script**
  (`pages[].imagesWithoutSize`)
- Below-the-fold images `loading="lazy"`; the above-the-fold critical one `fetchpriority="high"` (Angular's
  `NgOptimizedImage` `priority`). **judge**

## Performance

- Long lists (over about 50 items) are paged or virtualised, or use `content-visibility: auto`. **judge**
- No layout reads interleaved with writes. **source**
- `preconnect` for CDN and asset origins; critical fonts preloaded with `font-display: swap`. **judge**
  (`browser_evaluate` on `<head>`)
- Video (`autoplay muted loop playsinline`) rather than an animated GIF, with a still alternative. **judge**
- Console errors and failed requests on load. **script** (`pages[].consoleErrors`, `failedRequests`)

## Navigation and state

- The URL holds the state: filters, tabs, pagination and expanded panels in query parameters, so reload and Back
  restore them. **judge** (filter, reload, Back)
- Links are real `<a href>` (in Angular, `routerLink` on an `<a>`), so Cmd/Ctrl-click and middle-click work.
  **judge** (snapshot roles)
- Destructive actions ask to confirm or offer undo. **judge**, without triggering them

## Touch and interaction

- `touch-action: manipulation`; `-webkit-tap-highlight-color` set on purpose. **judge**
- `overscroll-behavior: contain` in modals, drawers and sheets. **judge**
- Gestures (drag, swipe, pinch) have a tap or click and keyboard alternative. **judge**
- During a drag, text selection is off and the dragged element is `inert`. **judge**
- `autofocus` sparingly: desktop only, one primary input. **judge**
- Hover gives feedback; hover, active and focus states are more prominent than rest. **judge**

## Spacing and alignment

A spacing finding is severity 1 or 2, a craft issue, unless groups read wrongly: that changes what people take as
related, and can rank higher.

- Gaps, padding and margins are steps of the repo's spacing scale; without one, 4, 8, 12, 16, 24, 32, 48 and 64 px
  (Tailwind 1, 2, 3, 4, 6, 8, 12, 16). Not arbitrary values (`mt-[13px]`) or fractions the scale doesn't name
  (`pt-1.75`). **source** (Grep templates and styles)
- Less space inside a group than between groups: a label sits closer to its field, and items in a card closer to each
  other, than to the next group; the next level is at least two steps larger. Equal gaps everywhere group nothing.
  **judge** (screenshots; `browser_evaluate` for the gaps)
- Groups are made with space before borders, dividers and cards; a boundary only where a wider gap can't do it
  (variable-height cards in a grid, dense tables). **judge**
- Icons line up with their label by `align-items: center` and a `gap`, not by margin or padding nudges, least of all
  per breakpoint (`mt-0.75 sm:mt-2.25`). **source** (Grep for top margins or padding on icons beside labels) and
  **judge** (screenshots: an icon visibly above or below the label's middle)

## Layout and theming

- Full-bleed layouts use `env(safe-area-inset-*)`. **judge**
- No unwanted scrollbars: fix the overflow rather than hiding it. **script** (`pages[].overflow`) and **judge**
- Layout from CSS (flex, grid, media and container queries), not JS measurement, and not picked in a component by
  `BreakpointObserver` or `isPlatformBrowser`: under SSR the server renders the no-match branch and phones shift after
  hydration (claude-kb LAYOUT-015). `BreakpointObserver` for behaviour after render, such as closing a menu, is fine.
  **source**
- Page margins of 15–16 px on phones: no text closer than 15 px to either edge at 390 and 320. **script**
  (`pages[].gutter`: `left` or `right` under 15 at those widths is a finding; a large `right` only means no text
  reaches that side)
- Components placed in more than one region respond to their container (container queries); the page responds to the
  viewport. A card that breaks in a sidebar at a width where it fits in the main column is a finding. **judge**
- Dark themes set `color-scheme: dark` on `<html>`; `<meta name="theme-color">` matches the background; native
  `<select>` gets an explicit `background-color` and `color`. **judge** (`browser_evaluate`)
- Dates and numbers through `Intl.DateTimeFormat` and `Intl.NumberFormat`; brand names and code in
  `translate="no"`. **judge**
- Server-rendered dates and times match what the client renders (no hydration flash). **judge**

## Charts

- The title states the finding ("Prices fell after the update"), in HTML rather than in the image; a subtitle says what
  the data is and the period. **judge**
- The takeaway in visible text, and the data in a `<table>` with a `<caption>`, beside the chart or behind
  `<details>`, unless the title and text already carry everything. Ask: what's the takeaway, and where is the table?
  **judge**
- One `role="img"` with a name on the `<svg>`, `<canvas>` or its wrapper when nothing inside is focusable (with
  focusable points, a labelled `role="group"` or `<figure>`), or `aria-hidden="true"` when visible text carries the
  description. **judge** (snapshot)
- Chart animation stops under `prefers-reduced-motion: reduce`: no tested library honours it (ECharts, Chart.js and
  ngx-charts animate by default), so the app passes it in. **judge** (the reduced-motion pass; a canvas chart animates
  in script, outside `motion[]`, so compare the first render under `browser_emulate_media` reduce) or **source** (the
  chart's animation option reads the preference)

## Changes from upstream

- **Dropped, React or Next.js only** (UIREV-002): "Inputs with `value` need `onChange`", "`suppressHydrationWarning`
  only where truly needed", "Prefer uncontrolled inputs", nuqs (now: query parameters), `<Link>` (now: `<a href>`),
  `htmlFor`, `spellCheck`, `autoFocus` and `virtua` (now: the HTML and generic names).
- **Dropped, Vercel's copy taste** (UIREV-002: upstream's README marks these "aren't universal guidelines", but
  `command.md` doesn't): Title Case, numerals for counts, second person, `&` over "and". Typography rules kept with
  "the repo's style guide wins".
- **Fixed, misfiring** (UIREV-003): keyboard handlers on every interactive element (now custom widgets only: native
  buttons handle Enter and Space).
- **Fixed, contradicting WCAG or this setup**: `autocomplete="off"` on non-auth fields (now: tokens on fields about
  the user, WCAG 1.3.5); "spinner during request" (now `aria-disabled` and a busy label, UIPAT-009);
  "`aria-live="polite"` on async updates" (now one persistent status region, UIPAT-015).
- **Added**: contrast on WCAG 2 ratios, not APCA (UIREV-003, claude-kb DESIGN-017; upstream's README and `AGENTS.md`
  prefer APCA); 24×24 targets as the AA floor, 44px as a goal; 16px inputs instead of `maximum-scale` (UIREV-003);
  focus must not fall to `<body>`; the "States of a data view" section (UIPAT-001, UIPAT-005, UIPAT-013); reflow at
  320 px (WCAG 1.4.10).
- **Added** (claude-kb, 2026-10-28): the "Spacing and alignment" section (SPACE-002, SPACE-005, SPACE-006,
  SPACE-012, SPACE-021); no layout from `BreakpointObserver` (LAYOUT-015), phone page margins (LAYOUT-003) and
  container queries for components (LAYOUT-009) in Layout and theming; the "Charts" section (VIZ-005, VIZ-014,
  VIZ-027).
- **Regrouped**: "Hover & Interactive States" into Touch and interaction; "Safe Areas", "Dark Mode" and "Locale" into
  Layout and theming; the anti-patterns list merged into the rules it repeats; upstream's review prompt and
  `file:line` output format dropped (the skill's report replaces them).

## Licence

```
MIT License

Copyright (c) 2025 Vercel Labs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
