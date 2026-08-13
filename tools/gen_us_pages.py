#!/usr/bin/env python3
"""Generate the server-rendered US site under /sarasota/.

Why this exists
---------------
The site serves one set of URLs for both locales: assets/content.json holds the US
copy and js/haus.js swaps it in with innerHTML at runtime. A crawler therefore only
ever sees the Canadian text, so the US versions of home, services, why-nano and care
have no URL to rank and no server-rendered copy to rank on.

This generator takes the authored (CA) page, applies the US overrides that the admin
console already manages, drops the CA-only blocks, and writes a real US page at
/sarasota/<page>. The admin console keeps editing content.json exactly as before —
the pages are regenerated on save.

Pairs every page with hreflang en-CA / en-US / x-default, and gives each side a
self-referencing canonical, so the two URL sets are a locale pair rather than
duplicate content.

Run:  python3 tools/gen_us_pages.py [--dry]
"""
import json, os, re, sys

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "preview", "haus")
OUT_DIR = os.path.join(SITE, "sarasota")
ORIGIN = "https://beautyextensionhaus.com"
DRY = "--dry" in sys.argv

# CA page -> US page. index.html becomes /sarasota/ (directory index).
PAGES = {
    "index.html": "index.html",
    "services.html": "services.html",
    "why-nano.html": "why-nano.html",
    "care.html": "care.html",
}

# US-facing title + meta description. The CA pages target Barrie; these target
# Sarasota, which is the entire point of giving the locale its own URLs.
META = {
    "index.html": (
        "Hair Extensions Sarasota FL | Beauty Extension Haus",
        "Nano bead hair extensions in Sarasota, Florida — strand by strand, no glue, "
        "no heat, no chemicals. Downtown at 1724 4th Street."),
    "services.html": (
        "Hair Extension Prices Sarasota | Beauty Extension Haus",
        "Hair extension prices in Sarasota, Florida: nano bead installs, maintenance, "
        "custom color and K-Tips, priced in USD at 1724 4th Street."),
    "why-nano.html": (
        "Nano Bead Extensions for Fine Hair | Sarasota, Florida",
        "Nano bead extensions for fine hair in Sarasota: no glue, no heat, no chemicals, "
        "and the most discreet attachment there is."),
    "care.html": (
        "Hair Extension Aftercare | Beauty Extension Haus Sarasota",
        "Hair extension aftercare in Sarasota: how to wash, sleep in and look after nano "
        "bead extensions, plus the questions we hear most."),
}

SKIP_PREFIX = ("http://", "https://", "//", "#", "mailto:", "tel:", "data:", "blob:", "/")


def us_url(page):
    return "/sarasota/" if page == "index.html" else "/sarasota/" + page


def ca_url(page):
    return "/" if page == "index.html" else "/" + page


def rewrite_url(u):
    """Relative -> root-absolute; CA page links -> their /sarasota/ counterpart."""
    if not u or u.startswith(SKIP_PREFIX):
        return u
    frag = ""
    if "#" in u:
        u, frag = u.split("#", 1)
        frag = "#" + frag
    if not u:                       # pure fragment
        return frag
    base = u.split("?")[0]
    query = u[len(base):]
    if base in PAGES:
        return us_url(base) + query + frag
    return "/" + base + query + frag


def read_loc_us():
    """The US location block out of js/haus.js, so the address is never duplicated here.

    js/haus.js:425-428 fills [data-loc-field] nodes at runtime. A crawler never runs
    that, so a prerendered US page would otherwise ship the Barrie address — the exact
    NAP mistake that costs local rankings.
    """
    js = open(os.path.join(SITE, "js", "haus.js"), encoding="utf-8").read()
    m = re.search(r"\bus:\s*\{(.*?)\}", js, re.S)
    if not m:
        raise SystemExit("gen_us_pages: could not find LOC.us in js/haus.js")
    return dict(re.findall(r'(\w+)\s*:\s*"([^"]*)"', m.group(1)))


def apply_loc_fields(soup, loc):
    """Mirror of applyLoc() in js/haus.js, done at build time instead of runtime."""
    n = 0
    for node in soup.select("[data-loc-field]"):
        f = node.get("data-loc-field")
        if f == "phone":
            node.string = loc["phone"]
            if node.name == "a":
                node["href"] = loc["phoneHref"]
        elif f == "email":
            node.string = loc["email"]
            if node.name == "a":
                node["href"] = "mailto:" + loc["email"]
        elif f == "book":
            if node.name == "a":
                node["href"] = loc["book"]
            if not node.has_attr("data-keep-label"):
                node.string = loc["bookLabel"]
        elif f in loc:
            node.string = loc[f]
        else:
            continue
        n += 1
    return n


def apply_us_content(soup, page, content):
    text = (content.get("us") or {}).get("text", {})
    img = (content.get("us") or {}).get("img", {})
    applied = 0
    for node in soup.select("[data-edit]"):
        eid = node.get("data-edit")
        if eid in text:
            node.clear()
            node.append(BeautifulSoup(text[eid], "html.parser"))
            applied += 1
    for node in soup.select("img[data-slot]"):
        slot = node.get("data-slot")
        if slot in img and img[slot].get("desktop"):
            node["src"] = rewrite_url(img[slot]["desktop"])
            applied += 1
    for node in soup.select("source[data-slot-src]"):
        slot = node.get("data-slot-src")
        if slot in img and img[slot].get("desktop"):
            node["srcset"] = rewrite_url(img[slot]["desktop"])
            applied += 1
    return applied


