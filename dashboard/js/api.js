"use strict";

/** Minimum allowed polling interval, to prevent hammering the backend. */
const MIN_POLLING_INTERVAL_MS = 250;

/**
 * Client-side API wrapper for the PoseAI Flask backend.
 * Handles connection management, polling, and typed access
 * to every supported REST endpoint.
 */
class PoseAIApi {
  /**
   * @param {Object} [options]
   * @param {string} [options.baseUrl] - Base URL of the Flask server. Defaults to
   *   http://127.0.0.1:5000 since the dashboard is often served from a different
   *   origin/port (e.g. Live Server on 5500) than the Flask backend.
   * @param {number} [options.pollingIntervalMs] - Polling interval in ms (clamped to a minimum of 250ms).
   * @param {number} [options.requestTimeoutMs] - Per-request timeout in ms.
   * @param {boolean} [options.supportsBackendReset] - Set to true only once your Flask
   *   backend actually handles a reset action on /api/update. Defaults to false, in
   *   which case resetSession() only clears client-side polling state.
   */
  constructor(options = {}) {
    const defaultBaseUrl =
      typeof window !== "undefined" &&
      window.location &&
      window.location.protocol !== "file:"
        ? `${window.location.protocol}//${window.location.host}`
        : "http://127.0.0.1:5000";

    this.baseUrl = (options.baseUrl || defaultBaseUrl).replace(/\/$/, "");

    this.pollingIntervalMs = Math.max(
      MIN_POLLING_INTERVAL_MS,
      options.pollingIntervalMs || 500,
    );
    this.requestTimeoutMs = options.requestTimeoutMs || 1000;
    this.supportsBackendReset = Boolean(options.supportsBackendReset);

    // Only endpoints that actually exist on the Flask backend.
    this.endpoints = Object.freeze({
      health: "/",
      status: "/api/status",
      workout: "/api/workout",
      summary: "/api/session",
      statistics: "/api/statistics",
      coach: "/api/coach",
      streak: "/api/streak",
      achievements: "/api/achievements",
      update: "/api/update",
      startWorkout: "/api/workout/start",
      pauseWorkout: "/api/workout/pause",
      resumeWorkout: "/api/workout/resume",
      finishWorkout: "/api/workout/finish",
      workoutFrame: "/api/workout/frame",
    });

    this.connectionStatus = "Disconnected";

    this._pollingIntervalId = null;
    this._isPolling = false;
    this._isRequestInFlight = false; // polling lock, prevents overlapping requests
    this._pollingAbortController = null; // lets disconnect()/stopPolling() cancel an in-flight poll

    // Maps endpoint path -> in-flight promise, so simultaneous callers of
    // the same GET endpoint (e.g. multiple widgets reading /api/workout)
    // share a single network request instead of firing duplicates.
    this._inFlightRequests = new Map();

    this._dataUpdateSubscribers = new Set();
    this._connectionChangeSubscribers = new Set();
    this._errorSubscribers = new Set();
  }

  // ---------------------------------------------------------------------
  // Subscriptions
  // ---------------------------------------------------------------------

  /**
   * Subscribe to dashboard data updates (emitted on every successful poll).
   * @param {(data: any) => void} callback
   * @returns {() => void} Unsubscribe function.
   */
  onDataUpdate(callback) {
    return this.#subscribe(this._dataUpdateSubscribers, callback);
  }

  /**
   * Subscribe to connection status changes ("Connecting" | "Connected" | "Disconnected").
   * @param {(status: string) => void} callback
   * @returns {() => void} Unsubscribe function.
   */
  onConnectionChange(callback) {
    return this.#subscribe(this._connectionChangeSubscribers, callback);
  }

  /**
   * Subscribe to normalized error events.
   * @param {(error: {context: string, message: string, timestamp: string}) => void} callback
   * @returns {() => void} Unsubscribe function.
   */
  onError(callback) {
    return this.#subscribe(this._errorSubscribers, callback);
  }

