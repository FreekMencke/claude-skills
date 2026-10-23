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
      "root": "main",
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
| `views[].page` | Page holding the data view | required |
| `views[].api` | Glob or URL of the request the view loads, as `page.route` takes it | required |
| `views[].from`, `views[].link` | For a server-rendered view: a page to start on and the selector of a link to the view, followed client-side so the data loads in the browser | load `page` directly |
| `views[].root` | Selector of the view: text, axe and overflow are read inside it | `main` |
| `views[].retry` | The error state's retry control; pressed with Enter, then focus is recorded | error state only, no retry |
| `views[].refetch` | A control in the loaded view that requests the API again (refresh, a filter); clicked while offline | offline state skipped |
| `views[].bodies.empty`, `.partial`, `.long` | JSON bodies for those states, in the API's real shape (fetch one real response first) | that state skipped |
| `forms[].page`, `forms[].form` | Page and form selector | form: `form` |

States per view: `loaded`, `loading` (the response held for 1.5 s), `empty`, `error` (500, and the retry succeeds),
`network` (`connectionrefused`), `partial`, `long` (at the narrowest width), `offline` (no mock, so the browser's
offline mode applies). A long body: one string of about 200 characters without spaces in each text field the view
shows, and enough items to page or scroll.

Forms: every request but `GET` is aborted and listed under `blockedRequests`, so the empty submit never reaches the
server. The script finds the first `[required]` or `[aria-required="true"]` field and the submit button inside the
form.

Limits: `page.route` sees only the browser's requests, not data fetched during server rendering: for a server-rendered
view, set `from` and `link`. When the empty state's text matches the loaded one's, the script says the mock may not
have reached the view, under `notRun`. A service worker (MSW) hides requests from it. Chromium only.
