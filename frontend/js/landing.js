/**
 * PoseAI Fitness Market — Landing Page Controller
 *
 * Implements Reference Design Image 3:
 * - Deals section with live ticking countdown
 * - Biomechanics Recommended section
 * - Featured for You section
 * - Interactive category chips (instant filter of featured section)
 * - Real API integration via MarketAPI.home() and MarketAPI.products()
 */
"use strict";

(function () {
  var api = window.MarketAPI;
  var wk = window.PoseAIMarket;

  var els = {};
  var countdownInterval = null;

  function esc(value) {
    return wk.escapeHtml(value);
  }

  function repeat(count, html) {
    var out = "";
    for (var i = 0; i < count; i += 1) out += html;
    return out;
  }

  function showSkeletons() {
    if (els.deals) els.deals.innerHTML = repeat(4, wk.skeletonCard());
    if (els.recommended) els.recommended.innerHTML = repeat(4, wk.skeletonCard());
    if (els.featured) els.featured.innerHTML = repeat(8, wk.skeletonCard());
  }

  function emptyState(message) {
    return (
      '<div class="col-span-full flex flex-col items-center justify-center gap-2 py-12 text-center rounded-2xl border border-dashed border-slate-200 bg-white px-6">' +
      '<span class="material-symbols-outlined text-3xl text-slate-400">inventory_2</span>' +
      '<p class="text-sm font-semibold text-slate-500">' + esc(message) + '</p>' +
      '</div>'
    );
  }

  function renderList(list, el, emptyMsg) {
    if (!el) return;
    if (!list || !list.length) {
      el.innerHTML = emptyState(emptyMsg || "No products found.");
      return;
    }
    el.innerHTML = list.map(function (p) {
      return wk.productCard(p);
    }).join("");
  }

  function startCountdown() {
    if (!els.dealCountdown) return;
    // Set a dynamic target 4 hours, 18 minutes from now
    var target = Date.now() + (4 * 3600 + 18 * 60 + 12) * 1000;

    function update() {
      var remaining = Math.max(0, target - Date.now());
      var h = Math.floor(remaining / 3600000);
      var m = Math.floor((remaining % 3600000) / 60000);
      var s = Math.floor((remaining % 60000) / 1000);

      var hStr = (h < 10 ? "0" : "") + h;
      var mStr = (m < 10 ? "0" : "") + m;
      var sStr = (s < 10 ? "0" : "") + s;

      els.dealCountdown.innerHTML =
        '<span class="material-symbols-outlined text-[13px]">alarm</span> Ends in ' +
        hStr + 'h : ' + mStr + 'm : ' + sStr + 's';
    }

    update();
    countdownInterval = setInterval(update, 1000);
  }

  function loadCategory(catSlug, btn) {
    // Highlight button
    if (els.chips) {
      var allBtns = els.chips.querySelectorAll("button[data-cat]");
      allBtns.forEach(function (b) {
        b.className = "px-4 py-2 rounded-full text-xs font-bold shrink-0 transition-all bg-white border border-slate-200 text-slate-700 hover:border-blue-300 hover:text-blue-600";
      });
      if (btn) {
        btn.className = "px-4 py-2 rounded-full text-xs font-black shrink-0 transition-all bg-blue-600 text-white shadow-sm";
      }
    }

    if (catSlug === "deals") {
      window.location.href = "/fitness-market/products?deals=true";
      return;
    }

    if (!catSlug) {
      // Reload default featured
      if (els.featured) els.featured.innerHTML = repeat(8, wk.skeletonCard());
      api.products({ limit: 8, sort: "popularity" })
        .then(function (res) {
          var items = (res && (res.products || res.items)) || [];
          renderList(items, els.featured, "No featured products available.");
        })
        .catch(function () {
          if (els.featured) els.featured.innerHTML = emptyState("Could not load products.");
        });
      return;
    }

    if (els.featured) els.featured.innerHTML = repeat(8, wk.skeletonCard());
    api.products({ category: catSlug, limit: 8 })
      .then(function (res) {
        var items = (res && (res.products || res.items)) || [];
        renderList(items, els.featured, "No products found in this category.");
      })
      .catch(function () {
        if (els.featured) els.featured.innerHTML = emptyState("Could not load category products.");
      });
  }

  function wireChips() {
    if (!els.chips) return;
    els.chips.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-cat]");
      if (!btn) return;
      var cat = btn.getAttribute("data-cat");
      loadCategory(cat, btn);
    });
  }

  function loadLanding() {
    showSkeletons();
    api.home()
      .then(function (data) {
        var home = (data && (data.home || data)) || {};
        var deals = home.deals || [];
        var rec = (home.recommended && home.recommended.items) || [];
        var best = home.best_sellers || [];
        var newArrivals = home.new_arrivals || [];

        renderList(deals, els.deals, "No deals currently available.");
        renderList(rec.length ? rec : best.slice(0, 4), els.recommended, "No recommendations yet.");
        renderList(best.length ? best : newArrivals, els.featured, "No featured products.");
      })
      .catch(function (err) {
        console.error("Failed to load /api/market/home:", err);
        if (els.deals) els.deals.innerHTML = emptyState("Failed to load deals.");
        if (els.recommended) els.recommended.innerHTML = emptyState("Failed to load recommendations.");
        if (els.featured) els.featured.innerHTML = emptyState("Failed to load products.");
      });
  }

  function boot() {
    els.deals = document.getElementById("landingDeals");
    els.recommended = document.getElementById("landingRecommended");
    els.featured = document.getElementById("landingFeatured");
    els.dealCountdown = document.getElementById("dealCountdown");
    els.chips = document.getElementById("categoryChips");

    startCountdown();
    wireChips();
    loadLanding();

    if (wk.renderMarketFooter) wk.renderMarketFooter("mkFooterSlot");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();