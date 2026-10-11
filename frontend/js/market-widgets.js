/**
 * PoseAI Fitness Market — reference-design widgets.
 *
 * Implements the canonical product card, dynamic quantity stepper,
 * wishlist toggle, skeleton loader, and market footer matching the reference designs.
 */
"use strict";

(function () {
  var host = window.PoseAIMarket = window.PoseAIMarket || {};
  window.PoseAICartQuantities = window.PoseAICartQuantities || {};

  // ── Sync initial cart quantities ─────────────────────────────────
  function syncCartState() {
    if (!window.MarketAPI || !window.MarketAPI.cart) return;
    window.MarketAPI.cart({ silent: true })
      .then(function (data) {
        var cart = (data && data.cart) || {};
        var items = cart.items || [];
        window.PoseAICartQuantities = {};
        items.forEach(function (item) {
          window.PoseAICartQuantities[item.product_id] = item.quantity;
        });
        // Update any rendered card steppers on page
        updateAllCardButtons();
      })
      .catch(function () {
        /* offline / unauthenticated fallback */
      });
  }

  // ── String helpers ───────────────────────────────────────────────
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function money(value) {
    var num = Number(value) || 0;
    return "₹" + num.toLocaleString("en-IN");
  }

  function stars(rating) {
    var full = Math.round(Number(rating) || 0);
    var out = "";
    for (var i = 1; i <= 5; i += 1) {
      var cls = i <= full ? "text-amber-500" : "off text-slate-300";
      out += '<span class="material-symbols-outlined text-[13px] ' + cls + '">star</span>';
    }
    return out;
  }

  // ── Product image & fallback ─────────────────────────────────────
  function fallbackTile(name) {
    var brand = (name || "").split(" ").slice(0, 2).join(" ") || "PoseAI";
    return (
      '<div class="mk-fallback-tile">' +
      '<span class="material-symbols-outlined text-4xl text-blue-600">fitness_center</span>' +
      '<span class="text-[11px] font-extrabold tracking-wider text-slate-600 uppercase text-center max-w-[85%] truncate">' + escapeHtml(brand) + "</span>" +
      "</div>"
    );
  }

  function productImage(product) {
    var img = product.image || (product.image_urls && product.image_urls[0]);
    if (img) {
      return (
        '<img src="' + escapeHtml(img) + '" alt="' + escapeHtml(product.name) +
        '" loading="lazy" class="w-full h-full object-contain p-2.5 transition-transform duration-200 group-hover:scale-105" ' +
        'onerror="this.parentElement.className=\'mk-image-tile\'; this.parentElement.innerHTML=window.PoseAIMarket.fallbackTile(this.alt)" />'
      );
    }
    return fallbackTile(product.name);
  }

  // ── Badge renderer matching reference ─────────────────────────────
  function renderCardBadge(product) {
    var badgeText = product.badge;
    var color = product.badge_color || "blue";

    if (!badgeText) {
      if (product.discount_percentage && product.discount_percentage > 0) {
        badgeText = Math.round(product.discount_percentage) + "% OFF";
        color = "red";
      } else if (product.is_deal) {
        badgeText = "DEAL";
        color = "amber";
      }
    }
    if (!badgeText) return "";

    var colorClass = "mk-badge-" + color;
    return (
      '<span class="absolute top-2.5 left-2.5 z-10 mk-badge ' + colorClass + ' shadow-sm">' +
      escapeHtml(badgeText) +
      "</span>"
    );
  }

  // ── Button / Stepper renderer matching Reference Image 4 ─────────
  function renderActionButton(product) {
    var id = escapeHtml(product.id);
    if (!product.in_stock) {
      return (
        '<button type="button" class="w-full py-1.5 px-3 rounded-lg bg-slate-100 text-slate-400 text-xs font-bold cursor-not-allowed" disabled>' +
        'Out of Stock</button>'
      );
    }

    var qty = window.PoseAICartQuantities[product.id] || 0;
    if (qty > 0) {
      return (
        '<div class="mk-card-stepper" data-card-stepper="' + id + '">' +
        '<button type="button" data-stepper-dec="' + id + '" aria-label="Decrease quantity">−</button>' +
        '<span class="qty">' + qty + '</span>' +
        '<button type="button" data-stepper-inc="' + id + '" aria-label="Increase quantity">+</button>' +
        '</div>'
      );
    }

    return (
      '<button type="button" class="mk-add-btn" data-add="' + id + '">' +
      '<span class="material-symbols-outlined text-[15px]">add</span> ADD' +
      '</button>'
    );
  }

  function updateAllCardButtons() {
    var cardContainers = document.querySelectorAll("[data-product-card-id]");
    cardContainers.forEach(function (card) {
      var id = card.getAttribute("data-product-card-id");
      var btnSlot = card.querySelector("[data-action-slot]");
      if (!btnSlot) return;
      var inStock = card.getAttribute("data-in-stock") !== "false";
      var qty = window.PoseAICartQuantities[id] || 0;
      if (!inStock) return;

      if (qty > 0) {
        btnSlot.innerHTML =
          '<div class="mk-card-stepper" data-card-stepper="' + id + '">' +
          '<button type="button" data-stepper-dec="' + id + '" aria-label="Decrease quantity">−</button>' +
          '<span class="qty">' + qty + '</span>' +
          '<button type="button" data-stepper-inc="' + id + '" aria-label="Increase quantity">+</button>' +
          '</div>';
      } else {
        btnSlot.innerHTML =
          '<button type="button" class="mk-add-btn" data-add="' + id + '">' +
          '<span class="material-symbols-outlined text-[15px]">add</span> ADD' +
          '</button>';
      }
    });
  }

  // ── Canonical Reference Product Card ─────────────────────────────
  function productCard(product) {
    var id = escapeHtml(product.id);
    var href = "/fitness-market/product/" + id;
    var favActive = !!product.is_favorite;
    var favIcon = favActive ? "favorite" : "favorite_border";
    var favCls = favActive ? "active" : "";

    var heart =
      '<button type="button" class="absolute top-2.5 right-2.5 z-10 mk-fav-btn ' + favCls + '" ' +
      'aria-label="' + (favActive ? "Remove from wishlist" : "Add to wishlist") + '" ' +
      'aria-pressed="' + (favActive ? "true" : "false") + '" data-fav="' + id + '">' +
      '<span class="material-symbols-outlined text-[18px]">' + favIcon + '</span>' +
      '</button>';

    var weightLabel = product.weight_label
      ? '<span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">' + escapeHtml(product.weight_label) + '</span>'
      : '';

    var ratingVal = Number(product.rating || 4.8).toFixed(1);
    var reviewsVal = product.review_count ? '(' + (product.review_count > 999 ? (product.review_count / 1000).toFixed(1) + 'k' : product.review_count) + ')' : '';

    var discountPercent = product.discount_percentage || (product.original_price > product.price ? Math.round(((product.original_price - product.price) / product.original_price) * 100) : 0);

    return (
      '<article class="mk-product-card group relative rounded-xl border border-slate-200/90 overflow-hidden flex flex-col" data-product-card-id="' + id + '" data-in-stock="' + (product.in_stock ? "true" : "false") + '">' +
      '<div class="relative w-full aspect-[4/3] bg-slate-50 overflow-hidden flex items-center justify-center">' +
      renderCardBadge(product) +
      heart +
      '<a class="w-full h-full block flex items-center justify-center" href="' + href + '">' +
      productImage(product) +
      '</a>' +
      '</div>' +

      '<div class="p-3.5 flex flex-col flex-1 gap-1.5">' +
      '<div class="flex items-center justify-between gap-2">' +
      '<span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 truncate">' + escapeHtml(product.brand || "PoseAI") + '</span>' +
      weightLabel +
      '</div>' +

      '<a class="mk-clamp-2 text-[13px] font-bold text-slate-900 leading-snug hover:text-blue-600 transition-colors min-h-[2.3rem]" href="' + href + '">' +
      escapeHtml(product.name) +
      '</a>' +

      '<div class="flex items-center gap-1.5 pt-0.5">' +
      '<span class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-emerald-600 text-white text-[10px] font-extrabold">★ ' + ratingVal + '</span>' +
      '<span class="text-[11px] text-slate-400 font-medium">' + reviewsVal + '</span>' +
      (product.in_stock
        ? '<span class="text-[11px] font-bold text-emerald-600 ml-auto">• In Stock</span>'
        : '<span class="text-[11px] font-bold text-red-500 ml-auto">• Out of Stock</span>') +
      '</div>' +

      '<div class="mt-auto pt-2 flex items-baseline gap-2">' +
      '<span class="text-[16px] font-black text-slate-900">' + money(product.price) + '</span>' +
      (product.original_price > product.price
        ? '<span class="text-xs text-slate-400 line-through">' + money(product.original_price) + '</span>'
        : '') +
      (discountPercent > 0
        ? '<span class="text-[11px] font-bold text-emerald-600">-' + discountPercent + '% OFF</span>'
        : '') +
      '</div>' +

      '<div class="pt-2" data-action-slot>' +
      renderActionButton(product) +
      '</div>' +
      '</div>' +
      '</article>'
    );
  }

  function skeletonCard() {
    return (
      '<div class="rounded-xl border border-slate-200 overflow-hidden bg-white flex flex-col">' +
      '<div class="mk-skeleton aspect-[4/3] w-full"></div>' +
      '<div class="p-3.5 space-y-2.5 flex-1 flex flex-col">' +
      '<div class="flex justify-between"><div class="mk-skeleton h-2.5 w-1/3 rounded"></div><div class="mk-skeleton h-2.5 w-1/4 rounded"></div></div>' +
      '<div class="mk-skeleton h-4 w-5/6 rounded"></div>' +
      '<div class="mk-skeleton h-3 w-1/2 rounded"></div>' +
      '<div class="mt-auto pt-2 flex gap-2"><div class="mk-skeleton h-4 w-1/3 rounded"></div><div class="mk-skeleton h-4 w-1/4 rounded"></div></div>' +
      '<div class="mk-skeleton h-8 w-full rounded-lg mt-2"></div>' +
      '</div>' +
      '</div>'
    );
  }

  // ── Toast notification helper ────────────────────────────────────
  function toast(message, kind) {
    var existing = document.getElementById("mkToast");
    if (existing) existing.remove();
    var toastEl = document.createElement("div");
    toastEl.id = "mkToast";
    toastEl.className =
      "fixed bottom-6 left-1/2 -translate-x-1/2 z-[80] flex items-center gap-2 px-5 py-2.5 rounded-full shadow-xl text-sm font-bold text-white " +
      (kind === "error" ? "bg-red-600" : "bg-slate-900");
    toastEl.innerHTML =
      '<span class="material-symbols-outlined text-[18px]">' + (kind === "error" ? "error" : "check_circle") + "</span>" +
      escapeHtml(message);
    document.body.appendChild(toastEl);
    window.setTimeout(function () {
      toastEl.style.transition = "opacity 200ms ease";
      toastEl.style.opacity = "0";
      window.setTimeout(function () { toastEl.remove(); }, 220);
    }, 2400);
  }

  // ── Global click delegation for ADD and STEPPER ──────────────────
  function setupInteractionDelegation() {
    document.addEventListener("click", function (event) {
      // 1. ADD TO CART
      var addBtn = event.target.closest("[data-add]");
      if (addBtn) {
        event.preventDefault();
        var pid = addBtn.getAttribute("data-add");
        if (!pid) return;

        // Optimistic UI update
        window.PoseAICartQuantities[pid] = 1;
        updateAllCardButtons();
        toast("Added to cart");

        if (window.MarketAPI && window.MarketAPI.addToCart) {
          window.MarketAPI.addToCart(pid, 1)
            .then(function (res) {
              if (window.PoseAIMarket.refreshCartBadge) window.PoseAIMarket.refreshCartBadge();
              if (window.PoseAICartBadgeRefresh) window.PoseAICartBadgeRefresh();
            })
            .catch(function (err) {
              window.PoseAICartQuantities[pid] = 0;
              updateAllCardButtons();
              toast((err && err.message) || "Could not add item", "error");
            });
        }
        return;
      }

      // 2. STEPPER INCREASE
      var incBtn = event.target.closest("[data-stepper-inc]");
      if (incBtn) {
        event.preventDefault();
        var incId = incBtn.getAttribute("data-stepper-inc");
        if (!incId) return;

        var currentQty = window.PoseAICartQuantities[incId] || 1;
        var newQty = currentQty + 1;
        window.PoseAICartQuantities[incId] = newQty;
        updateAllCardButtons();

        if (window.MarketAPI && window.MarketAPI.updateQuantity) {
          window.MarketAPI.updateQuantity(incId, newQty)
            .then(function () {
              if (window.PoseAIMarket.refreshCartBadge) window.PoseAIMarket.refreshCartBadge();
              if (window.PoseAICartBadgeRefresh) window.PoseAICartBadgeRefresh();
            })
            .catch(function (err) {
              window.PoseAICartQuantities[incId] = currentQty;
              updateAllCardButtons();
              toast((err && err.message) || "Could not update quantity", "error");
            });
        }
        return;
      }

      // 3. STEPPER DECREASE
      var decBtn = event.target.closest("[data-stepper-dec]");
      if (decBtn) {
        event.preventDefault();
        var decId = decBtn.getAttribute("data-stepper-dec");
        if (!decId) return;

        var curQty = window.PoseAICartQuantities[decId] || 1;
        if (curQty <= 1) {
          // Remove from cart
          window.PoseAICartQuantities[decId] = 0;
          updateAllCardButtons();
          toast("Removed from cart");

          if (window.MarketAPI && window.MarketAPI.removeItem) {
            window.MarketAPI.removeItem(decId)
              .then(function () {
                if (window.PoseAIMarket.refreshCartBadge) window.PoseAIMarket.refreshCartBadge();
                if (window.PoseAICartBadgeRefresh) window.PoseAICartBadgeRefresh();
              })
              .catch(function (err) {
                window.PoseAICartQuantities[decId] = curQty;
                updateAllCardButtons();
                toast((err && err.message) || "Could not remove item", "error");
              });
          }
        } else {
          var updatedQty = curQty - 1;
          window.PoseAICartQuantities[decId] = updatedQty;
          updateAllCardButtons();

          if (window.MarketAPI && window.MarketAPI.updateQuantity) {
            window.MarketAPI.updateQuantity(decId, updatedQty)
              .then(function () {
                if (window.PoseAIMarket.refreshCartBadge) window.PoseAIMarket.refreshCartBadge();
                if (window.PoseAICartBadgeRefresh) window.PoseAICartBadgeRefresh();
              })
              .catch(function (err) {
                window.PoseAICartQuantities[decId] = curQty;
                updateAllCardButtons();
                toast((err && err.message) || "Could not update quantity", "error");
              });
          }
        }
        return;
      }

      // 4. WISHLIST HEART TOGGLE
      var favBtn = event.target.closest("[data-fav]");
      if (favBtn) {
        event.preventDefault();
        var favId = favBtn.getAttribute("data-fav");
        if (!favId) return;
        var isActive = favBtn.classList.contains("active");

        favBtn.classList.toggle("active", !isActive);
        var iconEl = favBtn.querySelector(".material-symbols-outlined");
        if (iconEl) iconEl.textContent = isActive ? "favorite_border" : "favorite";

        var action = isActive
          ? (window.MarketAPI.removeFavorite ? window.MarketAPI.removeFavorite(favId) : Promise.resolve())
          : (window.MarketAPI.addFavorite ? window.MarketAPI.addFavorite(favId) : Promise.resolve());

        toast(isActive ? "Removed from wishlist" : "Added to wishlist");
        action.catch(function (err) {
          favBtn.classList.toggle("active", isActive);
          if (iconEl) iconEl.textContent = isActive ? "favorite" : "favorite_border";
          toast((err && err.message) || "Wishlist action failed", "error");
        });
      }
    });
  }

  // ── Global Market Footer Matching Reference Design ───────────────
  function renderMarketFooter(rootId) {
    var root = document.getElementById(rootId || "marketFooterSlot");
    if (!root) return;
    if (root.dataset.marketFooterRendered) return;
    root.dataset.marketFooterRendered = "true";

    root.innerHTML =
      '<footer class="w-full bg-white border-t border-slate-200 mt-16 pt-12 pb-8">' +
      '<div class="max-w-7xl mx-auto px-4 md:px-10">' +
      '<div class="grid grid-cols-1 md:grid-cols-5 gap-8 pb-10 border-b border-slate-100">' +
      '<div class="md:col-span-2 space-y-3">' +
      '<div class="flex items-center gap-2">' +
      '<span class="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold">' +
      '<span class="material-symbols-outlined text-[20px]">fitness_center</span>' +
      '</span>' +
      '<span class="text-xl font-black tracking-tight text-slate-900">PoseAI</span>' +
      '</div>' +
      '<p class="text-xs text-slate-500 leading-relaxed max-w-sm">' +
      'Computer vision fitness tracking paired with high-performance sports nutrition and biometric gear. Real-time form correction meets instant athletic recovery.' +
      '</p>' +
      '</div>' +

      '<div>' +
      '<h4 class="text-xs font-black uppercase tracking-wider text-slate-900 mb-3">MARKETPLACE</h4>' +
      '<ul class="space-y-2 text-xs text-slate-600">' +
      '<li><a href="/fitness-market/products?category=protein" class="hover:text-blue-600 transition-colors">Supplements</a></li>' +
      '<li><a href="/fitness-market/products?category=accessories" class="hover:text-blue-600 transition-colors">Biometric Gear</a></li>' +
      '<li><a href="/fitness-market/products?category=apparel" class="hover:text-blue-600 transition-colors">Recovery Wear</a></li>' +
      '<li><a href="/fitness-market/products?category=deals" class="hover:text-blue-600 transition-colors">AI Nutrition Bundles</a></li>' +
      '</ul>' +
      '</div>' +

      '<div>' +
      '<h4 class="text-xs font-black uppercase tracking-wider text-slate-900 mb-3">ACCOUNT &amp; HELP</h4>' +
      '<ul class="space-y-2 text-xs text-slate-600">' +
      '<li><a href="/fitness-market/orders" class="hover:text-blue-600 transition-colors">Track Orders</a></li>' +
      '<li><a href="/profile" class="hover:text-blue-600 transition-colors">Account Settings</a></li>' +
      '<li><a href="#" class="hover:text-blue-600 transition-colors">Help Center</a></li>' +
      '<li><a href="#" class="hover:text-blue-600 transition-colors">Contact Support</a></li>' +
      '</ul>' +
      '</div>' +

      '<div>' +
      '<h4 class="text-xs font-black uppercase tracking-wider text-slate-900 mb-3">PLATFORM</h4>' +
      '<ul class="space-y-2 text-xs text-slate-600">' +
      '<li><a href="/workout" class="hover:text-blue-600 transition-colors">Pose Tracker</a></li>' +
      '<li><a href="/analysis" class="hover:text-blue-600 transition-colors">Biomech Reports</a></li>' +
      '<li><a href="#" class="hover:text-blue-600 transition-colors">Privacy Policy</a></li>' +
      '<li><a href="#" class="hover:text-blue-600 transition-colors">Terms of Service</a></li>' +
      '</ul>' +
      '</div>' +
      '</div>' +

      '<div class="pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">' +
      '<div>© 2025 PoseAI Technologies India Pvt. Ltd. All rights reserved.</div>' +
      '<div class="flex items-center gap-5">' +
      '<a href="#" class="hover:text-slate-800">Privacy</a>' +
      '<a href="#" class="hover:text-slate-800">Terms</a>' +
      '<a href="#" class="hover:text-slate-800">Security</a>' +
      '<span class="flex items-center gap-1 text-emerald-600 font-semibold">' +
      '<span class="material-symbols-outlined text-[15px]">verified_user</span> Safe Checkout' +
      '</span>' +
      '</div>' +
      '</div>' +
      '</div>' +
      '</footer>';
  }

  // Exports
  host.escapeHtml = escapeHtml;
  host.money = money;
  host.stars = stars;
  host.fallbackTile = fallbackTile;
  host.productImage = productImage;
  host.productCard = productCard;
  host.skeletonCard = skeletonCard;
  host.toast = toast;
  host.syncCartState = syncCartState;
  host.updateAllCardButtons = updateAllCardButtons;
  host.renderMarketFooter = renderMarketFooter;

  // Initial boot
  setupInteractionDelegation();
  syncCartState();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      renderMarketFooter("marketFooterSlot");
    });
  } else {
    renderMarketFooter("marketFooterSlot");
  }
})();

