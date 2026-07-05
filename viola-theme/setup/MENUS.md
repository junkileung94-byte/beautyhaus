# Menu build guide — Viola Canada

Build these in **Shopify admin → Content → Menus**. Shopify menus support 3 levels of
nesting, which is exactly what the header mega-menu and mobile drawer render.

Source of truth: `../../audit/data/nav-tree.json` (the UK site's full tree).
Below is the **recommended Canadian phase-1 tree** — UK branches you don't stock yet
(Wigs, Marketing Material, in-salon courses) are dropped; add them later by just adding
menu items, no code changes needed.

Menu links point at collections — create collections with matching handles first, or
point items at existing ones. Collections auto-fill if products carry the UK tag scheme
(`NANO TIP`, `LUXE`, shade codes like `#60B` — see `../../audit/data/products.json`).

## `main-menu` (header mega-menu)

```
Luxe Hair Extensions            → /collections/luxe-hair
├─ Luxe Nano Tip                → /collections/luxe-nano-tip-hair
├─ Luxe Tape In                 → /collections/luxe-tape-in-hair-extensions
└─ Luxe Genius Weave            → /collections/luxe-genius-hair-weave-extensions

Professional Hair Extensions    → /collections/professional-hair-extensions
├─ Shop by Type                 → /collections/professional-hair-extensions
│  ├─ Nano Tip                  → /collections/nano-tip-hair-extensions
│  ├─ Tape In                   → /collections/tape-in-hair-extensions
│  ├─ Genius Weave              → /collections/genius-hair-weave-extensions
│  ├─ Hair Weave (Weft)         → /collections/weft
│  ├─ I-Tip                     → /collections/i-tip-hair-extensions
│  └─ Colour Ring               → /collections/colour-ring
├─ Shop by Colour               → /collections/shop-by-colour
│  ├─ Black                     → /collections/black-hair-extensions
│  ├─ Brunette                  → /collections/brunette-hair-extensions
│  ├─ Blonde                    → /collections/blonde-hair-extensions
│  ├─ Red                       → /collections/red-hair-extensions
│  ├─ Highlighted               → /collections/highlighted-hair-extensions
│  ├─ Root Stretch              → /collections/root-stretch-hair-extensions
│  ├─ Balayage                  → /collections/balayage-hair-extensions
│  └─ Vibrant                   → /collections/vibrant-hair-extensions
└─ Shop by Length               → /collections/shop-by-length
   ├─ 16 Inch … 26 Inch         → /collections/16-inch-hair-extensions … etc.

Equipment                       → /collections/equipment
├─ Beads & Fittings             → /collections/beads-fittings
│  ├─ Nano Rings                → /collections/hair-extensions-nano-rings
│  ├─ Copper Tubes & Rings      → /collections/hair-extensions-copper-tubes
│  └─ Tape Tabs                 → /collections/hair-extensions-tape-tabs
├─ Pliers                       → /collections/pliers
├─ Application Tools            → /collections/application-tools
└─ Brushes & Combs              → /collections/brushes-combs

Hair Care                       → /collections/hair-care
├─ Shampoos                     → /collections/shampoos
├─ Conditioners                 → /collections/conditioners
└─ Styling                      → /collections/styling

Sale                            → /collections/sale
Trade Accounts                  → /pages/trade-accounts
```

## `footer` menu (Help column)

```
FAQs                → /pages/faqs
190-Day Guarantee   → /pages/190-day-guarantee
Aftercare           → /pages/aftercare
Returns & Delivery  → /pages/returns-delivery
Colour Chart        → /pages/colour-chart
Terms               → /policies/terms-of-service
Privacy             → /policies/privacy-policy
```

## Utility menu (optional, header top-right)

```
Blog & News   → /blogs/news
Contact       → /pages/contact
```

Then in the theme editor (Header section) set: Main menu → `main-menu`,
Utility menu → the utility menu. Footer "Help" block → `footer` menu.
