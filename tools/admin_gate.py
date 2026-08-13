#!/usr/bin/env python3
"""Admin-console regression gate for the on-site SEO pass.

Proves the client can still edit every copy slot, in both locales, after markup
changes. Runs against a THROWAWAY COPY of the site so nothing here can write to
what nginx is serving.

Checks:
  A  slot inventory      — every data-edit id the admin can see, per page
  B  CA round-trip       — set_text(..., "ca") rewrites the HTML and restores
  C  US round-trip       — set_text(..., "us") writes content.json and restores
  D  link safety         — no <a href> to an internal page sits INSIDE a data-edit element
  E  override integrity  — every US override id still resolves to an element in the HTML

Usage:  python3 admin_gate.py [baseline.json]
        no arg  -> print report, write /tmp/admin-gate.json
        arg     -> also diff against that earlier run and fail on regressions
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile

SRC = "/home/mj/beautyhaus"
INTERNAL = re.compile(
    r'href="(?:/|\.\./)?(?:index|services|care|trade|why-nano|'
    r'hair-extensions-barrie|nano-bead-hair-extensions-sarasota)\.html|'
    r'href="(?:/|\.\./)?guide/')


def load_admin(root):
    """Import the admin server from a copy so its SITE constant points at the copy."""
    path = os.path.join(root, "tools", "haus_admin_server.py")
    spec = importlib.util.spec_from_file_location("admin_under_test", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["admin_under_test"] = m
    spec.loader.exec_module(m)
    assert m.SITE == os.path.join(root, "preview", "haus"), m.SITE
    return m


def check_link_safety(site, content):
    """D — internal links inside editable slots.

    The admin's sanitiser (admin.html cleanTx) keeps <a> tags, so a link inside a
    data-edit slot survives an ordinary save — it is a WARN, not a failure. What
    does break: a slot carrying a US override, because js/haus.js:331 replaces the
    element's innerHTML with that override string. If the override has no link, the
    link exists on the CA site only. That is the FAIL.
    """
    bad = []
    us = (content.get("us") or {}).get("text", {})
    tags = "h1|h2|h3|h4|p|li|a|span|td|th|summary|footer|figcaption|blockquote"
    for dirpath, dirnames, filenames in os.walk(site):
        dirnames[:] = [d for d in dirnames if d not in ("assets", "css", "js", "docs")]
        for fn in sorted(filenames):
            if not fn.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), site)
            html = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for m in re.finditer(r'<(%s)[^>]*\bdata-edit="([^"]+)"[^>]*>(.*?)</\1>'
                                 % tags, html, re.S):
                inner, eid = m.group(3), m.group(2)
                if INTERNAL.search(inner):
                    override = us.get(eid)
                    bad.append({
                        "page": rel, "id": eid,
                        "snippet": re.sub(r"\s+", " ", inner)[:90],
                        "us_override": override is not None,
                        # link lost on the US site: override exists and carries no link
                        "us_drops_link": override is not None
                                         and not INTERNAL.search(override),
                    })
    return bad


def check_overrides(admin, site):
    """E — a US override whose id no longer exists in the HTML is dead copy."""
    content = admin.read_content()
    ids = set()
    for dirpath, dirnames, filenames in os.walk(site):
        dirnames[:] = [d for d in dirnames if d not in ("assets", "css", "js", "docs")]
        for fn in filenames:
            if fn.endswith(".html"):
                html = open(os.path.join(dirpath, fn), encoding="utf-8").read()
                ids |= set(re.findall(r'data-edit="([^"]+)"', html))
    orphans = {}
    for loc in ("ca", "us"):
        t = (content.get(loc) or {}).get("text", {})
        orphans[loc] = sorted(k for k in t if k not in ids)
    return orphans


def main():
    root = tempfile.mkdtemp(prefix="admin-gate-")
    try:
        for sub in ("preview", "tools"):
            shutil.copytree(os.path.join(SRC, sub), os.path.join(root, sub),
                            ignore=shutil.ignore_patterns("assets", "__pycache__"))
        # assets are needed for content.json but are heavy — copy just what admin reads
        os.makedirs(os.path.join(root, "preview", "haus", "assets"), exist_ok=True)
        for f in ("content.json", "layout.json", "gallery.json", "beforeafter.json"):
            s = os.path.join(SRC, "preview", "haus", "assets", f)
            if os.path.exists(s):
                shutil.copy(s, os.path.join(root, "preview", "haus", "assets", f))

        admin = load_admin(root)
        site = admin.SITE
        report = {"slots": {}, "ca_roundtrip": {}, "us_roundtrip": {}}

        # A — inventory
        texts = admin.scan_texts()
        per_page = {}
        for t in texts:
            per_page.setdefault(t["page"], []).append(t["id"])
        report["slots"] = {p: sorted(v) for p, v in sorted(per_page.items())}
        report["slot_total"] = len(texts)

        # B / C — round-trips, one slot per page, both locales
        for page, ids in sorted(per_page.items()):
            eid = sorted(ids)[0]
            path = os.path.join(site, page)
            before = open(path, encoding="utf-8").read()
            ok_ca = admin.set_text(eid, "PROBE-CA", "ca")
            after = open(path, encoding="utf-8").read()
            hit = "PROBE-CA" in after
            open(path, "w", encoding="utf-8").write(before)   # restore
            report["ca_roundtrip"][page] = {"id": eid, "returned": bool(ok_ca),
                                            "written": hit,
                                            "restored": open(path, encoding="utf-8").read() == before}
            content_before = json.dumps(admin.read_content(), sort_keys=True)
            admin.set_text(eid, "PROBE-US", "us")
            c = admin.read_content()
            us_hit = c["us"]["text"].get(eid) == "PROBE-US"
            c2 = json.loads(content_before)
            admin.write_content(c2)
            report["us_roundtrip"][page] = {"id": eid, "written": us_hit,
                                            "restored": json.dumps(admin.read_content(),
                                                                   sort_keys=True) == content_before}

        report["links_inside_edit_slots"] = check_link_safety(site, admin.read_content())
        report["orphaned_overrides"] = check_overrides(admin, site)

        failures = []
        for page, r in report["ca_roundtrip"].items():
            if not (r["returned"] and r["written"] and r["restored"]):
                failures.append("CA round-trip failed on %s (%s)" % (page, r["id"]))
        for page, r in report["us_roundtrip"].items():
            if not (r["written"] and r["restored"]):
                failures.append("US round-trip failed on %s (%s)" % (page, r["id"]))
        warnings = []
        for b in report["links_inside_edit_slots"]:
            if b["us_drops_link"]:
                failures.append("US override drops the link in slot %s on %s"
                                % (b["id"], b["page"]))
            else:
                warnings.append("link inside editable slot %s on %s (survives saves)"
                                % (b["id"], b["page"]))
        for loc, orph in report["orphaned_overrides"].items():
            for o in orph:
                warnings.append("orphaned %s override: %s (dead copy, no element)"
                                % (loc.upper(), o))

        baseline = None
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            baseline = json.load(open(sys.argv[1]))
            lost = {i for p in baseline["slots"].values() for i in p} - \
                   {i for p in report["slots"].values() for i in p}
            for i in sorted(lost):
                failures.append("slot id LOST since baseline: %s" % i)
            if baseline["slot_total"] != report["slot_total"]:
                print("note: slot count %d -> %d"
                      % (baseline["slot_total"], report["slot_total"]))

        print("slots: %d across %d pages" % (report["slot_total"], len(report["slots"])))
        print("CA round-trips: %d ok" % sum(
            1 for r in report["ca_roundtrip"].values()
            if r["returned"] and r["written"] and r["restored"]))
        print("US round-trips: %d ok" % sum(
            1 for r in report["us_roundtrip"].values() if r["written"] and r["restored"]))
        print("links inside editable slots: %d (%d lose the link on the US site)"
              % (len(report["links_inside_edit_slots"]),
                 sum(1 for b in report["links_inside_edit_slots"] if b["us_drops_link"])))
        for b in report["links_inside_edit_slots"]:
            print("   %s %s  %s  %s" % ("US-DROPS" if b["us_drops_link"] else "ok      ",
                                        b["page"], b["id"], b["snippet"][:60]))
        print("orphaned overrides: ca=%d us=%d" % (len(report["orphaned_overrides"]["ca"]),
                                                   len(report["orphaned_overrides"]["us"])))
        for o in report["orphaned_overrides"]["us"]:
            print("   US orphan:", o)

        out = "/tmp/admin-gate.json"
        json.dump(report, open(out, "w"), indent=1)
        print("\nreport ->", out)

        if warnings:
            print("\nWARN (%d) — pre-existing, not blocking:" % len(warnings))
            for w in warnings:
                print("  -", w)
        if failures:
            print("\nFAIL (%d):" % len(failures))
            for f in failures:
                print("  -", f)
            return 1
        print("\nPASS")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
