# Data sources — what was measured with what (2026-07-24)

| Source | Status | Used for |
|---|---|---|
| Google SERP (browser, `gl=ca`/`gl=us`, `num=20`) | USED | Step-3 SERP pulls, both runs |
| Location override (DevTools geolocation) | NOT USED | Browser session was not geo-spoofed; the keywords are themselves geo-modified, so SERPs are representative but not resident-identical. MODE noted per run. |
| Ahrefs / Ahrefs Webmaster Tools | UNAVAILABLE | No account. AWT signup is the #1 operator action — it fills the whole "ours" row incl. velocity, free. |
| Moz Link Explorer API | UNAVAILABLE | No key configured (free tier exists — operator signup). |
| Bing Webmaster Tools | UNAVAILABLE | Not verified yet (operator: Import from GSC). |
| Common Crawl web graph (tier 0) | DEFERRED | Domain-level only — fills none of the four page-level grid columns (per plan C2). Scheduled for the T+30 remeasure as domain-level context. |
| Google Search Console | UNAVAILABLE | Property not created yet (operator, DNS TXT). |
| IndexNow | USED | 8 sitemap URLs submitted 2026-07-24 (202 Accepted → Bing/Yandex/Seznam/Naver). Key file at site root. |

Baseline probes, redirect verification, sitemap and schema builds: see
`~/beautyhaus-preseo-20260724-1532.tar.gz` (pre-change rollback) and git history.
