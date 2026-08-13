#!/usr/bin/env python3
"""Beauty Extension Haus — one source of truth for every price on the site.

`preview/haus/assets/prices.json` holds base numbers only (hair per bundle,
install per bundle, the maintenance ladder, the deposit, ...). Everything the
visitor reads is *derived* from those numbers here and written back into the
pages, so a price change can never leave the arithmetic — or the "from $X"
headline, the schema markup, or the meta description — behind.

Two kinds of target in the HTML:

  <span data-price="ca.nano.own_hair" contenteditable="false">$85</span>
      inline value inside prose the admin Text tab still owns. contenteditable
      is false so a text edit can't type over the number.

  <p data-price="us.nano.20.table"> ... </p>
      a whole generated block (the bundle tables, the maintenance ladders).
      These carry no data-edit — the Pricing tab owns them outright.

apply_prices() rewrites those, the services.html meta descriptions, the
services.html OfferCatalog schema, and the deposit inside the US copy overrides
in content.json.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "preview", "haus")
PRICES_JSON = os.path.join(SITE, "assets", "prices.json")
CONTENT_JSON = os.path.join(SITE, "assets", "content.json")

# every page that carries a data-price marker
PRICE_PAGES = ["index.html", "services.html", "care.html", "trade.html",
               "why-nano.html", "hair-extensions-barrie.html",
               "nano-bead-hair-extensions-sarasota.html"]

PROVIDER = "https://beautyextensionhaus.com/hair-extensions-barrie.html#salon"

# a money amount as it appears in prose — strict about thousands separators so a
# trailing sentence comma ("from $145, plus ...") is never eaten as part of it
MONEY_RE = r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?"


# ---------------------------------------------------------------- formatting

def money(v):
    """230 -> '$230', 1140 -> '$1,140', 12.5 -> '$12.50'."""
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return "${:,.0f}".format(v)
    return "${:,.2f}".format(v)


def fmt(v, kind="plain"):
    if kind == "plus":
        return money(v) + "+"
    if kind == "from":
        return "from " + money(v)
    return money(v)


def _rng(a, b):
    return money(a) + "–" + money(b)


def _ladder(maint):
    """The maintenance ladder: whole bundles as priced, half bundles derived.

    A half bundle is its whole bundle plus that step's uplift — the uplift is
    per row (it isn't flat across the ladder), so half prices follow whenever a
    whole price moves. half_delta's length is how many half rows to show.

    Returns (whole_rows, half_rows) as lists of (label, value).
    """
    whole, deltas = maint["whole"], maint["half_delta"]
    w = [(str(i + 1), float(v)) for i, v in enumerate(whole)]
    h = [(str(i + 1) + ".5", float(whole[i]) + float(deltas[i]))
         for i in range(min(len(deltas), len(whole)))]
    return w, h


def _rows_html(rows, suffix=""):
    return "<br>".join("%s — %s%s" % (lbl, money(v), suffix) for lbl, v in rows)


def _slash(vals):
    return " / ".join(money(v) for v in vals)


def _bundle_tables(out, prefix, block):
    """US-shape pricing: hair per bundle + install per bundle, totalled per row.

    Writes "<prefix>.<length>.table" (the full-set ladder) and
    "<prefix>.<length>.from" (the menu headline) for every length in the block.
    Shared by the straight nano menu and the wavy menu, which price the same
    way and differ only in what the hair costs.
    """
    inst, g = float(block["install_per_bundle"]), int(block["grams_per_bundle"])
    bundles = max(1, min(12, int(block["bundles"])))  # the table is a menu, not a spreadsheet
    for L in block["lengths"]:
        key = re.sub(r"\D", "", L["label"])           # 20″ -> "20"
        hair = float(L["hair"])
        rows = ["%d g (%d) — %s + %s = %s"
                % (g * i, i, money(hair * i), money(inst * i),
                   money((hair + inst) * i))
                for i in range(1, bundles + 1)]
        out["%s.%s.table" % (prefix, key)] = "<br>".join(rows)
        out["%s.%s.from" % (prefix, key)] = fmt(hair + inst, "from")


# -------------------------------------------------------------------- render

def render(p):
    """Every derived string, keyed by its data-price marker."""
    out = {}
    ca, us = p["ca"], p["us"]
    n, w, k = ca["nano"], ca["weft"], ca["ktip"]

    out["deposit"] = money(p["deposit"])
    out["training_deposit"] = money(p["training_deposit"])

    # --- CA nano
    lens = n["lengths"]
    out["ca.nano.starting"] = "<br>".join(
        "%s from %s per 25g bundle" % (L["label"], money(L["bundle"])) for L in lens)
    out["ca.nano.bundle_min"] = money(min(L["bundle"] for L in lens))
    out["ca.nano.from"] = fmt(min(L["bundle"] for L in lens), "from")
    out["ca.nano.own_hair"] = fmt(n["own_hair"])
    cw, ch = _ladder(n["maint"])
    out["ca.nano.maint.whole"] = _rows_html(cw)
    out["ca.nano.maint.half"] = _rows_html(ch)
    out["ca.nano.maint.min"] = money(min(n["maint"]["whole"]))
    out["ca.nano.maint.from"] = fmt(min(n["maint"]["whole"]), "from")
    out["ca.nano.removal"] = fmt(n["removal"])
    out["ca.nano.dematting"] = fmt(n["dematting"], "plus")
    out["ca.nano.curling"] = fmt(n["curling"])

    # --- CA wavy · same install, its own hair price per bundle
    cwv = ca["wavy"]["lengths"]
    out["ca.wavy.starting"] = "<br>".join(
        "%s from %s per 25g bundle" % (L["label"], money(L["bundle"])) for L in cwv)
    out["ca.wavy.bundle_min"] = money(min(L["bundle"] for L in cwv))
    out["ca.wavy.from"] = fmt(min(L["bundle"] for L in cwv), "from")

    # --- CA Genius Wefts
    out["ca.weft.hair_list"] = _slash(w["hair"])
    out["ca.weft.hair_from"] = fmt(min(w["hair"]), "from")
    out["ca.weft.install_list"] = _slash(w["install"])
    out["ca.weft.install_from"] = fmt(min(w["install"]), "from")
    out["ca.weft.maint_rows"] = _rows_html([(r["label"], r["price"]) for r in w["maint_rows"]])
    out["ca.weft.maint_from"] = fmt(min(r["price"] for r in w["maint_rows"]), "from")
    out["ca.weft.cocktail"] = _rng(w["cocktail_min"], w["cocktail_max"])
    out["ca.weft.removal"] = fmt(w["removal"], "from")
    out["ca.weft.addons"] = ("Nano cocktail (15–25 g) — %s<br>Weft removal — %s"
                             % (out["ca.weft.cocktail"], out["ca.weft.removal"]))

    # --- CA K-Tips
    out["ca.ktip.list"] = _slash(k["hair_install"])
    out["ca.ktip.from"] = fmt(min(k["hair_install"]), "from")
    out["ca.ktip.removal"] = _rng(k["removal_min"], k["removal_max"])

    # --- US nano · hair is priced separately, so every total is hair + install
    un = us["nano"]
    _bundle_tables(out, "us.nano", un)
    _bundle_tables(out, "us.wavy", us["wavy"])
    uw, uh = _ladder(un["maint"])
    out["us.nano.maint.whole"] = _rows_html(uw, "+")
    out["us.nano.maint.half"] = _rows_html(uh, "+")
    out["us.nano.maint.from"] = fmt(min(un["maint"]["whole"]), "from")
    out["us.nano.removal"] = fmt(un["removal"], "from")

    # --- colour & care menu (shown on both sites)
    for c in p["colour"]:
        out["colour." + c["id"]] = fmt(c["value"], c.get("fmt", "plain"))

    return out


# ---------------------------------------------------------------------- read

def read_prices():
    with open(PRICES_JSON, encoding="utf-8") as f:
        return json.load(f)


def write_prices(p):
    with open(PRICES_JSON, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _num(v, old):
    """Accept a number (or numeric string) from the admin; keep old on junk."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return old
    if f != f or f in (float("inf"), float("-inf")) or f < 0:
        return old
    return int(f) if abs(f - round(f)) < 1e-9 else round(f, 2)


def merge(base, incoming):
    """Overlay admin input on the stored prices, shape-checked against it.

    Numbers stay numbers, lists keep their length, unknown keys are dropped —
    the posted payload can never reshape the file.
    """
    if isinstance(base, dict):
        if not isinstance(incoming, dict):
            return base
        return {k: merge(v, incoming.get(k, v)) for k, v in base.items()}
    if isinstance(base, list):
        if not isinstance(incoming, list):
            return base
        return [merge(v, incoming[i] if i < len(incoming) else v)
                for i, v in enumerate(base)]
    if isinstance(base, bool):
        return base
    if isinstance(base, (int, float)):
        return _num(incoming, base)
    return base                                     # labels/names/ids: untouched


# --------------------------------------------------------------------- apply

_MARKER = re.compile(
    r'(<(\w+)(?=[^>]*\bdata-price="([^"]+)")[^>]*>)(.*?)(</\2>)', re.S)


def _write_markers(html, r):
    """Replace the contents of every <tag data-price="key"> with its render."""
    hits = []

    def sub(m):
        key = m.group(3)
        if key not in r:
            return m.group(0)
        hits.append(key)
        return m.group(1) + r[key] + m.group(5)

    return _MARKER.sub(sub, html), hits


def _write_meta(html, r):
    """services.html meta/OG/Twitter descriptions quote two headline prices."""
    html = re.sub(r"installs from %s per bundle" % MONEY_RE,
                  "installs from %s per bundle" % r["ca.nano.from"][len("from "):], html)
    html = re.sub(r"maintenance from %s" % MONEY_RE,
                  "maintenance from %s" % r["ca.nano.maint.from"][len("from "):], html)
    return html


def _catalog(p, r):
    """The services.html OfferCatalog, rebuilt from the same numbers."""
    ca, us = p["ca"], p["us"]
    n, w, k, un = ca["nano"], ca["weft"], ca["ktip"], us["nano"]
    cc, uc = ca["currency"], us["currency"]
    items = [
        ("New install — hair + install", min(L["bundle"] for L in n["lengths"]), "minPrice", cc),
        ("Install — bring your own hair", n["own_hair"], "price", cc),
        ("Maintenance", min(n["maint"]["whole"]), "minPrice", cc),
        ("Removal", n["removal"], "price", cc),
        ("Dematting", n["dematting"], "price", cc),
        ("Hair curling", n["curling"], "price", cc),
    ]
    for L in un["lengths"]:
        items.append(("%s Nano — hair + install" % L["label"],
                      float(L["hair"]) + float(un["install_per_bundle"]), "minPrice", uc))
    items.append(("Wavy nano — hair + install",
                  min(L["bundle"] for L in ca["wavy"]["lengths"]), "minPrice", cc))
    for L in us["wavy"]["lengths"]:
        items.append(("%s Wavy nano — hair + install" % L["label"],
                      float(L["hair"]) + float(us["wavy"]["install_per_bundle"]),
                      "minPrice", uc))
    items += [
        ("Maintenance", min(un["maint"]["whole"]), "minPrice", uc),
        ("Removal only", un["removal"], "minPrice", uc),
        ("Weft hair", min(w["hair"]), "minPrice", cc),
        ("Custom install", min(w["install"]), "minPrice", cc),
        ("Maintenance", min(x["price"] for x in w["maint_rows"]), "minPrice", cc),
        ("Nano cocktail pieces", w["cocktail_min"], "price", cc),
        ("Weft removal", w["removal"], "minPrice", cc),
        ("Hair + install", min(k["hair_install"]), "minPrice", cc),
        ("Removal", k["removal_min"], "price", cc),
    ]
    for c in p["colour"]:
        kind = "minPrice" if c.get("fmt") == "from" else "price"
        items.append((c["name"], c["value"], kind, cc))
    return [{
        "@type": "Offer",
        "itemOffered": {"@type": "Service", "name": name,
                        "provider": {"@id": PROVIDER}},
        "priceSpecification": {"@type": "PriceSpecification", kind: float(val),
                               "priceCurrency": cur},
    } for name, val, kind, cur in items]


def _write_schema(html, p, r):
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', html, re.S)
    if not m:
        return html
    try:
        data = json.loads(m.group(2))
    except ValueError:
        return html

    found = [False]

    def walk(o):
        if isinstance(o, dict):
            if o.get("@type") == "OfferCatalog" and str(o.get("@id", "")).endswith("#menu"):
                o["itemListElement"] = _catalog(p, r)
                found[0] = True
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    if not found[0]:
        return html
    body = json.dumps(data, indent=2, ensure_ascii=False)
    return html[:m.start(2)] + "\n" + body + "\n" + html[m.end(2):]


_LDJSON = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)
_DEPOSIT_PROSE = re.compile(
    MONEY_RE + r"(?=\s+(?:non-refundable\s+)?(?:hair\s+)?deposit)")


