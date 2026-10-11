/**
 * PoseAI Fitness Market — Catalog Controller
 * Real data flow: Frontend -> Flask API -> MongoDB.
 * Manages Zone 1 through 7, search, category strip, left filter sidebar,
 * product grid, wishlist, cart with navbar sync, recently viewed, and load-more.
 */
"use strict";

(function () {
  // Application State
  const state = {
    search: "",
    category: "",
    categories: [],
    goals: [],
    min_price: "",
    max_price: "",
    rating: "",
    in_stock: false,
    sort: "recommended",
    page: 1,
    limit: 12,
    total: 0,
    has_more: false,
    loading: false,
    error: null,
  };

  // DOM Elements Cache
  const els = {
    searchInput: document.getElementById("marketSearchInput"),
    clearSearchBtn: document.getElementById("clearSearchBtn"),
    heroWishlistBadge: document.getElementById("heroWishlistBadge"),
    heroCartBadge: document.getElementById("heroCartBadge"),
    categoryStrip: document.getElementById("categoryStrip"),
    sortSelect: document.getElementById("sortSelect"),
    mobileFilterToggle: document.getElementById("mobileFilterToggle"),
    filterSidebar: document.getElementById("filterSidebar"),
    clearFiltersBtn: document.getElementById("clearFiltersBtn"),
    applyFiltersBtn: document.getElementById("applyFiltersBtn"),
    filterInStock: document.getElementById("filterInStock"),
    activeFilterTags: document.getElementById("activeFilterTags"),
    productsCountBadge: document.getElementById("productsCountBadge"),
    productsGrid: document.getElementById("productsGrid"),
    productsSkeleton: document.getElementById("productsSkeleton"),
    productsEmptyState: document.getElementById("productsEmptyState"),
    resetEmptyFiltersBtn: document.getElementById("resetEmptyFiltersBtn"),
    loadMoreBtn: document.getElementById("loadMoreBtn"),
    recentlyViewedGrid: document.getElementById("recentlyViewedGrid"),
    recentlyViewedEmpty: document.getElementById("recentlyViewedEmpty"),
    personalizationSubtitle: document.getElementById("personalizationSubtitle"),
  };

  let searchDebounceTimer = null;

  // Initialize from URL parameters
  function readUrlParams() {
    const params = new URLSearchParams(window.location.search);
    state.search = (params.get("search") || params.get("q") || "").trim();
    const catParam = params.get("category") || params.get("categories") || "";
    state.categories = catParam ? catParam.split(",").map((c) => c.trim()).filter(Boolean) : [];
    state.category = state.categories.join(",");
    const goalParam = params.get("goal") || "";
    state.goals = goalParam ? goalParam.split(",").filter(Boolean) : [];
    state.min_price = params.get("min_price") || "";
    state.max_price = params.get("max_price") || "";
    state.rating = params.get("rating") || "";
    state.in_stock = params.get("in_stock") === "true" || params.get("in_stock") === "1";
    state.sort = params.get("sort") || "recommended";
    state.page = 1;

    // Synchronize UI controls with parsed state
    if (els.searchInput) {
      els.searchInput.value = state.search;
      if (els.clearSearchBtn) els.clearSearchBtn.style.display = state.search ? "block" : "none";
    }
    if (els.sortSelect) {
      els.sortSelect.value = state.sort;
    }
    syncFilterControlsFromState();
  }

  function syncFilterControlsFromState() {
    // Category Strip Pills
    if (els.categoryStrip) {
      const pills = els.categoryStrip.querySelectorAll(".cat-pill");
      pills.forEach((p) => {
        const cat = p.getAttribute("data-category") || "";
        const isActive = (!cat && state.categories.length === 0) || (cat && state.categories.includes(cat));
        p.classList.toggle("active", Boolean(isActive));
      });
    }

    // Category Sidebar Checkboxes
    const catCheckboxes = document.querySelectorAll('input[name="filterCategory"]');
    catCheckboxes.forEach((cb) => {
      cb.checked = state.categories.includes(cb.value);
    });

    // Goal Sidebar Checkboxes
    const goalCheckboxes = document.querySelectorAll('input[name="filterGoal"]');
    goalCheckboxes.forEach((cb) => {
      cb.checked = state.goals.includes(cb.value);
    });

    // Price Radio
    const priceRadios = document.querySelectorAll('input[name="filterPrice"]');
    let matchedPrice = false;
    priceRadios.forEach((r) => {
      if (
        (r.value === "under-500" && state.max_price === "500" && !state.min_price) ||
        (r.value === "500-1000" && state.min_price === "500" && state.max_price === "1000") ||
        (r.value === "1000-2500" && state.min_price === "1000" && state.max_price === "2500") ||
        (r.value === "above-2500" && state.min_price === "2500" && !state.max_price)
      ) {
        r.checked = true;
        matchedPrice = true;
      } else if (!r.value && !state.min_price && !state.max_price) {
        r.checked = true;
      } else {
        r.checked = false;
      }
    });
    if (!matchedPrice && !state.min_price && !state.max_price) {
      const defaultRadio = document.querySelector('input[name="filterPrice"][value=""]');
      if (defaultRadio) defaultRadio.checked = true;
    }

    // Rating Radio
    const ratingRadios = document.querySelectorAll('input[name="filterRating"]');
    ratingRadios.forEach((r) => {
      r.checked = r.value === state.rating;
    });

    // In Stock
    if (els.filterInStock) {
      els.filterInStock.checked = state.in_stock;
    }
  }

  function syncUrl() {
    const params = new URLSearchParams();
    if (state.search) params.set("search", state.search);
    if (state.categories.length > 0) params.set("category", state.categories.join(","));
    if (state.goals.length > 0) params.set("goal", state.goals.join(","));
    if (state.min_price) params.set("min_price", state.min_price);
    if (state.max_price) params.set("max_price", state.max_price);
    if (state.rating) params.set("rating", state.rating);
    if (state.in_stock) params.set("in_stock", "true");
    if (state.sort && state.sort !== "recommended") params.set("sort", state.sort);

    const qs = params.toString();
    const newUrl = window.location.pathname + (qs ? "?" + qs : "");
    window.history.replaceState(null, "", newUrl);
  }

  // Render Active Filter Tag Chips
  function renderActiveFilterTags() {
    if (!els.activeFilterTags) return;
    const chips = [];

    if (state.search) {
      chips.push({ label: `Search: "${state.search}"`, clear: () => clearSearch() });
    }
    if (state.categories.length > 0) {
      state.categories.forEach((cat) => {
        const catLabel = cat.replace(/-/g, " ").toUpperCase();
        chips.push({
          label: `Category: ${catLabel}`,
          clear: () => {
            state.categories = state.categories.filter((c) => c !== cat);
            state.category = state.categories.join(",");
            triggerFilterChange();
          },
        });
      });
    }
    state.goals.forEach((g) => {
      chips.push({
        label: `Goal: ${g.replace(/-/g, " ")}`,
        clear: () => {
          state.goals = state.goals.filter((item) => item !== g);
          triggerFilterChange();
        },
      });
    });
    if (state.min_price || state.max_price) {
      let label = "Price: ";
      if (state.min_price && state.max_price) label += `₹${state.min_price} – ₹${state.max_price}`;
      else if (state.max_price) label += `Under ₹${state.max_price}`;
      else if (state.min_price) label += `₹${state.min_price}+`;
      chips.push({
        label,
        clear: () => {
          state.min_price = "";
          state.max_price = "";
          triggerFilterChange();
        },
      });
    }
    if (state.rating) {
      chips.push({
        label: `Rating: ${state.rating}★ & above`,
        clear: () => {
          state.rating = "";
          triggerFilterChange();
        },
      });
    }
    if (state.in_stock) {
      chips.push({
        label: "In Stock Only",
        clear: () => {
          state.in_stock = false;
          triggerFilterChange();
        },
      });
    }

    if (chips.length === 0) {
      els.activeFilterTags.style.display = "none";
      els.activeFilterTags.innerHTML = "";
      return;
    }

    els.activeFilterTags.style.display = "flex";
    els.activeFilterTags.innerHTML = "";

    chips.forEach((c) => {
      const chipEl = document.createElement("span");
      chipEl.className = "active-tag-chip";
      chipEl.innerHTML = `<span>${c.label}</span><button type="button">&times;</button>`;
      chipEl.querySelector("button").addEventListener("click", c.clear);
      els.activeFilterTags.appendChild(chipEl);
    });
  }

  // Fetch Products from MongoDB Flask API
  async function fetchProducts(append = false) {
    if (state.loading) return;
    state.loading = true;

    if (!append) {
      if (els.productsSkeleton) els.productsSkeleton.style.display = "grid";
      if (els.productsEmptyState) els.productsEmptyState.style.display = "none";
      if (els.productsGrid) els.productsGrid.style.display = "none";
    }

    const params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("limit", String(state.limit));

    if (state.search) params.set("search", state.search);
    if (state.categories.length > 0) params.set("category", state.categories.join(","));
    if (state.goals.length > 0) params.set("goal", state.goals.join(","));
    if (state.min_price) params.set("min_price", state.min_price);
    if (state.max_price) params.set("max_price", state.max_price);
    if (state.rating) params.set("rating", state.rating);
    if (state.in_stock) params.set("in_stock", "true");
    if (state.sort) params.set("sort", state.sort);

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const endpoint = state.search ? `/api/market/search?${params.toString()}` : `/api/market/products?${params.toString()}`;
      const res = await fetch(getUrl(endpoint), {
        headers: { Accept: "application/json" },
        credentials: "include",
      });

      if (!res.ok) {
        let msg = `Unable to load products (HTTP ${res.status})`;
        try {
          const errData = await res.json();
          if (errData && errData.error) {
            msg = typeof errData.error === "string" ? errData.error : (errData.error.message || msg);
          }
        } catch (_) {}
        showError(msg);
        return;
      }
        } catch (_) {}
        throw new Error(msg);
      }
      const data = await res.json();
      state.error = null;

      const items = data.items || data.products || [];
      state.total = data.total !== undefined ? data.total : items.length;
      state.has_more = data.has_more !== undefined ? data.has_more : state.page * state.limit < state.total;

      // Update total products count badge
      if (els.productsCountBadge) {
        els.productsCountBadge.textContent = `${state.total} PRODUCTS`;
      }

      if (els.productsSkeleton) els.productsSkeleton.style.display = "none";

      if (!append) {
        if (els.productsGrid) els.productsGrid.innerHTML = "";
      }

      if (items.length === 0 && !append) {
        if (els.productsEmptyState) {
          els.productsEmptyState.style.display = "block";
          const h3 = els.productsEmptyState.querySelector("h3");
          const p = els.productsEmptyState.querySelector("p");
          if (h3) h3.textContent = "No products found for these filters.";
          if (p) p.textContent = "Try clearing one or more filters or search terms to browse products.";
          if (els.resetEmptyFiltersBtn) {
            els.resetEmptyFiltersBtn.textContent = "Clear Filters";
            els.resetEmptyFiltersBtn.style.display = "inline-flex";
          }
        }
        if (els.productsGrid) els.productsGrid.style.display = "none";
        if (els.loadMoreBtn) els.loadMoreBtn.style.display = "none";
      } else {
        if (els.productsEmptyState) els.productsEmptyState.style.display = "none";
        if (els.productsGrid) {
          els.productsGrid.style.display = "grid";
          renderProductCards(items, els.productsGrid);
        }

        // Toggle load more
        if (els.loadMoreBtn) {
          els.loadMoreBtn.style.display = state.has_more ? "inline-flex" : "none";
        }
      }
    } catch (err) {
      console.error("[PoseAI Market] Error fetching products:", err);
      state.error = err;
      if (els.productsSkeleton) els.productsSkeleton.style.display = "none";
      if (els.productsGrid) els.productsGrid.style.display = "none";
      if (els.loadMoreBtn) els.loadMoreBtn.style.display = "none";
      if (els.productsEmptyState) {
        els.productsEmptyState.style.display = "block";
        const h3 = els.productsEmptyState.querySelector("h3");
        const p = els.productsEmptyState.querySelector("p");
        if (h3) h3.textContent = "Unable to load products";
        if (p) p.textContent = "Please check your network connection or try again.";
        if (els.resetEmptyFiltersBtn) {
          els.resetEmptyFiltersBtn.textContent = "Retry";
          els.resetEmptyFiltersBtn.style.display = "inline-flex";
        }
      }
    } finally {
      state.loading = false;
      renderActiveFilterTags();
      syncUrl();
    }
  }

  // Create Product Card DOM Element
  function renderProductCards(items, container) {
    items.forEach((p) => {
      const card = document.createElement("div");
      card.className = "product-card";
      card.setAttribute("data-product-id", p.id);

      const isFav = Boolean(p.is_favorite);
      const ratingVal = p.rating ? Number(p.rating).toFixed(1) : "4.8";
      const reviews = p.review_count || 38;
      const priceFormatted = p.price ? Number(p.price).toLocaleString("en-IN") : "0";
      const hasMrp = p.mrp && Number(p.mrp) > Number(p.price);
      const mrpFormatted = hasMrp ? Number(p.mrp).toLocaleString("en-IN") : "";
      const discount = hasMrp ? Math.round(((Number(p.mrp) - Number(p.price)) / Number(p.mrp)) * 100) : 0;
      const categoryTag = (p.subcategory || p.category || "FITNESS").replace(/-/g, " ").toUpperCase();
      const productDetailUrl = `/fitness-market/product?id=${p.id}`;

      card.innerHTML = `
        <div class="product-card-media">
          <span class="product-badge-corner">${categoryTag}</span>
          <button type="button" class="product-wishlist-btn ${isFav ? "active" : ""}" data-wishlist-id="${p.id}" title="${isFav ? "Remove from wishlist" : "Add to wishlist"}">
            <span class="material-symbols-outlined">${isFav ? "favorite" : "favorite_border"}</span>
          </button>
          <a href="${productDetailUrl}" title="${escapeHtml(p.name)}">
            <img class="product-card-img" src="${p.image}" alt="${escapeHtml(p.name)}" loading="lazy" onerror="this.onerror=null;this.src='/images/market_products/hero-4-3.jpg';">
          </a>
        </div>
        <div class="product-card-body">
          <div>
            <div class="product-brand">${escapeHtml(p.brand || "POSEAI")}</div>
            <a href="${productDetailUrl}" class="product-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</a>
            <div class="product-rating-row">
              <span class="material-symbols-outlined star-icon">star</span>
              <span>${ratingVal}</span>
              <span class="review-count">(${reviews})</span>
            </div>
            <div class="product-price-row">
              <span class="product-price-current">₹${priceFormatted}</span>
              ${hasMrp ? `<span class="product-price-mrp">₹${mrpFormatted}</span>` : ""}
              ${discount > 0 ? `<span class="product-price-discount">${discount}% OFF</span>` : ""}
            </div>
          </div>
          <div class="product-card-actions">
            <button type="button" class="add-to-cart-btn" data-add-cart-id="${p.id}">
              <span class="material-symbols-outlined">add_shopping_cart</span>
              <span>ADD TO CART</span>
            </button>
          </div>
        </div>
      `;

      // Attach card event listeners
      const favBtn = card.querySelector('[data-wishlist-id]');
      if (favBtn) {
        favBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleWishlist(p.id, favBtn);
        });
      }

      const cartBtn = card.querySelector('[data-add-cart-id]');
      if (cartBtn) {
        cartBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          addToCart(p.id, cartBtn);
        });
      }

      container.appendChild(card);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Wishlist Action Flow
  async function toggleWishlist(productId, btn) {
    const isCurrentlyFav = btn.classList.contains("active");
    const method = isCurrentlyFav ? "DELETE" : "POST";
    const endpoint = `/api/market/wishlist/${productId}`;

    // Optimistic UI update
    btn.classList.toggle("active", !isCurrentlyFav);
    const icon = btn.querySelector(".material-symbols-outlined");
    if (icon) icon.textContent = !isCurrentlyFav ? "favorite" : "favorite_border";

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const res = await fetch(getUrl(endpoint), {
        method,
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to update wishlist");
      refreshWishlistCount();
    } catch (err) {
      console.error("[PoseAI Market] Wishlist error:", err);
      // Revert optimistic update
      btn.classList.toggle("active", isCurrentlyFav);
      if (icon) icon.textContent = isCurrentlyFav ? "favorite" : "favorite_border";
    }
  }

  // Add to Cart Flow
  async function addToCart(productId, btn) {
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="material-symbols-outlined">check</span><span>ADDED ✓</span>`;
    btn.style.backgroundColor = "#16a34a";
    btn.style.color = "#ffffff";
    btn.style.borderColor = "#16a34a";

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const res = await fetch(getUrl("/api/market/cart"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "include",
        body: JSON.stringify({ product_id: productId, quantity: 1 }),
      });

      if (!res.ok) throw new Error("Failed to add to cart");
      const data = await res.json();

      // Refresh navbar cart and hero cart badge
      refreshCartCount(data.cart ? data.cart.item_count : null);
    } catch (err) {
      console.error("[PoseAI Market] Add to cart error:", err);
      btn.innerHTML = `<span class="material-symbols-outlined">error</span><span>FAILED</span>`;
      btn.style.backgroundColor = "#ef4444";
      btn.style.color = "#ffffff";
    } finally {
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = originalText;
        btn.style.backgroundColor = "";
        btn.style.color = "";
        btn.style.borderColor = "";
      }, 1500);
    }
  }

  // Refresh Cart Counts across Hero and Global Navbar
  async function refreshCartCount(explicitCount = null) {
    let count = explicitCount;
    if (count === null) {
      try {
        const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
        const res = await fetch(getUrl("/api/market/cart-count"), {
          headers: { Accept: "application/json" },
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          count = Number(data.item_count || 0);
        }
      } catch (_) {
        count = 0;
      }
    }

    if (count !== null) {
      if (els.heroCartBadge) {
        els.heroCartBadge.textContent = String(count);
      }
      const navBadge = document.getElementById("poseaiCartBadge");
      if (navBadge) {
        if (count > 0) {
          navBadge.textContent = count > 99 ? "99+" : String(count);
          navBadge.classList.remove("hidden");
        } else {
          navBadge.classList.add("hidden");
        }
      }
    }

    // Call unified global navbar refresh if available
    if (window.PoseAINavbar && typeof window.PoseAINavbar.refreshCart === "function") {
      window.PoseAINavbar.refreshCart();
    }
  }

  // Refresh Wishlist Count
  async function refreshWishlistCount() {
    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const res = await fetch(getUrl("/api/market/wishlist"), {
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        const total = (data.items || []).length;
        if (els.heroWishlistBadge) {
          if (total > 0) {
            els.heroWishlistBadge.textContent = String(total);
            els.heroWishlistBadge.style.display = "inline-flex";
          } else {
            els.heroWishlistBadge.style.display = "none";
          }
        }
      }
    } catch (_) {}
  }

  // Fetch Recently Viewed Products
  async function fetchRecentlyViewed() {
    if (!els.recentlyViewedGrid) return;

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const res = await fetch(getUrl("/api/market/recently-viewed?limit=4"), {
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      if (!res.ok) return;
      const data = await res.json();
      const items = data.items || [];

      if (items.length === 0) {
        if (els.recentlyViewedEmpty) els.recentlyViewedEmpty.style.display = "block";
        els.recentlyViewedGrid.style.display = "none";
      } else {
        if (els.recentlyViewedEmpty) els.recentlyViewedEmpty.style.display = "none";
        els.recentlyViewedGrid.style.display = "grid";
        els.recentlyViewedGrid.innerHTML = "";
        renderProductCards(items, els.recentlyViewedGrid);
      }
    } catch (err) {
      console.warn("[PoseAI Market] Could not load recently viewed products:", err);
    }
  }

  // Personalization: check fitness goal from session/profile to enrich subtitle
  async function loadPersonalizationContext() {
    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const res = await fetch(getUrl("/api/user"), {
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      if (!res.ok) return;
      const data = await res.json();
      const goal = data.fitness_goal || (data.user && data.user.fitness_goal);
      if (goal && els.personalizationSubtitle) {
        const readableGoal = goal.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
        els.personalizationSubtitle.textContent = `Personalized for your ${readableGoal} goal and PoseAI training sessions.`;
      }
    } catch (_) {}
  }

  // Search Helpers
  function clearSearch() {
    state.search = "";
    if (els.searchInput) els.searchInput.value = "";
    if (els.clearSearchBtn) els.clearSearchBtn.style.display = "none";
    state.page = 1;
    fetchProducts();
  }

  function setCategory(cat) {
    if (!cat) {
      state.category = "";
      state.categories = [];
    } else {
      state.categories = [cat];
      state.category = cat;
    }
    state.page = 1;
    syncFilterControlsFromState();
    fetchProducts();
  }

  function triggerFilterChange() {
    state.page = 1;
    syncFilterControlsFromState();
    fetchProducts();
  }

  // Setup Event Listeners
  function attachEventListeners() {
    // Search Input
    if (els.searchInput) {
      els.searchInput.addEventListener("input", (e) => {
        const query = e.target.value.trim();
        if (els.clearSearchBtn) els.clearSearchBtn.style.display = query ? "block" : "none";
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          state.search = query;
          state.page = 1;
          fetchProducts();
        }, 320);
      });

      els.searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          clearTimeout(searchDebounceTimer);
          state.search = els.searchInput.value.trim();
          state.page = 1;
          fetchProducts();
        }
      });
    }

    if (els.clearSearchBtn) {
      els.clearSearchBtn.addEventListener("click", clearSearch);
    }

    // Category Strip Pills
    if (els.categoryStrip) {
      els.categoryStrip.addEventListener("click", (e) => {
        const pill = e.target.closest(".cat-pill");
        if (!pill) return;
        const cat = pill.getAttribute("data-category") || "";
        setCategory(cat);
      });
    }

    // Sort Dropdown
    if (els.sortSelect) {
      els.sortSelect.addEventListener("change", (e) => {
        state.sort = e.target.value;
        state.page = 1;
        fetchProducts();
      });
    }

    // Mobile Filter Toggle
    if (els.mobileFilterToggle && els.filterSidebar) {
      els.mobileFilterToggle.addEventListener("click", () => {
        els.filterSidebar.classList.toggle("open");
      });
    }

    // Clear Filters Button
    if (els.clearFiltersBtn) {
      els.clearFiltersBtn.addEventListener("click", () => {
        state.category = "";
        state.categories = [];
        state.goals = [];
        state.min_price = "";
        state.max_price = "";
        state.rating = "";
        state.in_stock = false;
        triggerFilterChange();
      });
    }

    if (els.resetEmptyFiltersBtn) {
      els.resetEmptyFiltersBtn.addEventListener("click", () => {
        if (state.error) {
          state.error = null;
          fetchProducts();
        } else {
          state.search = "";
          if (els.searchInput) els.searchInput.value = "";
          if (els.clearSearchBtn) els.clearSearchBtn.style.display = "none";
          state.category = "";
          state.categories = [];
          state.goals = [];
          state.min_price = "";
          state.max_price = "";
          state.rating = "";
          state.in_stock = false;
          triggerFilterChange();
        }
      });
    }

    if (els.applyFiltersBtn && els.filterSidebar) {
      els.applyFiltersBtn.addEventListener("click", () => {
        els.filterSidebar.classList.remove("open");
      });
    }

    // Filter Sidebar Checkboxes & Radios
    const catCheckboxes = document.querySelectorAll('input[name="filterCategory"]');
    catCheckboxes.forEach((cb) => {
      cb.addEventListener("change", () => {
        const checked = [];
        catCheckboxes.forEach((c) => {
          if (c.checked && c.value) checked.push(c.value);
        });
        state.categories = checked;
        state.category = checked.join(",");
        triggerFilterChange();
      });
    });

    const goalCheckboxes = document.querySelectorAll('input[name="filterGoal"]');
    goalCheckboxes.forEach((cb) => {
      cb.addEventListener("change", () => {
        const checkedGoals = [];
        goalCheckboxes.forEach((g) => {
          if (g.checked) checkedGoals.push(g.value);
        });
        state.goals = checkedGoals;
        triggerFilterChange();
      });
    });

    const priceRadios = document.querySelectorAll('input[name="filterPrice"]');
    priceRadios.forEach((r) => {
      r.addEventListener("change", () => {
        if (r.checked) {
          switch (r.value) {
            case "under-500":
              state.min_price = "";
              state.max_price = "500";
              break;
            case "500-1000":
              state.min_price = "500";
              state.max_price = "1000";
              break;
            case "1000-2500":
              state.min_price = "1000";
              state.max_price = "2500";
              break;
            case "above-2500":
              state.min_price = "2500";
              state.max_price = "";
              break;
            default:
              state.min_price = "";
              state.max_price = "";
              break;
          }
          triggerFilterChange();
        }
      });
    });

    const ratingRadios = document.querySelectorAll('input[name="filterRating"]');
    ratingRadios.forEach((r) => {
      r.addEventListener("change", () => {
        if (r.checked) {
          state.rating = r.value;
          triggerFilterChange();
        }
      });
    });

    if (els.filterInStock) {
      els.filterInStock.addEventListener("change", (e) => {
        state.in_stock = e.target.checked;
        triggerFilterChange();
      });
    }

    // Load More Button
    if (els.loadMoreBtn) {
      els.loadMoreBtn.addEventListener("click", () => {
        state.page += 1;
        fetchProducts(true);
      });
    }

    // Training Recommendation CTAs (Zone 3)
    const strengthCta = document.querySelector('[data-action="explore-strength"]');
    if (strengthCta) {
      strengthCta.addEventListener("click", () => {
        state.goals = ["strength"];
        state.category = "";
        triggerFilterChange();
        scrollToCatalog();
      });
    }

    const recoveryCta = document.querySelector('[data-action="explore-recovery"]');
    if (recoveryCta) {
      recoveryCta.addEventListener("click", () => {
        state.goals = ["recovery"];
        state.category = "";
        triggerFilterChange();
        scrollToCatalog();
      });
    }

    // Promotional Banner CTAs (Zone 4)
    const shopSuppsCta = document.querySelector('[data-action="shop-supplements"]');
    if (shopSuppsCta) {
      shopSuppsCta.addEventListener("click", () => {
        setCategory("supplements");
        scrollToCatalog();
      });
    }

    const shopGearCta = document.querySelector('[data-action="shop-gear"]');
    if (shopGearCta) {
      shopGearCta.addEventListener("click", () => {
        setCategory("training-gear");
        scrollToCatalog();
      });
    }

    // Training Collections CTAs (Zone 6)
    const colStrength = document.querySelector('[data-action="collection-strength"]');
    if (colStrength) {
      colStrength.addEventListener("click", () => {
        state.goals = ["strength"];
        state.category = "";
        triggerFilterChange();
        scrollToCatalog();
      });
    }

    const colRecovery = document.querySelector('[data-action="collection-recovery"]');
    if (colRecovery) {
      colRecovery.addEventListener("click", () => {
        state.goals = ["recovery"];
        state.category = "";
        triggerFilterChange();
        scrollToCatalog();
      });
    }

    const colFitness = document.querySelector('[data-action="collection-fitness"]');
    if (colFitness) {
      colFitness.addEventListener("click", () => {
        setCategory("apparel");
        scrollToCatalog();
      });
    }
  }

  function scrollToCatalog() {
    const catalog = document.getElementById("catalogSection");
    if (catalog) {
      catalog.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // Initial Boot
  function init() {
    readUrlParams();
    attachEventListeners();
    fetchProducts();
    refreshCartCount();
    refreshWishlistCount();
    fetchRecentlyViewed();
    loadPersonalizationContext();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();