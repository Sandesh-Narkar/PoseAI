/**
 * PoseAI Fitness Market — Dynamic Universal Product Detail Controller
 *
 * Implements one single, reusable dynamic Product Details page for EVERY product
 * in the catalog (Supplements, Protein, Performance, Recovery, Training Gear,
 * Apparel, Accessories).
 *
 * Conforms strictly to:
 * - Reference Design layout and information architecture
 * - Category-adaptive rendering:
 *     * Food/Supplements: Nutrition Facts table + Nutrition KPIs + Flavor/Size pills
 *     * Training Gear/Dumbbells: Technical Specs table + Gear KPIs + Weight pills (NO nutrition)
 *     * Apparel: Sizing table + Fabric KPIs + S/M/L/XL pills (NO nutrition)
 *     * Accessories: Hardware Specs table + Hardware KPIs + Capacity pills (NO nutrition)
 * - Dynamic Frequently Bought Together / Synergy Stack
 * - Accurate stock validation & badges
 */
"use strict";

(function () {
  var api = window.MarketAPI;
  var wk = window.PoseAIMarket;

  var product = null;
  var quantity = 1;
  var selectedFlavor = "";
  var selectedSize = "";
  var selectedWeight = "";
  var activeTab = "primary";

  function esc(val) {
    if (val === null || val === undefined) return "";
    return String(val)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function money(val) {
    if (wk && wk.money) return wk.money(val);
    var num = Number(val) || 0;
    return "₹" + num.toLocaleString("en-IN");
  }

  function productIdFromUrl() {
    var searchParams = new URLSearchParams(window.location.search);
    var fromQuery = searchParams.get("id") || searchParams.get("product_id");
    if (fromQuery) return fromQuery;

    var parts = window.location.pathname.split("/").filter(Boolean);
    var last = parts[parts.length - 1];
    if (last && last !== "product" && last !== "product_detail.html") {
      return last;
    }
    return "";
  }

  function isNutritionProduct(p) {
    var cat = (p.category || "").toLowerCase();
    var ptype = (p.product_type || "").toLowerCase();
    return (
      cat === "protein" ||
      cat === "supplements" ||
      cat === "performance" ||
      cat === "vitamins" ||
      cat === "creatine" ||
      ptype === "supplement" ||
      ptype === "nutrition"
    );
  }

  function isGearProduct(p) {
    var cat = (p.category || "").toLowerCase();
    return cat === "training-gear" || cat === "gear" || cat === "equipment";
  }

  function isApparelProduct(p) {
    var cat = (p.category || "").toLowerCase();
    return cat === "apparel" || cat === "clothing" || cat === "wearables";
  }

  /* ─────────────────────────────────────────────────────────────
     1. IMAGE GALLERY
  ───────────────────────────────────────────────────────────── */
  function renderGallery(p) {
    var images = (p.image_urls && p.image_urls.length)
      ? p.image_urls
      : [p.image || p.thumbnail || "/images/products/muscleblaze-biozyme-whey.svg"];

    var badgeHtml = "";
    if (p.badge) {
      var colorClass = p.badge_color || "bg-emerald-600";
      badgeHtml += '<span class="px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider ' +
        (colorClass.startsWith("mk-") ? "bg-emerald-600 text-white" : colorClass) + ' text-white shadow-sm">' +
        esc(p.badge) + '</span>';
    }

    if (p.ai_match && p.ai_match >= 90) {
      badgeHtml += '<span class="px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider bg-blue-600 text-white shadow-sm">AI MATCH ' + p.ai_match + '%</span>';
    }

    var thumbsHtml = "";
    if (images.length > 1) {
      thumbsHtml = images.map(function (url, idx) {
        var isAct = idx === 0;
        var labels = ["Front View", "Details", "Angle / Specs", "Certificate / Pack"];
        var label = labels[idx] || ("Angle " + (idx + 1));
        return (
          '<button type="button" data-gallery-idx="' + idx + '" class="thumb-btn flex flex-col items-center gap-1 p-1 rounded-xl bg-white border-2 ' +
          (isAct ? "border-blue-600 shadow-sm" : "border-slate-200 hover:border-slate-300") + ' transition-all">' +
          '<div class="w-14 h-14 rounded-lg bg-slate-50 flex items-center justify-center p-1 overflow-hidden">' +
          '<img src="' + esc(url) + '" alt="' + esc(label) + '" class="w-full h-full object-contain" />' +
          '</div>' +
          '<span class="text-[9px] font-bold text-slate-600 truncate max-w-[60px]">' + esc(label) + '</span>' +
          '</button>'
        );
      }).join("");
    }

    return (
      '<div class="w-full lg:w-1/2 space-y-4">' +
        '<div class="relative bg-white rounded-3xl border border-slate-200/90 p-6 flex flex-col items-center justify-center aspect-square shadow-sm overflow-hidden group">' +
          '<div class="absolute top-4 left-4 z-10 flex flex-col gap-1.5">' + badgeHtml + '</div>' +
          '<div class="absolute top-4 right-4 z-10 flex items-center gap-2">' +
            '<button type="button" id="productFavBtn" data-fav="' + esc(p.id) + '" aria-pressed="' + (p.is_favorite ? "true" : "false") + '" class="w-9 h-9 rounded-full bg-white/90 backdrop-blur-sm border border-slate-200 shadow-sm flex items-center justify-center text-slate-500 hover:text-red-500 transition-colors">' +
              '<span class="material-symbols-outlined text-[20px] ' + (p.is_favorite ? "text-red-500 font-variation-fill" : "") + '">favorite</span>' +
            '</button>' +
            '<button type="button" id="shareBtn" class="w-9 h-9 rounded-full bg-white/90 backdrop-blur-sm border border-slate-200 shadow-sm flex items-center justify-center text-slate-500 hover:text-blue-600 transition-colors">' +
              '<span class="material-symbols-outlined text-[18px]">share</span>' +
            '</button>' +
          '</div>' +
          '<div class="w-full h-full flex items-center justify-center p-4">' +
            '<img id="mainGalleryImg" src="' + esc(images[0]) + '" alt="' + esc(p.name) + '" class="max-h-80 w-auto object-contain transition-transform duration-300 group-hover:scale-105" />' +
          '</div>' +
          '<div class="absolute bottom-3 right-4 inline-flex items-center gap-1 text-[11px] font-bold text-slate-400 bg-white/80 backdrop-blur px-2.5 py-1 rounded-md border border-slate-200/80">' +
            '<span class="material-symbols-outlined text-[13px]">zoom_in</span> Hover to Zoom' +
          '</div>' +
        '</div>' +
        (thumbsHtml ? '<div class="flex items-center gap-2 overflow-x-auto mk-h-scroll py-1">' + thumbsHtml + '</div>' : '') +
        '<div class="grid grid-cols-3 gap-2 pt-2 text-center">' +
          '<div class="p-3 rounded-xl bg-white border border-slate-200 shadow-xs">' +
            '<span class="material-symbols-outlined text-[20px] text-blue-600">verified</span>' +
            '<div class="text-[11px] font-black text-slate-900 mt-1">100% Authentic</div>' +
            '<div class="text-[10px] text-slate-500">Verified Brand Direct</div>' +
          '</div>' +
          '<div class="p-3 rounded-xl bg-white border border-slate-200 shadow-xs">' +
            '<span class="material-symbols-outlined text-[20px] text-emerald-600">local_shipping</span>' +
            '<div class="text-[11px] font-black text-slate-900 mt-1">Free Express</div>' +
            '<div class="text-[10px] text-slate-500">Orders above ₹999</div>' +
          '</div>' +
          '<div class="p-3 rounded-xl bg-white border border-slate-200 shadow-xs">' +
            '<span class="material-symbols-outlined text-[20px] text-indigo-600">assignment_return</span>' +
            '<div class="text-[11px] font-black text-slate-900 mt-1">7 Days Easy</div>' +
            '<div class="text-[10px] text-slate-500">Hassle-free Returns</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  /* ─────────────────────────────────────────────────────────────
     2. RIGHT-SIDE PURCHASE PANEL
  ───────────────────────────────────────────────────────────── */
  function renderPurchasePanel(p) {
    var discountBadge = p.discount_percentage > 0
      ? '<span class="px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 text-xs font-black">-' + p.discount_percentage + '% OFF</span>'
      : "";
    var origPrice = p.original_price > p.price
      ? '<span class="text-sm font-bold text-slate-400 line-through">' + money(p.original_price) + '</span>'
      : "";
    var savings = p.original_price > p.price ? (p.original_price - p.price) : 0;

    // Stock Status
    var stock = Number(p.stock_quantity) || 0;
    var stockBadge = "";
    if (stock <= 0) {
      stockBadge = '<span class="flex items-center gap-1.5 font-bold text-red-600"><span class="w-2 h-2 rounded-full bg-red-500"></span> Out of Stock</span>';
    } else if (stock <= 5) {
      stockBadge = '<span class="flex items-center gap-1.5 font-bold text-amber-600"><span class="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span> Only ' + stock + ' left in stock!</span>';
    } else {
      stockBadge = '<span class="flex items-center gap-1.5 font-bold text-emerald-600"><span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> In Stock (' + stock + ' available)</span>';
    }

    // Dynamic Variant Selectors
    var variantsHtml = "";

    // 1. Flavors (Food/Supplements only)
    if (isNutritionProduct(p) && p.flavor_options && p.flavor_options.length > 0) {
      selectedFlavor = selectedFlavor || p.flavor_options[0];
      var flavorPills = p.flavor_options.map(function (f) {
        var isAct = f === selectedFlavor;
        return (
          '<button type="button" data-flavor="' + esc(f) + '" class="flavor-btn px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ' +
          (isAct ? "border-blue-600 bg-blue-50 text-blue-700 shadow-xs" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300") + '">' +
          esc(f) + '</button>'
        );
      }).join("");

      variantsHtml += (
        '<div class="space-y-2">' +
          '<div class="flex items-center justify-between text-xs">' +
            '<span class="font-black text-slate-700 uppercase tracking-wide">Select Flavor:</span>' +
            '<span class="font-bold text-blue-600" id="activeFlavorLabel">' + esc(selectedFlavor) + '</span>' +
          '</div>' +
          '<div class="flex flex-wrap gap-2" id="flavorContainer">' + flavorPills + '</div>' +
        '</div>'
      );
    }

    // 2. Weights (Training Gear / Dumbbells)
    if (isGearProduct(p)) {
      var weightList = p.weight_options && p.weight_options.length ? p.weight_options : [];
      if (!weightList.length && p.weight_label) {
        weightList = [{ weight: p.weight_label, price: p.price, is_popular: true }];
      }
      if (weightList.length > 0) {
        selectedWeight = selectedWeight || (weightList[0].weight || weightList[0]);
        var weightPills = weightList.map(function (w) {
          var label = typeof w === "object" ? (w.weight || w.size) : w;
          var wPrice = typeof w === "object" ? w.price : null;
          var isAct = label === selectedWeight;
          return (
            '<div class="relative flex flex-col items-center">' +
            (w.is_popular ? '<span class="text-[9px] font-black text-blue-600 bg-blue-100 px-1.5 py-0.2 rounded-full mb-1">Popular Choice</span>' : '') +
            '<button type="button" data-weight="' + esc(label) + '" data-price="' + (wPrice || p.price) + '" class="weight-btn px-4 py-2 rounded-xl text-xs font-bold border transition-all ' +
            (isAct ? "border-blue-600 bg-blue-600 text-white shadow-xs" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300") + '">' +
            esc(label) + (wPrice ? ' — ' + money(wPrice) : '') + '</button>' +
            '</div>'
          );
        }).join("");

        variantsHtml += (
          '<div class="space-y-2">' +
            '<div class="flex items-center justify-between text-xs">' +
              '<span class="font-black text-slate-700 uppercase tracking-wide">Select Weight / Spec:</span>' +
              '<span class="font-bold text-blue-600" id="activeWeightLabel">' + esc(selectedWeight) + '</span>' +
            '</div>' +
            '<div class="flex flex-wrap gap-2 items-end" id="weightContainer">' + weightPills + '</div>' +
          '</div>'
        );
      }
    }

    // 3. Sizes (Nutrition sizes or Apparel sizes)
    if (p.size_options && p.size_options.length > 0) {
      selectedSize = selectedSize || (p.size_options[0].size || p.size_options[0]);
      var sizePills = p.size_options.map(function (s) {
        var label = typeof s === "object" ? s.size : s;
        var sPrice = typeof s === "object" ? s.price : null;
        var isPopular = typeof s === "object" ? Boolean(s.is_popular) : false;
        var isAct = label === selectedSize;
        return (
          '<div class="relative flex flex-col items-center">' +
          (isPopular ? '<span class="text-[9px] font-black text-blue-600 bg-blue-100 px-1.5 py-0.2 rounded-full mb-1">Most Popular</span>' : '') +
          '<button type="button" data-size="' + esc(label) + '" data-price="' + (sPrice || p.price) + '" class="size-btn px-4 py-2 rounded-xl text-xs font-bold border transition-all ' +
          (isAct ? "border-blue-600 bg-blue-600 text-white shadow-xs" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300") + '">' +
          esc(label) + (sPrice ? ' — ' + money(sPrice) : '') + '</button>' +
          '</div>'
        );
      }).join("");

      var sizeHeading = isApparelProduct(p) ? "Select Apparel Size:" : "Select Packaging Size:";
      variantsHtml += (
        '<div class="space-y-2">' +
          '<div class="flex items-center justify-between text-xs">' +
            '<span class="font-black text-slate-700 uppercase tracking-wide">' + sizeHeading + '</span>' +
            '<span class="font-bold text-blue-600" id="activeSizeLabel">' + esc(selectedSize) + '</span>' +
          '</div>' +
          '<div class="flex flex-wrap gap-2 items-end" id="sizeContainer">' + sizePills + '</div>' +
        '</div>'
      );
    }

    // PoseAI Training Recommendation Box
    var aiMatch = p.ai_match || 95;
    var recommendationHtml = (
      '<div class="p-3.5 rounded-2xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200/80 flex items-start gap-3">' +
        '<div class="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5">' +
          '<span class="material-symbols-outlined text-[20px]">bolt</span>' +
        '</div>' +
        '<div class="text-xs">' +
          '<div class="flex items-center gap-2">' +
            '<span class="font-black text-slate-900">PoseAI Training Match: ' + aiMatch + '%</span>' +
            '<span class="text-[10px] font-black text-blue-700 bg-blue-100 px-1.5 py-0.2 rounded-md">Recommended</span>' +
          '</div>' +
          '<p class="text-slate-600 font-medium text-[11px] mt-0.5">' +
            (p.target_benefit || "Optimized for your selected fitness goals and active training schedule.") +
          '</p>' +
        '</div>' +
      '</div>'
    );

    // Rate per unit / serving if food
    var unitRateHtml = "";
    if (isNutritionProduct(p)) {
      unitRateHtml = '<span class="text-xs font-bold text-slate-500 ml-auto">₹' + Math.max(1, Math.round(p.price / 30)) + ' / serving</span>';
    } else if (p.weight_label) {
      unitRateHtml = '<span class="text-xs font-bold text-slate-500 ml-auto">' + esc(p.weight_label) + '</span>';
    }

    return (
      '<div class="w-full lg:w-1/2 space-y-5 bg-white rounded-3xl border border-slate-200/90 p-6 md:p-8 shadow-sm">' +
        '<div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">' +
          '<div class="flex items-center gap-2">' +
            '<span class="inline-flex items-center gap-1 text-[11px] font-black text-blue-700 bg-blue-50 border border-blue-200/70 px-2.5 py-0.5 rounded-full uppercase">' +
              '<span class="material-symbols-outlined text-[13px]">verified</span> ' + esc(p.brand || "PoseAI") + ' OFFICIAL PARTNER' +
            '</span>' +
          '</div>' +
          '<span class="text-[11px] font-bold text-slate-400">CATEGORY: ' + esc(p.category.toUpperCase()) + '</span>' +
        '</div>' +

        '<div>' +
          '<h1 class="text-xl md:text-2xl font-black tracking-tight text-slate-900 leading-snug">' + esc(p.name) + '</h1>' +
          '<p class="text-xs text-slate-500 font-medium mt-1 leading-relaxed">' +
            esc(p.description || "Premium athletic essential engineered for performance and endurance.") +
          '</p>' +
        '</div>' +

        '<div class="flex flex-wrap items-center gap-3 text-xs">' +
          '<div class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-700 text-white font-black text-[11px]">' +
            '★ ' + (p.rating || 4.7).toFixed(1) +
          '</div>' +
          '<span class="font-bold text-slate-700">' + (p.review_count || 520).toLocaleString("en-IN") + ' Ratings</span>' +
          '<span class="text-slate-300">•</span>' +
          '<span class="text-slate-500 font-medium">Verified Biometric Feedback</span>' +
          '<span class="text-slate-300">•</span>' +
          '<span class="text-blue-600 font-bold flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">verified</span> 100% Genuine</span>' +
        '</div>' +

        '<div class="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">' +
          '<div class="flex items-baseline gap-3 flex-wrap">' +
            '<span class="text-2xl md:text-3xl font-black text-slate-900" id="detailActivePrice">' + money(p.price) + '</span>' +
            origPrice +
            discountBadge +
            unitRateHtml +
          '</div>' +
          '<div class="text-[11px] text-slate-500 font-medium">' +
            'Inclusive of all taxes ' + (savings ? '• <span class="text-emerald-700 font-bold">Save ' + money(savings) + ' today</span>' : '') +
          '</div>' +
        '</div>' +

        recommendationHtml +

        variantsHtml +

        '<div class="p-3.5 rounded-2xl bg-white border border-slate-200 space-y-2 text-xs">' +
          '<div class="flex items-center justify-between text-[11px]">' +
            stockBadge +
            '<span class="text-slate-500 font-semibold">Dispatch within <span class="text-slate-800 font-black">24 Hours</span></span>' +
          '</div>' +
          '<div class="flex items-center gap-2">' +
            '<div class="relative flex-1">' +
              '<span class="material-symbols-outlined text-[16px] text-slate-400 absolute left-3 top-2.5">location_on</span>' +
              '<input type="text" id="pincodeInput" value="560001" placeholder="Enter Pincode" class="w-full pl-8 pr-3 py-2 text-xs rounded-xl border border-slate-200 outline-none focus:border-blue-600" />' +
            '</div>' +
            '<button type="button" id="pincodeCheckBtn" class="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-black transition-colors">Check</button>' +
          '</div>' +
          '<p id="pincodeMsg" class="text-[11px] text-emerald-700 font-bold flex items-center gap-1">' +
            '<span class="material-symbols-outlined text-[13px]">local_shipping</span> Guaranteed Delivery to 560001 by Tomorrow, 11:00 AM' +
          '</p>' +
        '</div>' +

        '<div class="flex flex-wrap items-center gap-3 pt-2">' +
          '<div class="flex items-center border border-slate-300 rounded-xl bg-white p-1 shadow-xs">' +
            '<button type="button" id="detailQtyMinus" class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-100 font-black text-sm">&minus;</button>' +
            '<span id="detailQtyVal" class="w-8 text-center text-xs font-black text-slate-900">1</span>' +
            '<button type="button" id="detailQtyPlus" class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-100 font-black text-sm">&plus;</button>' +
          '</div>' +

          '<button type="button" id="detailAddToCartBtn" ' + (stock <= 0 ? "disabled" : "") + ' class="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl ' +
            (stock <= 0 ? "bg-slate-200 text-slate-400 cursor-not-allowed" : "bg-blue-50 border border-blue-600 text-blue-700 hover:bg-blue-100 shadow-xs") + ' text-xs font-black transition-all">' +
            '<span class="material-symbols-outlined text-[18px]">add_shopping_cart</span> ' + (stock <= 0 ? "OUT OF STOCK" : "ADD TO CART") +
          '</button>' +

          '<button type="button" id="detailBuyNowBtn" ' + (stock <= 0 ? "disabled" : "") + ' class="flex-1 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl ' +
            (stock <= 0 ? "bg-slate-300 text-slate-500 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700 text-white shadow-sm hover:scale-[1.01]") + ' text-xs font-black transition-all">' +
            'BUY NOW' +
          '</button>' +
        '</div>' +

        '<div class="flex items-center gap-2 text-[11px] text-slate-400 justify-center">' +
          '<span class="material-symbols-outlined text-[14px] text-emerald-600">verified_user</span>' +
          '<span>Official serial number verification. 100% genuine with invoice.</span>' +
        '</div>' +

      '</div>'
    );
  }

  /* ─────────────────────────────────────────────────────────────
     3. FREQUENTLY BOUGHT TOGETHER / SYNERGY STACK
  ───────────────────────────────────────────────────────────── */
  function renderSynergyStack() {
    var container = document.getElementById("synergyStackContainer");
    if (!container) return;

    var stack = (product && product.synergy_stack && product.synergy_stack.length > 0)
      ? product.synergy_stack
      : [];

    if (!stack.length) {
      container.innerHTML = "";
      return;
    }

    var totalStackPrice = product.price;
    var stackItemsHtml = (
      '<div class="flex items-center gap-2 p-2 rounded-xl bg-slate-50 border border-slate-200">' +
        '<img src="' + esc(product.thumbnail || (product.image_urls && product.image_urls[0])) + '" class="w-12 h-12 object-contain" alt="' + esc(product.name) + '" />' +
        '<div class="text-xs">' +
          '<span class="text-[9px] font-bold text-slate-400 block uppercase">Main Item</span>' +
          '<span class="font-bold text-slate-900 block truncate max-w-[120px]">' + esc(product.name) + '</span>' +
          '<span class="font-black text-blue-600">' + money(product.price) + '</span>' +
        '</div>' +
      '</div>'
    );

    stack.forEach(function (item) {
      totalStackPrice += (Number(item.price) || 0);
      stackItemsHtml += (
        '<span class="text-lg font-black text-slate-300">&plus;</span>' +
        '<div class="flex items-center gap-2 p-2 rounded-xl bg-slate-50 border border-slate-200">' +
          '<img src="' + esc(item.image || "/images/products/poseai-smart-thermal-shaker.svg") + '" class="w-12 h-12 object-contain" alt="' + esc(item.name) + '" />' +
          '<div class="text-xs">' +
            '<span class="text-[9px] font-bold text-slate-400 block uppercase">Synergy Match</span>' +
            '<span class="font-bold text-slate-900 block truncate max-w-[120px]">' + esc(item.name) + '</span>' +
            '<span class="font-black text-blue-600">' + money(item.price) + '</span>' +
          '</div>' +
        '</div>'
      );
    });

    var count = stack.length + 1;

    container.innerHTML =
      '<div class="p-6 rounded-3xl bg-white border border-slate-200/90 shadow-sm space-y-4">' +
        '<div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">' +
          '<div class="flex items-center gap-2">' +
            '<span class="material-symbols-outlined text-blue-600 text-[20px]">hub</span>' +
            '<span class="text-xs font-black text-blue-600 tracking-wider uppercase">SYNERGY STACK</span>' +
            '<h3 class="text-sm font-black text-slate-900">Frequently Bought Together</h3>' +
          '</div>' +
          '<span class="text-[11px] font-black text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">' +
            'Frequently paired by athletes' +
          '</span>' +
        '</div>' +

        '<div class="flex flex-col md:flex-row items-center justify-between gap-4">' +
          '<div class="flex flex-wrap items-center gap-3">' +
            stackItemsHtml +
          '</div>' +

          '<div class="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 pt-3 md:pt-0">' +
            '<div class="text-right">' +
              '<div class="text-[11px] text-slate-400 font-bold">Stack Total Price:</div>' +
              '<div class="text-lg font-black text-slate-900">' + money(totalStackPrice) + '</div>' +
            '</div>' +
            '<button type="button" id="addStackBtn" class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black shadow-sm transition-all">' +
              'ADD ' + count + ' ITEMS TO CART' +
            '</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    var addStackBtn = document.getElementById("addStackBtn");
    if (addStackBtn) {
      addStackBtn.addEventListener("click", function () {
        addStackBtn.disabled = true;
        addStackBtn.textContent = "Adding Stack…";
        api.addToCart(product.id, 1)
          .then(function () {
            wk.toast("Added stack items to cart!");
            if (wk.refreshCartBadge) wk.refreshCartBadge();
            addStackBtn.textContent = "Stack Added ✓";
            addStackBtn.className = "px-5 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-black";
          })
          .catch(function () {
            wk.toast("Could not add stack", "error");
            addStackBtn.disabled = false;
            addStackBtn.textContent = "ADD " + count + " ITEMS TO CART";
          });
      });
    }
  }

  /* ─────────────────────────────────────────────────────────────
     4. ADAPTIVE PRODUCT INFORMATION TABS
  ───────────────────────────────────────────────────────────── */
  function renderTabs() {
    var container = document.getElementById("tabsContainer");
    if (!container) return;

    var isNutr = isNutritionProduct(product);
    var isGear = isGearProduct(product);
    var isApparel = isApparelProduct(product);

    var tabLabels = [];
    if (isNutr) {
      tabLabels = [
        { id: "nutrition", label: "Nutrition & Highlights" },
        { id: "description", label: "Description & Science" },
        { id: "usage", label: "How To Use" },
        { id: "certification", label: "Quality & Certification" },
        { id: "reviews", label: "Customer Reviews (" + (product.review_count || 520) + ")" },
      ];
    } else if (isGear) {
      tabLabels = [
        { id: "specs", label: "Specifications & Build" },
        { id: "description", label: "Product Overview" },
        { id: "usage", label: "Training Guidelines" },
        { id: "reviews", label: "Customer Reviews (" + (product.review_count || 310) + ")" },
      ];
    } else if (isApparel) {
      tabLabels = [
        { id: "specs", label: "Fabric & Tech Specifications" },
        { id: "description", label: "Overview & Fit" },
        { id: "size_guide", label: "Size Guide" },
        { id: "reviews", label: "Customer Reviews (" + (product.review_count || 240) + ")" },
      ];
    } else {
      // Accessories / Recovery
      tabLabels = [
        { id: "specs", label: "Product Specifications" },
        { id: "description", label: "Description & Features" },
        { id: "usage", label: "Usage & Care" },
        { id: "reviews", label: "Customer Reviews (" + (product.review_count || 180) + ")" },
      ];
    }

    if (!tabLabels.some(function (t) { return t.id === activeTab; })) {
      activeTab = tabLabels[0].id;
    }

    // Tab buttons
    var tabsHeaderHtml = tabLabels.map(function (tab) {
      var isAct = tab.id === activeTab;
      return (
        '<button type="button" data-tab="' + esc(tab.id) + '" class="tab-nav-btn pb-3 text-xs font-black transition-colors border-b-2 ' +
        (isAct ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-900") + '">' +
        esc(tab.label) + '</button>'
      );
    }).join("");

    // KPI Cards (4 highlight boxes)
    var kpiBoxes = "";
    if (product.highlights && product.highlights.length >= 4) {
      kpiBoxes = product.highlights.slice(0, 4).map(function (h, i) {
        var bgColors = ["bg-blue-50/60 border-blue-100 text-blue-700", "bg-indigo-50/60 border-indigo-100 text-indigo-700", "bg-sky-50/60 border-sky-100 text-sky-700", "bg-emerald-50/60 border-emerald-100 text-emerald-700"];
        var color = bgColors[i % bgColors.length];
        return (
          '<div class="p-4 rounded-2xl border text-center ' + color + '">' +
            '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">' + esc(h.title) + '</span>' +
            '<div class="text-2xl font-black mt-1">' + esc(h.value) + '</div>' +
            '<span class="text-[10px] font-bold text-slate-500">' + esc(h.sub || "") + '</span>' +
          '</div>'
        );
      }).join("");
    } else if (isNutr) {
      kpiBoxes = (
        '<div class="p-4 rounded-2xl bg-blue-50/60 border border-blue-100 text-center text-blue-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">PROTEIN / SERVING</span>' +
          '<div class="text-2xl font-black mt-1">25g</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Pure Grade Concentration</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100 text-center text-indigo-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">ESSENTIAL AMINOS</span>' +
          '<div class="text-2xl font-black mt-1">11.75g</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Accelerated Muscle Recovery</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-sky-50/60 border border-sky-100 text-center text-sky-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">BCAA PROFILE</span>' +
          '<div class="text-2xl font-black mt-1">5.5g</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Prevents Muscle Breakdown</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-emerald-50/60 border border-emerald-100 text-center text-emerald-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">ADDED SUGAR</span>' +
          '<div class="text-2xl font-black mt-1">0g</div>' +
          '<span class="text-[10px] font-bold text-slate-500">100% Clean Formulation</span>' +
        '</div>'
      );
    } else if (isGear) {
      kpiBoxes = (
        '<div class="p-4 rounded-2xl bg-blue-50/60 border border-blue-100 text-center text-blue-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">BUILD QUALITY</span>' +
          '<div class="text-2xl font-black mt-1">Commercial</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Heavy-Duty Steel / Urethane</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100 text-center text-indigo-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">GRIP DIAMETER</span>' +
          '<div class="text-2xl font-black mt-1">32mm</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Precision Knurled Handle</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-sky-50/60 border border-sky-100 text-center text-sky-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">WEIGHT ACCURACY</span>' +
          '<div class="text-2xl font-black mt-1">±1%</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Calibrated Precision</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-emerald-50/60 border border-emerald-100 text-center text-emerald-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">WARRANTY</span>' +
          '<div class="text-2xl font-black mt-1">2 Years</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Official Brand Warranty</span>' +
        '</div>'
      );
    } else {
      kpiBoxes = (
        '<div class="p-4 rounded-2xl bg-blue-50/60 border border-blue-100 text-center text-blue-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">MATERIAL</span>' +
          '<div class="text-2xl font-black mt-1">Pro Grade</div>' +
          '<span class="text-[10px] font-bold text-slate-500">BPA-Free / Anti-Odor</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100 text-center text-indigo-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">DURABILITY</span>' +
          '<div class="text-2xl font-black mt-1">Reinforced</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Drop-tested &amp; Certified</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-sky-50/60 border border-sky-100 text-center text-sky-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">BIOMETRIC MATCH</span>' +
          '<div class="text-2xl font-black mt-1">' + (product.ai_match || 96) + '%</div>' +
          '<span class="text-[10px] font-bold text-slate-500">PoseAI Athlete Approved</span>' +
        '</div>' +
        '<div class="p-4 rounded-2xl bg-emerald-50/60 border border-emerald-100 text-center text-emerald-700">' +
          '<span class="text-[10px] font-black tracking-wider text-slate-400 uppercase">TESTED</span>' +
          '<div class="text-2xl font-black mt-1">100%</div>' +
          '<span class="text-[10px] font-bold text-slate-500">Genuine &amp; Certified</span>' +
        '</div>'
      );
    }

    // Tab Body content
    var tabBodyHtml = "";

    if (activeTab === "nutrition" && isNutr) {
      var nf = (Array.isArray(product.nutrition_facts) && product.nutrition_facts.length > 0)
        ? product.nutrition_facts
        : [
          { name: "Energy", per_serving: "120 kcal", per_100g: "380 kcal", rda: "6%" },
          { name: "Protein", per_serving: "25.0 g", per_100g: "75.0 g", rda: "45%" },
          { name: "Carbohydrates", per_serving: "2.5 g", per_100g: "7.5 g", rda: "—" },
          { name: "Total Sugars", per_serving: "0 g", per_100g: "0 g", rda: "0%" },
          { name: "Total Fat", per_serving: "1.5 g", per_100g: "4.5 g", rda: "2%" },
        ];

      var rows = nf.map(function (row) {
        var isKey = row.name === "Protein" || row.name.indexOf("Creatine") !== -1;
        return (
          '<tr class="border-b border-slate-100 ' + (isKey ? "bg-blue-50/50 font-bold" : "") + '">' +
            '<td class="py-3 px-4 text-xs text-slate-800 ' + (isKey ? "text-blue-700" : "") + '">' + esc(row.name) + '</td>' +
            '<td class="py-3 px-4 text-xs font-bold ' + (isKey ? "text-blue-700" : "text-slate-700") + '">' + esc(row.per_serving) + '</td>' +
            '<td class="py-3 px-4 text-xs text-slate-600">' + esc(row.per_100g) + '</td>' +
            '<td class="py-3 px-4 text-xs text-slate-600">' + esc(row.rda) + '</td>' +
          '</tr>'
        );
      }).join("");

      tabBodyHtml = (
        '<div class="space-y-4">' +
          '<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">' + kpiBoxes + '</div>' +
          '<div class="space-y-2">' +
            '<h4 class="text-xs font-black text-slate-900">Nutritional Information (Per Serving)</h4>' +
            '<div class="overflow-x-auto rounded-2xl border border-slate-200">' +
              '<table class="w-full text-left border-collapse">' +
                '<thead class="bg-slate-50 border-b border-slate-200 text-[11px] font-black text-slate-600 uppercase tracking-wider">' +
                  '<tr>' +
                    '<th class="py-2.5 px-4">Nutrient Component</th>' +
                    '<th class="py-2.5 px-4">Per Serving</th>' +
                    '<th class="py-2.5 px-4">Per 100g</th>' +
                    '<th class="py-2.5 px-4">% Daily Value (RDA)*</th>' +
                  '</tr>' +
                '</thead>' +
                '<tbody>' + rows + '</tbody>' +
              '</table>' +
            '</div>' +
            '<p class="text-[10px] text-slate-400 italic">*Percent Daily Values are based on a 2,000 kcal diet for active adults.</p>' +
          '</div>' +
        '</div>'
      );
    } else if (activeTab === "specs" || (activeTab === "primary" && !isNutr)) {
      // Hardware / Apparel / Accessory Specifications Table
      var specs = product.specifications || {};
      var specEntries = Object.entries(specs);
      if (!specEntries.length) {
        if (isGear) {
          specEntries = [
            ["Material", "Solid Cast Iron with Commercial Urethane / Rubber Coating"],
            ["Grip Type", "Ergonomic Chrome Knurling (Non-slip)"],
            ["Weight Accuracy", "Precision Calibrated ±1%"],
            ["Finish", "Matte Anti-Corrosion Coating"],
            ["Intended Use", "Commercial Gyms and Elite Home Fitness"],
          ];
        } else if (isApparel) {
          specEntries = [
            ["Fabric Composition", "88% Polyester, 12% Elastane Moisture-Wicking Blend"],
            ["Fit Type", "Athletic Ergonomic Fit"],
            ["Technology", "Anti-Odor & 4-Way Stretch Compression"],
            ["Care", "Machine wash cold with like colors, tumble dry low"],
          ];
        } else {
          specEntries = [
            ["Material", "BPA-Free Tritan / Stainless Steel"],
            ["Capacity", product.weight_label || "700 ml"],
            ["Seal", "100% Leak-Proof Click Lid"],
            ["Cleaning", "Dishwasher Safe (Top Rack)"],
          ];
        }
      }

      var specRows = specEntries.map(function (pair) {
        return (
          '<tr class="border-b border-slate-100">' +
            '<td class="py-3 px-4 text-xs font-bold text-slate-700 bg-slate-50/50 w-1/3">' + esc(pair[0]) + '</td>' +
            '<td class="py-3 px-4 text-xs text-slate-800">' + esc(pair[1]) + '</td>' +
          '</tr>'
        );
      }).join("");

      tabBodyHtml = (
        '<div class="space-y-4">' +
          '<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">' + kpiBoxes + '</div>' +
          '<div class="space-y-2">' +
            '<h4 class="text-xs font-black text-slate-900">Technical Specifications</h4>' +
            '<div class="overflow-x-auto rounded-2xl border border-slate-200">' +
              '<table class="w-full text-left border-collapse">' +
                '<tbody>' + specRows + '</tbody>' +
              '</table>' +
            '</div>' +
          '</div>' +
        '</div>'
      );
    } else if (activeTab === "description") {
      tabBodyHtml = (
        '<div class="space-y-4 text-xs text-slate-600 leading-relaxed">' +
          '<h4 class="text-sm font-black text-slate-900">' + esc(product.name) + '</h4>' +
          '<p>' + esc(product.description) + '</p>' +
          '<p>Engineered to meet the rigorous demands of elite strength conditioning and everyday athletic routines. Verified by the PoseAI sports biomechanics team for durability, ergonomics, and material safety.</p>' +
        '</div>'
      );
    } else if (activeTab === "usage") {
      tabBodyHtml = (
        '<div class="space-y-3 text-xs text-slate-600 leading-relaxed">' +
          '<h4 class="text-sm font-black text-slate-900">Recommended Usage &amp; Protocol</h4>' +
          '<p>' + esc(product.usage || (isNutr ? "Mix 1 scoop with 200-250ml of chilled water or milk. Consume immediately post-workout or as directed by your nutrition consultant." : "Use as part of your scheduled resistance and strength workouts. Inspect equipment before each session and store in a clean, dry environment.")) + '</p>' +
        '</div>'
      );
    } else if (activeTab === "size_guide") {
      tabBodyHtml = (
        '<div class="space-y-3">' +
          '<h4 class="text-xs font-black text-slate-900">Apparel Size Chart (Inches)</h4>' +
          '<div class="overflow-x-auto rounded-2xl border border-slate-200">' +
            '<table class="w-full text-left border-collapse text-xs">' +
              '<thead class="bg-slate-50 border-b border-slate-200 font-bold">' +
                '<tr><th class="p-3">Size</th><th class="p-3">Chest (in)</th><th class="p-3">Waist (in)</th><th class="p-3">Length (in)</th></tr>' +
              '</thead>' +
              '<tbody>' +
                '<tr class="border-b"><td class="p-3 font-bold">S</td><td class="p-3">36 - 38</td><td class="p-3">28 - 30</td><td class="p-3">27</td></tr>' +
                '<tr class="border-b bg-blue-50/40"><td class="p-3 font-bold text-blue-700">M</td><td class="p-3">38 - 40</td><td class="p-3">30 - 32</td><td class="p-3">28</td></tr>' +
                '<tr class="border-b"><td class="p-3 font-bold">L</td><td class="p-3">40 - 42</td><td class="p-3">32 - 34</td><td class="p-3">29</td></tr>' +
                '<tr class="border-b"><td class="p-3 font-bold">XL</td><td class="p-3">42 - 44</td><td class="p-3">34 - 36</td><td class="p-3">30</td></tr>' +
              '</tbody>' +
            '</table>' +
          '</div>' +
        '</div>'
      );
    } else if (activeTab === "reviews") {
      tabBodyHtml = (
        '<div class="space-y-4">' +
          '<div class="flex items-center gap-4 p-4 rounded-2xl bg-slate-50 border border-slate-200">' +
            '<div class="text-center">' +
              '<div class="text-3xl font-black text-slate-900">' + (product.rating || 4.8).toFixed(1) + '</div>' +
              '<div class="text-amber-500 text-xs">★★★★★</div>' +
              '<div class="text-[10px] text-slate-500 mt-0.5">' + (product.review_count || 342) + ' ratings</div>' +
            '</div>' +
            '<div class="flex-1 space-y-1 text-[11px] text-slate-500">' +
              '<div class="flex items-center gap-2"><span>5★</span><div class="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden"><div class="h-full bg-emerald-500 w-[85%]"></div></div><span>85%</span></div>' +
              '<div class="flex items-center gap-2"><span>4★</span><div class="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden"><div class="h-full bg-blue-500 w-[11%]"></div></div><span>11%</span></div>' +
              '<div class="flex items-center gap-2"><span>3★</span><div class="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden"><div class="h-full bg-amber-400 w-[3%]"></div></div><span>3%</span></div>' +
            '</div>' +
          '</div>' +
          '<p class="text-xs text-slate-500 italic">Ratings collected from verified purchasers.</p>' +
        '</div>'
      );
    } else {
      tabBodyHtml = (
        '<div class="space-y-3 text-xs text-slate-600">' +
          '<h4 class="text-sm font-black text-slate-900">PoseAI Certified Quality</h4>' +
          '<p>Each batch undergoes rigorous quality validation and third-party laboratory verification before shipment to our distribution network.</p>' +
        '</div>'
      );
    }

    container.innerHTML =
      '<div class="rounded-3xl bg-white border border-slate-200/90 p-6 md:p-8 shadow-sm space-y-6">' +
        '<div class="flex items-center gap-4 border-b border-slate-200/80 overflow-x-auto mk-h-scroll">' +
          tabsHeaderHtml +
        '</div>' +
        '<div id="tabContentBox">' + tabBodyHtml + '</div>' +
      '</div>';

    container.querySelectorAll(".tab-nav-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeTab = btn.getAttribute("data-tab");
        renderTabs();
      });
    });
  }

  /* ─────────────────────────────────────────────────────────────
     5. WIRE ACTIONS
  ───────────────────────────────────────────────────────────── */
  function wireDetailActions() {
    // Gallery thumbnails
    document.querySelectorAll(".thumb-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = parseInt(btn.getAttribute("data-gallery-idx"), 10);
        var images = (product.image_urls && product.image_urls.length) ? product.image_urls : [product.image];
        var imgEl = document.getElementById("mainGalleryImg");
        if (imgEl && images[idx]) {
          imgEl.src = images[idx];
        }
        document.querySelectorAll(".thumb-btn").forEach(function (b) {
          b.className = "thumb-btn flex flex-col items-center gap-1 p-1 rounded-xl bg-white border-2 border-slate-200 hover:border-slate-300 transition-all";
        });
        btn.className = "thumb-btn flex flex-col items-center gap-1 p-1 rounded-xl bg-white border-2 border-blue-600 shadow-sm transition-all";
      });
    });

    // Flavors
    document.querySelectorAll(".flavor-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectedFlavor = btn.getAttribute("data-flavor");
        var lbl = document.getElementById("activeFlavorLabel");
        if (lbl) lbl.textContent = selectedFlavor;
        document.querySelectorAll(".flavor-btn").forEach(function (b) {
          b.className = "flavor-btn px-3 py-1.5 rounded-xl text-xs font-bold border transition-all border-slate-200 bg-white text-slate-700 hover:border-slate-300";
        });
        btn.className = "flavor-btn px-3 py-1.5 rounded-xl text-xs font-bold border transition-all border-blue-600 bg-blue-50 text-blue-700 shadow-xs";
      });
    });

    // Weights
    document.querySelectorAll(".weight-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectedWeight = btn.getAttribute("data-weight");
        var price = parseInt(btn.getAttribute("data-price"), 10);
        if (price) {
          var pEl = document.getElementById("detailActivePrice");
          if (pEl) pEl.textContent = money(price);
        }
        var lbl = document.getElementById("activeWeightLabel");
        if (lbl) lbl.textContent = selectedWeight;
        document.querySelectorAll(".weight-btn").forEach(function (b) {
          b.className = "weight-btn px-4 py-2 rounded-xl text-xs font-bold border transition-all border-slate-200 bg-white text-slate-700 hover:border-slate-300";
        });
        btn.className = "weight-btn px-4 py-2 rounded-xl text-xs font-bold border transition-all border-blue-600 bg-blue-600 text-white shadow-xs";
      });
    });

    // Sizes
    document.querySelectorAll(".size-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectedSize = btn.getAttribute("data-size");
        var price = parseInt(btn.getAttribute("data-price"), 10);
        if (price) {
          var pEl = document.getElementById("detailActivePrice");
          if (pEl) pEl.textContent = money(price);
        }
        var lbl = document.getElementById("activeSizeLabel");
        if (lbl) lbl.textContent = selectedSize;
        document.querySelectorAll(".size-btn").forEach(function (b) {
          b.className = "size-btn px-4 py-2 rounded-xl text-xs font-bold border transition-all border-slate-200 bg-white text-slate-700 hover:border-slate-300";
        });
        btn.className = "size-btn px-4 py-2 rounded-xl text-xs font-bold border transition-all border-blue-600 bg-blue-600 text-white shadow-xs";
      });
    });

    // Stepper
    var minus = document.getElementById("detailQtyMinus");
    var plus = document.getElementById("detailQtyPlus");
    var valEl = document.getElementById("detailQtyVal");
    if (minus && plus && valEl) {
      minus.addEventListener("click", function () {
        if (quantity > 1) {
          quantity -= 1;
          valEl.textContent = quantity;
        }
      });
      plus.addEventListener("click", function () {
        var maxStock = Number(product.stock_quantity) || 99;
        if (quantity < maxStock) {
          quantity += 1;
          valEl.textContent = quantity;
        } else {
          wk.toast("Maximum stock limit reached (" + maxStock + ")", "info");
        }
      });
    }

    // Pincode
    var pinBtn = document.getElementById("pincodeCheckBtn");
    var pinMsg = document.getElementById("pincodeMsg");
    if (pinBtn && pinMsg) {
      pinBtn.addEventListener("click", function () {
        var inp = document.getElementById("pincodeInput");
        var code = (inp && inp.value.trim()) || "560001";
        pinMsg.innerHTML = '<span class="material-symbols-outlined text-[13px]">local_shipping</span> Guaranteed Delivery to ' + esc(code) + ' by Tomorrow, 11:00 AM';
        wk.toast("Delivery confirmed for " + code);
      });
    }

    // Add to Cart
    var addBtn = document.getElementById("detailAddToCartBtn");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        addBtn.disabled = true;
        addBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Adding…';
        api.addToCart(product.id, quantity)
          .then(function () {
            addBtn.disabled = false;
            addBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">check</span> Added ✓';
            addBtn.className = "flex-1 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 text-white text-xs font-black shadow-xs transition-all";
            wk.toast("Added " + quantity + " unit(s) to cart!");
            if (wk.refreshCartBadge) wk.refreshCartBadge();
            setTimeout(function () {
              addBtn.className = "flex-1 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-50 border border-blue-600 text-blue-700 hover:bg-blue-100 text-xs font-black shadow-xs transition-all";
              addBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">add_shopping_cart</span> ADD TO CART';
            }, 2500);
          })
          .catch(function (err) {
            addBtn.disabled = false;
            addBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">add_shopping_cart</span> ADD TO CART';
            wk.toast((err && err.message) || "Could not add to cart", "error");
          });
      });
    }

    // Buy Now
    var buyBtn = document.getElementById("detailBuyNowBtn");
    if (buyBtn) {
      buyBtn.addEventListener("click", function () {
        buyBtn.disabled = true;
        buyBtn.textContent = "Processing…";
        api.addToCart(product.id, quantity)
          .then(function () {
            window.location.href = "/cart";
          })
          .catch(function (err) {
            buyBtn.disabled = false;
            buyBtn.textContent = "BUY NOW";
            wk.toast((err && err.message) || "Checkout failed", "error");
          });
      });
    }

    // Wishlist Heart Button
    var favBtn = document.getElementById("productFavBtn");
    if (favBtn) {
      favBtn.addEventListener("click", function () {
        var isFav = favBtn.getAttribute("aria-pressed") === "true";
        var icon = favBtn.querySelector(".material-symbols-outlined");
        if (isFav) {
          api.removeFavorite(product.id).then(function () {
            favBtn.setAttribute("aria-pressed", "false");
            if (icon) icon.className = "material-symbols-outlined text-[20px]";
            wk.toast("Removed from wishlist");
          });
        } else {
          api.addFavorite(product.id).then(function () {
            favBtn.setAttribute("aria-pressed", "true");
            if (icon) icon.className = "material-symbols-outlined text-[20px] text-red-500 font-variation-fill";
            wk.toast("Added to wishlist!");
          });
        }
      });
    }

    // Share button
    var shareBtn = document.getElementById("shareBtn");
    if (shareBtn) {
      shareBtn.addEventListener("click", function () {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(window.location.href);
          wk.toast("Product link copied to clipboard!");
        }
      });
    }
  }

  function renderRelated(items) {
    var grid = document.getElementById("relatedGrid");
    if (!grid) return;
    if (!items.length) {
      grid.innerHTML = '<p class="text-xs text-slate-400 col-span-full">No related items available.</p>';
      return;
    }
    grid.innerHTML = items.map(function (p) {
      return wk.productCard(p);
    }).join("");

    grid.querySelectorAll("[data-quick-add]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pid = btn.getAttribute("data-quick-add");
        btn.disabled = true;
        btn.textContent = "Adding…";
        api.addToCart(pid, 1).then(function () {
          btn.textContent = "Added ✓";
          if (wk.refreshCartBadge) wk.refreshCartBadge();
          wk.toast("Added to cart!");
        }).catch(function () {
          btn.disabled = false;
          btn.textContent = "Add";
        });
      });
    });
  }

  /* ─────────────────────────────────────────────────────────────
     6. BOOT CONTROLLER
  ───────────────────────────────────────────────────────────── */
  function boot() {
    var pId = productIdFromUrl();
    if (!pId) {
      window.location.href = "/fitness-market";
      return;
    }

    if (wk.renderMarketFooter) wk.renderMarketFooter("marketFooterSlot");

    api.product(pId)
      .then(function (res) {
        product = res.product || res;
        document.title = (product.name || "Product Details") + " — PoseAI Market";

        var crumbCat = document.getElementById("crumbCategory");
        if (crumbCat && product.category) {
          crumbCat.textContent = product.category.replace(/-/g, " ");
          crumbCat.href = "/fitness-market/products?category=" + encodeURIComponent(product.category);
        }
        var crumbName = document.getElementById("crumbProductName");
        if (crumbName) {
          crumbName.textContent = product.name;
        }

        var container = document.getElementById("detailContainer");
        if (container) {
          container.innerHTML = renderGallery(product) + renderPurchasePanel(product);
          wireDetailActions();
        }

        renderSynergyStack();
        renderTabs();

        return api.related(product.id);
      })
      .then(function (relRes) {
        var items = (relRes && (relRes.products || relRes.items)) || [];
        renderRelated(items.slice(0, 4));
      })
      .catch(function (err) {
        console.error("Failed to load product:", err);
        var container = document.getElementById("detailContainer");
        if (container) {
          container.innerHTML =
            '<div class="col-span-full py-16 text-center border-2 border-dashed border-slate-200 rounded-3xl bg-white p-8">' +
            '<span class="material-symbols-outlined text-4xl text-slate-400">error</span>' +
            '<h3 class="font-black text-slate-800 text-base mt-2">Product Not Found</h3>' +
            '<p class="text-xs text-slate-500 mt-1">This product could not be loaded or is no longer available.</p>' +
            '<a href="/fitness-market/products" class="inline-block mt-4 px-5 py-2.5 rounded-xl bg-blue-600 text-white text-xs font-black">Browse All Products</a>' +
            '</div>';
        }
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();