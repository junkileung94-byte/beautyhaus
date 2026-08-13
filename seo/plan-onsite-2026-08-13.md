# On-site SEO plan — everything doable without a Google login

```
SITE:   beautyextensionhaus.com
DATE:   2026-08-13
BASIS:  seo/vasco/run-03-full-site/RUN.md (floor grid, link graph, Tier-0 link teardown)
SCOPE:  code + content only. No GSC, no GBP, no directory work, no link building.
```

The link teardown said the gap is not this site's constraint: of nine competitor
domains, one has real authority and none are accumulating links. So the ceiling is
on-site, and this is the list of things that raise it before anyone logs into Search
Console.

---

## Constraints this plan has to respect

Four properties of this codebase decide *how* every task below is done. Ignoring them
breaks the client's admin console or the US site.

1. **Edits are live the moment they are saved.** nginx bind-mounts `preview/haus` into
   the `web` container read-only (`deploy/docker-compose.yml:21`). There is no build, no
   staging copy, and `seo/` is untracked while `preview/haus` has 14 uncommitted modified
   files. Snapshot before touching anything.
2. **`data-edit` elements belong to the admin console.** `haus_admin_server.py:250`
   rewrites the *entire inner HTML* of a `data-edit` element when the client edits that
   slot. Any `<a>` placed inside one is one client edit away from deletion. New internal
   links go **outside** `data-edit` elements — in their own wrapper.
3. **65 US text overrides are keyed to `data-edit` ids** (`assets/content.json`, applied
   at `js/haus.js:331`). Renaming an id orphans its override; rewriting CA copy under an
   id that has a US override means US visitors keep seeing the old copy. `why-nano.html`
   alone has **32** overrides, including `wn-title`. Every copy change below names
   whether a paired `content.json` edit is required.
4. **`trade.html` is dormant on purpose** (`settings.json`: `training: false`,
   `hiring: false` → dropped from the sitemap, redirected away at `js/haus.js:523`).
   It is out of scope until those flags flip.

---

## Phase 0 — make the work reversible (30 min)

- Tarball `preview/haus` + `tools` + `assets/content.json` to
  `~/beautyhaus-preseo-<date>.tar.gz`, matching the convention of the July run.
- Commit the 14 modified + 33 untracked paths first, on a branch. Right now the live
  site is the only copy of three weeks of edits, and `seo/` is not in git at all.
- Record a "before" baseline: `~/vasco-run/floor.py`, `~/vasco-run/links.py`, and the
  12-URL live probe, saved to `seo/vasco/run-03-full-site/baseline-before.txt`.

**Gate:** rollback path exists and is tested (extract the tarball to a temp dir, diff).

---

## Phase 1 — indexing hygiene (1 hour, zero risk)

Cheap, mechanical, and it makes everything later land faster.

1. Re-run `python3 tools/gen_sitemap.py`. `lastmod` currently says 2026-08-06 for all 8
   URLs while care/barrie/index/why-nano were edited 08-09 and services 08-11.
