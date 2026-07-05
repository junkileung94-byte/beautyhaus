# Viola Canada — custom Shopify theme

Custom-built Liquid theme for **violahairextensions.myshopify.com** (violahairextensions.co),
implementing the design language documented in the UK-site audit (`../audit/REPORT.md`):
ink `#1C1B1B` on white, blush `#F8E3EA` accent, Montserrat 500 uppercase tracked headings,
Nunito Sans body, square ghost/solid buttons, 3-level mega-menu, PDP accordions
(Description / Details / For Use), collection pages with long-form copy below the grid.

## ⚠️ Sandbox-first workflow — the live store is never touched

All commands run from this directory (`viola-theme/`). The store is preconfigured in
`shopify.theme.toml` as the `dev` environment, **flagged unpublished**.

```bash
# 1. LOCAL PREVIEW (safest, start here)
#    Temporary preview URL with the store's real products. Hot reload.
#    Nothing is saved to the store. First run opens a browser login.
shopify theme dev -e dev

# 2. DRAFT THEME ON SHOPIFY (shareable preview)
#    Uploads/updates ONLY the unpublished draft "Viola Canada — DEV (do not publish)".
#    Preview & share it from admin: Online Store → Themes → ... → Preview.
shopify theme push -e dev
```

**Going live** is deliberately excluded from this workflow. It only happens when *you*
click **Publish** on the draft theme in Shopify admin (or run `shopify theme publish`,
which we never do from here).

## Structure

```
layout/theme.liquid          Frame: fonts, color tokens, header/footer groups
layout/password.liquid       Storefront password page frame
sections/
  announcement-bar.liquid    Blush bar (shipping message)
  header.liquid              Black header: utility row, wordmark, 3-level mega menu, mobile drawer
  footer.liquid              Multi-column footer (link lists / text / newsletter blocks)
  hero.liquid                Full-bleed campaign hero
  rich-welcome.liquid        Centered welcome copy
  category-boxes.liquid      3 photo category cards ("View products")
  category-pills.liquid      Outline pill links ("Featured categories")
  featured-collection.liquid Best-sellers grid
  testimonial.liquid         Full-bleed quote band
  newsletter.liquid          Email capture band
  main-product.liquid        PDP: gallery+thumbs, variant picker, qty, ATC, accordions, LUXE trade note
  related-products.liquid    "You may also like" (Shopify recommendations API)
  main-collection.liquid     Grid + sort + pagination + SEO copy below
  main-{page,cart,search,blog,article,404,list-collections}.liquid
templates/                   JSON templates + gift_card/password/customers liquid
snippets/product-card.liquid Audit-style card: tinted media, tracked title, "From $x"
assets/viola.css             The whole design system (tokens in layout/theme.liquid)
assets/viola.js              Drawer, qty steppers, variant picker, gallery
config/settings_schema.json  Editable brand colors
```

## Wiring checklist (in the theme editor / admin, all safe on the draft)

- **Menus** (Content → Menus): build `main-menu` from `../audit/data/nav-tree.json`
  (3 levels supported). Create a `footer` menu for the Help column.
- **Metafields**: PDP accordions read `product.metafields.custom.details` and
  `custom.for_use` (rich-text) — define them under Settings → Custom data → Products.
- **Trade note**: shows automatically on products tagged `LUXE`.
- **Homepage**: assign collections/images to the hero, category boxes, pills and
  best-sellers sections in the editor — all content is section settings, no code edits.
- **Catalog import**: source titles/tags/options/descriptions from `../audit/data/products.json`
  (keep the UK tag scheme so the colour/length/type collections auto-assemble).

## Status

`shopify theme check`: 47 files, 0 errors (5 info-level warnings for Google Fonts CDN links).
