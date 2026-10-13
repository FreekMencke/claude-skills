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
| Field Core Web Vitals | CrUX | PSI's `loadingExperience`; low-traffic sites have none |
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
- Lab has no INP. Field data, when PSI returns it, outranks lab numbers.

## Server logs

Use the route the repo's docs name. Filter by user agent: drop requests whose user agent contains `seo-audit` (this
audit's own), then count Googlebot and other bots per template, and render times (p50, p90) per template. A
self-declared Googlebot is unverified; Google verifies by reverse DNS.

## GA4

Only through a GA4 MCP server the session already has. Useful questions: landing pages for the Organic Search channel
(sessions, engagement) per template. Without one, leave GA4 out of the tier; don't offer data the session can't read.
