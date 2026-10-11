/**
 * PoseAI Fitness Market — orders controller.
 *
 * Two modes on one page:
 *   - no `id`  → renders the order history list (GET /api/market/orders)
 *   - `id`     → renders one order's detail (GET /api/market/orders/<id>)
 * The id is read from `?id=` in the URL; it also falls back to the last
 * path segment so `/fitness-market/order/<id>` works without a query string.
 *
 * Every number (order number, dates, totals, item counts) comes from the
 * API. Status/payment chips always reflect the server fields, and payment
 * is honestly surfaced as pending when the server says so.
 */
"use strict";

(function () {
  var api = window.MarketAPI;
  var wk = window.PoseAIMarket;

  var els = {};
  var orderId = "";

  function money(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN");
  }

  function show(element) {
    element.classList.remove("hidden");
  }

  function hide(element) {
    element.classList.add("hidden");
  }

  function statusChip(label, tone) {
    var cls = tone === "pending"
      ? "bg-tertiary-container text-on-tertiary-container"
      : tone === "error"
        ? "bg-error-container text-on-error-container"
        : "bg-secondary-container text-on-secondary-container";
    return '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-extrabold uppercase tracking-wide ' + cls + '">' +
      '<span class="w-1.5 h-1.5 rounded-full bg-current"></span>' + wk.escapeHtml(label) +
      "</span>";
  }

  function orderDate(iso) {
    if (!iso) return "";
    var date = new Date(iso);
    if (isNaN(date.getTime())) return wk.escapeHtml(iso);
    var days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var hh = date.getHours();
    var mm = date.getMinutes();
    var ampm = hh >= 12 ? "pm" : "am";
    hh = hh % 12;
    if (hh === 0) hh = 12;
    var pad = function (n) { return n < 10 ? "0" + n : String(n); };
    var out = days[date.getDay()] + ", " + date.getDate() + " " + months[date.getMonth()] + " " + date.getFullYear();
    return out + " • " + hh + ":" + pad(mm) + " " + ampm;
  }

  function paymentTone(order) {
    var status = (order.payment_status || "").toUpperCase();
    if (status === "PAID") return "ok";
    if (status === "FAILED") return "error";
    return "pending";
  }

  function orderTone(order) {
    var status = (order.status || "").toUpperCase();
    if (status === "CANCELLED" || status === "FAILED") return "error";
    if (status === "CONFIRMED" || status === "DELIVERED" || status === "SHIPPED") return "ok";
    return "pending";
  }

  // ── list mode ──────────────────────────────────────────────────

  function paymentChip(order) {
    var tone = paymentTone(order);
    if (tone === "ok") return statusChip(order.payment_label || "Paid", "ok");
    if (tone === "error") return statusChip(order.payment_label || "Payment failed", "error");
    return statusChip(order.payment_label || "Payment pending", "pending");
  }

  function orderCard(order) {
    var href = "/fitness-market/order/" + wk.escapeHtml(order.id);
    var address = order.shipping_address || {};
    var chips =
      statusChip(order.status_label || order.status, orderTone(order)) +
      paymentChip(order);
    return (
      '<a class="group block bg-surface-container-lowest rounded-xl border border-surface-container-high p-5 hover:border-primary hover:shadow-sm transition-all" href="' + href + '">' +
      '<div class="flex items-start justify-between gap-3">' +
      '<div class="min-w-0">' +
      '<p class="text-[11px] font-extrabold uppercase tracking-widest text-primary">' + wk.escapeHtml(order.order_number) + "</p>" +
      '<p class="text-xs text-on-surface-variant mt-1">' + orderDate(order.created_at) + "</p>" +
      "</div>" +
      '<span class="material-symbols-outlined text-[20px] text-on-surface-variant group-hover:text-primary transition-colors">chevron_right</span>' +
      "</div>" +
      '<div class="flex flex-wrap items-center gap-2 mt-4">' + chips + "</div>" +
      '<div class="flex items-center justify-between mt-4 pt-3 border-t border-surface-container-high">' +
      '<span class="text-xs text-on-surface-variant">' + order.item_count + " item" + (order.item_count === 1 ? "" : "s") + " • " + wk.escapeHtml(address.city || "—") + "</span>" +
      '<span class="text-base font-extrabold text-on-surface">' + money(order.total) + "</span>" +
      "</div>" +
      "</a>"
    );
  }

  function renderList(payload) {
    els.title.textContent = "Orders";
    els.sub.textContent = "Every order placed on your PoseAI Fitness Market account.";
    var crumb = document.getElementById("ordersCrumb");
    if (crumb) crumb.setAttribute("href", "/fitness-market");

    hide(els.error);
    hide(els.loading);
    show(els.listView);

    var orders = (payload && payload.orders) || [];
    if (orders.length === 0) {
      hide(els.grid);
      show(els.empty);
      return;
    }
    hide(els.empty);
    show(els.grid);
    var cards = [];
    for (var i = 0; i < orders.length; i += 1) cards.push(orderCard(orders[i]));
    els.grid.innerHTML = cards.join("");
  }

  // ── detail mode ────────────────────────────────────────────────

  function lineItem(item) {
    var pid = wk.escapeHtml(item.product_id);
    var href = "/fitness-market/product/" + pid;
    var image = item.image_url
      ? '<img class="w-full h-full object-cover" src="' + wk.escapeHtml(item.image_url) + '" alt="' + wk.escapeHtml(item.name) + '" loading="lazy" onerror="this.parentElement.innerHTML=window.PoseAIMarket.fallbackTile(this.alt)">'
      : wk.fallbackTile(item.name);
    return (
      '<li class="flex gap-3 py-3 border-b border-surface-container-high last:border-0">' +
      '<a class="w-16 h-16 rounded-xl overflow-hidden mk-image-tile shrink-0" href="' + href + '">' + image + "</a>" +
      '<div class="flex-1 min-w-0">' +
      '<span class="block text-[9px] font-bold uppercase tracking-widest text-primary">' + wk.escapeHtml(item.brand) + "</span>" +
      '<a class="mk-clamp-2 block text-xs font-semibold text-on-surface leading-snug hover:text-primary transition-colors" href="' + href + '">' + wk.escapeHtml(item.name) + "</a>" +
      '<p class="text-xs text-on-surface-variant mt-1">' + item.quantity + " × " + money(item.price) + "</p>" +
      "</div>" +
      '<span class="text-sm font-extrabold text-on-surface shrink-0">' + money(item.line_total) + "</span>" +
      "</li>"
    );
  }

  function addressBlock(address) {
    var lines = [];
    if (address && address.full_name) lines.push('<p class="font-extrabold text-on-surface">' + wk.escapeHtml(address.full_name) + "</p>");
    if (address && address.line1) lines.push("<p>" + wk.escapeHtml(address.line1) + "</p>");
    if (address && address.line2) lines.push("<p>" + wk.escapeHtml(address.line2) + "</p>");
    var cityState = [];
    if (address && address.city) cityState.push(wk.escapeHtml(address.city));
    if (address && address.state) cityState.push(wk.escapeHtml(address.state));
    if (address && address.pincode) cityState.push(wk.escapeHtml(address.pincode));
    if (cityState.length) lines.push("<p>" + cityState.join(", ") + "</p>");
    if (address && address.phone) lines.push('<p class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[14px]">call</span>' + wk.escapeHtml(address.phone) + "</p>");
    if (lines.length === 0) lines.push('<p class="text-on-surface-variant">No shipping address recorded.</p>');
    return '<div class="text-sm text-on-surface-variant leading-relaxed space-y-0.5">' + lines.join("") + "</div>";
  }

  function totalsBlock(order) {
    var discountRow = order.discount > 0
      ? '<div class="flex justify-between"><span class="text-on-surface-variant">Discount</span><span class="font-semibold text-secondary">- ' + money(order.discount) + "</span></div>"
      : "";
    return (
      '<div class="space-y-2 text-sm">' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Subtotal</span><span class="font-semibold text-on-surface">' + money(order.subtotal) + "</span></div>" +
      discountRow +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Delivery</span><span class="font-semibold ' + (order.delivery_fee > 0 ? "text-on-surface" : "text-secondary") + '">' + (order.delivery_fee > 0 ? money(order.delivery_fee) : "FREE") + "</span></div>" +
      "</div>" +
      '<div class="h-px bg-surface-container-high my-2.5"></div>' +
      '<div class="flex justify-between items-baseline">' +
      '<span class="font-bold text-on-surface">Total</span>' +
      '<span class="text-lg font-extrabold text-on-surface">' + money(order.total) + "</span>" +
      "</div>" +
      '<p class="text-[11px] text-on-surface-variant">' + order.item_count + " item(s) • " + wk.escapeHtml(order.currency || "INR") + "</p>"
    );
  }

  function renderDetail(order) {
    els.title.textContent = "Order Details";
    els.sub.textContent = "Order " + (order.order_number || "") + " — every line and total is a snapshot from when the order was placed.";
    var crumb = document.getElementById("ordersCrumb");
    if (crumb) crumb.setAttribute("href", "/fitness-market");

    hide(els.error);
    hide(els.loading);
    show(els.detailView);

    var items = (order.items || []).map(lineItem).join("");
    var paymentLabel = (order.payment_label || "Payment pending").toLowerCase() === "payment pending" || (order.payment_status || "").toUpperCase() === "PENDING"
      ? "We'll take payment once the payment gateway is integrated — nothing has been charged."
      : wk.escapeHtml(order.payment_label || "");

    els.detailBody.innerHTML =
      '<div class="grid grid-cols-1 lg:grid-cols-[1fr_20rem] gap-6 items-start">' +

      '<div class="space-y-6 min-w-0">' +

      '<section class="bg-surface-container-lowest rounded-xl border border-surface-container-high p-5 shadow-sm">' +
      '<h2 class="text-sm font-extrabold text-on-surface mb-3">Items</h2>' +
      '<ul class="divide-y divide-surface-container-high">' + items + "</ul>" +
      "</section>" +

      '<section class="bg-surface-container-lowest rounded-xl border border-surface-container-high p-5 shadow-sm">' +
      '<h2 class="text-sm font-extrabold text-on-surface mb-3">Shipping address</h2>' +
      addressBlock(order.shipping_address) +
      "</section>" +

      "</div>" +

      '<aside class="lg:sticky lg:top-24 space-y-4">' +

      '<section class="bg-surface-container-lowest rounded-xl border border-surface-container-high p-5 shadow-sm space-y-3">' +
      '<h2 class="text-sm font-extrabold text-on-surface">Order summary</h2>' +
      '<div class="flex flex-wrap items-center gap-2">' +
      (orderTone(order) === "ok" ? statusChip(order.status_label || order.status, "ok") : "") +
      (orderTone(order) === "error" ? statusChip(order.status_label || order.status, "error") : "") +
      (orderTone(order) !== "ok" && orderTone(order) !== "error" ? statusChip(order.status_label || order.status, "pending") : "") +
      "</div>" +
      '<div class="flex flex-wrap items-center gap-2">' +
      (paymentTone(order) === "pending" ? statusChip("Payment pending", "pending") : "") +
      (paymentTone(order) === "ok" ? statusChip("Payment " + (order.payment_status || "").toLowerCase(), "ok") : "") +
      (paymentTone(order) === "error" ? statusChip("Payment failed", "error") : "") +
      "</div>" +
      '<p class="text-xs text-on-surface-variant mt-2">' + paymentLabel + "</p>" +
      '<p class="text-xs text-on-surface-variant">' + orderDate(order.created_at) + "</p>" +
      "</section>" +

      '<section class="bg-surface-container-lowest rounded-xl border border-surface-container-high p-5 shadow-sm">' +
      totalsBlock(order) +
      "</section>" +

      "</aside>" +
      "</div>";
  }

  // ── fetch ──────────────────────────────────────────────────────

  function readOrderId() {
    var params = new URLSearchParams(window.location.search);
    var fromQuery = (params.get("id") || "").trim();
    if (fromQuery) return fromQuery;
    var parts = window.location.pathname.split("/").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function showError(message) {
    hide(els.loading);
    if (message && els.errorMsg) els.errorMsg.textContent = message;
    show(els.error);
  }

  function loadList() {
    show(els.loading);
    hide(els.error);
    api.orders()
      .then(function (payload) {
        renderList((payload && payload.orders) ? payload : { orders: [], count: 0 });
      })
      .catch(function (error) {
        if (error && error.code === "UNAUTHENTICATED") return;
        showError((error && error.message) || "We couldn't reach the orders feed. Check your connection and try again.");
        if (typeof console !== "undefined" && console.error) {
          console.error("Loading /api/market/orders failed:", error);
        }
      });
  }

  function loadDetail() {
    show(els.loading);
    hide(els.error);
    if (!orderId) {
      showError("That order link looks invalid.");
      return;
    }
    api.order(orderId)
      .then(function (payload) {
        renderDetail((payload && payload.order) || {});
      })
      .catch(function (error) {
        if (error && error.code === "UNAUTHENTICATED") return;
        var message = (error && error.message) || "We couldn't load this order.";
        showError(message);
        if (typeof console !== "undefined" && console.error) {
          console.error("Loading order detail failed:", error);
        }
      });
  }

  function boot() {
    els.loading = document.getElementById("ordersLoading");
    els.error = document.getElementById("ordersError");
    els.errorMsg = document.getElementById("ordersErrorMsg");
    els.listView = document.getElementById("ordersListView");
    els.detailView = document.getElementById("ordersDetailView");
    els.grid = document.getElementById("ordersGrid");
    els.empty = document.getElementById("ordersEmpty");
    els.detailBody = document.getElementById("orderDetailBody");
    els.title = document.getElementById("ordersPageTitle");
    els.sub = document.getElementById("ordersPageSub");

    var retry = document.getElementById("ordersRetryBtn");
    if (retry) retry.addEventListener("click", function () {
      if (orderId) loadDetail();
      else loadList();
    });

    if (wk && wk.renderMarketFooter) wk.renderMarketFooter("marketFooterSlot");

    orderId = readOrderId();
    if (orderId) loadDetail();
    else loadList();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();