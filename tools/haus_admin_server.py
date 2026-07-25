#!/usr/bin/env python3
"""Beauty Extension Haus — preview server + /admin image manager.

Serves the static site from preview/haus on :8877 (same port the tailscale
serve proxy points at) and adds:

  GET  /admin              admin UI (tools/admin.html — NOT in the deployed tree)
  GET  /api/slots          every data-slot on the site (page, src or placeholder)
  GET  /api/library        images in haus-media-library/
  GET  /api/thumb/<name>   cached 360px thumbnail of a library image
  GET  /api/full/<name>    full-size library image (for the cropper)
  POST /api/apply          {slot, file, crop?{x,y,w,h}} → crop → assets/photos/slot-<slot>.jpg
                           and point the slot's <img> (or replace its placeholder) at it
  POST /api/sync           re-pull the Google Drive folder into the library

Tailnet-only by deployment (tailscale serve); no auth of its own.
"""
import io, json, os, re, subprocess, sys, threading, time
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import haus_auth as auth
from urllib.parse import parse_qs, urlsplit, unquote
from html import unescape as html_unescape
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
SITE = os.path.join(ROOT, "preview", "haus")
LIB = os.path.join(ROOT, "haus-media-library")
DOCS_DIR = os.path.join(SITE, "docs")
PHOTOS = os.path.join(SITE, "assets", "photos")
ADMIN_HTML = os.path.join(ROOT, "tools", "admin.html")
# Contact-form submissions, written by the deploy/contact receiver. In the
# container this is the /data ro mount; locally it falls back to deploy/data.
MESSAGES_FILE = os.environ.get("HAUS_MESSAGES",
                               os.path.join(ROOT, "deploy", "data", "messages.jsonl"))


