---
name: angular-conventions
description: "House rules for Angular apps, on top of angular-developer: templates, accessibility (native elements, dialogs, focus after navigation, status messages), forms (submit button, field errors, autocomplete), animation (SSR-safe entrances, reduced motion, libraries), imports and layers, signal stores, loading, empty and failure states, routes, URL state and page meta, upgrades (ng update, TypeScript range, migration opt-outs), SSR on a custom Express server (CSP nonce, transfer cache, third-party timeouts), Vitest specs, charts, layout and spacing in CSS, Tailwind tokens and CSS features. Use when writing, reviewing, refactoring or upgrading code in an Angular app that follows these house rules, or when asked for our Angular conventions. Not for how an Angular API works, choosing between Angular's forms APIs, or scaffolding: use angular-developer."
---

# Angular conventions

An opinionated set of choices for Angular apps (SignalStore for shared state, Tailwind tokens, SSR on a custom Express
server), used as-is where a repo has made no choice of its own.

- This skill builds on `angular-developer`, Angular's official skill: load that one too for Angular's APIs. Where they
  differ, this skill wins. The repo's agent instructions (`CLAUDE.md`, `AGENTS.md`) and project skill win over both,
  and hold the repo's paths and examples.
- The installed Angular version (`@angular/core` in `package.json`) wins over `angular-developer`, which follows
  Angular's `main` and can describe newer APIs. When the repo's `.mcp.json` has the angular-cli MCP server, check an API
  with `search_documentation` (pass `version`, the major) or `get_best_practices` (pass `workspacePath` from
  `list_projects`). Without it, hover the API with the LSP tool or read its `.d.ts`.
- Verify with the verify command from the repo's agent instructions, not `angular-developer`'s plain `ng build`.

## Templates

- Inline (`template:`) up to about 80 lines, a `.html` file beside the component (`templateUrl`) above that, so the
  class stays readable. Move it out when a change takes it over.

## Accessibility

Target WCAG 2.2 AA. No ARIA is better than bad ARIA: a role promises keyboard behaviour that the browser won't add.

- Native elements first: `<button>` for actions, `<a href>` for navigation, never a click handler on a `<div>` or
  `<span>` (no focus, no Enter or Space). Every input has a `<label>`, since a placeholder isn't one, and an icon button
  has an accessible name.