  #subscribe(subscriberSet, callback) {
    if (typeof callback !== "function") {
      console.warn("[api.js] Attempted to subscribe a non-function callback.");
      return () => {};
    }
    subscriberSet.add(callback);
    return () => subscriberSet.delete(callback);
  }

  #emit(subscriberSet, payload) {
    subscriberSet.forEach((callback) => {
      try {
        callback(payload);
      } catch (error) {
        console.error("[api.js] Subscriber callback threw an error:", error);
      }
    });
  }

  #setConnectionStatus(status) {
    if (this.connectionStatus === status) {
      return;
    }
    this.connectionStatus = status;
    this.#emit(this._connectionChangeSubscribers, status);
  }

  #handleError(context, error) {
    const normalizedError = {
      context,
      message: error && error.message ? error.message : String(error),
      timestamp: new Date().toISOString(),
    };
    console.error(`[api.js] Error in ${context}:`, error);
    this.#emit(this._errorSubscribers, normalizedError);
  }

  /**
   * Decides whether a parsed health-check response should be treated as
   * "backend is up." Deliberately does not assume one fixed JSON shape,
   * since #request() already guarantees that by the time this runs, Flask
   * responded with a 2xx and valid JSON — the only remaining question is
   * whether the body explicitly signals failure.
   */
  #isHealthyResponse(result) {
    if (!result || typeof result !== "object") {
      return false;
    }
    if (result.success === false || result.ok === false || result.error) {
      return false;
    }
    // Accept {success:true}, {status:"ok"/"healthy"}, {message:"..."} or
    // any other 2xx JSON body that doesn't explicitly signal failure.
    return true;
  }

  // ---------------------------------------------------------------------
  // Low-level networking
  // ---------------------------------------------------------------------

  /**
   * Performs a fetch with timeout, abort handling, and JSON parsing safety.
   * Never throws — returns null on any failure and emits an error event instead.
   * @param {string} path
   * @param {RequestInit} [requestOptions]
   * @param {AbortController} [externalController] - Optional controller so callers
   *   (like the polling loop) can cancel this specific request from outside.
   */
  async #request(path, requestOptions = {}, externalController = null) {
    const controller = externalController || new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      this.requestTimeoutMs,
    );

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        ...requestOptions,
      });

      if (!response.ok) {
        throw new Error(
          `Server responded with status ${response.status} (${response.statusText})`,
        );
      }

      try {
        return await response.json();
      } catch (parseError) {
        throw new Error("Invalid response: could not parse JSON.");
      }
    } catch (error) {
      if (error.name === "AbortError") {
        this.#handleError(
          `request:${path}`,
          new Error("Request timed out or was cancelled."),
        );
      } else if (error instanceof TypeError) {
        this.#handleError(
          `request:${path}`,
          new Error("Network error: server may be offline."),
        );
      } else {
        this.#handleError(`request:${path}`, error);
      }
      return null;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  #get(path, controller = null) {
    return this.#request(path, { method: "GET" }, controller);
  }

  #post(path, body = {}, controller = null) {
    return this.#request(
      path,
      { method: "POST", body: JSON.stringify(body) },
      controller,
    );
  }

  /**
   * GET with request deduplication: if a request to this path is already
   * in flight, returns the same promise instead of firing a duplicate
   * network call. Used for endpoints that multiple UI widgets may read
   * simultaneously (e.g. /api/workout).
   */
  #dedupedGet(path) {
    if (this._inFlightRequests.has(path)) {
      return this._inFlightRequests.get(path);
    }

    const requestPromise = this.#get(path).finally(() => {
      this._inFlightRequests.delete(path);
    });

    this._inFlightRequests.set(path, requestPromise);
    return requestPromise;
  }

  // ---------------------------------------------------------------------
  // Connection lifecycle
  // ---------------------------------------------------------------------

  /**
   * Attempts to reach the backend health endpoint and updates connection status.
   * Accepts any well-formed 2xx JSON response from "/" that doesn't explicitly
   * signal failure — it does not require a specific response shape.
   * @returns {Promise<boolean>} True if the backend is reachable.
   */
  async connect() {
    try {
      this.#setConnectionStatus("Connecting");
      const result = await this.#get(this.endpoints.health);

      if (this.#isHealthyResponse(result)) {
        this.#setConnectionStatus("Connected");
        return true;
      }

      this.#setConnectionStatus("Disconnected");
      return false;
    } catch (error) {
      this.#handleError("connect", error);
      this.#setConnectionStatus("Disconnected");
      return false;
    }
  }

  /**
   * Stops polling, aborts any in-flight polling request, and marks the client
   * as disconnected.
   * @returns {Promise<boolean>} Always true unless an unexpected error occurs.
   */
  async disconnect() {
    try {
      this.stopPolling();
      this.#setConnectionStatus("Disconnected");
      return true;
    } catch (error) {
      this.#handleError("disconnect", error);
      this.#setConnectionStatus("Disconnected");
      return false;
    }
  }

  /**
   * Pings the backend once and updates connection status accordingly.
   * @returns {Promise<boolean>} True if connected.
   */
  async checkConnection() {
    const result = await this.#get(this.endpoints.health);
    const isConnected = this.#isHealthyResponse(result);
    this.#setConnectionStatus(isConnected ? "Connected" : "Disconnected");
    return isConnected;
  }

  // ---------------------------------------------------------------------
  // Data getters (all backed by real Flask endpoints only)
  // ---------------------------------------------------------------------

  /**
   * Fetches the full dashboard status payload.
   * @returns {Promise<Object|null>}
   */
  getDashboardData() {
    return this.#get(this.endpoints.status);
  }

  /**
   * Fetches current workout state (exercise, rep, set, stage, angle, calories, time).
   * Deduplicated: concurrent calls from multiple widgets share one request.
   * @returns {Promise<Object|null>}
   */
  getWorkoutStatus() {
    return this.#dedupedGet(this.endpoints.workout);
  }

  /**
   * Fetches the current/most recent session summary.
   * @returns {Promise<Object|null>}
   */
  getSessionSummary() {
    return this.#get(this.endpoints.summary);
  }

  /**
   * Fetches aggregate statistics.
   * @returns {Promise<Object|null>}
   */
  getStatistics() {
    return this.#get(this.endpoints.statistics);
  }

  /**
   * Fetches unlocked achievements.
   * @returns {Promise<Object|null>}
   */
  getAchievements() {
    return this.#get(this.endpoints.achievements);
  }

  /**
   * Fetches the user's current streak data.
   * @returns {Promise<Object|null>}
   */
  getStreak() {
    return this.#get(this.endpoints.streak);
  }

  /**
   * Fetches AI coach feedback.
   * @returns {Promise<Object|null>}
   */
  getCoachFeedback() {
    return this.#get(this.endpoints.coach);
  }

  /**
   * Sends an update payload to the backend (e.g. settings/state sync).
   * @param {Object} [body] - Update payload.
   * @returns {Promise<Object|null>}
   */
  sendUpdate(body = {}) {
    return this.#post(this.endpoints.update, body);
  }

  /**
   * Returns just the camera-related portion of the dashboard status payload,
   * rather than the entire dashboard JSON. Falls back to the full payload
   * if the backend response doesn't include a distinct "camera" field.
   * @returns {Promise<Object|null>}
   */
  async getCameraStatus() {
    const response = await this.getDashboardData();
    if (!response) {
      return null;
    }
    const data = response.data || response;
    return data.camera || data.cameraStatus || data;
  }

  // All of the following share getWorkoutStatus()'s deduplication, so
  // calling several of these back-to-back (e.g. from different widgets
  // in the same render cycle) results in a single /api/workout request.

  /** @returns {Promise<Object|null>} Current exercise info (from workout status). */
  getCurrentExercise() {
    return this.getWorkoutStatus();
  }

  /** @returns {Promise<Object|null>} Current rep info (from workout status). */
  getCurrentRep() {
    return this.getWorkoutStatus();
  }

  /** @returns {Promise<Object|null>} Current set info (from workout status). */
  getCurrentSet() {
    return this.getWorkoutStatus();
  }

  /** @returns {Promise<Object|null>} Current exercise stage (from workout status). */
  getCurrentStage() {
    return this.getWorkoutStatus();
  }

  /** @returns {Promise<Object|null>} Current joint angle data (from workout status). */
  getCurrentAngle() {
    return this.getWorkoutStatus();
  }

  /** @returns {Promise<Object|null>} Calories burned (from workout status). */
  getCalories() {
    return this.getWorkoutStatus();
  }

  /** @returns {Promise<Object|null>} Elapsed workout time (from workout status). */
  getWorkoutTime() {
    return this.getWorkoutStatus();
  }

  // ---------------------------------------------------------------------
  // Polling
  // ---------------------------------------------------------------------

  /**
   * Starts polling /api/status on an interval and emits data-update events.
   * Safe to call multiple times — will not create duplicate polling loops.
   * Uses an internal lock so overlapping requests are never sent, and clamps
   * the interval to a sane minimum to avoid hammering the backend.
   * @param {number} [intervalMs] - Optional polling interval override (min 250ms).
   */
  startPolling(intervalMs = this.pollingIntervalMs) {
    if (this._isPolling) {
      return;
    }

    this._isPolling = true;
    this.pollingIntervalMs = Math.max(MIN_POLLING_INTERVAL_MS, intervalMs);

    this._pollingIntervalId = setInterval(async () => {
      if (this._isRequestInFlight) {
        // Previous request hasn't resolved yet — skip this tick.
        return;
      }

      this._isRequestInFlight = true;
      this._pollingAbortController = new AbortController();

      try {
        const response = await this.#get(
          this.endpoints.status,
          this._pollingAbortController,
        );
        const payload = response && response.success ? response.data : null;
        if (payload) {
          this.#emit(this._dataUpdateSubscribers, payload);
        }
      } catch (error) {
        this.#handleError("startPolling", error);
      } finally {
        this._isRequestInFlight = false;
        this._pollingAbortController = null;
      }
    }, this.pollingIntervalMs);
  }

  /**
   * Stops any active polling loop, releases the interval handle, AND aborts
   * an in-flight polling request if one is still running. This prevents a
   * "ghost" dataUpdate event from firing after pauseSession()/resetSession()
   * have already told the UI that polling stopped.
   */
  stopPolling() {
    if (this._pollingAbortController) {
      this._pollingAbortController.abort();
      this._pollingAbortController = null;
    }

    if (!this._isPolling) {
      return;
    }

    clearInterval(this._pollingIntervalId);
    this._pollingIntervalId = null;
    this._isPolling = false;
    this._isRequestInFlight = false;
  }

  // ---------------------------------------------------------------------
  // Session lifecycle (connect + poll convenience wrappers)
  // ---------------------------------------------------------------------

  /**
   * Connects to the backend and, if successful, starts polling.
   * Safe to call multiple times — will not start duplicate polling loops.
   */
  async startSession() {
    try {
      const connected = await this.connect();
      if (!connected) {
        return;
      }
      this.startPolling();
    } catch (error) {
      this.#handleError("startSession", error);
    }
  }

  /**
   * Pauses the current session by stopping polling (and aborting any
   * in-flight poll request) without disconnecting.
   */
  async pauseSession() {
    try {
      this.stopPolling();
    } catch (error) {
      this.#handleError("pauseSession", error);
    }
  }

  /**
   * Resumes a paused session. Re-checks the connection first in case the
   * backend went offline while paused, then restarts polling only if the
   * reconnect succeeds.
   */
  async resumeSession() {
    try {
      const connected = await this.connect();
      if (!connected) {
        return;
      }
      this.startPolling();
    } catch (error) {
      this.#handleError("resumeSession", error);
    }
  }

  /**
   * Resets the session. By default this only stops local polling (aborting
   * any in-flight request) — it does NOT contact the backend, since we
   * cannot assume Flask's /api/update understands a reset action unless
   * explicitly confirmed.
   *
   * Set `supportsBackendReset: true` in the constructor options once your
   * Flask backend implements this, and this method will additionally send
   * `{ action: "reset" }` to /api/update.
   * @returns {Promise<Object|null>} The backend's response if a backend reset
   *   was sent, otherwise null.
   */
  async resetSession() {
    try {
      this.stopPolling();

      if (this.supportsBackendReset) {
        return await this.sendUpdate({ action: "reset" });
      }

      return null;
    } catch (error) {
      this.#handleError("resetSession", error);
      return null;
    }
  }

  async startWorkout(payload = {}) {
    try {
      const response = await this.#post(this.endpoints.startWorkout, payload);
      const data = response && response.success ? response.data : null;
      if (data) {
        this.#emit(this._dataUpdateSubscribers, data);
      }
      return data;
    } catch (error) {
      this.#handleError("startWorkout", error);
      return null;
    }
  }

  async pauseWorkout(payload = {}) {
    try {
      const response = await this.#post(this.endpoints.pauseWorkout, payload);
      const data = response && response.success ? response.data : null;
      if (data) {
        this.#emit(this._dataUpdateSubscribers, data);
      }
      return data;
    } catch (error) {
      this.#handleError("pauseWorkout", error);
      return null;
    }
  }

  async resumeWorkout(payload = {}) {
    try {
      const response = await this.#post(this.endpoints.resumeWorkout, payload);
      const data = response && response.success ? response.data : null;
      if (data) {
        this.#emit(this._dataUpdateSubscribers, data);
      }
      return data;
    } catch (error) {
      this.#handleError("resumeWorkout", error);
      return null;
    }
  }

  async finishWorkout(payload = {}) {
    try {
      const response = await this.#post(this.endpoints.finishWorkout, payload);
      const data = response && response.success ? response.data : null;
      if (data) {
        this.#emit(this._dataUpdateSubscribers, data);
      }
      return data;
    } catch (error) {
      this.#handleError("finishWorkout", error);
      return null;
    }
  }

  async sendWorkoutFrame(payload = {}) {
    try {
      const response = await this.#post(this.endpoints.workoutFrame, payload);
      const data = response && response.success ? response.data : null;
      if (data) {
        this.#emit(this._dataUpdateSubscribers, data);
      }
      return data;
    } catch (error) {
      this.#handleError("sendWorkoutFrame", error);
      return null;
    }
  }
}

window.DashboardAPI = new PoseAIApi();
