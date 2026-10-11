# Google OAuth Setup — "Continue with Google"

This document explains how to make PoseAI's **Continue with Google** button work,
and what happens on a server where Google sign-in is not configured.

---

## 1. Why the message appeared

`auth.py` only starts the Google flow when `GOOGLE_CLIENT_ID` **and**
`GOOGLE_CLIENT_SECRET` are present. With them missing, `/auth/google` used to
redirect to `/login?error=google_not_configured`, which produced the banner:

> Google OAuth is not configured on this server yet. Please sign in with email and password.

That is not a bug in the OAuth code — Google sign-in genuinely requires
credentials issued by Google for *your* app. There is no way to obtain them
from inside the codebase.

---

## 2. What is now implemented

| Server state | `/auth/providers` | UI behaviour |
|---|---|---|
| Real credentials set | `{"enabled": true, "mode": "live"}` | Google button shown, real Google consent screen |
| No credentials + `GOOGLE_OAUTH_DEV_MODE=1` | `{"enabled": true, "mode": "dev"}` | Button shown labelled **"Continue with Google (dev mode)"**, synthetic identity signs in |
| No credentials, dev mode off | `{"enabled": false, "mode": "off"}` | Button **and** "or continue with" divider hidden; a short hint replaces them — no error, no dead end |

The auth pages probe `GET /auth/providers` on load, so the button never leads to
an error page. Direct hits on `/auth/google` still redirect with a friendly
`?error=google_not_configured` message as a fallback.

---

## 3. Real Google credentials (recommended)

1. Go to <https://console.cloud.google.com> and create (or select) a project.
2. **APIs & Services → OAuth consent screen** → *External* → fill in app name,
   support email, developer contact. Add scopes `openid`, `email`, `profile`.
   While in *Testing* mode, add the Google accounts you want to test with.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   → application type **Web application**.
4. Add the URIs:

   | Field | Value (local dev) |
   |---|---|
   | Authorized JavaScript origin | `http://127.0.0.1:5000` |
   | Authorized redirect URI | `http://127.0.0.1:5000/auth/google/callback` |

   For a deployed host use `https://<your-host>/auth/google/callback` and set
   `GOOGLE_REDIRECT_URI` to the same value. The redirect URI must match
   **exactly** — scheme, host, port and path.

5. Put the values in `.env` (never in source control):

   ```ini
   GOOGLE_CLIENT_ID=1234567890-xxxxxxxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
   GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/auth/google/callback
   ```

6. Restart the app (`python app.py`) and reload `/login`. The button is now
   labelled "Continue with Google" and `GET /auth/providers` reports
   `"mode": "live"`.

**Verification**

```bash
python -c "import os,json,requests as r; print(r.get('http://127.0.0.1:5000/auth/providers').json())"
# {'google': {'enabled': True, 'mode': 'live', ...}, 'success': True}
```

Sign in with a test Google account → you land on `/dashboard`; the user document
has `auth_provider: "google"`, a `google_id`, and `password_hash: null`.

---

## 4. Local testing without Google credentials (dev stub)

Set exactly one line in `.env`:

```ini
GOOGLE_OAUTH_DEV_MODE=1
# optional: GOOGLE_DEV_EMAIL=google.dev@example.com
# optional: GOOGLE_DEV_NAME=Google Dev Athlete
```

Restart, then click the button (now labelled *dev mode*). `/auth/google` runs
the **same** account-linking code path as the real callback
(`_complete_google_login`) using a deterministic synthetic profile, then lands
on `/dashboard`.

What the stub does and does not do:

- ✔ Exercises first-time Google signup, returning-user login, and linking onto
  an existing local email (password hash preserved) — all idempotent.
- ✔ Refuses to activate when real credentials exist (real Google always wins).
-  It is **not** Google: no consent screen, no token exchange, no identity
  verification. It must never be enabled on a public host — `ProductionConfig`
  forces `GOOGLE_OAUTH_DEV_MODE = False`, and each use logs a warning:
  `Google OAuth DEV MODE active — using a synthetic identity (...)`.

---

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Button hidden, hint shown | Credentials missing — see section 3, or enable the dev stub (section 4) |
| `?error=google_not_configured` after clicking | You hit `/auth/google` directly while the provider is off |
| `?error=oauth_failed` | Token exchange failed: wrong `GOOGLE_CLIENT_SECRET`, clock skew, or a redirect URI mismatch |
| `redirect_uri_mismatch` on Google's page | The URI in Google Console must equal `GOOGLE_REDIRECT_URI` exactly |
| `?error=oauth_identity_missing` | Google returned no `sub`/`email` — check the `openid email profile` scopes |
| Existing email/password user suddenly signs in via Google | Expected: the account is **linked** (`google_id` added); the local password is kept |