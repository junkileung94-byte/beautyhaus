# Viola Hair Extensions UK — Full Site Audit

**Purpose:** document the look, feel, information architecture, and product-content model of
**violahairextensions.co.uk** so the Canadian site (**violahairextensions.co** /
`violahairextensions.myshopify.com`) can be rebuilt to match it as the Canadian branch.

**Method:** full Playwright crawl on 2026-07-05 — **879 URLs × 2 viewports = 1,758 full-page
captures, 0 errors** (desktop 1440×900, mobile 390×844): homepage, all 23 static pages, all 80
collections, all 768 products, blog, plus the current Canadian site for comparison. Structured
data pulled from Shopify JSON endpoints. Raw material:

| Artifact | Where |
|---|---|
| Full screenshot set (1.7 GB, gitignored) | `screenshots/{desktop,mobile}/{home,pages,collections,products,blogs,ca}/` |
| Curated sample (committed) | `screenshots-sample/` |
| All 768 products (variants, prices, tags, full HTML descriptions) | `data/products.json` |
| All 80 collections + product membership | `data/collections.json` |
| Catalog analysis | `data/catalog-stats.json` |
| 3-level nav tree | `data/nav-tree.json` |
| Per-page titles/meta/anatomy | `data/page-meta.json` |
| Full copy of every static page + key blog posts | `data/pages/*.md` |
| Computed design tokens | `data/design-tokens.json` |
| Crawl log | `data/crawl-log.json` |
| IA deep-dive | `ia-map.md` |

---

## 1. Platform & theme

- Shopify, theme **Prestige by Maestrooo** (identified from `Header__MainNav`, `SidebarMenu`,
  `DropdownMenu`, `AnnouncementBar` markup). Prestige is a premium theme (~US$300, Shopify
  Theme Store) — **the fastest path to matching the UK feel is licensing Prestige for the
  Canadian store** and configuring it identically, rather than rebuilding from scratch.
- Sticky black header; transparent-header variant on the homepage hero.
- Klaviyo-style newsletter, Google Maps embed, standard Shopify payments.

## 2. Design language ("the feel")

**Positioning:** quiet luxury, professional/trade-first. White space, thin letterspaced
uppercase type, near-black on white, one blush accent. No gradients, no rounded corners,
no loud color. Photography does the emotional work (hair textures, models); the UI stays
monochrome and recedes.

### Palette (from computed styles + pixel sampling)

| Token | Value | Use |
|---|---|---|
| Ink | `#1C1B1B` | Header bg, body text, solid buttons (Add to Cart) |
| White | `#FFFFFF` | Page + footer background |
| Blush | `#F8E3EA` | Announcement bar (the only color accent in the chrome) |
| Muted | `#6A6A6A` | Footer text, secondary labels |
| Page tint | `#F0F0F0` | Homepage body background behind sections |

### Typography

| Role | Spec |
|---|---|
| Headings / UI | **Montserrat 500** — always UPPERCASE, letterspaced (h1 20px / 4px tracking; PDP title 18px / 3.6px) |
| Body | **Nunito Sans 400/700** — 14px / 23.1px line-height |
| Logo | Serif VIOLA wordmark + "LONG MAY IT LAST" tagline, white on black |

Headings are *small but tracked wide* — hierarchy comes from spacing and case, not size.

### Components

- **Buttons:** rectangular (0 radius), Montserrat 12px 500, uppercase, 2.4px tracking,
  14px×28px padding. Two variants: ghost (1px ink border, transparent) and solid ink
  (white text) — solid is reserved for Add to Cart / primary CTAs.
