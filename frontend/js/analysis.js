/**
 * PoseAI Analysis Page Controller
 * Real MongoDB data + Chart.js functional graphs + unified global integration
 */
(function () {
  "use strict";

  if (typeof Chart !== "undefined" && Chart.defaults && Chart.defaults.font) {
    Chart.defaults.font.family = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
  }

  let formAccuracyChartInstance = null;
  let jointAngleChartInstance = null;
  let consistencyChartInstance = null;
  let currentWorkoutId = null;

  // Utility formatters
  function formatSeconds(sec) {
    const total = Number(sec) || 0;
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function formatDate(isoStr) {
    if (!isoStr) return "--";
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch (_) {
      return isoStr;
    }
  }

  function formatTime(isoStr) {
    if (!isoStr) return "--";
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return "--";
      return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    } catch (_) {
      return "--";
    }
  }

  // Load all user workouts for the selector dropdown
  async function loadWorkoutsList() {
    const selector = document.getElementById("workoutSelector");
    if (!selector) return;

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      let workouts = [];
      let res = await fetch(getUrl("/api/workouts"), { credentials: "include" });
      if (res.ok) {
        const json = await res.json();
        workouts = json.workouts || (json.data && json.data.workouts) || [];
      } else {
        const altRes = await fetch(getUrl("/api/analysis/workouts"), { credentials: "include" });
        if (altRes.ok) {
          const json = await altRes.json();
          workouts = json.workouts || (json.data && json.data.workouts) || [];
        }
      }

      selector.innerHTML = "";

      if (workouts.length === 0) {
        // Fallback: Check if latest workout exists on /api/analysis or /api/workouts
        try {
          const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
          const directRes = await fetch(getUrl("/api/analysis"), { credentials: "include" });
          if (directRes.ok) {
            const directJson = await directRes.json();
            const d = directJson.workout || directJson.data;
            if (d && (d.hasData || d.exercise)) {
              const opt = document.createElement("option");
              opt.value = d.id || d._id || "latest";
              const reps = d.total_reps != null ? d.total_reps : (d.reps != null ? d.reps : 0);
              const acc = d.form_accuracy != null ? Math.round(d.form_accuracy) : (d.accuracy != null ? Math.round(d.accuracy) : 0);
              opt.textContent = `${d.exercise_name || d.exercise} — ${formatDate(d.date)} — ${reps} reps — ${acc}% form`;
              selector.appendChild(opt);
              currentWorkoutId = opt.value;
              showEmptyState(false);
              loadWorkoutAnalysis(currentWorkoutId);
              return;
            }
          }
        } catch (_) {}

        showEmptyState(true);
        return;
      }

      showEmptyState(false);

      const urlParams = new URLSearchParams(window.location.search);
      const requestedId = urlParams.get("workoutId") || urlParams.get("workout_id");

      workouts.forEach((w) => {
        const opt = document.createElement("option");
        opt.value = w.id;
        const dateStr = formatDate(w.date);
        const reps = w.total_reps != null ? w.total_reps : (w.reps != null ? w.reps : 0);
        const acc = w.form_accuracy != null ? Math.round(w.form_accuracy) : (w.accuracy != null ? Math.round(w.accuracy) : 0);
        opt.textContent = `${w.exercise_name || w.exercise} — ${dateStr} — ${reps} reps — ${acc}% form`;
        selector.appendChild(opt);
      });

      // Select requested workout or newest
      if (requestedId && workouts.some((w) => String(w.id) === String(requestedId))) {
        selector.value = requestedId;
      } else {
        selector.value = workouts[0].id;
      }

      currentWorkoutId = selector.value;
      loadWorkoutAnalysis(currentWorkoutId);

      selector.onchange = function () {
        currentWorkoutId = this.value;
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.set("workoutId", currentWorkoutId);
        newUrl.searchParams.delete("workout_id");
        window.history.replaceState({}, "", newUrl.toString());
        loadWorkoutAnalysis(currentWorkoutId);
      };
    } catch (err) {
      console.error("Error loading workouts:", err);
      showEmptyState(true);
    }
  }

  // Load specific workout analysis
  async function loadWorkoutAnalysis(workoutId) {
    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      let data = null;
      if (workoutId && workoutId !== "latest") {
        let res = await fetch(getUrl(`/api/workouts/${encodeURIComponent(workoutId)}`), { credentials: "include" });
        if (res.ok) {
          const json = await res.json();
          data = json.workout || json.data;
        } else {
          const altRes = await fetch(getUrl(`/api/analysis/workout/${encodeURIComponent(workoutId)}`), { credentials: "include" });
          if (altRes.ok) {
            const json = await altRes.json();
            data = json.workout || json.data;
          }
        }
      } else {
        const res = await fetch(getUrl(`/api/analysis`), { credentials: "include" });
        if (res.ok) {
          const json = await res.json();
          data = json.workout || json.data;
        }
      }

      if (!data || (!data.hasData && !data.exercise)) {
        showEmptyState(true);
        return;
      }

      showEmptyState(false);
      populateOverviewAndStats(data);
      populateCoachAndFeedback(data);
      renderFormAccuracyChart(data.form_history || [], data);
      renderJointAngleChart(data.joint_angles || [], data);
      renderConsistencyChart(data);
      populateSetTable(data.sets_detail || data.sets || []);
      populateNutritionCard(data.nutrition || {});
      populateWorkoutDetails(data);
      if (workoutId && workoutId !== "latest") {
        loadPreviousComparison(workoutId);
      }
    } catch (err) {
      console.error("Error loading analysis data:", err);
      showEmptyState(true);
    }
  }

  function showEmptyState(isEmpty) {
    const emptyEl = document.getElementById("emptyState");
    const contentEl = document.getElementById("analysisContent");
    const downloadBtn = document.getElementById("downloadReportBtn");

    if (emptyEl) emptyEl.style.display = isEmpty ? "block" : "none";
    if (contentEl) contentEl.style.display = isEmpty ? "none" : "block";
    if (downloadBtn) downloadBtn.style.display = isEmpty ? "none" : "inline-flex";
  }

  // Populate hero stats and top summary
  function populateOverviewAndStats(data) {
    setText("sessionExerciseHeader", data.exercise_name || data.exercise || "--");
    setText("sessionDateHeader", formatDate(data.date));
    setText("sessionTimeHeader", data.completed_at ? formatTime(data.completed_at) : "--");
    setText("sessionStatusHeader", data.completed_sets >= data.target_sets ? "Completed" : "Logged");

    setText("statTotalReps", data.total_reps != null ? `${data.total_reps} reps` : "--");
    setText("statSets", data.completed_sets != null ? `${data.completed_sets} / ${data.target_sets || data.sets || 3}` : "--");
    setText("statAccuracy", data.form_accuracy != null ? `${Math.round(data.form_accuracy)}%` : "--");
    setText("statCalories", data.calories != null ? `${Math.round(data.calories)} kcal` : "--");
    setText("statDuration", data.duration != null ? formatSeconds(data.duration) : "--");

    // Train again button link
    const trainAgainBtn = document.getElementById("trainAgainBtn");
    if (trainAgainBtn && data.exercise) {
      trainAgainBtn.href = `/workout?exercise=${encodeURIComponent(data.exercise)}`;
    }
  }

  // Populate AI Coach recommendation, strengths, and weaknesses
  // Populate AI Coach recommendation, strengths, and weaknesses
  function populateCoachAndFeedback(data) {
    const coachBox = document.getElementById("coachRecommendationText");
    if (coachBox) {
      coachBox.textContent = data.coach_recommendation || "Maintain controlled cadence and consistent joint alignment throughout each set.";
    }

    // Strengths
    const strengthsList = document.getElementById("strengthsList");
    if (strengthsList) {
      strengthsList.innerHTML = "";
      const strengths = data.strengths && data.strengths.length ? data.strengths : ["Exercise cadence maintained during active sets."];
      strengths.forEach((s) => {
        const li = document.createElement("li");
        li.className = "sw-item";
        li.innerHTML = `<span class="material-symbols-outlined text-emerald-600 text-[16px] shrink-0">check_circle</span> <span>${escapeHtml(s)}</span>`;
        strengthsList.appendChild(li);
      });
    }

    // Weaknesses / Improvements
    const improvementsList = document.getElementById("improvementsList");
    if (improvementsList) {
      improvementsList.innerHTML = "";
      const improvements = data.improvements && data.improvements.length ? data.improvements : ["No significant form faults detected."];
      improvements.forEach((imp) => {
        const li = document.createElement("li");
        li.className = "sw-item";
        li.innerHTML = `<span class="material-symbols-outlined text-amber-600 text-[16px] shrink-0">info</span> <span>${escapeHtml(imp)}</span>`;
        improvementsList.appendChild(li);
      });
    }

    // Biomechanics metrics & adaptive joint label
    const bio = data.biomechanics || {};
    const exName = (data.exercise || "").toLowerCase();
    const jointLabel = exName.includes("squat") || exName.includes("lunge") ? "Knee Alignment" : (exName.includes("press") || exName.includes("push") ? "Shoulder / Elbow" : "Elbow Position");
    const jointLabelEl = document.getElementById("bioJointLabel");
    if (jointLabelEl) jointLabelEl.textContent = jointLabel;

    setText("bioElbow", bio.elbow_position || "Stable");
    setText("bioRom", bio.range_of_motion != null ? `${bio.range_of_motion}°` : "--");
    setText("bioTempo", bio.eccentric_tempo != null ? `${bio.eccentric_tempo}s` : "--");
  }

  // Helper to build timeline timestamps on X-axis (e.g. 14:20, 14:22 or 00:15, 00:30)
  function buildTimelineLabels(items, data) {
    const count = items.length;
    if (!count) return [];

    const start = data.started_at ? new Date(data.started_at) : (data.completed_at ? new Date(new Date(data.completed_at).getTime() - (data.duration || 60) * 1000) : null);
    const duration = Number(data.duration) || (count * 3);
    const intervalSec = count > 1 ? duration / (count - 1) : 0;

    return items.map((it, idx) => {
      if (it.timestamp || it.time) {
        const t = it.timestamp || it.time;
        if (typeof t === "string" && t.includes(":")) return t;
        const d = new Date(t);
        if (!isNaN(d.getTime())) {
          return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }
      }
      if (start && !isNaN(start.getTime())) {
        const pt = new Date(start.getTime() + idx * intervalSec * 1000);
        return pt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      }
      const elapsedSec = Math.round(idx * intervalSec);
      const m = Math.floor(elapsedSec / 60);
      const s = elapsedSec % 60;
      return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    });
  }

  // Chart.js: Form Accuracy Graph (Timeline vs Form Accuracy %)
  function renderFormAccuracyChart(formHistory, data) {
    data = data || {};
    const canvas = document.getElementById("formAccuracyChart");
    if (!canvas) return;

    if (formAccuracyChartInstance) {
      formAccuracyChartInstance.destroy();
    }

    const emptyNote = document.getElementById("formAccuracyEmpty");
    const points = (Array.isArray(data.rep_data) && data.rep_data.length > 0)
      ? data.rep_data.filter((r) => r.accuracy != null || r.form_accuracy != null)
      : ((Array.isArray(data.rep_history) && data.rep_history.length > 0)
          ? data.rep_history.filter((r) => r.form_accuracy != null || r.accuracy != null)
          : ((formHistory && formHistory.length > 0)
              ? formHistory
              : ((data.form_accuracy_data && data.form_accuracy_data.length > 0)
                  ? data.form_accuracy_data
                  : ((data.form_accuracy_series && data.form_accuracy_series.length > 0)
                      ? data.form_accuracy_series
                      : (data.timeline_data && data.timeline_data.filter((t) => t.accuracy != null))))));

    if (!points || points.length === 0) {
      if (emptyNote) {
        emptyNote.style.display = "block";
        emptyNote.innerHTML = `
          <p class="font-bold text-slate-800 mb-1">Detailed movement timeline was not recorded for this workout.</p>
          <p class="text-xs text-slate-500">Summary metrics above are fully recorded from your completed session.</p>
        `;
      }
      canvas.style.display = "none";
      return;
    }
    if (emptyNote) emptyNote.style.display = "none";
    canvas.style.display = "block";

    const labels = points.map((item, idx) => {
      if (item.rep != null) return `Rep ${item.rep}`;
      if (item.timestamp && typeof item.timestamp === "string" && item.timestamp.includes(":")) return item.timestamp;
      return `Rep ${idx + 1}`;
    });
    const dataPoints = points.map((item) => {
      const val = item.accuracy != null ? item.accuracy : (item.form_accuracy != null ? item.form_accuracy : item.score);
      return Math.round(Number(val) || 0);
    });
    const avgScore = Math.round(data.form_accuracy || data.accuracy || (dataPoints.reduce((a, b) => a + b, 0) / dataPoints.length));
    const bestScore = Math.max(...dataPoints);
    const currentScore = dataPoints[dataPoints.length - 1];
    const exerciseTitle = data.exercise_name || data.exercise || "Workout";

    const ctx = canvas.getContext("2d");
    formAccuracyChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Form Accuracy (%)",
            data: dataPoints,
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.08)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointBackgroundColor: "#2563eb",
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            padding: 10,
            cornerRadius: 8,
            titleFont: { size: 12, weight: "bold" },
            bodyFont: { size: 12 },
            callbacks: {
              title: (ctxList) => ctxList[0].label,
              label: (context) => [
                `Form Accuracy: ${context.parsed.y}%`,
                `Exercise: ${exerciseTitle}`,
                `Current: ${currentScore}% | Avg: ${avgScore}% | Best: ${bestScore}%`,
              ],
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            title: { display: true, text: "Repetitions", font: { size: 11, weight: 600 }, color: "#64748b" },
            ticks: { font: { size: 10 }, maxRotation: 0 },
          },
          y: {
            min: 0,
            max: 100,
            grid: { color: "#f1f5f9" },
            title: { display: true, text: "Form Accuracy (%)", font: { size: 11, weight: 600 }, color: "#64748b" },
            ticks: {
              callback: (val) => `${val}%`,
              font: { size: 10 },
            },
          },
        },
      },
    });
  }

  // Chart.js: Joint Angle & ROM Graph (Adapts to exercise biomechanics)
  function renderJointAngleChart(jointAngles, data) {
    data = data || {};
    const canvas = document.getElementById("jointAngleChart");
    if (!canvas) return;

    if (jointAngleChartInstance) {
      jointAngleChartInstance.destroy();
    }

    const emptyNote = document.getElementById("jointAngleEmpty");
    const points = (Array.isArray(data.angle_data) && data.angle_data.length > 0)
      ? data.angle_data.filter((r) => r.angle != null || r.deg != null)
      : ((Array.isArray(data.joint_angles) && data.joint_angles.length > 0)
          ? data.joint_angles.filter((r) => r.angle != null || r.deg != null)
          : ((Array.isArray(data.joint_angle_series) && data.joint_angle_series.length > 0)
              ? data.joint_angle_series.filter((r) => r.angle != null)
              : ((Array.isArray(data.rep_data) && data.rep_data.some((r) => r.angle != null))
                  ? data.rep_data.filter((r) => r.angle != null)
                  : (data.timeline_data && data.timeline_data.filter((t) => t.angle != null)))));

    if (!points || points.length === 0) {
      if (emptyNote) {
        emptyNote.style.display = "block";
        emptyNote.innerHTML = `
          <p class="font-bold text-slate-800 mb-1">Detailed movement timeline was not recorded for this workout.</p>
          <p class="text-xs text-slate-500">Summary metrics above are fully recorded from your completed session.</p>
        `;
      }
      canvas.style.display = "none";
      return;
    }
    if (emptyNote) emptyNote.style.display = "none";
    canvas.style.display = "block";

    const exName = (data.exercise || "").toLowerCase();
    let jointName = "Joint Angle";
    if (exName.includes("squat") || exName.includes("lunge")) {
      jointName = "Knee Angle";
    } else if (exName.includes("press") || exName.includes("push")) {
      jointName = "Shoulder Angle";
    } else if (exName.includes("curl")) {
      jointName = "Elbow Angle";
    }

    const titleEl = document.getElementById("jointAngleCardTitle");
    if (titleEl) titleEl.textContent = `${jointName.toUpperCase()} & RANGE OF MOTION`;
    const subEl = document.getElementById("jointAngleCardSub");
    if (subEl) subEl.textContent = `Measured ${jointName.toLowerCase()} across completed repetitions`;

    const labels = points.map((item, idx) => {
      if (item.rep != null) return `Rep ${item.rep}`;
      if (item.timestamp && typeof item.timestamp === "string" && item.timestamp.includes(":")) return item.timestamp;
      return `Rep ${idx + 1}`;
    });
    const dataPoints = points.map((item) => Number(item.angle != null ? item.angle : item.deg) || 0);
    const exerciseTitle = data.exercise_name || data.exercise || "Workout";

    const ctx = canvas.getContext("2d");
    jointAngleChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: `${jointName} (°)`,
            data: dataPoints,
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.08)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.3,
            pointBackgroundColor: "#10b981",
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            padding: 10,
            cornerRadius: 8,
            titleFont: { size: 12, weight: "bold" },
            bodyFont: { size: 12 },
            callbacks: {
              title: (ctxList) => ctxList[0].label,
              label: (context) => [
                `${jointName}: ${context.parsed.y}°`,
                `Exercise: ${exerciseTitle}`,
              ],
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            title: { display: true, text: "Repetitions", font: { size: 11, weight: 600 }, color: "#64748b" },
            ticks: { font: { size: 10 }, maxRotation: 0 },
          },
          y: {
            grid: { color: "#f1f5f9" },
            title: { display: true, text: "Degrees (°)", font: { size: 11, weight: 600 }, color: "#64748b" },
            ticks: {
              callback: (val) => `${val}°`,
              font: { size: 10 },
            },
          },
        },
      },
    });
  }

  // Chart.js: Form Consistency (Average, Best, Lowest)
  function renderConsistencyChart(data) {
    const consistency = data.form_consistency || {};
    setText("consAvg", consistency.average != null ? `${consistency.average}%` : "--");
    setText("consBest", consistency.best != null ? `${consistency.best}%` : "--");
    setText("consLowest", consistency.lowest != null ? `${consistency.lowest}%` : "--");

    const canvas = document.getElementById("consistencyChart");
    if (!canvas) return;

    if (consistencyChartInstance) {
      consistencyChartInstance.destroy();
    }

    if (consistency.average == null) {
      canvas.style.display = "none";
      return;
    }
    canvas.style.display = "block";

    const ctx = canvas.getContext("2d");
    consistencyChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Lowest", "Average", "Best"],
        datasets: [
          {
            label: "Form Accuracy",
            data: [consistency.lowest || 0, consistency.average || 0, consistency.best || 0],
            backgroundColor: ["#fca5a5", "#93c5fd", "#86efac"],
            borderRadius: 6,
            barThickness: 28,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            min: 50,
            max: 100,
            grid: { color: "#f1f5f9" },
            ticks: { callback: (val) => `${val}%` },
          },
        },
      },
    });
  }

  // Set-by-Set Performance Table
  function populateSetTable(setsDetail) {
    const tbody = document.getElementById("setTableBody");
    const emptyMsg = document.getElementById("setTableEmpty");
    if (!tbody) return;

    tbody.innerHTML = "";

    const sets = Array.isArray(setsDetail) && setsDetail.length > 0 ? setsDetail : [];

    if (!sets || sets.length === 0) {
      if (emptyMsg) emptyMsg.style.display = "block";
      return;
    }
    if (emptyMsg) emptyMsg.style.display = "none";

    sets.forEach((s) => {
      const tr = document.createElement("tr");

      const isGood = (s.status || "").toLowerCase().includes("completed") || (s.accuracy || s.form_score || 0) >= 80;
      const statusBadge = `<span class="badge-status ${isGood ? "good" : "warning"}">${escapeHtml(s.status || "Completed")}</span>`;

      const repsDisplay = s.completed_reps != null
        ? `${s.completed_reps}${s.target_reps ? ` / ${s.target_reps}` : ""}`
        : (s.reps != null ? `${s.reps}${s.target_reps ? ` / ${s.target_reps}` : ""}` : "--");
      const accDisplay = s.accuracy != null
        ? `${Math.round(s.accuracy)}%`
        : (s.form_score != null ? `${Math.round(s.form_score)}%` : "--");
      const angleDisplay = s.average_angle != null
        ? `${Math.round(s.average_angle)}°`
        : (s.avg_angle != null ? `${Math.round(s.avg_angle)}°` : "--");
      const tempoDisplay = s.average_tempo != null
        ? `${s.average_tempo}s`
        : (s.tempo != null ? `${s.tempo}s` : "--");

      tr.innerHTML = `
        <td style="font-weight: 700;">Set ${s.set_number || 1}</td>
        <td>${repsDisplay}</td>
        <td>${accDisplay}</td>
        <td>${angleDisplay}</td>
        <td>${tempoDisplay}</td>
        <td>${statusBadge}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Energy & Nutrition Integration Card
  function populateNutritionCard(nutrition) {
    const intakeEl = document.getElementById("nutFoodIntake");
    const burnEl = document.getElementById("nutActivityBurn");
    const netEl = document.getElementById("nutNetRecorded");
    const proteinEl = document.getElementById("nutProtein");
    const carbsEl = document.getElementById("nutCarbs");
    const fatEl = document.getElementById("nutFat");
    const emptyMsg = document.getElementById("nutEmptyMsg");
    const macroRow = document.getElementById("nutMacroGrid");

    if (burnEl) {
      burnEl.textContent = nutrition.activity_burn != null ? `${nutrition.activity_burn} kcal` : "--";
    }

    if (!nutrition.has_nutrition) {
      if (intakeEl) intakeEl.textContent = "--";
      if (netEl) netEl.textContent = "--";
      if (emptyMsg) emptyMsg.style.display = "block";
      if (macroRow) macroRow.style.display = "none";
      return;
    }

    if (emptyMsg) emptyMsg.style.display = "none";
    if (macroRow) macroRow.style.display = "grid";

    if (intakeEl) intakeEl.textContent = `${nutrition.food_intake} kcal`;
    if (netEl) netEl.textContent = `${nutrition.net_recorded} kcal`;
    if (proteinEl) proteinEl.textContent = nutrition.protein_g != null ? `${nutrition.protein_g}g` : "--";
    if (carbsEl) carbsEl.textContent = nutrition.carbs_g != null ? `${nutrition.carbs_g}g` : "--";
    if (fatEl) fatEl.textContent = nutrition.fat_g != null ? `${nutrition.fat_g}g` : "--";
  }

  // Workout Details Metadata Card
  function populateWorkoutDetails(data) {
    setText("detailExercise", data.exercise_name || data.exercise || "--");
    setText("detailDate", formatDate(data.date || data.completed_at || data.started_at));
    setText("detailStartTime", data.started_at ? formatTime(data.started_at) : "--");
    setText("detailEndTime", data.completed_at ? formatTime(data.completed_at) : "--");
    setText("detailDuration", data.duration != null ? formatSeconds(data.duration) : "--");
    setText("detailTotalReps", data.total_reps != null ? String(data.total_reps) : (data.reps != null ? String(data.reps) : "--"));
    setText("detailTotalSets", String(data.completed_sets != null ? data.completed_sets : (data.total_sets != null ? data.total_sets : (data.sets != null ? data.sets : "--"))));
    setText("detailCalories", data.calories != null ? `${Math.round(data.calories)} kcal` : "--");
    setText("detailAccuracy", data.form_accuracy != null ? `${Math.round(data.form_accuracy)}%` : (data.accuracy != null ? `${Math.round(data.accuracy)}%` : "--"));
    setText("detailStatus", data.status || (data.completed_sets >= data.target_sets ? "Completed" : "Logged"));
  }

  // Previous session comparison
  async function loadPreviousComparison(workoutId) {
    const emptyBox = document.getElementById("prevSessionEmpty");
    const contentBox = document.getElementById("prevSessionContent");

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      const res = await fetch(getUrl(`/api/analysis/previous/${encodeURIComponent(workoutId)}`), {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Could not fetch comparison");
      const json = await res.json();
      const comp = (json.data && json.data.comparison) || null;

      if (!json.data || !json.data.hasPrevious || !comp) {
        if (emptyBox) {
          emptyBox.style.display = "block";
          emptyBox.textContent = (json.data && json.data.message) || "No previous session available for this exercise.";
        }
        if (contentBox) contentBox.style.display = "none";
        return;
      }

      if (emptyBox) emptyBox.style.display = "none";
      if (contentBox) contentBox.style.display = "flex";

      // Form accuracy comparison
      const currAcc = comp.current.accuracy != null ? `${Math.round(comp.current.accuracy)}%` : "--";
      const prevAcc = comp.previous.accuracy != null ? `${Math.round(comp.previous.accuracy)}%` : "--";
      setText("prevAccFlow", `${prevAcc} → ${currAcc}`);
      renderDelta("prevAccDelta", comp.accuracy_diff, "%");

      // Total reps comparison
      const currReps = comp.current.reps != null ? comp.current.reps : "--";
      const prevReps = comp.previous.reps != null ? comp.previous.reps : "--";
      setText("prevRepsFlow", `${prevReps} → ${currReps}`);
      renderDelta("prevRepsDelta", comp.reps_diff, "");

      // Average angle comparison
      const currAngle = comp.current.average_angle != null ? `${Math.round(comp.current.average_angle)}°` : "--";
      const prevAngle = comp.previous.average_angle != null ? `${Math.round(comp.previous.average_angle)}°` : "--";
      setText("prevAngleFlow", `${prevAngle} → ${currAngle}`);
      renderDelta("prevAngleDelta", comp.angle_diff, "°");
    } catch (err) {
      if (emptyBox) {
        emptyBox.style.display = "block";
        emptyBox.textContent = "No previous session available for this exercise.";
      }
      if (contentBox) contentBox.style.display = "none";
    }
  }

  function renderDelta(elemId, diff, unit) {
    const el = document.getElementById(elemId);
    if (!el) return;
    if (diff == null || isNaN(diff)) {
      el.textContent = "--";
      el.className = "delta-tag";
      return;
    }
    const sign = diff > 0 ? "+" : "";
    el.textContent = `${sign}${diff}${unit}`;
    el.className = `delta-tag ${diff >= 0 ? "pos" : "neg"}`;
  }

  // Download real sanitized report
  async function downloadReport() {
    if (!currentWorkoutId) return;

    try {
      const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
      let res = await fetch(getUrl(`/api/workouts/${encodeURIComponent(currentWorkoutId)}/report`), {
        credentials: "include",
      });
      if (!res.ok) {
        res = await fetch(getUrl(`/api/analysis/workout/${encodeURIComponent(currentWorkoutId)}/report`), {
          credentials: "include",
        });
      }
      if (!res.ok) throw new Error("Could not download report");
      const json = await res.json();
      const r = json.data || {};
      const w = r.workout || {};
      const b = r.biomechanics || {};
      const a = r.joint_angle_metrics || {};

      let setRows = "No set details recorded.";
      if (Array.isArray(r.set_by_set_performance) && r.set_by_set_performance.length > 0) {
        setRows = r.set_by_set_performance.map((s) => {
          return `Set ${s.set_number || 1}: ${s.completed_reps || s.reps || 0} reps | Acc: ${Math.round(s.accuracy || 0)}% | Avg Angle: ${Math.round(s.average_angle || 0)}° | Tempo: ${s.average_tempo || "--"}s | Status: ${s.status || "Completed"}`;
        }).join("\n  ");
      }

      const reportText = `============================================================
POSEAI WORKOUT ANALYSIS REPORT
Generated: ${r.generated_at || new Date().toISOString()}
============================================================

WORKOUT SUMMARY
------------------------------------------------------------
Workout ID:        ${w.id || currentWorkoutId}
Exercise:          ${w.exercise || "--"}
Date:              ${w.date || "--"}
Duration:          ${w.duration_seconds != null ? formatSeconds(w.duration_seconds) : "--"}
Total Reps:        ${w.total_reps != null ? w.total_reps : "--"}
Completed Sets:    ${w.completed_sets != null ? w.completed_sets : "--"} / ${w.target_sets || "--"}
Form Accuracy:     ${w.form_accuracy_percent != null ? Math.round(w.form_accuracy_percent) + "%" : "--"}
Calories Burned:   ${w.calories_kcal != null ? w.calories_kcal + " kcal" : "--"}

BIOMECHANICAL OBSERVATIONS
------------------------------------------------------------
Joint Tracked:     ${a.joint_name || "Primary Joint"}
Average Angle:     ${a.average_angle != null ? Math.round(a.average_angle) + "°" : "--"}
Peak Flexion:      ${a.peak_flexion != null ? Math.round(a.peak_flexion) + "°" : "--"}
Peak Extension:    ${a.peak_extension != null ? Math.round(a.peak_extension) + "°" : "--"}
Range of Motion:   ${a.range_of_motion != null ? Math.round(a.range_of_motion) + "°" : "--"}
Rep Consistency:   ${r.form_consistency ? r.form_consistency.consistency_score + "% (" + r.form_consistency.rating + ")" : "--"}

SET-BY-SET PERFORMANCE
------------------------------------------------------------
  ${setRows}

AI COACHING RECOMMENDATION
------------------------------------------------------------
${r.ai_coach_recommendation || "Maintain consistent tempo and prioritize full range of motion on every repetition."}

STRENGTHS:
${Array.isArray(r.strengths) && r.strengths.length > 0 ? r.strengths.map(s => "  - " + s).join("\n") : "  - Good baseline consistency"}

AREAS FOR IMPROVEMENT:
${Array.isArray(r.areas_for_improvement) && r.areas_for_improvement.length > 0 ? r.areas_for_improvement.map(i => "  - " + i).join("\n") : "  - Continue practicing controlled eccentric phase"}

============================================================
CONFIDENTIAL & PROPRIETARY — POSEAI FITNESS PLATFORM
============================================================`;

      const blob = new Blob([reportText], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const downloadLink = document.createElement("a");
      downloadLink.href = url;
      downloadLink.download = `PoseAI_Workout_Report_${w.exercise || "Session"}_${w.date || currentWorkoutId}.txt`;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Unable to download report. Please try again.");
    }
  }

  // Helper text setter
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function escapeHtml(str) {
    return String(str || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Initialize page
  function init() {
    const downloadBtn = document.getElementById("downloadReportBtn");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", downloadReport);
    }
    loadWorkoutsList();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
