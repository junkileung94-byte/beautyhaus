# Beauty Extension Haus — redesigned site

Static, no build step. Lives at `preview/haus/` so Vercel (root: `preview/`) serves it at `/haus/` once pushed to the `junki` remote.

## Flow
1. **Country gate** — every visit (per browser session): US 🇺🇸 Sarasota / CAN 🇨🇦 Barrie, divider between. No choice persists across visits (`sessionStorage` only).
2. **Splash** — new crown logo on champagne gradient, then fades into the site.
3. **Site** — chosen country drives address / phone / booking CTA / location-scoped sections via `body[data-haus]` + `[data-loc]` (see `js/haus.js` `LOC` dict).

## Pages
- `index.html` — parallax home (hero, studio story, menu teaser, awards, gallery, Google-review testimonials, visit)
- `services.html` — full priced menu (nano / Genius Wefts / K-Tips / colour), policies, team
- `care.html` — FAQ accordions + aftercare golden rules
- `trade.html` — Training & Careers (feature-flagged via settings.json: training / hiring toggles in /admin)

## Design
Hallmark custom theme (stamp in `css/tokens.css`): Playfair Display + Jost. Palette anchored on brand **#EBD2FD** (lilac, hue 311) — lilac porcelain neutrals, champagne-gold accents, charcoal-violet darks (deliberately not Deep/Midnight Plum). All pairs WCAG-checked (body ≥6.8:1, accents ≥4.6:1). Glass surfaces over parallax photo folds (CSS scroll-driven `animation-timeline: view()`, static fallback, reduced-motion safe). Mobile-first; zero horizontal scroll verified at 320/390/1280.

## Media
All imagery/video are labelled placeholders — see `MEDIA-MANIFEST.md` for the slot map to fill from the Google Drive drop.

## Preview locally
```
cd preview/haus && python3 -m http.server 8877
# http://localhost:8877
```

## Business facts sourced from beautyextensionhaus.com (July 2026)
Prices CAD before tax; Barrie: 480 Mapleton Ave, Mon–Fri 10–4, Sat 10–3; booking via Square Appointments; $250 install deposit; 3-week grace period; Sarasota opened August 2026 — 1724 4th Street, nano-bead only, booking via Mangomint (`booking.mangomint.com/733325`); `js/haus.js` `LOC.us` already carries both.
