/**
 * PoseAI Fitness Market — My Favorites controller.
 *
 * Renders GET /api/market/favorites into the shared product card grid.
 * Un-favoriting a saved product removes its card in place; the remaining
 * count comes from the API response — never from the client.
 *
 * Unauthenticated (401) requests reject and api-client.js redirects to
 * /login; we just stop rendering after that.
 */
"use strict";

(function () {
  var SKELETON_COUNT = 8;

  var els = {};

  function repeat(count, html) {
    var out = "";
    for (var i = 0; i < count; i += 1) out += html;
    return out;
  }

  function show(element) {
    element.classList.remove("hidden");
  }

  function hide(element) {
    element.classList.add("hidden");
  }

  function renderSkeletons() {
    els.grid.innerHTML = repeat(SKELETON_COUNT, window.PoseAIMarket.skeletonCard());
  }

  function renderEmpty() {
    hide(els.error);
    show(els.empty);
    els.grid.innerHTML = "";
    els.count.textContent = "0 saved products";
  }

  function renderGrid(products) {
    hide(els.empty);
    hide(els.error);
    els.grid.innerHTML = products
      .map(function (product) {
        return window.PoseAIMarket.productCard(product);
      })
      .join("");
  }

  function renderError() {
    hide(els.empty);
    show(els.error);
    els.grid.innerHTML = "";
    els.count.textContent = "—";
  }

  function load() {
    renderSkeletons();
    hide(els.empty);
    hide(els.error);
    els.count.textContent = "Loading…";

    window.MarketAPI.favorites()
      .then(function (payload) {
        var products = (payload && payload.products) || [];
        var count = Number((payload && payload.count) || products.length) || 0;
        els.count.textContent = count + " saved product" + (count === 1 ? "" : "s");
        if (products.length === 0) {
          renderEmpty();
        } else {
          renderGrid(products);
        }
      })
      .catch(function (error) {
        if (error && error.code === "UNAUTHENTICATED") return;
        if (typeof console !== "undefined" && console.error) {
          console.error("Loading /api/market/favorites failed:", error);
        }
        renderError();
      });
  }

  function onFavoriteRemoved(btn) {
    btn.disabled = true;
    window.MarketAPI.removeFavorite(btn.getAttribute("data-fav"))
      .then(function (result) {
        var card = btn.closest("article");
        if (card && card.parentNode === els.grid) {
          card.parentNode.removeChild(card);
        }
        var count = Number((result && result.count) != null ? result.count : 0) || 0;
        els.count.textContent = count + " saved product" + (count === 1 ? "" : "s");
        window.PoseAIMarket.toast("Removed from favorites");
        if (count === 0 || !els.grid.querySelector("article")) {
          renderEmpty();
        }
      })
      .catch(function (error) {
        btn.disabled = false;
        window.PoseAIMarket.toast(
          (error && error.message) || "Could not update favorites",
          "error"
        );
      });
  }

  function wireCartAdds() {
    document.addEventListener("click", function (event) {
      var btn = event.target.closest ? event.target.closest("[data-add]") : null;
      if (!btn) return;
      event.preventDefault();
      var productId = btn.getAttribute("data-add");
      if (!productId || btn.disabled) return;
      btn.disabled = true;
      var original = btn.innerHTML;
      btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>Adding…';
      window.MarketAPI.addToCart(productId, 1)
        .then(function () {
          btn.innerHTML = original;
          btn.disabled = false;
          window.PoseAIMarket.toast("Added to cart");
          if (window.PoseAIMarket && window.PoseAIMarket.refreshCartBadge) {
            window.PoseAIMarket.refreshCartBadge();
          }
        })
        .catch(function (error) {
          btn.innerHTML = original;
          btn.disabled = false;
          window.PoseAIMarket.toast(
            (error && error.message) || "Could not add to cart",
            "error"
          );
        });
    });
  }

  function wireFavorites() {
    els.grid.addEventListener("click", function (event) {
      var btn = event.target.closest ? event.target.closest("[data-fav]") : null;
      if (!btn) return;
      event.preventDefault();
      onFavoriteRemoved(btn);
    });
  }

  function boot() {
    els.grid = document.getElementById("favoritesGrid");
    els.count = document.getElementById("favoritesCount");
    els.empty = document.getElementById("favoritesEmpty");
    els.error = document.getElementById("favoritesError");

    var retry = document.getElementById("favoritesRetryBtn");
    if (retry) retry.addEventListener("click", load);

    if (window.PoseAIMarket && window.PoseAIMarket.renderMarketFooter) {
      window.PoseAIMarket.renderMarketFooter("marketFooterSlot");
    }
    wireCartAdds();
    wireFavorites();

    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();