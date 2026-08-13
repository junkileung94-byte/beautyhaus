#!/usr/bin/env python3
"""Verify the /sarasota/ locale pair as a crawler sees it — raw HTML, no JavaScript.

Checks per US page: self-canonical, reciprocal hreflang, no CA-only blocks left,
no Barrie address in visible copy, internal links pointing at the US set, and a
Sarasota-targeted title. Then the CA side: hreflang back to its US twin.
"""
import re, sys, urllib.request

ORIGIN = "https://beautyextensionhaus.com"
PAIRS = [("/", "/sarasota/"),
         ("/services.html", "/sarasota/services.html"),
         ("/why-nano.html", "/sarasota/why-nano.html"),
         ("/care.html", "/sarasota/care.html")]


def get(path):
    req = urllib.request.Request(ORIGIN + path, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def strip_jsonld(h):
    return re.sub(r'(?is)<script type="application/ld\+json">.*?</script>', "", h)


def canonical(h):
    m = re.search(r'<link\b(?=[^>]*rel="canonical")[^>]*href="([^"]+)"', h, re.I)
    return m.group(1) if m else None


def hreflangs(h):
    return dict((lang, href) for href, lang in
                re.findall(r'<link\b(?=[^>]*rel="alternate")[^>]*href="([^"]+)"[^>]*hreflang="([^"]+)"',
                           h, re.I)) or \
           dict((lang, href) for lang, href in
                re.findall(r'<link\b(?=[^>]*rel="alternate")[^>]*hreflang="([^"]+)"[^>]*href="([^"]+)"',
                           h, re.I))


fails = []
for ca_path, us_path in PAIRS:
    us, ca = get(us_path), get(ca_path)
    body = strip_jsonld(us)

    def check(cond, msg):
        if not cond:
            fails.append("%s: %s" % (us_path, msg))

    check(canonical(us) == ORIGIN + us_path,
          "canonical is %s, want %s" % (canonical(us), ORIGIN + us_path))
    hl_us, hl_ca = hreflangs(us), hreflangs(ca)
    check(hl_us.get("en-US") == ORIGIN + us_path, "en-US hreflang wrong: %s" % hl_us.get("en-US"))
    check(hl_us.get("en-CA") == ORIGIN + ca_path, "en-CA hreflang wrong: %s" % hl_us.get("en-CA"))
    check(hl_ca.get("en-US") == ORIGIN + us_path,
          "CA page %s does not point back: %s" % (ca_path, hl_ca.get("en-US")))
    check(hl_ca.get("x-default") == ORIGIN + ca_path, "CA x-default wrong")
    check('data-loc="ca"' not in us, "CA-only blocks still present")
    check("480 Mapleton" not in body, "Barrie address in visible US copy")
    check("Sarasota" in re.search(r"(?is)<title>(.*?)</title>", us).group(1),
          "title not Sarasota-targeted")
    check(canonical(ca) == ORIGIN + ca_path, "CA canonical drifted: %s" % canonical(ca))
    # nav links on a US page must stay inside the US set
    navs = re.findall(r'href="(/(?:services|why-nano|care)\.html)"', body)
    check(not navs, "links to CA pages leak into the US page: %s" % sorted(set(navs)))
    print("%-26s canonical ok · hreflang ok · %d Sarasota mentions"
          % (us_path, body.count("Sarasota")))

print("\nFAIL %d" % len(fails) if fails else "\nall US locale checks pass")
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
