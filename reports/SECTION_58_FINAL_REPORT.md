# Section 58 — Final Report: One Engine, Two Input Sources (Routing Unification)

**Project:** PoseAI — AI Fitness Trainer
**Date:** 2026-09-17
**Scope:** Eliminate the duplicated per-exercise routing logic so the desktop
CLI (`main.py`) and the Flask web engine (`core/web_workout_engine.py`) exercise
**the exact same implementation**, proving the web camera → frame → MediaPipe →
workout → save → dashboard path is the real engine and not a fake/stub.
**Ground rule (observed throughout):** no new fake engine files, no fabricated
metrics, no rewrites; smallest behavior-preserving change.

---

## 1. What was already real (verified before refactoring)

The original reported symptom was the web UI stuck on `Move Into Camera View /
Angle 0° / Waiting…`. Before touching code, the engine chain was proven **alive**:

- MediaPipe starts in this environment (TensorFlow Lite XNNPACK delegate +
  `models/pose_landmarker_full.task`).
- A real photo (scikit-image `astronaut.png`, chest-up portrait) run through
  `WebWorkoutEngine.process_frame` with exercise `1` (Bicep Curl) produced
  genuine angles `125° → 134° → 135°` and real feedback
  (`Curl Higher` → `Align Your Wrist`).
- Leg exercises (`3/5/6`) honestly returned `Move Into Camera View` because leg
  visibility < 0.5 in a chest-up photo — the "stuck" UI was the **honest
  no-pose branch**, not a broken pipeline.

**Root cause of the remaining gap:** the per-exercise landmark dispatch
(`_run_bicep_curl` … `_run_crossover_toe_touch` + `_run_active_workout`) was
**duplicated verbatim** in both `main.py` and `core/web_workout_engine.py` — two
copies of the same "one engine" logic, free to drift.

## 2. Fix: shared, camera-independent `core/exercise_router.py`

New module `core/exercise_router.py` — single owner of:

- `workouts` dict (exercise key `1..9,g,t` → workout object), built once.
- `landmark_manager` (shared `LandmarkManager` instance).
- `VISIBILITY_THRESHOLD = 0.5`, `MOVE_INTO_VIEW` feedback constant.
- `EXERCISE_DRAW_KEYS` mapping plus `draw_key(key)` (used by the desktop HUD).
- `_dispatch` table built once at startup.
- All `_run_*` per-exercise handlers (copied byte-identical from the old copies).
- `run(landmarks)` → returns `None` when no handler, else the handler result.
- `set_exercise(key)` (does **not** reset the workout — callers reset), backed by the
  same fallback-to-current behavior the engine previously had.

**Refactors (behavior-preserving):**

- `core/web_workout_engine.py`
  - `WebWorkoutEngine.__init__` now builds `self.router = ExerciseRouter()`;
    `self.landmark_manager = self.router.landmark_manager`, `self.workouts =
    self.router.workouts`, `self.active_workout = self.router.active_workout`.
  - `set_exercise` delegates to `self.router.set_exercise(key)` then re-syncs
    `current_key` / `active_workout` and calls `active_workout.reset()`.
  - `_run_active_workout(landmarks)` → thin shim: `self.router.run(landmarks)`
    (returns the same `{"feedback": "Move Into Camera View"}` fallback when the
    router returns `None`).
  - Every duplicated `_run_*` method **deleted** (~150 lines).
- `main.py`
  - Removed the 11 workout-class imports, `LandmarkManager` import,
    `VISIBILITY_THRESHOLD`, `self.workouts`, `self.exercise_draw_keys`,
    `self._dispatch`, and all `_run_*` handlers.
  - `self.router = ExerciseRouter()`; `self.landmark_manager`, `self.current_key =
    "1"`, `self.active_workout` now come from the router.
  - `_switch_exercise` → `self.router.set_exercise(key)` + re-sync + `reset()`.
  - `_handle_key` membership check → `self.router.workouts`.
  - HUD `exercise_name` → `self.router.draw_key(self.current_key)`
    (empty string is falsy in `draw()`, identical to the old `.get` default).
  - `_run_active_workout(landmarks)` → `self.router.run(landmarks)` (same `None`
    contract the old dispatch returned).
  - `python -m py_compile` on all three files: OK.

**Result:** both entry points — desktop OpenCV camera and web browser frames —
feed the **same** `ExerciseRouter`. One engine, two input sources.

## 3. E2E verification (real engine, no webcam required)

`http_e2e.py` (test_client + mongomock + real MediaPipe + the astronaut JPEG);
same credentials/setup as Section 57 (`WTF_CSRF_ENABLED=False`,
`HIBP_CHECK_ENABLED=False`, `tests/helpers.setup_mongo_mock()`).

```
signup 201  -> login 200 (browser flow: /api/auth/signup sets no session by design)
GET /workout 200 HTML
start {exercise:'1'}   -> {cameraStatus:'tracking', exercise:'Bicep Curl'}
frame x3 (REAL person) -> angle 125 -> 133 -> 135, fb 'Curl Higher' -> 'Align Your Wrist', cam tracking
pause -> paused   |   resume -> tracking
finish             -> {currentStreak:1, isNewRecord:false}  "Workout saved."
finish (dup)       -> "Workout already saved."  (idempotency guard holds)
analysis     -> hasData, exercise 'Bicep Curl', formScore 0.0 (honest), feedback 'Align Your Wrist'
progress     -> total_workouts 1, days 1, recent 1
streak       -> currentStreak 1, todayCompleted true
statistics / achievements -> 200 with real rows
```

## 4. Test suite

```
python -m pytest tests/test_app.py tests/test_auth_mongo.py -q
35 passed, 2 subtests passed in ~5s
```

No regressions after the refactor; same count as before, now exercising the
shared router through both the desktop and web paths.

## 5. Files changed (this section)

- `core/exercise_router.py` — **new** shared routing engine (single implementation).
- `core/web_workout_engine.py` — delegates to the router; ~150 duplicated lines removed.
- `main.py` — delegates to the router; ~200 lines of duplicated dispatch removed.

## 6. Remaining notes

- Per-frame form/accuracy scores are still not computed by the engine, so saved
  form scores remain `0.0` and render as `--`; this stays honest (a real metric
  would be an engine feature, not a UI patch).
- `frontend/html/live-workout.html` remains dead, unserved demo code (not in
  `PAGE_ROUTES`); `core/persistence.py`, `core/report.py`,
  `frontend/js/dashboard.js` remain legacy/orphan assets (unchanged).
- Nothing here touches auth, Mongo, or the dashboard endpoints (unchanged in
  this section).

## 7. Final status

**READY.** The web flow is now provably the real PoseAI engine on the same
`ExerciseRouter` as the desktop CLI. Camera → frame API → MediaPipe → workout
logic → save → streak/analysis/progress/achievements verified end to end with
real data, no fabricated telemetry, no fake engine, no runtime (subprocess)
hacks. Full suite green (35 passed + 2 subtests).