/**
 * PoseAI - AI Fitness Trainer
 * dashboard/js/dashboard.js
 *
 * Dashboard UI Controller
 * -------------------------------------------------------------------------
 * Responsibilities:
 *   - Cache all relevant HTML elements once
 *   - Receive data objects and render them into the DOM
 *   - Manage visual state for progress bars, checklist, achievements,
 *     AI coach messages, session summary, and camera status
 *
 * This file NEVER:
 *   - Talks to Flask / any backend
 *   - Fetches data
 *   - Uses WebSockets
 *   - Creates timers
 *   - Generates fake/mock data
 *
 * It only receives data (from app.js, ultimately sourced via api.js) and
 * updates the interface. All DOM lookups are cached once during
 * construction to avoid repeated document.getElementById() calls.
 *
 * Architecture:
 *   app.js -> dashboard.js -> HTML Elements
 * -------------------------------------------------------------------------
 */

"use strict";

class DashboardUI {
  constructor() {
    /** @type {Object<string, Element|null>} */
    this.elements = {};

    /** @type {Map<string, HTMLElement>} Tracks dynamically rendered achievement badges */
    this._achievementBadges = new Map();

    /** @type {Map<string, HTMLElement>} Tracks dynamically rendered checklist items */
    this._checklistEntries = new Map();

    this.#cacheElements();
  }

  /* ==========================================================================
     ELEMENT CACHING
     ========================================================================== */

