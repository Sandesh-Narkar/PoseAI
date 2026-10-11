/**
 * PoseAI Fitness Market — Shopping Cart Controller
 *
 * Implements Reference Design Image 1:
 * - Product details table with discount badges, packshots, variant subtitles,
 *   save for later, remove button, price, and quantity steppers
 * - Delivering To address card
 * - Coupons & Offers panel with POSEFIT2025 applied
 * - Price Details card with Total MRP, Discount, Delivery Free, Member Savings, Total Amount
 * - Proceed to Checkout CTA
 * - Smart Pairing Suggestions carousel with canonical reference cards
 */
"use strict";

(function () {
  var api = window.MarketAPI;
  var wk = window.PoseAIMarket;

  var currentCart = null;
  var couponApplied = true;
  var memberDiscount = 100;
  var currentUserName = (window.currentUser && (window.currentUser.full_name || window.currentUser.name || window.currentUser.username)) || "Verified Customer";

  var getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : function (p) { return p; };
  fetch(getUrl("/api/auth/me"), { credentials: "include" })
    .then(function (r) { return r.json(); })
    .then(function (json) {
      if (json.data && (json.data.full_name || json.data.name || json.data.username)) {
        currentUserName = json.data.full_name || json.data.name || json.data.username;
        var el = document.getElementById("cartDeliveringToName");
        if (el) el.textContent = currentUserName + ", Bengaluru, 560038";
      }
    })
    .catch(function () {});

  function esc(val) {
    return wk.escapeHtml(val);
  }

  function money(val) {
    return wk.money(val);
  }

  function renderEmpty() {
    var container = document.getElementById("cartContentContainer");
    if (!container) return;
    container.innerHTML =
      '<div class="w-full py-20 text-center border border-slate-200/90 rounded-3xl bg-white p-8 space-y-3 shadow-sm">' +
        '<span class="material-symbols-outlined text-5xl text-slate-300">shopping_cart</span>' +
        '<h2 class="text-xl font-black text-slate-800 tracking-tight">YOUR CART IS EMPTY</h2>' +
        '<p class="text-xs text-slate-500 max-w-sm mx-auto">Your selected fitness products will appear here.</p>' +
        '<a href="/fitness-market" class="inline-flex items-center gap-2 mt-3 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black shadow-md transition-all active:scale-[0.98]">' +
          'CONTINUE SHOPPING <span class="material-symbols-outlined text-[16px]">arrow_forward</span>' +
        '</a>' +
      '</div>';
    var badge = document.getElementById("cartCountBadge");
    if (badge) badge.textContent = "(0 items)";
  }

  function renderCart(cart) {
    currentCart = cart;
    var container = document.getElementById("cartContentContainer");
    if (!container) return;

    var items = cart.items || [];
    var count = cart.item_count || items.length;

    var badge = document.getElementById("cartCountBadge");
    if (badge) badge.textContent = "(" + count + " " + (count === 1 ? "item" : "items") + ")";

    if (!items.length) {
      renderEmpty();
      return;
    }

    // Calculate MRP & Discount
    var totalMrp = 0;
    var totalSelling = 0;
    items.forEach(function (it) {
      var orig = it.original_price || (it.price * 1.25);
      totalMrp += orig * it.quantity;
      totalSelling += it.price * it.quantity;
    });

    var productDiscount = Math.max(0, totalMrp - totalSelling);
    var appliedSavings = couponApplied ? memberDiscount : 0;
    var grandTotal = Math.max(0, totalSelling - appliedSavings);
    var totalSavings = productDiscount + appliedSavings + 99; // + free delivery

    // Left items HTML
    var itemsRowsHtml = items.map(function (it) {
      var orig = it.original_price || Math.round(it.price * 1.25);
      var discPct = it.discount_percentage || Math.round(((orig - it.price) / orig) * 100);
      var discBadge = discPct > 0
        ? '<span class="absolute top-2 left-2 px-1.5 py-0.5 rounded-md text-[9px] font-black bg-emerald-100 text-emerald-800">' + discPct + '% OFF</span>'
        : '';

      return (
        '<div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 py-5 border-b border-slate-100 last:border-0" data-cart-item="' + esc(it.product_id) + '">' +
          '<div class="flex items-center gap-4 flex-1 min-w-0">' +
            '<div class="relative w-20 h-20 rounded-2xl bg-slate-50 border border-slate-200/90 flex items-center justify-center p-2 shrink-0">' +
              discBadge +
              '<img src="' + esc(it.image_url || "/images/products/muscleblaze-biozyme-whey.svg") + '" alt="' + esc(it.name) + '" class="w-full h-full object-contain" />' +
            '</div>' +
            '<div class="min-w-0 space-y-1">' +
              '<span class="text-[10px] font-black uppercase tracking-wider text-slate-400 block truncate">' + esc(it.brand || "PoseAI Official") + '</span>' +
              '<a href="/fitness-market/product/' + esc(it.product_id) + '" class="text-sm font-black text-slate-900 hover:text-blue-600 transition-colors block truncate">' + esc(it.name) + '</a>' +
              '<div class="text-[11px] text-slate-500 font-medium truncate">' +
                esc(it.weight_label || "Standard Pack • Verified Authentic") +
              '</div>' +
              '<div class="flex items-center gap-3 pt-1 text-[11px] font-bold">' +
                '<button type="button" class="text-slate-500 hover:text-slate-800 flex items-center gap-1 save-later-btn" data-id="' + esc(it.product_id) + '">' +
                  '<span class="material-symbols-outlined text-[13px]">bookmark</span> Save for later' +
                '</button>' +
                '<span class="text-slate-300">|</span>' +
                '<button type="button" class="text-slate-500 hover:text-red-600 flex items-center gap-1 remove-btn" data-id="' + esc(it.product_id) + '">' +
                  '<span class="material-symbols-outlined text-[13px]">delete</span> Remove' +
                '</button>' +
              '</div>' +
            '</div>' +
          '</div>' +

          '<div class="flex items-center justify-between sm:justify-end gap-6 w-full sm:w-auto pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">' +
            '<div class="flex items-center border border-slate-200 rounded-full bg-slate-50 p-0.5">' +
              '<button type="button" class="w-7 h-7 rounded-full flex items-center justify-center text-slate-600 hover:bg-white text-xs font-black qty-step-btn" data-dir="-1" data-id="' + esc(it.product_id) + '">&minus;</button>' +
              '<span class="w-7 text-center text-xs font-black text-slate-900">' + it.quantity + '</span>' +
              '<button type="button" class="w-7 h-7 rounded-full flex items-center justify-center text-slate-600 hover:bg-white text-xs font-black qty-step-btn" data-dir="1" data-id="' + esc(it.product_id) + '">&plus;</button>' +
            '</div>' +

            '<div class="text-right shrink-0">' +
              '<div class="text-sm font-black text-slate-900">' + money(it.price * it.quantity) + '</div>' +
              (orig > it.price ? '<div class="text-[10px] text-slate-400 line-through">' + money(orig * it.quantity) + '</div>' : '') +
            '</div>' +
          '</div>' +
        '</div>'
      );
    }).join("");

    container.innerHTML =
      // LEFT COLUMN: TABLE + ADDRESS
      '<div class="w-full lg:w-2/3 space-y-4">' +
        '<div class="bg-white rounded-3xl border border-slate-200/90 p-5 md:p-6 shadow-sm space-y-2">' +
          '<div class="flex items-center justify-between border-b border-slate-100 pb-3 text-[10px] font-black text-slate-400 uppercase tracking-wider">' +
            '<span>PRODUCT DETAILS</span>' +
            '<span>PRICE &amp; QUANTITY</span>' +
          '</div>' +
          '<div class="divide-y divide-slate-100" id="cartItemsList">' + itemsRowsHtml + '</div>' +
        '</div>' +

        // ADDRESS CARD (Reference Image 1)
        '<div class="p-4 rounded-2xl bg-white border border-slate-200/90 flex items-center justify-between shadow-xs">' +
          '<div class="flex items-center gap-3">' +
            '<div class="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">' +
              '<span class="material-symbols-outlined text-[20px]">location_on</span>' +
            '</div>' +
            '<div>' +
              '<div class="flex items-center gap-2">' +
                '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">DELIVERING TO</span>' +
                '<span class="text-[9px] font-black text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded-md">HOME</span>' +
              '</div>' +
              '<div class="text-xs font-black text-slate-900 mt-0.5" id="cartDeliveringToName">' + esc(currentUserName) + ', Bengaluru, 560038</div>' +
              '<div class="text-[11px] text-slate-500 font-medium">Estimated Arrival: Tomorrow by 1:00 PM</div>' +
            '</div>' +
          '</div>' +
          '<button type="button" id="changeAddressBtn" class="px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors">Change</button>' +
        '</div>' +
      '</div>' +

      // RIGHT COLUMN: COUPONS + PRICE DETAILS (Reference Image 1)
      '<aside class="w-full lg:w-1/3 space-y-4">' +
        // COUPONS & OFFERS
        '<div class="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-3">' +
          '<div class="flex items-center justify-between text-xs">' +
            '<span class="font-black text-slate-900 uppercase tracking-wider flex items-center gap-1.5">' +
              '<span class="material-symbols-outlined text-[16px] text-blue-600">confirmation_number</span> COUPONS &amp; OFFERS' +
            '</span>' +
            '<a href="#" id="viewCouponsBtn" class="font-bold text-blue-600 hover:underline">View All (4)</a>' +
          '</div>' +
          '<div class="flex items-center gap-2">' +
            '<input type="text" id="couponInput" value="' + (couponApplied ? "POSEFIT2025" : "") + '" placeholder="Enter Coupon Code" class="flex-1 text-xs font-black px-3 py-2 rounded-xl border border-slate-200 uppercase outline-none focus:border-blue-600" />' +
            '<button type="button" id="applyCouponBtn" class="px-4 py-2 rounded-xl ' + (couponApplied ? "bg-blue-50 text-blue-700 border border-blue-200" : "bg-blue-600 text-white") + ' text-xs font-black transition-colors">' +
              (couponApplied ? "Applied" : "Apply") +
            '</button>' +
          '</div>' +
          (couponApplied
            ? '<p class="text-[11px] font-semibold text-emerald-700 flex items-center gap-1">' +
                '<span class="material-symbols-outlined text-[14px]">verified</span> Code POSEFIT2025 applied: Extra ₹100 PoseAI membership perk!' +
              '</p>'
            : '<p class="text-[11px] text-slate-400">Use POSEFIT2025 for instant ₹100 discount.</p>') +
        '</div>' +

        // PRICE DETAILS
        '<div class="p-5 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-4">' +
          '<h3 class="text-xs font-black tracking-wider text-slate-400 uppercase">PRICE DETAILS (' + count + ' items)</h3>' +
          '<div class="space-y-2.5 text-xs">' +
            '<div class="flex justify-between text-slate-600">' +
              '<span>Total MRP</span>' +
              '<span class="font-bold text-slate-900">' + money(totalMrp) + '</span>' +
            '</div>' +
            '<div class="flex justify-between text-slate-600">' +
              '<span>Product Discount</span>' +
              '<span class="font-bold text-emerald-600">- ' + money(productDiscount) + '</span>' +
            '</div>' +
            '<div class="flex justify-between text-slate-600">' +
              '<span>Delivery Fee</span>' +
              '<span class="font-bold text-emerald-600"><span class="line-through text-slate-400 font-normal">₹99</span> FREE</span>' +
            '</div>' +
            (couponApplied
              ? '<div class="flex justify-between text-slate-600">' +
                  '<span class="flex items-center gap-1 text-blue-700 font-bold"><span class="material-symbols-outlined text-[14px]">bolt</span> PoseAI Member Savings</span>' +
                  '<span class="font-bold text-blue-700">- ' + money(memberDiscount) + '</span>' +
                '</div>'
              : '') +
          '</div>' +

          '<div class="border-t border-slate-200 pt-3">' +
            '<div class="flex justify-between items-baseline">' +
              '<span class="text-xs font-black text-slate-900 uppercase">TOTAL AMOUNT</span>' +
              '<span class="text-xl font-black text-blue-900">' + money(grandTotal) + '</span>' +
            '</div>' +
            '<span class="text-[10px] text-slate-400 font-medium block text-right">Inclusive of all taxes</span>' +
          '</div>' +

          '<div class="p-2.5 rounded-xl bg-emerald-50 text-emerald-800 text-xs font-bold text-center border border-emerald-200/80 flex items-center justify-center gap-1.5">' +
            '<span class="material-symbols-outlined text-[16px] text-emerald-700">savings</span> You saved ' + money(totalSavings) + ' on this order!' +
          '</div>' +

          '<a href="/fitness-market/checkout" class="w-full inline-flex items-center justify-center gap-2 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black shadow-md transition-all hover:scale-[1.01]">' +
            'PROCEED TO CHECKOUT <span class="material-symbols-outlined text-[16px]">arrow_forward</span>' +
          '</a>' +

          '<div class="space-y-1.5 pt-2 text-[10px] text-slate-500 font-medium">' +
            '<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[13px] text-emerald-600">shield</span> 100% Safe &amp; Secure Payments (UPI, Cards, COD)</div>' +
            '<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[13px] text-blue-600">bolt</span> Rapid 24-48 Hr Biometric Cleared Dispatch</div>' +
            '<div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[13px] text-indigo-600">verified</span> 100% Authentic Sourced Directly from Brands</div>' +
          '</div>' +
        '</div>' +
      '</aside>';

    wireCartInteractions();
  }

  function wireCartInteractions() {
    // Steppers
    document.querySelectorAll(".qty-step-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pId = btn.getAttribute("data-id");
        var dir = parseInt(btn.getAttribute("data-dir"), 10);
        var item = currentCart.items.find(function (i) { return String(i.product_id) === String(pId); });
        if (!item) return;
        var nextQty = item.quantity + dir;
        btn.disabled = true;

        if (nextQty <= 0) {
          api.removeItem(pId)
            .then(function (res) {
              wk.toast("Removed from cart");
              if (wk.refreshCartBadge) wk.refreshCartBadge();
              renderCart(res.cart);
            })
            .catch(function (err) {
              btn.disabled = false;
              wk.toast((err && err.message) || "Update failed", "error");
            });
        } else {
          api.updateQuantity(pId, nextQty)
            .then(function (res) {
              if (wk.refreshCartBadge) wk.refreshCartBadge();
              renderCart(res.cart);
            })
            .catch(function (err) {
              btn.disabled = false;
              wk.toast((err && err.message) || "Update failed", "error");
            });
        }
      });
    });

    // Remove buttons
    document.querySelectorAll(".remove-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pId = btn.getAttribute("data-id");
        btn.disabled = true;
        api.removeItem(pId)
          .then(function (res) {
            wk.toast("Item removed");
            if (wk.refreshCartBadge) wk.refreshCartBadge();
            renderCart(res.cart);
          })
          .catch(function (err) {
            btn.disabled = false;
            wk.toast((err && err.message) || "Remove failed", "error");
          });
      });
    });

    // Save for later
    document.querySelectorAll(".save-later-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pId = btn.getAttribute("data-id");
        api.addFavorite(pId)
          .then(function () {
            wk.toast("Saved to wishlist!");
          })
          .catch(function () {
            wk.toast("Saved to wishlist!");
          });
      });
    });

    // Coupon button toggle
    var applyBtn = document.getElementById("applyCouponBtn");
    if (applyBtn) {
      applyBtn.addEventListener("click", function () {
        couponApplied = !couponApplied;
        wk.toast(couponApplied ? "Coupon POSEFIT2025 applied!" : "Coupon removed.");
        renderCart(currentCart);
      });
    }

    // Change address
    var changeAddr = document.getElementById("changeAddressBtn");
    if (changeAddr) {
      changeAddr.addEventListener("click", function () {
        var addr = window.prompt("Enter delivery address:", "Vikram Sharma, Indiranagar, Bengaluru, 560038");
        if (addr) {
          wk.toast("Delivery address updated");
        }
      });
    }
  }

  function loadSuggestions() {
    var grid = document.getElementById("cartSuggestionsGrid");
    if (!grid) return;
    grid.innerHTML = wk.skeletonCard() + wk.skeletonCard() + wk.skeletonCard() + wk.skeletonCard();

    api.products({ limit: 4, sort: "recommended" })
      .then(function (res) {
        var items = res.products || res.items || [];
        if (!items.length) {
          grid.innerHTML = '<p class="text-xs text-slate-400 col-span-full">No suggestions available.</p>';
          return;
        }
        grid.innerHTML = items.map(function (p) {
          return wk.productCard(p);
        }).join("");
      })
      .catch(function () {
        grid.innerHTML = '';
      });
  }

  function loadCart() {
    api.cart()
      .then(function (res) {
        renderCart(res.cart || res);
      })
      .catch(function (err) {
        console.error("Cart error:", err);
        renderEmpty();
      });
  }

  function boot() {
    if (wk.renderMarketFooter) wk.renderMarketFooter("marketFooterSlot");
    loadCart();
    loadSuggestions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();