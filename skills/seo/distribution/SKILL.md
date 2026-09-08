---
name: distribution
description: Repurpose a published URL into an X thread, a LinkedIn post, and a Reddit answer that link back, keyword in the first line; also trend-led posts from Google Trends or X. Use when asked to promote, share, or distribute an article, or to write a thread or post from a URL.
---

# Distribution

Social posts are indexed within hours and put the URL in front of the people who link. LinkedIn and Reddit mark outbound links `nofollow` (Reddit `nofollow ugc`); X dropped the attribute in 2022 but routes through t.co redirects. Google has treated these attributes as hints since 2019 (crawling since March 2020) and says a nofollowed link carries no value rather than reduced value. Count on discovery and referral traffic, not on ranking credit. Reddit threads themselves rank: Sistrix data cited by Amsive shows reddit.com's Google visibility rising from rank 68 to rank 5 among US domains between July 2023 and July 2024 (top 50,000 keywords sample); a good answer in a ranking thread is a page-1 placement even without a link.

## Steps

1. **Read the source page.** Extract the primary keyword, the one claim or number worth quoting, 3–5 sub-points, and the original evidence (screenshot, own number). With a workspace, use `glossary.md` terms and the brand-voice lines in `strategy.md`.

2. **Produce three pieces** per [references/formats.md](references/formats.md): X thread, LinkedIn post, Reddit answer. Keyword in the first line of each. The link back sits in the last post of the thread, at the end or in the first comment on LinkedIn, and on Reddit only where it answers the thread.
   The answer is one table, `piece | platform | first line | where the link sits`, with the ready-to-paste texts under it.
   Done when three ready-to-paste texts exist with the URL placed, and the Reddit piece names a subreddit and the type of thread it answers.

3. **Trend hook, when given.** A trending topic from Google Trends or X leads the first line; sentence two bridges to the page. Without a trend, skip.

4. **Reply targets.** Name 3 larger posts or threads in the niche where a useful reply fits; write each reply. The link goes in only when the reply needs it to be complete. The three replies join the same table, one row each, with the thread in the platform cell.
   Done when three replies exist, each useful with the link removed.

5. **Log** one `distribution` row per published piece (`scaffold.py <domain> --log` in `jorekai-seo:setup`), `verify after` 14 days: referral clicks and any new link.

## Rules

- Useful first, link second. A reply that reads as an ad is removed and the account flagged.
- Reddit: the comment answers the question in full; the link is a footnote. Reddit retired its formal 10 % self-promotion rule; moderators judge whether the account is a participant or a promoter. Subreddit rules override everything.
- Every piece stands alone without the link.
