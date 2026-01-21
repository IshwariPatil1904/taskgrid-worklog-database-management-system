import os
from typing import Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError, PyMongoError
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Singleton client
_client: Optional[MongoClient] = None


def _build_mongo_uri() -> str:
    """Build MongoDB connection URI."""
    uri = os.getenv("MONGODB_URI")
    if uri:
        return uri

    host = os.getenv("MONGODB_HOST", "localhost")
    port = os.getenv("MONGODB_PORT", "27017")
    user = os.getenv("MONGODB_USER")
    password = os.getenv("MONGODB_PASSWORD")
    auth_db = os.getenv("MONGODB_AUTH_DB", "admin")

    if user and password:
        return f"mongodb://{user}:{password}@{host}:{port}/?authSource={auth_db}"
    else:
        return f"mongodb://{host}:{port}"


def get_client() -> MongoClient:
    """Return a singleton MongoClient (connects once)."""
    global _client
    if _client is not None:
        return _client

    uri = _build_mongo_uri()
    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")  # test connection
        return _client
    except (ConnectionFailure, ConfigurationError) as e:
        raise RuntimeError(f"Failed to connect to MongoDB at URI '{uri}': {e}") from e


def get_database(db_name: Optional[str] = None):
    """Return a database handle (default: taskgrid)."""
    client = get_client()
    name = db_name or os.getenv("MONGODB_DB", "taskgrid")
    return client[name]


def get_collection(name: str, db_name: Optional[str] = None):
    """Return a collection handle."""
    db = get_database(db_name)
    return db[name]


def is_healthy() -> bool:
    """Return True if MongoDB is reachable."""
    try:
        get_client().admin.command("ping")
        return True
    except PyMongoError:
        return False


# 🔹 Utility helpers
def oid(value):
    """Convert string to ObjectId safely"""
    try:
        return ObjectId(value)
    except Exception:
        return None


from bson import ObjectId

def to_str_id(doc):
    """
    Recursively convert ObjectId fields to strings for safe JSON serialization.
    Works for nested dicts and lists.
    """
    if not doc:
        return None

    # If it's a list, apply recursively to each item
    if isinstance(doc, list):
        return [to_str_id(d) for d in doc]

    # If it's a single document (dict)
    if isinstance(doc, dict):
        converted = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                converted[key] = str(value)
            elif isinstance(value, list):
                converted[key] = [to_str_id(v) for v in value]
            elif isinstance(value, dict):
                converted[key] = to_str_id(value)
            else:
                converted[key] = value
        return converted

    # If it's directly an ObjectId
    if isinstance(doc, ObjectId):
        return str(doc)

    return doc




# ✅ Collection shortcuts (auto-created when file imports)
_db = get_database()
users_col = _db["users"]
projects_col = _db["projects"]
tasks_col = _db["tasks"]
worklogs_col = _db["work_logs"]
notifications_col = _db["notifications"]
subtasks_col = _db["subtasks"]
work_uploads_col = _db["work_uploads"]
timeline_col = _db["timeline"]


# 🧩 ADD THIS FUNCTION BELOW — it’s what your app_mongo.py expects
def init_mongo(app=None):
    """
    Initialize MongoDB connection for Flask app.
    """
    try:
        client = get_client()
        db = get_database()
        print(f"[MongoDB] ✅ Connected successfully to database: {db.name}")
        print(f"[MongoDB] 📂 Collections available: {db.list_collection_names()}")
        return db
    except Exception as e:
        print(f"[MongoDB] ❌ Failed to connect: {e}")
        raise
