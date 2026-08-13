"""Auth engine for the Haus admin.

A single-user gate for /admin + /api:
  - Password, trust-on-first-use (the first password submitted becomes THE password).
    Stored only as a PBKDF2-HMAC-SHA256 hash. No username.
  - Passkey (WebAuthn) as a second factor, bound to RP_ID (the public domain).
  - Signed, HttpOnly session cookies (HMAC-SHA256 over a server secret).

State lives OUTSIDE the web root (deploy/auth/state.json) so it is never served.
Break-glass: delete that file to return to first-run; password-only login still
works over the tailnet (where the passkey origin doesn't match), so a lost
passkey never locks the owner out.
"""
import base64, hashlib, hmac, json, os, secrets, threading, time

RP_ID = os.environ.get("HAUS_RP_ID", "beautyextensionhaus.com")
RP_NAME = "Beauty Extension Haus Admin"
ORIGIN = os.environ.get("HAUS_ORIGIN", "https://beautyextensionhaus.com")
# Accept both the apex and www origins. A passkey whose RP ID is the apex domain
# is valid from www too (www is a subdomain of the RP ID), so we allow either.
ORIGINS = [o.strip() for o in os.environ.get(
    "HAUS_ORIGINS", ORIGIN + ",https://www." + RP_ID).split(",") if o.strip()]

AUTH_DIR = os.environ.get("HAUS_AUTH") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deploy", "auth")
STATE_FILE = os.path.join(AUTH_DIR, "state.json")

PBKDF2_ITERS = 240000
SESSION_TTL = 12 * 3600          # 12h
CHALLENGE_TTL = 300              # 5 min

_LOCK = threading.Lock()
_CHALLENGES = {}                 # token -> (challenge_bytes, expiry, kind)


# ---- small helpers ---------------------------------------------------------
def _b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64u_dec(s):
    s = s.replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4))


def _load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(st):
    os.makedirs(AUTH_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _secret():
    with _LOCK:
        st = _load()
        s = st.get("secret")
        if not s:
            s = _b64u(secrets.token_bytes(32))
            st["secret"] = s
            _save(st)
    return _b64u_dec(s)


# ---- password (TOFU) -------------------------------------------------------
def password_set():
    return bool(_load().get("password"))


def set_password(pw):
    """First password wins; returns False if one is already set."""
    if not pw or len(pw) < 8:
        raise ValueError("Password must be at least 8 characters.")
    with _LOCK:
        st = _load()
        if st.get("password"):
            return False
        salt = secrets.token_bytes(16)
        h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITERS)
        st["password"] = {"salt": _b64u(salt), "hash": _b64u(h), "iters": PBKDF2_ITERS}
        _save(st)
    return True


def verify_password(pw):
    p = _load().get("password")
    if not p or not pw:
        return False
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), _b64u_dec(p["salt"]), p.get("iters", PBKDF2_ITERS))
    return hmac.compare_digest(_b64u(h), p["hash"])


# ---- sessions --------------------------------------------------------------
def make_session(level):
    payload = _b64u(json.dumps({
        "lvl": level,
        "exp": int(time.time()) + SESSION_TTL,
        "n": _b64u(secrets.token_bytes(8)),
    }).encode())
    sig = _b64u(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return payload + "." + sig


def session_level(cookie):
    if not cookie or "." not in cookie:
        return None
    payload, sig = cookie.rsplit(".", 1)
    good = _b64u(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, good):
        return None
    try:
        obj = json.loads(_b64u_dec(payload))
    except Exception:
        return None
    if obj.get("exp", 0) < time.time():
        return None
    return obj.get("lvl")


# ---- passkeys --------------------------------------------------------------
def credentials():
    return _load().get("credentials", [])


def has_passkey():
    return bool(credentials())


def remove_passkeys():
    with _LOCK:
        st = _load()
        st["credentials"] = []
        _save(st)
    return True


def webauthn_available():
    try:
        import webauthn  # noqa: F401
        return True
    except Exception:
        return False


def _put_challenge(kind, challenge):
    tok = _b64u(secrets.token_bytes(16))
    now = time.time()
    with _LOCK:
        for k in [k for k, v in _CHALLENGES.items() if v[1] < now]:
            _CHALLENGES.pop(k, None)
        _CHALLENGES[tok] = (challenge, now + CHALLENGE_TTL, kind)
    return tok


def _take_challenge(tok, kind):
    with _LOCK:
        v = _CHALLENGES.pop(tok, None)
    if not v or v[1] < time.time() or v[2] != kind:
        return None
    return v[0]


def reg_begin():
    import webauthn
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement,
        PublicKeyCredentialDescriptor)
    exclude = [PublicKeyCredentialDescriptor(id=_b64u_dec(c["id"])) for c in credentials()]
    opts = webauthn.generate_registration_options(
        rp_id=RP_ID, rp_name=RP_NAME,
        user_id=b"haus-admin", user_name="admin", user_display_name="Haus Admin",
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED),
    )
    tok = _put_challenge("reg", opts.challenge)
    return tok, webauthn.options_to_json(opts)


