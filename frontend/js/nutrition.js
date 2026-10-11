/**
 * PoseAI Nutrition Intelligence System — Frontend Controller
 * ==========================================================
 * Manages live camera streaming, food image upload, AI estimation review,
 * meal timeline CRUD, interactive macro trends, and workout integration.
 */

"use strict";

const NutritionApp = (function () {
  // State
  const state = {
    todayData: null,
    trendsData: null,
    trendDays: 7,
    currentScan: null,
    cameraStream: null,
    targetMealType: "lunch",
    activePortionQty: 1,
    myFoods: [],
  };

  // Helper DOM selector
  const $ = (id) => document.getElementById(id);

  async function nutFetch(path, opts = {}) {
    const getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : (p) => p;
    return fetch(getUrl(path), {
      ...opts,
      credentials: "include",
    });
  }

  // ── INIT ─────────────────────────────────────────────────────────────
  async function init() {
    wireEvents();
    await loadTodayData();
    await loadTrends(7);
  }

  function wireEvents() {
    // Hero buttons
    $("scanFoodHeroBtn").addEventListener("click", () => openScannerModal("camera"));
    $("uploadFoodHeroBtn").addEventListener("click", () => $("hiddenFileInput").click());
    $("hiddenFileInput").addEventListener("change", handleFileUpload);

    // Modal controls
    $("closeModalBtn").addEventListener("click", closeScannerModal);
    $("startCamBtn").addEventListener("click", startCamera);
    $("captureCamBtn").addEventListener("click", captureSnapshot);
    $("retakeCamBtn").addEventListener("click", retakePhoto);
    $("pickFileModalBtn").addEventListener("click", () => $("hiddenFileInput").click());

    // Portion stepper
    $("portionMinusBtn").addEventListener("click", () => adjustPortion(-0.5));
    $("portionPlusBtn").addEventListener("click", () => adjustPortion(0.5));
    $("portionInput").addEventListener("change", (e) => {
      const val = parseFloat(e.target.value) || 1;
      setPortion(val);
    });

    // Confirmation
    $("confirmLogBtn").addEventListener("click", confirmCurrentScan);

    // Manual search fallback
    $("manualEditBtn").addEventListener("click", () => {
      $("manualSearchSection").classList.toggle("hidden");
      openManualSection();
    });
    $("doSearchBtn").addEventListener("click", performFoodSearch);
    $("foodSearchInput").addEventListener("keypress", (e) => {
      if (e.key === "Enter") performFoodSearch();
    });

    // Manual nutrition entry
    $("manualEntryHeroBtn").addEventListener("click", openManualEntry);
    $("manualSaveBtn").addEventListener("click", saveManualEntry);
    $("myFoodsRefreshBtn").addEventListener("click", loadMyFoods);

    // Quick add food from timeline
    $("addMealQuickBtn").addEventListener("click", () => openScannerModal("camera", "lunch"));

    // Macro filter buttons
    $("macroFilter7Days").addEventListener("click", () => switchTrends(7));
    $("macroFilter30Days").addEventListener("click", () => switchTrends(30));

    // Developer debug panel toggle (Requirement 35)
    $("toggleDevDebugBtn")?.addEventListener("click", () => {
      $("scannerDebugContainer")?.classList.toggle("hidden");
    });

    // Candidate selection card action buttons (Requirement 29)
    $("candidateScanAgainBtn")?.addEventListener("click", () => {
      $("candidateSelectionCard")?.classList.add("hidden");
      retakePhoto();
    });
    $("candidateManualBtn")?.addEventListener("click", () => {
      $("candidateSelectionCard")?.classList.add("hidden");
      openManualSection();
    });

    // View recommendation button
    $("viewRecommendationBtn").addEventListener("click", () => {
      const ins = state.todayData?.daily_insight;
      if (ins?.recommendations?.length) {
        alert("PoseAI Nutrition Recommendations:\n\n• " + ins.recommendations.join("\n• "));
      } else {
        alert("Keep logging your meals and workouts today for more tailored recommendations!");
      }
    });
  }

  // ── DATA FETCHING & RENDERING ────────────────────────────────────────

  async function loadTodayData() {
    try {
      const res = await nutFetch("/api/nutrition/today");
      const json = await res.json();
      if (!json.success) throw new Error(json.error || "Failed to load nutrition data");

      state.todayData = json.data;
      renderOverview(json.data);
      renderEnergyBalance(json.data.energy_balance);
      renderMacros(json.data.totals);
      renderMealTimeline(json.data.meal_timeline);
      renderFoodQuality(json.data.food_quality);
      renderInsight(json.data.daily_insight);
      renderActivitySuggestion(json.data.activity_suggestion);
    } catch (err) {
      console.error("Error loading today's nutrition:", err);
    }
  }

  async function loadTrends(days) {
    try {
      state.trendDays = days;
      const res = await nutFetch(`/api/nutrition/trends?days=${days}`);
      const json = await res.json();
      if (json.success) {
        state.trendsData = json.data;
        renderTrendChart(json.data.history || []);
      }
    } catch (err) {
      console.error("Error loading nutrition trends:", err);
    }
  }

  function switchTrends(days) {
    if (days === 7) {
      $("macroFilter7Days").className = "px-3 py-1 rounded-full bg-white shadow-sm text-slate-900 font-bold transition-colors";
      $("macroFilter30Days").className = "px-3 py-1 rounded-full text-slate-500 hover:text-slate-900 transition-colors";
      $("trendDaysLabel").textContent = "Past 7 days";
    } else {
      $("macroFilter7Days").className = "px-3 py-1 rounded-full text-slate-500 hover:text-slate-900 transition-colors";
      $("macroFilter30Days").className = "px-3 py-1 rounded-full bg-white shadow-sm text-slate-900 font-bold transition-colors";
      $("trendDaysLabel").textContent = "Past 30 days";
    }
    loadTrends(days);
  }

  // ── COMPONENT RENDERERS ─────────────────────────────────────────────

  function renderOverview(data) {
    const totals = data.totals || {};
    const targets = data.targets || {};

    // Check if targets are configured
    if (!targets.configured) {
      $("targetWarningBanner").classList.remove("hidden");
    } else {
      $("targetWarningBanner").classList.add("hidden");
    }

    const tCal = targets.calories_kcal || 2200;
    const tProt = targets.protein_g || 120;
    const tCarb = targets.carbs_g || 275;
    const tFat = targets.fat_g || 70;

    const cCal = totals.calories_kcal || 0;
    const cProt = Math.round(totals.protein_g || 0);
    const cCarb = Math.round(totals.carbs_g || 0);
    const cFat = Math.round(totals.fat_g || 0);

    // Current numbers
    $("overviewCalCurrent").textContent = cCal.toLocaleString();
    $("overviewCalTarget").textContent = `/ ${tCal.toLocaleString()} kcal`;
    $("overviewCalBar").style.width = Math.min(100, Math.round((cCal / tCal) * 100)) + "%";

    $("overviewProtCurrent").textContent = cProt;
    $("overviewProtTarget").textContent = `/ ${tProt}g`;
    $("overviewProtBar").style.width = Math.min(100, Math.round((cProt / tProt) * 100)) + "%";

    $("overviewCarbCurrent").textContent = cCarb;
    $("overviewCarbTarget").textContent = `/ ${tCarb}g`;
    $("overviewCarbBar").style.width = Math.min(100, Math.round((cCarb / tCarb) * 100)) + "%";

    $("overviewFatCurrent").textContent = cFat;
    $("overviewFatTarget").textContent = `/ ${tFat}g`;
    $("overviewFatBar").style.width = Math.min(100, Math.round((cFat / tFat) * 100)) + "%";

    if (data.date) {
      const d = new Date(data.date + "T00:00:00");
      $("overviewDateBadge").textContent = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    }
  }

  function renderEnergyBalance(energy) {
    if (!energy) return;
    $("energyEatenVal").textContent = `${(energy.eaten_kcal || 0).toLocaleString()} kcal`;
    $("energyActivityVal").textContent = `-${(energy.activity_kcal || 0).toLocaleString()} kcal`;
    $("energyNetVal").textContent = `${(energy.net_recorded_kcal || 0).toLocaleString()} kcal`;
    const count = state.todayData?.activity?.workout_count || 0;
    $("energyActivityCount").textContent = `${count} PoseAI Workout${count === 1 ? "" : "s"}`;
  }

  function renderMacros(totals) {
    if (!totals) return;
    const cal = totals.calories_kcal || 1;
    const prot = totals.protein_g || 0;
    const carb = totals.carbs_g || 0;
    const fat = totals.fat_g || 0;

    $("macroProtVal").textContent = `${Math.round(prot)}g`;
    $("macroProtPct").textContent = `${Math.round(((prot * 4) / cal) * 100)}% of calories`;

    $("macroCarbVal").textContent = `${Math.round(carb)}g`;
    $("macroCarbPct").textContent = `${Math.round(((carb * 4) / cal) * 100)}% of calories`;

    $("macroFatVal").textContent = `${Math.round(fat)}g`;
    $("macroFatPct").textContent = `${Math.round(((fat * 9) / cal) * 100)}% of calories`;

    $("macroFiberVal").textContent = `${Math.round(totals.fiber_g || 0)}g`;
    $("macroSugarVal").textContent = `${Math.round(totals.sugar_g || 0)}g`;
    $("macroSodiumVal").textContent = `${Math.round(totals.sodium_mg || 0)}mg`;
  }

  function renderMealTimeline(timeline) {
    if (!timeline) return;
    const mealTypes = ["breakfast", "lunch", "snack", "dinner"];

    mealTypes.forEach((mt) => {
      const items = timeline[mt] || [];
      const listEl = $(`mealItems-${mt}`);
      const calEl = $(`mealCal-${mt}`);

      let mealCal = 0;
      if (!items.length) {
        listEl.innerHTML = `<div class="text-center py-6 text-slate-400 text-xs">No food logged yet</div>`;
      } else {
        listEl.innerHTML = items
          .map((scan) => {
            const nut = scan.nutrition || {};
            const foodName = scan.detected_foods?.[0]?.name || "Food Item";
            const qty = scan.detected_foods?.[0]?.quantity || "1 serving";
            mealCal += nut.calories_kcal || 0;

            return `
              <div class="bg-white rounded-xl p-3 border border-slate-200/80 shadow-xs flex flex-col gap-2">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <h4 class="text-xs font-bold text-slate-900 leading-tight">${escapeHtml(foodName)}</h4>
                    <p class="text-[10px] text-slate-500">${escapeHtml(qty)} • ${(nut.calories_kcal || 0)} kcal</p>
                  </div>
                  <button onclick="NutritionApp.deleteFoodScan('${scan.id}')" title="Remove" class="text-slate-400 hover:text-red-500 p-1">
                    <span class="material-symbols-outlined text-[16px]">delete</span>
                  </button>
                </div>
                <div class="flex items-center gap-2 text-[10px] font-semibold text-slate-500 pt-1 border-t border-slate-100">
                  <span class="text-blue-600">P: ${Math.round(nut.protein_g || 0)}g</span>
                  <span class="text-emerald-600">C: ${Math.round(nut.carbs_g || 0)}g</span>
                  <span class="text-purple-600">F: ${Math.round(nut.fat_g || 0)}g</span>
                  ${nut.fiber_g ? `<span class="text-amber-600">Fib: ${Math.round(nut.fiber_g)}g</span>` : ""}
                </div>
              </div>
            `;
          })
          .join("");
      }
      calEl.textContent = `${mealCal} kcal`;
    });
  }

  function renderFoodQuality(fq) {
    if (!fq) return;
    const nd = fq.nutrient_dense_percentage || 0;
    const occ = fq.occasional_percentage || 0;

    $("qualityNutrientDensePct").textContent = `${nd}%`;
    $("qualityNutrientDenseBar").style.width = `${nd}%`;

    $("qualityOccasionalPct").textContent = `${occ}%`;
    $("qualityOccasionalBar").style.width = `${occ}%`;
  }

  function renderInsight(insight) {
    if (!insight) return;
    $("insightSummaryText").textContent = insight.summary || "Start logging meals to view your dynamic AI insight.";

    const obsList = $("insightObservationsList");
    obsList.innerHTML = (insight.observations || ["No activity or meal records yet today."])
      .map((o) => `<li>${escapeHtml(o)}</li>`)
      .join("");
  }

  function renderActivitySuggestion(act) {
    if (!act) return;
    $("activityRecentFoodHeading").textContent = act.headline || "Recently recorded food";
    $("activityPromptText").textContent = act.prompt || "Want to add some activity today?";

    const ex = act.suggested_exercise || { id: "squat", name: "Squats", routine: "3 sets × 15 reps" };
    $("suggestedExName").textContent = ex.name;
    $("suggestedExRoutine").textContent = ex.routine;
    $("startWorkoutBtn").href = ex.start_url || `/workout?exercise=${ex.id}`;
  }

  let macroChart = null;

  function parseYMD(iso) {
    if (!iso) return null;
    const parts = String(iso).split("-");
    if (parts.length === 3) {
      return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    }
    return new Date(iso);
  }

  function fmtDate(iso) {
    const d = parseYMD(iso);
    if (!d || isNaN(d.getTime())) return iso || "--";
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function fmtDateFull(iso) {
    const d = parseYMD(iso);
    if (!d || isNaN(d.getTime())) return iso || "--";
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function renderTrendChart(history) {
    const canvas = $("macroTrendChart");
    const emptyEl = $("macroTrendEmpty");
    const sodiumValEl = $("macroSodiumTrendVal");
    if (!canvas) return;

    if (macroChart) {
      macroChart.destroy();
      macroChart = null;
    }

    if (!history || !history.length || history.every((h) => !(h.totals?.calories_kcal > 0))) {
      if (emptyEl) emptyEl.classList.remove("hidden");
      canvas.classList.add("opacity-0");
      if (sodiumValEl) sodiumValEl.textContent = "-- mg";
      return;
    }

    if (emptyEl) emptyEl.classList.add("hidden");
    canvas.classList.remove("opacity-0");

    // Labels with real calendar dates
    const labels = history.map((h) => fmtDate(h.date));
    const fullDates = history.map((h) => fmtDateFull(h.date));

    // Daily macros in grams
    const proteinData = history.map((h) => Math.round(h.totals?.protein_g || 0));
    const carbsData = history.map((h) => Math.round(h.totals?.carbs_g || 0));
    const fatData = history.map((h) => Math.round(h.totals?.fat_g || 0));
    const fiberData = history.map((h) => Math.round(h.totals?.fiber_g || 0));
    const sugarData = history.map((h) => Math.round(h.totals?.sugar_g || 0));
    const sodiumData = history.map((h) => Math.round(h.totals?.sodium_mg || 0));

    // Update dedicated sodium metric with latest day or average
    if (sodiumValEl) {
      const validSodium = sodiumData.filter((s) => s > 0);
      const latestSodium = sodiumData[sodiumData.length - 1] || (validSodium.length ? Math.round(validSodium.reduce((a, b) => a + b, 0) / validSodium.length) : 0);
      sodiumValEl.textContent = latestSodium > 0 ? `${latestSodium.toLocaleString()} mg` : "-- mg";
    }

    const ctx = canvas.getContext("2d");
    macroChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Protein (g)",
            data: proteinData,
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.08)",
            borderWidth: 2.5,
            pointBackgroundColor: "#2563eb",
            pointRadius: 3.5,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: false,
          },
          {
            label: "Carbs (g)",
            data: carbsData,
            borderColor: "#16a34a",
            backgroundColor: "rgba(22, 163, 74, 0.08)",
            borderWidth: 2.5,
            pointBackgroundColor: "#16a34a",
            pointRadius: 3.5,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: false,
          },
          {
            label: "Fat (g)",
            data: fatData,
            borderColor: "#9333ea",
            backgroundColor: "rgba(147, 51, 234, 0.08)",
            borderWidth: 2.5,
            pointBackgroundColor: "#9333ea",
            pointRadius: 3.5,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: false,
          },
          {
            label: "Fiber (g)",
            data: fiberData,
            borderColor: "#0d9488",
            backgroundColor: "rgba(13, 148, 136, 0.08)",
            borderWidth: 2,
            borderDash: [4, 4],
            pointBackgroundColor: "#0d9488",
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.3,
            fill: false,
          },
          {
            label: "Sugar (g)",
            data: sugarData,
            borderColor: "#ea580c",
            backgroundColor: "rgba(234, 88, 12, 0.08)",
            borderWidth: 2,
            borderDash: [2, 2],
            pointBackgroundColor: "#ea580c",
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.3,
            fill: false,
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
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: "#0f172a",
            titleColor: "#ffffff",
            bodyColor: "#f1f5f9",
            borderColor: "#334155",
            borderWidth: 1,
            padding: 10,
            cornerRadius: 10,
            callbacks: {
              title: function (items) {
                const idx = items[0].dataIndex;
                return fullDates[idx] || items[0].label;
              },
              afterBody: function (items) {
                const idx = items[0].dataIndex;
                const sod = sodiumData[idx] || 0;
                return `Sodium: ${sod.toLocaleString()}mg`;
              },
              label: function (item) {
                return `${item.dataset.label.split(" ")[0]}: ${item.raw}g`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              font: { size: 11, weight: "600" },
              color: "#64748b",
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "#f1f5f9" },
            ticks: {
              font: { size: 10 },
              color: "#64748b",
              callback: (val) => `${val}g`,
            },
          },
        },
      },
    });
  }

  // ── SCANNER & CAMERA HANDLING ───────────────────────────────────────

  function openScannerModal(mode = "camera", mealType = "lunch") {
    state.targetMealType = mealType;
    state.activePortionQty = 1;
    $("mealTypeSelect").value = mealType;
    $("scannerModal").classList.remove("hidden");
    $("detectionCard").classList.add("hidden");
    $("candidateSelectionCard")?.classList.add("hidden");
    $("manualSearchSection").classList.add("hidden");
    $("manualEntrySection").classList.add("hidden");

    if (mode === "manual") {
      openManualSection();
    } else if (mode === "camera") {
      startCamera();
    }
  }

  function closeScannerModal() {
    stopCamera();
    $("scannerModal").classList.add("hidden");
    $("detectionCard").classList.add("hidden");
    $("candidateSelectionCard")?.classList.add("hidden");
    $("manualEntrySection").classList.add("hidden");
    manualStatus("");
  }

  async function startCamera() {
    $("cameraPlaceholder").classList.add("hidden");
    $("imagePreview").classList.add("hidden");
    $("cameraVideo").classList.remove("hidden");
    $("startCamBtn").classList.add("hidden");
    $("captureCamBtn").classList.remove("hidden");
    $("retakeCamBtn").classList.add("hidden");

    try {
      state.cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
      const video = $("cameraVideo");
      video.srcObject = state.cameraStream;
      await video.play();
    } catch (err) {
      console.warn("Camera access denied or unavailable:", err);
      alert("Camera could not be accessed. Please choose a file instead.");
      stopCamera();
    }
  }

  function stopCamera() {
    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach((t) => t.stop());
      state.cameraStream = null;
    }
    $("cameraVideo").classList.add("hidden");
    $("cameraPlaceholder").classList.remove("hidden");
    $("startCamBtn").classList.remove("hidden");
    $("captureCamBtn").classList.add("hidden");
  }

  function captureSnapshot() {
    const video = $("cameraVideo");
    const canvas = $("captureCanvas");
    if (!video || !video.videoWidth) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const b64Data = canvas.toDataURL("image/jpeg", 0.85);

    // Freeze view
    stopCamera();
    $("cameraPlaceholder").classList.add("hidden");
    const preview = $("imagePreview");
    preview.src = b64Data;
    preview.classList.remove("hidden");
    $("retakeCamBtn").classList.remove("hidden");

    analyzeImageBase64(b64Data);
  }

  function retakePhoto() {
    $("imagePreview").classList.add("hidden");
    $("detectionCard").classList.add("hidden");
    startCamera();
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    openScannerModal("upload", state.targetMealType);
    stopCamera();

    const reader = new FileReader();
    reader.onload = function (event) {
      const b64Data = event.target.result;
      const preview = $("imagePreview");
      preview.src = b64Data;
      preview.classList.remove("hidden");
      $("cameraPlaceholder").classList.add("hidden");
      analyzeImageBase64(b64Data);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  async function analyzeImageBase64(b64String) {
    $("analyzingOverlay").classList.remove("hidden");
    $("startCamBtn").disabled = true;
    $("pickFileModalBtn").disabled = true;
    $("detectionCard").classList.add("hidden");
    const candCard = $("candidateSelectionCard");
    if (candCard) candCard.classList.add("hidden");

    try {
      const res = await nutFetch("/api/nutrition/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: b64String,
          meal_type: state.targetMealType,
        }),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || "Food analysis failed");

      const data = json.data || json;
      state.currentScan = data;

      // Render Developer Vision Debug Panel if debug trace is present (Requirement 35)
      if (data.debug) {
        renderDevDebug(data.debug, data);
      }

      // Check for uncertainty / needs confirmation (Requirements 13 & 27)
      if (data.status === "needs_confirmation" || data.requires_confirmation) {
        renderCandidatesChoice(data);
      } else {
        displayDetectionResult(data);
      }
    } catch (err) {
      console.error("Food vision error:", err);
      alert("We couldn't analyze this image. You can try again or enter food manually.");
      $("manualSearchSection").classList.remove("hidden");
    } finally {
      $("analyzingOverlay").classList.add("hidden");
      $("startCamBtn").disabled = false;
      $("pickFileModalBtn").disabled = false;
    }
  }

  function renderCandidatesChoice(data) {
    $("detectionCard").classList.add("hidden");
    const container = $("candidateSelectionCard");
    const list = $("candidateButtonsList");
    if (!container || !list) return;

    const candidates = data.candidates || [];
    if (!candidates.length) {
      list.innerHTML = `<p class="text-xs text-amber-800 italic">No clear food candidate detected. Please scan again or enter manually.</p>`;
    } else {
      list.innerHTML = candidates.map((c) => {
        const scorePct = Math.round((c.visual_score || c.score || 0.5) * 100);
        const reason = c.visual_reason || (c.supporting_evidence ? c.supporting_evidence.slice(0, 2).join(", ") : "");
        return `
          <button type="button" onclick="NutritionApp.selectCandidateByName('${escapeHtml(c.name)}')" 
                  class="w-full text-left p-3.5 rounded-xl bg-white hover:bg-amber-100/70 border border-amber-300 shadow-xs flex items-center justify-between transition-all active:scale-[0.99] group">
            <div class="flex-1 pr-3">
              <div class="flex items-center gap-2">
                <span class="text-sm font-black text-slate-900 group-hover:text-amber-900">${escapeHtml(c.name)}</span>
                <span class="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-bold">${scorePct}% match</span>
              </div>
              ${reason ? `<p class="text-[11px] text-slate-500 mt-1 line-clamp-1">${escapeHtml(reason)}</p>` : ""}
            </div>
            <span class="material-symbols-outlined text-amber-700 text-[20px] group-hover:translate-x-1 transition-transform">arrow_forward</span>
          </button>
        `;
      }).join("");
    }

    container.classList.remove("hidden");
  }

  function applyFoodSelection(food) {
    if (!food) return;
    const qty = food.default_serving_qty || 1;
    const base = food.per_unit || {};

    state.activePortionQty = qty;
    state.currentScan = {
      source: "curated_catalog",
      confidence: 0.95,
      confidence_message: `Confirmed as ${food.name} from authentic food database.`,
      food: {
        canonical_id: food.id,
        id: food.id,
        name: food.name,
      },
      detected_foods: [
        {
          id: food.id,
          name: food.name,
          quantity: `${qty} ${food.serving_unit || "serving"}`,
          serving_qty: qty,
          serving_unit: food.serving_unit || "serving",
          estimated_weight_g: food.estimated_weight_g,
        },
      ],
      nutrition: {
        calories_kcal: Math.round((base.calories_kcal || 0) * qty),
        protein_g: Math.round((base.protein_g || 0) * qty * 10) / 10,
        carbs_g: Math.round((base.carbs_g || 0) * qty * 10) / 10,
        fat_g: Math.round((base.fat_g || 0) * qty * 10) / 10,
        fiber_g: Math.round((base.fiber_g || 0) * qty * 10) / 10,
        sugar_g: Math.round((base.sugar_g || 0) * qty * 10) / 10,
        sodium_mg: Math.round((base.sodium_mg || 0) * qty),
        serving_qty: qty,
      },
      food_quality: food.food_quality || { classification: "nutrient_dense" },
    };

    const candCard = $("candidateSelectionCard");
    if (candCard) candCard.classList.add("hidden");
    const manualSearch = $("manualSearchSection");
    if (manualSearch) manualSearch.classList.add("hidden");

    displayDetectionResult(state.currentScan);
  }

  async function selectCandidateByName(foodName) {
    const candCard = $("candidateSelectionCard");
    if (candCard) candCard.classList.add("hidden");
    $("analyzingOverlay").classList.remove("hidden");
    try {
      // Lookup canonical food details
      const res = await nutFetch(`/api/nutrition/search?q=${encodeURIComponent(foodName)}`);
      const json = await res.json();
      let matched = (json.data || []).find(
        (f) => f.name.toLowerCase() === foodName.toLowerCase() ||
               (f.aliases && f.aliases.some((a) => a.toLowerCase() === foodName.toLowerCase())) ||
               (f.id && f.id.toLowerCase() === foodName.toLowerCase().replace(/\s+/g, "_"))
      );
      if (!matched && json.data && json.data.length > 0) {
        matched = json.data[0];
      }

      if (matched) {
        applyFoodSelection(matched);
      } else {
        // Build confirmed candidate state
        state.currentScan = {
          source: "visual_estimate",
          confidence: 0.85,
          confidence_message: `Estimated as ${foodName}.`,
          food: { name: foodName },
          detected_foods: [{
            name: foodName,
            quantity: "1 serving",
            serving_qty: 1.0,
            serving_unit: "serving",
            confidence: 0.85,
          }],
          nutrition: {
            calories_kcal: 310,
            protein_g: 25.0,
            carbs_g: 15.0,
            fat_g: 12.0,
            fiber_g: 2.0,
            sugar_g: 3.0,
            sodium_mg: 500,
          },
          food_quality: { classification: "nutrient_dense" },
        };
        displayDetectionResult(state.currentScan);
      }
    } catch (err) {
      console.error("Candidate selection error:", err);
    } finally {
      $("analyzingOverlay").classList.add("hidden");
    }
  }

  function renderDevDebug(dbg, rootData) {
    const qEl = $("debugImageQuality");
    const stEl = $("debugConfidenceState");
    const finEl = $("debugFinalCandidate");
    const srcEl = $("debugNutritionSource");
    const listEl = $("debugCandidatesList");

    if (qEl) qEl.textContent = dbg.image_quality?.score ? `${Math.round(dbg.image_quality.score * 100)}% (variance: ${Math.round(dbg.image_quality.variance || 0)})` : "Clear";
    if (stEl) {
      stEl.textContent = (dbg.confidence_state || rootData.recognition?.state || "HIGH").toUpperCase();
      stEl.className = (dbg.confidence_state === "needs_confirmation") ? "text-rose-400 font-bold ml-1" : "text-emerald-400 font-bold ml-1";
    }
    if (finEl) finEl.textContent = dbg.final_candidate || rootData.food?.name || "None";
    if (srcEl) srcEl.textContent = rootData.nutrition_source || dbg.nutrition_source || "food_database";

    if (listEl && dbg.candidates_ranked) {
      listEl.innerHTML = dbg.candidates_ranked.map((c, i) => `
        <div class="p-2 rounded bg-slate-800 border border-slate-700">
          <div class="flex items-center justify-between text-slate-200 font-bold text-xs">
            <span>#${i + 1} ${escapeHtml(c.name)}</span>
            <span class="text-amber-400 font-mono">${c.score !== undefined ? c.score.toFixed(2) : (c.visual_score || 0)}</span>
          </div>
          ${c.evidence && c.evidence.length ? `
            <div class="mt-1 text-[10px] space-y-0.5">
              ${c.evidence.map((ev) => `<div class="${ev.startsWith('+') ? 'text-emerald-400' : 'text-rose-400'}">${escapeHtml(ev)}</div>`).join("")}
            </div>
          ` : ""}
        </div>
      `).join("");
    }
  }

  function displayDetectionResult(data) {
    const candCard = $("candidateSelectionCard");
    if (candCard) candCard.classList.add("hidden");

    const food = data.detected_foods?.[0] || data.food || {};
    const nut = data.nutrition || {};
    const fq = data.food_quality || {};

    const foodName = data.food?.name || food.name || "Identified Food";
    $("detectedFoodName").textContent = foodName;

    // Confidence badge and state (Requirements 11, 12, 38)
    const confState = data.recognition?.state || (data.confidence >= 0.75 ? "high" : "medium");
    const badge = $("detectedConfidenceBadge");
    if (badge) {
      if (confState === "high") {
        badge.textContent = "● HIGH CONFIDENCE";
        badge.className = "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-black uppercase tracking-wider";
      } else {
        badge.textContent = "● MEDIUM CONFIDENCE";
        badge.className = "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-black uppercase tracking-wider";
      }
    }

    // Portion description (Requirement 20)
    const portionDesc = data.portion?.description || food.quantity || "1 piece";
    const portionEl = $("detectedPortionDesc");
    if (portionEl) {
      portionEl.textContent = `Estimated portion: ${portionDesc}`;
    }

    // Nutrition Source (Requirement 17)
    const srcEl = $("detectedNutritionSource");
    if (srcEl) {
      const srcText = data.nutrition_source === "food_database" ? "Food Database" :
                      data.nutrition_source === "open_food_facts" ? "Open Food Facts" : "AI Estimated";
      srcEl.textContent = srcText;
    }

    $("detectedConfidenceMsg").textContent = data.confidence_message || "Verified against PoseAI nutrition database.";

    // Estimated weight badge
    const weightBadge = $("detectedWeightBadge");
    if (weightBadge) {
      const w = data.portion?.estimated_weight_g || food.estimated_weight_g || 140;
      weightBadge.textContent = `≈ ${Math.round(w)}g`;
    }

    // Plate items breakdown
    const itemsSec = $("detectedItemsSection");
    const itemsList = $("detectedItemsList");
    if (itemsSec && itemsList) {
      if (food.items && food.items.length) {
        itemsList.innerHTML = food.items.map((it) => `
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-[11px] font-bold text-slate-700 shadow-2xs">
            <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            ${escapeHtml(it.name)}
            ${it.score ? `<span class="text-slate-400 font-normal">(${Math.round(it.score * 100)}%)</span>` : ""}
          </span>
        `).join("");
        itemsSec.classList.remove("hidden");
      } else {
        itemsSec.classList.add("hidden");
      }
    }

    const qClass = fq.classification === "occasional" ? "Occasional" : "Nutrient-dense";
    $("detectedQualityBadge").textContent = qClass;
    $("detectedQualityBadge").className =
      fq.classification === "occasional"
        ? "px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 text-xs font-bold"
        : "px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold";

    const initialQty = data.portion?.serving_qty || food.serving_qty || 1;
    // Store 1-unit base nutrition to avoid compounding multiplier issues
    state.currentScan.base_nutrition = {
      calories_kcal: (nut.calories_kcal || 0) / initialQty,
      protein_g: (nut.protein_g || 0) / initialQty,
      carbs_g: (nut.carbs_g || 0) / initialQty,
      fat_g: (nut.fat_g || 0) / initialQty,
      fiber_g: (nut.fiber_g || 0) / initialQty,
      sugar_g: (nut.sugar_g || 0) / initialQty,
      sodium_mg: (nut.sodium_mg || 0) / initialQty,
      estimated_weight_g: (data.portion?.estimated_weight_g || food.estimated_weight_g || 140) / initialQty,
    };

    setPortion(initialQty);
    $("portionUnitLabel").textContent = data.portion?.serving_unit || food.serving_unit || "piece";

    updateMacroDisplay(nut);
    $("detectionCard").classList.remove("hidden");
  }

  function setPortion(qty) {
    state.activePortionQty = Math.max(0.2, Math.round(qty * 10) / 10);
    $("portionInput").value = state.activePortionQty;

    if (state.currentScan?.base_nutrition) {
      const base = state.currentScan.base_nutrition;
      const factor = state.activePortionQty;
      const scaled = {
        calories_kcal: Math.round((base.calories_kcal || 0) * factor),
        protein_g: Math.round((base.protein_g || 0) * factor * 10) / 10,
        carbs_g: Math.round((base.carbs_g || 0) * factor * 10) / 10,
        fat_g: Math.round((base.fat_g || 0) * factor * 10) / 10,
        fiber_g: Math.round((base.fiber_g || 0) * factor * 10) / 10,
        sugar_g: Math.round((base.sugar_g || 0) * factor * 10) / 10,
        sodium_mg: Math.round((base.sodium_mg || 0) * factor),
        serving_qty: state.activePortionQty,
      };
      state.currentScan.nutrition = scaled;
      updateMacroDisplay(scaled);

      const weightBadge = $("detectedWeightBadge");
      if (weightBadge && base.estimated_weight_g) {
        weightBadge.textContent = `≈ ${Math.round(base.estimated_weight_g * factor)}g`;
      }
    }
  }

  function adjustPortion(delta) {
    setPortion(state.activePortionQty + delta);
  }

  function updateMacroDisplay(nut) {
    $("detCal").textContent = Math.round(nut.calories_kcal || 0);
    $("detProt").textContent = `${Math.round(nut.protein_g || 0)}g`;
    $("detCarb").textContent = `${Math.round(nut.carbs_g || 0)}g`;
    $("detFat").textContent = `${Math.round(nut.fat_g || 0)}g`;
    if ($("detFiber")) $("detFiber").textContent = `${Math.round(nut.fiber_g || 0)}g`;
  }

  // ── MANUAL NUTRITION ENTRY ───────────────────────────────────────────

  function openManualEntry() {
    openScannerModal("manual", $("mealTypeSelect").value || "lunch");
    $("manualMealType").value = $("mealTypeSelect").value || "lunch";
    $("manualFoodName").focus();
  }

  function openManualSection() {
    $("manualEntrySection").classList.remove("hidden");
    loadMyFoods();
  }

  function manualStatus(message, isError = false) {
    const el = $("manualStatus");
    if (!message) {
      el.textContent = "";
      el.className = "hidden text-[11px] font-semibold rounded-xl px-3 py-2";
      return;
    }
    el.textContent = message;
    el.className = isError
      ? "text-[11px] font-semibold rounded-xl px-3 py-2 bg-red-50 text-red-700 border border-red-200"
      : "text-[11px] font-semibold rounded-xl px-3 py-2 bg-emerald-50 text-emerald-700 border border-emerald-200";
  }

  async function saveManualEntry() {
    const num = (id) => {
      const v = parseFloat($(id).value);
      return isNaN(v) ? 0 : v;
    };
    const foodName = $("manualFoodName").value.trim();

    if (!foodName) {
      manualStatus("Please enter a food name.", true);
      return;
    }

    const payload = {
      food_name: foodName,
      meal_type: $("manualMealType").value,
      nutrition: {
        calories_kcal: num("manualCal"),
        protein_g: num("manualProt"),
        carbs_g: num("manualCarb"),
        fat_g: num("manualFat"),
        fiber_g: num("manualFiber"),
        sugar_g: num("manualSugar"),
        sodium_mg: num("manualSodium"),
      },
      portion: {
        amount: num("manualPortionAmount") || 100,
        unit: $("manualPortionUnit").value,
      },
      save_to_library: $("manualSaveToLibrary").checked,
    };

    $("manualSaveBtn").disabled = true;
    manualStatus("");

    try {
      const res = await nutFetch("/api/nutrition/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();

      if (!res.ok || !json.success) {
        // Surface the exact rejected fields from NutritionValidator.
        const details = (json.validation_errors || []).join(" • ");
        manualStatus(details || json.error || "Could not save food.", true);
        return;
      }

      resetManualForm();
      closeScannerModal();
      await loadTodayData();
      await loadTrends(state.trendDays);
    } catch (err) {
      manualStatus("Could not save food: " + err.message, true);
    } finally {
      $("manualSaveBtn").disabled = false;
    }
  }

  function resetManualForm() {
    $("manualFoodName").value = "";
    ["manualCal", "manualProt", "manualCarb", "manualFat",
     "manualFiber", "manualSugar", "manualSodium"].forEach((id) => {
      $(id).value = "0";
    });
    $("manualPortionAmount").value = "100";
  }

  // ── SAVED CUSTOM FOODS ("My Foods") ─────────────────────────────────

  async function loadMyFoods() {
    try {
      const res = await nutFetch("/api/nutrition/my-foods");
      const json = await res.json();
      if (!json.success) throw new Error(json.error || "Could not load saved foods");
      renderMyFoods(json.data || []);
    } catch (err) {
      console.error("Saved foods error:", err);
    }
  }

  function renderMyFoods(foods) {
    state.myFoods = foods;
    const row = $("myFoodsRow");
    const chips = $("myFoodsChips");

    if (!foods.length) {
      chips.innerHTML = "";
      row.classList.add("hidden");
      return;
    }

    chips.innerHTML = foods
      .map(
        (f) => `
        <span class="inline-flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-full bg-white border border-blue-200">
          <button type="button" onclick="NutritionApp.applyMyFood('${f.id}')" class="text-[11px] font-bold text-blue-800 hover:text-blue-950 transition-colors">${escapeHtml(f.name)}</button>
          <button type="button" onclick="NutritionApp.deleteMyFood('${f.id}')" title="Remove saved food" class="w-4 h-4 rounded-full bg-blue-50 hover:bg-red-100 text-blue-500 hover:text-red-600 text-[11px] leading-none font-black transition-colors">&times;</button>
        </span>
      `
      )
      .join("");

    row.classList.remove("hidden");
  }

  function applyMyFood(foodId) {
    const food = state.myFoods.find((f) => f.id === foodId);
    if (!food) return;

    const nut = food.nutrition || {};
    $("manualFoodName").value = food.name || "";
    $("manualCal").value = Math.round(nut.calories_kcal || 0);
    $("manualProt").value = nut.protein_g || 0;
    $("manualCarb").value = nut.carbs_g || 0;
    $("manualFat").value = nut.fat_g || 0;
    $("manualFiber").value = nut.fiber_g || 0;
    $("manualSugar").value = nut.sugar_g || 0;
    $("manualSodium").value = Math.round(nut.sodium_mg || 0);

    const portion = food.portion || {};
    $("manualPortionAmount").value = portion.amount || 100;
    if (portion.unit) $("manualPortionUnit").value = portion.unit;

    manualStatus(`Loaded "${food.name}" — review and tap SAVE FOOD.`);
  }

  async function deleteMyFood(foodId) {
    try {
      const res = await nutFetch(`/api/nutrition/my-foods/${foodId}`, {
        method: "DELETE",
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || "Could not remove saved food");
      await loadMyFoods();
    } catch (err) {
      manualStatus(err.message, true);
    }
  }

  async function confirmCurrentScan() {
    if (!state.currentScan) return;

    const btn = $("confirmLogBtn");
    if (btn && btn.disabled) return;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "ADDING...";
    }

    const chosenMeal = $("mealTypeSelect").value;
    const nut = state.currentScan.nutrition || {};
    const firstFood = state.currentScan.detected_foods?.[0] || state.currentScan.food || {};

    const payload = {
      meal_type: chosenMeal,
      canonical_id: state.currentScan.food?.canonical_id || firstFood.id,
      food_name: state.currentScan.food?.name || firstFood.name,
      detected_foods: [
        {
          id: state.currentScan.food?.canonical_id || firstFood.id || "food_item",
          name: state.currentScan.food?.name || firstFood.name || "Food Item",
          quantity: `${state.activePortionQty} ${firstFood.serving_unit || "piece"}`,
          serving_qty: state.activePortionQty,
          estimated_weight_g: firstFood.estimated_weight_g ? Math.round(firstFood.estimated_weight_g * state.activePortionQty) : null,
          confidence: state.currentScan.confidence || 0.95,
          items: firstFood.items || [],
        },
      ],
      nutrition: nut,
      food_quality: state.currentScan.food_quality,
      source: state.currentScan.nutrition_source || state.currentScan.source || "food_database",
      confidence: state.currentScan.confidence || 0.95,
    };

    try {
      const res = await nutFetch("/api/nutrition/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || "Save failed");

      closeScannerModal();
      await loadTodayData();
      await loadTrends(state.trendDays);
    } catch (err) {
      alert("Could not log food: " + err.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "ADD TO TODAY";
      }
    }
  }

  async function performFoodSearch() {
    const q = $("foodSearchInput").value.trim();
    if (!q) return;

    try {
      const res = await nutFetch(`/api/nutrition/search?q=${encodeURIComponent(q)}`);
      const json = await res.json();
      const list = $("searchResultsList");

      if (!json.success || !json.data?.length) {
        list.innerHTML = `<p class="text-xs text-slate-500 py-2">No matching foods found in catalog.</p>`;
        return;
      }

      list.innerHTML = json.data
        .map(
          (f) => `
          <button type="button" onclick="NutritionApp.selectCatalogFood('${f.id}')" class="w-full text-left p-2.5 rounded-xl bg-white hover:bg-slate-100 border border-slate-200 flex items-center justify-between transition-colors">
            <div>
              <p class="text-xs font-bold text-slate-800">${escapeHtml(f.name)}</p>
              <p class="text-[10px] text-slate-500">${f.per_unit?.calories_kcal} kcal per ${f.serving_unit}</p>
            </div>
            <span class="text-xs font-bold text-blue-600">Select</span>
          </button>
        `
        )
        .join("");
    } catch (err) {
      console.error("Food search error:", err);
    }
  }

  async function selectCatalogFood(foodId) {
    try {
      const res = await nutFetch(`/api/nutrition/search?q=${encodeURIComponent(foodId)}`);
      const json = await res.json();
      const food = json.data?.find((f) => f.id === foodId) || json.data?.[0];
      if (!food) return;
      applyFoodSelection(food);
    } catch (err) {
      console.error("Select food error:", err);
    }
  }

  async function deleteFoodScan(scanId) {
    if (!confirm("Are you sure you want to remove this food record from today?")) return;
    try {
      const res = await nutFetch(`/api/nutrition/scan/${scanId}`, {
        method: "DELETE",
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || "Could not remove item");

      await loadTodayData();
      await loadTrends(state.trendDays);
    } catch (err) {
      alert("Error: " + err.message);
    }
  }

  function escapeHtml(str) {
    return String(str || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Public API
  return {
    init,
    openAddModal: (meal) => openScannerModal("camera", meal),
    deleteFoodScan,
    selectCatalogFood,
    selectCandidateByName,
    openManualEntry,
    applyMyFood,
    deleteMyFood,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  NutritionApp.init();
});
