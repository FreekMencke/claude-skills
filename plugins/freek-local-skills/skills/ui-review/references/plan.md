# The check script's plan

`scripts/check.mjs` reads one JSON plan, written to the scratchpad with a heredoc:

```json
{
  "base": "http://localhost:4200",
  "pages": ["/", "/items", "/items/1"],
  "widths": [1440, 768, 375, 320],
  "colorScheme": "dark",
  "views": [
    {
      "page": "/items",
      "api": "**/api/items?*",
      "root": "section#items",
      "retry": "button:has-text('Try again')",
      "refetch": "button:has-text('Refresh')",
      "bodies": {
        "empty": { "items": [] },
        "partial": { "items": [{ "name": "Rune scimitar" }], "prices": null },
        "long": { "items": [{ "name": "<200 characters with no spaces>" }] }
      }
    }
  ],
  "forms": [{ "page": "/contact", "form": "form#contact" }]
}
```

| Key | Meaning | Default |
|---|---|---|
| `base` | Origin the paths resolve against: a local production build where the repo can serve one | required |
| `pages` | Paths for the page checks, keyboard walks and motion check | `[]` |
| `widths` | Viewport widths, CSS px; heights 900, 1024, 812, 640 for the defaults, else 900 | `[1440, 768, 375, 320]` |
| `colorScheme` | `light` or `dark`; for an app with both, run the plan once per scheme into separate `--out` folders | `light` |
| `dismiss` | Selectors clicked after each load when visible, such as a consent banner's decline button. Without it, the walks show what a first visit gets: a banner pinned to the bottom covers focus at phone widths | none |
| `views[].page` | Page holding the data view | required |
| `views[].api` | Glob or URL of the request the view loads, as `page.route` takes it | required |
| `views[].from`, `views[].link` | For a server-rendered view: a page to start on and the selector of a link to the view, followed client-side so the data loads in the browser. Pick a link visible on `from` at the widest width, in the page body, not in a dropdown or menu | load `page` directly |
| `views[].root` | Plain CSS selector of the view's own element, which shows only this request's data: text, axe and overflow are read inside it. Set it whenever the page holds a hero or more than one view; a card that falls back to other data when the request fails won't change under the mock. It also goes to `document.querySelector`, so no `:has-text` or other Playwright-only selectors | `main` |
| `views[].retry` | The error state's retry control, looked up inside `root` (page-wide only when the error replaced `root`); pressed with Enter, then focus is recorded | error state only, no retry |
| `views[].refetch` | A control in the loaded view that requests the API again (refresh, a filter); clicked while offline | offline state skipped |
| `views[].bodies.empty`, `.partial`, `.long` | JSON bodies for those states, in the API's real shape (fetch one real response first). `partial` stays within the API's contract: optional fields left out or the nulls the API really sends, not a required field dropped, which can crash the view in a way the real API can't | that state skipped |
| `forms[].page`, `forms[].form` | Page and form selector | form: `form` |

States per view: `loaded`, `loading` (the response held for 1.5 s), `empty`, `error` (500, and the retry succeeds),
`network` (`connectionrefused`), `partial`, `long` (at the narrowest width), `offline` (no mock, so the browser's
offline mode applies). A long body: one string of about 200 characters without spaces in each text field the view
shows, and enough items to page or scroll. After following `link`, the script waits for the URL to reach `page` and
the view's text to hold still for 1 s (at most 10 s); in `loading` it doesn't wait for the URL, as a resolver may hold
the navigation on the held request. A `link` that matches nothing visible, leads elsewhere or can't be clicked, or a
`root` that isn't plain CSS, ends that view with one `notRun` line. Screenshots are named after the page, the view's
place in `views` (`v1`, `v2`) and the state.

Forms: every request but `GET` is aborted and listed under `blockedRequests`, so the empty submit never reaches the
server. The script finds the first `[required]` or `[aria-required="true"]` field and the submit button inside the
form.

Limits: `page.route` sees only the browser's requests, not data fetched during server rendering: for a server-rendered
view, set `from` and `link`. When the empty state's text matches the loaded one's, the script says under `notRun` that
`root` may be too wide or the mock may not have reached the view. A service worker (MSW) hides requests from it. Chromium only.
