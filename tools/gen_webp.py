#!/usr/bin/env python3
"""Generate a .webp twin next to every site photo, for nginx Accept-negotiation.

foo.jpg  ->  foo.jpg.webp

nginx serves the .webp automatically to browsers that send `Accept: image/webp`
and falls back to the original otherwise (see deploy/nginx.conf), so no HTML,
JSON, or admin path ever changes. Re-run after adding photos:

    python3 tools/gen_webp.py

Only writes a twin when it is actually smaller than the original.
"""
import os, sys
from PIL import Image, ImageOps

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "preview", "haus")
QUALITY = 80
SRC_EXT = (".jpg", ".jpeg", ".png")

made = skipped = fresh = 0
before = after = 0

for dirpath, dirnames, filenames in os.walk(os.path.join(SITE, "assets")):
    for fn in filenames:
        if not fn.lower().endswith(SRC_EXT):
            continue
        src = os.path.join(dirpath, fn)
        dst = src + ".webp"
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            fresh += 1
            before += os.path.getsize(src)
            after += os.path.getsize(dst)
            continue
        try:
            im = Image.open(src)
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
            tmp = dst + ".tmp"
            im.save(tmp, "WEBP", quality=QUALITY, method=6)
            b, a = os.path.getsize(src), os.path.getsize(tmp)
            if a < b:
                os.replace(tmp, dst)
                os.chmod(dst, 0o644)
                made += 1
                before += b
                after += a
            else:
                os.remove(tmp)
                if os.path.exists(dst):
                    os.remove(dst)      # stale twin that no longer helps
                skipped += 1
                before += b
                after += b
        except Exception as e:
            print("SKIP %s (%s)" % (src, e), file=sys.stderr)
            skipped += 1

print("webp twins: %d created, %d already current, %d skipped (no win)"
      % (made, fresh, skipped))
if before:
    print("served weight to webp browsers: %.1f MB -> %.1f MB (%.0f%% smaller)"
          % (before / 1048576, after / 1048576, 100.0 * (before - after) / before))