def reg_finish(tok, credential_json):
    import webauthn
    challenge = _take_challenge(tok, "reg")
    if challenge is None:
        raise ValueError("Registration challenge expired — try again.")
    ver = webauthn.verify_registration_response(
        credential=credential_json, expected_challenge=challenge,
        expected_rp_id=RP_ID, expected_origin=ORIGINS)
    with _LOCK:
        st = _load()
        creds = st.setdefault("credentials", [])
        creds.append({
            "id": _b64u(ver.credential_id),
            "public_key": _b64u(ver.credential_public_key),
            "sign_count": ver.sign_count,
            "created": int(time.time()),
        })
        _save(st)
    return True


def auth_begin():
    import webauthn
    from webauthn.helpers.structs import (PublicKeyCredentialDescriptor, UserVerificationRequirement)
    allow = [PublicKeyCredentialDescriptor(id=_b64u_dec(c["id"])) for c in credentials()]
    opts = webauthn.generate_authentication_options(
        rp_id=RP_ID, allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED)
    tok = _put_challenge("auth", opts.challenge)
    return tok, webauthn.options_to_json(opts)


def auth_finish(tok, credential_json):
    import webauthn
    challenge = _take_challenge(tok, "auth")
    if challenge is None:
        raise ValueError("Login challenge expired — try again.")
    body = json.loads(credential_json) if isinstance(credential_json, str) else credential_json
    cid = (body.get("id") or body.get("rawId") or "").rstrip("=")
    with _LOCK:
        st = _load()
        creds = st.get("credentials", [])
        match = next((c for c in creds if c["id"].rstrip("=") == cid), None)
        if not match:
            raise ValueError("Unknown passkey.")
        ver = webauthn.verify_authentication_response(
            credential=credential_json, expected_challenge=challenge,
            expected_rp_id=RP_ID, expected_origin=ORIGINS,
            credential_public_key=_b64u_dec(match["public_key"]),
            credential_current_sign_count=match.get("sign_count", 0),
            require_user_verification=False)
        match["sign_count"] = ver.new_sign_count
        _save(st)
    return True


