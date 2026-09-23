# Fixes by check id

## http.*

- `http.fetch`: DNS, TLS, or timeout. Check the certificate chain (`openssl s_client -connect host:443`), DNS records, and that the origin answers Googlebot's user agent (some WAFs block it).
- `http.status`: non-200 on the audited URL. 4xx: restore or 301 to the replacement. 5xx: origin error, fix before anything else. 3xx after 10 hops: redirect loop; Google's crawlers stop after 10 hops as well.
- `http.https`: force HTTPS at the edge (301 from `http://`), add `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- `http.redirect-chain`: collapse to one 301 from the original URL to the final URL. Update internal links and the sitemap to the final URL. Google documents a limit of 10 hops per crawl; Mueller advises fewer than 5 for frequently crawled URLs. After a URL change keep the redirect for at least one year (Google's site-move guidance), better permanently.
- `http.redirect-temporary`: a 302, 303, or 307 in the chain. Google follows it but does not treat the target as the canonical, so the old URL can stay in the index. Use 301 or 308 for anything permanent; keep 302/307 only for genuinely temporary detours (maintenance, A/B).
- `http.ttfb`: HTML took more than 2.5 s. Cache HTML at the CDN, avoid blocking data fetches in the layout. Confirm the real number in GSC Core Web Vitals (LCP).

## render.*

- `render.bot-html`: Content is client-rendered or the server discriminates by user agent. Server-render (SSR) or pre-render (SSG) every indexable route; remove user-agent-based gating in the CDN or bot-protection layer. Verify with `curl -sA "Mozilla/5.0 (compatible; Googlebot/2.1)" URL`.
- `render.thin`: Under 300 characters of text. Either the page is genuinely thin (merge it, or add substance) or content sits in an iframe, image, or PDF. Text belongs in the HTML.
- `render.js-only` (with `--rendered`, comparing the raw fetch against a saved rendered DOM of the same URL): title, H1, canonical, body text, internal links, or structured data exist only after JavaScript runs. Server-render or pre-render the page; Google's second rendering pass can lag the first crawl by days to weeks, and every field named in the finding is invisible until it runs.
- `render.consent-wall`: a consent-management platform runs on a page the render check already found thin. The banner covering the page for a reader is not the bug; fetch the raw HTML with a Googlebot user agent (`curl -sA Googlebot URL`) and confirm the real content sits in the markup below the banner before treating this as `render.bot-html` or `render.thin`. If the text really is missing from the raw HTML, that other check id names the fix.

## head.*

- `head.title`: Missing: add `<title>`. Long: keyword first, brand last, about 50–60 characters. Google sets no character limit; it truncates by pixel width (roughly 600 px on desktop), so the number is a heuristic. Short: add the query the page targets. One title per page, unique across the site.
- `head.meta-description`: about 120–160 characters (a heuristic; Google sets no limit and rewrites descriptions freely), contains the keyword once, states a reason to click (outcome, number, year). Unique per page.
- `head.canonical`: Missing: add `<link rel="canonical" href="https://host/path">`, absolute, on every indexable page, pointing to itself. Multiple: keep one. Elsewhere: intended only for duplicates, pagination, and syndicated copies. Query-string variants canonicalize to the clean URL.
- `head.noindex`: Remove `<meta name="robots" content="noindex">` and the `X-Robots-Tag` header on pages meant to rank. Staging deployments often leak this into production. For PDFs, images, and other non-HTML files the only way to set noindex is the `X-Robots-Tag` response header. A page that must stay `noindex` but whose content is embedded elsewhere via iframe can add `indexifembedded` so the embedding pages keep the content (Google, since January 2022).
- `head.noindex-canonical`: the page says `noindex` and also canonicalizes to another URL. Mueller (September 2024): pick one. Duplicates get the canonical only; pages that must vanish get `noindex` only.
- `head.meta-refresh`: Google reads an instant meta refresh (`0;url=`) as a permanent redirect and a delayed one as temporary. Replace with a server-side 301/308; keep meta refresh only on static hosting that cannot send headers, and then with delay 0. JavaScript redirects are Google's last resort.
- `head.viewport`: `<meta name="viewport" content="width=device-width, initial-scale=1">`. Without it the page fails mobile-friendliness and mobile-first indexing.
- `head.lang`: `<html lang="de">` (BCP 47). For multi-language sites add `hreflang` alternates that reference each other and include `x-default`.
- `head.hreflang`: Google's rules: every version lists itself and all others; if two pages do not both point at each other the tags are ignored; codes are language first, region optional (`de`, `de-AT`, `de-CH`), a region alone is invalid, and `UK`, `EU`, `UN` are ignored; `x-default` names the fallback for unmatched languages, usually the language selector or the main version. HTML link tags, HTTP headers, and a sitemap are equivalent; pick one. The canonical on each version must point at itself, otherwise its hreflang is dropped (Mueller, May 2025). Same-language alternates for DE, AT, and CH with identical text are a weak case (Mueller, January 2022): add local signals (address, phone, prices in CHF) or serve one page. Search Console no longer reports hreflang errors (International targeting report removed September 2022); the script checks self-reference, x-default, and code format, not the return links. Verify those with a crawler that fetches every alternate.
- `head.dates`: `datePublished` and `dateModified` in JSON-LD must match the visible date on the page, never lie in the future, and never carry the date of the event described. Change the date only with a real content change; Mueller (February 2022): changing the date alone is "noise & useless". Google combines several signals for the date it shows, so a corrected date can take a recrawl to appear.
- `head.json-ld`: Optional. Add `Article`, `Product`, `Organization`, `LocalBusiness`, or `BreadcrumbList` where the content matches. FAQ and HowTo rich results are no longer shown for ordinary sites (since 2023); the FAQ section still helps, the schema does not. Sitelinks search box markup (`WebSite` with `SearchAction`) has been a no-op since November 2024; breadcrumbs show on desktop only since January 2025. `Organization`: `url`, `logo` (at least 112 by 112 px, crawlable), `sameAs` to profile pages. `Article`: `author.name` holds the name only, one `author` object per person. `VideoObject` only on the page where the video plays, with `name`, `thumbnailUrl`, `uploadDate`. `DiscussionForumPosting` only for user-generated posts, never staff content.
- `head.schema-invalid`: a `ld+json` block that does not parse is ignored whole, with every type in it. Usual causes: a trailing comma, an unescaped quote inside a description, a template variable that stayed empty, two objects in one block without an array. Fix the JSON, then confirm the page in Google's Rich Results Test.
- `head.schema-no-rich-result`: the page carries markup that earns nothing on an ordinary site. Remove it, or keep it only for a consumer that reads it. The FAQ section itself stays; it is the schema that returns nothing.
- `head.schema-review`: a rating or review on an `Organization`, `LocalBusiness`, or any node outside the reviewable types. An entity that controls the reviews about itself is ineligible for the star feature, so the markup earns nothing and invented reviews break the structured-data content rules. Remove the rating, or move it to `Product`, `Book`, `Course`, `Event`, `Movie`, `Recipe`, or `SoftwareApplication` where the page really shows those reviews. Ratings a customer left on a review platform belong on that platform.
- `head.open-graph`: Social previews only. `og:title`, `og:description`, `og:image` (1200×630).

## body.* / url.* / img.* / links.*

- `body.h1`: One H1 carrying the primary query is the convention this skill set follows for clarity and for the title/H1 keyword match. Google itself accepts zero or several H1s; treat this as structure hygiene, not a ranking fix. Logos and site names are not H1s.
- `body.h1-title-match`: Title and H1 share the keyword; they can differ in length and brand suffix. Google builds the title link from the `<title>`, the H1 and other headings, `og:title`, prominent styled text, and anchor text pointing at the page; in September 2021 it reported using the `<title>` as written about 87 % of the time. When the SERP shows a different title, the H1 or inbound anchors are usually the source.
- `body.error-text`: title or H1 reads like an error message ("not found", "no results", "nicht gefunden"). Google can classify a 200 page as a soft 404 from its content alone (Mueller, December 2021); Search Console reports it under "Soft 404". Reword real pages; return 404 for empty ones.
- `url.query-string`: Indexable pages live on clean paths. Parameters for tracking or filters get canonicals to the clean URL, or `noindex`.
- `url.slug`: Lowercase, hyphens, 3–6 words that are the shortened H1. Random IDs, dates, and underscores go. Changing an existing slug requires a 301 from the old URL.
- `url.slug-h1-match`: The slug carries at least the head noun of the H1. Keywords in URLs are a very small ranking factor per Google; the reason is readability in SERPs, link previews, and shared links. Never restructure existing URLs for this.
- `url.pagination-canonical` / `crawl.pagination-canonical`: page 2 and later canonicalize to page 1. Google: give each paginated page its own URL and its own canonical; `rel="prev"`/`rel="next"` is not used by Google since 2019. Infinite scroll needs paginated URLs that work without scrolling, and a sitemap that lists every item.
- `img.alt`: Descriptive alt on images that carry meaning (product, screenshot, chart). Decorative images get `alt=""`. Filenames short and descriptive. Google indexes only `<img src>` images (BMP, GIF, JPEG, PNG, WebP, SVG, AVIF); CSS background images are not indexed.
- `img.src-fallback`: `<img>` with `data-src` only. Google asks for a fallback `src` even with `srcset` or `<picture>`; lazy-loading must fire on viewport intersection (`loading="lazy"` or IntersectionObserver), never on scroll or click, because Googlebot does not interact. Images that only JavaScript can reveal also belong in an image sitemap.
- `img.lcp-lazy`: the first image is `loading="lazy"`. web.dev: never lazy-load the LCP image; give it `fetchpriority="high"` and, if it is only discoverable via CSS or JS, a `<link rel="preload">`. Confirm which element is LCP in PageSpeed Insights before changing more.
- `img.dimensions`: most images lack `width` and `height`. web.dev: always set both (or CSS `aspect-ratio`) so the browser reserves space; the common cause of layout shift (CLS).
- `links.internal`: Every page links to related pages and is linked from at least one. Descriptive anchors. Only `<a href="...">` counts as a crawlable link; buttons, `onclick` handlers, and `<span>` navigation do not. Google removed the "100 links per page" guideline before 2008; there is no cap, only "reasonable".

## redirects.* (only with `--redirects`, one fetch per row of a move's map)

- `redirects.map`: the file holds no URL rows. The first column carries the old URLs; `old,new` or `from,to` headers are read, and a file without a header is read positionally.
- `redirects.error`: the old URL got no response at all (DNS, TLS, or timeout). Check the URL is typed correctly and that the old host still resolves; a host taken fully offline before its redirects are live loses every signal on that row.
- `redirects.missing`: the old URL still answers on its own. Nothing was redirected, and both URLs now compete. Add the redirect, then re-run.
- `redirects.temporary`: the first hop is a 302, 303, or 307. Google keeps the old URL as the canonical, so the signals stay where the content no longer is. Use 301 or 308.
- `redirects.chain`: more than one hop. Collapse the map so every old URL points straight at its final target; a chain loses time on every crawl and hops are capped at 10.
- `redirects.broken`: the target answers something other than 200. Either the target moved again or the page was never built; repoint the row or serve 410 where nothing replaces it.
- `redirects.wrong-target`: the redirect lands somewhere other than the row's target, usually a catch-all rule that sends everything to the home page. A wrong target loses the ranking as reliably as no redirect.

## site.*

- `site.robots`: Missing: create `/robots.txt` with `User-agent: *`, `Allow: /`, explicit `Disallow` for admin, search, and cart paths, and `Sitemap: https://host/sitemap.xml`. Blocking: remove the `Disallow` that covers public pages. `robots.txt` blocks crawling, not indexing; use `noindex` to keep a crawlable page out of the index.
- `site.robots-noindex`: the URL is disallowed in robots.txt and carries `noindex`. Google: a page blocked from crawling never reveals its indexing rules, so the `noindex` is ignored and the URL can be indexed from links alone. To remove it, allow crawling and keep `noindex`; to keep it out of the index for good, add a removal request in GSC.
- `site.robots-sitemap`: Add the `Sitemap:` line.
- `site.robots-ai-search`: Allow `OAI-SearchBot` (ChatGPT search citations), `PerplexityBot` (Perplexity citations), `Bingbot` (Bing, Copilot, and the index behind ChatGPT search), and `Claude-SearchBot` plus `Claude-User` (Claude's search index and live fetches). Training-only tokens are a separate decision: `GPTBot` (OpenAI), `ClaudeBot` (Anthropic), `Applebot-Extended` (Apple; Applebot itself feeds Siri and Spotlight search). `Google-Extended` controls both Gemini training and Gemini grounding (content pulled from the Search index at prompt time in Gemini Apps and Vertex AI), so blocking it removes the site from Gemini answers; it does not affect Google Search inclusion, ranking, or AI Overviews, which run on Googlebot. There is no llms.txt requirement anywhere: Google's Mueller (January and June 2026) states no AI system is known to use the file.
- `site.sitemap`: Missing: generate `sitemap.xml` (index file above 50,000 URLs or 50 MB). Only canonical, 200, indexable URLs; `lastmod` reflecting real content changes. Submit in GSC and Bing. The sitemap ping endpoint was switched off in 2023; submission happens in GSC, Bing Webmaster Tools, or via `Sitemap:` in robots.txt.
- `site.sitemap-lastmod`: every URL carries the same `lastmod`, or dates lie in the future. Google uses `lastmod` only when it is "consistently and verifiably accurate" and stops believing a site whose dates do not match real changes. Emit the date of the last significant change (main text, structured data, links), not the build time, and omit `lastmod` where the CMS cannot supply it.
- `site.feed`: the page advertises an RSS or Atom feed. Google accepts a feed as a sitemap for recently changed URLs; submit it in GSC next to the XML sitemap. Sites with a feed can also push changes through WebSub, which Google still documents.
- `site.sitemap-hosts`: Every URL in the sitemap uses the canonical scheme and host.
- `site.sitemap-membership`: Add the page if it is meant to rank.
- `site.host-variant`: 301 the non-canonical host (`www` or apex) to the canonical one, path preserved. Same for HTTP.
- `site.http-redirect`: 301 `http://` to `https://` at the edge.
- `site.hsts`: Add the header once HTTPS is stable everywhere.
- `site.soft-404`: Unknown paths return status 404 (or 410 for removed content), with a helpful page body. SPA fallbacks that return 200 for everything need a server-side 404 route.
- `site.trailing-slash`: Pick one form, 301 the other, canonical on both.

## crawl.*

- `crawl.broken-link`: Fix or remove the link; 301 the old URL if it had traffic or links.
- `crawl.redirected-link`: Point internal links at the final URL. Links into the cart or checkout are not reported here (see `crawl.cart-links`).
- `crawl.tracking-params`: Remove `utm_*`, `gclid`, and similar parameters from links to the site's own pages; internal traffic is visible in analytics by referrer or page path. Where a campaign tag on an internal link is unavoidable, the target's self-referencing canonical must be the clean URL (it usually is; the parameter still costs crawl budget).
- `crawl.cart-links`: informational. Cart, checkout, and account URLs are `noindex` by design and never crawled by the script.
- `crawl.duplicate-title` / `crawl.duplicate-description`: Unique per page. Template pages need the distinguishing entity (product name, city, category) in title and description. Paginated series (reported as INFO): add the page number. URLs that are `noindex` or canonicalize elsewhere are excluded (`crawl.non-indexable` counts them).
- `crawl.non-indexable`: informational. Many such URLs (cart, add-to-cart, tracking parameters) linked from content waste crawl on a large site; on a small site ignore.
- `crawl.canonical`: Self-referencing canonical on every indexable page; see `head.canonical`.
- `crawl.h1`: See `body.h1`. Informational.
- `crawl.orphans`: Add at least one contextual internal link to each orphan from a related page, or remove the orphan from the sitemap if it should not rank. Google: "Every page you care about should have a link from at least one other page on your site"; sitemaps are the second discovery path after links (Illyes, 2019).
- `crawl.not-in-sitemap`: Add crawled indexable pages to the sitemap, or `noindex` them if they are utility pages. URLs with tracking parameters in this list are a `crawl.tracking-params` finding, not a sitemap gap.

## Hosted CMS: WordPress with Rank Math

For sites the repository does not contain. Every step names the admin screen so the user can apply it without searching; verify afterwards with the script.

- Title or meta description of one page/post/product (`head.title`, `head.meta-description`, `crawl.duplicate-*`): edit the post, open the Rank Math SEO meta box below or beside the editor, change title and description there. The exact button labels vary by editor and version (heuristic; not verified against a current screenshot).
- Archive and pagination titles (`crawl.duplicate-title` on `/blog/page/N/`): Rank Math SEO > Titles & Meta, the archive type's title template. Rank Math variables: `%page%` renders "Page N" only on page 2 and later, `%pagenumber%` the current number, `%pagetotal%` the total, `%sep%` the separator, `%sitename%` the site name.
- Redirects and removals (`crawl.broken-link`, `crawl.redirected-link`, `http.redirect-chain`): Rank Math SEO > Redirections (module must be enabled under Rank Math SEO > Dashboard > Modules, Advanced Mode). Types offered: 301, 302, 307, and the maintenance codes 410 (content deleted, no replacement) and 451. Prefer editing the link in the content over adding a redirect; a redirect is for URLs with external links or traffic.
- With shell access, every item above goes through WP-CLI instead of the admin: commands in the `seo` skill's [stacks/wordpress.md](../../seo/references/stacks/wordpress.md), handover prompt in [session-contract.md](../../seo/references/session-contract.md).
- Broken internal links: WordPress has no built-in link report. Take the `crawl.broken-link` list from the JSON, open each source page, replace the href.
- Sitemap membership (`crawl.not-in-sitemap`, `crawl.orphans`): Rank Math SEO > Sitemap Settings decides which post types and taxonomies are included; a single URL is excluded via `noindex` in its meta box (Rank Math drops `noindex` URLs from the sitemap).
