# On-page checklist

Tick every line before publishing.

## Head

- [ ] Title about 60 characters (heuristic; Google truncates by pixel width, no hard limit), primary query in the first half, brand last or omitted. Unique on the site. Google used the `<title>` as written about 87 % of the time (its own figure, September 2021); the rest comes from the H1, other headings, `og:title`, or anchor text, so keep those consistent.
- [ ] Meta description 120–160 characters, query once, one concrete reason to click (number, outcome, year, "free").
- [ ] Slug: lowercase, hyphens, 3–6 words, the shortened H1. Existing slug stays unless a 301 is set.
- [ ] Self-referencing canonical, `lang`, viewport (template-level; verify once with `jorekai-seo:tech-audit`).
- [ ] `datePublished` and `dateModified` in the Article JSON-LD equal the visible dates; never a future date, never the date of the event described.
- [ ] Structured data only for what the page is (`Article`, `Product`, `Organization`, `BreadcrumbList`), and every value in it stands visibly on the page. No rating or review markup for the site's own business: an entity that controls its own reviews earns no stars, and invented reviews break Google's structured-data content rules. `FAQPage` and `HowTo` earn no rich result; write the FAQ, skip the markup.
- [ ] `<meta name="robots" content="max-image-preview:large">` when the page should appear in Discover with a large image; the hero image at least 1200 px wide.

## Body

- [ ] One H1 (convention, Google accepts more); carries the primary query; matches the title's keyword.
- [ ] First paragraph answers the query in two sentences.
- [ ] Primary query in one H2; secondary queries in H2/H3 where they fit naturally.
- [ ] At least one piece of original evidence: screenshot, own number, tested result. Marked as a slot until the author fills it.
- [ ] Table or list wherever the top results use one.
- [ ] 3-question FAQ at the end, questions from GSC or People-also-ask, answers of 2–4 sentences.
- [ ] Alt text on the first image and on every image that carries meaning; `alt=""` on decoration. Descriptive filenames. Every `<img>` has a real `src` (plus `srcset` if wanted), `width` and `height`; the hero image is not lazy-loaded and carries `fetchpriority="high"`. Images only in CSS backgrounds are not indexed.
- [ ] No stale year, price, version, or "new" claim.

## Who, how, why (Google's helpful-content questions)

- [ ] Who: a byline with a real name that links to an author page with background. On product sites, the company page counts. Bylines are for readers: Google's Sullivan (January 2024) says they "don't help you rank better" and Google does not verify credentials. In `Article` JSON-LD, `author.name` holds the name only, one `author` object per person.
- [ ] Contact, about, and (for shops and YMYL pages) payment and return policies are reachable: the rater guidelines (September 2025, section 2.5.3) give a Low rating to pages handling money or trust with "an unsatisfying amount of customer service information or contact information". A commercially run site in Germany needs an imprint (Impressum) by law regardless (Digitale-Dienste-Gesetz, paragraph 5); any site collecting personal data needs a privacy policy (Datenschutzerklärung) covering GDPR Article 13's disclosures.
- [ ] How: the page says how the result was produced (tested on what, measured how, when). The evidence slots feed this.
- [ ] Why: the page exists to answer the query for a reader; a page written to fill a keyword slot fails this test even with the boxes above ticked.

## Links

- [ ] 2+ internal links out to related pages, descriptive anchors.
- [ ] 2+ internal links in from older pages: source URL, anchor text, the paragraph that gets the link.
- [ ] External links only to sources a reader would want; `rel="sponsored"` on paid ones.

## After publishing

- [ ] `lastmod` in the sitemap updated.
- [ ] GSC URL Inspection > Request indexing.
- [ ] URL handed to `jorekai-seo:distribution`.
