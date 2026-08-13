# Media slots — Beauty Extension Haus redesign

Every image/video on the site is a styled placeholder carrying a `data-slot` id.
When the Google Drive assets arrive, map each file to its slot and swap the
placeholder `<div class="ph">…</div>` for `<img>` / `<video>` inside the same
container — the layout, arch crops and parallax are already wired.

| Slot id | Page | Spot | Wanted |
| --- | --- | --- | --- |
| `hero-main` | index | Full-bleed hero fold (parallax) | Signature result photo or 10–15 s loop video (portrait-safe crop) |
| `home-studio` | index | "The Haus" band (parallax) | Barrie studio interior |
| `home-award` | index | Awards band | Deanna / award wall photo |
| `home-nano-1` | index | Why-nanos arch figure | Close-up nano beads at root |
| `home-shop` | index | Shop teaser band (parallax, dark) | Product flat-lay |
| `services-hero` | services | Top band (parallax) | Colour-match / consult in progress |
| `services-care` | services | Care & styling band | Wash-house / blow-out |
| `gallery-1 … gallery-6` | index gallery strip | 6 tiles | Before/after transformations |
| `shop-p1 … shop-p6` | shop | Product cards | Nanobead hair bundles, tools, aftercare |
| `trade-hero` | trade | Top band (parallax) | Bundles / shade-ring flat-lay |
| `sarasota-tease` | index (US view) | Sarasota fold | Sarasota build-out / teaser video |

Notes
- Placeholders labelled `· video` expect `<video autoplay muted loop playsinline>`.
- Hero media must NOT be `loading="lazy"` (it's the LCP). Everything below the fold should be.
- Keep crops ≥ 1600 px wide for full-bleed folds, 3:4 for product cards.

## Filled 2026-07-21 (from Google Drive drop)
| Slot | File |
| --- | --- |
| hero-main | photos/hero-team.jpg (IMG_5867 — smiling team) |
| home-award | photos/award-wall.jpg (IMG_5898) |
| gallery-1/2/3 | salon-team (IMG_5877) · team-lineup (IMG_5884) · hair-wall (IMG_5894) |
| home-shop (index) | photos/shade-rack.jpg (IMG_4401) |
| services-hero | photos/servicing.jpg (IMG_5900) |
| weft-photo | photos/genius-weft-news.jpg (IMG_4392) |
| ktip-photo | photos/ktip-strand.jpg (IMG_4374) |
| colour-photo | photos/colour-deanna.jpg (IMG_5880) |
| shop-p1 / p5 / p6 | haus-brush (IMG_4398) · retail-shelf (IMG_5893) · ghd-styling (IMG_4403) |
| shop hair band | photos/hair-band.jpg (IMG_4415) |
| trade-hero | photos/trade-rack.jpg (IMG_4416) |

Still placeholder: shop-p2 (Soma filter), shop-p3 (Malibu kits), shop-p4 (Amika) — no matching product shots in the drop.
Videos available but unused: "5 years.mov", "fix it.mov", "dont get caught.mov" (say the word to wire one into the hero as a loop).
Full Drive set kept at scratchpad/drive (67 photos).
