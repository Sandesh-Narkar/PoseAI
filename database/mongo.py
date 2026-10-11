"""
PoseAI — MongoDB Users Layer

Single reusable MongoDB connection for the authentication system.

Production path:
    MONGO_URI (from environment) -> PyMongo MongoClient -> poseai.users

Dev-only fallback:
    If MONGO_URI is unreachable AND MONGO_ALLOW_MOCK=1 is set, an
    in-memory mongomock database is used so the auth flow can be
    exercised on machines without a running MongoDB server. The mock is
    never activated silently — it must be explicitly enabled. When it is
    not enabled, every auth endpoint returns a clean error instead of
    crashing the application.

Storage contract for a user document:
    {
        "_id":             ObjectId,
        "name":            str,        # display name (alias: full_name)
        "full_name":       str,        # kept in sync with name
        "username":        str,        # unique, derived from email prefix
        "email":           str,        # normalized lowercase, unique
        "password_hash":   str | None, # Argon2id hash; None for Google-only
        "auth_provider":   str,        # "local" | "google"
        "google_id":       str | None, # Google OAuth "sub" (sparse index)
        "profile_picture": str | None, # Google avatar URL
        "email_verified":  bool,       # True once Google verified the email
        "is_active":       bool,
        "created_at":      datetime (UTC),
        "updated_at":      datetime (UTC),
    }

The password_hash field is NEVER serialized into API responses
(see user_to_dict). Passwords are hashed with Argon2id
(argon2-cffi), never with Werkzeug/scrypt.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import Config

logger = logging.getLogger("poseai.mongo")

_client: Any = None
_db: Any = None
_connection_error: Optional[str] = None
_using_mock: bool = False
_persisted_users: Any = None

MOCK_STORE_ENV = "MONGO_MOCK_STORE_PATH"


class MongoUnavailableError(Exception):
    """Raised when MongoDB cannot be reached and no dev fallback is enabled."""


def _ensure_indexes(database: Any) -> None:
    """Create the unique indexes enforcing normalized-email / username
    uniqueness and sparse google_id. Best-effort: never crashes the app if the
    DB rejects it."""
    try:
        users = database["users"]
        users.create_index([("email", ASCENDING)], unique=True)
        users.create_index([("google_id", ASCENDING)], sparse=True)
        users.create_index([("username", ASCENDING)], sparse=True)
    except PyMongoError:
        logger.warning("Could not create MongoDB unique indexes (best-effort).")


# ── Durable dev-only mock store ─────────────────────────────────────────
# The mongomock fallback is an in-memory store, so registered users would
# be lost when Flask restarts. To keep the auth flow testable end-to-end
# on machines without a real MongoDB server, the mock's `users` collection
# is mirrored to a JSON file (write-through) and restored on startup.
# This is STRICTLY limited to the dev fallback (MONGO_ALLOW_MOCK=1); the
# production pymongo path above never touches this store.


def _mock_store_path() -> str:
    """Resolve the JSON file used to persist the mock users collection."""
    configured = os.environ.get(MOCK_STORE_ENV)
    if configured:
        return configured
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "data", "mongo_mock_store.json")


def _doc_to_json(doc: dict) -> dict:
    """Convert a Mongo user document into a JSON-safe dict."""
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            out[key] = {"$oid": str(value)}
        elif isinstance(value, datetime):
            out[key] = {"$date": value.isoformat()}
        else:
            out[key] = value
    return out


def _doc_from_json(value: Any) -> Any:
    """Reverse of _doc_to_json (restores ObjectId / datetime)."""
    if isinstance(value, dict):
        if set(value) == {"$oid"}:
            return ObjectId(value["$oid"])
        if set(value) == {"$date"}:
            return datetime.fromisoformat(value["$date"])
        return {k: _doc_from_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_doc_from_json(item) for item in value]
    return value


class _MockFileStore:
    """JSON file store mirroring the mock users collection."""

    def __init__(self, users_collection: Any, path: Optional[str]) -> None:
        self._users = users_collection
        self._path = path

    def load(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            restored = [_doc_from_json(doc) for doc in payload]
            self._users.delete_many({})
            for doc in restored:
                self._users.insert_one(doc)
            logger.info("Restored %d user(s) from mock store: %s", len(restored), self._path)
        except Exception as exc:  # noqa: BLE001 - corrupt/legacy file must not crash startup
            logger.warning("Could not restore mock Mongo store (%s): %s", self._path, exc)

    def save(self) -> None:
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            docs = list(self._users.find({}))
            payload = [_doc_to_json(doc) for doc in docs]
            tmp_path = self._path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception as exc:  # noqa: BLE001 - persistence is best-effort in dev
            logger.warning("Could not persist mock Mongo store (%s): %s", self._path, exc)


class _PersistedUsers:
    """Wraps the mongomock users collection and mirrors writes to disk."""

    def __init__(self, wrapped: Any, store: Optional[_MockFileStore]) -> None:
        self._wrapped = wrapped
        self._store = store

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def insert_one(self, *args, **kwargs):
        result = self._wrapped.insert_one(*args, **kwargs)
        if self._store:
            self._store.save()
        return result

    def update_one(self, *args, **kwargs):
        result = self._wrapped.update_one(*args, **kwargs)
        if self._store:
            self._store.save()
        return result

    def delete_many(self, *args, **kwargs):
        result = self._wrapped.delete_many(*args, **kwargs)
        if self._store:
            self._store.save()
        return result


def _connect() -> None:
    global _client, _db, _connection_error, _using_mock
    if _db is not None:
        return

    uri = Config.MONGO_URI
    db_name = Config.MONGO_DB_NAME

    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=Config.MONGO_CONNECT_TIMEOUT_MS)
        # Force a real connection round-trip so failures surface immediately.
        _client.admin.command("ping")
        _db = _client[db_name]
        _using_mock = False
        _ensure_indexes(_db)
        return
    except PyMongoError as exc:
        _connection_error = str(exc)
    except Exception as exc:  # noqa: BLE001 - any connect failure should degrade gracefully
        _connection_error = str(exc)

    logger.warning("MongoDB unreachable (%s). ", _connection_error)
    if not Config.MONGO_ALLOW_MOCK:
        raise MongoUnavailableError("MongoDB is not available.")

    try:
        import mongomock  # dev-only fallback, optional dependency
    except ImportError:
        raise MongoUnavailableError(
            "MongoDB is not available and mongomock is not installed "
            "(pip install mongomock to enable the dev fallback)."
        )

    _client = None
    _db = mongomock.MongoClient()[db_name]
    _using_mock = True
    _ensure_indexes(_db)
    _build_persisted_users(_mock_store_path())
    logger.warning("Dev mode: MongoDB unavailable — using in-memory mongomock (persisted to %s).", _mock_store_path())


def _build_persisted_users(path: Optional[str]) -> None:
    """Build the users wrapper around the current _db, restoring from disk."""
    global _persisted_users
    store = _MockFileStore(_db["users"], path) if path else None
    if store:
        store.load()
    _persisted_users = _PersistedUsers(_db["users"], store)


def get_db() -> Any:
    """Return the shared MongoDB database object (connect on first use)."""
    if _db is None:
        _connect()
    return _db


def get_users_collection() -> Any:
    """Return the shared `users` collection used for authentication."""
    if _using_mock and _persisted_users is not None:
        return _persisted_users
    return get_db()["users"]


def is_mock() -> bool:
    """True when the active database is the dev-only in-memory mock."""
    return _using_mock


def normalize_email(email: Optional[str]) -> str:
    """Trim whitespace and lowercase an email address."""
    if not email:
        return ""
    return email.strip().lower()


def user_to_dict(user_doc: Optional[dict]) -> Optional[dict]:
    """Public serialization of a Mongo user. NEVER includes password_hash."""
    if not user_doc:
        return None
    created_at = user_doc.get("created_at")
    updated_at = user_doc.get("updated_at")
    name = user_doc.get("name") or user_doc.get("full_name") or user_doc.get("username", "")
    full_name = user_doc.get("full_name") or user_doc.get("name", "")
    return {
        "id": str(user_doc.get("_id")),
        "user_id": str(user_doc.get("_id")),
        "name": name,
        "full_name": full_name,
        "username": user_doc.get("username", ""),
        "email": user_doc.get("email", ""),
        "auth_provider": user_doc.get("auth_provider", "local"),
        "google_id": user_doc.get("google_id"),
        "profile_picture": user_doc.get("profile_picture"),
        "email_verified": bool(user_doc.get("email_verified", False)),
        "is_active": bool(user_doc.get("is_active", True)),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else None,
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else None,
        "preferences": user_doc.get("preferences", {}),
    }


def find_user_by_id(user_id: Any) -> Optional[dict]:
    """Fetch a user document by its string/ObjectId _id. Safe on bad input."""
    if not user_id:
        return None
    try:
        oid = ObjectId(str(user_id))
    except Exception:  # noqa: BLE001
        # Includes bson.errors.InvalidId (not a ValueError). A malformed
        # session id must resolve to "no user" (404), never a 500.
        return None
    return get_users_collection().find_one({"_id": oid})


def find_user_by_email(email: Optional[str]) -> Optional[dict]:
    """Fetch a user by normalized email (case-insensitive by construction)."""
    return get_users_collection().find_one({"email": normalize_email(email)})


def find_user_by_google_id(google_id: Optional[str]) -> Optional[dict]:
    """Fetch a user document by Google OAuth sub / id."""
    if not google_id:
        return None
    return get_users_collection().find_one({"google_id": str(google_id).strip()})


def link_google_account(
    user_id: Any,
    google_id: str,
    profile_picture: Optional[str] = None,
    name: Optional[str] = None,
) -> Optional[dict]:
    """Safely link an existing user with verified Google identity without deleting credentials."""
    try:
        oid = ObjectId(str(user_id))
    except (TypeError, ValueError):
        return None

    update_fields: dict[str, Any] = {
        "google_id": str(google_id).strip(),
        "email_verified": True,
        "updated_at": now_utc(),
    }
    if profile_picture:
        update_fields["profile_picture"] = profile_picture
    if name:
        update_fields["name"] = name

    col = get_users_collection()
    col.update_one({"_id": oid}, {"$set": update_fields})
    return col.find_one({"_id": oid})


def update_user_password_hash(user_id: Any, new_hash: str) -> bool:
    """Update user password hash (e.g. on Argon2id rehash)."""
    try:
        oid = ObjectId(str(user_id))
    except (TypeError, ValueError):
        return False
    res = get_users_collection().update_one(
        {"_id": oid},
        {"$set": {"password_hash": new_hash, "updated_at": now_utc()}},
    )
    return res.modified_count > 0


def is_email_taken(email: Optional[str]) -> bool:
    return find_user_by_email(email) is not None


def is_username_taken(username: Optional[str]) -> bool:
    return get_users_collection().find_one({"username": username.strip()}) is not None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def reset_for_tests() -> None:
    """Test helper: swap the active DB for a fresh in-memory mongomock DB.
    The durable disk store is NOT loaded or written, keeping tests isolated."""
    global _client, _db, _connection_error, _using_mock
    import mongomock

    _client = None
    _db = mongomock.MongoClient()[Config.MONGO_DB_NAME]
    _connection_error = None
    _using_mock = True
    _ensure_indexes(_db)
    _build_persisted_users(None)