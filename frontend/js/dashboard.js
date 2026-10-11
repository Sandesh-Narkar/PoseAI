/**
 * PoseAI Dashboard UI Controller
 * Manages all DOM rendering and real-time UI updates
 * NO XP functionality
 */

"use strict";

class DashboardUI {
  constructor() {
    this.elements = this._cacheElements();
    this._achievementBadges = new Map();
    this._checklistEntries = new Map();
  }

  /* ==========================================================================
     ELEMENT CACHING
     ========================================================================== */

  _cacheElements() {
    return {
      dashboardRoot: document.getElementById("dashboard"),
      exerciseName: document.getElementById("exercise-name"),
      repsValue: document.querySelector("#current-rep .stat-value"),
      setsValue: document.querySelector("#current-set .stat-value"),
      stageValue: document.querySelector("#current-stage .stat-value"),
      angleValue: document.querySelector("#current-angle .stat-value"),
      caloriesValue: document.getElementById("calories")
        ? document.querySelector("#calories .stat-value")
        : null,
      workoutTimerValue: document.getElementById("workout-timer")
        ? document.querySelector("#workout-timer .stat-value")
        : null,
      feedbackValue: document.getElementById("feedback"),
      streakValue: document.querySelector("#current-streak .card-content"),
      streakStatus: document.getElementById("streak-status"),
      streakLongestValue: document.querySelector(
        '[data-stat="longest-streak"] .stat-value',
      ),
      goalValue: document.querySelector("#todays-goal .card-content"),
      totalRepsValue: document.getElementById("total-reps")
        ? document.querySelector("#total-reps .stat-value")
        : null,
      statisticsCard: document.querySelector(".todays-performance"),
      cameraFeed: document.getElementById("camera-feed"),
      aiCoachCard: document.querySelector(".ai-coach-card"),
      aiCoachContent: document.querySelector(".ai-coach-card .card-content"),
      checklistContainer: document.querySelector(".checklist-items"),
      sessionSummaryCard: document.querySelector(".session-summary-card"),
      connectionIndicator: document.getElementById("connection-status"),
    };
  }

  /* ==========================================================================
     HELPER: SET TEXT SAFELY
     ========================================================================== */

