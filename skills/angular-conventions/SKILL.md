---
name: angular-conventions
description: "House rules for Angular apps, on top of angular-developer: file names, imports and layers, signal stores, failure states, routes and page meta, SSR on a custom Express server (CSP nonce, transfer cache, third-party timeouts), Vitest specs and Tailwind tokens. Use when writing, reviewing or refactoring code in an Angular app that follows these house rules, or when asked for our Angular conventions. Not for how an Angular API works or for scaffolding: use angular-developer."
---

# Angular conventions

- This skill builds on `angular-developer`, Angular's official skill: load that one too for Angular's APIs. Where they
  differ, this skill wins. The repo's `CLAUDE.md` and project skill win over both, and hold the repo's paths and
  examples.
- The installed Angular version (`@angular/core` in `package.json`) wins over `angular-developer`, which follows
  Angular's `main` and can describe newer APIs. When the repo's `.mcp.json` has the angular-cli MCP server, check an API
  with `search_documentation` (pass `version`, the major) or `get_best_practices` (pass `workspacePath` from
  `list_projects`). Without it, hover the API with the LSP tool or read its `.d.ts`.
- Verify with the repo's verify command (`CLAUDE.md`), not `angular-developer`'s plain `ng build`.

## Names

- Components and directives have no suffix: `home.ts` holds `class Home`, its template `home.html`.
- Other classes keep their suffix, and the file joins it with a hyphen: `StorageService` in `storage-service.ts`,
  `TimeAgoPipe` in `time-ago-pipe.ts`, likewise `-repo`, `-store`, `-resolver`, `-interceptor`. `angular-developer`
  drops it from the file name (`auth.ts`); don't. Generate with the suffix in the name: `ng g s <folder>/storage-service`.
- Only the CLI's own files keep a dot (`main.server.ts`, `app.config.server.ts`, `app.routes.ts`, `*.routes.ts`), and
  generated ones (`*.generated.ts`). Models get no `.model.ts`.

## Templates

- Inline (`template:`) up to about 80 lines, a `.html` file beside the component (`templateUrl`) above that, so the
  class stays readable. Move it out when a change takes it over.

## Imports and layers

- Relative within a feature or a shared folder; a path alias (`@app/…`) across them.
- Shared and core code never import a feature, features don't import each other, and app code never imports the Express
  server's code (only `app.config.server.ts` does). ESLint enforces the layers with `import-x/no-restricted-paths`; the
  repo's config lists them.
- `HttpClient` only in the repository layer (and specs); components and stores call repositories.

## State

- Signals, with explicitly typed public fields: `readonly total: Signal<number> = computed(...)`.
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

## Async data and failures

- `httpResource` or `rxResource`, also for a request a user action starts: a signal of the submitted input as `params`,
  `reload()` to repeat it. If you subscribe instead, reset the loading state in `finalize`.
- Every failable load shows its failure, with a retry (`reload()`). Never `catchError(() => of(empty))`, or an `error`
  callback that only empties the data.
- `encodeURIComponent` each path segment; query values go in `params`.

## Routes and page meta

- Lazy routes (`loadComponent`) to default-exported components, each with a `title`: `'<Page> - <Site>'`. A landing
  page may lead with its search term, `'<Term>: <Rest>'`, with a capital after the colon: Google may show it flipped,
  as `'<Rest> - <Site>'`.
- Page meta (title, description, canonical, social tags) is set in one place, once per navigation, from the deepest
  route's `data`. The data may be a function of the route's resolved data, so the resolver stays the only fetch. Never
  set meta from components or resolvers.

## Code navigation

- The LSP tool is plain TypeScript, without Angular's language service: `findReferences` misses template usages
  (inputs, outputs, methods, pipes), inline or in `.html`. Before renaming or deleting a member, grep the templates too.
  Without the LSP tool, grep for every reference.

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
- Specs sit next to the code and import from `vitest`.
- Server specs start with `// @vitest-environment node`. Run them as a quoted folder glob
  (`ng test --include 'src/server/**/*.spec.ts'`), not one by one: when `tsconfig.spec.json` leaves out Node's types,
  a spec that imports nothing that brings them in fails alone ("Cannot find name 'process'").
- `vi.mock` works for packages only: the unit-test builder rejects it for relative imports. Swap those through TestBed
  providers.
- App specs: `HttpTestingController` for HTTP, and clear `localStorage` in `afterEach`.

## Tailwind

- No arbitrary values (`w-[13px]`): a value the scale lacks becomes a token in the theme CSS.
- Colours are semantic tokens that swap under `.dark`, never `dark:` pairs.
- A tint is a colour made see-through, `color-mix(in oklch, <colour> N%, transparent)`, layered over the surface where
  needed. Never mix a colour with a slate token: the blend takes the slate's blue hue, and a red turns violet.
- Whole-pixel line heights (`text-xl/6`).
- `tabular-nums` on standalone values only (prices, counts, axes), never on numbers in running text or a page root.
- Hover changes the background, never adds a shadow.