  /**
   * Caches every HTML element the dashboard needs to update.
   * Called once during construction. Missing elements are logged as
   * warnings but never cause a crash.
   * @private
   */
  #cacheElements() {
    this.elements = {
      // Live Workout Panel
      exerciseName: this.#query("#exercise-name .stat-value"),
      currentSet: this.#query("#current-set .stat-value"),
      goalRep: this.#query("#goal-rep .stat-value"),
      currentRep: this.#query("#current-rep .stat-value"),
      currentStage: this.#query("#current-stage .stat-value"),
      currentAngle: this.#query("#current-angle .stat-value"),
      workoutTimer: this.#query("#workout-timer .stat-value"),
      liveCalories: this.#query("#calories .stat-value"),
      feedback: this.#query("#feedback .stat-value"),

      // Camera
      cameraFeed: this.#query("#camera-feed"),

      // Connection Status (optional - degrades gracefully if absent)
      connectionIndicator: this.#query("#connection-status"),

      // Set / Overall Progress Bars
      set1Bar: this.#query("#set-1 .set-progress-bar"),
      set2Bar: this.#query("#set-2 .set-progress-bar"),
      set3Bar: this.#query("#set-3 .set-progress-bar"),
      overallBar: this.#query("#overall-progress .overall-progress-bar"),

      // Main Dashboard Cards
      welcomeCard: this.#query("#welcome-card .card-content"),
      currentStreak: this.#query("#current-streak .card-content"),
      todaysGoal: this.#query("#todays-goal .card-content"),

      // Today's Performance
      totalReps: this.#query("#total-reps .stat-value"),
      perfWorkoutTime: this.#query("#workout-time .stat-value"),
      perfCalories: this.#query("#performance-calories .stat-value"),
      xp: this.#query("#xp .stat-value"),
      exercisesCompleted: this.#query("#exercises-completed .stat-value"),

      // Weekly Progress
      weeklyProgressChart: this.#query("#weekly-progress-chart"),

      // Achievements
      achievementsSection: this.#query("#achievements"),
      achievementCard: this.#query("#achievement-card"),

      // AI Coach
      aiCoachCard: this.#query("#ai-coach-card"),
      aiCoachTitle: this.#query("#ai-coach-card .card-title"),
      aiCoachContent: this.#query("#ai-coach-card .card-content"),

      // Exercise Checklist
      checklistContainer: this.#query("#checklist-items"),

      // Daily Challenge / Personal Best
      dailyChallengeCard: this.#query("#daily-challenge-card .card-content"),
      personalBestCard: this.#query("#personal-best-card .card-content"),

      // Streak Calendar
      streakCalendarGrid: this.#query("#streak-calendar-grid"),

      // Session Summary
      sessionSummaryCard: this.#query("#session-summary-card .card-content"),

      // Root containers (used for global loading / error states)
      dashboardRoot: this.#query("#dashboard"),
    };
  }

  /**
   * Safe wrapper around document.querySelector. Logs a warning instead
   * of throwing if the element cannot be found.
   * @param {string} selector
   * @returns {Element|null}
   * @private
   */
  #query(selector) {
    const element = document.querySelector(selector);
    if (!element) {
      console.warn(
        `[dashboard.js] Element not found for selector: "${selector}"`,
      );
    }
    return element;
  }

  /* ==========================================================================
     GENERIC RENDER HELPERS
     ========================================================================== */

  /**
   * Safely sets the text content of an element.
   * @param {Element|null} element
   * @param {string|number} value
   * @private
   */
  #setText(element, value) {
    try {
      if (!element) {
        return;
      }
      element.textContent =
        value === undefined || value === null ? "--" : String(value);
    } catch (error) {
      console.error("[dashboard.js] Failed to set text content:", error);
    }
  }

  /**
   * Safely sets the numeric value of a <progress> element, clamped 0-100.
   * @param {HTMLProgressElement|null} progressElement
   * @param {number} value
   * @private
   */
  #setProgressValue(progressElement, value) {
    try {
      if (!progressElement) {
        return;
      }
      const numericValue = Number(value);
      const clamped = Number.isFinite(numericValue)
        ? Math.min(100, Math.max(0, numericValue))
        : 0;
      progressElement.value = clamped;
    } catch (error) {
      console.error("[dashboard.js] Failed to set progress value:", error);
    }
  }

  /* ==========================================================================
     INITIAL / FULL DASHBOARD RENDER (called by app.js on load + reset)
     ========================================================================== */

  /**
   * Renders the dashboard from the "default dashboard data" shape used by
   * app.js's loadDefaultDashboard()/resetDashboard() flow. NOTE: this shape
   * uses different field names than the live polling payload handled by
   * updateWorkout() (e.g. "exerciseName" instead of "exercise",
   * "currentStreak" instead of "streak").
   *
   * Expected shape:
   * {
   *   exerciseName, currentSet, goalSet, currentRep, goalRep, totalReps,
   *   workoutTime, calories, stage, feedback, currentStreak, xp,
   *   todaysGoalPercent, setProgress
   * }
   *
   * @param {object} data
   */
  renderDashboard(data = {}) {
    try {
      if (!data || typeof data !== "object") {
        console.warn("[dashboard.js] renderDashboard() received invalid data.");
        return;
      }

      this.updateExercise(data.exerciseName);
      this.updateSets(data.currentSet, data.goalSet);
      this.updateReps(data.currentRep, data.goalRep);
      this.updateWorkoutTimer(data.workoutTime);
      this.updateCalories(data.calories);
      this.updateStage(data.stage);
      this.updateFeedback(data.feedback);
      this.updateStreak(data.currentStreak);
      this.updateXP(data.xp);
      this.updateGoal(data.todaysGoalPercent);
      this.updateStatistics({
        totalReps: data.totalReps ?? 0,
        workoutTime: data.workoutTime ?? "00:00",
        calories: data.calories ?? "0.0 kcal",
        xp: data.xp ?? 0,
        exercisesCompleted: data.exercisesCompleted ?? 0,
      });
    } catch (error) {
      console.error("[dashboard.js] renderDashboard() failed:", error);
    }
  }

  /* ==========================================================================
     WORKOUT / EXERCISE UPDATES
     ========================================================================== */

  /**
   * Master update method. Accepts the full live workout data payload and
   * delegates to the appropriate specific update methods.
   *
   * Expected shape:
   * {
   *   exercise, currentRep, goalRep, currentSet, goalSet, stage, angle,
   *   calories, workoutTime, feedback, xp, streak, goal, cameraStatus,
   *   statistics, coach, summary
   * }
   *
   * @param {object} data
   */
  updateWorkout(data) {
    try {
      if (!data || typeof data !== "object") {
        console.warn("[dashboard.js] updateWorkout() received invalid data.");
        return;
      }

      if (data.exercise !== undefined) this.updateExercise(data.exercise);
      if (data.currentRep !== undefined || data.goalRep !== undefined) {
        this.updateReps(data.currentRep, data.goalRep);
      }
      if (data.currentSet !== undefined || data.goalSet !== undefined) {
        this.updateSets(data.currentSet, data.goalSet);
      }
      if (data.stage !== undefined) this.updateStage(data.stage);
      if (data.angle !== undefined) this.updateAngle(data.angle);
      if (data.calories !== undefined) this.updateCalories(data.calories);
      if (data.workoutTime !== undefined)
        this.updateWorkoutTimer(data.workoutTime);
      if (data.feedback !== undefined) this.updateFeedback(data.feedback);
      if (data.xp !== undefined) this.updateXP(data.xp);
      if (data.streak !== undefined) this.updateStreak(data.streak);
      if (data.goal !== undefined) this.updateGoal(data.goal);
      if (data.cameraStatus !== undefined)
        this.updateCameraStatus(data.cameraStatus);
      if (data.statistics !== undefined) this.updateStatistics(data.statistics);
      if (data.coach !== undefined)
        this.updateCoach(data.coach.message, data.coach.type);
      if (data.summary !== undefined) this.updateSessionSummary(data.summary);
    } catch (error) {
      console.error("[dashboard.js] updateWorkout() failed:", error);
    }
  }

  /**
   * Updates the displayed exercise name.
   * @param {string} exerciseName
   */
  updateExercise(exerciseName) {
    this.#setText(
      this.elements.exerciseName,
      exerciseName || "No Exercise Selected",
    );
  }

  /**
   * Updates current/goal rep display.
   * @param {number} currentRep
   * @param {number} goalRep
   */
  updateReps(currentRep, goalRep) {
    this.#setText(this.elements.currentRep, currentRep ?? 0);
    this.#setText(this.elements.goalRep, goalRep ?? 0);
  }

  /**
   * Updates current/goal set display.
   * @param {number} currentSet
   * @param {number} goalSet
   */
  updateSets(currentSet, goalSet) {
    const goal = goalSet ?? 3;
    this.#setText(this.elements.currentSet, `${currentSet ?? 0} / ${goal}`);
  }

  /**
   * Updates the current exercise stage (e.g. "Up", "Down", "Waiting...").
   * @param {string} stage
   */
  updateStage(stage) {
    this.#setText(this.elements.currentStage, stage || "Waiting...");
  }

  /**
   * Updates the current joint/body angle reading.
   * @param {number|string} angle
   */
  updateAngle(angle) {
    const displayValue =
      angle === undefined || angle === null ? "--" : `${angle}°`;
    this.#setText(this.elements.currentAngle, displayValue);
  }

  /**
   * Updates the live calorie counter within the Live Workout panel.
   * Accepts either a raw numeric value (e.g. 18.6) or an already
   * formatted string (e.g. "0.0 kcal") without duplicating the suffix.
   * @param {number|string} calories
   */
  updateCalories(calories) {
    let displayValue;

    if (calories === undefined || calories === null || calories === "") {
      displayValue = "0.0 kcal";
    } else if (
      typeof calories === "string" &&
      calories.toLowerCase().includes("kcal")
    ) {
      displayValue = calories;
    } else {
      displayValue = `${calories} kcal`;
    }

    this.#setText(this.elements.liveCalories, displayValue);
  }

  /**
   * Updates the live workout timer display only. This reflects the
   * current active session's elapsed time, distinct from the
   * cumulative "Today's Performance" workout time (which is driven
   * exclusively by updateStatistics()).
   * @param {string} timeString - Pre-formatted time, e.g. "05:32".
   */
  updateWorkoutTimer(timeString) {
    this.#setText(this.elements.workoutTimer, timeString || "00:00");
  }

  /**
   * @deprecated Kept for backward compatibility. Delegates to
   * updateWorkoutTimer(). No longer touches the "Today's Performance"
   * total, which is owned by updateStatistics().
   * @param {string} timeString
   */
  updateWorkoutTime(timeString) {
    this.updateWorkoutTimer(timeString);
  }

  /**
   * Updates the live coaching feedback line.
   * @param {string} feedback
   */
  updateFeedback(feedback) {
    this.#setText(this.elements.feedback, feedback || "Waiting for Camera...");
  }

  /* ==========================================================================
     PROGRESS BARS
     ========================================================================== */

  /**
   * Updates Set 1, Set 2, Set 3, and Overall progress bars.
   * @param {object} progress
   * @param {number} [progress.set1] - 0-100
   * @param {number} [progress.set2] - 0-100
   * @param {number} [progress.set3] - 0-100
   * @param {number} [progress.overall] - 0-100
   */
  updateProgress(progress = {}) {
    try {
      this.#setProgressValue(this.elements.set1Bar, progress.set1 ?? 0);
      this.#setProgressValue(this.elements.set2Bar, progress.set2 ?? 0);
      this.#setProgressValue(this.elements.set3Bar, progress.set3 ?? 0);
      this.#setProgressValue(this.elements.overallBar, progress.overall ?? 0);
    } catch (error) {
      console.error("[dashboard.js] updateProgress() failed:", error);
    }
  }

  /* ==========================================================================
     XP / STREAK / GOAL
     ========================================================================== */

  /**
   * Updates the XP statistic.
   * @param {number} xp
   */
  updateXP(xp) {
    this.#setText(this.elements.xp, xp ?? 0);
  }

  /**
   * Updates the current streak display.
   * @param {number|string} streak
   */
  updateStreak(streak) {
    const displayValue =
      typeof streak === "number" ? `${streak} Days` : streak || "0 Days";
    this.#setText(this.elements.currentStreak, displayValue);
  }

  /**
   * Updates today's goal completion percentage.
   * @param {number|string} goalPercent
   */
  updateGoal(goalPercent) {
    const displayValue =
      typeof goalPercent === "number" ? `${goalPercent}%` : goalPercent || "0%";
    this.#setText(this.elements.todaysGoal, displayValue);
  }

  /* ==========================================================================
     TODAY'S PERFORMANCE STATISTICS
     ========================================================================== */

  /**
   * Updates the Today's Performance statistic cards. This is the sole
   * source of truth for the cumulative "Today's Performance" workout
   * time and calorie totals.
   * @param {object} statistics
   * @param {number} [statistics.totalReps]
   * @param {string} [statistics.workoutTime]
   * @param {number|string} [statistics.calories]
   * @param {number} [statistics.xp]
   * @param {number} [statistics.exercisesCompleted]
   */
  updateStatistics(statistics = {}) {
    try {
      this.#setText(this.elements.totalReps, statistics.totalReps ?? 0);
      this.#setText(
        this.elements.perfWorkoutTime,
        statistics.workoutTime ?? "00:00",
      );

      let caloriesDisplay;
      if (statistics.calories === undefined || statistics.calories === null) {
        caloriesDisplay = "0.0 kcal";
      } else if (
        typeof statistics.calories === "string" &&
        statistics.calories.toLowerCase().includes("kcal")
      ) {
        caloriesDisplay = statistics.calories;
      } else {
        caloriesDisplay = `${statistics.calories} kcal`;
      }
      this.#setText(this.elements.perfCalories, caloriesDisplay);

      this.#setText(this.elements.xp, statistics.xp ?? 0);
      this.#setText(
        this.elements.exercisesCompleted,
        statistics.exercisesCompleted ?? 0,
      );
    } catch (error) {
      console.error("[dashboard.js] updateStatistics() failed:", error);
    }
  }

  /* ==========================================================================
     WEEKLY PROGRESS
     ========================================================================== */

  /**
   * Renders weekly progress data as simple proportional bars inside the
   * chart container. Expects an array of { label, value } where value
   * is 0-100.
   * @param {Array<{label: string, value: number}>} weeklyData
   */
  updateWeeklyProgress(weeklyData) {
    try {
      const container = this.elements.weeklyProgressChart;
      if (!container) {
        return;
      }

      if (!Array.isArray(weeklyData) || weeklyData.length === 0) {
        container.replaceChildren();
        return;
      }

      const fragment = document.createDocumentFragment();

      weeklyData.forEach((entry) => {
        const barWrapper = document.createElement("div");
        barWrapper.className = "weekly-progress-bar";
        barWrapper.dataset.label = entry.label ?? "";

        const barFill = document.createElement("div");
        barFill.className = "weekly-progress-bar-fill";
        const clampedValue = Math.min(
          100,
          Math.max(0, Number(entry.value) || 0),
        );
        barFill.style.height = `${clampedValue}%`;
        barFill.setAttribute(
          "aria-label",
          `${entry.label ?? "Day"}: ${clampedValue}%`,
        );

        barWrapper.appendChild(barFill);
        fragment.appendChild(barWrapper);
      });

      container.replaceChildren(fragment);
    } catch (error) {
      console.error("[dashboard.js] updateWeeklyProgress() failed:", error);
    }
  }

  /* ==========================================================================
     ACHIEVEMENTS
     ========================================================================== */

  /**
   * Adds a new achievement badge to the achievements section.
   * @param {string} id - Unique achievement identifier.
   * @param {object} data
   * @param {string} data.title
   * @param {string} [data.description]
   * @param {number} [data.progress] - 0-100
   */
  addAchievementBadge(id, data = {}) {
    try {
      const container = this.elements.achievementsSection;
      if (!container || !id) {
        console.warn(
          "[dashboard.js] Cannot add achievement badge: missing container or id.",
        );
        return;
      }

      if (this._achievementBadges.has(id)) {
        this.updateAchievementProgress(id, data.progress);
        return;
      }

      const badge = document.createElement("article");
      badge.className = "card achievement-badge";
      badge.dataset.achievementId = id;

      const title = document.createElement("h3");
      title.className = "card-title";
      title.textContent = data.title || "Achievement";

      const description = document.createElement("p");
      description.className = "card-content";
      description.textContent = data.description || "";

      badge.appendChild(title);
      badge.appendChild(description);

      container.appendChild(badge);
      this._achievementBadges.set(id, badge);
    } catch (error) {
      console.error("[dashboard.js] addAchievementBadge() failed:", error);
    }
  }

  /**
   * Removes an achievement badge by id.
   * @param {string} id
   */
  removeAchievementBadge(id) {
    try {
      const badge = this._achievementBadges.get(id);
      if (badge && badge.parentElement) {
        badge.parentElement.removeChild(badge);
      }
      this._achievementBadges.delete(id);
    } catch (error) {
      console.error("[dashboard.js] removeAchievementBadge() failed:", error);
    }
  }

  /**
   * Updates the progress description text of an existing achievement badge.
   * @param {string} id
   * @param {number} progress - 0-100
   */
  updateAchievementProgress(id, progress) {
    try {
      const badge = this._achievementBadges.get(id);
      if (!badge) {
        console.warn(
          `[dashboard.js] No achievement badge found for id "${id}".`,
        );
        return;
      }
      const description = badge.querySelector(".card-content");
      if (description) {
        const clamped = Math.min(100, Math.max(0, Number(progress) || 0));
        description.textContent = `Progress: ${clamped}%`;
      }
    } catch (error) {
      console.error(
        "[dashboard.js] updateAchievementProgress() failed:",
        error,
      );
    }
  }

  /**
   * Convenience method to fully re-render the achievements list from an array.
   * @param {Array<{id: string, title: string, description: string, progress: number}>} achievements
   */
  updateAchievements(achievements) {
    try {
      if (!Array.isArray(achievements)) {
        console.warn("[dashboard.js] updateAchievements() expects an array.");
        return;
      }

      achievements.forEach((achievement) => {
        if (!achievement || !achievement.id) {
          return;
        }
        this.addAchievementBadge(achievement.id, achievement);
      });
    } catch (error) {
      console.error("[dashboard.js] updateAchievements() failed:", error);
    }
  }

  /* ==========================================================================
     AI COACH
     ========================================================================== */

  /**
   * Displays an AI Coach message with a semantic type.
   * @param {string} message
   * @param {'success'|'warning'|'error'|'info'} [type='info']
   */
  updateCoach(message, type = "info") {
    try {
      const validTypes = ["success", "warning", "error", "info"];
      const messageType = validTypes.includes(type) ? type : "info";

      this.#setText(this.elements.aiCoachContent, message || "");

      const coachCard = this.elements.aiCoachCard;
      if (coachCard) {
        validTypes.forEach((validType) =>
          coachCard.classList.remove(`coach-${validType}`),
        );
        coachCard.classList.add(`coach-${messageType}`);
        coachCard.dataset.coachType = messageType;
      }
    } catch (error) {
      console.error("[dashboard.js] updateCoach() failed:", error);
    }
  }

  /* ==========================================================================
     EXERCISE CHECKLIST
     ========================================================================== */

  /**
   * Fully renders the exercise checklist from an array of items.
   * @param {Array<{id: string, name: string, completed: boolean}>} items
   */
  updateChecklist(items) {
    try {
      const container = this.elements.checklistContainer;
      if (!container || !Array.isArray(items)) {
        return;
      }

      const fragment = document.createDocumentFragment();
      this._checklistEntries.clear();

      items.forEach((item) => {
        if (!item || !item.id) {
          return;
        }

        const listItem = document.createElement("li");
        listItem.className = "checklist-item";
        listItem.dataset.exerciseId = item.id;

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "checklist-checkbox";
        checkbox.id = `checklist-${item.id}`;
        checkbox.checked = Boolean(item.completed);
        checkbox.disabled = true;

        const label = document.createElement("label");
        label.setAttribute("for", checkbox.id);
        label.textContent = item.name || "Exercise";

        listItem.appendChild(checkbox);
        listItem.appendChild(label);

        fragment.appendChild(listItem);
        this._checklistEntries.set(item.id, listItem);
      });

      container.replaceChildren(fragment);
    } catch (error) {
      console.error("[dashboard.js] updateChecklist() failed:", error);
    }
  }

  /**
   * Marks a checklist item as complete.
   * @param {string} id
   */
  markExerciseComplete(id) {
    this.#setChecklistState(id, true);
  }

  /**
   * Marks a checklist item as pending (incomplete).
   * @param {string} id
   */
  markExercisePending(id) {
    this.#setChecklistState(id, false);
  }

  /**
   * Internal helper to toggle a checklist item's completed state.
   * @param {string} id
   * @param {boolean} isComplete
   * @private
   */
  #setChecklistState(id, isComplete) {
    try {
      const listItem = this._checklistEntries.get(id);
      if (!listItem) {
        console.warn(`[dashboard.js] No checklist entry found for id "${id}".`);
        return;
      }
      const checkbox = listItem.querySelector(".checklist-checkbox");
      if (checkbox) {
        checkbox.checked = isComplete;
      }
      listItem.classList.toggle("is-complete", isComplete);
      listItem.classList.toggle("is-pending", !isComplete);
    } catch (error) {
      console.error("[dashboard.js] Failed to set checklist state:", error);
    }
  }

  /* ==========================================================================
     SESSION SUMMARY
     ========================================================================== */

  /**
   * Renders the session summary card with final workout results.
   * @param {object} summary
   * @param {string} [summary.exercise]
   * @param {number} [summary.sets]
   * @param {number} [summary.reps]
   * @param {string} [summary.workoutTime]
   * @param {number|string} [summary.calories]
   * @param {number} [summary.xp]
   * @param {number|string} [summary.streak]
   */
  updateSessionSummary(summary = {}) {
    try {
      const container = this.elements.sessionSummaryCard;
      if (!container) {
        return;
      }

      const summaryFields = [
        { label: "Exercise", value: summary.exercise ?? "--" },
        { label: "Sets", value: summary.sets ?? 0 },
        { label: "Reps", value: summary.reps ?? 0 },
        { label: "Workout Time", value: summary.workoutTime ?? "00:00" },
        {
          label: "Calories",
          value:
            summary.calories !== undefined
              ? `${summary.calories} kcal`
              : "0.0 kcal",
        },
        { label: "XP", value: summary.xp ?? 0 },
        {
          label: "Streak",
          value:
            typeof summary.streak === "number"
              ? `${summary.streak} Days`
              : (summary.streak ?? "0 Days"),
        },
      ];

      const list = document.createElement("dl");
      list.className = "session-summary-list";

      summaryFields.forEach((field) => {
        const term = document.createElement("dt");
        term.textContent = field.label;

        const description = document.createElement("dd");
        description.textContent = field.value;

        list.appendChild(term);
        list.appendChild(description);
      });

      container.replaceChildren(list);
    } catch (error) {
      console.error("[dashboard.js] updateSessionSummary() failed:", error);
    }
  }

  /* ==========================================================================
     CAMERA STATUS
     ========================================================================== */

  /**
   * Updates the visual state of the camera feed container. Accepts the
   * backend's status vocabulary ("online"/"offline") as well as the
   * internal CSS state vocabulary ("connected"/"disconnected"/"loading"),
   * normalizing either into a valid internal state.
   * @param {'online'|'connected'|'disconnected'|'loading'|'connecting'|'offline'} status
   */
  updateCameraStatus(status) {
    try {
      const camera = this.elements.cameraFeed;
      if (!camera) {
        return;
      }

      const statusAliasMap = {
        online: "connected",
        connected: "connected",
        disconnected: "disconnected",
        connecting: "loading",
        loading: "loading",
        offline: "offline",
      };

      const normalizedInput =
        typeof status === "string" ? status.toLowerCase() : "";
      const normalizedStatus = statusAliasMap[normalizedInput] || "offline";

      const validStatuses = ["connected", "disconnected", "loading", "offline"];
      validStatuses.forEach((validStatus) =>
        camera.classList.remove(`camera-${validStatus}`),
      );
      camera.classList.add(`camera-${normalizedStatus}`);
      camera.dataset.cameraStatus = normalizedStatus;

      const statusLabels = {
        connected: "",
        disconnected: "Camera Disconnected",
        loading: "Connecting to Camera...",
        offline: "Camera Offline",
      };

      camera.textContent = statusLabels[normalizedStatus] || "";
    } catch (error) {
      console.error("[dashboard.js] updateCameraStatus() failed:", error);
    }
  }

  /* ==========================================================================
     CONNECTION STATUS (backend/session connection, distinct from camera)
     ========================================================================== */

  /**
   * Reflects the backend connection status (Connected/Disconnected/
   * Connecting) reported by app.js. Updates an optional dedicated
   * indicator element if present, and always flags the state on the
   * dashboard root via a data attribute/class for CSS hooks.
   * @param {'Connected'|'Disconnected'|'Connecting'} status
   */
  setConnectionStatus(status) {
    try {
      const normalizedStatus =
        typeof status === "string" ? status.toLowerCase() : "disconnected";
      const validStatuses = ["connected", "disconnected", "connecting"];
      const safeStatus = validStatuses.includes(normalizedStatus)
        ? normalizedStatus
        : "disconnected";

      const root = this.elements.dashboardRoot;
      if (root) {
        validStatuses.forEach((validStatus) =>
          root.classList.remove(`connection-${validStatus}`),
        );
        root.classList.add(`connection-${safeStatus}`);
        root.dataset.connectionStatus = safeStatus;
      }

      if (this.elements.connectionIndicator) {
        this.#setText(this.elements.connectionIndicator, status);
      }

      console.log(`[dashboard.js] Connection status set to: ${status}`);
    } catch (error) {
      console.error("[dashboard.js] setConnectionStatus() failed:", error);
    }
  }

  /* ==========================================================================
     WINDOW / RESPONSIVE EVENTS
     ========================================================================== */

  /**
   * Handles viewport resize notifications forwarded by app.js. Currently
   * a defensive no-op placeholder; reserved for future responsive
   * recalculation of charts or layout-sensitive elements.
   * @param {{width: number, height: number}} dimensions
   */
  handleResize(dimensions = {}) {
    try {
      console.log(
        `[dashboard.js] Handling resize: ${dimensions.width ?? "?"}x${
          dimensions.height ?? "?"
        }`,
      );
    } catch (error) {
      console.error("[dashboard.js] handleResize() failed:", error);
    }
  }

  /**
   * Handles future API-originated events forwarded by app.js via the
   * "poseai:apiEvent" custom event. Delegates to updateWorkout() since
   * such events are expected to carry the same live data shape.
   * @param {object} payload
   */
  handleApiEvent(payload) {
    try {
      if (!payload || typeof payload !== "object") {
        console.warn("[dashboard.js] handleApiEvent() received invalid payload.");
        return;
      }
      this.updateWorkout(payload);
    } catch (error) {
      console.error("[dashboard.js] handleApiEvent() failed:", error);
    }
  }

  /* ==========================================================================
     LOADING / ERROR / CLEAR STATES
     ========================================================================== */

  /**
   * Applies a loading state to a target element (or the dashboard root
   * by default).
   * @param {Element} [target=this.elements.dashboardRoot]
   */
  showLoading(target = this.elements.dashboardRoot) {
    try {
      if (!target) {
        return;
      }
      target.classList.add("is-loading");
      target.setAttribute("aria-busy", "true");
    } catch (error) {
      console.error("[dashboard.js] showLoading() failed:", error);
    }
  }

  /**
   * Removes a loading state from a target element (or the dashboard root
   * by default).
   * @param {Element} [target=this.elements.dashboardRoot]
   */
  hideLoading(target = this.elements.dashboardRoot) {
    try {
      if (!target) {
        return;
      }
      target.classList.remove("is-loading");
      target.removeAttribute("aria-busy");
    } catch (error) {
      console.error("[dashboard.js] hideLoading() failed:", error);
    }
  }

  /**
   * Displays an error message on a target element (or the dashboard root
   * by default). Does not remove existing content permanently; only
   * flags the error state and logs the message.
   * @param {string} message
   * @param {Element} [target=this.elements.dashboardRoot]
   */
  showError(message, target = this.elements.dashboardRoot) {
    try {
      console.error(`[dashboard.js] UI Error: ${message}`);
      if (!target) {
        return;
      }
      target.classList.add("has-error");
      target.dataset.errorMessage = message || "An unknown error occurred.";
    } catch (error) {
      console.error("[dashboard.js] showError() failed:", error);
    }
  }

  /**
   * Resets all dashboard UI elements back to their default placeholder
   * state. Does not touch application/session state; that is handled
   * by app.js.
   */
  clearDashboard() {
    try {
      this.updateExercise("No Exercise Selected");
      this.updateSets(0, 3);
      this.updateReps(0, 15);
      this.updateStage("Waiting...");
      this.updateAngle(null);
      this.updateCalories("0.0 kcal");
      this.updateWorkoutTimer("00:00");
      this.updateFeedback("Waiting for Camera...");
      this.updateXP(0);
      this.updateStreak(0);
      this.updateGoal(0);
      this.updateProgress({ set1: 0, set2: 0, set3: 0, overall: 0 });
      this.updateStatistics({
        totalReps: 0,
        workoutTime: "00:00",
        calories: "0.0 kcal",
        xp: 0,
        exercisesCompleted: 0,
      });
      this.updateCameraStatus("offline");

      if (this.elements.dashboardRoot) {
        this.elements.dashboardRoot.classList.remove("is-loading", "has-error");
        this.elements.dashboardRoot.removeAttribute("aria-busy");
        delete this.elements.dashboardRoot.dataset.errorMessage;
      }

      console.log("[dashboard.js] Dashboard cleared to default state.");
    } catch (error) {
      console.error("[dashboard.js] clearDashboard() failed:", error);
    }
  }
}

/* ==========================================================================
   GLOBAL EXPOSURE
   ========================================================================== */

window.DashboardUI = new DashboardUI();