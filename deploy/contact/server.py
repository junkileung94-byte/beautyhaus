#!/usr/bin/env python3
"""Beauty Extension Haus — public contact-form receiver.

Replaces the old Square-hosted (Square Online / Weebly) contact iframe. The
static site POSTs the form to /api/message; nginx (`web`) proxies that one path
to this service on the compose network. Nothing else here is public.

  POST /api/message   {name,email,phone,message, company?(honeypot)}
                      -> append a line to $MESSAGES_FILE (default /data/messages.jsonl)
                      -> optionally email a notification if SMTP_* env is set
  GET  /health        -> "ok" (compose healthcheck)

Stdlib only (no pip deps) so the image stays tiny. Read the stored messages in
the admin "Messages" tab (haus_admin_server.py GET /api/messages over the same
/data mount, read-only).
"""
import json, os, re, smtplib, threading, time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

MESSAGES_FILE = os.environ.get("MESSAGES_FILE", "/data/messages.jsonl")
MAX_BODY = 32 * 1024            # 32 KB — a contact message is never bigger
RL_WINDOW = 600                # seconds
RL_MAX = 5                     # max submissions per IP per window
RL_MIN_GAP = 2                 # min seconds between two submissions from one IP
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_LIMITS = {}                   # ip -> [timestamps]
_LIM_LOCK = threading.Lock()
_FILE_LOCK = threading.Lock()


def _rate_ok(ip, now):
    """True if this IP may submit now; records the hit when allowed."""
    with _LIM_LOCK:
        hits = [t for t in _LIMITS.get(ip, []) if now - t < RL_WINDOW]
        if hits and now - hits[-1] < RL_MIN_GAP:
            return False
        if len(hits) >= RL_MAX:
            _LIMITS[ip] = hits
            return False
        hits.append(now)
        _LIMITS[ip] = hits
        # opportunistic prune so the dict can't grow without bound
        if len(_LIMITS) > 5000:
            for k in [k for k, v in _LIMITS.items()
                      if not v or now - v[-1] > RL_WINDOW]:
                _LIMITS.pop(k, None)
        return True


def _clean(v, limit):
    return (v or "").replace("\r", " ").replace("\x00", "").strip()[:limit]


def _validate(data):
    """Return (record, error). record is None on validation failure."""
    name = _clean(data.get("name"), 120)
    email = _clean(data.get("email"), 200)
    phone = _clean(data.get("phone"), 60)
    message = (data.get("message") or "").replace("\x00", "").strip()[:5000]
    if not name:
        return None, "name required"
    if not EMAIL_RE.match(email):
        return None, "valid email required"
    if not message:
        return None, "message required"
    return {"name": name, "email": email, "phone": phone, "message": message}, None


def _store(record):
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _FILE_LOCK:
        os.makedirs(os.path.dirname(MESSAGES_FILE) or ".", exist_ok=True)
        with open(MESSAGES_FILE, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())


def _email_async(record):
    """Fire-and-forget SMTP notification; only if SMTP_HOST + SMTP_TO are set."""
    host = os.environ.get("SMTP_HOST")
    to = os.environ.get("SMTP_TO", "barrie@beautyextensionhaus.com")
    if not host or not to:
        return

    def send():
        try:
            msg = EmailMessage()
            msg["Subject"] = "New contact message — %s" % record["name"]
            msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", to))
            msg["To"] = to
            if EMAIL_RE.match(record["email"]):
                msg["Reply-To"] = record["email"]
            msg.set_content(
                "Name:    %(name)s\nEmail:   %(email)s\nPhone:   %(phone)s\n"
                "When:    %(ts)s (%(loc)s)\n\n%(message)s\n" % record)
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=15) as s:
                if os.environ.get("SMTP_TLS", "1") not in ("0", "false", "no"):
                    s.starttls()
                user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
                if user and pw:
                    s.login(user, pw)
                s.send_message(msg)
        except Exception as e:                       # never let email break intake
            print("contact: email failed:", e, flush=True)

    threading.Thread(target=send, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "haus-contact"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _client_ip(self):
        xff = self.headers.get("X-Forwarded-For", "")
        return (xff.split(",")[0].strip()
                or self.headers.get("CF-Connecting-IP", "").strip()
                or self.client_address[0])

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/message":
            return self._json({"ok": False, "error": "not found"}, 404)

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            return self._json({"ok": False, "error": "bad request"}, 400)
        raw = self.rfile.read(length)

        ctype = (self.headers.get("Content-Type") or "").lower()
        try:
            if "application/json" in ctype:
                data = json.loads(raw.decode("utf-8"))
            else:
                data = {k: v[0] for k, v in parse_qs(raw.decode("utf-8")).items()}
        except Exception:
            return self._json({"ok": False, "error": "bad request"}, 400)
        if not isinstance(data, dict):
            return self._json({"ok": False, "error": "bad request"}, 400)

        # Honeypot: bots fill hidden 'company'. Pretend success, store nothing.
        if _clean(data.get("company"), 80):
            return self._json({"ok": True})

        now = time.time()
        if not _rate_ok(self._client_ip(), now):
            return self._json({"ok": False,
                               "error": "too many messages — please try again shortly"}, 429)

        record, err = _validate(data)
        if err:
            return self._json({"ok": False, "error": err}, 400)

        record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        record["loc"] = _clean(data.get("loc"), 8) or "ca"
        record["ip"] = self._client_ip()
        record["ua"] = _clean(self.headers.get("User-Agent"), 300)
        try:
            _store(record)
        except Exception as e:
            print("contact: store failed:", e, flush=True)
            return self._json({"ok": False, "error": "server error"}, 500)
        _email_async(record)
        return self._json({"ok": True})


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    srv = ThreadingHTTPServer((host, port), Handler)
    print("contact receiver on %s:%d -> %s" % (host, port, MESSAGES_FILE), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
