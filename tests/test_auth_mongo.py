"""
PoseAI — Comprehensive Authentication Test Suite

Validates all 20 security and functionality scenarios:
  TEST 1  — Empty login validation
  TEST 2  — Invalid email format validation
  TEST 3  — Short password rejection (min 12 characters)
  TEST 4  — Signup creates user in MongoDB without plaintext password
  TEST 5  — Password is Argon2id hashed
  TEST 6  — Signup creates authenticated session & redirect
  TEST 7  — Login with created credentials succeeds
  TEST 8  — Wrong password rejected with generic error (no enumeration)
  TEST 9  — Duplicate email rejected (409)
  TEST 10 — Session persistence across requests
  TEST 11 — Current user endpoint returns user without password hash
  TEST 12 — Logout invalidates server session
  TEST 13 — Protected dashboard redirects unauthenticated request to /login
  TEST 14 — Multi-user session isolation
  TEST 15 — Google OAuth signup/login flow
  TEST 16 — Google OAuth re-login recognizes existing account
  TEST 17 — Google OAuth safe account-linking with existing local email
  TEST 18 — Rate limiting activates on excessive requests
  TEST 19 — CSRF token endpoint and protection
  TEST 20 — Have I Been Pwned breach detection and offline tolerance
  TEST 21 — Automatic Argon2id re-hashing
"""

import unittest
from unittest.mock import MagicMock, patch
import argon2

from app import app
from auth import (
    _ph,
    _is_rate_limited,
    _RATE_LIMIT_BUCKETS,
    check_needs_rehash,
    hash_password,
    is_password_breached,
    verify_password,
)
from config import Config
from database.mongo import MongoUnavailableError
from tests.helpers import setup_mongo_mock, users_collection


