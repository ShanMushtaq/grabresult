"""SQLite persistence layer for GrabResult.

Tables:
  jobs      - research jobs and their lifecycle (queued/running/completed/partial/failed/cancelled)
  leads     - discovered business records (the Leads Database)
  job_leads - which leads belong to which job
  sources   - source-adapter registry rows (availability cache)
  imports   - uploaded import batches
  exports   - generated export files
  settings  - simple key/value settings
"""
import json
import os
import sqlite3
import threading
import time
import uuid

_lock = threading.RLock()


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    request_text TEXT NOT NULL,
    plan_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL NOT NULL DEFAULT 0,
    progress_message TEXT DEFAULT '',
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL,
    error TEXT DEFAULT '',
    summary_json TEXT NOT NULL DEFAULT '{}',
    source_log_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    business_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    category TEXT DEFAULT '',
    website TEXT DEFAULT '',
    country TEXT DEFAULT '',
    city TEXT DEFAULT '',
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    socials_json TEXT NOT NULL DEFAULT '{}',
    source_url TEXT DEFAULT '',
    source_name TEXT DEFAULT '',
    discovered_at REAL NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'discovered',
    confidence REAL NOT NULL DEFAULT 0,
    lead_score INTEGER NOT NULL DEFAULT 0,
    score_reasons_json TEXT NOT NULL DEFAULT '[]',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS job_leads (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    lead_id TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, lead_id)
);
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    adapter TEXT NOT NULL,
    kind TEXT NOT NULL,
    auth_required TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL DEFAULT 'unknown',
    last_checked REAL,
    last_success REAL,
    fields_json TEXT NOT NULL DEFAULT '[]',
    limitations TEXT DEFAULT '',
    docs_url TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS imports (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    created_at REAL NOT NULL,
    rows_total INTEGER NOT NULL DEFAULT 0,
    rows_imported INTEGER NOT NULL DEFAULT 0,
    rows_skipped INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed',
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS exports (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at REAL NOT NULL,
    rows INTEGER NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_leads_name ON leads(business_name);
CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(verification_status);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with _lock, _connect(path) as conn:
            conn.executescript(SCHEMA)

    def _run(self, fn):
        with _lock:
            conn = _connect(self.path)
            try:
                result = fn(conn)
                conn.commit()
                return result
            finally:
                conn.close()

    # ---- jobs -------------------------------------------------------------
    def create_job(self, request_text: str, plan: dict) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()

        def _op(conn):
            conn.execute(
                "INSERT INTO jobs (id, request_text, plan_json, status, created_at)"
                " VALUES (?,?,?,?,?)",
                (job_id, request_text, json.dumps(plan), "queued", now),
            )

        self._run(_op)
        return job_id

    def update_job(self, job_id: str, **fields):
        def _op(conn):
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE jobs SET {sets} WHERE id=?", (*fields.values(), job_id)
            )

        self._run(_op)

    def get_job(self, job_id: str):
        def _op(conn):
            return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

        row = self._run(_op)
        return dict(row) if row else None

    def list_jobs(self, limit: int = 100):
        def _op(conn):
            return conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

        return [dict(r) for r in self._run(_op)]

    # ---- leads ------------------------------------------------------------
    def upsert_lead(self, lead: dict) -> str:
        lead_id = lead.get("id") or uuid.uuid4().hex[:12]
        lead["id"] = lead_id
        cols = [
            "id", "business_name", "description", "industry", "category", "website",
            "country", "city", "address", "phone", "email", "socials_json",
            "source_url", "source_name", "discovered_at", "verification_status",
            "confidence", "lead_score", "score_reasons_json", "provenance_json", "notes",
        ]
        vals = [lead.get(c, "") for c in cols]

        def _op(conn):
            conn.execute(
                f"INSERT OR REPLACE INTO leads ({','.join(cols)})"
                f" VALUES ({','.join('?' * len(cols))})",
                vals,
            )

        self._run(_op)
        return lead_id

    def link_lead_to_job(self, job_id: str, lead_id: str):
        def _op(conn):
            conn.execute(
                "INSERT OR IGNORE INTO job_leads (job_id, lead_id) VALUES (?,?)",
                (job_id, lead_id),
            )

        self._run(_op)

    def get_lead(self, lead_id: str):
        def _op(conn):
            return conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()

        row = self._run(_op)
        return dict(row) if row else None

    def list_leads(self, limit=200, offset=0, status=None, city=None, country=None,
                   min_score=None, search=None):
        clauses, params = [], []
        if status:
            clauses.append("verification_status=?"); params.append(status)
        if city:
            clauses.append("city LIKE ?"); params.append(f"%{city}%")
        if country:
            clauses.append("country LIKE ?"); params.append(f"%{country}%")
        if min_score is not None:
            clauses.append("lead_score>=?"); params.append(min_score)
        if search:
            clauses.append("(business_name LIKE ? OR category LIKE ? OR industry LIKE ?)")
            params += [f"%{search}%"] * 3
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        def _op(conn):
            total = conn.execute(f"SELECT COUNT(*) c FROM leads {where}", params).fetchone()["c"]
            rows = conn.execute(
                f"SELECT * FROM leads {where} ORDER BY lead_score DESC, discovered_at DESC"
                " LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
            return total, [dict(r) for r in rows]

        return self._run(_op)

    def leads_for_job(self, job_id: str):
        def _op(conn):
            return conn.execute(
                "SELECT l.* FROM leads l JOIN job_leads j ON j.lead_id=l.id"
                " WHERE j.job_id=? ORDER BY l.lead_score DESC",
                (job_id,),
            ).fetchall()

        return [dict(r) for r in self._run(_op)]

    def delete_lead(self, lead_id: str):
        def _op(conn):
            conn.execute("DELETE FROM job_leads WHERE lead_id=?", (lead_id,))
            conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))

        self._run(_op)

    def count_leads(self) -> int:
        def _op(conn):
            return conn.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]

        return self._run(_op)

    def find_duplicate_candidates(self, name_norm: str, domain: str):
        """Return leads whose normalized name or website domain matches."""
        def _op(conn):
            rows = conn.execute(
                "SELECT * FROM leads WHERE website LIKE ? OR business_name LIKE ?",
                (f"%{domain}%" if domain else "\x00", f"%{name_norm[:24]}%"),
            ).fetchall()
            return [dict(r) for r in rows]

        return self._run(_op)

    # ---- sources ----------------------------------------------------------
    def upsert_source(self, row: dict):
        cols = ["name", "adapter", "kind", "auth_required", "status", "last_checked",
                "last_success", "fields_json", "limitations", "docs_url"]

        def _op(conn):
            conn.execute(
                f"INSERT OR REPLACE INTO sources ({','.join(cols)})"
                f" VALUES ({','.join('?' * len(cols))})",
                [row.get(c) for c in cols],
            )

        self._run(_op)

    def list_sources(self):
        def _op(conn):
            return conn.execute("SELECT * FROM sources ORDER BY name").fetchall()

        return [dict(r) for r in self._run(_op)]

    # ---- imports / exports ------------------------------------------------
    def record_import(self, row: dict) -> str:
        rid = uuid.uuid4().hex[:12]
        row["id"] = rid

        def _op(conn):
            conn.execute(
                "INSERT INTO imports (id, filename, created_at, rows_total,"
                " rows_imported, rows_skipped, status, notes)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (rid, row["filename"], row.get("created_at", time.time()),
                 row.get("rows_total", 0), row.get("rows_imported", 0),
                 row.get("rows_skipped", 0), row.get("status", "completed"),
                 row.get("notes", "")),
            )

        self._run(_op)
        return rid

    def list_imports(self, limit=50):
        def _op(conn):
            return conn.execute(
                "SELECT * FROM imports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

        return [dict(r) for r in self._run(_op)]

    def record_export(self, row: dict) -> str:
        rid = uuid.uuid4().hex[:12]

        def _op(conn):
            conn.execute(
                "INSERT INTO exports (id, job_id, kind, filename, path, created_at,"
                " rows, size_bytes) VALUES (?,?,?,?,?,?,?,?)",
                (rid, row.get("job_id"), row["kind"], row["filename"], row["path"],
                 time.time(), row.get("rows", 0), row.get("size_bytes", 0)),
            )

        self._run(_op)
        return rid

    def list_exports(self, limit=50):
        def _op(conn):
            return conn.execute(
                "SELECT * FROM exports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

        return [dict(r) for r in self._run(_op)]

    def get_export(self, export_id: str):
        def _op(conn):
            return conn.execute("SELECT * FROM exports WHERE id=?", (export_id,)).fetchone()

        row = self._run(_op)
        return dict(row) if row else None

    # ---- settings ---------------------------------------------------------
    def get_setting(self, key: str, default: str = "") -> str:
        def _op(conn):
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

        return self._run(_op)

    def set_setting(self, key: str, value: str):
        def _op(conn):
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                         (key, value))

        self._run(_op)

    def clear_all_data(self):
        def _op(conn):
            for t in ("job_leads", "leads", "jobs", "imports", "exports"):
                conn.execute(f"DELETE FROM {t}")

        self._run(_op)