def read_messages(limit=500):
    """Contact-form submissions, newest first. Missing file -> []."""
    out = []
    try:
        with open(MESSAGES_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        return []
    except Exception:
        return []
    out.reverse()
    return out[:limit]
GDOWN = os.environ.get("HAUS_GDOWN", os.path.join(ROOT, "tools", ".venv", "bin", "gdown"))
PYEXE = os.environ.get("HAUS_PYEXE", os.path.join(ROOT, "tools", ".venv", "bin", "python3"))
SYNC_SCRIPT = os.path.join(ROOT, "tools", "haus_drive_sync.py")
DRIVE_URL = "https://drive.google.com/drive/folders/1nTIbsLNa0Gt1jgB1-oN5L2yM9aQt11UR"

# built-in drives (id, display name, legacy settings key) — always present, not removable.
# Extra named drives are user-managed and live in settings["drives"] as [{id,name,url}].
BUILTIN_DRIVES = [("ca", "Canada", "driveCa"),
                  ("us", "US · Sarasota", "driveUs"),
                  ("client", "Client hair", "driveClient")]
DRIVES = {d[0]: d[2] for d in BUILTIN_DRIVES}   # built-in id -> legacy settings key


def _slug_drive(name, taken):
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "drive"
    slug, n = base, 2
    while slug in taken or slug in DRIVES:
        slug = "%s-%d" % (base, n); n += 1
    return slug


def read_drives():
    """All drives [{id,name,url,builtin}] — built-ins seeded from legacy settings keys."""
    try:
        s = json.load(open(SETTINGS))
    except Exception:
        s = {}
    out, seen = [], set()
    for did, name, key in BUILTIN_DRIVES:
        out.append({"id": did, "name": name, "url": str(s.get(key, "") or ""), "builtin": True})
        seen.add(did)
    for d in (s.get("drives") or []):
        did = str(d.get("id") or "").strip()
        if did and did not in seen:
            seen.add(did)
            out.append({"id": did, "name": str(d.get("name") or did),
                        "url": str(d.get("url") or ""), "builtin": False})
    return out


def write_drives(drives):
    """Persist: built-in urls mirror to legacy keys, custom drives into settings['drives']."""
    try:
        s = json.load(open(SETTINGS))
    except Exception:
        s = {}
    custom = []
    for d in drives:
        did = str(d.get("id") or "").strip()
        if not did:
            continue
        if did in DRIVES:
            s[DRIVES[did]] = str(d.get("url") or "")
        else:
            custom.append({"id": did, "name": str(d.get("name") or did),
                           "url": str(d.get("url") or "")})
    s["drives"] = custom
    json.dump(s, open(SETTINGS, "w"), indent=2)


def drive_ids():
    return {d["id"] for d in read_drives()}


def drive_url(drive):
    for d in read_drives():
        if d["id"] == drive:
            return d["url"]
    return ""


def lib_dir(drive):
    d = drive if drive in drive_ids() else "ca"
    p = os.path.join(LIB, d)
    os.makedirs(p, exist_ok=True)
    return p


def thumbs_dir(drive):
    p = os.path.join(lib_dir(drive), ".thumbs")
    os.makedirs(p, exist_ok=True)
    return p


# sync runs as a subprocess under the venv python (which has gdown + requests);
# the server itself runs under system python (which has Pillow). Progress is
# parsed live from the subprocess stderr into SYNC_STATUS.
SYNC_STATUS = {}   # drive -> {running, done, total, downloaded, failed, ok, error}
SYNC_LOCK = threading.Lock()
_PROG_RE = re.compile(r"\[(\d+)/(\d+)\]\s+downloaded=(\d+)\s+failed=(\d+)")


def run_sync(drive, url):
    dest = lib_dir(drive)
    st = {"running": True, "done": 0, "total": 0, "downloaded": 0, "failed": 0,
          "ok": None, "started": time.time()}
    SYNC_STATUS[drive] = st
    try:
        proc = subprocess.Popen([PYEXE, SYNC_SCRIPT, url, dest],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        summary = {}
        for line in proc.stderr:
            m = _PROG_RE.search(line)
            if m:
                st.update(done=int(m.group(1)), total=int(m.group(2)),
                          downloaded=int(m.group(3)), failed=int(m.group(4)))
        out, _ = proc.communicate()
        for ln in (out or "").splitlines():
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    summary = json.loads(ln)
                except Exception:
                    pass
        st.update(summary)
        st["ok"] = proc.returncode == 0
    except Exception as e:
        st["ok"] = False
        st["error"] = str(e)
    st["running"] = False
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
VID_EXT = (".mp4", ".mov", ".webm", ".m4v")
PAGES = ["index.html", "services.html", "care.html", "trade.html", "why-nano.html",
         "hair-extensions-barrie.html", "nano-bead-hair-extensions-sarasota.html"]
SETTINGS = os.path.join(SITE, "settings.json")
DEFAULT_SETTINGS = {
    "training": False, "hiring": False, "beforeafter": True,
    "queensScrim": 0.7,   # dark overlay opacity over the "queens" bg photo (0–1)
    "driveCa": "https://drive.google.com/drive/folders/1nTIbsLNa0Gt1jgB1-oN5L2yM9aQt11UR",
    "driveUs": "",
    "driveClient": "",
}
CONTENT_JSON = os.path.join(SITE, "assets", "content.json")
LAYOUT_JSON = os.path.join(SITE, "assets", "layout.json")


def read_content():
    try:
        c = json.load(open(CONTENT_JSON))
    except Exception:
        c = {}
    for loc in ("ca", "us"):
        c.setdefault(loc, {})
        c[loc].setdefault("text", {})
        c[loc].setdefault("img", {})
        c[loc].setdefault("contact", {})   # per-locale phone/email overrides (visit section, nav, footer)
    c["us"].setdefault("team", [])   # Sarasota team lives in content.json (CA team lives in team.json)
    return c


def write_content(c):
    json.dump(c, open(CONTENT_JSON, "w"), indent=2)


# tags whose data-edit text the admin can edit in place
EDIT_TAGS = "h1|h2|h3|h4|p|li|a|span|td|th|summary|footer|figcaption|blockquote"


def scan_texts():
    """Every data-edit text node across the pages, with its base (CA) content."""
    out = []
    seen = set()
    for page in PAGES:
        path = os.path.join(SITE, page)
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        for m in re.finditer(
                r'<(%s)[^>]*\bdata-edit="([^"]+)"[^>]*>(.*?)</\1>' % EDIT_TAGS, html, re.S):
            eid = m.group(2)
            if eid in seen:
                continue
            seen.add(eid)
            out.append({"id": eid, "page": page, "tag": m.group(1),
                        "html": m.group(3).strip()})
    return out


def set_text(eid, value, locale):
    if locale == "us":
        c = read_content()
        c["us"]["text"][eid] = value
        write_content(c)
        return True
    # ca / base — write straight into the HTML element
    changed = False
    for page in PAGES:
        path = os.path.join(SITE, page)
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        new = re.sub(
            r'(<(%s)[^>]*\bdata-edit="%s"[^>]*>).*?(</\2>)'
            % (EDIT_TAGS, re.escape(eid)),
            lambda mm: mm.group(1) + value + mm.group(3), html, count=1, flags=re.S)
        if new != html:
            open(path, "w", encoding="utf-8").write(new)
            changed = True
    return changed
GALLERY_JSON = os.path.join(SITE, "assets", "gallery.json")
GALLERY_ASPECT = 4 / 5  # the carousel frame shape
BA_JSON = os.path.join(SITE, "assets", "beforeafter.json")
BA_ASPECT = 3 / 4       # before/after slider frame shape


def read_ba():
    try:
        return json.load(open(BA_JSON))
    except Exception:
        return []


def write_ba(items):
    json.dump(items, open(BA_JSON, "w"), indent=2)


def _fit_ba(im):
    """Center-crop a whole photo to the before/after frame aspect (3:4), no splitting."""
    w, h = im.size
    if w / h > BA_ASPECT:            # too wide — crop the sides
        nw = int(round(h * BA_ASPECT))
        x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    else:                           # too tall — crop top/bottom
        nh = int(round(w / BA_ASPECT))
        y = (h - nh) // 2
        im = im.crop((0, y, w, y + nh))
    im.thumbnail((1200, 1600))
    return im


def _crop_ba(spec, drive):
    """Load one before/after photo, apply the user's crop rect (if any), fit to 3:4.
    `spec` is either a bare filename or {"file": ..., "crop": {x,y,w,h}}."""
    fname = spec.get("file") if isinstance(spec, dict) else spec
    crop = spec.get("crop") if isinstance(spec, dict) else None
    flip = bool(spec.get("flip")) if isinstance(spec, dict) else False
    path = safe_lib_path(fname, drive)
    if not path:
        raise ValueError("unknown library file")
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if flip:
        im = ImageOps.mirror(im)        # crop rect was drawn on the flipped preview
    if crop:
        x, y, w, h = (int(crop[k]) for k in ("x", "y", "w", "h"))
        x = max(0, min(x, im.width - 1))
        y = max(0, min(y, im.height - 1))
        w = max(1, min(w, im.width - x))
        h = max(1, min(h, im.height - y))
        im = im.crop((x, y, x + w, y + h))
    return _fit_ba(im)          # enforce exact 3:4 + downsize (no-op crop when already 3:4)


def ba_add(before, after, drive="ca"):
    """Store a before/after pair from two separate photos, each cropped to the 3:4 slider frame."""
    before = _crop_ba(before, drive)
    after = _crop_ba(after, drive)
    base = "ba-%d" % int(time.time() * 1000)
    before.save(os.path.join(PHOTOS, base + "-before.jpg"), quality=85, optimize=True)
    after.save(os.path.join(PHOTOS, base + "-after.jpg"), quality=85, optimize=True)
    items = read_ba()
    items.append({"before": "assets/photos/%s-before.jpg" % base,
                  "after": "assets/photos/%s-after.jpg" % base})
    write_ba(items)
    return items


def read_gallery(locale="ca"):
    if locale == "us":
        c = read_content()
        g = c["us"].get("gallery")
        if isinstance(g, list):
            return g
        return []  # US starts with its own (empty) gallery
    try:
        return json.load(open(GALLERY_JSON))
    except Exception:
        return []


def write_gallery(items, locale="ca"):
    if locale == "us":
        c = read_content()
        c["us"]["gallery"] = items
        write_content(c)
    else:
        json.dump(items, open(GALLERY_JSON, "w"), indent=2)


def gallery_add(fname, crop, locale="ca", drive="ca"):
    src_path = safe_lib_path(fname, drive)
    if not src_path:
        raise ValueError("unknown library file")
    im = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    if crop:
        x, y, w, h = (int(crop[k]) for k in ("x", "y", "w", "h"))
        x = max(0, min(x, im.width - 1)); y = max(0, min(y, im.height - 1))
        w = max(16, min(w, im.width - x)); h = max(16, min(h, im.height - y))
        im = im.crop((x, y, x + w, y + h))
    else:
        # center-crop to the carousel aspect
        cur = im.width / im.height
        if cur > GALLERY_ASPECT:
            nw = int(im.height * GALLERY_ASPECT); x = (im.width - nw) // 2
            im = im.crop((x, 0, x + nw, im.height))
        else:
            nh = int(im.width / GALLERY_ASPECT); y = int((im.height - nh) * 0.15)
            im = im.crop((0, y, im.width, y + nh))
    im.thumbnail((1400, 1400))
    out = "gallery-%s%d.jpg" % ("us-" if locale == "us" else "", int(time.time() * 1000))
    im.save(os.path.join(PHOTOS, out), quality=85, optimize=True)
    items = read_gallery(locale)
    items.append({"src": "assets/photos/%s" % out, "alt": ""})
    write_gallery(items, locale)
    return items


# ---- team roster (CA in team.json, US in content.json["us"]["team"]) ----
# each member: {"name", "role", "bio", "photo"}. Photos are square (1:1) portraits.
TEAM_JSON = os.path.join(SITE, "assets", "team.json")
TEAM_ASPECT = 1  # square portrait crop


def read_team(locale="ca"):
    if locale == "us":
        t = read_content()["us"].get("team")
        return t if isinstance(t, list) else []
    try:
        t = json.load(open(TEAM_JSON))
        return t if isinstance(t, list) else []
    except Exception:
        return []


def write_team(items, locale="ca"):
    if locale == "us":
        c = read_content()
        c["us"]["team"] = items
        write_content(c)
    else:
        json.dump(items, open(TEAM_JSON, "w"), indent=2)


def _clean_member(f):
    f = f or {}
    return {
        "name": str(f.get("name", "")).strip()[:80],
        "role": str(f.get("role", "")).strip()[:140],
        "bio": str(f.get("bio", "")).strip()[:900],
    }


def _team_crop_square(im, crop):
    if crop:
        x, y, w, h = (int(crop[k]) for k in ("x", "y", "w", "h"))
        x = max(0, min(x, im.width - 1)); y = max(0, min(y, im.height - 1))
        w = max(16, min(w, im.width - x)); h = max(16, min(h, im.height - y))
        im = im.crop((x, y, x + w, y + h))
    else:  # center-crop to square, biased slightly toward the top (faces)
        side = min(im.width, im.height)
        x = (im.width - side) // 2
        y = int((im.height - side) * 0.15)
        im = im.crop((x, y, x + side, y + side))
    im.thumbnail((900, 900))
    return im


def team_save_photo(fname, crop, locale, drive):
    src_path = safe_lib_path(fname, drive)
    if not src_path:
        raise ValueError("unknown library file")
    im = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    im = _team_crop_square(im, crop)
    out = "team-%s%d.jpg" % ("us-" if locale == "us" else "", int(time.time() * 1000))
    im.save(os.path.join(PHOTOS, out), quality=86, optimize=True)
    return "assets/photos/%s" % out


def _team_gc(old_path, items):
    """Delete an admin-generated team photo no longer referenced by any member."""
    of = (old_path or "").split("?")[0]
    if "/team-" in of and not any(of in (it.get("photo", "") or "") for it in items):
        fp = os.path.join(SITE, of)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass


def team_add(fields, locale="ca"):
    items = read_team(locale)
    m = _clean_member(fields)
    m["photo"] = ""
    items.append(m)
    write_team(items, locale)
    return items


def team_update(index, fields, locale="ca"):
    items = read_team(locale)
    if 0 <= index < len(items):
        items[index].update(_clean_member(fields))
        write_team(items, locale)
    return items


def team_set_photo(index, fname, crop, locale="ca", drive="ca"):
    items = read_team(locale)
    if not (0 <= index < len(items)):
        raise ValueError("bad index")
    photo = team_save_photo(fname, crop, locale, drive)
    old = items[index].get("photo", "")
    items[index]["photo"] = photo
    write_team(items, locale)
    _team_gc(old, items)
    return items


def team_remove(index, locale="ca"):
    items = read_team(locale)
    if 0 <= index < len(items):
        gone = items.pop(index)
        write_team(items, locale)
        _team_gc(gone.get("photo", ""), items)
    return items


def team_reorder(order, locale="ca"):
    cur = read_team(locale)
    items = [cur[i] for i in order if 0 <= i < len(cur)]
    write_team(items, locale)
    return items


def read_settings():
    try:
        s = json.load(open(SETTINGS))
    except Exception:
        s = {}
    out = {}
    for k, v in DEFAULT_SETTINGS.items():
        val = s.get(k, v)
        if isinstance(v, bool):
            out[k] = bool(val)
        elif isinstance(v, (int, float)):
            try:
                out[k] = float(val)
            except (TypeError, ValueError):
                out[k] = v
        else:
            out[k] = str(val)
    out["drives"] = read_drives()
    return out

os.makedirs(PHOTOS, exist_ok=True)


# ---- section visibility (hide/show whole sections, per locale) ----
# Stored in assets/layout.json as { locale: { page: {"hidden":[keys]} } }.
# Sections are tagged in the HTML with data-section / data-section-label (+ optional data-loc).

def read_layout():
    try:
        d = json.load(open(LAYOUT_JSON))
    except Exception:
        d = {}
    for loc in ("ca", "us"):
        d.setdefault(loc, {})
    return d


def write_layout(d):
    json.dump(d, open(LAYOUT_JSON, "w"), indent=2)


def scan_sections(page):
    """Every <section data-section> on a page, in DOM order: [{key,label,loc}]."""
    path = os.path.join(SITE, page)
    if not os.path.exists(path):
        return []
    html = open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r'<section\b[^>]*\bdata-section="([^"]+)"[^>]*>', html):
        tag = m.group(0)
        key = m.group(1)
        label = re.search(r'data-section-label="([^"]*)"', tag)
        loc = re.search(r'data-loc="([^"]*)"', tag)
        out.append({
            "key": key,
            "label": html_unescape(label.group(1)) if label else key,
            "loc": loc.group(1) if loc else "",
        })
    return out


def _loc_matches(sec_loc, locale):
    # a section with no data-loc shows in both; otherwise it must include the locale
    return not sec_loc or locale in sec_loc.split()


def sections_for(page, locale):
    """DOM-ordered sections visible in `locale`, each flagged hidden per saved layout."""
    scanned = [s for s in scan_sections(page) if _loc_matches(s["loc"], locale)]
    hidden = set(read_layout().get(locale, {}).get(page, {}).get("hidden", []))
    return [{"key": s["key"], "label": s["label"], "hidden": s["key"] in hidden}
            for s in scanned]


def layout_set_hidden(page, locale, key, hidden):
    if page not in PAGES:
        raise ValueError("unknown page")
    keys = [s["key"] for s in scan_sections(page)]
    if key not in keys:
        raise ValueError("unknown section")
    d = read_layout()
    d.setdefault(locale, {})
    pc = d[locale].setdefault(page, {})
    cur = [k for k in pc.get("hidden", []) if k in keys]
    if hidden and key not in cur:
        cur.append(key)
    elif not hidden and key in cur:
        cur.remove(key)
    pc["hidden"] = cur
    write_layout(d)
    return sections_for(page, locale)


def safe_lib_path(name, drive="ca"):
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    p = os.path.join(lib_dir(drive), name)
    return p if os.path.isfile(p) and name.lower().endswith(IMG_EXT) else None


def safe_media_path(name, drive="ca"):
    """Like safe_lib_path but also allows video files (for the video picker)."""
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    p = os.path.join(lib_dir(drive), name)
    return p if os.path.isfile(p) and name.lower().endswith(IMG_EXT + VID_EXT) else None


VIDEOS = os.path.join(SITE, "assets", "videos")
os.makedirs(VIDEOS, exist_ok=True)


def apply_video(slot, fname, locale="ca", drive="ca"):
    """Transcode a library clip to a web-friendly, muted mp4 in assets/videos and
    register it on the slot in content.json (runtime override, both locales)."""
    src_path = safe_media_path(fname, drive)
    if not src_path or not fname.lower().endswith(VID_EXT):
        raise ValueError("unknown library video")
    slug = re.sub(r"[^a-z0-9-]", "", slot.lower())
    out_name = "slot-%s%s.mp4" % (slug, "-us" if locale == "us" else "")
    out_path = os.path.join(VIDEOS, out_name)
    # H.264/faststart, capped to 1280w, audio stripped (autoplay is muted anyway)
    cmd = ["ffmpeg", "-y", "-i", src_path,
           "-vf", "scale='min(1280,iw)':-2",
           "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
           "-crf", "24", "-preset", "veryfast", "-movflags", "+faststart",
           "-an", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise ValueError("video conversion failed: " + (r.stderr or "")[-300:])
    url = "assets/videos/%s?v=%d" % (out_name, int(time.time()))
    c = read_content()
    c[locale]["img"].setdefault(slot, {})["video"] = url
    write_content(c)
    return url


def remove_video(slot, locale="ca"):
    c = read_content()
    entry = c.get(locale, {}).get("img", {}).get(slot)
    if entry:
        entry.pop("video", None)
        write_content(c)
    return True


def scan_slots():
    slots = []
    for page in PAGES:
        path = os.path.join(SITE, page)
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        for m in re.finditer(r'<img[^>]*data-slot="([^"]+)"[^>]*>', html):
            tag = m.group(0)
            slot = m.group(1)
            src = re.search(r'src="([^"]*)"', tag)
            alt = re.search(r'alt="([^"]*)"', tag)
            # mobile source, if this img sits in a picture with a data-slot-src
            msrc = re.search(
                r'<source[^>]*data-slot-src="%s"[^>]*srcset="([^"]*)"' % re.escape(slot), html)
            dsrc = src.group(1) if src else None
            m_src = msrc.group(1) if msrc else None
            # a transparent data: seed (unset bg slot) reads as empty in the admin
            if dsrc and dsrc.startswith("data:"):
                dsrc = None
            if m_src and m_src.startswith("data:"):
                m_src = None
            slots.append({
                "slot": slot, "page": page, "kind": "img",
                "src": dsrc, "alt": alt.group(1) if alt else "",
                "mobile_src": m_src,
                "mobile_distinct": bool(m_src and m_src != dsrc),
            })
        for m in re.finditer(r'<div class="ph[^"]*"[^>]*data-slot="([^"]+)"', html):
            kind_m = re.search(
                r'data-slot="%s"[\s\S]{0,400}?<span class="ph__kind">([^<]*)' % re.escape(m.group(1)), html)
            slots.append({
                "slot": m.group(1), "page": page, "kind": "placeholder",
                "src": None, "alt": kind_m.group(1).strip() if kind_m else "",
            })
        # figure-based placeholders (e.g. FAQ pics): data-slot on the <figure>,
        # empty until a photo is applied (once filled it's caught by the <img> scan)
        for m in re.finditer(r'<figure[^>]*\bdata-slot="([^"]+)"[^>]*>([\s\S]*?)</figure>', html):
            slot, inner = m.group(1), m.group(2)
            if "<img" in inner:
                continue
            kind_m = re.search(r'ph__kind">([^<]*)', inner)
            slots.append({
                "slot": slot, "page": page, "kind": "placeholder",
                "src": None, "alt": kind_m.group(1).strip() if kind_m else "",
            })
    return slots


def apply_image(slot, fname, crop, viewport="desktop", locale="ca", drive="ca"):
    src_path = safe_lib_path(fname, drive)
    if not src_path:
        raise ValueError("unknown library file")
    mobile = viewport == "mobile"
    im = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    if crop:
        x, y, w, h = (int(crop[k]) for k in ("x", "y", "w", "h"))
        x = max(0, min(x, im.width - 1)); y = max(0, min(y, im.height - 1))
        w = max(16, min(w, im.width - x)); h = max(16, min(h, im.height - y))
        im = im.crop((x, y, x + w, y + h))
    im.thumbnail((1600, 1600))
    slug = re.sub(r"[^a-z0-9-]", "", slot.lower())
    us = locale == "us"
    out_name = "slot-%s%s%s.jpg" % (slug, "-us" if us else "", "-m" if mobile else "")
    im.save(os.path.join(PHOTOS, out_name), quality=85, optimize=True)
    new_src = "assets/photos/%s?v=%d" % (out_name, int(time.time()))

    if us:
        # US images are runtime overrides — never touch the base HTML
        c = read_content()
        entry = c["us"]["img"].setdefault(slot, {})
        entry["mobile" if mobile else "desktop"] = new_src
        entry.pop("video", None)   # picking a photo clears any video on this slot
        write_content(c)
        return new_src

    changed = False
    for page in PAGES:
        path = os.path.join(SITE, page)
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        n = 0

        if mobile:
            # update the <source data-slot-src="slot" ... srcset="..."> (mobile variant)
            def swap_srcset(m):
                return re.sub(r'srcset="[^"]*"', 'srcset="%s"' % new_src, m.group(0))
            html, n = re.subn(
                r'<source[^>]*data-slot-src="%s"[^>]*>' % re.escape(slot), swap_srcset, html)
        else:
            # update the desktop <img src>
            def swap_src(m):
                return re.sub(r'src="[^"]*"', 'src="%s"' % new_src, m.group(0))
            html, n = re.subn(
                r'<img[^>]*data-slot="%s"[^>]*>' % re.escape(slot), swap_src, html)
            if n == 0:
                # placeholder div → picture+img (keeps wrapper; alt from slot label)
                ph_re = (r'<div class="ph[^"]*"[^>]*data-slot="%s">\s*'
                         r'<div class="ph__tag">[\s\S]*?</div>\s*</div>' % re.escape(slot))
                repl = ('<picture data-slot-pic="%s"><source data-slot-src="%s" '
                        'media="(max-width: 60rem)" srcset="%s">'
                        '<img data-slot="%s" src="%s" alt="%s" loading="lazy" '
                        'style="width:100%%;height:100%%;object-fit:cover;display:block">'
                        '</picture>'
                        % (slot, slot, new_src, slot, new_src, slot.replace("-", " ")))
                html, n = re.subn(ph_re, repl, html)
            if n == 0:
                # figure-based placeholder (FAQ pics): swap its inner .ph for a
                # filling picture+img, keep the <figure> wrapper + its arch styling
                fig_re = (r'(<figure[^>]*\bdata-slot="%s"[^>]*>)\s*'
                          r'<div class="ph[\s\S]*?</div>\s*</div>\s*(</figure>)' % re.escape(slot))
                def fig_repl(m):
                    open_tag = m.group(1).replace(' aria-hidden="true"', '')
                    pic = ('<picture data-slot-pic="%s"><source data-slot-src="%s" '
                           'media="(max-width: 60rem)" srcset="%s">'
                           '<img data-slot="%s" src="%s" alt="%s" loading="lazy" '
                           'style="width:100%%;height:100%%;object-fit:cover;display:block">'
                           '</picture>'
                           % (slot, slot, new_src, slot, new_src, slot.replace("-", " ")))
                    return open_tag + pic + m.group(2)
                html, n = re.subn(fig_re, fig_repl, html)
        if n:
            open(path, "w", encoding="utf-8").write(html)
            changed = True
    if not changed:
        raise ValueError("slot not found in any page")
    remove_video(slot, "ca")   # picking a photo clears any video on this slot
    return new_src


# ---- link-in-bio (assets/linkinbio.json, served at /linkinbio) ----
LINKINBIO_JSON = os.path.join(SITE, "assets", "linkinbio.json")
LINKINBIO_DIR = os.path.join(SITE, "assets", "linkinbio")


def read_linkinbio():
    try:
        with open(LINKINBIO_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"profile": {"name": "", "tagline": "", "avatar": ""}, "socials": [], "links": []}


def write_linkinbio(data):
    prof = data.get("profile") or {}
    out = {
        "profile": {
            "name": str(prof.get("name", "")),
            "tagline": str(prof.get("tagline", "")),
            "avatar": str(prof.get("avatar", "")),
        },
        "socials": [{"type": str(s.get("type", "website")), "href": str(s.get("href", "")).strip()}
                    for s in (data.get("socials") or []) if str(s.get("href", "")).strip()],
        "links": [],
    }
    for i, l in enumerate(data.get("links") or []):
        title = str(l.get("title", "")).strip()
        href = str(l.get("href", "")).strip()
        if not title and not href:
            continue
        out["links"].append({
            "id": str(l.get("id") or ("l%d" % (i + 1))),
            "title": title,
            "href": href,
            "thumb": str(l.get("thumb", "")),
            "active": bool(l.get("active", True)),
        })
    os.makedirs(os.path.dirname(LINKINBIO_JSON), exist_ok=True)
    tmp = LINKINBIO_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LINKINBIO_JSON)
    return out


def save_linkinbio_thumb(dataurl):
    import base64
    m = re.match(r"data:image/[\w.+-]+;base64,(.+)$", dataurl or "", re.S)
    if not m:
        raise ValueError("Unsupported image data.")
    raw = base64.b64decode(m.group(1))
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    if s > 240:
        im = im.resize((240, 240))
    os.makedirs(LINKINBIO_DIR, exist_ok=True)
    fn = "up-%d.jpg" % int(time.time() * 1000)
    im.save(os.path.join(LINKINBIO_DIR, fn), quality=82)
    return "/assets/linkinbio/%s" % fn


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # static-file responses must never be browser-cached, so admin edits
        # (crown, team, text) show on a normal refresh instead of a hard reload
        self.send_header("Cache-Control", "no-store, must-revalidate")
        sc = getattr(self, "_pending_setcookie", None)
        if sc:
            self.send_header("Set-Cookie", sc)
            self._pending_setcookie = None
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    _VID_CTYPE = {".mp4": "video/mp4", ".webm": "video/webm",
                  ".m4v": "video/x-m4v", ".mov": "video/quicktime"}

    def _serve_media(self, path):
        # HTTP Range support (SimpleHTTPRequestHandler has none) — iOS Safari needs 206 for <video>
        ctype = self._VID_CTYPE.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            try:
                s, e = (rng[6:].split("-") + [""])[:2]
                start = int(s) if s else 0
                end = int(e) if e else size - 1
            except ValueError:
                start, end = 0, size - 1
            start = max(0, start); end = min(end, size - 1)
            if start > end:
                start, end = 0, size - 1
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Length", str(length))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(path, "rb") as f:
                self.wfile.write(f.read())

    def _file(self, path, ctype):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- auth gate --------------------------------------------------------
    def _cookie(self, name):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            c = SimpleCookie(raw)
            return c[name].value if name in c else None
        except Exception:
            return None

    def _is_public(self):
        h = self.headers.get("Host", "").split(":")[0]
        return h == auth.RP_ID or h == "www." + auth.RP_ID

    def _secure_flag(self):
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https" or self._is_public()

    def _set_session(self, level):
        parts = ["haus_sess=" + auth.make_session(level), "Path=/", "HttpOnly",
                 "SameSite=Lax", "Max-Age=43200"]
        if self._secure_flag():
            parts.append("Secure")
        self._pending_setcookie = "; ".join(parts)

    def _clear_session(self):
        self._pending_setcookie = "haus_sess=; Path=/; HttpOnly; Max-Age=0"

    def _level(self):
        return auth.session_level(self._cookie("haus_sess"))

    def _send_login(self):
        body = auth.LOGIN_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _gate_ok(self, p):
        if p.startswith("/api/auth/"):
            return True
        if self._level() == "full":
            return True
        if p.startswith("/api/"):
            self._json({"error": "auth required"}, 401)
        else:
            self._send_login()
        return False

    def _handle_auth(self, p):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad request"}, 400)
        try:
            if p == "/api/auth/set-password":
                if auth.password_set():
                    return self._json({"error": "Password already set."}, 409)
                auth.set_password(data.get("password", ""))
                self._set_session("full")
                return self._json({"ok": True})
            if p == "/api/auth/login":
                if not auth.verify_password(data.get("password", "")):
                    return self._json({"error": "Incorrect password."}, 401)
                if auth.has_passkey() and self._is_public():
                    self._set_session("pw")
                    return self._json({"ok": True, "passkey_required": True})
                self._set_session("full")
                return self._json({"ok": True})
            if p == "/api/auth/logout":
                self._clear_session()
                return self._json({"ok": True})
            if p.startswith("/api/auth/passkey/") and not auth.webauthn_available():
                return self._json({"error": "Passkeys are unavailable on the server."}, 500)
            # passwordless one-tap sign-in — the passkey itself proves identity
            if p == "/api/auth/passkey/login-begin":
                if not auth.has_passkey():
                    return self._json({"error": "No passkey registered yet."}, 400)
                tok, options = auth.auth_begin()
                return self._json({"ok": True, "token": tok, "options": options})
            if p == "/api/auth/passkey/login-finish":
                auth.auth_finish(data.get("token", ""), json.dumps(data.get("credential")))
                self._set_session("full")
                return self._json({"ok": True})
            # enrolling or removing passkeys requires an authenticated session
            if self._level() != "full":
                return self._json({"error": "auth required"}, 401)
            if p == "/api/auth/passkey/register-begin":
                tok, options = auth.reg_begin()
                return self._json({"ok": True, "token": tok, "options": options})
            if p == "/api/auth/passkey/register-finish":
                auth.reg_finish(data.get("token", ""), json.dumps(data.get("credential")))
                return self._json({"ok": True, "passkeys": len(auth.credentials())})
            if p == "/api/auth/passkey/remove":
                auth.remove_passkeys()
                return self._json({"ok": True, "passkeys": 0})
            return self._json({"error": "not found"}, 404)
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            return self._json({"error": "Auth error: %s" % e}, 500)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/auth/status":
            return self._json({
                "password_set": auth.password_set(),
                "authed": self._level() == "full",
                "passkeys": len(auth.credentials()),
                "public": self._is_public(),
                "webauthn": auth.webauthn_available(),
            })
        if not self._gate_ok(p):
            return
        if p in ("/admin", "/admin/"):
            return self._file(ADMIN_HTML, "text/html; charset=utf-8")
        if p == "/api/messages":
            return self._json(read_messages())
        if p == "/api/slots":
            return self._json(scan_slots())
        if p == "/api/settings":
            return self._json(read_settings())
        if p == "/api/drives":
            return self._json(read_drives())
        if p == "/api/gallery":
            loc = (self.path.split("locale=")[1].split("&")[0]
                   if "locale=" in self.path else "ca")
            return self._json(read_gallery(loc))
        if p == "/api/beforeafter":
            return self._json(read_ba())
        if p == "/api/team":
            loc = (self.path.split("locale=")[1].split("&")[0]
                   if "locale=" in self.path else "ca")
            return self._json(read_team(loc))
        if p == "/api/texts":
            return self._json(scan_texts())
        if p == "/api/content":
            return self._json(read_content())
        if p == "/api/linkinbio":
            return self._json(read_linkinbio())
        if p == "/api/sections":
            q = parse_qs(urlsplit(self.path).query)
            page = (q.get("page") or ["index.html"])[0]
            loc = (q.get("locale") or ["ca"])[0]
            if page not in PAGES:
                return self._json({"error": "unknown page"}, 400)
            return self._json(sections_for(page, loc))
        if p == "/api/library":
            drive = (self.path.split("drive=")[1].split("&")[0]
                     if "drive=" in self.path else "ca")
            out = []
            for f in sorted(os.listdir(lib_dir(drive))):
                if f.lower().endswith(VID_EXT):
                    out.append({"file": f, "video": True})
                    continue
                fp = safe_lib_path(f, drive)
                if not fp:
                    continue
                try:
                    with Image.open(fp) as im:
                        im = ImageOps.exif_transpose(im)
                        out.append({"file": f, "w": im.width, "h": im.height})
                except Exception:
                    pass
            return self._json(out)
        if p == "/api/sync-status":
            drive = (self.path.split("drive=")[1].split("&")[0]
                     if "drive=" in self.path else "ca")
            st = SYNC_STATUS.get(drive, {"running": False})
            st = dict(st)
            st["library_now"] = len([x for x in os.listdir(lib_dir(drive))
                                     if x.lower().endswith(IMG_EXT)])
            return self._json(st)
        if p.startswith("/api/doc/"):
            # Confidential documents (preview/haus/docs). nginx 404s /docs/ on the
            # public site, so the admin Documents viewer reads them through here —
            # behind the same session gate as every other /api/ route above.
            name = os.path.basename(unquote(p[len("/api/doc/"):]))
            if not name or name.startswith("."):
                return self._json({"error": "not found"}, 404)
            ext = os.path.splitext(name)[1].lower()
            ctypes = {".pdf": "application/pdf",
                      ".html": "text/html; charset=utf-8"}
            if ext not in ctypes:
                return self._json({"error": "not found"}, 404)
            fp = os.path.join(DOCS_DIR, name)
            if os.path.dirname(os.path.abspath(fp)) != os.path.abspath(DOCS_DIR) \
                    or not os.path.isfile(fp):
                return self._json({"error": "not found"}, 404)
            return self._file(fp, ctypes[ext])
        if p.startswith("/api/thumb/"):
            rest = p[len("/api/thumb/"):].split("/")
            drive = rest[0] if len(rest) > 1 and rest[0] in drive_ids() else "ca"
            name = os.path.basename(unquote(rest[-1]))
            fp = safe_media_path(name, drive)
            if not fp:
                return self._json({"error": "not found"}, 404)
            tp = os.path.join(thumbs_dir(drive), name + ".jpg")
            if not os.path.exists(tp) or os.path.getmtime(tp) < os.path.getmtime(fp):
                if name.lower().endswith(VID_EXT):
                    # grab a representative frame ~1s in for the video's thumbnail
                    subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", fp,
                                    "-frames:v", "1", "-vf", "scale=360:-2", tp],
                                   capture_output=True)
                    if not os.path.exists(tp):   # clip shorter than 1s → first frame
                        subprocess.run(["ffmpeg", "-y", "-i", fp, "-frames:v", "1",
                                        "-vf", "scale=360:-2", tp], capture_output=True)
                else:
                    im = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
                    im.thumbnail((360, 360))
                    im.save(tp, quality=78)
            if not os.path.exists(tp):
                return self._json({"error": "thumb failed"}, 500)
            return self._file(tp, "image/jpeg")
        if p.startswith("/api/full/"):
            rest = p[len("/api/full/"):].split("/")
            drive = rest[0] if len(rest) > 1 and rest[0] in drive_ids() else "ca"
            name = os.path.basename(unquote(rest[-1]))
            fp = safe_lib_path(name, drive)
            if not fp:
                return self._json({"error": "not found"}, 404)
            return self._file(fp, "image/jpeg")
        if p.startswith("/assets/videos/") and p.lower().endswith(tuple(self._VID_CTYPE)):
            fp = os.path.join(VIDEOS, os.path.basename(unquote(p)))
            if os.path.isfile(fp):
                return self._serve_media(fp)
        return super().do_GET()

    def do_POST(self):
        p = self.path.split("?")[0]
        if p.startswith("/api/auth/"):
            return self._handle_auth(p)
        if self._level() != "full":
            return self._json({"error": "auth required"}, 401)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)
        if p == "/api/apply":
            try:
                vp = data.get("viewport", "desktop")
                loc = data.get("locale", "ca")
                drive = data.get("drive", "ca")
                new_src = apply_image(data["slot"], data["file"], data.get("crop"), vp, loc, drive)
                return self._json({"ok": True, "src": new_src, "viewport": vp, "locale": loc})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/apply-video":
            try:
                slot = data["slot"]
                loc = data.get("locale", "ca")
                if data.get("remove"):
                    remove_video(slot, loc)
                    return self._json({"ok": True, "removed": True})
                url = apply_video(slot, data["file"], loc, data.get("drive", "ca"))
                return self._json({"ok": True, "video": url, "locale": loc})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/text":
            try:
                ok = set_text(data["id"], data["value"], data.get("locale", "ca"))
                return self._json({"ok": ok})
            except KeyError as e:
                return self._json({"error": "missing " + str(e)}, 400)
        if p == "/api/contact":
            # per-locale phone/email override (blank clears → falls back to the built-in default)
            loc = data.get("locale", "ca")
            if loc not in ("ca", "us"):
                return self._json({"error": "unknown locale"}, 400)
            c = read_content()
            for f in ("phone", "email"):
                if f in data:
                    v = str(data[f]).strip()
                    if v:
                        c[loc]["contact"][f] = v
                    else:
                        c[loc]["contact"].pop(f, None)
            write_content(c)
            return self._json({"ok": True, "contact": c[loc]["contact"]})
        if p == "/api/settings":
            s = read_settings()
            for k, dv in DEFAULT_SETTINGS.items():
                if k in data:
                    if isinstance(dv, bool):
                        s[k] = bool(data[k])
                    elif isinstance(dv, (int, float)):
                        try:
                            s[k] = max(0.0, min(1.0, float(data[k]))) if k == "queensScrim" else float(data[k])
                        except (TypeError, ValueError):
                            pass
                    else:
                        s[k] = str(data[k])
            json.dump(s, open(SETTINGS, "w"), indent=2)
            return self._json({"ok": True, "settings": s})
        if p == "/api/gallery":
            act = data.get("action")
            loc = data.get("locale", "ca")
            drive = data.get("drive", "ca")
            try:
                if act == "add":
                    items = gallery_add(data["file"], data.get("crop"), loc, drive)
                elif act == "remove":
                    items = read_gallery(loc)
                    idx = int(data["index"])
                    if 0 <= idx < len(items):
                        gone = items.pop(idx)
                        write_gallery(items, loc)
                        f = gone.get("src", "").split("?")[0]
                        if "/gallery-" in f:
                            fp = os.path.join(SITE, f)
                            if os.path.exists(fp) and not any(f in it.get("src", "") for it in items):
                                os.remove(fp)
                elif act == "reorder":
                    order = data["order"]
                    cur = read_gallery(loc)
                    items = [cur[i] for i in order if 0 <= i < len(cur)]
                    write_gallery(items, loc)
                elif act == "alt":
                    items = read_gallery(loc)
                    idx = int(data["index"])
                    if 0 <= idx < len(items):
                        items[idx]["alt"] = str(data.get("alt", ""))
                        write_gallery(items, loc)
                else:
                    return self._json({"error": "unknown action"}, 400)
                return self._json({"ok": True, "gallery": items})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/team":
            act = data.get("action")
            loc = data.get("locale", "ca")
            drive = data.get("drive", "ca")
            try:
                if act == "add":
                    items = team_add(data.get("fields", {}), loc)
                elif act == "update":
                    items = team_update(int(data["index"]), data.get("fields", {}), loc)
                elif act == "photo":
                    items = team_set_photo(int(data["index"]), data["file"],
                                           data.get("crop"), loc, drive)
                elif act == "remove":
                    items = team_remove(int(data["index"]), loc)
                elif act == "reorder":
                    items = team_reorder(data["order"], loc)
                else:
                    return self._json({"error": "unknown action"}, 400)
                return self._json({"ok": True, "team": items})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/beforeafter":
            act = data.get("action")
            drive = data.get("drive", "ca")
            try:
                if act == "add":
                    items = ba_add(data["before"], data["after"], drive)
                elif act == "remove":
                    items = read_ba()
                    idx = int(data["index"])
                    if 0 <= idx < len(items):
                        gone = items.pop(idx)
                        write_ba(items)
                        for k in ("before", "after"):
                            f = gone.get(k, "").split("?")[0]
                            fp = os.path.join(SITE, f)
                            if "/ba-" in f and os.path.exists(fp):
                                os.remove(fp)
                elif act == "reorder":
                    order = data["order"]
                    cur = read_ba()
                    items = [cur[i] for i in order if 0 <= i < len(cur)]
                    write_ba(items)
                else:
                    return self._json({"error": "unknown action"}, 400)
                return self._json({"ok": True, "beforeafter": items})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/drives":
            act = data.get("action")
            drives = read_drives()
            if act == "add":
                name = str(data.get("name") or "").strip()
                if not name:
                    return self._json({"error": "name required"}, 400)
                did = _slug_drive(name, {d["id"] for d in drives})
                drives.append({"id": did, "name": name,
                               "url": str(data.get("url") or "").strip(), "builtin": False})
                write_drives(drives)
                return self._json({"ok": True, "id": did, "drives": read_drives()})
            if act == "update":
                did = data.get("id")
                for d in drives:
                    if d["id"] == did:
                        if "name" in data and not d["builtin"]:
                            d["name"] = str(data["name"]).strip() or d["name"]
                        if "url" in data:
                            d["url"] = str(data["url"]).strip()
                        write_drives(drives)
                        return self._json({"ok": True, "drives": read_drives()})
                return self._json({"error": "unknown drive"}, 400)
            if act == "remove":
                did = data.get("id")
                if did in DRIVES:
                    return self._json({"error": "built-in drives can't be removed"}, 400)
                write_drives([d for d in drives if d["id"] != did])
                return self._json({"ok": True, "drives": read_drives()})
            return self._json({"error": "unknown action"}, 400)
        if p == "/api/sync":
            # kick off a per-drive sync in the background; UI polls /api/sync-status
            drive = data.get("drive", "ca")
            if drive not in drive_ids():
                return self._json({"error": "unknown drive"}, 400)
            url = drive_url(drive)
            if not url:
                return self._json({"ok": False,
                                   "note": "No Google Drive set for this one — add the link and save first."})
            with SYNC_LOCK:
                cur = SYNC_STATUS.get(drive)
                if cur and cur.get("running"):
                    return self._json({"ok": True, "started": False, "running": True,
                                       "note": "Already syncing this drive…"})
                t = threading.Thread(target=run_sync, args=(drive, url), daemon=True)
                t.start()
            return self._json({"ok": True, "started": True, "drive": drive})
        if p == "/api/layout":
            try:
                if data.get("action") != "hide":
                    return self._json({"error": "unknown action"}, 400)
                items = layout_set_hidden(data.get("page", "index.html"),
                                          data.get("locale", "ca"),
                                          data["key"], bool(data["hidden"]))
                return self._json({"ok": True, "layout": items})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/linkinbio":
            try:
                return self._json({"ok": True, "data": write_linkinbio(data)})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        if p == "/api/linkinbio/thumb":
            try:
                return self._json({"ok": True, "path": save_linkinbio_thumb(data.get("dataurl", ""))})
            except (KeyError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
        return self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    # host/port from argv ([host] [port], any order) or env; defaults localhost:8877.
    # Bind 0.0.0.0 to serve the site + /admin + /api over the tailnet, e.g.:
    #   python3 haus_admin_server.py 0.0.0.0 8790
    host = os.environ.get("HAUS_ADMIN_HOST", "127.0.0.1")
    port = int(os.environ.get("HAUS_ADMIN_PORT", "8877"))
    for a in sys.argv[1:]:
        if a.isdigit():
            port = int(a)
        else:
            host = a
    print("Haus admin serving %s -> http://%s:%d/admin" % (SITE, host, port), flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
