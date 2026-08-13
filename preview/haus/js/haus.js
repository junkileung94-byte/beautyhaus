/* Beauty Extension Haus — gate → splash → site
 * The gate (US / CAN) shows on every visit (per browser session), before the splash.
 * Chosen haus drives location-scoped copy via body[data-haus] + [data-loc]. */
(function () {
  "use strict";

  /* Booking config.
   * CA (Barrie): Square booking, opened in the on-site iframe modal (openBooking).
   * US (Sarasota): Mangomint online booking. Its app.js is injected ONLY when the
   *   US site is active (loadMangomint, called from applyLoc) — the CA site never
   *   loads it. app.js intercepts clicks on links to booking.mangomint.com and
   *   opens its own overlay, so US Book buttons just carry that href and the click
   *   handler leaves them alone (we do NOT iframe Mangomint — it blocks framing). */
  var BOOKING = {
    widgetScript: null
  };

  var LOC = {
    ca: {
      name: "Barrie, Ontario",
      short: "Barrie · ON",
      address: "480 Mapleton Ave, Barrie ON L4N 9C2",
      phone: "+1 705-241-8452",
      phoneHref: "tel:+17052418452",
      email: "barrie@beautyextensionhaus.com",
      book: "https://book.squareup.com/appointments/d2wslhq6ohtrno/location/0SNE1R5SHR4FD/services",
      bookLabel: "Book now"
    },
    us: {
      name: "Sarasota, Florida",
      short: "Sarasota · FL",
      address: "1724 4th Street, Sarasota, Florida 34236",
      phone: "+1 705-241-8452",
      phoneHref: "tel:+17052418452",
      email: "barrie@beautyextensionhaus.com",
      book: "https://booking.mangomint.com/733325",
      bookLabel: "Book now"
    }
  };

  /* Official flag geometry. Canada: 1:2, quarter red bars, Wikimedia maple-leaf
   * path (public domain). US: 10:19 spec — 13 stripes, canton 7 stripes tall,
   * 50 stars in the official 6/5 alternating grid (generated below). */
  var FLAG_CA =
    '<svg viewBox="0 0 9600 4800" role="img" aria-label="Canadian flag">' +
      '<path fill="#d52b1e" d="M0 0h2400v4800H0zm7200 0h2400v4800H7200z"/>' +
      '<path fill="#fff" d="M2400 0h4800v4800H2400z"/>' +
      '<path fill="#d52b1e" d="m4890 4430-45-863a95 95 0 0 1 111-98l859 151-116-320a65 65 0 0 1 20-73l941-762-212-99a65 65 0 0 1-34-79l186-572-542 115a65 65 0 0 1-73-38l-105-247-423 454a65 65 0 0 1-111-57l204-1052-327 189a65 65 0 0 1-91-27l-332-652-332 652a65 65 0 0 1-91 27l-327-189 204 1052a65 65 0 0 1-111 57l-423-454-105 247a65 65 0 0 1-73 38l-542-115 186 572a65 65 0 0 1-34 79l-212 99 941 762a65 65 0 0 1 20 73l-116 320 859-151a95 95 0 0 1 111 98l-45 863z"/>' +
    "</svg>";
  var FLAG_US = (function () {
    function star(cx, cy, r) {
      var pts = [];
      for (var i = 0; i < 10; i++) {
        var ang = -Math.PI / 2 + (i * Math.PI) / 5;
        var rad = i % 2 === 0 ? r : r * 0.382;
        pts.push((cx + rad * Math.cos(ang)).toFixed(0) + "," + (cy + rad * Math.sin(ang)).toFixed(0));
      }
      return "M" + pts.join("L") + "z";
    }
    var stripes = "";
    for (var i = 0; i < 13; i += 2) stripes += '<rect y="' + i * 300 + '" width="7410" height="300"/>';
    var stars = "";
    for (var row = 1; row <= 9; row++) {
      for (var col = row % 2 === 1 ? 1 : 2; col <= 11; col += 2) {
        stars += star(col * 247, row * 210, 120);
      }
    }
    return (
      '<svg viewBox="0 0 7410 3900" role="img" aria-label="United States flag">' +
        '<rect width="7410" height="3900" fill="#fff"/>' +
        '<g fill="#b22234">' + stripes + "</g>" +
        '<rect width="2964" height="2100" fill="#3c3b6e"/>' +
        '<path fill="#fff" d="' + stars + '"/>' +
      "</svg>"
    );
  })();

  /* Analytics hook — js/track.js (loaded after this file) defines hausTrack and
   * appends the " -ca" / " -us" locale suffix. Used for the things a delegated
   * click can't see: modal opens and form SUCCESSES. */
  // track.js loads after this file, so boot-time calls (Gate Shown) are queued
  // and drained by track.js once it defines hausTrack.
  function trk(name, props) {
    if (window.hausTrack) { window.hausTrack(name, props); return; }
    (window.__hausTrackQ = window.__hausTrackQ || []).push([name, props]);
  }

  var ROOT = (function () {
    // resolve asset paths relative to this script (works at any mount path)
    var s = document.currentScript;
    return s ? s.src.replace(/js\/haus\.js.*$/, "") : "./";
  })();

  function el(html) {
    var t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  var FLAGS = { ca: FLAG_CA, us: FLAG_US };

  // Reveal locale-variant content (held by .loc-ready in haus.css) as soon as the
  // CURRENT locale's content is ready — instantly for CA (no overrides) and for a
  // returning US visitor (content cached below), so the page loads as a single
  // locale with no base/CA flash and no blank.
  function markReady() { document.body.classList.add("loc-ready"); }
  function revealIfReady() {
    if (document.body.dataset.haus === "ca" || CONTENT) markReady();
  }
  setTimeout(markReady, 1500); // fail-safe: never stay hidden if the fetch is slow/unavailable

  // Per-locale content overrides (text/images/team), edited in /admin, stored in
  // content.json. Cached in localStorage and applied SYNCHRONOUSLY at boot so a
  // returning visitor's locale renders in one paint; the network copy then
  // refreshes the cache (and re-applies only if it actually changed).
  var CONTENT = null;
  var CONTENT_KEY = "hausContent";
  try {
    var _cached = localStorage.getItem(CONTENT_KEY);
    if (_cached) { CONTENT = JSON.parse(_cached); window.__hausContent = CONTENT; }
  } catch (e) {}

  fetch(ROOT + "assets/content.json?v=" + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (c) {
      var changed = JSON.stringify(c) !== JSON.stringify(CONTENT);
      CONTENT = c; window.__hausContent = c;
      try { localStorage.setItem(CONTENT_KEY, JSON.stringify(c)); } catch (e) {}
      var h = document.body.dataset.haus;
      if (h && changed) applyLoc(h);
      markReady();
    })
    .catch(function () { markReady(); });

  // per-locale section visibility, edited in /admin → Sections, stored in layout.json.
  // Only toggles .sec-hidden on tagged <section> nodes — no reorder, colours untouched.
  var LAYOUT = null;
  fetch(ROOT + "assets/layout.json?v=" + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (l) { LAYOUT = l || {}; var h = document.body.dataset.haus; if (h) applyLayout(h); })
    .catch(function () {});

  // per-locale team roster — CA lives in assets/team.json, US in content.json["us"].team.
  // Both are edited in /admin → Team. Renders into <ul data-team>; toggles [data-team-empty].
  var TEAM_CA = null;
  fetch(ROOT + "assets/team.json?v=" + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (t) { TEAM_CA = Array.isArray(t) ? t : []; renderTeam(document.body.dataset.haus || "ca"); })
    .catch(function () { TEAM_CA = []; });

  function teamCard(m) {
    m = m || {};
    var name = (m.name || "").trim();
    var role = (m.role || "").trim();
    var bio = (m.bio || "").trim();
    var photo = (m.photo || "").trim();
    var portrait = photo
      ? '<img src="' + ROOT + photo + '" alt="' + name.replace(/"/g, "&quot;") + '" loading="lazy">'
      : '<span class="team-card__placeholder" aria-hidden="true"></span>';
    return '<li class="team-card">' +
        '<figure class="team-card__portrait">' + portrait + "</figure>" +
        (name ? '<h3 class="team-card__name">' + name + "</h3>" : "") +
        (role ? '<p class="label team-card__role">' + role + "</p>" : "") +
        (bio ? '<p class="muted team-card__bio">' + bio + "</p>" : "") +
      "</li>";
  }

  function renderTeam(haus) {
    var grid = document.querySelector("[data-team]");
    if (!grid) return;
    var items = haus === "us"
      ? ((CONTENT && CONTENT.us && CONTENT.us.team) || [])
      : (TEAM_CA || []);
    grid.innerHTML = items.map(teamCard).join("");
    var empty = document.querySelector("[data-team-empty]");
    if (empty) empty.hidden = items.length > 0;
  }

  // ---- slot videos: a photo slot can instead hold a clip that autoplays on scroll ----
  var NO_MOTION = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var VID_IO = ("IntersectionObserver" in window) ? new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      var v = en.target;
      if (en.isIntersecting && en.intersectionRatio >= 0.6) {
        // in view = the clip must actually load now. Bump preload off "metadata"
        // (which only ever reaches readyState 1 — no frame) and start the
        // watchdog that restores the photo if no frame arrives.
        if (v.preload !== "auto") v.preload = "auto";
        if (v.__arm) v.__arm();
        var pr = v.play(); if (pr && pr.catch) pr.catch(function () {});
      } else if (!v.paused) { v.pause(); }
    });
  }, { threshold: [0, 0.6, 1] }) : null;

  function resolveUrl(u) { return /^(https?:|\/|data:|blob:)/.test(u) ? u : ROOT + u; }

  // How long a slot video that is ON SCREEN may go without producing a frame
  // before we fall back to its photo.
  var VID_WATCHDOG_MS = 7000;

  // mount/update a slot's muted looping video overlay (the photo stays behind as poster)
  function mountSlotVideo(slot, url, imgEl, picEl) {
    var host = picEl ? picEl.parentElement : (imgEl ? imgEl.parentElement : null);
    if (!host) return;
    var vid = host.querySelector('video[data-slot-video="' + slot + '"]');
    var src = resolveUrl(url);
    if (!vid) {
      vid = document.createElement("video");
      vid.setAttribute("data-slot-video", slot);
      vid.className = "slot-video";
      vid.muted = true; vid.defaultMuted = true; vid.loop = true; vid.playsInline = true;
      vid.setAttribute("muted", ""); vid.setAttribute("loop", ""); vid.setAttribute("playsinline", "");
      vid.preload = "metadata";

      // The clip is only ever "ready" once it holds a decodable frame
      // (readyState >= HAVE_CURRENT_DATA). `loadeddata` alone is not enough to
      // rely on: with preload="metadata" iOS stops at readyState 1 and never
      // fires it, so listen for every event that can signal a first frame.
      function ready() {
        if (vid.readyState < 2 || vid.classList.contains("is-ready")) return;
        clearTimeout(vid.__wd); vid.__wd = null;
        vid.classList.add("is-ready");
        // frame is on screen and opaque → drop the poster photo underneath so it
        // can't flash through a loop seam.
        host.classList.add("slot-live");
      }
      ["loadeddata", "canplay", "canplaythrough", "playing", "timeupdate"].forEach(function (ev) {
        vid.addEventListener(ev, ready);
      });

      // No frame = fall back to the photo. This is the path that used to leave a
      // bare pink block: the photo was hidden at mount time and nothing ever put
      // it back when the clip failed to decode. Chrome keeps its media cache
      // across sessions (Safari's clears more readily), so one truncated range
      // response can wedge the same slot on every later visit — hence the single
      // cache-busted retry before giving up.
      function fail() {
        if (vid.classList.contains("is-ready")) return;   // already playing — ignore late noise
        clearTimeout(vid.__wd); vid.__wd = null;
        if (!vid.__retried) {
          vid.__retried = 1;
          var u = vid.__src;
          vid.setAttribute("src", u + (u.indexOf("?") > -1 ? "&" : "?") + "cb=" + Date.now());
          vid.load();
          var pr = vid.play(); if (pr && pr.catch) pr.catch(function () {});
          vid.__arm();
          return;
        }
        removeSlotVideo(vid);
      }
      vid.addEventListener("error", fail);
      // NOT `stalled`/`waiting` — those fire routinely while buffering a big clip
      // on a slow phone connection. Treating them as failure would throw away a
      // download that was going to succeed.
      vid.__arm = function () { if (!vid.__wd) vid.__wd = setTimeout(fail, VID_WATCHDOG_MS); };
      // Bytes are still arriving → reset the watchdog. So the timeout means
      // "stuck for 7s", not "slower than 7s" — a phone on a weak connection keeps
      // its clip instead of being dropped to the photo for being slow.
      vid.addEventListener("progress", function () {
        if (!vid.__wd || vid.classList.contains("is-ready")) return;
        clearTimeout(vid.__wd); vid.__wd = null; vid.__arm();
      });

      if (getComputedStyle(host).position === "static") host.style.position = "relative";
      host.appendChild(vid);
      if (VID_IO) VID_IO.observe(vid);
    }
    if (vid.getAttribute("src") !== src) {
      // new clip for this slot: show the photo again until the new one has a frame
      vid.__src = src; vid.__retried = 0;
      clearTimeout(vid.__wd); vid.__wd = null;
      vid.classList.remove("is-ready");
      host.classList.remove("slot-live");
      vid.setAttribute("src", src);
    }
    // the slot's own photo doubles as the clip's poster, so even a video that
    // never decodes paints the right image instead of the section background.
    var poster = (imgEl && (imgEl.currentSrc || imgEl.src)) || "";
    if (poster && vid.poster !== poster) vid.poster = poster;
  }

  function removeSlotVideo(vid) {
    if (VID_IO) VID_IO.unobserve(vid);
    clearTimeout(vid.__wd); vid.__wd = null;
    try { vid.pause(); } catch (e) {}
    var host = vid.parentElement;
    vid.remove();
    if (host && !host.querySelector("video[data-slot-video]")) host.classList.remove("slot-live");
  }

  // The authored HTML IS the CA/base site (CA carries no overrides of its own).
  // Snapshot every copy/image slot's default ONCE, before any locale is applied,
  // so switching locales can REVERT the ids a previous locale overrode. Without
  // this, US copy/images (63 text overrides) linger on the CA site after a
  // US→CA switch — CA has nothing to overwrite them back with.
  var DEFAULTS = null;
  function snapshotDefaults() {
    if (DEFAULTS) return;
    DEFAULTS = { text: {}, img: {}, srcset: {} };
    document.querySelectorAll("[data-edit]").forEach(function (n) {
      DEFAULTS.text[n.getAttribute("data-edit")] = n.innerHTML;
    });
    document.querySelectorAll("img[data-slot]").forEach(function (n) {
      DEFAULTS.img[n.getAttribute("data-slot")] = n.getAttribute("src") || "";
    });
    document.querySelectorAll("source[data-slot-src]").forEach(function (n) {
      DEFAULTS.srcset[n.getAttribute("data-slot-src")] = n.getAttribute("srcset") || "";
    });
    // inline <video data-vid> (the welcome clip) — these play with sound on a
    // click, so they're separate from the muted autoplay slot videos above.
    DEFAULTS.vid = {};
    document.querySelectorAll("video[data-vid]").forEach(function (n) {
      var s = n.querySelector("source");
      DEFAULTS.vid[n.getAttribute("data-vid")] = {
        src: (s && s.getAttribute("src")) || n.getAttribute("src") || "",
        poster: n.getAttribute("poster") || ""
      };
    });
  }

  function applyContent(haus) {
    snapshotDefaults();
    var C = (CONTENT && CONTENT[haus]) || {};
    var t = C.text || {};
    var img = C.img || {};

    // text: every snapshotted slot → this locale's override if present, else its
    // authored default. The default-branch is what reverts a prior locale.
    Object.keys(DEFAULTS.text).forEach(function (id) {
      var el = document.querySelector('[data-edit="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
      if (el) el.innerHTML = (id in t) ? t[id] : DEFAULTS.text[id];
    });

    // images: reset each slot's <img src> and <source srcset> to default, then
    // layer this locale's override (if any).
    Object.keys(DEFAULTS.img).forEach(function (slot) {
      var el = document.querySelector('img[data-slot="' + slot + '"]');
      if (el) el.src = (img[slot] && img[slot].desktop) || DEFAULTS.img[slot];
    });
    Object.keys(DEFAULTS.srcset).forEach(function (slot) {
      var srcEl = document.querySelector('source[data-slot-src="' + slot + '"]');
      if (!srcEl) return;
      var o = img[slot] || {};
      srcEl.srcset = o.mobile || o.desktop || DEFAULTS.srcset[slot];
    });

    // mount this locale's slot videos (poster photo stays behind)
    Object.keys(img).forEach(function (slot) {
      var o = img[slot] || {};
      if (o.video && !NO_MOTION) {
        var pic = document.querySelector('picture[data-slot-pic="' + slot + '"]');
        var el = document.querySelector('img[data-slot="' + slot + '"]');
        mountSlotVideo(slot, o.video, el, pic);
      }
    });
    // drop any slot videos not wanted in this locale (e.g. after a CA/US switch)
    document.querySelectorAll("video[data-slot-video]").forEach(function (v) {
      var s = v.getAttribute("data-slot-video");
      var oo = img[s];
      if (!oo || !oo.video || NO_MOTION) removeSlotVideo(v);
    });

    // inline videos: point each at this locale's clip. CA is the authored base,
    // so it falls back to the clip in the HTML; any other locale needs its own
    // (set in /admin) — otherwise its block is hidden, never borrowed from CA.
    var vid = C.vid || {};
    Object.keys(DEFAULTS.vid).forEach(function (name) {
      var el = document.querySelector('video[data-vid="' + name + '"]');
      if (!el) return;
      var o = vid[name] || (haus === "ca" ? DEFAULTS.vid[name] : null);
      var wrap = el.closest('[data-vid-wrap="' + name + '"]') || el.parentElement;
      if (!o || !o.src) { if (wrap) wrap.classList.add("vid-empty"); return; }
      if (wrap) wrap.classList.remove("vid-empty");
      var src = resolveUrl(o.src);
      var srcEl = el.querySelector("source");
      if (srcEl) {
        // <source> changes need an explicit load() — unlike src on the element
        if (srcEl.getAttribute("src") !== src) { srcEl.setAttribute("src", src); el.load(); }
      } else if (el.getAttribute("src") !== src) {
        el.setAttribute("src", src);
      }
      el.poster = o.poster ? resolveUrl(o.poster) : "";
    });
    document.dispatchEvent(new CustomEvent("haus:locale", { detail: haus }));
  }

  // Hide sections for the current locale (per /admin → Sections). Visibility only.
  function applyLayout(haus) {
    var main = document.querySelector("main");
    if (!main) return;
    var nodes = main.querySelectorAll(":scope > [data-section]");
    if (!nodes.length) return;
    var cfg = (LAYOUT && LAYOUT[haus] && LAYOUT[haus][pageKey()]) || {};
    var hidden = Array.isArray(cfg.hidden) ? cfg.hidden : [];
    nodes.forEach(function (n) {
      n.classList.toggle("sec-hidden", hidden.indexOf(n.getAttribute("data-section")) !== -1);
    });
  }

  function pageKey() {
    var p = (location.pathname || "").split("/").pop();
    return p && /\.html$/.test(p) ? p : "index.html";
  }

  function applyLoc(haus) {
    // start from the built-in defaults, then layer any /admin contact overrides (phone/email)
    var loc = {};
    var base = LOC[haus] || {};
    for (var k in base) loc[k] = base[k];
    var ov = (CONTENT && CONTENT[haus] && CONTENT[haus].contact) || {};
    if (ov.phone) { loc.phone = ov.phone; loc.phoneHref = "tel:" + ov.phone.replace(/[^\d+]/g, ""); }
    if (ov.email) { loc.email = ov.email; }
    document.body.dataset.haus = haus;
    applyContent(haus);
    applyLayout(haus);
    renderTeam(haus);
    // nav switcher shows the CURRENT location's flag (click to switch)
    document.querySelectorAll("[data-loc-flag]").forEach(function (n) {
      n.innerHTML = FLAGS[haus] || "";
      var btn = n.closest("[data-switch-haus]");
      if (btn) btn.title = "You're on the " + (haus === "us" ? "US" : "Canada") + " site — tap to switch";
    });
    document.querySelectorAll("[data-loc-field]").forEach(function (n) {
      var f = n.dataset.locField;
      if (f === "phone") { n.textContent = loc.phone; if (n.tagName === "A") n.href = loc.phoneHref; }
      else if (f === "email") { n.textContent = loc.email; if (n.tagName === "A") n.href = "mailto:" + loc.email; }
      else if (f === "book") { n.href = loc.book; if (n.dataset.keepLabel === undefined) n.textContent = loc.bookLabel; }
      else if (loc[f] !== undefined) { n.textContent = loc[f]; }
    });
    if (haus === "us") loadMangomint();
  }

  // Mangomint online booking — injected ONLY on the US (Sarasota) site, on demand.
  // The CA site never loads it. Loads once even if the locale is re-applied.
  var mangomintLoaded = false;
  function loadMangomint() {
    if (mangomintLoaded) return;
    mangomintLoaded = true;
    window.Mangomint = window.Mangomint || {};
    window.Mangomint.CompanyId = 733325;
    var s = document.createElement("script");
    s.src = "https://booking.mangomint.com/app.js";
    s.async = true;
    document.head.appendChild(s);
  }

  function showSplash(haus, done) {
    var splash = el(
      '<div class="splash" role="status" aria-label="Beauty Extension Haus">' +
        '<div class="splash__stack">' +
          '<img class="splash__logo" src="' + ROOT + 'assets/logo.png" alt="Beauty Extension Haus">' +
          '<p class="splash__loc">' + LOC[haus].short + "</p>" +
        "</div>" +
      "</div>"
    );
    document.body.appendChild(splash);
    var dwell = matchMedia("(prefers-reduced-motion: reduce)").matches ? 600 : 1900;
    setTimeout(function () {
      splash.classList.add("is-leaving");
      setTimeout(function () { splash.remove(); done(); }, 650);
    }, dwell);
  }

  function showGate() {
    document.body.classList.add("is-gated");
    var gate = el(
      '<div class="gate" role="dialog" aria-modal="true" aria-label="Choose your Beauty Extension Haus location">' +
        '<img class="gate__logo" src="' + ROOT + 'assets/logo.png" alt="">' +
        '<div>' +
          '<div class="gate__head"><p class="label">Beauty Extension Haus</p>' +
          '<h1 class="gate__title">Choose your Haus</h1></div>' +
          '<div class="gate__inner" style="margin-top:var(--space-xl)">' +
            '<button class="gate__choice" data-haus="us">' +
              '<span class="gate__flag">' + FLAG_US + "</span>" +
              '<span class="gate__country">United States</span>' +
              '<span class="gate__city">Sarasota · Florida</span>' +
              '<span class="gate__note">Nano bead specialists</span>' +
            "</button>" +
            '<div class="gate__divider" aria-hidden="true"><img class="gate__crown" src="' + ROOT + 'assets/brand/crown-gold.png" alt=""></div>' +
            '<button class="gate__choice" data-haus="ca">' +
              '<span class="gate__flag">' + FLAG_CA + "</span>" +
              '<span class="gate__country">Canada</span>' +
              '<span class="gate__city">Barrie · Ontario</span>' +
              '<span class="gate__note">Award-winning studio</span>' +
            "</button>" +
          "</div>" +
        "</div>" +
        '<p class="gate__foot">Two salons · one Haus</p>' +
      "</div>"
    );
    gate.addEventListener("click", function (e) {
      // Only the two choice cards act. Scope to .gate__choice so clicks on the
      // logo / crown / divider / background do nothing — NOT closest("[data-haus]"),
      // which would walk up to <body data-haus> and silently pick Canada.
      var choice = e.target.closest(".gate__choice");
      if (!choice) return;
      var haus = choice.dataset.haus;
      if (!haus) return;
      try { sessionStorage.setItem("haus", haus); } catch (err) {}
      applyLoc(haus);
      revealIfReady();
      // Cover with the (now-opaque) splash BEFORE removing the gate, so the site
      // is never visible between the two — no flash before the splash.
      showSplash(haus, function () {
        document.body.classList.remove("is-gated");
      });
      gate.remove();
    });
    document.body.appendChild(gate);
    trk("Gate Shown");
  }

  // ---- feature flags (settings.json, managed from /admin) ----
  fetch(ROOT + "settings.json?v=" + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (s) {
      document.documentElement.dataset.training = s.training ? "on" : "off";
      document.documentElement.dataset.hiring = s.hiring ? "on" : "off";
      document.documentElement.dataset.ba = s.beforeafter === false ? "off" : "on";
      // dark-scrim opacity over the "queens" background photo (0–1, from /admin)
      if (s.queensScrim != null) document.documentElement.style.setProperty("--queens-scrim", s.queensScrim);
      var measuring = window.self !== window.top || /[?&]measure=/.test(location.search);
      if (/trade\.html$/.test(location.pathname) && !s.training && !s.hiring && !measuring) {
        location.replace("index.html");
      }
    })
    .catch(function () {}); // no settings file → everything stays hidden

  // ---- boot ----
  // Both locales are live: the gate offers Canada and the US, and a saved choice
  // re-enters that locale for the tab. A ?haus=us|ca override still enters that
  // locale AND sticks for the tab (sessionStorage "hausPreview") so a locale can
  // be linked to / QA'd directly without the gate.
  var qHaus = (location.search.match(/[?&]haus=(us|ca)\b/) || [])[1];
  if (qHaus && LOC[qHaus]) { try { sessionStorage.setItem("hausPreview", qHaus); } catch (err) {} }
  var preview = null, saved = null;
  try { preview = sessionStorage.getItem("hausPreview"); } catch (err) {}
  try { saved = sessionStorage.getItem("haus"); } catch (err) {}
  // Geo landing pages carry <body data-haus-pin="ca|us">: render that locale
  // outright, never show the gate. Additive and opt-in — pages without the
  // attribute (the entire existing site) fall through to the same branches
  // as before, and the pin never touches sessionStorage.
  var pinned = document.body.getAttribute("data-haus-pin");
  if (pinned && LOC[pinned]) {
    applyLoc(pinned);
  } else if (preview && LOC[preview]) {
    applyLoc(preview);
  } else if (saved && LOC[saved]) {
    applyLoc(saved);
  } else {
    applyLoc("ca"); // default content under the gate
    showGate();
  }
  // reveal now if the current locale needs no network: CA has no overrides, and a
  // returning US visitor already had content applied synchronously from the cache.
  revealIfReady();

  // ---- booking modal — Square booking without leaving the site ----
  var bmodal = null;
  function openBooking(url) {
    if (!bmodal) {
      bmodal = document.createElement("dialog");
      bmodal.className = "bmodal";
      bmodal.innerHTML =
        '<div class="bmodal__bar">' +
          '<span class="label">Book with the Haus</span>' +
          '<div class="bmodal__actions">' +
            '<a class="bmodal__ext" target="_blank" rel="noopener">Open in new tab ↗</a>' +
            '<button class="bmodal__close" aria-label="Close booking">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 5l14 14M19 5L5 19"/></svg>' +
            "</button>" +
          "</div>" +
        "</div>" +
        '<div class="bmodal__body"></div>';
      document.body.appendChild(bmodal);
      bmodal.querySelector(".bmodal__close").addEventListener("click", function () { bmodal.close(); });
      bmodal.addEventListener("click", function (e) { if (e.target === bmodal) bmodal.close(); });
    }
    bmodal.querySelector(".bmodal__ext").href = url;
    var body = bmodal.querySelector(".bmodal__body");
    if (body.dataset.url !== url) {
      body.dataset.url = url;
      if (BOOKING.widgetScript) {
        body.innerHTML = '<div class="bmodal__widget"></div>';
        var s = document.createElement("script");
        s.src = BOOKING.widgetScript;
        s.async = true;
        body.firstElementChild.appendChild(s);
      } else {
        body.innerHTML =
          '<iframe class="bmodal__frame" src="' + url + '" title="Book an appointment" loading="eager"></iframe>';
      }
    }
    bmodal.showModal();
    trk("Booking Modal", { label: url });
  }

  document.addEventListener("click", function (e) {
    var book = e.target.closest('[data-loc-field="book"]');
    if (!book) return;
    var haus = document.body.dataset.haus || "ca";
    var url = LOC[haus].book;
    // Mangomint booking opens in its own overlay — its app.js (loaded in <head>)
    // intercepts the click on this link, so leave the event alone and let it run.
    if (/booking\.mangomint\.com/.test(url)) return;
    // Everything else (Square) opens in the on-site iframe modal.
    e.preventDefault();
    openBooking(url);
  });

  // switch location (nav) — clears the choice and re-runs the gate
  document.addEventListener("click", function (e) {
    var sw = e.target.closest("[data-switch-haus]");
    if (!sw) return;
    e.preventDefault();
    try { sessionStorage.removeItem("haus"); } catch (err) {}
    try { sessionStorage.removeItem("hausPreview"); } catch (err) {} // also drop any QA preview
    showGate();
  });

  // ---- glass menu ----
  var menu = document.querySelector(".menu");
  if (menu) {
    document.querySelectorAll("[data-menu-open]").forEach(function (b) {
      b.addEventListener("click", function () {
        menu.classList.add("is-open");
        menu.querySelector("a, button").focus({ preventScroll: true });
      });
    });
    document.querySelectorAll("[data-menu-close]").forEach(function (b) {
      b.addEventListener("click", function () { menu.classList.remove("is-open"); });
    });
    menu.addEventListener("click", function (e) {
      if (e.target.closest("a")) menu.classList.remove("is-open");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") menu.classList.remove("is-open");
    });
  }

  // ---- sticky book bar — reveals after the hero ----
  var bar = document.querySelector(".bookbar");
  var hero = document.querySelector(".fold--hero") || document.querySelector("main > section");
  if (bar && hero && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      bar.classList.toggle("is-shown", !entries[0].isIntersecting && !document.body.classList.contains("is-gated"));
    }, { threshold: 0.05 }).observe(hero);
  }

  // ---- Instagram follow popup — every page (US + CA), slides in at 15% scroll.
  // Once dismissed (or followed), stays hidden for the rest of that day; shows
  // again on a later calendar day. ----
  (function () {
    var IG = "https://www.instagram.com/beautyextensionhaus/";
    var IG_KEY = "igPopDismissed";
    function today() { var d = new Date(); return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate(); }
    try { if (localStorage.getItem(IG_KEY) === today()) return; } catch (e) {}
    var pop = el(
      '<aside class="igpop" role="dialog" aria-label="Follow Beauty Extension Haus on Instagram">' +
        '<button class="igpop__x" type="button" aria-label="Dismiss" data-track-event="IG Popup Dismiss">&times;</button>' +
        '<span class="igpop__icon" aria-hidden="true">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">' +
          '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/>' +
          '<circle cx="17.5" cy="6.5" r="1.15" fill="currentColor" stroke="none"/></svg></span>' +
        '<span class="igpop__body">' +
          '<p class="igpop__title">Follow our journey</p>' +
          '<p class="igpop__sub">Transformations, tips &amp; behind the chair.</p>' +
          '<span class="igpop__handle">@beautyextensionhaus</span>' +
        '</span>' +
        '<a class="btn igpop__cta" href="' + IG + '" target="_blank" rel="noopener" data-track-event="IG Popup Follow">Follow</a>' +
      "</aside>"
    );
    document.body.appendChild(pop);
    var shown = false, done = false;
    function finish() {
      done = true;
      try { localStorage.setItem(IG_KEY, today()); } catch (e) {}  // suppress until next day
      pop.classList.remove("is-shown");
      window.removeEventListener("scroll", onScroll);
      setTimeout(function () { if (pop.parentNode) pop.remove(); }, 650);
    }
    pop.querySelector(".igpop__x").addEventListener("click", finish);
    pop.querySelector(".igpop__cta").addEventListener("click", finish);
    function onScroll() {
      if (shown || done || document.body.classList.contains("is-gated")) return;
      var doc = document.documentElement;
      var max = doc.scrollHeight - window.innerHeight;
      if (max > 0 && window.scrollY / max >= 0.15) {
        shown = true; pop.classList.add("is-shown");
        trk("IG Popup Shown");
      }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
  })();

  /* Contact form → self-hosted receiver (deploy/contact, proxied at /api/message).
   * Replaces the old Square-hosted contact iframe. Progressive: if JS fails the
   * form just doesn't submit and the email fallback line below it still works. */
  (function () {
    var form = document.getElementById("cform");
    if (!form) return;
    var status = document.getElementById("cform-status");
    var btn = form.querySelector('button[type="submit"]');

    function say(msg, kind) {
      if (!status) return;
      status.textContent = msg;
      status.classList.remove("is-ok", "is-err");
      if (kind) status.classList.add(kind === "ok" ? "is-ok" : "is-err");
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!form.reportValidity()) return;
      var payload = {
        name: form.name.value,
        email: form.email.value,
        phone: form.phone.value,
        message: form.message.value,
        company: form.company.value,
        loc: document.body.getAttribute("data-haus") || "ca"
      };
      btn.disabled = true;
      var label = btn.textContent;
      btn.textContent = "Sending…";
      say("");
      fetch("/api/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, d: d }; });
      }).then(function (res) {
        if (res.ok && res.d && res.d.ok) {
          form.reset();
          trk("Contact Submit", { label: "contact form" });
          say("Thank you — your message is with the studio. We'll be in touch soon.", "ok");
        } else {
          say((res.d && res.d.error ? res.d.error.charAt(0).toUpperCase() + res.d.error.slice(1) : "Something went wrong") +
            ". Please try again, or email barrie@beautyextensionhaus.com.", "err");
        }
      }).catch(function () {
        say("Couldn't send just now. Please email barrie@beautyextensionhaus.com.", "err");
      }).then(function () {
        btn.disabled = false;
        btn.textContent = label;
      });
    });
  })();
})();
