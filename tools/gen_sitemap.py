#!/usr/bin/env python3
"""Generate preview/haus/sitemap.xml from the site's own pages. Stdlib only.

Rules (claude-seo seo-sitemap + this site's constraints):
  - URL source is each page's own <link rel="canonical"> — the sitemap can never
    disagree with the page. A page missing a canonical FAILS the run (exit 2),
    so this doubles as a canonical lint.
  - Skips: docs/ (confidential, nginx-404'd), 404.html, any page whose meta
    robots contains "noindex".
  - Reads settings.json: while both `training` and `hiring` are false the live
    site client-side-redirects trade.html away, so it is dropped from the map.
  - <lastmod> from the file's mtime (real per-page dates, YYYY-MM-DD).
  - No <priority>/<changefreq> — ignored by Google.
  - Atomic write: tempfile + os.replace, so nginx never serves a half file.

Run on demand after content changes:  python3 tools/gen_sitemap.py
"""
import json, os, re, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "preview", "haus")
OUT = os.path.join(SITE, "sitemap.xml")

# attribute order is not fixed: hand-authored pages write rel first, the generated
# /sarasota/ pages (BeautifulSoup output) write href first. Match either.
CANON_RE = re.compile(
    r'<link\b(?=[^>]*\brel="canonical")[^>]*\bhref="([^"]+)"', re.I)
ROBOTS_RE = re.compile(
    r'<meta\s+name="robots"\s+content="([^"]*)"', re.I)


def settings():
    try:
        with open(os.path.join(SITE, "settings.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def collect():
    s = settings()
    drop_trade = not s.get("training") and not s.get("hiring")
    entries, errors = [], []
    for dirpath, dirnames, filenames in os.walk(SITE):
        rel = os.path.relpath(dirpath, SITE)
        # never descend into confidential or asset trees
        dirnames[:] = [d for d in dirnames
                       if d not in ("docs", "assets", "css", "js")]
        for fn in sorted(filenames):
            if not fn.endswith(".html") or fn == "404.html":
                continue
            relpath = fn if rel == "." else os.path.join(rel, fn)
            if drop_trade and relpath == "trade.html":
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            m = ROBOTS_RE.search(html)
            if m and "noindex" in m.group(1).lower():
                continue
            c = CANON_RE.search(html)
            if not c:
                errors.append(relpath)
                continue
            loc = c.group(1)
            if not loc.startswith("https://"):
                errors.append("%s (non-https canonical: %s)" % (relpath, loc))
                continue
            lastmod = time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(path)))
            entries.append((loc, lastmod))
    return entries, errors


def main():
    entries, errors = collect()
    if errors:
        for e in errors:
            print("MISSING/BAD CANONICAL: %s" % e, file=sys.stderr)
        sys.exit(2)
    # de-dup (two files claiming one canonical would be a bug worth failing on)
    seen = {}
    for loc, lastmod in entries:
        if loc in seen:
            print("DUPLICATE CANONICAL: %s" % loc, file=sys.stderr)
            sys.exit(2)
        seen[loc] = lastmod
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc in sorted(seen):
        lines.append("  <url><loc>%s</loc><lastmod>%s</lastmod></url>"
                     % (loc, seen[loc]))
    lines.append("</urlset>\n")
    body = "\n".join(lines)
    fd, tmp = tempfile.mkstemp(dir=SITE, suffix=".sitemap")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    os.chmod(tmp, 0o644)   # mkstemp gives 0600; nginx (other user) must read it
    os.replace(tmp, OUT)
    print("wrote %s (%d URLs)" % (OUT, len(seen)))


if __name__ == "__main__":
    main()