def strip_ca_only(soup, page, layout):
    """Remove CA-only blocks and any section the admin hides for the US locale."""
    removed = 0
    for node in soup.select("[data-loc]"):
        locs = (node.get("data-loc") or "").split()
        if "us" not in locs:
            node.decompose()
            removed += 1
    hidden = ((layout.get("us") or {}).get(page) or {}).get("hidden") or []
    for name in hidden:
        for node in soup.select('[data-section="%s"]' % name):
            node.decompose()
            removed += 1
    return removed


def rewrite_urls(soup):
    for node in soup.find_all(True):
        for attr in ("href", "src", "action"):
            if node.has_attr(attr):
                node[attr] = rewrite_url(node[attr])
        if node.has_attr("srcset"):
            node["srcset"] = ", ".join(
                " ".join([rewrite_url(p.split()[0])] + p.split()[1:])
                for p in (s.strip() for s in node["srcset"].split(",")) if p)


def set_head(soup, page):
    title, desc = META[page]
    if soup.title:
        soup.title.string = title
    for sel, attr, val in (
            ('meta[name="description"]', "content", desc),
            ('meta[property="og:title"]', "content", title),
            ('meta[property="og:description"]', "content", desc),
            ('meta[property="og:url"]', "content", ORIGIN + us_url(page)),
            ('meta[name="twitter:title"]', "content", title),
            ('meta[name="twitter:description"]', "content", desc)):
        for node in soup.select(sel):
            node[attr] = val
    for node in soup.select('link[rel="canonical"]'):
        node["href"] = ORIGIN + us_url(page)
    set_hreflang(soup, page)


def set_hreflang(soup, page):
    """en-CA / en-US / x-default, idempotent — used for both sides of the pair."""
    for node in soup.select("link[hreflang]"):
        node.decompose()
    canon = soup.select_one('link[rel="canonical"]')
    if not canon:
        return
    for lang, href in (("en-CA", ORIGIN + ca_url(page)),
                       ("en-US", ORIGIN + us_url(page)),
                       ("x-default", ORIGIN + ca_url(page))):
        link = soup.new_tag("link", rel="alternate", href=href)
        link["hreflang"] = lang
        canon.insert_after(link)


def fix_jsonld(soup, page):
    """The US page keeps both real locations but points its WebPage node at itself."""
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.string or "{}")
        except Exception:
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        nodes = graph if isinstance(graph, list) else [data]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            t = n.get("@type")
            if t == "WebPage":
                n["url"] = ORIGIN + us_url(page)
                n["name"] = META[page][0]
                n["description"] = META[page][1]
            if isinstance(n.get("@id"), str):
                n["@id"] = n["@id"].replace(ORIGIN + ca_url(page), ORIGIN + us_url(page))
        node.string = json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build(page, content, layout, loc):
    html = open(os.path.join(SITE, page), encoding="utf-8").read()
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if body is not None:
        body["data-haus-pin"] = "us"          # js/haus.js renders this locale outright
    applied = apply_us_content(soup, page, content)
    applied += apply_loc_fields(soup, loc)
    removed = strip_ca_only(soup, page, layout)
    rewrite_urls(soup)
    set_head(soup, page)
    fix_jsonld(soup, page)
    banner = ("\n<!-- generated by tools/gen_us_pages.py from %s — do not edit by hand; "
              "edit the CA page or the US copy in /admin -->\n" % page)
    return str(soup) + banner, applied, removed


def pair_ca_page(page):
    """Give the CA original the matching hreflang trio.

    Deliberately a string edit, not a BeautifulSoup round-trip: re-serialising an
    authored page rewrites every attribute order and self-closing tag in it, which
    is 1,500 lines of churn on a live file and breaks gen_sitemap.py's canonical
    lint. The generated US pages are machine-owned, so bs4 is fine there; these are
    hand-authored, so only the three lines we add may change.
    """
    path = os.path.join(SITE, page)
    html = open(path, encoding="utf-8").read()
    canon = re.search(r'<link rel="canonical" href="[^"]*">', html)
    if not canon:
        print("  ! %s has no canonical — skipped hreflang" % page)
        return False
    block = "".join(
        '\n<link rel="alternate" hreflang="%s" href="%s">' % (lang, href)
        for lang, href in (("en-CA", ORIGIN + ca_url(page)),
                           ("en-US", ORIGIN + us_url(page)),
                           ("x-default", ORIGIN + ca_url(page))))
    existing = re.findall(r'\n<link rel="alternate" hreflang="[^"]*" href="[^"]*">', html)
    if "".join(existing) == block:
        return False
    for e in existing:                      # drop stale pairs before re-adding
        html = html.replace(e, "")
    html = html.replace(canon.group(0), canon.group(0) + block, 1)
    if not DRY:
        open(path, "w", encoding="utf-8").write(html)
    return True


def main():
    content = json.load(open(os.path.join(SITE, "assets", "content.json"), encoding="utf-8"))
    layout_path = os.path.join(SITE, "assets", "layout.json")
    layout = json.load(open(layout_path, encoding="utf-8")) if os.path.exists(layout_path) else {}

    if not DRY:
        os.makedirs(OUT_DIR, exist_ok=True)
    loc = read_loc_us()
    written = paired = 0
    for page, out_name in PAGES.items():
        html, applied, removed = build(page, content, layout, loc)
        out = os.path.join(OUT_DIR, out_name)
        if not DRY:
            tmp = out + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(html)
            os.replace(tmp, out)     # atomic: nginx never serves a half file
        written += 1
        print("  %-16s -> %-26s overrides=%-3d ca-blocks-removed=%d"
              % (page, us_url(page), applied, removed))
        if pair_ca_page(page):
            paired += 1

    print("\nwrote %d US pages, added hreflang to %d CA pages%s"
          % (written, paired, "  (dry run)" if DRY else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
