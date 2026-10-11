"""
End-to-end test for workout.html functionality.
Starts the Flask server, then simulates browser requests.
"""
import subprocess, time, requests, sys, json, os

# Start the Flask server
proc = subprocess.Popen(
    [sys.executable, "app.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=os.path.dirname(os.path.abspath(__file__)),
    env={**os.environ, "FLASK_ENV": "testing"}
)

time.sleep(3)

base = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
s = requests.Session()

try:
    # 1. Check if we get redirected to login (no auth)
    r = s.get(f"{base}/workout", allow_redirects=False)
    print(f"1. GET /workout (no auth): status={r.status_code}, location={r.headers.get('Location', 'none')}")

    # 2. Login as existing test user (try multiple passwords)
    for pw in ["TestPass123!", "password", "testpass"]:
        r = s.post(f"{base}/auth/login", data={
            "username": "testuser_workout",
            "password": pw,
        }, allow_redirects=False)
        print(f"2. POST /auth/login (pw={pw}): status={r.status_code}")
        if r.status_code in (302, 200):
            break

    # If signup succeeded (new user), login was automatic via session
    # If login failed, try signup
    if r.status_code != 200 or "login" in r.headers.get("Location", "").lower():
        # Try signup
        r = s.post(f"{base}/auth/signup", data={
            "username": "testuser_workout2",
            "email": "testuser_workout2@poseai.com",
            "password": "TestPass123!",
            "name": "Test User",
            "confirm_password": "TestPass123!",
        }, allow_redirects=True)
        print(f"2b. POST /auth/signup: status={r.status_code}")

    # 3. Check /api/exercises with auth
    r = s.get(f"{base}/api/exercises")
    print(f"3. GET /api/experiments (authed): status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        exercises = data.get("data", [])
        print(f"   Exercise count: {len(exercises)}")
        for ex in exercises:
            print(f"   - id={ex.get('id')}, name={ex.get('name')}, muscles={ex.get('muscles', [])}")
    else:
        print(f"   Response: {r.text[:300]}")

    # 4. Check the /workout page HTML
    r = s.get(f"{base}/workout")
    print(f"4. GET /workout (authed): status={r.status_code}, len={len(r.text)}")
    html = r.text
    checks = {
        "exerciseGrid": "exerciseGrid" in html,
        "renderExercises": "renderExercises" in html,
        "loadExercises": "loadExercises" in html,
        "shell.js": "shell.js" in html,
        "startBtn": "startBtn" in html,
        "welcomeCard": "welcomeCard" in html,
        "sessionArea": "sessionArea" in html,
        "window.api.get": "window.api.get" in html,
        "/api/exercises": "/api/exercises" in html,
        "Choose an exercise": "Choose an exercise" in html,
        "START SESSION": "START SESSION" in html,
    }
    for name, found in checks.items():
        status = "OK" if found else "MISSING"
        print(f"   {name}: {status}")

    # 5. Check if the page is actually the workout page or login page
    if "password" in html.lower() and "login" in html.lower():
        print("   WARNING: This looks like the LOGIN page, not the workout page!")
    else:
        print("   This is the workout page (no login form detected)")

    # 6. Check /api/workout/session
    r = s.get(f"{base}/api/workout/session")
    print(f"5. GET /api/workout/session: status={r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {json.dumps(r.json())[:300]}")

    # 7. Start a workout
    r = s.post(f"{base}/api/workout/start", json={"exercise": "1"})
    print(f"6. POST /api/workout/start: status={r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {json.dumps(r.json())[:300]}")

    # 8. Check /api/workout
    r = s.get(f"{base}/api/workout")
    print(f"7. GET /api/workout: status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   exercise={data.get('data', {}).get('exercise', 'N/A')}")

finally:
    proc.terminate()
    proc.wait()
    print("\nServer stopped.")

