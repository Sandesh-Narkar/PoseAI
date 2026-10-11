/**
 * PoseAI â€” App Shell
 * Injects the shared top navigation, user chip, mobile drawer, and footer
 * into every authenticated page. Also exposes small global helpers:
 *   window.api.fetchJSON(path, options)  â€” same-origin JSON helper
 *   window.api.guard()                   â€” redirect to login when logged out
 * The active nav item is derived from <body data-page="...">.
 */
"use strict";

(function () {
  if (!window.__POSEAI_NAVBAR_INIT__ && !document.querySelector('script[src*="navbar.js"]')) {
    const s = document.createElement("script");
    s.src = "/js/navbar.js";
    document.head.appendChild(s);
  }

  const PAGE = document.body.dataset.page || "dashboard";

  const NAV = [
    { path: "dashboard", label: "Dashboard", href: "/" },
    { path: "workout", label: "Workout", href: "/workout" },
    { path: "analysis", label: "Analysis", href: "/analysis" },
    { path: "progress", label: "Progress", href: "/progress" },
    { path: "game", label: "Game", href: "/game" },
    { path: "nutrition", label: "Nutrition", href: "/nutrition" },
    { path: "market", label: "Fitness Market", href: "/fitness-market", badge: "NEW" },
  ];

  // NOTE: hrefs must match the Flask page routes registered in app.py
  // (PAGE_ROUTES -> /exercises and /achievements). Pointing the dropdown at
  // the raw template file name returned 404 from Flask.
  const MORE = [
    { path: "exercises", label: "Exercises", href: "/exercises" },
    { path: "achievements", label: "Achievements", href: "/achievements" },
  ];

  // Exercises / Achievements are children of "More", so the More button
  // must render as the active item on those pages.
  const MORE_ACTIVE = MORE.some((item) => item.path === PAGE);

  const ACTIVE = "bg-primary-container text-on-primary-container shadow-sm";
  const IDLE =
    "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors";

  function pill(active) {
    return (
      "px-3.5 py-1.5 rounded-full text-xs font-bold " + (active ? ACTIVE : IDLE)
    );
  }

  function navLink(item) {
    const active = item.path === PAGE;
    const cls = `inline-flex items-center gap-1.5 ${pill(active)} text-center`;
    const current = active ? ' aria-current="page"' : "";
    const badge = item.badge ? '<span class="px-1.5 py-0.2 rounded-full bg-blue-600 text-white text-[9px] font-black uppercase tracking-wider">NEW</span>' : '';
    return `<a${current} class="${cls}" href="${item.href}"><span>${item.label}</span>${badge}</a>`;
  }

  function drawerLink(item) {
    const active = item.path === PAGE;
    const cls = active
      ? "flex items-center justify-between px-4 py-2 rounded-lg bg-primary-container text-on-primary-container text-sm font-bold"
      : "flex items-center justify-between px-4 py-2 rounded-lg text-sm font-medium text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface";
    const current = active ? ' aria-current="page"' : "";
    const badge = item.badge ? '<span class="px-1.5 py-0.5 rounded-full bg-blue-600 text-white text-[9px] font-black uppercase">NEW</span>' : '';
    return `<a${current} class="${cls}" href="${item.href}"><span>${item.label}</span>${badge}</a>`;
  }

  function drawerSubLink(item) {
    const active = item.path === PAGE;
    const cls = active
      ? "block pl-8 pr-4 py-2 rounded-lg bg-primary-container text-on-primary-container text-sm font-bold"
      : "block pl-8 pr-4 py-2 rounded-lg text-sm font-medium text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface";
    const current = active ? ' aria-current="page"' : "";
    return `<a${current} class="${cls}" href="${item.href}">${item.label}</a>`;
  }

  function buildHeader() {
    const logo =
      '<span class="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold"><span class="material-symbols-outlined text-[20px]">fitness_center</span></span>';
    return `
<header class="fixed top-0 left-0 right-0 w-full z-50 bg-white/95 backdrop-blur-xl border-b border-slate-200/80 shadow-[0_1px_6px_rgba(0,0,0,0.03)]">
  <div class="h-16 max-w-7xl mx-auto px-4 md:px-8 flex items-center justify-between gap-3">
    <div class="flex items-center gap-5">
      <a class="flex items-center gap-2" href="/">${logo}<span class="text-lg font-black tracking-tight text-slate-900">PoseAI</span></a>
      <nav class="hidden lg:flex items-center gap-0.5 bg-slate-100/90 p-1 rounded-full border border-slate-200/60">
        ${NAV.map(navLink).join("")}
        <div class="relative" id="more-dropdown-container">
          <button class="inline-flex items-center gap-0.5 px-3 py-1.5 rounded-full text-xs font-bold ${pill(MORE_ACTIVE)}" type="button" id="moreBtn" aria-haspopup="true" aria-expanded="false">
            <span>More</span><span class="material-symbols-outlined text-[16px]" id="moreChevron">expand_more</span>
          </button>
          <div class="absolute left-0 top-full mt-2 w-48 bg-white rounded-xl shadow-lg py-1 hidden border border-slate-200 z-50" id="moreDropdown" role="menu">
            ${MORE.map(
              (m) =>
                `<a class="block px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 hover:text-blue-600 transition-colors" href="${m.href}" role="menuitem">${m.label}</a>`,
            ).join("")}
          </div>
        </div>
      </nav>
    </div>

    <!-- Search form in navbar matching reference designs -->
    <form action="/fitness-market/products" method="GET" class="hidden xl:flex items-center gap-2 bg-slate-100/90 border border-slate-200/80 rounded-full px-3.5 py-1.5 w-64 focus-within:w-80 focus-within:border-blue-500 focus-within:bg-white transition-all">
      <span class="material-symbols-outlined text-[17px] text-slate-400">search</span>
      <input type="search" name="search" placeholder="Search supplements, gear, workouts…" class="bg-transparent text-xs text-slate-800 placeholder:text-slate-400 outline-none w-full min-w-0" />
    </form>

    <div class="flex items-center gap-2 sm:gap-3">
      <a class="relative flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-colors" href="/cart" id="cartBtn" data-open-cart-drawer title="Shopping Cart" aria-label="Shopping Cart">
        <span class="material-symbols-outlined text-[19px] text-blue-600">shopping_bag</span>
        <span class="hidden sm:inline">Cart</span>
        <span class="hidden min-w-[18px] h-[18px] px-1 rounded-full bg-blue-600 text-white text-[10px] font-black items-center justify-center" id="cartBadgeCount">0</span>
      </a>
      <button class="relative w-8 h-8 rounded-full flex items-center justify-center text-slate-600 hover:bg-slate-100 transition-colors" id="notifBtn" type="button" title="Notifications">
        <span class="material-symbols-outlined text-[20px]">notifications</span>
      </button>
      <div class="relative">
        <button class="flex items-center gap-2 p-1 rounded-full hover:bg-surface-container-low transition-colors focus:outline-none" type="button" id="userMenuBtn" aria-haspopup="true" aria-expanded="false">
          <img id="userAvatar" alt="Avatar" class="w-8 h-8 rounded-full object-cover ring-2 ring-surface-container-high hidden" src="">
          <span id="userAvatarFallback" class="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center text-xs font-bold ring-2 ring-surface-container-high">U</span>
          <div class="hidden xl:flex flex-col text-left">
            <span class="text-sm font-semibold text-on-surface leading-none" id="userName">Athlete</span>
            <span class="text-[11px] text-on-surface-variant leading-tight">Member</span>
          </div>
          <span class="material-symbols-outlined text-[18px] text-on-surface-variant hidden xl:inline">expand_more</span>
        </button>
        <div class="absolute right-0 top-full mt-2 w-48 bg-surface-container-lowest rounded-2xl shadow-[0_8px_32px_0_rgba(15,23,42,0.08)] py-2 hidden border border-surface-container-high z-50" id="userMenuDropdown" role="menu">
          <a class="flex items-center gap-2 px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface" href="/profile" role="menuitem"><span class="material-symbols-outlined text-[18px]">person</span>Profile</a>
          <div class="my-1 border-t border-surface-container"></div>
          <button id="logoutBtn" class="w-full flex items-center gap-2 px-4 py-2 text-sm text-error hover:bg-error-container/20" type="button"><span class="material-symbols-outlined text-[18px]">logout</span>Logout</button>
        </div>
      </div>
      <button aria-label="Toggle Menu" class="lg:hidden w-10 h-10 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container-low transition-colors" type="button" id="menuBtn">
        <span class="material-symbols-outlined text-[24px]">menu</span>
      </button>
    </div>
  </div>
  <div class="hidden lg:hidden border-t border-surface-container-high bg-surface-container-lowest px-4 py-6 shadow-lg" id="mobile-drawer">
    <nav class="flex flex-col gap-1">
      ${NAV.map(drawerLink).join("")}
      <span class="px-4 pt-3 pb-1 text-[11px] uppercase tracking-wider font-bold text-on-surface-variant">More</span>
      ${MORE.map(drawerSubLink).join("")}
      <div class="h-px bg-surface-container-high my-2"></div>
      ${drawerLink({ path: "profile", label: "Profile", href: "/profile" })}
      <button class="w-full text-left px-4 py-2 rounded-lg text-sm font-medium text-error hover:bg-error-container/20" type="button" data-logout>Logout</button>
    </nav>
  </div>
</header>`;
  }

  function buildFooter() {
    return `
<footer class="w-full bg-surface-container-lowest border-t border-surface-container">
  <div class="max-w-7xl mx-auto px-4 md:px-10 py-10 flex flex-col md:flex-row items-center justify-between gap-4">
    <div class="flex items-center gap-2">
      <span class="w-6 h-6 rounded-lg bg-primary text-on-primary flex items-center justify-center"><span class="material-symbols-outlined text-[14px]">fitness_center</span></span>
      <span class="text-sm text-on-surface-variant">Â© 2024 PoseAI Systems Inc. All rights reserved.</span>
    </div>
    <div class="flex items-center gap-6">
      <a class="text-sm text-on-surface-variant hover:text-primary transition-colors" href="#">Privacy Policy</a>
      <a class="text-sm text-on-surface-variant hover:text-primary transition-colors" href="#">Telemetry Terms</a>
    </div>
  </div>
</footer>`;
  }

  /* â”€â”€ JSON helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  async function request(path, options = {}) {
    const { body, method = body ? "POST" : "GET", headers = {} } = options;
    const url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
      ? window.getApiUrl(path)
      : path;
    const res = await fetch(url, {
      method,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      /* non-JSON */
    }
    if (res.status === 401 && !path.startsWith("/api/auth")) {
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const message = (data && (data.message || data.error)) || res.statusText;
      throw new Error(message);
    }
    return data;
  }

  window.api = {
    get: (path, headers) => request(path, { method: "GET", headers }),
    post: (path, body) => request(path, { method: "POST", body }),
    patch: (path, body) => request(path, { method: "PATCH", body }),
    delete: (path, body) => request(path, { method: "DELETE", body }),
  };

  /* ── Cart badge (shared by every authenticated header) ──────────────
     The Fitness Market pages call PoseAIMarket.refreshCartBadge() after
     any cart mutation so the navbar count stays live without a reload. */
  async function refreshCartBadge() {
    const badge = document.getElementById("cartBadgeCount");
    const poseaiBadge = document.getElementById("poseaiCartBadge");
    const poseaiDrawerBadge = document.getElementById("poseaiDrawerCartBadge");
    try {
      const url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
        ? window.getApiUrl("/api/market/cart-count")
        : "/api/market/cart-count";
      const res = await fetch(url, {
        method: "GET",
        credentials: "include",
        headers: { "Accept": "application/json" },
      });
      if (!res.ok) return;
      const data = await res.json();
      const count = Number((data && data.item_count) || 0);
      if (count > 0) {
        const text = count > 99 ? "99+" : String(count);
        if (badge) {
          badge.textContent = text;
          badge.classList.remove("hidden");
          badge.classList.add("flex");
        }
        if (poseaiBadge) {
          poseaiBadge.textContent = text;
          poseaiBadge.classList.remove("hidden");
        }
        if (poseaiDrawerBadge) {
          poseaiDrawerBadge.textContent = text;
          poseaiDrawerBadge.classList.remove("hidden");
        }
      } else {
        if (badge) {
          badge.classList.add("hidden");
          badge.classList.remove("flex");
        }
        if (poseaiBadge) poseaiBadge.classList.add("hidden");
        if (poseaiDrawerBadge) poseaiDrawerBadge.classList.add("hidden");
      }
    } catch (_) {
      /* offline / transient — keep badge hidden */
    }
  }

  /* ── Global cart drawer ─────────────────────────────────────────
     Available on EVERY authenticated page: it depends only on the same
     same-origin fetch the badge uses, never on api-client.js (which the
     workout/analysis pages don't load). Desktop = slide-over from the
     right, mobile = full-screen sheet. All totals are server-computed.
     ─────────────────────────────────────────────────────────────── */
  var drawer = {
    root: null,
    panel: null,
    body: null,
    footer: null,
    data: null,
    rendered: false,
  };

  function drawerMoney(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN");
  }

  function drawerEsc(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function drawerToast(message, kind) {
    var existing = document.getElementById("mkDrawerToast");
    if (existing) existing.remove();
    var toast = document.createElement("div");
    toast.id = "mkDrawerToast";
    toast.className =
      "fixed bottom-5 left-1/2 -translate-x-1/2 z-[80] max-w-[90vw] px-4 py-2.5 rounded-full shadow-lg text-sm font-semibold text-on-primary text-center " +
      (kind === "error" ? "bg-error" : "bg-primary");
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(function () {
      toast.style.transition = "opacity 200ms ease";
      toast.style.opacity = "0";
      window.setTimeout(function () { toast.remove(); }, 220);
    }, 2600);
  }

  function drawerFallback(name) {
    var brand = (name || "").split(" ").slice(0, 2).join(" ") || "PoseAI";
    return (
      '<div class="mk-fallback-tile" style="display:flex;align-items:center;justify-content:center;height:100%;min-height:64px;padding:6px;">' +
      '<span class="material-symbols-outlined" style="font-size:22px;line-height:1;">fitness_center</span>' +
      '<span class="brand" style="display:block;font-size:9px;line-height:1.2;text-align:center;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-top:2px;">' + drawerEsc(brand) + "</span></div>"
    );
  }

  function drawerImage(line) {
    if (line.image_url) {
      return '<img class="w-full h-full object-cover" src="' + drawerEsc(line.image_url) + '" alt="' + drawerEsc(line.name) + '" loading="lazy" onerror="this.parentElement.innerHTML=window.PoseAIMarket.fallbackTile(this.alt)">';
    }
    return drawerFallback(line.name);
  }

  function drawerLine(line) {
    var stepper;
    if (line.in_stock) {
      stepper =
        '<div class="flex items-center gap-1.5 mt-1.5">' +
        '<button class="w-7 h-7 rounded-full flex items-center justify-center bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high disabled:opacity-30" type="button" data-drawer-dec="' + drawerEsc(line.product_id) + '" aria-label="Decrease"><span class="material-symbols-outlined text-[15px]">remove</span></button>' +
        '<span class="w-6 text-center font-extrabold text-on-surface text-sm">' + line.quantity + "</span>" +
        '<button class="w-7 h-7 rounded-full flex items-center justify-center bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high" type="button" data-drawer-inc="' + drawerEsc(line.product_id) + '" aria-label="Increase"><span class="material-symbols-outlined text-[15px]">add</span></button>' +
        "</div>";
    } else {
      stepper =
        '<div class="text-[11px] font-bold text-error mt-1.5">' + drawerEsc(line.stock_label || "Unavailable") + " — not billed</div>";
    }
    return (
      '<div class="flex gap-3 py-3 border-b border-surface-container-high last:border-0" data-drawer-line="' + drawerEsc(line.product_id) + '">' +
      '<a class="w-16 h-16 rounded-xl overflow-hidden mk-image-tile shrink-0" href="/fitness-market/product/' + drawerEsc(line.product_id) + '">' + drawerImage(line) + "</a>" +
      '<div class="flex-1 min-w-0">' +
      '<div class="flex items-start justify-between gap-2">' +
      '<div class="min-w-0">' +
      '<span class="block text-[9px] font-bold uppercase tracking-widest text-primary">' + drawerEsc(line.brand) + "</span>" +
      '<span class="mk-clamp-2 block text-xs font-semibold text-on-surface leading-snug">' + drawerEsc(line.name) + "</span>" +
      "</div>" +
      '<button class="w-7 h-7 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-error-container hover:text-error shrink-0" type="button" data-drawer-remove="' + drawerEsc(line.product_id) + '" aria-label="Remove"><span class="material-symbols-outlined text-[16px]">delete</span></button>' +
      "</div>" +
      '<div class="flex items-center justify-between gap-2 mt-1">' +
      (line.in_stock
        ? '<span class="text-sm font-extrabold text-on-surface">' + drawerMoney(line.line_total) + "</span>"
        : '<span class="text-xs text-on-surface-variant line-through">' + drawerMoney(line.price * line.quantity) + "</span>") +
      stepper +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function drawerStateMarkup() {
    var cart = drawer.data;
    if (!cart) {
      return (
        '<div class="flex flex-col items-center justify-center py-16 text-center px-6">' +
        '<span class="material-symbols-outlined animate-spin text-3xl text-on-surface-variant">progress_activity</span>' +
        '<p class="text-sm text-on-surface-variant mt-3">Loading your cart…</p></div>'
      );
    }
    if (!cart.items || cart.items.length === 0) {
      return (
        '<div class="flex flex-col items-center justify-center py-16 text-center px-6">' +
        '<div class="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center text-outline mb-3"><span class="material-symbols-outlined text-3xl">shopping_bag</span></div>' +
        '<h3 class="font-bold text-on-surface">Your cart is empty</h3>' +
        '<p class="text-sm text-on-surface-variant mt-1">Add supplements and gear from the Fitness Market.</p>' +
        '<a href="/fitness-market" class="mt-4 px-5 py-2.5 rounded-full bg-primary text-on-primary text-sm font-bold hover:opacity-95">Explore the Market</a>' +
        "</div>"
      );
    }
    return cart.items.map(drawerLine).join("");
  }

  function drawerFooterMarkup(cart) {
    if (!cart || !cart.items || cart.items.length === 0) return "";
    var deliveryNote = "";
    if (cart.delivery_fee > 0) {
      var shortfall = (cart.free_delivery_threshold || 999) - cart.total;
      deliveryNote = '<p class="text-[11px] text-on-surface-variant mt-1">Add ' + drawerMoney(shortfall) + " more for FREE delivery</p>";
    }
    return (
      '<div class="p-4 border-t border-surface-container-high bg-surface-container-lowest">' +
      '<div class="space-y-1.5 text-sm">' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Subtotal</span><span class="font-semibold text-on-surface">' + drawerMoney(cart.subtotal) + "</span></div>" +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Discount</span><span class="font-semibold text-secondary">- ' + drawerMoney(cart.discount) + "</span></div>" +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Delivery</span><span class="font-semibold ' + (cart.delivery_fee === 0 ? "text-secondary" : "text-on-surface") + '">' +
      (cart.delivery_fee === 0 ? "FREE" : drawerMoney(cart.delivery_fee)) + "</span></div>" +
      deliveryNote +
      "</div>" +
      '<div class="h-px bg-surface-container-high my-2.5"></div>' +
      '<div class="flex justify-between items-baseline">' +
      '<span class="font-bold text-on-surface">Total</span>' +
      '<span class="text-lg font-extrabold text-on-surface">' + drawerMoney(cart.grand_total) + "</span></div>" +
      '<button class="w-full mt-3 py-2.5 rounded-full bg-primary text-on-primary font-bold text-sm hover:opacity-95" type="button" data-drawer-checkout>Proceed to Checkout</button>' +
      '<div class="flex items-center justify-between mt-2">' +
      '<a href="/cart" class="text-xs font-bold text-primary hover:underline">View full cart</a>' +
      '<button class="text-xs font-bold text-on-surface-variant hover:text-error" type="button" data-drawer-clear>Clear cart</button>' +
      "</div></div>"
    );
  }

  function renderDrawer() {
    var cart = drawer.data;
    drawer.body.innerHTML = drawerStateMarkup();
    drawer.footer.innerHTML = drawerFooterMarkup(cart);
    var countEl = document.getElementById("mkDrawerCount");
    if (countEl) countEl.textContent = cart ? cart.item_count : 0;
    drawer.rendered = true;
  }

  window.PoseAIMarket = window.PoseAIMarket || {};
  window.PoseAIMarket.refreshCartBadge = refreshCartBadge;
  window.PoseAIMarket.fallbackTile = drawerFallback;

  function setUser(user) {
    if (!user) return;
    const name = user.name || user.full_name || user.username || "Athlete";
    const firstName = name.trim().split(/\s+/)[0] || "A";
    const chipName = document.getElementById("userName");
    const initial = document.getElementById("userAvatarFallback");
    const avatar = document.getElementById("userAvatar");
    if (chipName) chipName.textContent = name;
    const poseaiName = document.getElementById("poseaiNavUserName");
    const poseaiInitial = document.getElementById("poseaiAvatarInitial");
    const poseaiImg = document.getElementById("poseaiAvatarImg");
    if (poseaiName) poseaiName.textContent = name;

    if (avatar && user.profile_picture) {
      avatar.src = user.profile_picture;
      avatar.classList.remove("hidden");
      if (initial) initial.classList.add("hidden");
    } else if (initial) {
      initial.textContent = firstName.charAt(0).toUpperCase();
      initial.classList.remove("hidden");
    }

    if (poseaiImg && user.profile_picture) {
      poseaiImg.src = user.profile_picture;
      poseaiImg.style.display = "block";
      if (poseaiInitial) poseaiInitial.style.display = "none";
    } else if (poseaiInitial) {
      poseaiInitial.textContent = firstName.charAt(0).toUpperCase();
    }
  }

  async function logout() {
    try {
      await window.api.post("/api/auth/logout");
    } catch (_) {
      /* session still cleared server-side */
    }
    window.location.href = "/login";
  }

  function wireHeader() {
    const headerEl = document.getElementById("app-header");
    const footerEl = document.getElementById("app-footer");
    if (headerEl) {
      if (!headerEl.querySelector(".poseai-navbar")) {
        headerEl.innerHTML = buildHeader();
      }
      const logoutBtn = document.getElementById("logoutBtn");
      if (logoutBtn) logoutBtn.addEventListener("click", logout);
      document
        .querySelectorAll("[data-logout]")
        .forEach((el) =>
          el.addEventListener("click", (e) => {
            e.preventDefault();
            logout();
          }),
        );
      const notifBtn = document.getElementById("notifBtn");
      if (notifBtn) {
        notifBtn.addEventListener("click", () => window.location.assign("/achievements"));
      }
      /* ── Dropdown helpers ────────────────────────────────────────────
         All three navbar menus (More, mobile drawer, profile chip) are
         CLICK-toggled. Hover/mouseleave driven menus were the reason the
         "More" items could not be reached with the cursor: the panel
         vanished as soon as the pointer left the trigger. Clicking the
         trigger again, clicking outside, or pressing Escape closes them. */
      function closeAllMenus() {
        closeMore();
        closeMobileDrawer();
        closeUserMenu();
      }

      /* ── More dropdown (desktop) ─────────────────────────────────── */
      const moreBtn = document.getElementById("moreBtn");
      const moreDropdown = document.getElementById("moreDropdown");
      const moreChevron = document.getElementById("moreChevron");

      function openMore() {
        if (!moreDropdown) return;
        moreDropdown.classList.remove("hidden");
        moreDropdown.style.opacity = "0";
        moreDropdown.style.transform = "translateY(-4px)";
        requestAnimationFrame(function () {
          moreDropdown.style.transition = "opacity 120ms ease, transform 120ms ease";
          moreDropdown.style.opacity = "1";
          moreDropdown.style.transform = "translateY(0)";
        });
        if (moreBtn) moreBtn.setAttribute("aria-expanded", "true");
        if (moreChevron) moreChevron.style.transform = "rotate(180deg)";
      }

      function closeMore() {
        if (!moreDropdown || moreDropdown.classList.contains("hidden")) return;
        moreDropdown.style.opacity = "0";
        moreDropdown.style.transform = "translateY(-4px)";
        window.setTimeout(function () {
          moreDropdown.classList.add("hidden");
        }, 120);
        if (moreBtn) moreBtn.setAttribute("aria-expanded", "false");
        if (moreChevron) moreChevron.style.transform = "rotate(0deg)";
      }

      if (moreBtn && moreDropdown) {
        moreBtn.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          if (moreDropdown.classList.contains("hidden")) {
            closeMobileDrawer();
            closeUserMenu();
            openMore();
          } else {
            closeMore();
          }
        });
        // Selecting a destination closes the menu; the link still navigates.
        moreDropdown.querySelectorAll("a").forEach(function (link) {
          link.addEventListener("click", function () {
            closeMore();
          });
        });
      }

      /* ── Mobile drawer ───────────────────────────────────────────── */
      const menuBtn = document.getElementById("menuBtn");
      const drawer = document.getElementById("mobile-drawer");

      function closeMobileDrawer() {
        if (drawer) drawer.classList.add("hidden");
      }

      if (menuBtn && drawer) {
        menuBtn.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          const willOpen = drawer.classList.contains("hidden");
          if (willOpen) {
            closeMore();
            closeUserMenu();
            drawer.classList.remove("hidden");
          } else {
            drawer.classList.add("hidden");
          }
        });
        // Keep the drawer open until the user picks something, taps
        // outside, or presses Escape (no auto-close on scroll/hover).
        drawer.querySelectorAll("a").forEach(function (link) {
          link.addEventListener("click", closeMobileDrawer);
        });
      }

      /* ── Profile chip menu ───────────────────────────────────────── */
      const userMenuBtn = document.getElementById("userMenuBtn");
      const userMenuDropdown = document.getElementById("userMenuDropdown");

      function closeUserMenu() {
        if (userMenuDropdown) userMenuDropdown.classList.add("hidden");
        if (userMenuBtn) userMenuBtn.setAttribute("aria-expanded", "false");
      }

      if (userMenuBtn && userMenuDropdown) {
        userMenuBtn.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          const willOpen = userMenuDropdown.classList.contains("hidden");
          if (willOpen) {
            closeMore();
            closeMobileDrawer();
            userMenuDropdown.classList.remove("hidden");
            userMenuBtn.setAttribute("aria-expanded", "true");
          } else {
            closeUserMenu();
          }
        });
      }


