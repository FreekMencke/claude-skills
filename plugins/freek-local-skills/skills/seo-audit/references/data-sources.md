# Data sources: what each answers and how to ask it

| Question | Source | Route |
|---|---|---|
| What does the server send? | Server HTML | `scripts/probe.sh` (curl) |
| Does the page agree after hydration? | Rendered DOM | Playwright `browser_evaluate` |
| Which pages and queries get impressions and clicks? | Search Console Search Analytics | The read-only wrapper or MCP server |
| Is a URL indexed, and which canonical did Google pick? | URL Inspection | Same; one URL per call, 2,000 a day per site |
| Why are pages not indexed (counts per reason)? | Search Console Pages report | UI only: a manual step |
| How often does Google crawl, how fast does the server answer? | Crawl stats, server logs | Crawl stats is UI only; logs through the repo's documented route |
| Lab LCP, CLS, TBT | Lighthouse | PSI API with a key, or the Lighthouse CLI |
| Field Core Web Vitals | CrUX | The CrUX API with a key; low-traffic sites have none |
| Where do visitors land from search, what do they do? | GA4 | A GA4 MCP server, if the session has one |

Compute numbers with `jq` or Python over the JSON; never estimate them by reading rows.

## Search Console

Use the wrapper or server the repo's docs or the session's memory name. Never list or read a credentials folder to
find one: auto mode blocks that as credential exploration, and the key must never be printed.

**Performance per page** (request body for `searchanalytics.query`; dates in Pacific time, data lags about 2 days):

```json
{"startDate": "<28 days ago>", "endDate": "<yesterday>", "dimensions": ["page"], "rowLimit": 25000, "dataState": "all"}
```

