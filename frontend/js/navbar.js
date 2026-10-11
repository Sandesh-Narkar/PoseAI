/**
 * PoseAI Unified Global Navbar
 * Single source of truth for the authenticated navbar across all pages.
 */
(function () {
  "use strict";

  // Prevent double-initialization
  if (window.__POSEAI_NAVBAR_INIT__) return;
  window.__POSEAI_NAVBAR_INIT__ = true;

  // Ensure navbar.css is present in head
  if (!document.querySelector('link[href*="navbar.css"]')) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/css/navbar.css";
    document.head.appendChild(link);
  }

  // Determine current active page based on pathname
  function detectCurrentRoute() {
    const path = window.location.pathname.toLowerCase();
    if (path === "/" || path.endsWith("/index.html") || path === "/dashboard") return "dashboard";
    if (path.includes("workout")) return "workout";
    if (path.includes("analysis")) return "analysis";
    if (path.includes("progress")) return "progress";
    if (path.includes("game")) return "game";
    if (path.includes("nutrition")) return "nutrition";
    if (path.includes("market") || path.includes("product") || path.includes("cart") || path.includes("order")) return "market";
    if (path.includes("exercise")) return "exercises";
    if (path.includes("achievement")) return "achievements";
    if (path.includes("profile")) return "profile";
    if (path.includes("settings")) return "settings";
    return "";
  }

  const currentRoute = detectCurrentRoute();

  const NAV_ITEMS = [
    { id: "dashboard", label: "Dashboard", href: "/" },
    { id: "workout", label: "Workout", href: "/workout" },
    { id: "analysis", label: "Analysis", href: "/analysis" },
    { id: "progress", label: "Progress", href: "/progress" },
    { id: "game", label: "Game", href: "/game" },
    { id: "nutrition", label: "Nutrition", href: "/nutrition" },
    { id: "market", label: "Fitness Market", href: "/fitness-market" },
  ];

  const MORE_ITEMS = [
    { id: "exercises", label: "Exercises", href: "/exercises" },
    { id: "achievements", label: "Achievements", href: "/achievements" },
    { id: "settings", label: "Settings", href: "/profile" },
  ];

  function renderNavbarHTML() {
    const isMoreActive = MORE_ITEMS.some((m) => m.id === currentRoute);

    return `
<nav class="poseai-navbar" id="poseaiNavbar" role="navigation" aria-label="Main Navigation">
  <div class="poseai-navbar__container">
    <!-- Brand -->
    <div class="poseai-navbar__brand-wrap">
      <a class="poseai-navbar__brand" href="/" aria-label="PoseAI Home">
        <span class="poseai-navbar__sparkle">✦</span>
        <span>POSEAI</span>
      </a>
    </div>

    <!-- Center Navigation Links -->
    <ul class="poseai-navbar__nav" role="menubar">
      ${NAV_ITEMS.map((item) => {
        const isActive = item.id === currentRoute;
        return `
        <li role="none">
          <a class="poseai-navbar__link ${isActive ? "active" : ""}" 
             href="${item.href}" 
             role="menuitem"
             ${isActive ? 'aria-current="page"' : ""}>
            ${item.label}
          </a>
        </li>`;
      }).join("")}

      <!-- More Dropdown -->
      <li class="poseai-navbar__dropdown-wrapper" role="none">
        <button class="poseai-navbar__dropdown-toggle ${isMoreActive ? "active" : ""}" 
                id="poseaiMoreBtn" 
                type="button" 
                aria-haspopup="true" 
                aria-expanded="false" 
                role="menuitem">
          <span>More</span>
          <span class="poseai-navbar__caret">▾</span>
        </button>
        <div class="poseai-navbar__dropdown-menu" id="poseaiMoreDropdown" role="menu" aria-label="More options">
          ${MORE_ITEMS.map((m) => {
            const isActive = m.id === currentRoute;
            return `<a class="poseai-navbar__dropdown-item ${isActive ? "active" : ""}" 
                       href="${m.href}" 
                       role="menuitem"
                       ${isActive ? 'aria-current="page"' : ""}>
                      ${m.label}
                    </a>`;
          }).join("")}
        </div>
      </li>
    </ul>

    <!-- Right Actions -->
    <div class="poseai-navbar__actions">
      <!-- Cart -->
      <a class="poseai-navbar__action-btn" href="/cart" id="poseaiCartBtn" data-open-cart-drawer title="Shopping Cart" aria-label="Shopping Cart">
        <span>🛒</span>
        <span class="poseai-navbar__badge hidden" id="poseaiCartBadge">0</span>
      </a>

      <!-- Notifications -->
      <button class="poseai-navbar__action-btn" id="poseaiNotifBtn" type="button" title="Notifications" aria-label="Notifications">
        <span>🔔</span>
        <span class="poseai-navbar__badge hidden" id="poseaiNotifBadge">0</span>
      </button>

      <!-- Profile & Settings Menu -->
      <div class="poseai-navbar__profile-wrap">
        <button class="poseai-navbar__profile-btn" id="poseaiProfileBtn" type="button" aria-haspopup="true" aria-expanded="false">
          <div class="poseai-navbar__avatar" id="poseaiNavAvatar">
            <span id="poseaiAvatarInitial">U</span>
            <img id="poseaiAvatarImg" src="" alt="Avatar" style="display: none;" />
          </div>
          <span class="poseai-navbar__user-name" id="poseaiNavUserName">Athlete</span>
          <span class="poseai-navbar__caret">▾</span>
        </button>

        <div class="poseai-navbar__profile-menu" id="poseaiProfileMenu" role="menu" aria-label="User menu">
          <div class="poseai-navbar__profile-header">ACCOUNT</div>
          <a class="poseai-navbar__profile-item" href="/profile" role="menuitem">
            <span>👤</span>
            <span>View Profile</span>
          </a>
          <a class="poseai-navbar__profile-item" href="/profile" role="menuitem">
            <span>⚙️</span>
            <span>Settings</span>
          </a>
          <div class="poseai-navbar__dropdown-divider"></div>
          <button class="poseai-navbar__profile-item danger" id="poseaiLogoutBtn" type="button" role="menuitem">
            <span>🚪</span>
            <span>Logout</span>
          </button>
        </div>
      </div>

      <!-- Mobile Hamburger Button -->
      <button class="poseai-navbar__hamburger" id="poseaiHamburgerBtn" type="button" aria-label="Open navigation menu">
        ☰
      </button>
    </div>
  </div>

  <!-- Mobile Drawer Backdrop -->
  <div class="poseai-navbar__drawer-backdrop" id="poseaiDrawerBackdrop"></div>

  <!-- Mobile Drawer -->
  <div class="poseai-navbar__drawer" id="poseaiMobileDrawer" role="dialog" aria-modal="true" aria-label="Mobile Navigation">
    <div class="poseai-navbar__drawer-header">
      <a class="poseai-navbar__brand" href="/">
        <span class="poseai-navbar__sparkle">✦</span>
        <span>POSEAI</span>
      </a>
      <button class="poseai-navbar__drawer-close" id="poseaiDrawerCloseBtn" type="button" aria-label="Close menu">✕</button>
    </div>

    <div class="poseai-navbar__drawer-content">
      ${NAV_ITEMS.map((item) => {
        const isActive = item.id === currentRoute;
        return `
        <a class="poseai-navbar__drawer-link ${isActive ? "active" : ""}" 
           href="${item.href}" 
           ${isActive ? 'aria-current="page"' : ""}>
          <span>${item.label}</span>
        </a>`;
      }).join("")}

      <div class="poseai-navbar__drawer-divider"></div>
      <div style="padding: 4px 14px; font-size: 0.75rem; font-weight: 700; color: var(--poseai-nav-muted); text-transform: uppercase;">MORE</div>

      ${MORE_ITEMS.map((m) => {
        const isActive = m.id === currentRoute;
        return `
        <a class="poseai-navbar__drawer-link ${isActive ? "active" : ""}" 
           href="${m.href}" 
           ${isActive ? 'aria-current="page"' : ""}>
          <span>${m.label}</span>
        </a>`;
      }).join("")}

      <div class="poseai-navbar__drawer-divider"></div>

      <a class="poseai-navbar__drawer-link" href="/cart">
        <span>🛒 Cart</span>
        <span class="poseai-navbar__badge hidden" id="poseaiDrawerCartBadge" style="position: static;">0</span>
      </a>

      <a class="poseai-navbar__drawer-link" href="/achievements">
        <span>🔔 Notifications</span>
      </a>

      <a class="poseai-navbar__drawer-link ${currentRoute === "profile" ? "active" : ""}" href="/profile">
        <span>👤 Profile & Settings</span>
      </a>
    </div>

    <div class="poseai-navbar__drawer-footer">
      <button class="poseai-navbar__profile-item danger" id="poseaiDrawerLogoutBtn" type="button" style="padding: 10px 14px;">
        <span>🚪 Logout</span>
      </button>
    </div>
  </div>
</nav>
`;
  }

  // Mount navbar into page
  function mountNavbar() {
    let container = document.getElementById("app-header");
    if (!container) {
      container = document.createElement("div");
      container.id = "app-header";
      document.body.prepend(container);
    }

    container.innerHTML = renderNavbarHTML();
    setupNavbarEvents();
    fetchUserData();
    refreshCartCount();
    fetchNotificationCount();
  }

  // Attach interactive events
  function setupNavbarEvents() {
    const moreBtn = document.getElementById("poseaiMoreBtn");
    const moreDropdown = document.getElementById("poseaiMoreDropdown");
    const profileBtn = document.getElementById("poseaiProfileBtn");
    const profileMenu = document.getElementById("poseaiProfileMenu");
    const hamburgerBtn = document.getElementById("poseaiHamburgerBtn");
    const drawer = document.getElementById("poseaiMobileDrawer");
    const backdrop = document.getElementById("poseaiDrawerBackdrop");
    const drawerCloseBtn = document.getElementById("poseaiDrawerCloseBtn");
    const logoutBtn = document.getElementById("poseaiLogoutBtn");
    const drawerLogoutBtn = document.getElementById("poseaiDrawerLogoutBtn");
    const notifBtn = document.getElementById("poseaiNotifBtn");

    function closeAllDropdowns() {
      if (moreDropdown) moreDropdown.classList.remove("show");
      if (moreBtn) moreBtn.setAttribute("aria-expanded", "false");
      if (profileMenu) profileMenu.classList.remove("show");
      if (profileBtn) profileBtn.setAttribute("aria-expanded", "false");
    }

    function openMobileDrawer() {
      closeAllDropdowns();
      if (drawer) drawer.classList.add("open");
      if (backdrop) backdrop.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function closeMobileDrawer() {
      if (drawer) drawer.classList.remove("open");
      if (backdrop) backdrop.classList.remove("open");
      document.body.style.overflow = "";
    }

    // More dropdown toggle
    if (moreBtn && moreDropdown) {
      moreBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        const isOpen = moreDropdown.classList.contains("show");
        closeAllDropdowns();
        if (!isOpen) {
          moreDropdown.classList.add("show");
          moreBtn.setAttribute("aria-expanded", "true");
        }
      });
    }

    // Profile menu toggle
    if (profileBtn && profileMenu) {
      profileBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        const isOpen = profileMenu.classList.contains("show");
        closeAllDropdowns();
        if (!isOpen) {
          profileMenu.classList.add("show");
          profileBtn.setAttribute("aria-expanded", "true");
        }
      });
    }

    // Outside click closes menus
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#poseaiMoreBtn") && !e.target.closest("#poseaiMoreDropdown") &&
          !e.target.closest("#poseaiProfileBtn") && !e.target.closest("#poseaiProfileMenu")) {
        closeAllDropdowns();
      }
    });

    // Escape key closes menus and drawer
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeAllDropdowns();
        closeMobileDrawer();
      }
    });

    // Hamburger drawer controls
    if (hamburgerBtn) hamburgerBtn.addEventListener("click", openMobileDrawer);
    if (drawerCloseBtn) drawerCloseBtn.addEventListener("click", closeMobileDrawer);
    if (backdrop) backdrop.addEventListener("click", closeMobileDrawer);

    // Notifications button action
    if (notifBtn) {
      notifBtn.addEventListener("click", function () {
        window.location.assign("/achievements");
      });
    }

    // Logout handling
    async function handleLogout() {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      try {
        await fetch(getUrl("/auth/logout"), { method: "POST", credentials: "include" });
      } catch (_) {
        // Fallback endpoint
        try {
          await fetch(getUrl("/api/auth/logout"), { method: "POST", credentials: "include" });
        } catch (__) {}
      }
      window.location.href = "/login";
    }

    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
    if (drawerLogoutBtn) drawerLogoutBtn.addEventListener("click", handleLogout);
  }

  // Dynamic user data
  async function fetchUserData() {
    const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
    try {
      const res = await fetch(getUrl("/api/auth/me"), { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      const user = data.user || data;
      if (!user) return;

      const name = user.name || user.full_name || user.username || "Athlete";
      const initial = name.trim().charAt(0).toUpperCase();

      const nameEl = document.getElementById("poseaiNavUserName");
      const initialEl = document.getElementById("poseaiAvatarInitial");
      const imgEl = document.getElementById("poseaiAvatarImg");

      if (nameEl) nameEl.textContent = name;
      if (user.profile_picture && imgEl) {
        imgEl.src = user.profile_picture;
        imgEl.style.display = "block";
        if (initialEl) initialEl.style.display = "none";
      } else if (initialEl) {
        initialEl.textContent = initial;
      }
    } catch (_) {}
  }

  // Real cart badge count
  async function refreshCartCount() {
    const badge = document.getElementById("poseaiCartBadge");
    const drawerBadge = document.getElementById("poseaiDrawerCartBadge");
    if (!badge) return;

    const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
    try {
      const res = await fetch(getUrl("/api/market/cart-count"), {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return;
      const data = await res.json();
      const count = Number(data.item_count || 0);

      if (count > 0) {
        const text = count > 99 ? "99+" : String(count);
        badge.textContent = text;
        badge.classList.remove("hidden");
        if (drawerBadge) {
          drawerBadge.textContent = text;
          drawerBadge.classList.remove("hidden");
        }
      } else {
        badge.classList.add("hidden");
        if (drawerBadge) drawerBadge.classList.add("hidden");
      }
    } catch (_) {}
  }

  // Real notification count
  async function fetchNotificationCount() {
    const badge = document.getElementById("poseaiNotifBadge");
    if (!badge) return;

    const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
    try {
      const res = await fetch(getUrl("/api/achievements"), {
        method: "GET",
        credentials: "include",
      });
      if (!res.ok) return;
      const data = await res.json();
      // Count newly unlocked achievements if available
      const unread = (data.achievements || []).filter((a) => a.unlocked && !a.seen).length;
      if (unread > 0) {
        badge.textContent = String(unread);
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
    } catch (_) {}
  }

  // Expose global methods for refreshing badge counts from other scripts
  window.PoseAINavbar = {
    refreshCart: refreshCartCount,
    refreshNotifications: fetchNotificationCount,
    refreshUser: fetchUserData,
  };

  // Mount when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountNavbar);
  } else {
    mountNavbar();
  }
})();