/* ── Shared dismiss behaviour ────────────────────────────────── */
      document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        closeAllMenus();
      });

      document.addEventListener("click", function (event) {
        const target = event.target;
        // More
        if (moreDropdown && !moreDropdown.classList.contains("hidden")) {
          if (!moreDropdown.contains(target) && (!moreBtn || !moreBtn.contains(target))) {
            closeMore();
          }
        }
        // Mobile drawer
        if (drawer && !drawer.classList.contains("hidden")) {
          if (!drawer.contains(target) && (!menuBtn || !menuBtn.contains(target))) {
            closeMobileDrawer();
          }
        }
        // Profile chip
        if (userMenuDropdown && !userMenuDropdown.classList.contains("hidden")) {
          if (!userMenuDropdown.contains(target) && (!userMenuBtn || !userMenuBtn.contains(target))) {
            closeUserMenu();
          }
        }
      });

      if (footerEl) {
        footerEl.innerHTML = buildFooter();
      }
    }
  }

  function drawerPanelMarkup() {
    return (
      '<div id="mkCartRoot" class="hidden">' +
      '<div id="mkCartOverlay" class="fixed inset-0 z-[70] bg-inverse-surface/40 backdrop-blur-sm"></div>' +
      '<aside id="mkCartDrawer" class="fixed top-0 right-0 z-[71] h-full w-full max-w-[400px] bg-surface-container-lowest shadow-2xl flex flex-col translate-x-full transition-transform duration-200 ease-out" role="dialog" aria-modal="true" aria-label="Shopping cart">' +
      '<div class="flex items-center justify-between px-4 h-16 border-b border-surface-container-high shrink-0">' +
      '<div class="flex items-center gap-2"><h2 class="font-extrabold text-on-surface">Your Cart</h2>' +
      '<span id="mkDrawerCount" class="px-2 py-0.5 rounded-full bg-secondary text-on-secondary text-[11px] font-bold">0</span></div>' +
      '<button id="mkDrawerClose" class="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container-low transition-colors" type="button" aria-label="Close cart"><span class="material-symbols-outlined text-[20px]">close</span></button>' +
      "</div>" +
      '<div id="mkCartBody" class="flex-1 overflow-y-auto px-4 pt-2"></div>' +
      '<div id="mkCartFooter"></div>' +
      "</aside></div>"
    );
  }

  function ensureDrawerDOM() {
    if (drawer.root) return;
    var holder = document.createElement("div");
    holder.innerHTML = drawerPanelMarkup();
    var root = holder.firstElementChild;
    document.body.appendChild(root);
    drawer.root = root;
    drawer.panel = document.getElementById("mkCartDrawer");
    drawer.body = document.getElementById("mkCartBody");
    drawer.footer = document.getElementById("mkCartFooter");

    drawer.panel.addEventListener("click", function (event) {
      var target = event.target.closest("[data-drawer-inc],[data-drawer-dec],[data-drawer-remove],[data-drawer-checkout],[data-drawer-clear]");
      if (!target) return;
      if (target.hasAttribute("data-drawer-inc") || target.hasAttribute("data-drawer-dec")) {
        var line = drawerLineById(target.dataset.drawerInc || target.dataset.drawerDec);
        if (!line) return;
        var next = line.quantity + (target.hasAttribute("data-drawer-inc") ? 1 : -1);
        if (next < 1) { drawerRemove(target.dataset.drawerDec); return; }
        drawerUpdate(target.dataset.drawerInc || target.dataset.drawerDec, next);
      } else if (target.hasAttribute("data-drawer-remove")) {
        drawerRemove(target.dataset.drawerRemove);
      } else if (target.hasAttribute("data-drawer-clear")) {
        drawerClear();
      } else if (target.hasAttribute("data-drawer-checkout")) {
        window.location.href = "/fitness-market/checkout";
      }
    });

    document.getElementById("mkDrawerClose").addEventListener("click", closeCartDrawer);
    document.getElementById("mkCartOverlay").addEventListener("click", closeCartDrawer);
  }

  function drawerLineById(productId) {
    if (!drawer.data || !drawer.data.items) return null;
    for (var i = 0; i < drawer.data.items.length; i += 1) {
      if (String(drawer.data.items[i].product_id) === String(productId)) return drawer.data.items[i];
    }
    return null;
  }

  async function cartFetch() {
    var url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
      ? window.getApiUrl("/api/market/cart")
      : "/api/market/cart";
    var res = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" },
    });
    if (res.status === 401) { window.location.href = "/login"; throw new Error("Unauthorized"); }
    if (!res.ok) throw new Error("Could not load cart");
    var data = await res.json();
    return data && data.cart ? data.cart : { items: [], item_count: 0, subtotal: 0, discount: 0, delivery_fee: 0, total: 0, grand_total: 0, currency: "INR", free_delivery_threshold: 999 };
  }

  async function refreshDrawer() {
    if (!drawer.root) return;
    try {
      drawer.data = await cartFetch();
      renderDrawer();
      refreshCartBadge();
    } catch (error) {
      if (error && error.message === "Unauthorized") return;
      drawer.data = null;
      drawer.body.innerHTML =
        '<div class="flex flex-col items-center justify-center py-16 text-center px-6">' +
        '<div class="w-16 h-16 rounded-full bg-error-container text-error flex items-center justify-center mb-3"><span class="material-symbols-outlined text-3xl">error_outline</span></div>' +
        '<h3 class="font-bold text-on-surface">Could not load your cart</h3>' +
        '<p class="text-sm text-on-surface-variant mt-1">Please check your connection and retry.</p>' +
        '<button class="mt-4 px-5 py-2.5 rounded-full bg-primary text-on-primary text-sm font-bold" type="button" data-drawer-retry>Retry</button></div>';
      drawer.footer.innerHTML = "";
      var retry = drawer.body.querySelector("[data-drawer-retry]");
      if (retry) retry.addEventListener("click", refreshDrawer);
    }
  }

  async function drawerUpdate(productId, quantity) {
    try {
      var url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
        ? window.getApiUrl("/api/market/cart/" + encodeURIComponent(productId))
        : "/api/market/cart/" + encodeURIComponent(productId);
      var res = await fetch(url, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ quantity: quantity }),
      });
      var data = await res.json();
      if (!res.ok) {
        var err = (data && data.error) || {};
        drawerToast(err.message || "Could not update quantity", "error");
        refreshDrawer();
        return;
      }
      drawer.data = data.cart;
      renderDrawer();
      refreshCartBadge();
    } catch (_) {
      refreshDrawer();
    }
  }

  async function drawerRemove(productId) {
    try {
      var url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
        ? window.getApiUrl("/api/market/cart/" + encodeURIComponent(productId))
        : "/api/market/cart/" + encodeURIComponent(productId);
      var res = await fetch(url, {
        method: "DELETE",
        credentials: "include",
        headers: { "Accept": "application/json" },
      });
      var data = await res.json();
      drawer.data = data.cart;
      renderDrawer();
      refreshCartBadge();
      drawerToast("Removed from cart");
    } catch (_) {
      drawerToast("Could not remove item", "error");
    }
  }

  async function drawerClear() {
    if (!window.confirm("Remove all items from your cart?")) return;
    try {
      var url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
        ? window.getApiUrl("/api/market/cart/clear")
        : "/api/market/cart/clear";
      var res = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: { "Accept": "application/json" },
      });
      var data = await res.json();
      drawer.data = data.cart;
      renderDrawer();
      refreshCartBadge();
      drawerToast("Cart cleared");
    } catch (_) {
      drawerToast("Could not clear the cart", "error");
    }
  }

  function openCartDrawer() {
    ensureDrawerDOM();
    drawer.root.classList.remove("hidden");
    requestAnimationFrame(function () {
      drawer.panel.classList.remove("translate-x-full");
    });
    if (!drawer.rendered) refreshDrawer();
    document.body.style.overflow = "hidden";
  }

  function closeCartDrawer() {
    if (!drawer.root || drawer.root.classList.contains("hidden")) return;
    drawer.panel.classList.add("translate-x-full");
    window.setTimeout(function () {
      drawer.root.classList.add("hidden");
    }, 200);
    document.body.style.overflow = "";
  }

  function wireDrawerTriggers() {
    document.querySelectorAll("[data-open-cart-drawer]").forEach(function (trigger) {
      trigger.addEventListener("click", function (event) {
        event.preventDefault();
        openCartDrawer();
      });
    });
  }

  window.PoseAIMarket.openCartDrawer = openCartDrawer;
  window.PoseAIMarket.closeCartDrawer = closeCartDrawer;
  window.PoseAIMarket.refreshCartBadge = refreshCartBadge;

  function boot() {
    wireHeader();
    // Hydrate the user chip / avatar from the authenticated session.
    window.api
      .get("/api/auth/me")
      .then(function (res) {
        // /api/auth/me returns {authenticated, user} (not the {data} envelope).
        setUser((res && (res.user || res.data)) || null);
      })
      .catch(function () {
        /* chip keeps its neutral default */
      });
    // Keep the cart badge in sync on every page load.
    refreshCartBadge();
    // Cart drawer openers (navbar bag icon on every injected page).
    ensureDrawerDOM();
    wireDrawerTriggers();
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeCartDrawer();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
