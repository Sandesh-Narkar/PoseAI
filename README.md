<div align="center">

# PoseAI — AI Fitness Trainer & Analytics Platform

**Real-time exercise tracking, repetition counting, posture feedback, and nutrition intelligence powered by Computer Vision and Generative AI.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose%20Landmarker-00897B?style=flat-square&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![Render](https://img.shields.io/badge/Render-Deployable-46E3B7?style=flat-square&logo=render&logoColor=white)](https://render.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

</div>

---

## Overview

**PoseAI** is a production-ready computer-vision fitness trainer, workout analytics dashboard, and nutrition scanner. It combines **MediaPipe's 33-landmark pose estimation** with custom 3-point joint-angle trigonometry to count repetitions, analyze biomechanical form, and provide real-time audio/visual posture feedback.

The platform includes:
- **Web & Desktop Engines**: "One engine, two input sources" architecture supporting both browser webcam streaming and high-FPS desktop OpenCV feeds.
- **Interactive Web Dashboard**: Analytics, streak tracking, workout history, and gamified achievement progression.
- **Fitness Market E-Commerce**: Integrated gear & nutrition marketplace with catalog filtering, cart state management, and checkout simulation.
- **AI Food Scanner**: Visual meal nutrition estimation powered by Gemini 2.5 Flash, barcode scanning, and USDA FoodData Central integration.
- **Production Hardening**: Production WSGI support via Gunicorn, Argon2id password hashing, HTTPS session cookie policies, security headers, rate limiting, and Render Blueprints.

---

## Architecture & Project Structure

```
Second_year/
├── app.py                      # Flask HTTP server & WSGI entry point (serves API & frontend)
├── main.py                     # Desktop OpenCV + MediaPipe pose detection engine
├── config.py                   # Centralized, environment-driven configuration
├── auth.py                     # Authentication Blueprint (Argon2id, Session cookies, Google OAuth)
├── dashboard_api.py            # User dashboard, analytics, workouts, and reporting endpoints
├── models.py                   # Data models, achievements, and schemas
├── Procfile                    # Production process definition for Gunicorn
├── render.yaml                 # Render Blueprint specification
├── requirements.txt            # Production Python dependencies
├── requirements-dev.txt        # Development and testing dependencies
├── .python-version             # Pinned Python runtime (3.11.9)
├── .env.example                # Template of all environment variables (safe placeholders)
├── .gitignore                  # Git exclusion rules for secrets, venv, bytecode, and logs
│
├── core/                       # Shared Computer Vision & Exercise Engine
│   ├── camera.py               # Webcam capture & resolution pipeline
│   ├── pose_detector.py        # MediaPipe Pose tracking integration
│   ├── exercise_router.py      # Exercise routing & normalization
│   ├── angle_calculator.py     # 3-point joint angle trigonometry
│   ├── landmark_smoother.py    # Exponential Moving Average jitter reduction
│   ├── web_workout_engine.py   # Headless workout engine for browser video frames
│   ├── session_manager.py      # Per-user engine instance registry
│   └── ui_layout.py            # Desktop OpenCV on-screen HUD layout
│
├── workouts/                   # 11 Exercise Form Evaluators
│   ├── bicep_curl.py, pushup.py, squat.py, shoulder_press.py, lunge.py,
│   ├── plank.py, jumping_jack.py, crunch.py, lateral_raise.py,
│   └── triceps_pushdown.py, burpees.py
│
├── database/                   # Data Access Layer
│   ├── mongo.py                # MongoDB Atlas connection & client management
│   └── workouts.py             # Workout history, statistics, and achievement persistence
│
├── market/                     # Fitness Market E-Commerce Blueprint
│   ├── routes.py               # Products, categories, cart, and order endpoints
│   ├── repository.py           # MongoDB store for product catalog & carts
│   ├── service.py              # Business logic & payment simulation
│   └── schemas.py              # Cart & checkout validation
│
├── nutrition/                  # AI Food Scanner & Nutrition Blueprint
│   ├── routes.py               # Nutrition recognition & lookup API endpoints
│   ├── gemini_vision.py        # Google Gemini 2.5 Flash food vision engine
│   ├── usda_db.py              # USDA FoodData Central API integration
│   ├── product_lookup.py       # Barcode scanner & offline product database
│   └── validator.py            # Nutrition label extraction validation
│
├── frontend/                   # Client-Side Application (Vanilla HTML/CSS/JS)
│   ├── html/                   # Responsive UI pages (index, workout, analysis, profile, etc.)
│   ├── css/                    # Custom themes, dark mode & layout stylesheets
│   ├── js/                     # Client application logic (api.js, shell.js, config.js)
│   └── images/                 # Static visual assets & product photography
│
└── tests/                      # Automated Test Suite (Pytest & Unittest)
```

---

## Local Development Setup

### 1. Prerequisites
- **Python 3.11.x** (3.11.9 recommended)
- **Git**
- Optional: MongoDB local instance or a free MongoDB Atlas cluster

### 2. Clone and Setup Environment
```bash
# Clone repository
git clone https://github.com/Sandesh-Narkar/PoseAI.git
cd PoseAI

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure Environment Variables
Copy the template to create your local `.env`:
```bash
cp .env.example .env
```
Fill in the parameters in `.env`. For offline local testing without MongoDB, you can set `MONGO_ALLOW_MOCK=1`. In production, a real MongoDB Atlas URI is mandatory.

### 4. Run the Application
```bash
# Start Flask backend web server (serves web UI on http://localhost:5000)
python app.py

# Optional: Run the desktop camera pose trainer in a separate terminal
python main.py
```

### 5. Run the Automated Tests
```bash
pytest
```

---

## Environment Variables Reference

Configure these in `.env` for local development and in the **Render Dashboard -> Environment Variables** for production.

| Variable | Required in Prod | Default / Value | Description |
| :--- | :---: | :--- | :--- |
| `APP_ENV` | Yes | `production` | Sets application mode (`production`, `development`, or `test`). |
| `PORT` | Yes (Render auto) | `5000` | Port the web service binds to (Render sets this automatically). |
| `PYTHON_VERSION` | Yes | `3.11.9` | Pinned Python runtime for Render builds. |
| `SECRET_KEY` | Yes | *Generated* | Session encryption key. Auto-generated via `generateValue: true` in `render.yaml`. |
| `MONGODB_URI` | Yes | — | MongoDB Atlas connection string with TLS (`mongodb+srv://...`). |
| `MONGODB_DATABASE` | No | `poseai` | MongoDB database name. |
| `FRONTEND_URL` | Recommended | — | Allowed frontend URL (e.g. `https://poseai.onrender.com`). |
| `ALLOWED_ORIGINS` | Recommended | — | Comma-separated list of origins permitted for CORS requests. |
| `SESSION_COOKIE_SECURE` | Yes | `1` | Enforces HTTPS-only cookies in production. |
| `SESSION_COOKIE_SAMESITE` | Yes | `None` | `None` for cross-origin or `Lax` for same-origin session handling. |
| `MONGO_ALLOW_MOCK` | Yes | `0` | Must be `0` in production. Prohibits in-memory fallback. |
| `RATE_LIMIT_ENABLED` | No | `1` | Enables sliding window rate limiting on authentication routes. |
| `HIBP_CHECK_ENABLED` | No | `1` | Enables Have I Been Pwned password leak verification. |
| `WTF_CSRF_ENABLED` | No | `1` | Enables CSRF protection for sensitive form posts. |
| `GEMINI_API_KEY` | Optional | — | Google Gemini 2.5 Flash API key for visual meal recognition. |
| `USDA_API_KEY` | Optional | — | USDA FoodData Central API key for nutritional information lookup. |
| `GOOGLE_CLIENT_ID` | Optional | — | Google Cloud OAuth 2.0 Web Client ID. |
| `GOOGLE_CLIENT_SECRET` | Optional | — | Google Cloud OAuth 2.0 Client Secret. |
| `GOOGLE_REDIRECT_URI` | Optional | — | OAuth callback URL (`https://your-domain.onrender.com/auth/google/callback`). |
| `DASHBOARD_API_URL` | Optional | — | Target API endpoint used by `main.py` desktop client. |

---

## Deploying to Render

You can deploy PoseAI using either Render's automated Blueprint or manual web service creation.

### Option A: Automated Deployment via Blueprint (Recommended)
1. Push your repository to GitHub or GitLab.
2. Log in to your [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** and select **Blueprint**.
4. Connect your PoseAI repository. Render will automatically detect [`render.yaml`](file:///render.yaml).
5. Render will prompt you to enter values for keys marked with `sync: false`:
   - `MONGODB_URI`: Paste your MongoDB Atlas connection string.
   - Optional API keys: `GEMINI_API_KEY`, `USDA_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`.
   - `FRONTEND_URL` & `ALLOWED_ORIGINS`: Set to your Render web service URL (e.g., `https://poseai-backend.onrender.com`).
6. Click **Apply**. Render will automatically build the environment with Python 3.11.9 and launch Gunicorn.

### Option B: Manual Web Service Setup
1. In the Render Dashboard, click **New +** -> **Web Service**.
2. Connect your Git repository.
3. Configure the service settings:
   - **Name**: `poseai`
   - **Language**: `Python 3`
   - **Region**: Oregon (or nearest to your MongoDB cluster)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 app:app`
   - **Health Check Path**: `/health`
4. Under **Environment Variables**, add each variable specified in the table above.
5. Click **Create Web Service**.

---

## Pre-Deployment Verification Checklist

Before deploying or triggering a production build, verify each of the following:

- [ ] **No Secrets Committed**: Run `git status` and `git diff` to confirm `.env` and credential files are untracked and excluded by [`.gitignore`](file:///.gitignore).
- [ ] **Dependencies Pinned**: Verify [`.python-version`](file:///.python-version) is present (`3.11.9`) and all required packages are present in [`requirements.txt`](file:///requirements.txt).
- [ ] **Database Reachable**: MongoDB Atlas Network Access whitelist permits Render (`0.0.0.0/0` or Render static outbound IP).
- [ ] **Automated Tests Pass**: Run `pytest` locally to confirm all tests pass cleanly.
- [ ] **Health Check Configured**: Confirm `/health` and `/api/health` return HTTP 200 with database status.
- [ ] **CORS Configured**: Ensure `ALLOWED_ORIGINS` or `FRONTEND_URL` matches your deployed domain.
- [ ] **HTTPS Cookies**: Ensure `SESSION_COOKIE_SECURE=1` and `SESSION_COOKIE_SAMESITE=None` are set for production HTTPS traffic.

---

## Author

**Sandesh Narkar**  
B.Sc. Information Technology Student  

[![Email](https://img.shields.io/badge/Email-your--email%40example.com-D14836?style=flat-square&logo=gmail&logoColor=white)](mailto:your-email@example.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sandesh%20Narkar-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/sandesh-narkar-2339a03a5)
[![GitHub](https://img.shields.io/badge/GitHub-Sandesh--Narkar-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Sandesh-Narkar)

---

## License

This project is licensed under the [MIT License](LICENSE).
https://poseai.onrender.com