# ---- login gate page (self-contained; served when unauthenticated) ---------
LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Haus Admin</title>
<meta name="robots" content="noindex, nofollow">
<link rel="icon" href="/assets/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600&family=Jost:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{box-sizing:border-box}
  :root{--brand:#EBD2FD;--paper:#FBF5FF;--ink:#1A171C;--ink2:#4a4550;--muted:#6b6572;
    --rule:#d9c4ec;--accent:#8a6d1e;--accent2:#b9922e;--glassbrd:rgba(255,255,255,.65)}
  html,body{margin:0;height:100%;overflow-x:clip}
  body{font-family:"Jost",system-ui,sans-serif;color:var(--ink);
    background:radial-gradient(130% 55% at 50% -10%, #fff 0, transparent 60%),
      radial-gradient(80% 40% at 85% 8%, rgba(185,146,46,.18) 0, transparent 55%),
      linear-gradient(180deg,#FBF5FF,#F1E6FA 60%,#E8DBF1);
    min-height:100svh;display:grid;place-items:center;padding:1.5rem}
  .card{width:100%;max-width:23rem;background:rgba(255,255,255,.55);
    -webkit-backdrop-filter:blur(18px) saturate(1.3);backdrop-filter:blur(18px) saturate(1.3);
    border:1px solid var(--glassbrd);border-radius:22px;
    box-shadow:0 24px 60px -30px rgba(26,23,28,.5);padding:2rem 1.7rem 1.7rem;text-align:center}
  .brand{font-size:.72rem;letter-spacing:.32em;text-transform:uppercase;color:var(--accent);margin:0 0 1.1rem}
  h1{font-family:"Playfair Display",serif;font-weight:600;font-size:1.7rem;margin:.2rem 0 .3rem}
  .sub{font-size:.9rem;line-height:1.5;color:var(--ink2);margin:0 auto 1.4rem;max-width:19rem}
  form{display:flex;flex-direction:column;gap:.7rem}
  label{text-align:left;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
  input[type=password]{width:100%;font:inherit;font-size:1rem;padding:.7rem .85rem;border:1px solid var(--rule);
    border-radius:12px;background:rgba(255,255,255,.7);color:var(--ink)}
  input:focus{outline:2px solid var(--accent2);outline-offset:1px;border-color:var(--accent2)}
  button{font:inherit;font-weight:500;font-size:.95rem;padding:.75rem 1rem;border:0;border-radius:999px;
    background:var(--ink);color:#FBF5FF;cursor:pointer;transition:transform .18s,opacity .18s;margin-top:.2rem}
  button:hover{transform:translateY(-1px)}
  button:disabled{opacity:.5;cursor:default;transform:none}
  button.ghost{background:transparent;color:var(--ink2);border:1px solid var(--rule)}
  .msg{min-height:1.1rem;font-size:.82rem;margin:.4rem 0 0}
  .msg.err{color:#9a2b3a}.msg.ok{color:var(--accent)}
  .foot{margin:1.3rem 0 0;font-size:.7rem;letter-spacing:.05em;color:var(--muted)}
  .hidden{display:none}
  .key{display:inline-block;width:1.05rem;height:1.05rem;vertical-align:-2px;margin-right:.35rem}
</style></head>
<body>
  <main class="card">
    <p class="brand">Beauty Extension Haus</p>
    <h1 id="title">Haus Admin</h1>
    <p class="sub" id="sub">Checking…</p>

    <form id="pwform" class="hidden" autocomplete="off">
      <label id="pwlabel" for="pw">Password</label>
      <input type="password" id="pw" name="pw" autocomplete="current-password" required>
      <input type="password" id="pw2" name="pw2" class="hidden" autocomplete="new-password" placeholder="Confirm password">
      <button type="submit" id="pwbtn">Continue</button>
    </form>

    <div id="pkstep" class="hidden">
      <button id="pkbtn"><svg class="key" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M15 7a4 4 0 1 0-3.9 5H14l1.5 1.5L14 15l1.5 1.5L18 14l-1-1a4 4 0 0 0-2-6z"/></svg><span id="pklabel">Use your passkey</span></button>
      <button id="pkskip" class="ghost hidden" type="button">Skip for now</button>
    </div>

    <p class="msg" id="msg"></p>
    <p class="foot">Private · authorized access only</p>
  </main>

<script>
(function(){
  "use strict";
  var S = {};
  var $ = function(id){ return document.getElementById(id); };
  function msg(t, cls){ var m=$("msg"); m.textContent=t||""; m.className="msg"+(cls?" "+cls:""); }
  function show(id){ $(id).classList.remove("hidden"); }
  function hide(id){ $(id).classList.add("hidden"); }

  function b64uToBuf(s){ s=s.replace(/-/g,"+").replace(/_/g,"/"); var pad="=".repeat((4-s.length%4)%4);
    var bin=atob(s+pad), b=new Uint8Array(bin.length); for(var i=0;i<bin.length;i++)b[i]=bin.charCodeAt(i); return b.buffer; }
  function bufToB64u(buf){ var b=new Uint8Array(buf), s=""; for(var i=0;i<b.length;i++)s+=String.fromCharCode(b[i]);
    return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,""); }
  function prepCreate(json){ var o=JSON.parse(json); o.challenge=b64uToBuf(o.challenge); o.user.id=b64uToBuf(o.user.id);
    (o.excludeCredentials||[]).forEach(function(c){ c.id=b64uToBuf(c.id); }); return o; }
  function prepGet(json){ var o=JSON.parse(json); o.challenge=b64uToBuf(o.challenge);
    (o.allowCredentials||[]).forEach(function(c){ c.id=b64uToBuf(c.id); }); return o; }
  function credJSON(cred){ var r=cred.response, out={id:cred.id,rawId:bufToB64u(cred.rawId),type:cred.type,response:{}};
    if(r.attestationObject){ out.response.attestationObject=bufToB64u(r.attestationObject); out.response.clientDataJSON=bufToB64u(r.clientDataJSON); }
    else { out.response.authenticatorData=bufToB64u(r.authenticatorData); out.response.clientDataJSON=bufToB64u(r.clientDataJSON);
      out.response.signature=bufToB64u(r.signature); if(r.userHandle)out.response.userHandle=bufToB64u(r.userHandle); }
    out.clientExtensionResults=cred.getClientExtensionResults?cred.getClientExtensionResults():{}; return out; }

  function api(path, body){ return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body||{})}).then(function(r){ return r.json(); }); }
  function done(){ msg("Welcome back ✦","ok"); setTimeout(function(){ location.href="/admin"; }, 350); }

  function registerPasskey(){
    msg("Follow your device's prompt…");
    return api("/api/auth/passkey/register-begin").then(function(r){
      if(!r.ok) throw new Error(r.error||"Could not start passkey setup");
      return navigator.credentials.create({publicKey: prepCreate(r.options)}).then(function(cred){
        return api("/api/auth/passkey/register-finish",{token:r.token,credential:credJSON(cred)});
      });
    }).then(function(r){ if(!r||!r.ok) throw new Error((r&&r.error)||"Passkey setup failed"); done(); });
  }
  function assertPasskey(){
    msg("Confirm with your passkey…");
    return api("/api/auth/passkey/login-begin").then(function(r){
      if(!r.ok) throw new Error(r.error||"Could not start passkey check");
      return navigator.credentials.get({publicKey: prepGet(r.options)}).then(function(cred){
        return api("/api/auth/passkey/login-finish",{token:r.token,credential:credJSON(cred)});
      });
    }).then(function(r){ if(!r||!r.ok) throw new Error((r&&r.error)||"Passkey check failed"); done(); });
  }

  function offerRegister(optional){
    hide("pwform"); show("pkstep");
    $("pklabel").textContent = "Set up a passkey";
    $("title").textContent = "Add a passkey";
    $("sub").textContent = optional ? "Add a passkey (Touch ID / Face ID / security key) as your second step."
                                    : "Secure this admin with a passkey — your second factor from now on.";
    $("pkskip").classList.toggle("hidden", !optional);
    msg("");
    $("pkbtn").onclick = function(){ $("pkbtn").disabled=true;
      registerPasskey().catch(function(e){ $("pkbtn").disabled=false; msg(e.message||String(e),"err"); }); };
    $("pkskip").onclick = function(){ done(); };
  }

  function initFirstRun(){
    $("title").textContent="Create your password";
    $("sub").textContent="Set the password for the Haus admin. There is no username — just this password. You'll add a passkey next.";
    $("pwlabel").textContent="New password (min 8 characters)";
    $("pw").setAttribute("autocomplete","new-password");
    show("pwform"); show("pw2");
    $("pwbtn").textContent="Set password";
    $("pwform").onsubmit=function(e){ e.preventDefault();
      var a=$("pw").value, b=$("pw2").value;
      if(a.length<8){ msg("Use at least 8 characters.","err"); return; }
      if(a!==b){ msg("Passwords don't match.","err"); return; }
      $("pwbtn").disabled=true; msg("");
      api("/api/auth/set-password",{password:a}).then(function(r){
        $("pwbtn").disabled=false;
        if(!r.ok){ msg(r.error||"Could not set password.","err"); return; }
        done();   // passkey is added later (see admin Security), so go straight in
      }); };
  }

  function initLogin(){
    var hasPk = S.passkeys>0 && S.public && window.PublicKeyCredential;
    $("title").textContent="Haus Admin";
    $("sub").textContent = hasPk ? "Tap your passkey, or use your password." : "Sign in to continue.";
    $("pwlabel").textContent="Password";
    show("pwform");
    $("pwbtn").textContent="Continue";
    $("pwform").onsubmit=function(e){ e.preventDefault();
      $("pwbtn").disabled=true; msg("");
      api("/api/auth/login",{password:$("pw").value}).then(function(r){
        if(!r.ok){ $("pwbtn").disabled=false; msg(r.error||"Incorrect password.","err"); $("pw").select(); return; }
        if(r.passkey_required){ msg("Now confirm with your passkey…");
          assertPasskey().catch(function(err){ $("pwbtn").disabled=false; msg((err&&err.message)||String(err),"err"); }); return; }
        done();
      }); };
    // one-tap passwordless sign-in, offered when a passkey exists
    if(hasPk){
      show("pkstep"); $("pkskip").classList.add("hidden"); $("pklabel").textContent="Sign in with a passkey";
      $("pkbtn").onclick=function(){ $("pkbtn").disabled=true; msg("");
        assertPasskey().catch(function(err){ $("pkbtn").disabled=false; msg((err&&err.message)||String(err),"err"); }); };
    }
  }

  fetch("/api/auth/status").then(function(r){ return r.json(); }).then(function(s){
    S=s;
    if(!s.password_set) initFirstRun(); else initLogin();
    setTimeout(function(){ var el=$("pw"); if(el) el.focus(); }, 60);
  }).catch(function(){ msg("Server unavailable. Refresh to retry.","err"); });
})();
</script>
</body></html>
"""
