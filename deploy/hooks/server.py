#!/usr/bin/env python3
"""Beauty Extension Haus — booking webhook receiver.

Turns "an appointment was actually booked" into a Plausible event. Both booking
systems live off-site (Square's iframe for Barrie, Mangomint's overlay for
Sarasota), so the browser can never see a completed booking — the only signal is
a server-to-server webhook.

  POST /api/hook/square      Square webhooks. Verified with the HMAC-SHA256
                             signature Square sends (SQUARE_SIGNATURE_KEY).
  POST /api/hook/mangomint   Mangomint webhooks. Mangomint support configures
                             the endpoint for you and their payload is not
                             publicly documented, so this one is verified with a
                             shared secret (MANGOMINT_SECRET) sent as ?key=,
                             X-Webhook-Secret, or Authorization: Bearer.
  GET  /health               -> "ok" (compose healthcheck)

EVERY accepted delivery is appended verbatim to $HOOKS_FILE, whether or not it
maps to an event. That log is the point: it's how the Mangomint payload gets
learned, and how a mis-mapped Square event can be replayed later.

No customer data is ever forwarded to Plausible — only the event name, a status
and a couple of coarse counters. Stdlib only, same as the contact receiver.
"""
import base64, hashlib, hmac, json, os, threading, time, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

HOOKS_FILE = os.environ.get("HOOKS_FILE", "/data/hooks.jsonl")
MAX_BODY = 256 * 1024

SQUARE_KEY = os.environ.get("SQUARE_SIGNATURE_KEY", "")
SQUARE_URL = os.environ.get("SQUARE_NOTIFICATION_URL",
                            "https://beautyextensionhaus.com/api/hook/square")
MANGOMINT_SECRET = os.environ.get("MANGOMINT_SECRET", "")

PLAUSIBLE_ENDPOINT = os.environ.get("PLAUSIBLE_ENDPOINT", "http://plausible:8000/api/event")
PLAUSIBLE_DOMAIN = os.environ.get("PLAUSIBLE_DOMAIN", "beautyextensionhaus.com")
# Virtual URL: these events have no page of their own, and custom events don't
# count towards Top Pages, so a clearly-fake path is the honest choice.
PLAUSIBLE_URL = os.environ.get("PLAUSIBLE_URL", "https://beautyextensionhaus.com/booking/confirmed")
# Plausible needs a User-Agent (it fingerprints on it). Verified that an honest
# non-browser string is accepted and stored — no need to fake a browser.
PLAUSIBLE_UA = os.environ.get("PLAUSIBLE_UA", "BeautyHaus-Hooks/1.0")

_FILE_LOCK = threading.Lock()
_SEEN = deque(maxlen=1000)          # recent delivery ids, for retry de-duplication
_SEEN_SET = set()
_SEEN_LOCK = threading.Lock()

CANCELLED = ("CANCELLED", "DECLINED", "NO_SHOW")


def _seen(key):
    """True if this delivery id was already handled (webhooks retry on timeout)."""
    if not key:
        return False
    with _SEEN_LOCK:
        if key in _SEEN_SET:
            return True
        if len(_SEEN) == _SEEN.maxlen:
            _SEEN_SET.discard(_SEEN[0])
        _SEEN.append(key)
        _SEEN_SET.add(key)
        return False


def _seed_seen():
    """Re-arm de-duplication across restarts from the tail of the log."""
    try:
        with open(HOOKS_FILE, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 256 * 1024))
            lines = f.read().decode("utf-8", "replace").splitlines()[-500:]
    except OSError:
        return
    for line in lines:
        try:
            _seen(json.loads(line).get("delivery_id"))
        except Exception:
            pass


def _log(record):
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _FILE_LOCK:
        os.makedirs(os.path.dirname(HOOKS_FILE) or ".", exist_ok=True)
        with open(HOOKS_FILE, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())


