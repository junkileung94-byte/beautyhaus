#!/usr/bin/env python3
"""Robust Google Drive folder sync for the Haus media library.

gdown's folder download silently truncates / rate-flakes on large public
folders. This enumerates every file in the folder tree (via gdown's parser),
then downloads each MISSING file individually by ID with retries — so a big
folder actually lands completely. Idempotent: already-present files are skipped.

Usage: haus_drive_sync.py [FOLDER_ID_OR_URL] [DEST_DIR]
Prints a JSON summary on the last line.
"""
import json
import os
import re
import sys
import time

import requests
from gdown.download_folder import _download_and_parse_google_drive_link
import gdown

# HEIC (iPhone) → JPG conversion, so browsers and the server can use the photos
try:
    from PIL import Image, ImageOps
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HEIC_OK = True
except Exception:
    _HEIC_OK = False


def convert_heic(path):
    """Convert a .heic/.heif file to a sibling .jpg; return the new path (or original)."""
    if not _HEIC_OK or not path.lower().endswith((".heic", ".heif")):
        return path
    try:
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        out = os.path.splitext(path)[0] + ".jpg"
        im.save(out, quality=88, optimize=True)
        os.remove(path)
        return out
    except Exception:
        return path

IMG_VID_EXT = (".jpg", ".jpeg", ".png", ".webp", ".mov", ".mp4", ".heic")


def folder_id(s):
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", s)
    return m.group(1) if m else s


def _enumerate_once(fid):
    sess = requests.session()
    root = _download_and_parse_google_drive_link(sess, fid, quiet=True)
    out = []

    def walk(node):
        for c in node.children:
            if c.is_folder():
                walk(c)
            else:
                out.append((c.id, c.name))

    walk(root)
    return out


def enumerate_folder(fid):
    """Google's folder-listing endpoint is rate-limited and often returns a
    PARTIAL list under load. Retry a few times and keep the largest result."""
    best = []
    for attempt in range(5):
        try:
            got = _enumerate_once(fid)
        except Exception:
            got = []
        if len(got) > len(best):
            best = got
        # if two consecutive reads agree and are non-trivial, trust it
        if len(got) == len(best) and len(best) > 0 and attempt >= 1:
            # one more confirming read; if it doesn't grow, stop
            try:
                again = _enumerate_once(fid)
            except Exception:
                again = []
            if len(again) > len(best):
                best = again
                continue
            break
        time.sleep(1.2 * (attempt + 1))
    return best


def unique_name(name, taken):
    """Drive allows duplicate names; keep both by suffixing the 2nd+ with -N."""
    if name not in taken:
        return name
    stem, ext = os.path.splitext(name)
    i = 2
    while f"{stem}-{i}{ext}" in taken:
        i += 1
    return f"{stem}-{i}{ext}"


IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic")


def download_public(gid, path, sess):
    """Fetch a public Drive file. For images, use the googleusercontent CDN
    (lh3.googleusercontent.com/d/<id>=s0 → full-res, no rate limit). Fall back
    to gdown for anything the CDN won't serve (e.g. video)."""
    is_img = path.lower().endswith(IMG_EXT)
    if is_img:
        for url in ("https://lh3.googleusercontent.com/d/%s=s0" % gid,
                    "https://drive.google.com/thumbnail?id=%s&sz=w2400" % gid):
            try:
                r = sess.get(url, timeout=60, stream=True)
                ctype = r.headers.get("Content-Type", "")
                if r.status_code == 200 and ctype.startswith("image/"):
                    with open(path, "wb") as f:
                        for chunk in r.iter_content(65536):
                            f.write(chunk)
                    if os.path.getsize(path) > 1024:
                        return True
                    os.remove(path)
            except Exception:
                pass
    # fallback (videos, or CDN miss)
    try:
        r = gdown.download(id=gid, output=path, quiet=True)
        return bool(r) and os.path.exists(path) and os.path.getsize(path) > 0
    except Exception:
        return False


def sync(fid, dest, progress=None):
    os.makedirs(dest, exist_ok=True)
    files = enumerate_folder(fid)
    existing = set(os.listdir(dest))
    taken = set(existing)
    sess = requests.session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    got, skipped, failed = 0, 0, []
    total = len(files)
    for idx, (gid, name) in enumerate(files):
        if not name.lower().endswith(IMG_VID_EXT):
            skipped += 1
            continue
        if name in existing:  # already have this exact name
            skipped += 1
            continue
        target = unique_name(name, taken)
        taken.add(target)
        path = os.path.join(dest, target)
        ok = False
        for attempt in range(3):
            if download_public(gid, path, sess):
                ok = True
                break
            time.sleep(0.8 * (attempt + 1))
        if ok:
            convert_heic(path)  # iPhone HEIC → JPG so it's browser-usable
            got += 1
        else:
            failed.append(name)
            if os.path.exists(path) and os.path.getsize(path) == 0:
                os.remove(path)
        if progress:
            progress(idx + 1, total, got, len(failed))
    # also convert any HEIC already sitting in the folder from earlier syncs
    for f in list(os.listdir(dest)):
        if f.lower().endswith((".heic", ".heif")):
            convert_heic(os.path.join(dest, f))
    return {
        "drive_total": total,
        "downloaded": got,
        "skipped_existing_or_nonmedia": skipped,
        "failed": len(failed),
        "failed_names": failed[:40],
        "library_now": len([f for f in os.listdir(dest)
                            if f.lower().endswith(IMG_VID_EXT)]),
    }


if __name__ == "__main__":
    fid = folder_id(sys.argv[1]) if len(sys.argv) > 1 else \
        "1nTIbsLNa0Gt1jgB1-oN5L2yM9aQt11UR"
    dest = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "haus-media-library")

    def prog(done, total, got, failed):
        if done % 10 == 0 or done == total:
            print(f"[{done}/{total}] downloaded={got} failed={failed}",
                  file=sys.stderr, flush=True)

    result = sync(fid, dest, prog)
    print(json.dumps(result))
