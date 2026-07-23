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
        var pr = v.play(); if (pr && pr.catch) pr.catch(function () {});
      } else if (!v.paused) { v.pause(); }
    });
  }, { threshold: [0, 0.6, 1] }) : null;

  function resolveUrl(u) { return /^(https?:|\/|data:|blob:)/.test(u) ? u : ROOT + u; }

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
      vid.addEventListener("loadeddata", function () { vid.classList.add("is-ready"); });
      if (getComputedStyle(host).position === "static") host.style.position = "relative";
      // this slot holds a video → hide its poster photo now so the old image
      // is NEVER shown (no first-paint show, no loop-seam flash). Host bg fills
      // the gap until the clip fades in.
      host.classList.add("slot-live");
      host.appendChild(vid);
      if (VID_IO) VID_IO.observe(vid);
    }
    if (vid.getAttribute("src") !== src) vid.setAttribute("src", src);
  }

  function removeSlotVideo(vid) {
    if (VID_IO) VID_IO.unobserve(vid);
    try { vid.pause(); } catch (e) {}
    var host = vid.parentElement;
    vid.remove();
    if (host && !host.querySelector("video[data-slot-video]")) host.classList.remove("slot-live");
  }

  function applyContent(haus) {
    if (!CONTENT || !CONTENT[haus]) return;
    var t = CONTENT[haus].text || {};
    Object.keys(t).forEach(function (id) {
      var el = document.querySelector('[data-edit="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
      if (el) el.innerHTML = t[id];
    });
    var img = CONTENT[haus].img || {};
    Object.keys(img).forEach(function (slot) {
      var pic = document.querySelector('picture[data-slot-pic="' + slot + '"]');
      var el = document.querySelector('img[data-slot="' + slot + '"]');
      var o = img[slot] || {};
      if (el && o.desktop) el.src = o.desktop;
      if (pic) {
        var srcEl = pic.querySelector('source[data-slot-src="' + slot + '"]');
        if (srcEl && (o.mobile || o.desktop)) srcEl.srcset = o.mobile || o.desktop;
      }
      if (o.video && !NO_MOTION) mountSlotVideo(slot, o.video, el, pic);
    });
    // drop any slot videos not wanted in this locale (e.g. after a CA/US switch)
    document.querySelectorAll("video[data-slot-video]").forEach(function (v) {
      var s = v.getAttribute("data-slot-video");
      var oo = img[s];
      if (!oo || !oo.video || NO_MOTION) removeSlotVideo(v);
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
              '<span class="gate__note">Opening 2026 — waitlist open</span>' +
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
      var b = e.target.closest("[data-haus]");
      if (!b) return;
      var haus = b.dataset.haus;
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
  var saved = null;
  try { saved = sessionStorage.getItem("haus"); } catch (err) {}
  if (saved && LOC[saved]) {
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
  }

  document.addEventListener("click", function (e) {
    var book = e.target.closest('[data-loc-field="book"]');
    if (!book) return;
    var haus = document.body.dataset.haus || "ca";
    var url = LOC[haus].book;
    // Mangomint booking opens in its own overlay — its app.js (loaded in <head>)
    // intercepts the click on this link, so leave the event alone and let it run.
    if (/booking\.mangomint\.com/.test(url)) return;
    // Everything else (US waitlist) opens in the on-site iframe modal.
    e.preventDefault();
    openBooking(url);
  });

  // switch location (nav) — clears the choice and re-runs the gate
  document.addEventListener("click", function (e) {
    var sw = e.target.closest("[data-switch-haus]");
    if (!sw) return;
    e.preventDefault();
    try { sessionStorage.removeItem("haus"); } catch (err) {}
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
        '<button class="igpop__x" type="button" aria-label="Dismiss">&times;</button>' +
        '<span class="igpop__icon" aria-hidden="true">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">' +
          '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/>' +
          '<circle cx="17.5" cy="6.5" r="1.15" fill="currentColor" stroke="none"/></svg></span>' +
        '<span class="igpop__body">' +
          '<p class="igpop__title">Follow our journey</p>' +
          '<p class="igpop__sub">Transformations, tips &amp; behind the chair.</p>' +
          '<span class="igpop__handle">@beautyextensionhaus</span>' +
        '</span>' +
        '<a class="btn igpop__cta" href="' + IG + '" target="_blank" rel="noopener">Follow</a>' +
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
      if (max > 0 && window.scrollY / max >= 0.15) { shown = true; pop.classList.add("is-shown"); }
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