  #setText(element, text) {
    try {
      if (element && typeof text !== "undefined") {
        element.textContent = String(text);
      }
    } catch (error) {
      console.error("[dashboard.js] Failed to set text:", error);
    }
  }

  /* ==========================================================================
     EXERCISE & LIVE METRICS
     ========================================================================== */

  updateExercise(name) {
    try {
      this.#setText(this.elements.exerciseName, name ?? "No Exercise Selected");
      this.#setText(
        this.elements.exerciseName?.querySelector(".stat-value"),
        name ?? "No Exercise Selected",
      );
    } catch (error) {
      console.error("[dashboard.js] updateExercise() failed:", error);
    }
  }

  updateReps(current, goal) {
    try {
      const repsElement = this.elements.repsValue;
      if (repsElement) {
        this.#setText(repsElement, `${current ?? 0} / ${goal ?? 15}`);
      }
    } catch (error) {
      console.error("[dashboard.js] updateReps() failed:", error);
    }
  }

  updateSets(current, goal) {
    try {
      const setsElement = this.elements.setsValue;
      if (setsElement) {
        this.#setText(setsElement, `${current ?? 0} / ${goal ?? 3}`);
      }
    } catch (error) {
      console.error("[dashboard.js] updateSets() failed:", error);
    }
  }

  updateStage(stage) {
    try {
      this.#setText(this.elements.stageValue, stage ?? "Waiting...");
    } catch (error) {
      console.error("[dashboard.js] updateStage() failed:", error);
    }
  }

  updateAngle(angle) {
    try {
      if (angle !== null && angle !== undefined) {
        this.#setText(this.elements.angleValue, `${Math.round(angle)}°`);
      } else {
        this.#setText(this.elements.angleValue, "--");
      }
    } catch (error) {
      console.error("[dashboard.js] updateAngle() failed:", error);
    }
  }

  updateCalories(calories) {
    try {
      const value =
        typeof calories === "number"
          ? `${calories.toFixed(1)} kcal`
          : (calories ?? "0.0 kcal");
      if (this.elements.caloriesValue) {
        this.#setText(this.elements.caloriesValue, value);
      }
    } catch (error) {
      console.error("[dashboard.js] updateCalories() failed:", error);
    }
  }

  updateWorkoutTimer(time) {
    try {
      if (this.elements.workoutTimerValue) {
        this.#setText(this.elements.workoutTimerValue, time ?? "00:00");
      }
    } catch (error) {
      console.error("[dashboard.js] updateWorkoutTimer() failed:", error);
    }
  }

  updateFeedback(message) {
    try {
      const element = this.elements.feedbackValue;
      if (element) {
        const valueSpan = element.querySelector(".stat-value");
        if (valueSpan) {
          this.#setText(valueSpan, message ?? "");
        }
      }
    } catch (error) {
      console.error("[dashboard.js] updateFeedback() failed:", error);
    }
  }

  /* ==========================================================================
     STREAK (NO XP)
     ========================================================================== */

  updateStreak(streak, todayCompleted) {
    try {
      const value =
        typeof streak === "number" ? `${streak} Days` : (streak ?? "0 Days");
      this.#setText(this.elements.streakValue, value);
      this.#updateStreakStatus(streak, todayCompleted);
    } catch (error) {
      console.error("[dashboard.js] updateStreak() failed:", error);
    }
  }

  #updateStreakStatus(streak, todayCompleted) {
    const el = this.elements.streakStatus;
    if (!el) {
      return;
    }
    const numericStreak =
      typeof streak === "number" ? streak : parseInt(String(streak), 10) || 0;
    if (todayCompleted) {
      el.textContent = "Today completed. Streak secured.";
      el.className = "streak-status streak-status--complete";
    } else if (numericStreak > 0) {
      el.textContent = "Complete a workout today to keep your streak alive.";
      el.className = "streak-status";
    } else {
      el.textContent = "Complete a workout today to start your streak.";
      el.className = "streak-status";
    }
  }

  updateLongestStreak(longest) {
    try {
      const value = typeof longest === "number" ? longest : (longest ?? 0);
      if (this.elements.streakLongestValue) {
        this.#setText(this.elements.streakLongestValue, value);
      }
    } catch (error) {
      console.error("[dashboard.js] updateLongestStreak() failed:", error);
    }
  }

  updateGoal(goal) {
    try {
      const value = typeof goal === "number" ? `${goal}%` : (goal ?? "0%");
      this.#setText(this.elements.goalValue, value);
    } catch (error) {
      console.error("[dashboard.js] updateGoal() failed:", error);
    }
  }

  /* ==========================================================================
     PROGRESS TRACKING
     ========================================================================== */

  updateProgress(progress) {
    try {
      if (!progress || typeof progress !== "object") {
        return;
      }

      const container = document.querySelector(".active-set-progress");
      if (!container) {
        return;
      }

      const sets = ["set1", "set2", "set3"];
      sets.forEach((setKey, index) => {
        const value = Math.min(100, Math.max(0, Number(progress[setKey]) || 0));
        const bar = container.querySelector(`[data-set="${index + 1}"]`);
        if (bar) {
          bar.value = value;
        }
      });

      const overallBar = container.querySelector('[data-stat="overall"]');
      if (overallBar) {
        const overall = Math.min(
          100,
          Math.max(0, Number(progress.overall) || 0),
        );
        overallBar.value = overall;
      }
    } catch (error) {
      console.error("[dashboard.js] updateProgress() failed:", error);
    }
  }

  /* ==========================================================================
     WEEKLY PROGRESS CHART
     ========================================================================== */

  updateWeeklyProgress(weekData) {
    try {
      const container = document.querySelector(".chart-container");
      if (!container || !Array.isArray(weekData)) {
        return;
      }

      const fragment = document.createDocumentFragment();
      const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const maxValue = Math.max(1, ...weekData.map((d) => Number(d) || 0));

      weekData.slice(0, 7).forEach((value, index) => {
        const bar = document.createElement("div");
        bar.className = "weekly-progress-bar";
        bar.dataset.label = days[index] || "Day";

        const fill = document.createElement("div");
        fill.className = "weekly-progress-bar-fill";
        const height = maxValue > 0 ? (Number(value) / maxValue) * 100 : 0;
        fill.style.height = `${height}%`;

        bar.appendChild(fill);
        fragment.appendChild(bar);
      });

      container.replaceChildren(fragment);
    } catch (error) {
      console.error("[dashboard.js] updateWeeklyProgress() failed:", error);
    }
  }

  /* ==========================================================================
     STATISTICS (NO XP)
     ========================================================================== */

  updateStatistics(stats) {
    try {
      if (!stats || typeof stats !== "object") {
        return;
      }

      if (this.elements.totalRepsValue) {
        this.#setText(this.elements.totalRepsValue, stats.totalReps ?? 0);
      }

      const workoutTimeElement = document.getElementById("workout-time");
      if (workoutTimeElement) {
        const workoutTimeValue = workoutTimeElement.querySelector(".stat-value");
        this.#setText(workoutTimeValue, stats.workoutTime ?? "00:00");
      }

      const caloriesElement = document.getElementById("performance-calories");
      if (caloriesElement) {
        const caloriesValue = caloriesElement.querySelector(".stat-value");
        const calories =
          typeof stats.calories === "number"
            ? `${stats.calories.toFixed(1)}`
            : (stats.calories ?? "0.0");
        this.#setText(caloriesValue, calories);
      }

      const exercisesElement = document.getElementById("exercises-completed");
      if (exercisesElement) {
        const exercisesValue = exercisesElement.querySelector(".stat-value");
        this.#setText(exercisesValue, stats.exercisesCompleted ?? 0);
      }
    } catch (error) {
      console.error("[dashboard.js] updateStatistics() failed:", error);
    }
  }

  /* ==========================================================================
     RENDER FULL DASHBOARD
     ========================================================================== */

  renderDashboard(data) {
    try {
      if (!data || typeof data !== "object") {
        return;
      }

      this.updateExercise(data.exerciseName);
      this.updateReps(data.currentRep, data.goalRep);
      this.updateSets(data.currentSet, data.goalSet);
      this.updateStage(data.stage);
      this.updateAngle(data.angle);
      this.updateCalories(data.calories);
      this.updateWorkoutTimer(data.workoutTime);
      this.updateFeedback(data.feedback);
      this.updateStreak(data.currentStreak, data.todayCompleted);
      this.updateGoal(data.todaysGoalPercent ?? data.goal ?? 0);
      this.updateStatistics(data.statistics);
      this.updateWeeklyProgress(data.weeklyProgress);
      this.updateSessionSummary(data.summary);

      console.log("[dashboard.js] Dashboard rendered successfully.");
    } catch (error) {
      console.error("[dashboard.js] renderDashboard() failed:", error);
    }
  }

  /* ==========================================================================
     LIVE WORKOUT UPDATE
     ========================================================================== */

  updateWorkout(payload) {
    try {
      if (!payload || typeof payload !== "object") {
        return;
      }

      this.updateExercise(payload.exercise || payload.exerciseName);
      this.updateReps(payload.currentRep, payload.goalRep);
      this.updateSets(payload.currentSet, payload.goalSet);
      this.updateStage(payload.stage);
      this.updateAngle(payload.angle);
      this.updateCalories(payload.calories);
      this.updateWorkoutTimer(payload.workoutTime);
      this.updateFeedback(payload.feedback);
      this.updateStreak(payload.streak ?? payload.currentStreak, payload.todayCompleted);
      this.updateGoal(payload.todaysGoalPercent ?? payload.goal ?? 0);
      this.updateStatistics(payload.statistics);
      this.updateWeeklyProgress(payload.weeklyProgress);
      this.updateSessionSummary(payload.summary);
    } catch (error) {
      console.error("[dashboard.js] updateWorkout() failed:", error);
    }
  }

  /* ==========================================================================
     ACHIEVEMENTS
     ========================================================================== */

  addAchievementBadge(id, achievement) {
    try {
      if (!id || !achievement) {
        return;
      }

      let badge = this._achievementBadges.get(id);
      if (!badge) {
        const container = document.querySelector("#achievements");
        if (!container) {
          return;
        }

        badge = document.createElement("div");
        badge.className = "achievement-badge card";
        badge.dataset.achievementId = id;
        container.appendChild(badge);
        this._achievementBadges.set(id, badge);
      }

      const title =
        badge.querySelector(".card-title") || document.createElement("div");
      if (!badge.querySelector(".card-title")) {
        title.className = "card-title";
        badge.appendChild(title);
      }
      this.#setText(title, achievement.title ?? "Achievement");

      const description =
        badge.querySelector(".card-content") || document.createElement("div");
      if (!badge.querySelector(".card-content")) {
        description.className = "card-content";
        badge.appendChild(description);
      }
      this.#setText(description, achievement.description ?? "");
    } catch (error) {
      console.error("[dashboard.js] addAchievementBadge() failed:", error);
    }
  }

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

  markExerciseComplete(id) {
    this.#setChecklistState(id, true);
  }

  markExercisePending(id) {
    this.#setChecklistState(id, false);
  }

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
     SESSION SUMMARY (NO XP)
     ========================================================================== */

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
     CONNECTION STATUS
     ========================================================================== */

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
     EVENTS & RESIZE
     ========================================================================== */

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

  handleApiEvent(payload) {
    try {
      if (!payload || typeof payload !== "object") {
        console.warn(
          "[dashboard.js] handleApiEvent() received invalid payload.",
        );
        return;
      }
      this.updateWorkout(payload);
    } catch (error) {
      console.error("[dashboard.js] handleApiEvent() failed:", error);
    }
  }

  /* ==========================================================================
     LOADING / ERROR / CLEAR
     ========================================================================== */

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
      this.updateStreak(0);
      this.updateGoal(0);
      this.updateProgress({ set1: 0, set2: 0, set3: 0, overall: 0 });
      this.updateStatistics({
        totalReps: 0,
        workoutTime: "00:00",
        calories: "0.0 kcal",
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