def _send_plausible(name, props):
    """Fire-and-forget custom event. Never blocks the webhook acknowledgement."""
    def send():
        body = json.dumps({
            "name": name,
            "url": PLAUSIBLE_URL,
            "domain": PLAUSIBLE_DOMAIN,
            "props": {k: str(v)[:300] for k, v in props.items() if v not in (None, "")},
        }).encode()
        req = urllib.request.Request(
            PLAUSIBLE_ENDPOINT, data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": PLAUSIBLE_UA})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                if r.status >= 300:
                    print("hooks: plausible said %s" % r.status, flush=True)
        except Exception as e:
            print("hooks: plausible send failed:", e, flush=True)

    threading.Thread(target=send, daemon=True).start()


# ---- Square ---------------------------------------------------------------

def _square_ok(raw, signature):
    """Square signs base64(HMAC-SHA256(key, notification_url + body))."""
    if not SQUARE_KEY or not signature:
        return False
    mac = hmac.new(SQUARE_KEY.encode(), SQUARE_URL.encode() + raw, hashlib.sha256)
    return hmac.compare_digest(base64.b64encode(mac.digest()).decode(), signature)


def _square_event(payload):
    """(event_name, props) for a Square booking webhook, or (None, props)."""
    kind = (payload.get("type") or "").lower()
    booking = (((payload.get("data") or {}).get("object") or {}).get("booking") or {})
    status = (booking.get("status") or "").upper()
    props = {
        "system": "square",
        "type": kind,
        "status": status,
        "location_id": booking.get("location_id"),
        "services": len(booking.get("appointment_segments") or []) or None,
    }
    if not kind.startswith("booking."):
        return None, props                      # payments/orders: logged, not sent
    if any(c in status for c in CANCELLED):
        return "Booking Cancelled -ca", props
    if kind == "booking.created":
        return "Booking Confirmed -ca", props
    return None, props                          # plain updates: logged, not sent


# ---- Mangomint ------------------------------------------------------------

def _mangomint_ok(path_query, headers):
    if not MANGOMINT_SECRET:
        return False
    given = (parse_qs(path_query).get("key", [""])[0]
             or headers.get("X-Webhook-Secret", "")
             or headers.get("Authorization", "").removeprefix("Bearer ").strip())
    return bool(given) and hmac.compare_digest(given, MANGOMINT_SECRET)


def _mangomint_event(payload):
    """Mangomint's payload is undocumented, so match on whatever type-ish field
    it carries and stay conservative: anything unrecognised is logged only, and
    the log is what we use to tighten this once real deliveries land."""
    kind = ""
    for key in ("type", "event", "eventType", "event_type", "name", "topic"):
        v = payload.get(key)
        if isinstance(v, str) and v:
            kind = v.lower()
            break
    props = {"system": "mangomint", "type": kind or "unknown",
             "status": payload.get("status") or payload.get("appointmentStatus")}
    if not kind:
        return None, props
    if "cancel" in kind:
        return "Booking Cancelled -us", props
    if ("appointment" in kind or "booking" in kind) and ("book" in kind or "creat" in kind):
        return "Booking Confirmed -us", props
    if "sale" in kind and ("complet" in kind or "creat" in kind):
        return "Sale -us", props
    return None, props


class Handler(BaseHTTPRequestHandler):
    server_version = "haus-hooks"

    def log_message(self, *a):
        pass

    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlsplit(self.path).path == "/health":
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self._reply(404, {"ok": False})

    def do_POST(self):
        parts = urlsplit(self.path)
        source = parts.path.rsplit("/", 1)[-1]
        if source not in ("square", "mangomint"):
            return self._reply(404, {"ok": False})

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            return self._reply(400, {"ok": False})
        raw = self.rfile.read(length)

        if source == "square":
            ok = _square_ok(raw, self.headers.get("x-square-hmacsha256-signature", ""))
        else:
            ok = _mangomint_ok(parts.query, self.headers)
        if not ok:
            print("hooks: rejected unverified %s delivery" % source, flush=True)
            return self._reply(401, {"ok": False})

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._reply(400, {"ok": False})
        if not isinstance(payload, dict):
            return self._reply(400, {"ok": False})

        delivery_id = (payload.get("event_id") or payload.get("id")
                       or self.headers.get("X-Delivery-Id") or "")
        if _seen(delivery_id):
            return self._reply(200, {"ok": True, "duplicate": True})

        if source == "square":
            name, props = _square_event(payload)
        else:
            name, props = _mangomint_event(payload)

        try:
            _log({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "source": source, "delivery_id": delivery_id,
                  "event": name, "props": props, "payload": payload})
        except Exception as e:
            print("hooks: log failed:", e, flush=True)

        if name:
            _send_plausible(name, props)
        return self._reply(200, {"ok": True, "event": name})


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    _seed_seen()
    print("hooks receiver on %s:%d -> %s (square key: %s, mangomint secret: %s)" % (
        host, port, HOOKS_FILE,
        "set" if SQUARE_KEY else "MISSING", "set" if MANGOMINT_SECRET else "MISSING"), flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
