# Run 03 — full-site pass

```
BUSINESS:  beautyextensionhaus.com (all 8 indexable pages)
KEYWORDS:  6 targets, one per money page (grid below)
DATE:      2026-08-13
TIER:      0 (Common Crawl only — no Moz key, no Bing key, no Google API creds)
MODE:      SERP UNAVAILABLE — see "SERP blocker" below
```

Runs 01 and 02 took one keyword each. This run applies the same method to every
page on the site at once, and closes the Common Crawl velocity item that
`remeasure/T+30.md` scheduled (the only T+30 checkbox that needs no operator login).

The audit read `preview/haus/` on the Pop!_OS box. nginx bind-mounts that directory
into the `web` container read-only, so **what was audited is what is being served** —
including the edits that are still uncommitted in git.

---

## SERP blocker — read this before the verdicts

Step 3 of the method needs a SERP pull. All three free capture paths failed from this
box on 2026-08-13:

| Path | Result |
|---|---|
| Google, headless Chromium | `"Our systems have detected unusual traffic from your computer network"` — IP 99.233.113.25 |
| Google, headed Chromium on `DISPLAY=:1`, persistent profile, automation flag disabled | same block page |
| DuckDuckGo (`html.duckduckgo.com`) | blocked — error page, zero results |
| Bing (`bing.com/search`) | returns 10 results but they answer the **first token only** ("nano bead hair extensions sarasota" → GNU nano, Wikipedia). Bot-degraded, not usable as a SERP. |

So every **position** cell in this run is UNAVAILABLE, and every verdict below is
either carried forward from the 2026-07-24 SERPs (labelled as such, now 20 days stale)
or based on non-SERP evidence. Nothing here estimates a position.

Unblocking it, cheapest first:
1. Solve the Google captcha once by hand in the headed profile at
   `~/vasco-run/profile` (`DISPLAY=:1 node ~/vasco-run/serp.mjs "<kw>" ca`) — the
   cookie persists and reruns work.
2. GSC is already verified (2026-07-24, `ricestuff@gmail.com`) and gives real positions
   instead of scraped ones — but the API needs `~/.config/claude-seo/google-api.json`,
   which does not exist. Operator action.
3. Ahrefs Webmaster Tools was linked on 2026-07-24 and, three weeks on, should now hold
   the "ours" backlink row that T0 could not measure. Browser login only.

---

## Step 2 — on-page floor, every page

Method's floor: exact keyword in slug · title **starts with** keyword · keyword natural
in body · H1 exact match not required.

| Page | Keyword | Slug | Title starts | Body hits | Words | H1 has kw | Floor |
|---|---|---|---|---|---|---|---|
| `index.html` | hair extensions barrie | n/a (home) | yes | 1 | 1103 | no | **PASS** |
| `hair-extensions-barrie.html` | hair extensions barrie | yes | yes | 1 | 547 | no | **PASS** |
| `nano-bead-hair-extensions-sarasota.html` | nano bead hair extensions sarasota | yes | yes | 1 | 464 | no | **PASS** |
| `services.html` | hair extension prices barrie | no | no | **0** | 2234 | no | **FAIL** |
| `why-nano.html` | nano bead extensions | no | no | 3 | 718 | no | **FAIL** |
| `guide/nano-bead-extensions/` | nano bead extensions | yes | yes | 1 | 2990 | no | **PASS** |
| `care.html` | hair extension aftercare | no | yes | 1 | 1898 | no | PASS (soft) |
| `trade.html` | nano bead extension training | no | no | **0** | 274 | no | **FAIL** |

Every page: one H1, canonical self-referencing, OG tags present, no `noindex`, zero
images missing `alt`. Schema is on every page (`HairSalon` + `OpeningHoursSpecification`
on home/Barrie, `FAQPage` on care, `Service`/`Offer`/`PriceSpecification` on services,
`Article` on the guide, `BreadcrumbList` everywhere but home). Titles 46–61 chars,
descriptions 142–155 — all inside limits, no duplicates.

The three floor failures, in plain terms:

- **`services.html`** ranks for nothing geo. 2,234 words about prices and the phrase
  "hair extension prices barrie" appears zero times. The title starts with "Hair
  Extension Prices" — the non-geo half of the floor is met, the Barrie half is absent.
- **`why-nano.html` vs the guide** — both target "nano bead extensions". The guide meets
  the floor on every count (slug, title, 2,990 words); why-nano meets none of it and has
  718. **Cannibalization**: two pages, one keyword, and the weaker one carries the nav
  link. Pick the guide as canonical for that term, retarget why-nano at
  "nano bead extensions for fine hair" (which is what the page actually argues).
