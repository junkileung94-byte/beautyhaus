/* Beauty Extension Haus — analytics tagging (Plausible, first-party proxied).
 *
 * Two jobs:
 *
 * 1. LOCALE TAG. Every event this site sends carries a `locale` property
 *    ("ca" | "us"), and every custom event name is suffixed " -ca" / " -us".
 *    The property rides on pageviews AND on Plausible's built-in `engagement`
 *    events (time-on-page + scroll depth), because the tracker copies the
 *    pageview's props onto them — so "how long / how far did US visitors read"
 *    is a property filter in the dashboard, not a separate metric.
 *    Mechanism: /js/script.pageview-props.js re-reads the `event-*` attributes
 *    on its own <script> tag at EVERY event, so writing `event-locale` here is
 *    enough. This file is a plain (non-defer) script at the end of <body>, so
 *    it always runs BEFORE the deferred tracker fires its first pageview.
 *
 * 2. CLICK TRACKING. One delegated, capturing listener classifies every link /
 *    button press into a small fixed set of event names (Book, Call, Nav, …)
 *    so no markup has to be tagged by hand. Opt out with data-track="off";
 *    override the name with data-track-event="…" and the label with
 *    data-track="…".
 *
 * Time-on-page and scroll depth need NO code here — Plausible CE v3's tracker
 * sends them natively in `engagement` events (engagement_time + scroll_depth).
 */
(function () {
  "use strict";

  var TAG = document.querySelector('script[data-domain][data-api="/api/event"]');

  // Standard Plausible queue stub: a click that happens before the deferred
  // tracker has loaded is replayed instead of dropped.
  window.plausible = window.plausible || function () {
    (window.plausible.q = window.plausible.q || []).push(arguments);
  };

  // ---- locale ----------------------------------------------------------
  // body[data-track-loc] (hard pin, e.g. the Sarasota waitlist page)
  //   → body[data-haus] (set by haus.js at boot, before this file runs)
  //   → body[data-haus-pin] (geo landing pages) → the QA/session choice → ca.
  function readLoc() {
    var b = document.body, l = "";
    if (b) {
      l = b.getAttribute("data-track-loc") || b.getAttribute("data-haus") ||
          b.getAttribute("data-haus-pin") || "";
    }
    if (!l) {
      try { l = sessionStorage.getItem("hausPreview") || sessionStorage.getItem("haus") || ""; } catch (e) {}
    }
    return String(l).toLowerCase() === "us" ? "us" : "ca";
  }

  var LOC = readLoc();
  function tag(l) { if (TAG) TAG.setAttribute("event-locale", l); }
  tag(LOC);

  // haus.js fires this whenever a locale is applied (gate choice, nav switch,
  // late content refresh). Only a real CHANGE counts as new browsing: re-tag and
  // send a fresh pageview, which also flushes the previous page's engagement.
  document.addEventListener("haus:locale", function (e) {
    var l = String(e.detail || "").toLowerCase() === "us" ? "us" : "ca";
    if (l === LOC) return;
    LOC = l;
    tag(l);
    window.plausible("pageview");
  });

  // ---- helpers ---------------------------------------------------------
  function pagePath() {
    return (location.pathname || "/").replace(/index\.html$/, "") || "/";
  }
  function clean(s, max) {
    return String(s || "").replace(/\s+/g, " ").trim().slice(0, max || 60);
  }

  /* Send one custom event. Name gets the locale suffix; props always carry the
   * page it happened on. window.hausTrack(name, props) is the public hook —
   * haus.js and page-level scripts call it for things a click can't express
   * (form successes, modal opens). */
  function track(name, props) {
    if (!name) return;
    var p = { page: pagePath() };
    if (props) {
      for (var k in props) {
        var v = clean(props[k], 300);   // room for a full URL in `href`
        if (v) p[k] = v;
      }
    }
    window.plausible(name + " -" + LOC, { props: p });
  }
  window.hausTrack = track;

  // drain anything haus.js queued before this file ran (e.g. "Gate Shown")
  var q = window.__hausTrackQ || [];
  for (var i = 0; i < q.length; i++) track(q[i][0], q[i][1]);
  window.__hausTrackQ = { push: function (a) { track(a[0], a[1]); } };

  // ---- click classification -------------------------------------------
  var HOST = location.hostname;

  function kindOf(node, raw, anchor) {
    var explicit = node.closest("[data-track-event]");
    if (explicit) return explicit.getAttribute("data-track-event");
    if (node.closest(".gate__choice")) return "Gate Choice";
    if (node.closest("[data-switch-haus]")) return "Locale Switch";
    if (node.closest('[data-loc-field="book"]') || /squareup\.com|mangomint\.com/.test(raw)) return "Book";
    if (node.hasAttribute("data-waitlist") || node.closest("[data-waitlist]") || /(^|\/)waitlist\/?$/.test(raw)) return "Waitlist Open";
    if (node.closest("[data-menu-open]")) return "Menu Open";
    if (node.closest("[data-menu-close]")) return "Menu Close";
    if (/^tel:/i.test(raw)) return "Call";
    if (/^mailto:/i.test(raw)) return "Email";
    if (/instagram\.com/i.test(raw)) return "Instagram";
    if (/facebook\.com|tiktok\.com|youtube\.com|pinterest\./i.test(raw)) return "Social";
    if (anchor && /^https?:$/i.test(anchor.protocol) && anchor.hostname && anchor.hostname !== HOST) return "Outbound";
    if (raw) return "Nav";
    return "Button";
  }

  function labelOf(node, raw) {
    // innerText, not textContent: stacked spans (the gate cards, bookbar) would
    // otherwise concatenate into "CanadaBarrie · OntarioAward-winning studio".
    return clean(node.getAttribute("data-track")) ||
           clean(node.getAttribute("aria-label")) ||
           clean(node.innerText || node.textContent) ||
           clean(node.getAttribute("title")) ||
           clean(raw);
  }

  var lastNode = null, lastAt = 0;

  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var node = t.closest('a[href], button, summary, [role="button"], [data-track], [data-track-event]');
    if (!node) return;
    if (node.getAttribute("data-track") === "off" || node.closest('[data-track="off"]')) return;

    // one press = one event (label→control re-dispatch, nested handlers)
    var now = +new Date();
    if (node === lastNode && now - lastAt < 400) return;
    lastNode = node; lastAt = now;

    var anchor = node.tagName === "A" ? node : node.closest("a[href]");
    var raw = (anchor && anchor.getAttribute("href")) || "";
    var section = node.closest("[data-section]");
    var bio = node.closest("[data-bio-id]");   // link-in-bio tiles
    track(kindOf(node, raw, anchor), {
      label: labelOf(node, raw),
      section: section && section.getAttribute("data-section"),
      href: /^https?:/i.test(raw) ? raw : "",
      bio_id: bio && bio.getAttribute("data-bio-id"),
      bio_pos: bio && bio.getAttribute("data-bio-pos")
    });
  }, true);

  // Form submit ATTEMPTS (the matching success events are sent explicitly by
  // haus.js / the page script, so attempt-vs-success is visible).
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!f || f.tagName !== "FORM") return;
    track("Form Submit", { label: f.id || f.getAttribute("name") || f.className || "form" });
  }, true);
})();
