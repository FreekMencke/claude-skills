# Google's rules the audit checks

Quotes from Google's own pages, read 2026-10-13. Google changes these: before a rule decides a finding, check that it
still holds on its linked page (`curl -sL <url> | grep -i -o '.\{0,120\}<phrase>.\{0,200\}'`). For a rule that isn't
here, read Google's page first; never state one from memory. [Search Central documentation
updates](https://developers.google.com/search/updates) lists every change.

## Contents

- Rendering and the server HTML
- Status codes
- Titles and descriptions
- Canonicals and duplicates
- noindex and robots.txt
- Sitemaps
- Links and images
- Structured data
- Core Web Vitals
- AI features and llms.txt
- Crawler user agents
- Advice Google retired

## Rendering and the server HTML

[JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics):

- "Googlebot queues all pages with a 200 HTTP status code for rendering, unless a robots meta tag or header tells
  Google not to index the page."
- "If the HTTP status code is non-200 (for example, on error pages with 404 status code), rendering might be
  skipped." So an error page's status and content must be in the server HTML.
- "When Google encounters the noindex tag, it may skip rendering and JavaScript execution … If you do want the page
  indexed, don't use a noindex tag in the original page code."
- Canonical: "you shouldn't use JavaScript to change the canonical URL to something else than the URL you specified
  as the canonical URL in the original HTML."
- "Google can only discover your links if they are `<a>` HTML elements with an href attribute."

So the server HTML (curl) and the rendered DOM must agree on the canonical and the robots meta.

## Status codes

[How HTTP status codes affect Google's crawlers](https://developers.google.com/crawling/docs/troubleshooting/http-status-codes):

- 2xx: "If the content suggests an error for Google Search, an empty page or an error message, Search Console will
  show a soft 404 error." A not-found state served with 200 is a soft 404.
- "Google doesn't index URLs that return a 4xx status code, and URLs that are already indexed and return a 4xx status
  code are removed from the index."
- 301: "a strong signal that the redirect target should be processed"; 302: "a weak signal".
- "Googlebot generally follows 10 redirect hops".

## Titles and descriptions

- [Title links](https://developers.google.com/search/docs/appearance/title-link): "Make sure every page on your site
  has a title specified in the `<title>` element." "Avoid vague descriptors like "Home" for your home page". "While
  there's no limit on how long a `<title>` element can be, the title link is truncated in Google Search results as
  needed, typically to fit the device width." "Avoid keyword stuffing." "Google uses a number of different sources to
  automatically determine the title link". On a site name in every title: "consider including just your site name at
  the beginning or end of each `<title>` element, separated from the rest of the text with a delimiter such as a
  hyphen, colon, or pipe".
- [Meta descriptions](https://developers.google.com/search/docs/appearance/snippet): "Google primarily uses the content
  on the page to automatically determine the appropriate snippet." "There's no limit on how long a meta description
  can be, but the snippet is truncated in Google Search results as needed, typically to fit the device width."

A title or description shared by every page of a template is a finding; a length outside 60 or 160 characters is not.

A `Brand: phrase` title whose phrase starts lowercase is a low finding: check `probe.sh`'s title column. Google's page
allows the format, but on 2026-10-13 Google showed two such titles as `phrase - Brand`, leading with the lowercase
word (claude-kb WEB-033, through the `claude-kb-lookup` skill). Fix: capitalise the phrase, or write `Phrase - Brand`.

## Canonicals and duplicates

[Consolidate duplicate URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls):

- "Redirects: A strong signal". "rel="canonical" link annotations: A strong signal". "Sitemap inclusion: A weak
  signal".
- "Don't use the robots.txt file for canonicalization purposes."

Duplicates matter when Google reports them (Search Console's Pages report, or URL Inspection's `googleCanonical`
differing from `userCanonical`). Without that, a duplicate URL is low impact.

## noindex and robots.txt

- [Block indexing](https://developers.google.com/search/docs/crawling-indexing/block-indexing): "For the noindex rule
  to be effective, the page or resource must not be blocked by a robots.txt file". A page both disallowed and
  `noindex` can still be indexed.
- [Robots meta tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag): "Any rule that can
  be used in a robots meta tag can also be specified as an X-Robots-Tag." Check the header as well as the tag.
- [robots.txt spec](https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec): "Google supports the
  following fields (other fields such as crawl-delay aren't supported): user-agent … allow … disallow … sitemap".

## Sitemaps

[Build a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap):

- "All formats limit a single sitemap to 50MB (uncompressed) or 50,000 URLs."
- "Google ignores `<priority>` and `<changefreq>` values."
- "Google uses the `<lastmod>` value if it's consistently and verifiably (for example by comparing to the last
  modification of the page) accurate."

Check that listed URLs return 200 at their canonical form; a sitemap of redirects or 404s wastes crawl.

## Links and images

- [Crawlable links](https://developers.google.com/search/docs/crawling-indexing/links-crawlable): "Google can only
  crawl your link if it's an `<a>` HTML element (also known as anchor element) with an href attribute."
- [Image SEO](https://developers.google.com/search/docs/appearance/google-images): "The most important attribute when
  it comes to providing more metadata for an image is the alt text".

A page template reachable only through the sitemap (no `<a href>` to it in any server HTML) is a discovery finding.

## Structured data

- [General guidelines](https://developers.google.com/search/docs/appearance/structured-data/sd-policies): "Google does
  not guarantee that your structured data will show up in search results, even if your page is marked up correctly
  according to the Rich Results Test." Markup must represent the page's visible main content.
- Which types still earn a rich result: [Search gallery](https://developers.google.com/search/docs/appearance/structured-data/search-gallery).
  Read it before recommending a type; the list shrinks (below).
- No API validates markup: the Rich Results Test is a manual step for the user.

## Core Web Vitals

[Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals): "strive to have LCP occur
within the first 2.5 seconds", "an INP of less than 200 milliseconds", "a CLS score of less than 0.1". These are field
thresholds (75th percentile of real visits); a lab run only estimates LCP and CLS and has no INP.

## AI features and llms.txt

[AI features and your website](https://developers.google.com/search/docs/appearance/ai-features): "There are no
additional requirements to appear in AI Overviews or AI Mode". "You don't need to create new machine readable files,
AI text files, or markup to appear in these features." Don't recommend llms.txt as a search fix.

## Crawler user agents

- [Google's common crawlers](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers):
  Googlebot Smartphone is `Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like
  Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)`, where
  "Chrome/W.X.Y.Z … is a placeholder". "The HTTP user agent string can be spoofed."
- [Spam policies](https://developers.google.com/search/docs/essentials/spam-policies): cloaking is "presenting
  different content to users and search engines with the intent to manipulate search rankings and mislead users". A
  difference between the Googlebot and browser probes is a finding to explain, not proof of cloaking.

## Advice Google retired

Models still give these. Each is wrong today; flag it when the site follows it, at low impact.

| Advice | Google now |
|---|---|
| Sitemap `priority`, `changefreq` | "Google ignores `<priority>` and `<changefreq>` values." ([Build a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)) |
| Ping Google with the sitemap | "The sitemaps ping endpoint deprecation is complete." ([2023-06-26](https://developers.google.com/search/blog/2023/06/sitemaps-lastmod-ping)) |
| Meta keywords | "not used by Google Search, and it has no effect on indexing and ranking at all" ([Special tags](https://developers.google.com/search/docs/crawling-indexing/special-tags)) |
| `rel=prev/next` for pagination | "Google no longer uses these tags" ([Pagination](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading)) |
| `noindex` or `crawl-delay` in robots.txt | Unsupported fields ([robots.txt spec](https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec)) |
| Titles under 60, descriptions of 150–160 characters | "there's no limit"; truncated "to fit the device width" ([Title links](https://developers.google.com/search/docs/appearance/title-link), [Snippets](https://developers.google.com/search/docs/appearance/snippet)) |
| FAQ or HowTo markup for rich results | HowTo stopped showing 2023-09-13 ([post](https://developers.google.com/search/blog/2023/08/howto-faq-changes)); FAQ "will no longer appear in Google Search starting May 7, 2026" ([updates](https://developers.google.com/search/updates)) |
| `WebSite` + `SearchAction` for a sitelinks search box | "The sitelinks search box feature is no longer available in Google Search results." (docs removed 2024-11-29, [updates](https://developers.google.com/search/updates)) |
| FID as a Core Web Vital | "Interaction to Next Paint is now a stable Core Web Vital metric, replacing First Input Delay." ([web.dev, 2024-03-12](https://web.dev/blog/inp-cwv-launch)) |
| Keyword density, keyword in the first 100 words | Not in Google's docs; "Avoid keyword stuffing" ([Title links](https://developers.google.com/search/docs/appearance/title-link)) |
| llms.txt for search visibility | "You don't need to create new machine readable files" ([AI features](https://developers.google.com/search/docs/appearance/ai-features)) |
