/**
 * PoseAI Public Client Configuration
 *
 * Safe public configuration for the frontend. NEVER put private backend secrets here.
 * In production (Vercel), API_BASE_URL points to the Render backend (e.g. https://your-poseai-backend.onrender.com).
 * In development (Flask single server or local dev), API_BASE_URL defaults to empty (same origin) or http://localhost:5000.
 */
(function () {
  "use strict";
  if (typeof window === "undefined") return;

  const metaTag = document.querySelector('meta[name="api-base-url"]');
  const metaUrl = metaTag ? metaTag.getAttribute("content") : "";
  let storedUrl = "";
  try {
    storedUrl = localStorage.getItem("POSEAI_API_BASE_URL") || "";
  } catch (_) {}

  // Detect whether frontend is served standalone (e.g. Vercel, LiveServer) or directly from Flask
  let autoUrl = "";
  if (window.location && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    // If window.API_BASE_URL is not explicitly set in HTML or meta tag, keep empty for same-origin or use configured
    autoUrl = "";
  }

  // Support injected environment variables if hosted via static hosting/bundlers
  const envApiUrl =
    (typeof window !== "undefined" && (window.VITE_API_URL || window.REACT_APP_API_URL || window.RENDER_API_URL)) || "";

  window.API_BASE_URL = window.API_BASE_URL || envApiUrl || metaUrl || storedUrl || autoUrl || "";

  window.getApiUrl = function (path) {
    if (!path) return "";
    if (path.startsWith("http://") || path.startsWith("https://")) return path;
    const base = (window.API_BASE_URL || "").replace(/\/$/, "");
    const cleanPath = path.startsWith("/") ? path : "/" + path;
    return base ? `${base}${cleanPath}` : cleanPath;
  };
})();