- Group the rows by page template (map path patterns from the repo's routes), then sum clicks and impressions per
  template. Each template's share of impressions sets the impact of its findings.
- Quick wins: pages with an average position of 8 to 20 and real impressions (titles, descriptions, content can move
  them onto page one). Weak click-through at positions 1 to 5 points at the title and description.
- Add `"query"` as a second dimension for the top template to see what people search for.
- A 3-month or 16-month range shows trends; Search Console keeps 16 months.

**URL Inspection** (`inspectionUrl`, `siteUrl`), for each sampled URL. Read from `inspectionResult.indexStatusResult`:
`verdict`, `coverageState`, `lastCrawlTime`, `googleCanonical` against `userCanonical`, `referringUrls`, `sitemap`.
It reports the indexed version only ("you cannot test the indexability of a live URL"), and can disagree with the UI.

**Sitemaps** (`sitemaps.list`): `isPending`, `lastDownloaded`, `errors`, `warnings` per submitted index and child.
`isPending: true` with 0 errors, on a sitemap the logs show Googlebot fetching with a 200, means not processed yet:
not a finding, even when the UI says "could not be read". A sitemap index row stuck pending is harmless when its
children are submitted directly and read fine. Seen on one site (2026-10-13): new child sitemaps showed "could not be
read" minutes after a submit, though Googlebot got a 200, and cleared on their own within hours; a resubmitted index
stayed pending for days. So the fix for a stuck index is submitting the children directly, not resubmitting it. Check
in order: `sitemaps.list`, the logs for Googlebot's fetch and status, then URL Inspection's live test of the sitemap
URL (its non-live view says "URL is unknown to Google" for any sitemap, which means nothing).

**UI only** (manual steps for the user, or a browser they sign in to): the Pages report's reasons ("Discovered –
currently not indexed", "Crawled – currently not indexed", duplicates), Crawl stats, the Core Web Vitals report.

Without Search Console, say so in the report, weight impact by how many URLs a template has and what the repo's docs
say matters, and mark impact-based ranking as likely.

## PageSpeed Insights API

It needs a key in practice: keyless calls return 429. Read the key into a variable from where the repo's docs or the
session's memory say; never echo it.

```bash
curl -s -G https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed \
  --data-urlencode "url=<page URL>" -d strategy=mobile -d category=performance -d category=seo \
  --data-urlencode "key=$key" |
  jq '{perf: .lighthouseResult.categories.performance.score, seo: .lighthouseResult.categories.seo.score,
       lcp: .lighthouseResult.audits["largest-contentful-paint"].displayValue,
       cls: .lighthouseResult.audits["cumulative-layout-shift"].displayValue,
       tbt: .lighthouseResult.audits["total-blocking-time"].displayValue,
       lcp_element: [.lighthouseResult.audits["lcp-breakdown-insight"].details.items[]? | select(.type == "node") | .snippet][0],
       failed_seo: [.lighthouseResult.categories.seo.auditRefs[].id as $id | .lighthouseResult.audits[$id] | select(.score == 0) | .id],
       field: (.loadingExperience.overall_category // "none"), error: .error.message}'
```

Runs take 20 to 60 seconds; run one page per template, in parallel. PSI fetches production only.

## CrUX API

Field data, 75th percentile of real Chrome visits over 28 days. PSI's `loadingExperience` is the same data, but Google
plans to drop it from PSI ("We plan to discontinue including real-world data from the Chrome User Experience Report in
this API", [Get started](https://developers.google.com/speed/docs/insights/v5/get-started)), so ask CrUX directly. It
needs a key "provisioned for Chrome UX Report API usage": the PSI key works once the Chrome UX Report API is enabled in
its project and allowed in the key's restrictions. 150 queries a minute per project
([CrUX API](https://developer.chrome.com/docs/crux/api)).

```bash
curl -s -X POST "https://chromeuxreport.googleapis.com/v1/records:queryRecord?key=$key" \
  -H 'Content-Type: application/json' -d '{"url": "<page URL>", "formFactor": "PHONE"}' |
  jq '{lcp: .record.metrics.largest_contentful_paint.percentiles.p75,
       inp: .record.metrics.interaction_to_next_paint.percentiles.p75,
       cls: .record.metrics.cumulative_layout_shift.percentiles.p75, error: .error.message}'
```

Ask per page first, then `"origin"` instead of `"url"` for the whole site. An error and no `record` means CrUX has no
data for it: small sites usually have none.

## Lighthouse CLI

Needs Node 22 or later and a local Chrome or Chromium. Run it from the scratchpad, not the repo: under WSL its Chrome
profile path can land as a folder named `C:\…` in the current directory.

```bash
npx -y lighthouse@13 "<page URL>" --only-categories=performance,seo --output=json --output-path=stdout --quiet \
  --chrome-flags="--headless=new" | jq '<the same fields as above, without .lighthouseResult>'
```

## Reading lab numbers

- Lab LCP with simulated throttling is an estimate from a fast load. Don't name a cause (a font, a script) from it
  alone; a cause needs a trace or a run with `--throttling-method=devtools` that shows it.
- Lab has no INP. Field data, when CrUX has it, outranks lab numbers.

## Server logs

Use the route the repo's docs name. Filter by user agent: drop requests whose user agent contains `seo-audit` (this
audit's own), then count Googlebot and other bots per template, and render times (p50, p90) per template. A
self-declared Googlebot is unverified; Google verifies by reverse DNS.

## GA4

Only through a GA4 MCP server the session already has. Useful questions: landing pages for the Organic Search channel
(sessions, engagement) per template. Without one, leave GA4 out of the tier; don't offer data the session can't read.

## Giving a session the data (for the user)

The audit only reads what the session already has; it sets nothing up. The Coverage section points here for what was
missing. Set these up once per site, outside every repo, then name the route (the wrapper or the server, not the key)
in the repo's `CLAUDE.md` or the session's memory. Auto mode denies listing a credentials folder as credential
exploration, so a session can't find an unnamed route on its own.

**Search Console.** Google ships no MCP server for it (checked 2026-10-14).

1. In a Google Cloud project, enable the Google Search Console API, and create a service account with a JSON key.
2. In Search Console, Settings › Users and permissions › Add user: the service account's email, permission
   **Restricted** ("simple view rights on most data"; it can't submit sitemaps)
   ([Managing owners, users, and permissions](https://support.google.com/webmasters/answer/7687615)).
3. Authorise with the read-only scope, `https://www.googleapis.com/auth/webmasters.readonly`
   ([Authorizing requests](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing)).
4. Give the session one route that holds the key: a small wrapper script (`sites`, `analytics`, `inspect`,
   `sitemaps`) or a community MCP server. The most used, [`AminForou/mcp-gsc`](https://github.com/AminForou/mcp-gsc),
   asks for the read/write scope and can submit sitemaps; its `GSC_ALLOW_DESTRUCTIVE` (default `false`) only gates
   adding or deleting sites and deleting sitemaps. Prefer the wrapper on the read-only scope, which can't write.

**PSI key.** Create one with "Get a Key" on
[Get started](https://developers.google.com/speed/docs/insights/v5/get-started) or on the Cloud console's Credentials
page, and restrict it to the PageSpeed Insights API. The docs call a key optional, but keyless calls returned 429
(2026-10-13). For field data, also enable the Chrome UX Report API in the same project and add it to the key's
restrictions.

**GA4.** Google's [`google-analytics-mcp`](https://github.com/googleanalytics/google-analytics-mcp) (experimental),
installed per its README. It needs the Admin and Data APIs enabled and read-only credentials; the Search Console
service account works, added as a Viewer on the GA4 property.

**Logs and browser.** A Grafana or Loki MCP server or claude.ai connector for log history, a Kubernetes MCP server for
the current pods, and Playwright or Chrome DevTools MCP for the rendered DOM.
