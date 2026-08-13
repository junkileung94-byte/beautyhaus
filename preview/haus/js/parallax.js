/* Scroll parallax + tasteful reveals.
 * Engine: parallax-controller (the core of jscottsmith/react-scroll-parallax),
 * bundled locally at js/vendor/parallax-controller.min.js as window.ParallaxKit. */
(function () {
  "use strict";
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var mobile = matchMedia("(max-width: 40rem)").matches;
  // ≤60rem the hero media is a stacked band / centered 9:16 portrait card
  // (see haus.css); a parallax transform there knocks the card off-center.
  var heroStacked = matchMedia("(max-width: 60rem)").matches;

  /* ---- before / after drag sliders ([data-beforeafter]) ---- */
  document.querySelectorAll("[data-beforeafter]").forEach(function (root) {
    var stage = root.querySelector(".ba__stage");
    var dots = root.querySelector(".ba__dots");
    var manifest = root.dataset.beforeafter;
    var pairs = [], idx = 0, pos = 50;

    stage.innerHTML =
      '<div class="ba__after"><img alt="After"></div>' +
      '<div class="ba__before"><img alt="Before"></div>' +
      '<span class="ba__lbl is-before">Before</span>' +
      '<span class="ba__lbl is-after">After</span>' +
      '<div class="ba__handle"><span class="ba__grip">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">' +
        '<path d="M9 7l-4 5 4 5M15 7l4 5-4 5"/></svg></span></div>';
    var afterImg = stage.querySelector(".ba__after img");
    var beforeWrap = stage.querySelector(".ba__before");
    var beforeImg = beforeWrap.querySelector("img");
    var handle = stage.querySelector(".ba__handle");

    function setPos(p) {
      pos = Math.max(0, Math.min(100, p));
      beforeWrap.style.clipPath = "inset(0 " + (100 - pos) + "% 0 0)";
      handle.style.left = pos + "%";
    }
    function show(n) {
      idx = (n + pairs.length) % pairs.length;
      afterImg.src = pairs[idx].after;
      beforeImg.src = pairs[idx].before;
      if (dots) [].forEach.call(dots.children, function (d, i) {
        d.classList.toggle("is-active", i === idx);
      });
      setPos(50);
    }

    function drag(clientX) {
      var r = stage.getBoundingClientRect();
      setPos(((clientX - r.left) / r.width) * 100);
    }
    var dragging = false, userHold = false, resumeTimer = null;
    function holdOn() { userHold = true; clearTimeout(resumeTimer); }
    function holdRelease() {   // resume scroll-scrub after the user has been idle a moment
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(function () { userHold = false; }, 2500);
    }
    stage.addEventListener("pointerdown", function (e) {
      dragging = true; holdOn(); stage.setPointerCapture(e.pointerId); drag(e.clientX);
    });
    stage.addEventListener("pointermove", function (e) { if (dragging) drag(e.clientX); });
    stage.addEventListener("pointerup", function () { dragging = false; holdRelease(); });
    stage.addEventListener("pointercancel", function () { dragging = false; holdRelease(); });
    // keyboard
    stage.tabIndex = 0;
    stage.setAttribute("role", "slider");
    stage.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { holdOn(); setPos(pos - 4); holdRelease(); e.preventDefault(); }
      else if (e.key === "ArrowRight") { holdOn(); setPos(pos + 4); holdRelease(); e.preventDefault(); }
    });

    // ---- scroll scrub: sweep the reveal as the section travels through the viewport ----
    // mouse/finger always wins — scroll-drive is suspended while dragging and briefly after.
    function onScroll() {
      if (reduced || dragging || userHold) return;
      var r = stage.getBoundingClientRect();
      var vh = window.innerHeight || document.documentElement.clientHeight;
      if (r.bottom < 0 || r.top > vh) return;                 // section offscreen
      var center = r.top + r.height / 2;
      var prog = Math.max(0, Math.min(1, 1 - center / vh));   // 0 entering bottom → 1 leaving top
      setPos(6 + prog * 88);                                  // gentle 6%–94% sweep
    }
    var ticking = false;
    function schedule() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () { ticking = false; onScroll(); });
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);

    function build(list) {
      pairs = list;
      if (dots) {
        dots.innerHTML = "";
        if (pairs.length > 1) pairs.forEach(function (_, i) {
          var d = document.createElement("button");
          d.className = "ba__dot" + (i === 0 ? " is-active" : "");
          d.type = "button"; d.setAttribute("role", "tab");
          d.setAttribute("aria-label", "Transformation " + (i + 1));
          d.addEventListener("click", function () { holdOn(); show(i); holdRelease(); });
          dots.appendChild(d);
        });
      }
      show(0);
      schedule();   // set initial reveal from current scroll position
    }

    if (manifest) {
      fetch(manifest + "?v=" + Date.now())
        .then(function (r) { return r.json(); })
        .then(function (list) { if (Array.isArray(list) && list.length) build(list); })
        .catch(function () {});
    }
  });

  /* ---- fade carousels ([data-carousel]) — images from a gallery.json list ---- */
  document.querySelectorAll("[data-carousel]").forEach(function (root) {
    var frame = root.querySelector(".carousel__frame");
    var dots = root.querySelector(".carousel__dots");
    var interval = parseInt(root.dataset.interval, 10) || 3000;
    var manifest = root.dataset.gallery;

    function build(images) {
      frame.innerHTML = "";
      if (dots) dots.innerHTML = "";
      images.forEach(function (im, n) {
        var slide = document.createElement("div");
        slide.className = "carousel__slide" + (n === 0 ? " is-active" : "");
        var img = document.createElement("img");
        img.src = im.src;
        img.alt = im.alt || "";
        img.loading = n === 0 ? "eager" : "lazy";
        slide.appendChild(img);
        frame.appendChild(slide);
        if (dots) {
          var d = document.createElement("button");
          d.className = "carousel__dot" + (n === 0 ? " is-active" : "");
          d.type = "button"; d.setAttribute("role", "tab");
          d.setAttribute("aria-label", "Photo " + (n + 1));
          d.addEventListener("click", function () { go(n); restart(); });
          dots.appendChild(d);
        }
      });
      run();
    }

    var slides = [], dotEls = [], i = 0, timer = null, paused = false;
    function go(n) {
      if (!slides.length) return;
      slides[i].classList.remove("is-active");
      if (dotEls[i]) dotEls[i].classList.remove("is-active");
      i = (n + slides.length) % slides.length;
      slides[i].classList.add("is-active");
      if (dotEls[i]) dotEls[i].classList.add("is-active");
    }
    function tick() { if (!paused) go(i + 1); }
    function start() { if (!reduced && !timer && slides.length > 1) timer = setInterval(tick, interval); }
    function stop() { clearInterval(timer); timer = null; }
    function restart() { stop(); start(); }

    var wired = false;
    function wire() {
      // one-time event wiring — build()/run() can re-run on locale switches,
      // and re-adding these listeners made every tap advance 2–3 slides
      if (wired) return;
      wired = true;

      // pause on hover / focus (WCAG 2.2.2)
      root.onmouseenter = function () { paused = true; };
      root.onmouseleave = function () { paused = false; };
      root.addEventListener("focusin", function () { paused = true; });
      root.addEventListener("focusout", function () { paused = false; });
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (e) { paused = !e[0].isIntersecting; },
          { threshold: 0.2 }).observe(root);
      }
      document.addEventListener("visibilitychange", function () { paused = document.hidden; });

      // tap to advance (tap right half = next, left half = previous)
      frame.addEventListener("click", function (e) {
        if (slides.length < 2) return;
        var r = frame.getBoundingClientRect();
        go(i + (e.clientX - r.left > r.width / 2 ? 1 : -1));
        restart();
      });

      // swipe left / right (touch)
      var sx = 0, sy = 0, moved = false;
      frame.addEventListener("touchstart", function (e) {
        sx = e.touches[0].clientX; sy = e.touches[0].clientY; moved = false; paused = true;
      }, { passive: true });
      frame.addEventListener("touchmove", function (e) {
        if (Math.abs(e.touches[0].clientX - sx) > 8) moved = true;
      }, { passive: true });
      frame.addEventListener("touchend", function (e) {
        var dx = e.changedTouches[0].clientX - sx;
        var dy = e.changedTouches[0].clientY - sy;
        if (moved && Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
          go(i + (dx < 0 ? 1 : -1)); restart();
        }
        paused = false;
      }, { passive: true });
    }

    function run() {
      slides = [].slice.call(frame.querySelectorAll(".carousel__slide"));
      dotEls = dots ? [].slice.call(dots.children) : [];
      i = 0;
      if (slides.length < 2 && dots) dots.style.display = slides.length < 2 ? "none" : "";
      wire();
      restart();
    }

    function loadFor(haus) {
      var c = window.__hausContent;
      if (haus === "us" && c && c.us && Array.isArray(c.us.gallery) && c.us.gallery.length) {
        build(c.us.gallery); return;
      }
      if (manifest) {
        fetch(manifest + "?v=" + Date.now())
          .then(function (r) { return r.json(); })
          .then(function (imgs) { if (Array.isArray(imgs) && imgs.length) build(imgs); })
          .catch(function () {});
      }
    }

    if (manifest) {
      loadFor(document.body.dataset.haus || "ca");
      document.addEventListener("haus:locale", function (e) { stop(); loadFor(e.detail); });
    } else {
      run(); // static slides already in the DOM
    }
  });

  /* ---- parallax ---- */
  if (!reduced && window.ParallaxKit) {
    var controller = ParallaxKit.ParallaxController.init({ scrollAxis: "vertical" });
    var k = mobile ? 0.5 : 1;

    // photo folds — the media drifts slower than the page (classic speed effect)
    // (on mobile the hero media sits in flow above the panel — leave it still)
    document.querySelectorAll(".fold__media").forEach(function (el) {
      var hero = el.closest(".fold--hero");
      if (hero && heroStacked) return; // stacked/portrait hero card: leave it still
      controller.createElement({ el: el, props: { speed: (hero ? -5 : -9) * k, shouldAlwaysCompleteAnimation: true } });
    });
    // glass panels inside folds — a whisper of counter-drift
    document.querySelectorAll(".fold__content .glass").forEach(function (el) {
      controller.createElement({ el: el, props: { speed: 2.5 * k, shouldAlwaysCompleteAnimation: true } });
    });
    // arch figures — gentle float
    document.querySelectorAll(".head-split .figure-ph, .figure-ph--arch").forEach(function (el) {
      controller.createElement({ el: el, props: { speed: 3 * k, easing: "easeOutQuad" } });
    });
    // footer statement line — settles in with a slow rise
    document.querySelectorAll(".foot__line").forEach(function (el) {
      controller.createElement({ el: el, props: { translateY: ["24px", "0px"], opacity: [0.25, 1], shouldAlwaysCompleteAnimation: true } });
    });

    window.addEventListener("load", function () { controller.update(); });
  }

  /* ---- one-shot reveals, staggered inside their group ---- */
  var SEL = [".section__head", ".menu-sheet tbody tr", ".product", ".info-card",
             ".figure-ph", "blockquote", ".steps li", ".qa", ".form", ".wrap--narrow"];
  var els = [];
  document.querySelectorAll("main section").forEach(function (section) {
    if (section.classList.contains("fold--hero")) return; // hero has its own entrance
    var group = section.querySelectorAll(SEL.join(","));
    var i = 0;
    group.forEach(function (el) {
      if (el.closest(".rv") && el.closest(".rv") !== el) return; // no nesting
      el.classList.add("rv");
      el.style.setProperty("--rv-i", Math.min(i++, 7));
      els.push(el);
    });
  });
  // hand-authored reveals (class="rv" in the markup) keep their own --rv-i stagger
  document.querySelectorAll("main .rv").forEach(function (el) {
    if (els.indexOf(el) === -1) els.push(el);
  });
  if (reduced || !("IntersectionObserver" in window)) {
    els.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---- flourish dividers: sweep the lines in from both edges, crown lands after ---- */
  var flourishes = document.querySelectorAll(".flourish");
  if (reduced || !("IntersectionObserver" in window)) {
    flourishes.forEach(function (f) { f.classList.add("in"); });
  } else {
    var fio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); fio.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.35 });
    flourishes.forEach(function (f) { fio.observe(f); });
  }
})();
