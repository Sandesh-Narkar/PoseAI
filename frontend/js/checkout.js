/**
 * PoseAI Fitness Market — checkout controller.
 *
 * Loads the server-authoritative cart, renders drawer-style line items and
 * the server-computed totals, then posts the validated shipping address to
 * POST /api/market/orders. Payment is clearly presented as PENDING — no
 * amount is ever claimed to be charged, because it isn't.
 *
 * Every number on the page (item prices, subtotal, delivery fee, grand
 * total, order number) comes straight from the API.
 */
"use strict";

(function () {
  var api = window.MarketAPI;
  var wk = window.PoseAIMarket;

  var busy = false;
  var pending = false;

  var els = {};

  var PHONE_RE = /^[6-9]\d{9}$/;
  var PINCODE_RE = /^\d{6}$/;

  function money(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN");
  }

  function show(element) {
    element.classList.remove("hidden");
  }

  function hide(element) {
    element.classList.add("hidden");
  }

  function lineImage(line) {
    if (line.image_url) {
      return (
        '<img class="w-full h-full object-cover" src="' + wk.escapeHtml(line.image_url) +
        '" alt="' + wk.escapeHtml(line.name) + '" loading="lazy" ' +
        'onerror="this.parentElement.innerHTML=window.PoseAIMarket.fallbackTile(this.alt)">'
      );
    }
    return wk.fallbackTile(line.name);
  }

  // ── line items (drawer geometry) ───────────────────────────────

  function lineMarkup(line) {
    var pid = wk.escapeHtml(line.product_id);
    var href = "/fitness-market/product/" + pid;

    var controls;
    if (line.in_stock) {
      controls =
        '<div class="flex items-center gap-1.5 bg-surface-container-low rounded-lg p-1">' +
        '<button class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high transition-colors disabled:opacity-30 disabled:pointer-events-none" type="button" data-checkout-dec="' + pid + '" aria-label="Decrease quantity"><span class="material-symbols-outlined text-[15px]">remove</span></button>' +
        '<span class="mk-stepper-qty w-6 text-center font-extrabold text-on-surface text-sm">' + line.quantity + "</span>" +
        '<button class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high transition-colors disabled:opacity-30 disabled:pointer-events-none" type="button" data-checkout-inc="' + pid + '" aria-label="Increase quantity"><span class="material-symbols-outlined text-[15px]">add</span></button>' +
        "</div>";
    } else {
      controls =
        '<div class="text-[11px] font-bold text-error">' + wk.escapeHtml(line.stock_label || "Unavailable") + " — not billed</div>";
    }

    return (
      '<li class="flex gap-3 py-3 border-b border-surface-container-high last:border-0" data-checkout-node="' + pid + '">' +
      '<a class="w-16 h-16 rounded-xl overflow-hidden mk-image-tile shrink-0" href="' + href + '">' + lineImage(line) + "</a>" +
      '<div class="flex-1 min-w-0">' +
      '<div class="flex items-start justify-between gap-2">' +
      '<div class="min-w-0">' +
      '<span class="block text-[9px] font-bold uppercase tracking-widest text-primary">' + wk.escapeHtml(line.brand) + "</span>" +
      '<a class="mk-clamp-2 block text-xs font-semibold text-on-surface leading-snug hover:text-primary transition-colors" href="' + href + '">' + wk.escapeHtml(line.name) + "</a>" +
      "</div>" +
      '<button class="w-7 h-7 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-error-container hover:text-error transition-colors shrink-0" type="button" data-checkout-remove="' + pid + '" aria-label="Remove ' + wk.escapeHtml(line.name) + '"><span class="material-symbols-outlined text-[16px]">delete</span></button>' +
      "</div>" +
      '<div class="flex items-center justify-between gap-2 mt-1.5">' + controls +
      (line.in_stock
        ? '<span class="text-sm font-extrabold text-on-surface">' + money(line.line_total) + "</span>"
        : '<span class="text-xs text-on-surface-variant line-through">' + money(line.price * line.quantity) + "</span>") +
      "</div>" +
      "</div>" +
      "</li>"
    );
  }

  function renderItems(cart) {
    var items = (cart && cart.items) || [];
    els.items.innerHTML = items.map(lineMarkup).join("");
    els.checkoutTitle.textContent =
      items.length + " item" + (items.length === 1 ? "" : "s") + " · " + (cart.item_count || 0) + " units";
  }

  // ── summary (server-computed totals) ───────────────────────────

  function renderSummary(cart) {
    var deliveryNote = "";
    if (cart.delivery_fee > 0) {
      var shortfall = Math.max(0, Number(cart.free_delivery_threshold || 0) - Number(cart.total || 0));
      deliveryNote = '<p class="text-[11px] text-tertiary font-semibold mt-1">Add ' + money(shortfall) + " more for FREE delivery</p>";
    }
    var discountRow = Number(cart.discount) > 0
      ? '<div class="flex justify-between"><span class="text-on-surface-variant">Discount</span><span class="font-semibold text-secondary">- ' + money(cart.discount) + "</span></div>"
      : "";

    els.summary.innerHTML =
      '<h2 class="text-sm font-extrabold text-on-surface">Order Summary</h2>' +
      '<div class="space-y-2 text-sm">' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Subtotal</span><span class="font-semibold text-on-surface">' + money(cart.subtotal) + "</span></div>" +
      discountRow +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Delivery</span><span class="font-semibold ' + (cart.delivery_fee > 0 ? "text-on-surface" : "text-secondary") + '">' + (cart.delivery_fee > 0 ? money(cart.delivery_fee) : "FREE") + "</span></div>" +
      deliveryNote +
      "</div>" +
      '<div class="h-px bg-surface-container-high my-2.5"></div>' +
      '<div class="flex justify-between items-baseline">' +
      '<span class="font-bold text-on-surface">Grand total</span>' +
      '<span class="text-lg font-extrabold text-on-surface">' + money(cart.grand_total) + "</span></div>" +
      '<p class="text-[11px] text-on-surface-variant">' + (cart.item_count || 0) + " item(s) • " + wk.escapeHtml(cart.currency || "INR") + "</p>" +
      '<p class="flex items-center gap-1.5 text-[11px] text-on-surface-variant mt-2">' +
      '<span class="material-symbols-outlined text-[14px] text-secondary">verified</span>' +
      "Totals re-verified by the server at order time.</p>";
  }

  function render(cart) {
    hide(els.loading);
    if (!cart || !cart.items || cart.items.length === 0) {
      hide(els.layout);
      hide(els.error);
      show(els.empty);
      return;
    }
    hide(els.error);
    hide(els.empty);
    show(els.layout);
    renderItems(cart);
    renderSummary(cart);
  }

  // ── load ───────────────────────────────────────────────────────

  function load() {
    hide(els.empty);
    hide(els.error);
    show(els.loading);
    api.cart()
      .then(function (payload) {
        render((payload && payload.cart) || null);
      })
      .catch(function (error) {
        if (error && error.code === "UNAUTHENTICATED") return;
        hide(els.loading);
        hide(els.empty);
        show(els.error);
      });
  }

  // ── quantity changes (server-authoritative re-render) ──────────

  function refreshCartBadge() {
    if (wk && wk.refreshCartBadge) wk.refreshCartBadge();
  }

  function changeQuantity(productId, quantity) {
    if (busy) return;
    busy = true;
    var task;
    if (quantity < 1) {
      task = api.removeItem(productId).then(function (result) {
        wk.toast("Removed from cart");
        return result;
      });
    } else {
      task = api.updateQuantity(productId, quantity); // throws INSUFFICIENT_STOCK etc.
    }
    task
      .then(function (payload) {
        render((payload && payload.cart) || null);
        refreshCartBadge();
      })
      .catch(function (error) {
        var message =
          error && error.code === "INSUFFICIENT_STOCK" && error.details
            ? "Only " + error.details.available_quantity + " left in stock"
            : (error && error.message) || "Could not update quantity";
        wk.toast(message, "error");
        load();
      })
      .then(function () {
        busy = false;
      });
  }

  // ── address validation ─────────────────────────────────────────

  function fieldValue(id) {
    var input = document.getElementById(id);
    return input ? input.value.trim() : "";
  }

  function setError(id, message) {
    var span = document.querySelector('[data-err-for="' + id + '"]');
    if (span) {
      if (message) {
        span.textContent = message;
        span.classList.remove("hidden");
      } else {
        span.textContent = "";
        span.classList.add("hidden");
      }
    }
    return !message;
  }

  function clearErrors() {
    var fields = ["addrName", "addrPhone", "addrLine1", "addrLine2", "addrCity", "addrState", "addrPincode"];
    for (var i = 0; i < fields.length; i += 1) {
      setError(fields[i], "");
    }
    hide(els.formError);
  }

  function showFormError(message) {
    els.formErrorText.textContent = message;
    show(els.formError);
  }

  function validateAddress() {
    clearErrors();
    var valid = true;

    var name = fieldValue("addrName");
    var phone = fieldValue("addrPhone");
    var line1 = fieldValue("addrLine1");
    var city = fieldValue("addrCity");
    var state = fieldValue("addrState");
    var pincode = fieldValue("addrPincode");

    if (!name) valid = setError("addrName", "Full name is required.") && valid;
    if (!PHONE_RE.test(phone)) valid = setError("addrPhone", "Phone must be a 10-digit Indian mobile number.") && valid;
    if (!line1) valid = setError("addrLine1", "Address line 1 is required.") && valid;
    if (!city) valid = setError("addrCity", "City is required.") && valid;
    if (!state) valid = setError("addrState", "State is required.") && valid;
    if (!PINCODE_RE.test(pincode)) valid = setError("addrPincode", "Pincode must be a 6-digit number.") && valid;

    if (!valid) return null;

    var address = {
      full_name: name,
      phone: phone,
      line1: line1,
      city: city,
      state: state,
      pincode: pincode,
    };
    var line2 = fieldValue("addrLine2");
    if (line2) address.line2 = line2;
    return address;
  }

  // ── place order ────────────────────────────────────────────────

  function restoreButton() {
    pending = false;
    els.placeOrderBtn.disabled = false;
    els.placeOrderBtn.innerHTML =
      '<span class="material-symbols-outlined text-[18px]">lock</span>Place Order';
  }

  function setPending(active) {
    pending = active;
    els.placeOrderBtn.disabled = active;
    if (active) {
      els.placeOrderBtn.innerHTML =
        '<span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>Placing order…';
    }
  }

  function onPlaceOrder() {
    if (pending) return;
    var address = validateAddress();
    if (!address) {
      showFormError("Please fix the highlighted fields before placing the order.");
      return;
    }
    setPending(true);
    api.createOrder(address)
      .then(function (payload) {
        var order = (payload && payload.order) || {};
        hide(els.layout);
        hide(els.loading);
        els.successOrderNo.textContent = "Order " + (order.order_number || "") + " confirmed";
        show(els.successPanel);
        refreshCartBadge();
      })
      .catch(function (error) {
        clearErrors();
        showFormError((error && error.message) || "We couldn't place your order. Please try again.");
      })
      .then(function () {
        restoreButton();
      });
  }

  // ── wiring ─────────────────────────────────────────────────────

  function currentQuantity(productId) {
    var node = els.items.querySelector('[data-checkout-node="' + productId + '"]');
    var span = node && node.querySelector(".mk-stepper-qty");
    var value = span ? parseInt(span.textContent, 10) : 1;
    return isFinite(value) ? value : 1;
  }

  function wireItems() {
    els.items.addEventListener("click", function (event) {
      var target = event.target.closest(
        "[data-checkout-inc],[data-checkout-dec],[data-checkout-remove]"
      );
      if (!target) return;
      event.preventDefault();
      if (target.hasAttribute("data-checkout-inc")) {
        changeQuantity(target.getAttribute("data-checkout-inc"), currentQuantity(target.getAttribute("data-checkout-inc")) + 1);
      } else if (target.hasAttribute("data-checkout-dec")) {
        changeQuantity(target.getAttribute("data-checkout-dec"), currentQuantity(target.getAttribute("data-checkout-dec")) - 1);
      } else if (target.hasAttribute("data-checkout-remove")) {
        changeQuantity(target.getAttribute("data-checkout-remove"), 0);
      }
    });
  }

  function boot() {
    els.loading = document.getElementById("checkoutLoading");
    els.empty = document.getElementById("checkoutEmpty");
    els.error = document.getElementById("checkoutError");
    els.layout = document.getElementById("checkoutLayout");
    els.items = document.getElementById("checkoutItems");
    els.checkoutTitle = document.getElementById("checkoutTitle");
    els.summary = document.getElementById("checkoutSummary");
    els.placeOrderBtn = document.getElementById("placeOrderBtn");
    els.formError = document.getElementById("checkoutFormError");
    els.formErrorText = document.getElementById("checkoutFormErrorText");
    els.successPanel = document.getElementById("checkoutSuccessPanel");
    els.successOrderNo = document.getElementById("checkoutSuccessOrderNo");

    var retry = document.getElementById("checkoutRetryBtn");
    if (retry) retry.addEventListener("click", load);

    els.placeOrderBtn.addEventListener("click", onPlaceOrder);
    wireItems();

    if (wk && wk.renderMarketFooter) wk.renderMarketFooter("marketFooterSlot");

    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();