def _write_schema_prose(html, r):
    """The deposit is quoted inside FAQ answers in the schema blocks too.

    Only touched inside ld+json — the visible copy carries a data-price marker,
    which this pattern can't match across the span tag.
    """
    return _LDJSON.sub(
        lambda m: m.group(1) + _DEPOSIT_PROSE.sub(r["deposit"], m.group(2)) + m.group(3),
        html)


def _write_content_overrides(r):
    """US copy overrides live in content.json — keep their markers current too."""
    try:
        with open(CONTENT_JSON, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError):
        return 0
    hits = 0
    for loc in ("ca", "us"):
        texts = (c.get(loc) or {}).get("text") or {}
        for tid, val in list(texts.items()):
            if not isinstance(val, str) or "data-price=" not in val:
                continue
            new, got = _write_markers(val, r)
            if new != val:
                texts[tid] = new
                hits += len(got)
    if hits:
        with open(CONTENT_JSON, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2)
    return hits


def apply_prices(p=None):
    """Push prices.json out to every page. Returns {page: markers written}."""
    p = p or read_prices()
    r = render(p)
    report = {}
    for page in PRICE_PAGES:
        path = os.path.join(SITE, page)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            html = orig = f.read()
        html, hits = _write_markers(html, r)
        html = _write_schema_prose(html, r)
        if page == "services.html":
            html = _write_meta(html, r)
            html = _write_schema(html, p, r)
        if html != orig:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
        report[page] = len(hits)
    report["content.json"] = _write_content_overrides(r)
    return report


if __name__ == "__main__":
    print(json.dumps(apply_prices(), indent=2))
