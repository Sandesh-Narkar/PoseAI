/**
 * PoseAI - AI Fitness Trainer
 * dashboard/js/app.js
 *
 * Application Entry Point / Controller
 * -------------------------------------------------------------------------
 * Responsibilities:
 *   - Initialize the dashboard on page load
 *   - Load and expose default dashboard values
 *   - Register global event listeners
 *   - Start/stop the workout timer clock
 *   - Delegate UI rendering to dashboard.js
 *   - Delegate data/communication concerns to api.js
 *
 * This file does NOT render UI and does NOT talk to any backend directly.
 * It only orchestrates calls to DashboardUI (dashboard.js) and
 * DashboardAPI (api.js), which are expected to be loaded beforehand and
 * exposed on the global window object.
 * -------------------------------------------------------------------------
 */

"use strict";

(() => {
  /* ==========================================================================
     1. CONSTANTS / DEFAULT DATA
     ========================================================================== */

  const CONNECTION_STATE = Object.freeze({
    CONNECTED: "Connected",
    DISCONNECTED: "Disconnected",
    CONNECTING: "Connecting",
  });

  const DEFAULT_DASHBOARD_DATA = Object.freeze({
    exerciseName: "No Exercise Selected",
    currentSet: 0,
    goalSet: 3,
    currentRep: 0,
    goalRep: 15,
    totalReps: 0,
    workoutTime: "00:00",
    calories: "0.0 kcal",
    stage: "Waiting...",
    feedback: "Waiting for Camera...",
    currentStreak: "0 Days",
    xp: 0,
    todaysGoalPercent: "0%",
    setProgress: "All Empty",
  });

  const TIMER_TICK_INTERVAL_MS = 1000;
  const FRAME_CAPTURE_INTERVAL_MS = 300;

  /* ==========================================================================
     2. APPLICATION STATE
     ========================================================================== */

  const appState = {
    connectionStatus: CONNECTION_STATE.DISCONNECTED,
    timerIntervalId: null,
    timerSeconds: 0,
    isTimerRunning: false,
    isInitialized: false,
    stream: null,
    videoElement: null,
    frameIntervalId: null,
    activeExercise: null,
    currentSession: null,
    cameraReady: false,
    workoutPending: false,
  };

  /* ==========================================================================
     3. UTILITY HELPERS
     ========================================================================== */

  /**
   * Safely calls a method on a globally exposed module (e.g. DashboardUI,
   * DashboardAPI) if that module and method exist. Prevents hard failures
   * if dashboard.js or api.js have not been loaded yet.
   *
   * @param {object|undefined} moduleRef - The global module reference.
   * @param {string} methodName - The method name to invoke.
   * @param {...*} args - Arguments to forward to the method.
   * @returns {*} The method's return value, or undefined if unavailable.
   */
  function safeModuleCall(moduleRef, methodName, ...args) {
    try {
      if (moduleRef && typeof moduleRef[methodName] === "function") {
        return moduleRef[methodName](...args);
      }
      console.warn(
        `[app.js] Skipped call: "${methodName}" is not available yet.`,
      );
    } catch (error) {
      console.error(`[app.js] Error while calling "${methodName}":`, error);
    }
    return undefined;
  }

  /**
   * Formats a total number of elapsed seconds into MM:SS display format.
   *
   * @param {number} totalSeconds
   * @returns {string} Formatted time string, e.g. "05:32".
   */
  function formatElapsedTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const pad = (value) => String(value).padStart(2, "0");
    return `${pad(minutes)}:${pad(seconds)}`;
  }

  /* ==========================================================================
     4. CONNECTION STATUS
     ========================================================================== */

  /**
   * Updates the internal connection status and notifies the UI layer.
   * Valid states: Connected, Disconnected, Connecting.
   *
   * @param {string} [newStatus] - One of CONNECTION_STATE values.
   *                                Defaults to re-broadcasting current status.
   */
  function updateConnectionStatus(newStatus = appState.connectionStatus) {
    try {
      const validStates = Object.values(CONNECTION_STATE);

      if (!validStates.includes(newStatus)) {
        console.warn(
          `[app.js] Ignored invalid connection status: "${newStatus}"`,
        );
        return;
      }

      appState.connectionStatus = newStatus;
      console.log(`[app.js] Connection status updated: ${newStatus}`);

      safeModuleCall(window.DashboardUI, "setConnectionStatus", newStatus);
    } catch (error) {
      console.error("[app.js] Failed to update connection status:", error);
    }
  }

  /* ==========================================================================
     5. TIMER / CLOCK
     ========================================================================== */

  /**
   * Starts the dashboard workout timer. Increments once per second and
   * forwards the formatted time to the UI layer. Safe to call multiple
   * times; will not create duplicate intervals.
   */
  function startClock() {
    try {
      if (appState.isTimerRunning) {
        console.warn("[app.js] Clock is already running.");
        return;
      }

      appState.isTimerRunning = true;
      appState.timerIntervalId = setInterval(() => {
        appState.timerSeconds += 1;
        const formattedTime = formatElapsedTime(appState.timerSeconds);
        safeModuleCall(window.DashboardUI, "updateWorkoutTimer", formattedTime);
      }, TIMER_TICK_INTERVAL_MS);

      console.log("[app.js] Clock started.");
    } catch (error) {
      console.error("[app.js] Failed to start clock:", error);
    }
  }

  /**
   * Stops the dashboard workout timer without resetting elapsed time.
   */
  function stopClock() {
    try {
      if (!appState.isTimerRunning) {
        return;
      }

      clearInterval(appState.timerIntervalId);
      appState.timerIntervalId = null;
      appState.isTimerRunning = false;

      console.log("[app.js] Clock stopped.");
    } catch (error) {
      console.error("[app.js] Failed to stop clock:", error);
    }
  }

  /* ==========================================================================
     6. DASHBOARD LOADING / RESET
     ========================================================================== */

  /**
   * Loads the default dashboard values and forwards them to the UI layer
   * for initial rendering. Does not perform any DOM manipulation itself.
   */
  function loadDefaultDashboard() {
    try {
      console.log("[app.js] Loading default dashboard values...");
      safeModuleCall(
        window.DashboardUI,
        "renderDashboard",
        DEFAULT_DASHBOARD_DATA,
      );
    } catch (error) {
      console.error("[app.js] Failed to load default dashboard:", error);
    }
  }

  /**
   * Resets the dashboard back to its default state. Stops any running
   * timer, resets elapsed time, and re-renders default values via
   * dashboard.js.
   */
  function resetDashboard() {
    try {
      console.log("[app.js] Resetting dashboard...");

      stopClock();
      stopFrameCapture();
      stopCameraStream();
      appState.timerSeconds = 0;
      appState.activeExercise = null;
      appState.workoutPending = false;

      loadDefaultDashboard();
      safeModuleCall(window.DashboardAPI, "resetSession");

      console.log("[app.js] Dashboard reset complete.");
    } catch (error) {
      console.error("[app.js] Failed to reset dashboard:", error);
    }
  }

  /**
   * Starts an active dashboard session. Kicks off the clock and notifies
   * api.js that a session should begin (data fetching/streaming logic
   * lives entirely in api.js).
   */
  function startDashboard() {
    try {
      console.log("[app.js] Starting dashboard session...");

      updateConnectionStatus(CONNECTION_STATE.CONNECTING);
      startClock();

      safeModuleCall(window.DashboardAPI, "startSession");
    } catch (error) {
      console.error("[app.js] Failed to start dashboard session:", error);
    }
  }

  async function startWorkoutFlow() {
    try {
      console.log("[PoseAI] Camera requested");
      safeModuleCall(window.DashboardUI, "updateCameraStatus", "loading");
      safeModuleCall(window.DashboardUI, "updateFeedback", "Requesting camera access...");

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });

      const videoElement = document.querySelector("#camera-feed video") || document.createElement("video");
      videoElement.autoplay = true;
      videoElement.playsInline = true;
      videoElement.muted = true;
      videoElement.srcObject = stream;
      appState.stream = stream;
      appState.videoElement = videoElement;
      appState.cameraReady = true;

      const cameraContainer = document.querySelector("#camera-feed");
      if (cameraContainer) {
        cameraContainer.innerHTML = "";
        cameraContainer.appendChild(videoElement);
      }
      await videoElement.play().catch(() => {});
      safeModuleCall(window.DashboardUI, "updateCameraStatus", "connected");
      console.log("[PoseAI] Camera started");

      const backend = window.DashboardAPI;
      if (backend && typeof backend.startSession === "function") {
        await backend.startSession();
      }

      const exercise = appState.activeExercise || "1";
      if (backend && typeof backend.startWorkout === "function") {
        await backend.startWorkout({ exercise });
      }

      appState.workoutPending = true;
      startFrameCapture();
      safeModuleCall(window.DashboardUI, "updateFeedback", "PoseAI is tracking your workout...");
      console.log("[PoseAI] Workout session started");
    } catch (error) {
      console.error("[PoseAI] Unable to start workout flow:", error);
      safeModuleCall(window.DashboardUI, "updateCameraStatus", "disconnected");
      safeModuleCall(window.DashboardUI, "updateFeedback", error && error.message ? error.message : "Camera access failed.");
    }
  }

  function startFrameCapture() {
    if (appState.frameIntervalId) {
      clearInterval(appState.frameIntervalId);
    }

    appState.frameIntervalId = setInterval(() => {
      if (!appState.cameraReady || !appState.stream || !appState.videoElement) {
        return;
      }
      captureAndSendFrame();
    }, FRAME_CAPTURE_INTERVAL_MS);
  }

  function stopFrameCapture() {
    if (appState.frameIntervalId) {
      clearInterval(appState.frameIntervalId);
      appState.frameIntervalId = null;
    }
  }

  function stopCameraStream() {
    if (appState.stream) {
      appState.stream.getTracks().forEach((track) => track.stop());
      appState.stream = null;
    }
    if (appState.videoElement) {
      appState.videoElement.srcObject = null;
    }
    appState.cameraReady = false;
  }

  function captureAndSendFrame() {
    try {
      const video = appState.videoElement;
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 320;
      canvas.height = video.videoHeight || 240;
      const context = canvas.getContext("2d");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = canvas.toDataURL("image/jpeg", 0.7);
      const backend = window.DashboardAPI;
      if (backend && typeof backend.sendWorkoutFrame === "function") {
        backend.sendWorkoutFrame({ image: imageData, exercise: appState.activeExercise || "1" });
      }
    } catch (error) {
      console.error("[PoseAI] Frame capture failed:", error);
    }
  }

  /* ==========================================================================
     7. EVENT LISTENERS
     ========================================================================== */

  /**
   * Handles browser window resize events. Delegates any responsive
   * UI recalculation to dashboard.js.
   */
  function handleWindowResize() {
    try {
      safeModuleCall(window.DashboardUI, "handleResize", {
        width: window.innerWidth,
        height: window.innerHeight,
      });
    } catch (error) {
      console.error("[app.js] Error handling window resize:", error);
    }
  }

  /**
   * Handles document visibility changes (tab switching, minimizing).
   * Pauses/resumes relevant activity through api.js.
   */
  function handleVisibilityChange() {
    try {
      const isHidden = document.hidden;
      console.log(`[app.js] Visibility changed. Hidden: ${isHidden}`);

      if (isHidden) {
        safeModuleCall(window.DashboardAPI, "pauseSession");
      } else {
        safeModuleCall(window.DashboardAPI, "resumeSession");
      }
    } catch (error) {
      console.error("[app.js] Error handling visibility change:", error);
    }
  }

  /**
   * Placeholder handler for future API-originated events (e.g. live
   * pose updates, rep counts, camera status). api.js is expected to
   * dispatch a CustomEvent named "poseai:apiEvent" with a `detail`
   * payload once real-time functionality is implemented.
   *
   * @param {CustomEvent} event
   */
  function handleFutureApiEvent(event) {
    try {
      const payload = event && event.detail ? event.detail : null;
      console.log("[app.js] Received future API event:", payload);

      safeModuleCall(window.DashboardUI, "handleApiEvent", payload);
    } catch (error) {
      console.error("[app.js] Error handling API event:", error);
    }
  }

  /**
   * Registers all application-level event listeners. Should be called
   * once during initialization.
   */
  function registerEventListeners() {
    try {
      window.addEventListener("resize", handleWindowResize);
      document.addEventListener("visibilitychange", handleVisibilityChange);
      document.addEventListener("poseai:apiEvent", handleFutureApiEvent);

      const startButton = document.querySelector("#start-workout");
      if (startButton) {
        startButton.addEventListener("click", () => {
          appState.activeExercise = document.querySelector("#selected-exercise")?.value || "1";
          startWorkoutFlow();
        });
      }

      const pauseButton = document.querySelector("#pause-workout");
      if (pauseButton) {
        pauseButton.addEventListener("click", async () => {
          if (window.DashboardAPI && typeof window.DashboardAPI.pauseWorkout === "function") {
            await window.DashboardAPI.pauseWorkout();
          }
        });
      }

      const resumeButton = document.querySelector("#resume-workout");
      if (resumeButton) {
        resumeButton.addEventListener("click", async () => {
          if (window.DashboardAPI && typeof window.DashboardAPI.resumeWorkout === "function") {
            await window.DashboardAPI.resumeWorkout();
          }
        });
      }

      const finishButton = document.querySelector("#finish-workout");
      if (finishButton) {
        finishButton.addEventListener("click", async () => {
          if (window.DashboardAPI && typeof window.DashboardAPI.finishWorkout === "function") {
            await window.DashboardAPI.finishWorkout();
          }
          stopFrameCapture();
          stopCameraStream();
        });
      }

      console.log("[app.js] Event listeners registered.");
    } catch (error) {
      console.error("[app.js] Failed to register event listeners:", error);
    }
  }

  /* ==========================================================================
     8. INITIALIZATION
     ========================================================================== */

  /**
   * Main initialization routine. Called once on DOMContentLoaded.
   * Loads default data, registers listeners, and prepares the
   * connection status. Does not automatically start the workout timer;
   * that begins explicitly via startDashboard().
   */
  function initializeDashboard() {
    try {
      if (appState.isInitialized) {
        console.warn("[app.js] Dashboard already initialized. Skipping.");
        return;
      }

      console.log("[app.js] Initializing PoseAI dashboard...");

      loadDefaultDashboard();
      registerEventListeners();
      updateConnectionStatus(CONNECTION_STATE.DISCONNECTED);

      if (window.DashboardAPI && typeof window.DashboardAPI.onDataUpdate === "function") {
        window.DashboardAPI.onDataUpdate((payload) => {
          safeModuleCall(window.DashboardUI, "updateWorkout", payload);
        });
      }

      if (window.DashboardAPI && typeof window.DashboardAPI.onConnectionChange === "function") {
        window.DashboardAPI.onConnectionChange((status) => {
          updateConnectionStatus(status);
        });
      }

      if (window.DashboardAPI && typeof window.DashboardAPI.onError === "function") {
        window.DashboardAPI.onError((error) => {
          console.error("[app.js] API error:", error);
        });
      }

      startDashboard();
      appState.isInitialized = true;
      console.log("[app.js] Dashboard initialization complete.");
    } catch (error) {
      console.error("[app.js] Dashboard initialization failed:", error);
    }
  }

  /* ==========================================================================
     9. BOOTSTRAP
     ========================================================================== */

  document.addEventListener("DOMContentLoaded", initializeDashboard);
})();