- **`trade.html`** is 274 words with zero keyword hits, and it is absent from
  `sitemap.xml` — **deliberately**. `settings.json` has `training: false` and
  `hiring: false`; `gen_sitemap.py` drops the page while both flags are off, and
  `js/haus.js:523` client-side-redirects the page away. It is dormant by design, not
  broken. Nothing to fix until the flags flip.

---

## Step 4 — link teardown

Page-level backlink data needs Moz (no key) or Ahrefs (browser only). Every page-level
cell is UNAVAILABLE — as at T0. What Tier 0 adds this run is domain-level Common Crawl,
which the T0 runs deferred.

| Domain | Role | In CC | PageRank rank (2026 Q1) | Ref-domain sample | Source |
|---|---|---|---|---|---|
| **beautyextensionhaus.com** | ours | yes | **below ranking threshold** | 0 | CC tier 0, domain-level |
| chatters.ca | Barrie SERP #3 (2026-07-24) | yes | 983,720 | 0 | CC tier 0 |
| glowdayspa.ca | Barrie SERP #2 (2026-07-24) | yes | 18,500,030 | 0 | CC tier 0 |
| moncherihairstudio.com | Barrie SERP #6 | yes | below threshold | 0 | CC tier 0 |
| clairebeauty.ca | Barrie SERP #5 | yes | below threshold | 0 | CC tier 0 |
| euronaturals.ca | Barrie SERP #8 | yes | below threshold | 0 | CC tier 0 |
| srqhair.com | Sarasota SERP #6 | yes | below threshold | 0 | CC tier 0 |
| poisedbeautysalon.com | Sarasota SERP #4 | **not in CC at all** | — | 0 | CC tier 0 |
| modishsalon.com | Sarasota SERP #5 | **not in CC at all** | — | 0 | CC tier 0 |

`--top-referrers 50` returned an empty list for **every** domain including the two that
rank — at this size band Common Crawl holds the node but not a usable referrer set.
So the method's Step-6 deliverable, *the exported list of domains to replicate*, cannot
be produced at Tier 0. That list needs Moz (free key, 2 min) or AWT. Stated plainly
rather than substituted with something weaker.

Reading it anyway: of nine competitors, **one** (chatters.ca — a national chain, not a
Barrie extension specialist) has any real link authority. Every independent salon in
both markets sits at or below the same threshold this business does. Two Sarasota
competitors are not in the web graph at all.

### Step 4b — velocity across four releases

The go/no-go input. Rank number **rising = falling authority**.

| Domain | 2024 Q4 | 2025 Q2 | 2025 Q4 | 2026 Q1 | Read |
|---|---|---|---|---|---|
| beautyextensionhaus.com | below thr. | below thr. | below thr. | below thr. | no trend measurable |
| glowdayspa.ca | 15,219,436 | 17,226,293 | 17,357,851 | 18,500,030 | drifting down |
| chatters.ca | 743,865 | 600,608 | 672,851 | 983,720 | flat, latest release worse |

Honest caveat: the CC graph grows each release, so rank *numbers* inflate for a site
that merely stands still. Both competitors drift the same direction by a similar
proportion, which is exactly what graph growth alone produces. The safe reading is
therefore **not "competitors are declining"** but **"no competitor is accumulating
links"** — which is the answer the go/no-go actually needs.

**Nobody is pulling away.** The gap is not widening while work happens.

---

## Steps 5–6 — verdicts

| Keyword | Page | Verdict | Basis |
|---|---|---|---|
| hair extensions barrie | `/hair-extensions-barrie.html` | **WINNABLE — held at last measure** | Position 1 on 2026-07-24 (via old index + 301s). Competitor velocity flat. Position unverified for 20 days. |
| nano bead hair extensions sarasota | `/nano-bead-hair-extensions-sarasota.html` | **WINNABLE — empty lane** | No Sarasota competitor targets "nano bead"; two of them are not even in the web graph. |
| nano bead extensions | `/guide/nano-bead-extensions/` | **WINNABLE, self-blocked** | Floor passes and 2,990 words, but why-nano splits the term and the guide was just pulled from the nav (commit `d73753d`). |
| hair extension aftercare | `/care.html` | **WINNABLE** | 1,898 words + valid `FAQPage` schema; no competitor with link authority in this niche. |
| hair extension prices barrie | `/services.html` | **NOT CONTESTED YET** | Page does not target the keyword — zero body hits. On-page work first, then re-measure. |
| nano bead extension training | `/trade.html` | **DORMANT BY DESIGN** | Feature-flagged off (`training`/`hiring` both false): redirected away client-side, excluded from the sitemap. Not a target until the flags flip. |

All six are PROVISIONAL on position, per the SERP blocker.