- A widget with no HTML element (tabs, combobox, listbox, grid, tree, toolbar, an application's menus) is
  `@angular/aria` (`angular-developer` has its directives), not hand-written roles, states and key handling.
- Site navigation is a disclosure, not an ARIA menu: `<nav>` with links, `ariaCurrentWhenActive="page"` on the router
  links, and a `<button aria-expanded>` per dropdown. `role="menu"` promises OS-style menu keys that site navigation
  doesn't have, and screen readers then expect them.
- A modal is a `<dialog>` opened with `showModal()`: the browser makes the rest inert, moves focus in, closes on Esc and
  returns focus, so no focus trap of our own. A popover on a non-semantic element (`<div popover>`) has no role and
  moves no focus: add the ARIA, put it right after its trigger, and give something in it `autofocus`.
- Angular leaves focus where it was after a route change, so one place (the one that sets page meta) focuses the page's
  `h1` (`tabindex="-1"`) on `NavigationEnd`, in the browser only and skipping the first, server-rendered load. It also
  announces the title with `LiveAnnouncer`, since screen readers don't watch title changes. It skips query-only
  navigations too (a filter, sort or page change, see Routes): focus stays on the control, and the status region
  announces the result count.
- Status messages: one `role="status"` element always in the template, changing only its text ("Loading…", "12
  results", "No results", "Saved"), or CDK's `LiveAnnouncer`: a region added together with its text isn't read. Never a
  live region around a list or a view, which reads out every re-render. `role="alert"` only for an error that blocks
  the task.
- When the focused element goes away (Retry re-renders the view, a row is deleted, a form submits), keep it mounted or
  move focus to the next item, the list heading or the status text: otherwise it falls to `<body>`.
- Focus rings use `outline`, never `box-shadow`: forced-colors mode drops shadows. Never `outline: none` without a
  replacement. Targets are at least 24×24 CSS px, icon buttons included, unless 24 px circles around the smaller ones
  don't overlap.
- Lint templates with `templateRecommended` plus `templateAccessibility` (`angular-eslint`; the first doesn't include
  the second): it catches handlers on non-interactive elements, which axe passes.
- Verify with axe on the `wcag2a` to `wcag22aa` tags, on each state (menu open, dialog open, error shown), plus a
  keyboard walk: Tab order, visible focus, Enter, Space and Esc, focus after navigation. Scanners miss placeholder-only
  inputs, `alt="image"` and focus problems, so never report "accessible" from a scan alone: list what a person still
  checks (label and alt text meaning, screen-reader output, zoom to 400%, motion).

## Forms

- Submit stays enabled: never `[disabled]="!form().valid()"`, though Angular's signal forms guide shows it. A disabled
  button doesn't say why and isn't in the tab order; on click, validate and show the errors.
- While the request runs, mark the button busy, not `disabled` (which drops focus to `<body>`): `aria-disabled="true"`,
  a guard in the handler (`aria-disabled` blocks nothing by itself) and a label such as "Saving…".
- A field in error has `aria-invalid="true"` and `aria-describedby` with the hint's id, then the error's. Show errors
  once a field is touched, and on submit focus the first field in error (signal forms: in `onInvalid`,
  `errorSummary()[0]?.fieldTree().focusBoundControl()`).
- `autocomplete` on every field about the user (`name`, `email`, `tel`, `street-address`, `username`,
  `current-password`, `new-password`, `one-time-code`; WCAG 1.3.5). Not on fields about someone else, or search.

## Animation

Native CSS first, then Angular's `animate.enter` and `animate.leave` for elements it inserts and removes, then a
library, with its reason in a comment.

- No `@angular/animations` in new code: deprecated since 20.2, "Intent to remove in v23" in its JSDoc, and no
  `ng update` migration (angular.dev's "Migrating away from Angular's Animations package" maps each API by hand).
- Server-rendered content enters with `@starting-style` (Tailwind's `starting:`), not `animate.enter`, which replays at
  hydration: visible content fades out and in again (closed as intended in angular/angular#69180). `animate.enter` only
  for elements inserted after start-up (a toast, a row the user adds); `animate.leave` for exits. `@starting-style`
  needs no `@supports` (CSS features, under Tailwind): without it the element just appears.
- The end state is the base style; animate from something else. Never ship `opacity: 0` or an off-screen transform that
  waits for a script-added class: without JavaScript, or until hydration, the content stays hidden. Code that touches
  `window`, `matchMedia` or `element.animate()` runs in `afterNextRender` or an event handler.
- Animate `transform` and `opacity`: other properties lay out or repaint every frame. No `will-change` up front, only
  against a measured problem.
- Durations come from a published scale, not invented: NN/g's 100–400 ms (about 100 ms for a toggle, 200–300 ms for a
  modal, 400 ms only for large movements across the screen), shorter for frequent motion, exits shorter than entrances.
  Material 3 and Carbon motion tokens are scales to snap to.
- Reduced motion (`@media (prefers-reduced-motion: reduce)`, Tailwind's `motion-reduce:`/`motion-safe:`) replaces
  slides, zooms, parallax and spins with a short fade or nothing, and stops infinite loops (spinners, pulses,
  skeletons) with `animation: none` or a static state. Angular never checks it. It isn't a pause control: a loop that
  starts by itself and runs over five seconds beside other content needs one (WCAG 2.2.2), in either branch.
- Route transitions (`withViewTransitions()`): their CSS goes in global styles, since component styles scope it, even
  `@keyframes`. The router runs them under reduced motion too: author the animation under `no-preference` only, or call
  `transition.skipTransition()` in `onViewTransitionCreated` when reduced motion matches. They move no focus (see
  focus after navigation).
- Exits: Angular leaves a leaving element focusable. Move focus out first (to the trigger, or the next item or list
  heading if the trigger goes too), then set `inert` in the `(animate.leave)` callback and call `animationComplete()`. A
  bound `[inert]` never applies (the view is destroyed in that pass), and `inert` on a subtree that holds focus drops
  it to `<body>`. A leaving toast's message goes with it: announce through the status region.
- Tests: under Vitest with jsdom (no `getAnimations`), `animate.enter` adds no class and `animate.leave` removes at
  once, even with `animationsEnabled: true`, so assert end states and stub `matchMedia` where code reads it. Test motion
  and the `reducedMotion: 'reduce'` branch in Playwright.

### Animation libraries

- Only for what CSS can't do (sequences, timelines, scrubbing), with the reason and cost in a comment. Gzip added to an
  empty app: `motion/mini` 3.3 kB, Motion's `animate` 24.6 kB, GSAP 27.6 kB, with ScrollTrigger 45.4 kB.
- No Lenis: it ignores keys pressed mid-scroll, scrolls the page instead of nested scroll boxes, and its `anchors`
  option breaks hash links.
- GSAP's licence (Webflow's own) isn't OSI-approved: record the exception in the comment and the PR that add it.
- Start it in `afterNextRender`, with `DestroyRef` injected before it (`inject()` fails inside the callback): Motion's
  `inView` and `new Lenis()` throw on the server. Stop or revert everything in `DestroyRef.onDestroy`.
- Write the reduced branch yourself, as no library does it by default: `scopeMotion(setup, { matchMedia: 'motion' })`
  or `gsap.matchMedia()` with `(prefers-reduced-motion: no-preference)`; `scope.stop()` or `mm.revert()` on destroy. A
  reduce branch plays once or shows the end state, never a loop.
- Scroll reveals hide content from script only, only under `no-preference`, with `opacity` and `transform`, never
  `visibility` (which drops it from find-in-page, focus and screen readers). Add a print rule that shows it:
  `@media print { .reveal { opacity: 1 !important; transform: none !important; } }`.

## Imports and layers

- Relative within a feature or a shared folder; a path alias (`@app/…`) across them.
- Shared and core code never import a feature, features don't import each other, and app code never imports the Express
  server's code (only `app.config.server.ts` does). ESLint enforces the layers with `import-x/no-restricted-paths`; the
  repo's config lists them.
- `HttpClient` only in the repository layer (and specs); components and stores call repositories.

## State

- Signals, with inferred types: `readonly total = computed(...)`. Type only what inference gets wrong:
  `signal<User | null>(null)`.
- State shared between components, or kept in `localStorage`, is an `@ngrx/signals` `signalStore`, never a plain
  service. Its private members start with `_`, which keeps them out of the store's public API.
- `localStorage` only through a store, never from a component.

## Libraries first

Before writing a helper, use what's installed, and hand-write only what it can't do, with a comment saying why:

- RxJS operators: `switchMap` or `exhaustMap` cancel a request that a newer one replaces, instead of a manual
  `unsubscribe`.
- `@ngrx/signals`: `rxMethod`, `signalStoreFeature`.
- Dates: Angular's `formatDate(value, format, locale, 'UTC')` for UTC dates (date-fns' `format` is local time only),
  date-fns for local ones. `Intl` for numbers.

## Charts

IDs in parentheses here, under Async data and failures and under Layout and spacing are claude-kb entries, which hold
the evidence.

- Pick in this order, going on only when a step can't do the chart: no library (a stat tile with `Intl`, a `<meter>`,
  CSS-width bars in a table); a table or hand-written SVG in the template; `d3-scale`/`d3-shape` for scales, ticks and
  curves, with Angular still rendering the SVG (no `d3-selection`); then a library, with its reason in a comment. No
  ngx-charts: it relies on `@angular/animations`, leaves the chart unnamed and adds a Tab stop per bar (VIZ-012).
- Every chart states its takeaway in visible text (a title that gives the finding, not "Players online"), and has a
  `<table>` with a `<caption>` of its data, beside it or in a `<details>` (VIZ-005, VIZ-014).
- One `role="img"` with an `aria-label`, on the `<svg>`, the `<canvas>` or its wrapper, when nothing inside is
  focusable. A chart with focusable points is a labelled `<figure>` or `role="group"` instead (VIZ-014).
- No chart library reads `prefers-reduced-motion`: pass it in (`animation: false` under reduce), read in the browser
  and kept in a signal so a change updates the chart (VIZ-027).
- A library chart below the fold goes in `@defer (on viewport)` with a placeholder that carries the takeaway: some
  libraries throw during SSR, and it keeps them out of the initial bundle (VIZ-010).

## Async data and failures

- `httpResource` or `rxResource`, also for a request a user action starts: a signal of the submitted input as `params`,
  `reload()` to repeat it. If you subscribe instead, reset the loading state in `finalize`.
- Every failable load shows its failure, with a retry (`reload()`). Never `catchError(() => of(empty))`, or an `error`
  callback that only empties the data. The retry's busy label ("Checking…") comes from `status() === 'reloading'` or a
  signal set on click, never `isLoading()`, which is true on the first load too (NG-019).
- `@switch` on the resource's `status()`, so each state gets its branch: empty is distinct from loading (never "No
  results" before the data arrives), and `'reloading'` keeps the previous value on screen when `hasValue()`, instead of
  a skeleton. A reload after an error has no value, so it gets the loading state; `error()` stays set until it settles,
  so never test `error()` before `status()` (NG-019). `hasValue()` guards `value()`, which throws on error.
- `encodeURIComponent` each path segment; query values go in `params`.

## Routes and page meta

- Lazy routes (`loadComponent`) to default-exported components, each with a `title`: `'<Page> - <Site>'`. A landing
  page may lead with its search term, `'<Term>: <Rest>'`, with a capital after the colon: Google may show it flipped,
  as `'<Rest> - <Site>'`.
- Page meta (title, description, canonical, social tags) is set in one place, once per navigation, from the deepest
  route's `data`. The data may be a function of the route's resolved data, so the resolver stays the only fetch. Never
  set meta from components or resolvers.
- Filters, sort, tabs and paging live in query params, so reload, shared links and Back keep them: one history entry
  per applied change (`replaceUrl: true` per keystroke of a live search). Navigate with `queryParamsHandling: 'merge'`:
  the default replaces the query string, so setting `sort` drops `filter`. A filter or sort change resets the page,
  and an unknown value (`?page=abc`) reads as the default.

## Code navigation

- The LSP tool is plain TypeScript, without Angular's language service: `findReferences` misses template usages
  (inputs, outputs, methods, pipes), inline or in `.html`. Before renaming or deleting a member, grep the templates too.
  Without the LSP tool, grep for every reference.

## Upgrades

- Update with `ng update @angular/core@<major> @angular/cli@<major>`, one major at a time, together with the repo's
  other Angular-aligned packages (`angular-eslint`, `@angular/cdk`): the CLI refuses to jump several majors at once.
- After it, run each optional migration it listed, as `ng update <pkg> --name <migration>`, or note why you skip it. In
  a session `ng update` has no TTY, so it runs none and only prints their names.
- Keep `typescript` inside the range `npm view @angular/compiler-cli@<version> peerDependencies` gives, never
  `typescript@latest`: it can be a major ahead of what Angular accepts, and the build breaks. Take the range from the
  registry: angular.dev's versions page lags it.
- After any dependency bump, `npm ls --all` must exit 0. An npm warning is not a pass: a `typescript` outside the
  range installs with one `ERESOLVE overriding peer dependency` warning and fails only at `ngc`, and
  `--strict-peer-deps`, `npm ci` and a top-level `npm ls` all pass, since that peer is optional.
- Review each opt-out the migrations write to keep the old behaviour (`ChangeDetectionStrategy.Eager`,
  `strictTemplates: false`, `withNoIncrementalHydration()`, `$safeNavigationMigration()`, suppressed extended
  diagnostics): remove it, or keep it with the reason in the commit message.

## SSR on a custom Express server

- **CSP nonce**: every path that sends page HTML (the Angular handler, a page cache, error pages) sets the nonce, or
  every script is blocked. No inline event handlers. Never serve the browser build's `index.csr.html`: it has no nonce.
- **Transfer cache**: Angular leaves a response out when its `Cache-Control` has `no-store`, `no-cache` or `private`;
  the browser then refetches on hydration and the resource flashes back to its default value. When a page refetches
  after load, check the API's `Cache-Control` first. Entries in `<script id="ng-state">` are keyed by a hash, not the
  URL: search for a value from the response body.
- **Transfer state size**: every SSR response is embedded in the page. Load large payloads the first paint doesn't need
  in the browser only, and render skeletons on the server.
- **Third-party calls**: a render waits for every request it makes. Keep them small, give them a timeout during SSR
  (an interceptor), and render a failed one as loading on the server: the browser fetches it again after hydration.
- **Writes**: requests that record something run only in the browser for a human visitor, never during SSR or for
  crawlers.
- **Missing assets**: answer paths that end in a build asset extension (`.js`, `.css`, `.woff2`…) with a 404 after
  `express.static` and before Angular, as some crawlers resolve asset links against the page path. A server route that
  ends in such an extension registers before that middleware.

## Tests

- Only for complex or important logic, never for coverage. Break the protected code once to see the test fail.
- Write expected values as literals, never recomputed the way the code computes them: `expect(total(items)).toBe(
  items.reduce(...))` passes by construction and catches nothing.
- Specs sit next to the code and import from `vitest`.
- Server specs start with `// @vitest-environment node`. Run them as a quoted folder glob
  (`ng test --include 'src/server/**/*.spec.ts'`), not one by one: when `tsconfig.spec.json` leaves out Node's types,
  a spec that imports nothing that brings them in fails alone ("Cannot find name 'process'").
- `vi.mock` works for packages only: the unit-test builder rejects it for relative imports. Swap those through TestBed
  providers.
- App specs: `HttpTestingController` for HTTP, and clear `localStorage` in `afterEach`.

## Layout and spacing

- Layout is CSS, never an `@if` on `BreakpointObserver` or `isPlatformBrowser`: nothing matches on the server, so every
  visitor gets the no-match HTML and phones shift after hydration (LAYOUT-015). `BreakpointObserver` stays fine for
  behaviour after render, such as closing a menu or reduced motion in a chart.
- Per region, in this order: intrinsic CSS (`repeat(auto-fit, minmax(min(100%, 16rem), 1fr))`, a wrapping flex row);
  container queries for components; viewport breakpoints (`md`, `lg`) for page structure only (LAYOUT-003, LAYOUT-009,
  LAYOUT-011, LAYOUT-012).
- Spacing steps come from the scale only. Less space inside a group than between groups, at least two steps apart: 16
  against 20 doesn't read as a new group (SPACE-005, SPACE-021).
- Start from the role: icon to label 4–8 px, inside a group 8–16, between groups 24–32, between sections 48–80
  (SPACE-021).
- Group with space before borders, dividers or cards: widen the gap between groups first, and add a boundary only if the
  grouping still isn't clear, as with variable-height cards in a grid or a dense table (SPACE-006).
- Align an icon with its label with `items-center` and a `gap`, never per-breakpoint margin nudges (`mt-0.75
  sm:mt-2.25`). If a font still sits a pixel off, trim the label element (not the flex container) with `text-box:
  trim-both cap alphabetic`, as an enhancement only: it isn't Baseline (SPACE-012, SPACE-013, SPACE-014).

## Tailwind

- No arbitrary values (`w-[13px]`): a value the scale lacks becomes a token in the theme CSS.
- Colours are semantic tokens that swap under `.dark`, never `dark:` pairs.
- A tint is a colour made see-through, `color-mix(in oklch, <colour> N%, transparent)`, layered over the surface where
  needed. Never mix a colour with a slate token: the blend takes the slate's blue hue, and a red turns violet.
- Whole-pixel line heights (`text-xl/6`).
- `tabular-nums` on standalone values only (prices, counts, axes), never on numbers in running text or a page root.
- Hover changes the background, never adds a shadow.
- Shadows go on what floats or overlaps (menus, popovers, dialogs, overlapping images). Cards are flat by default, with
  a border, whitespace or a tone step; the design brief may say otherwise. Shadow tokens are named by job
  (`--shadow-raised`, `--shadow-overlay`, `--shadow-dialog`), never Tailwind's stock sizes: clear those with
  `--shadow-*: initial` in `@theme`.
- Every shadowed surface also has an edge forced colours keeps: `border`, or `border border-transparent` /
  `outline outline-transparent` when it shouldn't show. Forced colours computes every `box-shadow` to `none`, `ring-*`
  included.
- Dark mode shows height with a lighter surface token per level and a hairline `border` or `outline`, not only a
  stronger shadow.
- CSS features, utilities included: free to use when Baseline widely available on the Angular major's Baseline date
  (angular.dev/reference/versions; v22: 2026-05-07). Newer ones (`light-dark()`, `starting:`, `@scope`, `field-sizing`,
  scroll-driven animations) only as an enhancement, behind `@supports` or after a plain fallback declaration. Check
  one: `curl -s https://api.webstatus.dev/v1/features/<web-features id>`.
