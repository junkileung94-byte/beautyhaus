# Information Architecture — violahairextensions.co.uk

> Source: live crawl + sitemap + Shopify JSON endpoints, 2026-07-05.
> Machine-readable versions: `data/nav-tree.json`, `data/collections.json`, `data/catalog-stats.json`.

Platform: **Shopify**, theme: **Prestige (by Maestrooo)** — identified from `Header__MainNav` / `SidebarMenu` / `DropdownMenu` markup.

## Header

- **Announcement bar** (pale pink): shipping cutoff message ("Orders placed after 2pm will be shipped the next working day…")
- **Top utility row** (black): Blog & News · Careers · Contact · flag/locale · Account · Search · Cart
- **Main nav** (black bar, uppercase letterspaced) — 9 top-level items, 3-level dropdowns:

### Nav tree (complete)

- **Luxe Hair Extensions** → `/collections/luxe-hair`
  - Luxe Nano Tip · Luxe Tape In · Luxe Genius Weave
- **Professional Hair Extensions** → `/collections/professional-hair-extensions`
  - **Shop by Type** → Nano Tip · Tape In · Secret Tape In · Tape Weft · Hair Weave (weft) · Flat Weft · Genius Weave · I-tip · Pre-Bonded · Colour Ring
  - **Shop by Colour** → Black · Brunette · Blonde · Red · Highlighted · Root Stretch · Balayage · Vibrant
  - **Shop by Length** → 12″ · 14″ · 16″ · 18″ · 20″ · 22″ · 24″ · 26″
- **Equipment** → `/collections/equipment`
  - **Shop by Method** → Nano Ring · Tape In · Hair Weave · Micro Ring · Pre-Bonded accessories
  - **Beads & Fittings** → Nano Rings · Copper Tubes & Rings · Tape Tabs · Glue · Keratin Bond Removers · Thread
  - Pliers · Application Tools
  - **Brushes & Combs** → Extension Brushes · Hairdressing Combs
  - Electrical
  - **Hairdressing Accessories** → Clips & Grips · Scissors & Razors · Gowns · Trolleys & Cases · Sundries
  - Training Essentials · Marketing Materials
- **Hair Care** → `/collections/hair-care`
  - **Shop by Brand** → Viola products · Malibu C
  - **Shop by Type** → Shampoos · Conditioners · Masks & Treatments · Styling
  - **Shop by Hair Solution** → Discoloured · Dry/Damaged · Dull
- **Clip-Ins** → `/collections/hair-pieces`
- **Wigs** → `/collections/wigs`
- **Courses** → `/pages/viola-academy`
  - Online Courses (collection) · In-Salon Courses (page) · Gift Cards
- **Sale** → `/collections/sale`
- **Trade Accounts** → `/pages/trade-accounts`

## Collection taxonomy

80 collections in 4 orthogonal facets, driven by **product tags** (shade codes like `#60B`, type tags like `NANO TIP`, `LUXE`):

| Facet | Collections | Example sizes |
|---|---|---|
| By product line | luxe-hair (143), professional (436), clip-ins, wigs | Luxe = premium tier of each type |
| By attachment type | nano-tip, tape-in, secret-tape, tape-weft, weft, flat-weft, genius-weave, i-tip, pre-bonded, colour-ring | genius weave = flagship |
| By colour family | black, brunette, blonde (101), red, highlighted (89), root-stretch, balayage, vibrant | tag-driven via shade codes |
| By length | 12″–26″ (8 collections) | 18″ = 445 products (biggest) |
| Supporting | equipment (8 sub-facets), hair-care (3 sub-facets), courses, sale, training, marketing-material | |

## Static pages (23)

| Purpose | Pages |
|---|---|
| Trust/info | `190-day-guarantee`, `faqs`, `aftercare`, `returns-delivery`, `colour-chart`, `files-to-download` |
| Company | `about-us`, `contact`, `careers`, `opening-hours-2025-2026`, `christmas-orders`, `easter-opening-times` |
| Education/revenue | `viola-academy`, `hair-extension-training`, `in-salon`, `trade-accounts` |
| Legal | `terms-1`, `privacy`, `copyright` |
| Blog hub | `blog-news` |

## Homepage section order (Prestige sections)

1. Announcement bar → header (black)
2. Hero slideshow (seasonal campaign, e.g. swimming guide)
3. Welcome copy: "100% Human Hair Extension / At Viola, we offer luxurious Remy Russian Slavic hair…"
4. 3 featured category boxes: Professional / Hair Care / Equipment (photo cards + "VIEW PRODUCTS" ghost buttons)
5. "Featured Categories" — 8 outline pill links (Nano Tip, Tape In, Weave, Hair Pieces, Beads, Pliers, Application Tools, Virgin Slavic)
6. "Our Best Sellers" product grid (Colour Ring £68.33, nano rings, pliers)
7. Full-bleed testimonial band (model photo + customer quote)
8. News & Blog — 3 article cards
9. Newsletter band over full-bleed hair photo
10. Instagram strip
11. Long-form SEO copy block (h3-structured, ~8 paragraphs: "The genesis of grandeur", "The emporium of elegance"…)
12. Store locator: Google Map embed + address + hours + "GET DIRECTIONS"
13. Footer: Browse / Location (full company + VAT details) / Contact / Help / Popular Products + payment icons

## Product page anatomy (Prestige PDP)

- Breadcrumbs (Home › Product)
- Gallery (carousel, dot nav) | Right rail: uppercase letterspaced title, **price + "EXCL. VAT"** (trade-oriented), variant select (`Length | Weight` e.g. `18" | 55g`), quantity stepper, black full-width ADD TO CART
- Tab/accordion row: **DESCRIPTION ⌃ DETAILS ⌄ FOR USE ⌄** — avg 4,785 chars of rich description HTML per product
- "YOU MAY ALSO LIKE" 4-up recommendation grid
- Footer

## Current Canadian site (violahairextensions.co) — for gap analysis

- Standard Dawn-style theme, "Hi Queens…" welcome, product grid, phone 416-712-3429
- Carries a subset of catalog (nano tip, genius weave, tools, hair care)
- No luxe/professional split, no shop-by-colour/length facets, no education/trade layer, no guarantee page