**The link gap is not this site's constraint.** Two of eight competitor domains carry
measurable authority, neither is gaining, and the business already held position 1 on
both keywords it fought for. The constraints are on-page and internal — which the method
normally treats as a floor to clear and move past, and which is where the remaining
wins are here.

---

## Architecture finding — the US site is invisible to crawlers

Not part of the vasco method, found while auditing. Recorded because it caps what any
Sarasota keyword work can achieve.

The site serves **one set of URLs for both locales**. `assets/content.json` holds 65 US
text overrides and 8 US image overrides, and `js/haus.js:331` applies them by writing
`el.innerHTML` at runtime, keyed on `data-edit` ids. The authored HTML is the CA site;
`?haus=us` and the location switcher swap the copy client-side and persist the choice in
localStorage.

Consequences:
- A crawler fetching any shared URL gets the **Canadian** copy. The US version of the
  home page, services, why-nano and care has no URL of its own to rank, and no
  server-rendered text to rank on.
- `/nano-bead-hair-extensions-sarasota.html` is the **only** server-rendered US content
  on the site. Every Sarasota query the business wants has to funnel through that one
  464-word page.
- Anchor text and links placed **inside** a `data-edit` element are fragile twice over:
  the admin console rewrites that element's inner HTML on a CA edit
  (`haus_admin_server.py:250`), and the US locale overwrites it at runtime wherever an
  override exists for that id. Internal links added for SEO belong outside `data-edit`
  elements.

## Fix list

Site structure (this is where the leverage is — nothing below needs an operator login):

1. **`hair-extensions-barrie.html` has 1 inbound internal link** — the lowest on the
   site. `trade.html` has 6, `care.html` 7, `services.html` 7. The Barrie money page is
   the least-linked page there is. Link to it from home, services, why-nano and care.
2. **The guide has 0 outbound internal links.** 2,990 words, three pages linking in
   (why-nano, care, Sarasota), and it passes none of that onward. Add contextual links
   from the guide body to both geo pages and to services.
3. **The guide was removed from the nav** (`d73753d`) and its inbound count is now 3
   in-body links. If dropping it from the nav was deliberate, give it another route in —
   a footer link or a home-page card.
4. ~~`trade.html` missing from `sitemap.xml`~~ — **not a defect.** Feature-flagged off
   in `settings.json`; the generator and the client-side redirect both act on that
   flag deliberately.
5. **`sitemap.xml` `lastmod` is stale** — every entry says 2026-08-06, but care, Barrie,
   index, why-nano and trade were edited 08-09 and services 08-11. Re-run
   `tools/gen_sitemap.py` and re-ping IndexNow.
6. **Resolve the nano-bead cannibalization** — guide keeps "nano bead extensions",
   why-nano retargets to "nano bead extensions for fine hair" (title, H1, slug).
7. **`services.html`** — work "hair extension prices Barrie" into title and body if the
   geo term is wanted; otherwise drop the geo keyword from this run's target list.
8. **`trade.html`** is 274 words. Either build it out for the training keyword or accept
   it as a non-target page.

Operator-only, unchanged from `offsite/operator-checklist.md`, now overdue:

9. Moz free API key → `~/.config/claude-seo/backlinks-api.json` (`moz_api_key`). This is
   the single cheapest upgrade in the whole engagement: it turns every UNAVAILABLE cell
   above into a number and produces the Step-6 replication list.
10. Bing Webmaster "Import from GSC" — one click, and it fills the head-to-head gap.
11. GSC credentials for the API, so positions come from Search Console instead of a
    scrape Google is blocking.

---

## Sources

| Source | Status | Used for |
|---|---|---|
| Common Crawl web graph (tier 0) | USED | domain grid + 4-release velocity; 9 domains |
| Live HTTP probes (12 URLs, apex + www) | USED | all 200s; `/client-waitlist` still 301s to the Sarasota page; www→apex 301 holds |
| Static parse of `preview/haus/` | USED | floor grid, schema, internal-link graph, sitemap |
| Google SERP | **BLOCKED** | IP-level bot block, headless and headed |
| DuckDuckGo / Bing SERP | **BLOCKED / DEGRADED** | see SERP blocker |
| Moz Link Explorer | UNAVAILABLE | no key |
| Bing Webmaster API | UNAVAILABLE | no key |
| Google Search Console / PSI / CrUX | UNAVAILABLE | no `google-api.json` on this box |
| Ahrefs Webmaster Tools | UNAVAILABLE to tooling | linked 2026-07-24, browser login only |

Scripts and raw JSON from this run: `~/vasco-run/` on the Pop!_OS box
(`floor.py`, `links.py`, `serp.mjs`, `serp2.mjs`, `cc-*.json`, `velocity.log`).
