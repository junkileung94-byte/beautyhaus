/* Viola Canada theme JS — drawer, quantity, variant picker, gallery */
(function () {
  'use strict';

  /* ----- mobile drawer ----- */
  var burger = document.querySelector('[data-drawer-open]');
  var drawer = document.querySelector('[data-drawer]');
  var overlay = document.querySelector('[data-drawer-overlay]');
  function setDrawer(open) {
    if (!drawer) return;
    drawer.classList.toggle('is-open', open);
    overlay.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    document.body.style.overflow = open ? 'hidden' : '';
  }
  if (burger && drawer) {
    burger.addEventListener('click', function () { setDrawer(true); });
    overlay.addEventListener('click', function () { setDrawer(false); });
    drawer.querySelectorAll('[data-drawer-close]').forEach(function (el) {
      el.addEventListener('click', function () { setDrawer(false); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setDrawer(false);
    });
  }

  /* ----- quantity steppers ----- */
  document.querySelectorAll('.qty').forEach(function (qty) {
    var input = qty.querySelector('input');
    qty.querySelectorAll('button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var v = parseInt(input.value, 10) || 1;
        input.value = Math.max(1, v + (btn.dataset.step === 'up' ? 1 : -1));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  });

  /* ----- product variant picker ----- */
  var pdpForm = document.querySelector('[data-product-form]');
  if (pdpForm) {
    var variants = JSON.parse(document.querySelector('[data-variants-json]').textContent);
    var moneyFormat = pdpForm.dataset.moneyFormat || '${{amount}}';
    var selects = pdpForm.querySelectorAll('[data-option-select]');
    var idInput = pdpForm.querySelector('input[name="id"]');
    var priceEl = document.querySelector('[data-pdp-price]');
    var compareEl = document.querySelector('[data-pdp-compare]');
    var addBtn = pdpForm.querySelector('[data-add-to-cart]');

    function formatMoney(cents) {
      var amount = (cents / 100).toFixed(2);
      return moneyFormat.replace(/\{\{\s*amount\s*\}\}/, amount);
    }
    function currentVariant() {
      var opts = Array.prototype.map.call(selects, function (s) { return s.value; });
      return variants.find(function (v) {
        return opts.every(function (val, i) { return v.options[i] === val; });
      });
    }
    function onChange() {
      var v = currentVariant();
      if (!v) {
        addBtn.disabled = true;
        addBtn.textContent = addBtn.dataset.textUnavailable;
        return;
      }
      idInput.value = v.id;
      if (priceEl) priceEl.textContent = formatMoney(v.price);
      if (compareEl) {
        compareEl.style.display = v.compare_at_price > v.price ? '' : 'none';
        if (v.compare_at_price > v.price) compareEl.textContent = formatMoney(v.compare_at_price);
      }
      addBtn.disabled = !v.available;
      addBtn.textContent = v.available ? addBtn.dataset.textAdd : addBtn.dataset.textSoldout;
      var url = new URL(window.location);
      url.searchParams.set('variant', v.id);
      window.history.replaceState({}, '', url);
    }
    selects.forEach(function (s) { s.addEventListener('change', onChange); });
    onChange();
  }

  /* ----- PDP gallery thumbs ----- */
  var mainImg = document.querySelector('[data-pdp-image]');
  document.querySelectorAll('[data-pdp-thumb]').forEach(function (thumb) {
    thumb.addEventListener('click', function () {
      mainImg.src = thumb.dataset.src;
      mainImg.srcset = '';
      document.querySelectorAll('[data-pdp-thumb]').forEach(function (t) { t.classList.remove('is-active'); });
      thumb.classList.add('is-active');
    });
  });
})();