- **Announcement bar:** blush pink, ink text, operational messaging ("Orders placed after
  2pm ship next working day").
- **Header:** black; utility row (Blog & News · Careers · Contact · flag · account · search ·
  cart) above main nav row; 9 uppercase nav items with 3-level dropdowns.
- **Product cards:** plain — image, uppercase tracked title, "FROM £x EXCL. VAT". No borders,
  no shadows, no badges.
- **Footer:** white, 5 columns (Browse / Location / Contact / Help / Popular Products),
  full company registration + VAT details, payment icons.

## 3. Information architecture

(Full tree in `ia-map.md` / `data/nav-tree.json`.) 9 top-level nav items:
**Luxe · Professional · Equipment · Hair Care · Clip-Ins · Wigs · Courses · Sale · Trade Accounts**

The catalog is faceted 4 ways via **product tags** (shade codes `#60B`, type tags `NANO TIP`,
`LUXE`…), producing 80 collections:

- **By tier:** Luxe (143 products, trade-exclusive premium line) vs Professional (436)
- **By attachment type:** nano tip · tape-in · secret tape · tape weft · weft · flat weft ·
  genius weave · i-tip · pre-bonded · colour ring
- **By colour family (8):** black → vibrant, driven by shade-code tags
- **By length (8):** 12″–26″ (18″ is the largest: 445 products)

Plus supporting trees for Equipment (by method / beads & fittings / tools / accessories),
Hair Care (by brand / type / hair solution), education and trade.

**Key insight:** products are duplicated per shade (e.g. 13 products tagged `#1B`) with colour
in the *title* (`Luxe Genius Weave #8 Wild Truffle`) and Length|Weight as the variant
(`18" | 55g`, `20" | 60g`, `22" | 65g`). Collections assemble automatically from tags.
Replicating the tag scheme is what makes the whole IA work.

## 4. Product content model (why the site feels "informative")

Every product page (Prestige PDP): breadcrumbs → gallery | title, price **EXCL. VAT**,
variant dropdown, quantity, solid-black ADD TO CART → **Description / Details / For Use**
accordion → You May Also Like.

- Average description length: **4,785 characters of structured HTML** (h5/h6 subheads,
  bold key phrases, bullet specs).
- Editorial formula per hair product: *"What Makes This Colour Special"* (emotive colour
  story) → *"Why Choose…"* (method benefits) → *"Wear, Styling & Performance"* →
  spec bullets (WEIGHTS / MATERIAL / STYLE / WARRANTY) → link to Aftercare products.
- 486 of 768 products have multiple images; prices £0.36–£720.
- Luxe products carry trade-gating copy: "Exclusively available to trade account holders."

## 5. Trust & education layer

This is as important to the feel as the visuals:

- **190-Day Guarantee** page (longest in the UK; conditions tied to certified fitting +
  Viola aftercare products — also drives aftercare product sales)
- **Colour chart** (79 shades) + physical colour ring product
- **Aftercare** page + guide, **FAQs**, **Returns & Delivery**, **Files to Download**
- **Viola Academy**: in-house / in-salon / online courses (Nano, Tape-in, Beaded Weave)
- **Trade Accounts**: certificate-verified accounts unlock trade pricing + Luxe range
- Blog ("News & Blog") with seasonal care guides feeding homepage hero campaigns
- Long-form SEO copy blocks at the bottom of homepage and collection pages

## 6. Current Canadian site vs UK (gap analysis)

Captured in `screenshots/{desktop,mobile}/ca/` (2026-07-05):

| Dimension | UK (target) | CA today |
|---|---|---|
| Theme | Prestige, black/white/blush luxury | Default Dawn look, magenta gradient hero |
| Hero | Seasonal campaign imagery | Text apology: "bare with us as we are re-designing…" |
| Nav | 9 items, 3-level mega menu | 6 flat links (Professional, Luxe Nano, Equipment, Hair Care, Trade Accounts) |
| Catalog | 768 products, 80 collections, 4 facets | Genius Weave shades + subset (~dozens), no colour/length facets |
| Product info | ~4.8k-char editorial descriptions, 3 accordions | Basic descriptions |
| Trust layer | Guarantee, colour chart, aftercare, FAQs, downloads | None visible |
| Education/trade | Academy, courses, verified trade accounts | Trade Accounts link only |
| Footer | 5 columns, company details | Bare (policies + newsletter only) |
| Pricing | GBP excl. VAT (trade-oriented) | CAD incl. tax presentation |
| Contact | Romsey HQ, 01794 840130 | 416-712-3429, canadasupport@violahairextensions.co |

The repo's `theme/` (Beauty Extension Haus one-pager: hero → service menu → shop band) is a
salon-booking homepage — a different genre from the UK catalog site. Useful as a landing/booking
section, but not a basis for matching the UK experience.

## 7. Recommended path for the Canadian branch (informational — build is a follow-up task)

1. **License Prestige** for the Canadian store and copy the UK's settings: black header,
   blush announcement bar, Montserrat/Nunito Sans, transparent home header.
2. **Rebuild the nav** from `data/nav-tree.json`, dropping UK-only branches until stocked
   (e.g. Wigs, Marketing Material) — the JSON maps 1:1 to Shopify menus.
3. **Import the catalog** from `data/products.json` (titles, tags, options, descriptions,
   images) for the lines Canada carries; keep the exact tag scheme so the 80 collections
   auto-populate. Reprice in CAD.
4. **Port the trust layer first** (guarantee, aftercare, colour chart, FAQs, returns) —
   copy is already extracted in `data/pages/*.md`; adapt UK-specific terms (VAT, phone,
   address, "longest in the UK") to Canada.
5. **Localize:** CAD pricing, Canadian contact (416-712-3429 / canadasupport@…), Canadian
   shipping/returns policy, announcement-bar message.
6. **Phase 2:** Academy/courses and verified trade accounts if the Canadian operation
   supports them; otherwise link to the UK academy.

---
*All claims traceable to the crawl artifacts listed at the top. Regenerate any time with
`node audit/crawl.mjs` (resume-safe) + `fetch-data.mjs`/`analyze-catalog.mjs` (scratchpad).*
