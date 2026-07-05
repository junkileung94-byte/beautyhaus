# Store setup pack — Viola Canada

Everything here is applied in **Shopify admin** (safe: none of it touches the live theme).

## 1. Pages (admin → Online Store → Pages → Add page)

For each file in `pages/`, create a page, switch the content editor to the `<>` code view,
and paste the HTML (skip the leading comment). Suggested titles/handles:

| File | Title | Handle | Template |
|---|---|---|---|
| `190-day-guarantee.html` | 190 Day Guarantee | `190-day-guarantee` | Default page |
| `aftercare.html` | Aftercare | `aftercare` | Default page |
| `about-us.html` | About Us | `about-us` | Default page |
| `returns-delivery.html` | Returns & Delivery | `returns-delivery` | Default page — **⚠️ fill in Canadian courier rates before publishing** |
| `trade-accounts.html` | Trade Accounts | `trade-accounts` | Default page |
| `faqs.html` | FAQs | `faqs` | Default page — **⚠️ fill the [bracketed] answers** |
| — | Contact | `contact` | **page.contact** (form + Canadian phone/email built in) |

## 2. Menus

Follow `MENUS.md` (admin → Content → Menus). The header mega-menu, mobile drawer and
footer columns all populate from these menus automatically.

## 3. Theme editor (on the dev/draft theme only)

- Hero: assign a campaign image + link
- Category boxes: pick 3 collections + images
- Category pills: pick collections
- Best sellers: pick a collection
- Testimonial: assign a background photo

## 4. Product metafields (for PDP accordions)

Settings → Custom data → Products → Add definition:
- `custom.details` (Rich text) → renders as the DETAILS accordion
- `custom.for_use` (Rich text) → renders as the FOR USE accordion

The DESCRIPTION accordion uses the normal product description. The UK's editorial
formula per product is documented in `../../audit/REPORT.md` §4, with all 768 UK
product descriptions in `../../audit/data/products.json`.
