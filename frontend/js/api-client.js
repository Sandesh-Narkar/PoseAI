/**
 * PoseAI Fitness Market — API client.
 *
 * Thin, typed wrapper over the /api/market/* REST endpoints. Every market
 * failure is normalized into a MarketApiError with `{status, code, message,
 * details}` so the UI can branch on the spec error codes (UNAUTHENTICATED,
 * INVALID_ID, INVALID_QUANTITY, PRODUCT_NOT_FOUND, PRODUCT_INACTIVE,
 * OUT_OF_STOCK, INSUFFICIENT_STOCK, RATE_LIMITED, VALIDATION_ERROR).
 */
"use strict";

(function () {
  function MarketApiError(status, code, message, details) {
    this.name = "MarketApiError";
    this.status = status;
    this.code = code;
    this.message = message || "Something went wrong.";
    this.details = details || {};
  }
  MarketApiError.prototype = Object.create(Error.prototype);
  MarketApiError.prototype.constructor = MarketApiError;

  function normalizeError(status, body) {
    var err = (body && body.error) || {};
    if (typeof err === "string") {
      return new MarketApiError(status, "SERVER_ERROR", err, {});
    }
    return new MarketApiError(
      status,
      err.code || "SERVER_ERROR",
      err.message || "Something went wrong.",
      err.details || {},
    );
  }

  async function request(path, opts) {
    var options = opts || {};
    var url = (typeof window !== "undefined" && typeof window.getApiUrl === "function")
      ? window.getApiUrl(path)
      : path;
    var res = await fetch(url, {
      method: options.method || "GET",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: options.body != null ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });

    var data = null;
    try {
      data = await res.json();
    } catch (_) {
      /* non-JSON body */
    }

    if (res.status === 401 && !options.silent) {
      window.location.href = "/login";
      throw new MarketApiError(401, "UNAUTHENTICATED", "Authentication required.", {});
    }
    if (!res.ok) {
      throw normalizeError(res.status, data);
    }
    return data;
  }

  function toQuery(filters) {
    var params = new URLSearchParams();
    var f = filters || {};
    Object.keys(f).forEach(function (key) {
      var value = f[key];
      if (value === "" || value == null) return;
      if (Array.isArray(value)) {
        if (value.length) params.set(key, value.join(","));
      } else {
        params.set(key, value);
      }
    });
    return params.toString();
  }

  var MarketAPI = {
    products: function (filters, signal) {
      var qs = toQuery(filters);
      return request("/api/market/products" + (qs ? "?" + qs : ""), { signal: signal });
    },
    product: function (productId, signal) {
      return request("/api/market/products/" + encodeURIComponent(productId), { signal: signal });
    },
    related: function (productId, signal) {
      return request("/api/market/products/" + encodeURIComponent(productId) + "/related", { signal: signal });
    },
    categories: function (signal) {
      return request("/api/market/categories", { signal: signal });
    },
    brands: function (signal) {
      return request("/api/market/brands", { signal: signal });
    },
    cart: function (signal) {
      return request("/api/market/cart", { signal: signal });
    },
    addToCart: function (productId, quantity) {
      return request("/api/market/cart", {
        method: "POST",
        body: { product_id: productId, quantity: quantity },
      });
    },
    updateQuantity: function (productId, quantity) {
      return request("/api/market/cart/" + encodeURIComponent(productId), {
        method: "PATCH",
        body: { quantity: quantity },
      });
    },
    removeItem: function (productId) {
      return request("/api/market/cart/" + encodeURIComponent(productId), { method: "DELETE" });
    },
    clearCart: function () {
      return request("/api/market/cart/clear", { method: "POST" });
    },
    home: function (signal) {
      return request("/api/market/home", { signal: signal });
    },
    orders: function (signal) {
      return request("/api/market/orders", { signal: signal });
    },
    order: function (orderId, signal) {
      return request("/api/market/orders/" + encodeURIComponent(orderId), { signal: signal });
    },
    createOrder: function (address) {
      return request("/api/market/orders", { method: "POST", body: { address: address } });
    },
    favorites: function (signal) {
      return request("/api/market/favorites", { signal: signal });
    },
    addFavorite: function (productId) {
      return request("/api/market/favorites/" + encodeURIComponent(productId), { method: "POST" });
    },
    removeFavorite: function (productId) {
      return request("/api/market/favorites/" + encodeURIComponent(productId), { method: "DELETE" });
    },
  };

  MarketAPI.MarketApiError = MarketApiError;
  window.MarketAPI = MarketAPI;
})();