2. Re-ping IndexNow with the refreshed sitemap (the key file is already at site root;
   July's submit returned 202).
3. Confirm the 8 canonicals still match the sitemap — `gen_sitemap.py` already fails on a
   missing canonical, so this is just reading its exit code.
4. Decide `docs/`: those two pages are 404 live and excluded from the sitemap, but
   `robots.txt` does not disallow `/docs/`. Either leave it (nothing links to them) or add
   the Disallow for tidiness. Low stakes.

**Gate:** sitemap has 8 URLs with true mtimes; IndexNow returns 202; all 12 probes still 200.

---

## Phase 2 — internal link architecture (half a day, biggest cheap win)

The run-03 link graph, inbound counts: `index` 8, `care` 7, `services` 7, `trade` 6,
`why-nano` 6, **`guide` 3, `sarasota` 2, `barrie` 1**. The three pages that are supposed
to earn money are the three worst-linked pages on the site, and the dormant page outranks
two of them.

5. **Barrie page: 1 → 5+ inbound.** Contextual links from `index.html` (studio/visit
   section), `services.html` (pricing intro), `why-nano.html` (closing CTA) and
   `care.html` (booking line). Anchor text varies naturally around "hair extensions in
   Barrie" — no repeated exact-match anchor on every one.
6. **Sarasota page: 2 → 5+ inbound.** Same treatment from `index.html`, `services.html`,
   `guide/`. This is also the only indexable US page, so every link into it is worth more
   than the count suggests (see Phase 4).
7. **Guide: 0 outbound → 4.** 2,990 words that pass nothing onward. Add in-body links to
   both geo pages, `services.html` and `care.html` at the natural points (candidacy →
   Barrie/Sarasota, cost → services, maintenance → care).
8. **Give the guide a route back in.** It was pulled from the nav in `d73753d` and now
   survives on three in-body links. If the nav removal stays, add a footer link or a home
   page card so it is not one edit away from orphaned.

All eight links go in markup **outside** `data-edit` wrappers (constraint 2). Where a
sentence needs the link inline, wrap the link in its own non-`data-edit` element rather
than nesting it in the editable paragraph.

**Gate:** re-run `links.py`; assert every money page ≥4 inbound, guide ≥4 outbound; live
probes still 200; open the admin console and edit one slot on each touched page to confirm
nothing eats the new links.

---

## Phase 3 — fix the three floor failures (half a day)

9. **Nano-bead cannibalization.** `guide/nano-bead-extensions/` and `why-nano.html` both
   target "nano bead extensions"; the guide passes the floor on every count, why-nano
   passes none of it. Guide keeps the term. Retarget why-nano to **"nano bead extensions
   for fine hair"** — which is what the page actually argues — in `<title>`, H1 and the
   opening paragraph. **Keep the slug** (`/why-nano.html`); no URL change, no redirect.
   **Paired edit required:** `wn-title` and 31 other `wn-*` ids carry US overrides in
   `content.json` — update the US strings in the same pass or the US site keeps the old
   copy.
10. **`services.html`** — 2,234 words about pricing, zero hits for "hair extension prices
    barrie". Either work the geo phrase into the title and one body section, or drop the
    geo keyword from the target list and let the Barrie page own geo while services owns
    "hair extension prices". Recommendation: **the second** — one geo page per market is
    cleaner than three pages fighting over "barrie". Decision needed.
11. **`care.html`** — title starts with the keyword, but the H1 is "Ask us anything.
    We've heard it all." Add the term to the H1 or the first H2. `care-4` is the only
    `care-*` id with a US override, so the risk here is small.

**Gate:** `floor.py` shows PASS on every targeted page; no duplicate title/H1 targeting
across pages.

---

## Phase 4 — the US site has no URLs (the actual ceiling; 1–3 days depending on option)

Recorded in run-03 as the architecture finding. One set of URLs serves both locales;
`content.json` swaps 65 text slots and 8 image slots client-side. A crawler always gets
the Canadian copy. `/nano-bead-hair-extensions-sarasota.html` is the **only**
server-rendered US content on the site — 464 words carrying an entire market.

Three options, cheapest first:

- **A. Deepen the one US page.** 464 → 900+ words, add `FAQPage` schema, service list with
  US pricing, neighbourhood/parking detail for 1724 4th St. No architecture change. Half a
  day. Raises the ceiling a little; does not remove it.
- **B. Prerender US variants at their own URLs.** A build step that applies
  `content.json["us"]` to the authored HTML and writes `/us/<page>.html` (or `/sarasota/`),
  plus `hreflang` pairs `en-CA`/`en-US` and self-canonicals both ways. The admin console
  keeps editing `content.json` exactly as today; the generator re-runs on save, like
  `gen_sitemap.py` already does. 1–2 days. This is the one that actually removes the
  ceiling.
- **C. Leave it.** Defensible while Sarasota is pre-opening — but then stop expecting US
  queries other than the single nano-bead phrase to rank at all, and say so to the client.

Recommendation: **A now, B when Sarasota opens.** B is a real feature with a real
regression surface (two URL sets, hreflang, sitemap, admin save hook), and it should not
be bolted on the week before a location launch.

**Decision needed before Phase 4 starts.**

---

## Phase 5 — content depth (1 day, do after Phases 2–3 land)

12. **Barrie page 547 words.** Thinnest money page on the site. Take it to ~900 with
    material that is actually local: the 480 Mapleton Ave studio, parking, consultation
    process, what a first appointment costs and how long it takes. Add `FAQPage` schema —
    `care.html` already proves the pattern works here.
13. **Guide has zero images.** 2,990 words, no imagery: worse dwell time and no image-search
    surface. Add 4–6 process shots with descriptive alt text from `haus-media-library`.
14. **Home page** — 1,103 words across 15 H2s, one hit for the target phrase. It passes the
    floor, so this is polish, not a fix. Leave it until the pages above are done.

---

## Phase 6 — technical polish (half a day, smallest lever — do it last)

15. **130 `.webp` files exist and nothing references them** (`assets/*.png.webp`, made by
    `gen_webp.py`). Pages ship png/jpg only, zero `image/webp` sources. Wiring `<picture>`
    must keep `haus_admin_server.py:783-790`'s `src`/`srcset` rewrite working, so do this
    with the admin's slot convention, not against it.
16. **`hair-extensions-barrie.html` lazy-loads none of its 5 images.** Add `loading="lazy"`
    below the fold, keep the hero eager.
17. **Zero `rel=preload` anywhere.** Preload the hero image and the display font on the
    money pages. `haus.css` 47KB + `haus.js` 34KB are fine as-is.
18. Largest asset is a 67KB logo png — image weight is not a problem on this site. Do not
    spend a day here.

---

## Phase 7 — verification gate, then Search Console

Run before declaring on-site done:

- `floor.py` — every targeted page PASS
- `links.py` — money pages ≥4 inbound, guide ≥4 outbound, no orphans
- 12-URL live probe — all 200, `/client-waitlist` still 301s, www→apex still 301s
- Sitemap parity + fresh `lastmod`; IndexNow 202
- Admin console smoke test: edit one text slot per touched page, switch CA↔US, confirm
  nothing added here disappears
- Diff against the Phase 0 tarball and read every changed line

Only then GSC — and its first jobs are the ones this plan cannot do: request indexing for
the changed URLs, confirm the old Weebly-era titles are gone from the index, and read real
positions for the six keywords (which also unblocks the SERP step that run-03 could not
measure). The free Moz key belongs in the same session: it turns every UNAVAILABLE cell in
the run-03 link grid into a number.

---

## Explicitly not doing

- **Link building / outreach.** Velocity says nobody is accumulating links; the gap is not
  the constraint. Revisit if Moz data contradicts Tier 0.
- **`trade.html`.** Feature-flagged off by design.
- **Keyword expansion.** Six targets across eight pages is already at the edge of
  cannibalization — Phase 3 is about reducing overlap, not adding more.
- **Rewriting the home page.** It passes the floor.

## Sequencing summary

| Phase | Effort | Risk | Blocks GSC? |
|---|---|---|---|
| 0 — snapshot + commit | 30 min | none | yes — do first |
| 1 — sitemap/IndexNow | 1 h | none | yes |
| 2 — internal links | ½ day | low (admin collisions) | yes |
| 3 — floor failures | ½ day | medium (`content.json` pairing) | yes |
| 4 — US URLs | ½–2 days | high for option B | no — decision first |
| 5 — content depth | 1 day | low | no |
| 6 — technical polish | ½ day | low | no |
| 7 — verification | 1 h | none | yes — the gate |

Phases 0–3 and 7 are the "before GSC" block: about two days of work, and they are what
turns the current site from *floor-failing in three places with a starved link graph* into
something worth asking Google to recrawl.

---

## Status — 2026-08-13

| Phase | State | Evidence |
|---|---|---|
| 0 — snapshot + commit | **done** | `~/beautyhaus-preonsite-20260813-1703.tar.gz` (120M, extract-tested), branch `seo-onsite-2026-08-13`, commit `0891c49` |
| 1 — sitemap / IndexNow | **done** | 8 URLs with true mtimes; IndexNow 200 |
| 2 — internal links | **done** | commit `8fce0b1`. Inbound: Barrie 1→5, Sarasota 2→6, guide 3→4; guide outbound 0→4 |
| 3 — floor failures | **done** | commit `62459fd`. All 7 targeted pages PASS |
| 4 — US URLs | **done** | commit `d289714`. `/sarasota/` prerendered, hreflang paired, admin regenerates on save |
| 5 — content depth | **done** | commit `9c8c236`. Barrie 547 -> ~873 words + FAQPage schema; four photographs in the guide |
| 6 — technical polish | **done (narrowed)** | commit `9c8c236`. Footer logos lazy, 7 images given dimensions; WebP left alone, see below |
| 7 — verification gate | **done** (for 0–6) | admin gate PASS, locale render gate PASS, 11 live probes 200/301 |

### Gates built by this pass

- `tools/admin_gate.py` — copies the site to a temp dir, imports the admin server
  against that copy, and round-trips `set_text` in both locales. Proves the client can
  still edit every one of the 500 copy slots. Baseline at
  `seo/vasco/run-03-full-site/admin-gate-baseline.json`; pass it as an argument to fail
  on any slot id lost since.
- `~/vasco-run/locale_check.mjs` — loads the live site as `?haus=ca` and `?haus=us`,
  asserts each locale shows its own geo link and hides the other, and fails on any page
  JS error.
- `~/vasco-run/floor.py`, `~/vasco-run/links.py` — the floor grid and internal link graph.

### Correction to run-03

`trade.html`'s absence from the sitemap was listed as a defect in run-03. It is not:
`settings.json` carries `training: false` and `hiring: false`, `gen_sitemap.py` drops the
page while both are false, and `js/haus.js:523` redirects it away. The page is dormant by
design. Run-03 and this plan are both corrected.


## Phase 4 as built — the US locale at /sarasota/

Chosen shape: **`/sarasota/` prefix**, for the geo keyword in every US path.

| CA | US |
|---|---|
| `/` | `/sarasota/` |
| `/services.html` | `/sarasota/services.html` |
| `/why-nano.html` | `/sarasota/why-nano.html` |
| `/care.html` | `/sarasota/care.html` |

`tools/gen_us_pages.py` builds the US set from the CA pages plus the overrides the
admin console already owns. Per page it applies the US text and image overrides,
removes the CA-only blocks and anything `layout.json` hides for the US locale, fills
`[data-loc-field]` from `LOC.us` in `js/haus.js` (so the served HTML carries the
Sarasota address, not the Barrie one), rewrites relative URLs to root-absolute and
internal links to their US counterparts, and sets a Sarasota-targeted title and
description. `data-haus-pin="us"` on the body was already supported by the bootstrap,
so no JS change was needed.

Both sides carry `hreflang` en-CA / en-US / x-default plus self-canonicals. The CA
pages get theirs by string insert — a BeautifulSoup round-trip rewrote every attribute
in the file (1,500 lines of churn) and broke the sitemap's canonical lint, so that
approach was reverted.

**Staying correct over time:** `haus_admin_server.py` schedules a debounced,
off-thread rebuild after any content write, so a client edit in /admin reaches the US
pages on its own. If that hook is ever removed, `/sarasota/` silently goes stale —
`tools/check_us_pages.py` is the canary.

### Gates for this phase

- `tools/check_us_pages.py` — fetches the live pages as a crawler does (no JS) and
  asserts self-canonical, reciprocal hreflang both ways, no CA-only blocks, no Barrie
  address in visible copy, no links leaking back to the CA set.
- `~/vasco-run/us_render.mjs` — browser pass over the four US pages: locale resolves to
  `us`, no gate interstitial, no JS errors.

### Not done (do not block Search Console)

Phase 5 (content depth: the 547-word Barrie page, images in the guide) and Phase 6
(the 130 unused `.webp` files, lazy-loading, preloads).


## Phases 5 and 6 as built

**Phase 5.** The Barrie page carries a five-question FAQ and matching `FAQPage` schema,
taking it from 547 to ~873 words. Numbers are bound with `data-price` so
`tools/haus_prices.py` keeps them in step with `prices.json`; answers carry `data-edit`
ids in the page's `barrie-*` namespace so the client owns the copy.

The guide has four photographs, one per section they illustrate. They live in
`assets/guide/`, **not** referenced from `assets/photos/slot-*.jpg` — those are
admin-managed and a client swapping the FAQ photo would silently change the guide.

**Phase 6 was narrowed on evidence, and this is the useful part of the record:**

- **WebP stays unwired.** `deploy/nginx.conf` already documents why: Cloudflare's free
  plan ignores `Vary: Accept`, so Accept-negotiation would cache one variant for
  everyone and hand WebP to browsers that cannot render it. Serving the 130 twins needs
  CF Polish (paid) or `<picture>` sources wired through the admin upload path, where
  `haus_admin_server.py` rewrites `src`/`srcset` per slot. The run-03 fix list was wrong
  to call this a quick win.
- **"Barrie lazy-loads none of its 5 images" was a misread.** Those five are brand logos
  and a decorative crown; four are above the fold. Only the footer mark was a real
  candidate, and it is now lazy on all seven pages.
- **Real and done:** seven images that declared no dimensions now reserve their box, and
  the four new guide photographs are recompressed (51–254KB), sized, lazy, and stamped
  with `?v=` because Cloudflare had already cached the unoptimised copies for seven days.

### Cache lesson worth keeping

Publishing an image and *then* optimising it leaves Cloudflare serving the heavy copy
for the full seven-day TTL. Optimise before first publish, or change the URL.

## Where this leaves Search Console

Everything on-site in this plan is done. The remaining work needs a Google login and is
listed in `vasco/offsite/operator-checklist.md`: request indexing for the changed URLs
and the four new `/sarasota/` ones, confirm the Weebly-era titles are gone from the
index, and read real positions for the six keywords — which also unblocks the SERP step
run-03 could not measure from this box. The free Moz key belongs in the same session.
