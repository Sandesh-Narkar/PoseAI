# Section 56 — Complete Codebase Inventory & Architectural Findings

**Project:** PoseAI — AI Fitness Trainer
**Date:** 2026-09-16
**Scope:** Every non-vendored file, verified by full read (EOF markers confirmed for
all source files). Line counts from `(Get-Content).Count`; bytes from filesystem.

> No secrets: `.env` values (Mongo URI, `FLASK_SECRET_KEY`, OAuth client id/secret)
> are intentionally omitted.

---

## 1. Why the frontend "discrepancy" exists (resolved)

Prior reports (SECTIONS 54/55) documented a `dashboard/` tree (index.html,
live-workout.html, js/api.js, js/dashboard.js, js/app.js, css/*, per-page stubs…).
`git status` now shows that entire `dashboard/` tree was **deleted** and replaced by
an untracked **`frontend/`** directory. So the reports were written against the now
removed layout; the current, authoritative layout is `frontend/`.

| Theme | Old (reports) | Current (repo) |
|---|---|---|
| Root | `dashboard/` | `frontend/` |
| Pages | `dashboard/index.html`, per-page .html | `frontend/html/index.html` + per-page .html |
| JS | `dashboard/js/*` | `frontend/js/*` |
| Persistence | SQLite `instance/poseai.db` (SEC 54) | **MongoDB Atlas** `poseai` DB (SEC 55) + current code |
| Auth | Flask session | Flask session (cookie) + Argon2id + Google OAuth |

Currently-functional pages by full read: `index.html` (1067), `live-workout.html`
(889, Tailwind static mockup w/ hardcoded "Sandesh"/"BICEP CURL", sim-only JS),
`login.html` (464), `signup.html` (567). `progress/analysis/profile/achievements.html`
are 12-line stubs. CSS: only `style.css` (1423) and `auth.css` (981) are real;
the other 10 css files are 0-byte placeholders.

---

## 2. File inventory

### Root
| Path | Lines | Bytes | Role |
|---|---|---|---|
| `app.py` | 1295 | 52623 | Flask API, `dashboard_state`, auth`, Mongo persistence, `/api/*` |
| `auth.py` | 849 | 33670 | Auth blueprint, Google OAuth, `/auth/providers` |
| `main.py` | 955 | 37891 | OpenCV/MediaPipe desktop engine, POST /api/update |
| `config.py` | 136 | 5924 | Config classes incl. `ProductionConfig` |
| `models.py` | 217 | 11210 | Mongo document model wrapper (`WUser`…), serializers |
| `README.md` | 1 | 8 | Empty placeholder |
| `requirements.txt` | 17 | 603 | Runtime deps |
| `requirements-dev.txt` | 6 | 213 | Dev deps |
| `.gitignore` | 10 | 117 | Ignores venv, .env, etc. |
| `.env` | 45 | 2105 | **Secrets — never print** |
| `.env.example` | 68 | 3735 | Documented env template |

### `core/` — engine internals
| Path | Lines | Bytes | Role |
|---|---|---|---|
| `pose_detector.py` | 118 | 5062 | MediaPipe `PoseLandmarker` wrapper |
| `camera.py` | 86 | 1859 | Webcam capture abstraction |
| `angle_calculator.py` | 47 | 771 | Static `calculate(p1,p2,p3)` angle helper |
| `landmark_manager.py` | 414 | 12648 | Landmark cache, joint mapping |
| `landmark_smoother.py` | 362 | 15717 | Denoising / EMA smoothing |
| `web_workout_engine.py` | 437 | 20231 | `WebWorkoutEngine` — browser-session engine |
| `exercise_data.py` | 231 | 8043 | Exercise definitions / metadata |
| `persistence.py` | 256 | 9332 | Session/achievement persistence helpers |
| `report.py` | 286 | 9617 | PDF (reportlab) + CSV builders |
| `ui_layout.py` | 1541 | 68754 | Layout/UI drawing; **1541 = stray string** |
| `drawing.py` | 936 | 40456 | Landmark/skeleton drawing |

### `database/`
| Path | Lines | Bytes | Role |
|---|---|---|---|
| `__init__.py` | 7 | 216 | Module init |
| `mongo.py` | 377 | 13463 | Mongo connection + mongomock fallback |
| `workouts.py` | 645 | 24188 | Save/load workouts, totals, achievements |

### `workouts/` — 12 exercise modules + manager
| Path | Lines | Bytes | Type |
|---|---|---|---|
| `workout_manager.py` | 185 | 6433 | Registry/dispatch; keys: bicep, pushup, squat, triceps, lunges, jumpingjacks, shoulder_press, burpees, warrior2, goblet, toe_touch |
| `base_workout.py` | 42 | 727 | Base classe + shared helpers |
| `bicep.py` | 308 | 13338 | Rep counter |
| `pushup.py` | 311 | 13839 | Rep counter |
| `squat.py` | 396 | 16211 | Rep counter |
| `lunges.py` | 326 | 13513 | Stride + knee checks |
| `jumping_jacks.py` | 366 | 16138 | Sign-based (wrist vs shoulder) |
| `triceps_pushdown.py` | 325 | 12692 | Elbow angle cued |
| `shoulder_press.py` | 239 | 9141 | Angle cued |
| `burpees.py` | 349 | 13547 | 5-node state machine |
| `warrior2.py` | 169 | 7544 | Pose-hold timer (not rep) |
| `goblet_squat.py` | 396 | 16320 | Rep counter |
| `crossover_toe_touch.py` | 430 | 18472 | CENTER→RIGHT_CROSS→CENTER→LEFT_CROSS→CENTER |

All validate landmarks, reject jitter, use stability streaks + cooldowns; all call
`AngleCalculator` (none call `.calculate_angle` … except `drawing.py`).

### `frontend/`
| Path | Lines | Bytes | Role |
|---|---|---|---|
| `html/index.html` | 1067 | 77259 | Dashboard (Tailwind, hardcoded) |
| `html/live-workout.html` | 889 | 59547 | Live exercise page (mockup) |
| `html/login.html` | 464 | 20266 | Login |
| `html/signup.html` | 567 | 25220 | Signup |
| `html/{progress,analysis,profile,achievements}.html` | 12 each | ~200 each | **Stubs** |
| `js/dashboard.js` | 818 | 27429 | Dashboard wiring |
| `js/api.js` | 647 | 20846 | `PoseAIApi` client |
| `js/app.js` | 637 | 22297 | App bootstrap |
| `css/style.css` | 1423 | 33403 | Real styles |
| `css/auth.css` | 981 | 24214 | Real styles |
| `css/{variables,components,layout,sidebar,responsive,live-workout,analysis,progress,profile,achievements}.css` | 0 | 0 | **Empty placeholders** |

### `assets/` — exercise guide images (this session not fully re-read)
11 PNGs under `assets/exercise_guides/`, all double-extended `*.png.png`.

### `models/`
| Path | Bytes | Role |
|---|---|---|
| `models/pose_landmarker_full.task` | 9398198 | MediaPipe PoseLandmarker model |

### `Awwwards_level/` (51 PNGs)
`ezgif-frame-001…051.png` — design-reference screenshots of the target UI.

### `tests/`
| Path | Lines | Bytes | Role |
|---|---|---|---|
| `test_app.py` | 1314 | 53034 | API + persistence + engine tests |
| `test_auth_mongo.py` | 561 | 26274 | Auth/OAuth/mongo tests |
| `helpers.py` | 30 | 1028 | Shared test utilities (mongomock swap) |

### `reports/`
| Path | Lines | Bytes | Role |
|---|---|---|---|
| `SECTION_54_FINAL_REPORT.md` | 190 | 11982 | Streak-fix + SQLite-era report |
| `SECTION_55_FINAL_REPORT.md` | 295 | 16789 | Real-time/analysis/progress/report PDF |
| `GOOGLE_OAUTH_SETUP.md` | 115 | 5120 | OAuth setup guide |
| `SECTION_56_CODEBASE_INVENTORY.md` | — | — | This report |

Caches (excluded): `.pytest_cache/`, `venv/`, `__pycache__/`, `data/` (empty), `instance/`.

---

## 3. Confirmed code findings (to act on)

1. **`core/drawing.py:509`** calls `self.angle_calculator.calculate_angle(a, b, c)` —
   `AngleCalculator` only exposes `calculate(...)`. The `AttributeError` is swallowed
   by the `try/except`, so it silently falls back to local numpy math — a latent bug,
   not a crash. Workout modules never hit this path (they call `AngleCalculator.calculate`).
2. **`core/ui_layout.py:1541`** — orphaned stray string `""" bscitit9@gmail,com"""`
   after `_format_time()`'s return; unreachable leftover (mangled docstring).
3. **Frontend gap** — `index.html` and `live-workout.html` are hardcoded Tailwind
   mockups (container says "Sandesh", exercise "BICEP CURL", fake Google avatar URLs).
   The rendered dashboard/analysis/progress/profile/achievements experience described
   in SECTIONS 54/55 does **not** exist in `frontend/`; those four pages are 12-line stubs.
4. **Empty CSS** — 10 of 12 `frontend/css/*` files (all except `style.css`, `auth.css`)
   are 0-byte; any real page would load empty stylesheets.
5. **Missing pages** — nav references `workout.html` / `exercises.html`, neither exists
   in `frontend/html/` (only `live-workout.html` exists).
6. **`main.py` API bridge** — posts live snapshots to `POST /api/update`; on
   finish-with-key it also calls `/api/workout/finish` (X-API-Key auth, engine auto-save).
   Persistence is owned by `app.py` + `database/workouts.save_workout`.

---

## 4. Architecture (current)

```
main.py (desktop engine) ──live JSON──▶ POST /api/update ──▶ dashboard_state (memory)
        │  on finish: POST /api/workout/finish (X-API-Key)     │
        │                                                      │ /api/status (poll 500ms)
        ▼                                                      ▼
Browser ── Finish button ──▶ POST /api/workout/finish ──▶ save_workout ──▶ MongoDB (poseai)
                                                                 └─▶ /api/analysis, /api/progress,
                                                                     /api/statistics, /api/streak,
                                                                     /api/achievements, /api/report
```

MongoDB `poseai` DB: `users` (auth.py), `workout_sessions`, `user_stats`,
`user_achievements`. Tests swap the module DB handle with a fresh mongomock DB
(`tests/helpers.setup_mongo_mock`). `api.js` polls `/api/status` every 500 ms;
`credentials: "same-origin"` throughout.

Run: `python app.py` (Flask + pages on http://127.0.0.1:5000), then `python main.py`
(engine). Tests: `python -m unittest discover -s tests`.

---

## 5. Open questions / next candidate tasks (for the user to prioritize)

- Rebuild the 4 stub pages and `workout.html` to match the SEC 55 design?
- Make `style.css`/`auth.css` the single source and fill/remove the 10 empty CSS files?
- Fix `drawing.py:509` (`calculate_angle` → `calculate`) and remove `ui_layout.py:1541` stray string?
- Replace hardcoded Tailwind mockups with real bindings (the reports say this was done…
  but it isn't in `frontend/`)?
- Add a real local dev flow that doesn't require Atlas credentials?