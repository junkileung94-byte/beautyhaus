# Beauty Extension Haus — Shopify homepage (responsive)

Built from the Claude Design exports **"Homepage Mobile.dc.html"** and
**"Homepage.dc.html"** (project: *Website redesign brief*).

One responsive theme, mobile-first: the phone layout is the base and the
desktop layout kicks in at `min-width: 860px` (two-column hero, text nav,
3-up service grid, two-column shop band). Same DOM, no duplicate templates.

## What's here

```
theme/          Real Shopify theme (Liquid + JSON templates + schema)
  layout/theme.liquid          Frame, ambient orbs, font loading, section groups
  sections/header.liquid       Glass nav (logo, hamburger, BOOK)
  sections/hero.liquid         Eyebrow + headline + arched photo + badge + CTAs + divider
  sections/service-menu.liquid Service cards (repeatable blocks; dark "signature" variant)
  sections/shop-band.liquid    Plum "shop nanobead" band (repeatable product blocks)
  sections/footer.liquid       Footer logo, nav links, address
  sections/header-group.json   Static header placement + settings
  sections/footer-group.json   Static footer placement + nav blocks
  templates/index.json         Homepage: hero -> service-menu -> shop-band
  config/                      settings_schema.json + settings_data.json
  locales/en.default.json
  assets/base.css              All styles (mobile-first + desktop @media 860px)
  assets/logo.png

preview/        Static render of the homepage (identical markup + base.css)
  index.html    Served locally so you can view it without a Shopify store
                Responsive — resize the window to see desktop <-> mobile
```

Every piece of copy, every price, the logo, the CTA links and the product/
service cards are **editable in the Shopify theme editor** — they're wired as
section settings and repeatable blocks, not hard-coded.

## View the demo now (no Shopify account needed)

A local server is serving `preview/` on **port 80**:

- On this machine:      http://localhost/
- On your LAN:          http://192.168.1.197/
- Through your forward: your public IP / domain on port 80

To (re)start it:

```bash
python -m http.server 80 --bind 0.0.0.0 --directory preview
```

## Run it as a real Shopify theme

You'll need a (free) Shopify Partner **development store** + the Shopify CLI.

```bash
# 1. install the CLI (once)
npm install -g @shopify/cli @shopify/theme

# 2. from the theme folder, log in and start the live dev server
cd theme
shopify theme dev --store your-store.myshopify.com
```

`shopify theme dev` hot-reloads and gives you a preview URL. To publish:

```bash
shopify theme push --store your-store.myshopify.com
```

### Notes for the store version
- The hero photo and the two product cards fall back to labelled
  placeholders until you upload images in the theme editor.
- Service cards, footer links, and products are all **blocks** — add / remove /
  reorder them in the editor without touching code.
- Booking/CTA links currently point at in-page anchors (`#book`, `#services`,
  `#shop`); repoint them to your booking system or collection URLs in the editor.
