"""GrabResult configuration. All secrets come from environment variables; see .env.example."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Config:
    SECRET_KEY = os.environ.get("GRABRESULT_SECRET_KEY", "dev-only-change-me")
    DATABASE_PATH = os.environ.get(
        "GRABRESULT_DB_PATH", os.path.join(BASE_DIR, "instance", "grabresult.db")
    )
    UPLOAD_DIR = os.environ.get(
        "GRABRESULT_UPLOAD_DIR", os.path.join(BASE_DIR, "instance", "uploads")
    )
    EXPORT_DIR = os.environ.get(
        "GRABRESULT_EXPORT_DIR", os.path.join(BASE_DIR, "instance", "exports")
    )
    MAX_UPLOAD_MB = int(os.environ.get("GRABRESULT_MAX_UPLOAD_MB", "10"))
    # Research politeness / safety limits
    HTTP_TIMEOUT = int(os.environ.get("GRABRESULT_HTTP_TIMEOUT", "20"))
    MAX_RETRIES = int(os.environ.get("GRABRESULT_MAX_RETRIES", "2"))
    REQUESTS_PER_SECOND = float(os.environ.get("GRABRESULT_RPS", "1.0"))
    MAX_RECORDS_PER_JOB = int(os.environ.get("GRABRESULT_MAX_RECORDS", "500"))
    MAX_WEBSITE_INSPECT = int(os.environ.get("GRABRESULT_MAX_WEBSITE_INSPECT", "40"))
    USER_AGENT = os.environ.get("GRABRESULT_USER_AGENT", "GrabResult/1.0")
    JSON_SORT_KEYS = False