class PoseAIAuthSuite(unittest.TestCase):
    def setUp(self):
        setup_mongo_mock()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False  # Explicitly tested in test_csrf
        self.client = app.test_client()
        self.VALID_NAME = "Athlete Alex"
        self.VALID_EMAIL = "alex@poseai.test"
        self.VALID_PASSWORD = "StrongPassphrase123!"

    # ── TEST 1 — Empty Login ──────────────────────────────────────────
    def test_empty_login_rejected(self):
        resp = self.client.post("/auth/login", json={})
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data.get("success", False))

    # ── TEST 2 — Invalid Email ────────────────────────────────────────
    def test_invalid_email_format_rejected(self):
        for bad_email in ["abc", "abc@", "abc.com@", "@domain.com", ""]:
            resp = self.client.post("/auth/signup", json={
                "name": self.VALID_NAME,
                "email": bad_email,
                "password": self.VALID_PASSWORD,
                "confirm_password": self.VALID_PASSWORD,
            })
            self.assertEqual(resp.status_code, 400, f"Expected 400 for {bad_email}")

    # ── TEST 3 — Short Password ───────────────────────────────────────
    def test_short_password_rejected(self):
        # Must be at least 12 characters
        resp = self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": "Short123",
            "confirm_password": "Short123",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("12 characters", resp.get_json().get("message", ""))

    # ── TEST 4 — Signup Creates MongoDB User ─────────────────────────
    def test_signup_creates_mongodb_user(self):
        resp = self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data["success"])

        user_doc = users_collection().find_one({"email": self.VALID_EMAIL})
        self.assertIsNotNone(user_doc)
        self.assertEqual(user_doc["name"], self.VALID_NAME)
        self.assertEqual(user_doc["email"], self.VALID_EMAIL)
        self.assertEqual(user_doc["auth_provider"], "local")
        self.assertNotIn("StrongPassphrase123!", str(user_doc))  # No plaintext

    # ── TEST 5 — Password Hash is Argon2id ───────────────────────────
    def test_password_hash_is_argon2id(self):
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        user_doc = users_collection().find_one({"email": self.VALID_EMAIL})
        stored_hash = user_doc.get("password_hash", "")
        self.assertTrue(stored_hash.startswith("$argon2id$"))
        # Verify via Argon2 PasswordHasher
        self.assertTrue(_ph.verify(stored_hash, self.VALID_PASSWORD))

    # ── TEST 6 — Signup Creates Authenticated Session ────────────────
    def test_signup_authenticates_session_and_redirects(self):
        resp = self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data.get("redirect"), "/dashboard")

        # Check authenticated session
        me_resp = self.client.get("/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        self.assertTrue(me_resp.get_json().get("authenticated"))

    # ── TEST 7 — Login Flow ──────────────────────────────────────────
    def test_login_flow_success(self):
        # 1. Sign up
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        # 2. Log out
        self.client.post("/auth/logout")
        me_resp = self.client.get("/auth/me")
        self.assertFalse(me_resp.get_json().get("authenticated"))

        # 3. Log back in
        login_resp = self.client.post("/auth/login", json={
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
        })
        self.assertEqual(login_resp.status_code, 200)
        self.assertTrue(login_resp.get_json().get("success"))

        me_resp2 = self.client.get("/auth/me")
        self.assertTrue(me_resp2.get_json().get("authenticated"))

    # ── TEST 8 — Wrong Password Returns Generic Error ─────────────────
    def test_wrong_password_generic_error(self):
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        self.client.post("/auth/logout")

        resp = self.client.post("/auth/login", json={
            "email": self.VALID_EMAIL,
            "password": "WrongPassword123!",
        })
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get("message"), "Invalid email or password.")

        # Test non-existent user returns exact same generic message
        resp2 = self.client.post("/auth/login", json={
            "email": "nonexistent@poseai.test",
            "password": "SomePassword123!",
        })
        self.assertEqual(resp2.status_code, 401)
        self.assertEqual(resp2.get_json().get("message"), "Invalid email or password.")

    # ── TEST 9 — Duplicate Signup Rejected ───────────────────────────
    def test_duplicate_signup_rejected(self):
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        # Attempt identical email
        resp = self.client.post("/auth/signup", json={
            "name": "Second Person",
            "email": self.VALID_EMAIL,
            "password": "AnotherPassphrase123!",
            "confirm_password": "AnotherPassphrase123!",
        })
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.get_json().get("message", ""))
        self.assertEqual(users_collection().count_documents({"email": self.VALID_EMAIL}), 1)

    # ── TEST 10 — Refresh Keeps Session ──────────────────────────────
    def test_refresh_keeps_session(self):
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        # Simulate browser refresh by calling GET /auth/me multiple times
        for _ in range(3):
            resp = self.client.get("/auth/me")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json().get("authenticated"))

    # ── TEST 11 — Current User Endpoint ──────────────────────────────
    def test_current_user_no_password_leak(self):
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        resp = self.client.get("/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["authenticated"])
        user = data["user"]
        self.assertEqual(user["email"], self.VALID_EMAIL)
        self.assertEqual(user["name"], self.VALID_NAME)
        self.assertEqual(user["auth_provider"], "local")
        self.assertNotIn("password", user)
        self.assertNotIn("password_hash", user)

    # ── TEST 12 — Logout ─────────────────────────────────────────────
    def test_logout_invalidates_session(self):
        self.client.post("/auth/signup", json={
            "name": self.VALID_NAME,
            "email": self.VALID_EMAIL,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        logout_resp = self.client.post("/auth/logout")
        self.assertEqual(logout_resp.status_code, 200)

        me_resp = self.client.get("/auth/me")
        self.assertFalse(me_resp.get_json().get("authenticated"))

    # ── TEST 13 — Protected Dashboard ────────────────────────────────
    def test_protected_dashboard_redirects_unauthenticated(self):
        # HTML request to root without session
        resp = self.client.get("/", headers={"Accept": "text/html"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers.get("Location", ""))

        # Direct access to dashboard
        resp2 = self.client.get("/dashboard")
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("/login", resp2.headers.get("Location", ""))

    # ── TEST 14 — Multi-User Session Isolation ────────────────────────
    def test_multi_user_isolation(self):
        client1 = app.test_client()
        client2 = app.test_client()

        client1.post("/auth/signup", json={
            "name": "User One",
            "email": "user1@poseai.test",
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        client2.post("/auth/signup", json={
            "name": "User Two",
            "email": "user2@poseai.test",
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })

        me1 = client1.get("/auth/me").get_json()["user"]
        me2 = client2.get("/auth/me").get_json()["user"]

        self.assertEqual(me1["name"], "User One")
        self.assertEqual(me2["name"], "User Two")
        self.assertNotEqual(me1["id"], me2["id"])

    # ── TEST 15 — Google OAuth Flow ──────────────────────────────────
    def test_google_oauth_callback_creates_user(self):
        mock_token = {
            "userinfo": {
                "sub": "google-oauth-12345",
                "email": "googleuser@poseai.test",
                "name": "Google Athlete",
                "picture": "https://example.com/avatar.jpg",
                "email_verified": True,
            }
        }
        mock_client = MagicMock()
        mock_client.authorize_access_token.return_value = mock_token
        with patch("auth.oauth.create_client", return_value=mock_client), \
             patch("auth.Config.GOOGLE_CLIENT_ID", "mock-client-id"), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", "mock-secret"):

            resp = self.client.get("/auth/google/callback")
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/dashboard", resp.headers.get("Location", ""))

            user_doc = users_collection().find_one({"google_id": "google-oauth-12345"})
            self.assertIsNotNone(user_doc)
            self.assertEqual(user_doc["auth_provider"], "google")
            self.assertEqual(user_doc["email"], "googleuser@poseai.test")

            # Check authenticated session
            me = self.client.get("/auth/me").get_json()
            self.assertTrue(me["authenticated"])
            self.assertEqual(me["user"]["name"], "Google Athlete")

    # ── TEST 16 — Google Relogin Does Not Duplicate User ─────────────
    def test_google_relogin_no_duplicate(self):
        mock_token = {
            "userinfo": {
                "sub": "google-oauth-55555",
                "email": "returning@poseai.test",
                "name": "Returning User",
                "picture": "https://example.com/pic.jpg",
                "email_verified": True,
            }
        }
        mock_client = MagicMock()
        mock_client.authorize_access_token.return_value = mock_token
        with patch("auth.oauth.create_client", return_value=mock_client), \
             patch("auth.Config.GOOGLE_CLIENT_ID", "mock-client-id"), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", "mock-secret"):

            # First login
            self.client.get("/auth/google/callback")
            self.client.post("/auth/logout")

            # Second login
            self.client.get("/auth/google/callback")
            self.assertEqual(users_collection().count_documents({"google_id": "google-oauth-55555"}), 1)

    # ── TEST 17 — Google Safe Account-Linking ─────────────────────────
    def test_google_safe_account_linking(self):
        # 1. User signs up with local password
        self.client.post("/auth/signup", json={
            "name": "Local User",
            "email": "shared@poseai.test",
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        self.client.post("/auth/logout")

        initial_user = users_collection().find_one({"email": "shared@poseai.test"})
        initial_hash = initial_user["password_hash"]

        # 2. User logs in with Google using matching email
        mock_token = {
            "userinfo": {
                "sub": "google-link-9999",
                "email": "shared@poseai.test",
                "name": "Local User Google",
                "picture": "https://example.com/avatar.png",
                "email_verified": True,
            }
        }
        mock_client = MagicMock()
        mock_client.authorize_access_token.return_value = mock_token
        with patch("auth.oauth.create_client", return_value=mock_client), \
             patch("auth.Config.GOOGLE_CLIENT_ID", "mock-client-id"), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", "mock-secret"):

            resp = self.client.get("/auth/google/callback")
            self.assertEqual(resp.status_code, 302)

            # Account linked safely: same ID, same password hash preserved!
            updated_user = users_collection().find_one({"email": "shared@poseai.test"})
            self.assertEqual(updated_user["google_id"], "google-link-9999")
            self.assertEqual(updated_user["password_hash"], initial_hash)
            self.assertEqual(users_collection().count_documents({"email": "shared@poseai.test"}), 1)

    # ── TEST 18 — Rate Limiting ───────────────────────────────────────
    def test_rate_limiting_activates(self):
        _RATE_LIMIT_BUCKETS.clear()
        with patch("auth.Config.RATE_LIMIT_ENABLED", True):
            # Exceed 20 login attempts
            for i in range(25):
                resp = self.client.post("/auth/login", json={
                    "email": "throttled@poseai.test",
                    "password": "wrongpassword123!",
                })
                if resp.status_code == 429:
                    break
            self.assertEqual(resp.status_code, 429)
        _RATE_LIMIT_BUCKETS.clear()

    # ── TEST 19 — CSRF Token Endpoint & Protection ────────────────────
    def test_csrf_protection(self):
        # 1. Fetch CSRF token
        csrf_resp = self.client.get("/auth/csrf-token")
        self.assertEqual(csrf_resp.status_code, 200)
        token = csrf_resp.get_json().get("csrf_token")
        self.assertTrue(len(token) > 10)

        # 2. Test CSRF enforcement
        with patch.dict(app.config, {"WTF_CSRF_ENABLED": True, "WTF_CSRF_CHECK_DEFAULT": True}):
            # Request without CSRF token should be rejected
            rej_resp = self.client.post("/auth/login", json={
                "email": self.VALID_EMAIL,
                "password": self.VALID_PASSWORD,
            })
            self.assertEqual(rej_resp.status_code, 400)

            # Request with valid CSRF token header is accepted
            acc_resp = self.client.post(
                "/auth/login",
                headers={"X-CSRFToken": token},
                json={"email": self.VALID_EMAIL, "password": self.VALID_PASSWORD},
            )
            # Status will be 401 (invalid creds) instead of 400 (CSRF rejected)
            self.assertEqual(acc_resp.status_code, 401)

    # ── TEST 20 — HIBP Password Breach Check ──────────────────────────
    def test_hibp_breached_password_rejected(self):
        with patch("auth.is_password_breached", return_value=True):
            resp = self.client.post("/auth/signup", json={
                "name": self.VALID_NAME,
                "email": "breached@poseai.test",
                "password": "KnownBreachedPassword123!",
                "confirm_password": "KnownBreachedPassword123!",
            })
            self.assertEqual(resp.status_code, 400)
            self.assertIn("data breaches", resp.get_json().get("message", ""))

    def test_hibp_offline_fails_open_safely(self):
        # When HIBP raises network timeout, it must fail open without error
        with patch("auth.requests.get", side_effect=Exception("Network timeout")):
            self.assertFalse(is_password_breached("AnyPassword123!"))

    # ── TEST 21 — Argon2id Automatic Rehash ───────────────────────────
    def test_argon2id_rehash_detection(self):
        # Hash with old parameters
        old_ph = argon2.PasswordHasher(time_cost=1, memory_cost=16384, parallelism=1, type=argon2.Type.ID)
        old_hash = old_ph.hash("RehashMe12345678")
        self.assertTrue(check_needs_rehash(old_hash))

        # Hash with current parameters
        current_hash = hash_password("RehashMe12345678")
        self.assertFalse(check_needs_rehash(current_hash))


class GoogleProviderConfigTests(unittest.TestCase):
    """'Continue with Google' must never lead to a dead-end error."""

    def setUp(self):
        setup_mongo_mock()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def tearDown(self):
        app.config.pop("GOOGLE_CLIENT_ID", None)
        app.config.pop("GOOGLE_CLIENT_SECRET", None)
        app.config.pop("GOOGLE_REDIRECT_URI", None)

    def _with_credentials(self):
        app.config["GOOGLE_CLIENT_ID"] = "mock-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "mock-secret"
        app.config["GOOGLE_REDIRECT_URI"] = "http://localhost/auth/google/callback"

    # ── Provider discovery endpoint ──────────────────────────────────
    def test_providers_reports_off_without_credentials(self):
        with patch("auth.Config.GOOGLE_CLIENT_ID", ""), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", ""), \
             patch("auth.Config.GOOGLE_OAUTH_DEV_MODE", False):
            payload = self.client.get("/auth/providers").get_json()
        self.assertTrue(payload["success"])
        self.assertFalse(payload["google"]["enabled"])
        self.assertEqual(payload["google"]["mode"], "off")

    def test_providers_reports_live_with_credentials(self):
        self._with_credentials()
        with patch("auth.Config.GOOGLE_OAUTH_DEV_MODE", False):
            payload = self.client.get("/api/auth/providers").get_json()
        self.assertTrue(payload["google"]["enabled"])
        self.assertEqual(payload["google"]["mode"], "live")
        self.assertEqual(payload["google"]["label"], "Continue with Google")

    def test_providers_reports_dev_stub(self):
        with patch("auth.Config.GOOGLE_CLIENT_ID", ""), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", ""), \
             patch("auth.Config.GOOGLE_OAUTH_DEV_MODE", True):
            payload = self.client.get("/auth/providers").get_json()
        self.assertTrue(payload["google"]["enabled"])
        self.assertEqual(payload["google"]["mode"], "dev")
        self.assertIn("dev mode", payload["google"]["label"])

    # ── /auth/google with no configuration ───────────────────────────
    def test_google_login_redirects_with_hint_when_unconfigured(self):
        with patch("auth.Config.GOOGLE_CLIENT_ID", ""), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", ""), \
             patch("auth.Config.GOOGLE_OAUTH_DEV_MODE", False):
            resp = self.client.get("/auth/google")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("error=google_not_configured", resp.headers.get("Location", ""))

    # ── Dev stub end-to-end ──────────────────────────────────────────
    def test_dev_stub_signs_in_and_creates_google_user(self):
        with patch("auth.Config.GOOGLE_CLIENT_ID", ""), \
             patch("auth.Config.GOOGLE_CLIENT_SECRET", ""), \
             patch("auth.Config.GOOGLE_OAUTH_DEV_MODE", True), \
             patch("auth.Config.GOOGLE_DEV_EMAIL", "dev.user@poseai.test"), \
             patch("auth.Config.GOOGLE_DEV_NAME", "Dev Google User"):
            resp = self.client.get("/auth/google")

            self.assertEqual(resp.status_code, 302)
            self.assertIn("/dashboard", resp.headers.get("Location", ""))

            doc = users_collection().find_one({"email": "dev.user@poseai.test"})
            self.assertIsNotNone(doc)
            self.assertEqual(doc["auth_provider"], "google")
            self.assertTrue(doc["google_id"].startswith("dev-google-"))
            self.assertIsNone(doc["password_hash"])

            me = self.client.get("/auth/me").get_json()
            self.assertTrue(me["authenticated"])
            self.assertEqual(me["user"]["name"], "Dev Google User")

            # Second visit must reuse the account, never duplicate it
            self.client.post("/auth/logout")
            self.client.get("/auth/google")
            self.assertEqual(
                users_collection().count_documents({"email": "dev.user@poseai.test"}), 1
            )

    def test_dev_stub_never_overrides_real_credentials(self):
        self._with_credentials()
        with patch("auth.Config.GOOGLE_OAUTH_DEV_MODE", True):
            mock_client = MagicMock()
            mock_client.authorize_redirect.return_value = "redirected-to-google"
            with patch("auth.oauth.create_client", return_value=mock_client):
                resp = self.client.get("/auth/google")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(as_text=True), "redirected-to-google")
        self.assertIsNone(
            users_collection().find_one({"google_id": {"$regex": "^dev-google-"}})
        )

    # ── Auth pages must ship the probe + hint ────────────────────────
    def test_auth_pages_probe_providers_and_ship_hint(self):
        for page in ("/login", "/signup"):
            with self.subTest(page=page):
                body = self.client.get(page).data.decode("utf-8")
                self.assertIn("/auth/providers", body)
                self.assertIn('id="google-unavailable"', body)
                self.assertIn('id="google-auth-btn"', body)


if __name__ == "__main__":
    unittest.main()