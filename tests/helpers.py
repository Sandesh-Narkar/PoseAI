"""Shared helpers for the PoseAI test suites.

The authentication tests run against an in-memory mongomock database so
they are hermetic and do not require a running MongoDB server. The
production code path still uses the real PyMongo client — only the
module-level database handle is swapped here.
"""

import mongomock

from database import mongo as mongo_module


def setup_mongo_mock() -> None:
    """Point database.mongo at a fresh in-memory mongomock database.

    Called in each test's setUp so every test starts from an empty users
    collection (no duplicate/cross-test pollution).
    """
    mongo_module._client = None
    mongo_module._db = mongomock.MongoClient()[mongo_module.Config.MONGO_DB_NAME]
    mongo_module._connection_error = None
    mongo_module._using_mock = True
    mongo_module._persisted_users = None
    mongo_module._ensure_indexes(mongo_module._db)


def users_collection():
    """Return the mocked users collection for direct assertions."""
    return mongo_module.get_users_collection()