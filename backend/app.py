"""GrabResult Flask application: API + static frontend."""
import json
import os
import time

from flask import Flask, jsonify, request, send_file, send_from_directory

from backend import jobs
from backend.config import Config
from backend.db import Database
from backend.exports.csv_export import write_csv
from backend.exports.excel import build_workbook
from backend.imports import importer
from backend.research import planner
from backend.research.quality import STATUS_DESCRIPTIONS
from backend.security import clamp_int, safe_filename

db: Database | None = None
config = Config()


def create_app() -> Flask:
    global db
    app = Flask(__name__, static_folder="../frontend", static_url_path="")
    app.config.from_object(config)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(config.EXPORT_DIR, exist_ok=True)
    db = Database(config.DATABASE_PATH)

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # ---------- health ----------
    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "version": "1.0.0", "time": time.time()})

    # ---------- dashboard ----------
    @app.route("/api/dashboard")
    def dashboard():
        total_leads = db.count_leads()
        jobs_list = db.list_jobs(limit=5)
        by_status: dict = {}
        total, recent = db.list_leads(limit=5)
        for l in db.list_leads(limit=1000)[1]:
            s = l["verification_status"]
            by_status[s] = by_status.get(s, 0) + 1
        return jsonify({
            "total_leads": total_leads,
            "total_jobs": len(db.list_jobs(limit=1000)),
            "by_status": by_status,
            "recent_jobs": [
                {"id": j["id"], "request_text": j["request_text"][:80],
                 "status": j["status"], "progress": j["progress"],
                 "created_at": j["created_at"]} for j in jobs_list
            ],
            "recent_leads": [
                {"id": l["id"], "business_name": l["business_name"],
                 "city": l["city"], "lead_score": l["lead_score"],
                 "verification_status": l["verification_status"]} for l in recent
            ],
        })

    # ---------- research ----------
    @app.route("/api/research/plan", methods=["POST"])
    def research_plan():
        data = request.get_json(force=True, silent=True) or {}
        try:
            plan = planner.build_plan(data.get("request_text", ""),
                                      data.get("filters", {}))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "plan": plan})

    @app.route("/api/research/start", methods=["POST"])
    def research_start():
        data = request.get_json(force=True, silent=True) or {}
        try:
            plan = planner.build_plan(data.get("request_text", ""),
                                      data.get("filters", {}))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        job_id = db.create_job(data.get("request_text", ""), plan)
        jobs.start_job(db, config, job_id, plan)
        return jsonify({"ok": True, "job_id": job_id})

    @app.route("/api/research/jobs")
    def research_jobs():
        limit = clamp_int(request.args.get("limit"), 50, 1, 200)
        out = []
        for j in db.list_jobs(limit=limit):
            out.append({
                "id": j["id"], "request_text": j["request_text"],
                "status": j["status"], "progress": j["progress"],
                "progress_message": j["progress_message"],
                "created_at": j["created_at"], "started_at": j["started_at"],
                "finished_at": j["finished_at"], "error": j["error"],
                "summary": json.loads(j["summary_json"] or "{}"),
            })
        return jsonify({"ok": True, "jobs": out})

    @app.route("/api/research/jobs/<job_id>")
    def research_job(job_id):
        j = db.get_job(job_id)
        if not j:
            return jsonify({"ok": False, "error": "Job not found"}), 404
        leads = db.leads_for_job(job_id)
        return jsonify({"ok": True, "job": {
            "id": j["id"], "request_text": j["request_text"],
            "plan": json.loads(j["plan_json"] or "{}"),
            "status": j["status"], "progress": j["progress"],
            "progress_message": j["progress_message"],
            "created_at": j["created_at"], "started_at": j["started_at"],
            "finished_at": j["finished_at"], "error": j["error"],
            "summary": json.loads(j["summary_json"] or "{}"),
            "source_log": json.loads(j["source_log_json"] or "[]"),
            "leads": leads,
        }})

    @app.route("/api/research/jobs/<job_id>/cancel", methods=["POST"])
    def research_cancel(job_id):
        if jobs.cancel_job(db, job_id):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Job not found or not active"}), 404

    # ---------- leads ----------
    @app.route("/api/leads")
    def leads_list():
        limit = clamp_int(request.args.get("limit"), 50, 1, 500)
        offset = clamp_int(request.args.get("offset"), 0, 0, 100000)
        min_score = request.args.get("min_score")
        total, leads = db.list_leads(
            limit=limit, offset=offset,
            status=request.args.get("status") or None,
            city=request.args.get("city") or None,
            country=request.args.get("country") or None,
            min_score=int(min_score) if min_score not in (None, "") else None,
            search=request.args.get("search") or None,
        )
        return jsonify({"ok": True, "total": total, "leads": leads,
                        "status_descriptions": STATUS_DESCRIPTIONS})

    @app.route("/api/leads/<lead_id>", methods=["GET", "PATCH", "DELETE"])
    def lead_detail(lead_id):
        if request.method == "GET":
            lead = db.get_lead(lead_id)
            if not lead:
                return jsonify({"ok": False, "error": "Lead not found"}), 404
            return jsonify({"ok": True, "lead": lead})
        if request.method == "DELETE":
            db.delete_lead(lead_id)
            return jsonify({"ok": True})
        data = request.get_json(force=True, silent=True) or {}
        lead = db.get_lead(lead_id)
        if not lead:
            return jsonify({"ok": False, "error": "Lead not found"}), 404
        allowed = {"verification_status", "notes", "business_name", "website",
                   "email", "phone", "address", "city", "country", "category",
                   "industry", "description"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if "verification_status" in updates and \
                updates["verification_status"] not in STATUS_DESCRIPTIONS:
            return jsonify({"ok": False, "error": "Invalid status"}), 400
        if updates:
            merged = {**lead, **updates}
            db.upsert_lead(merged)
        return jsonify({"ok": True})

    # ---------- exports ----------
    @app.route("/api/exports", methods=["GET", "POST"])
    def exports():
        if request.method == "GET":
            return jsonify({"ok": True, "exports": db.list_exports()})
        data = request.get_json(force=True, silent=True) or {}
        kind = data.get("kind", "xlsx")
        job_id = data.get("job_id")
        if kind not in ("xlsx", "csv"):
            return jsonify({"ok": False, "error": "kind must be xlsx or csv"}), 400
        leads = db.leads_for_job(job_id) if job_id else db.list_leads(limit=5000)[1]
        if not leads:
            return jsonify({"ok": False, "error": "No leads to export"}), 400
        stamp = time.strftime("%Y%m%d-%H%M%S")
        if kind == "xlsx":
            filename = safe_filename(f"grabresult-export-{stamp}.xlsx")
            path = os.path.join(config.EXPORT_DIR, filename)
            job = db.get_job(job_id) if job_id else None
            summary = json.loads((job or {}).get("summary_json") or "{}")
            source_log = json.loads((job or {}).get("source_log_json") or "[]")
            info = build_workbook(leads, summary, source_log, path)
        else:
            filename = safe_filename(f"grabresult-export-{stamp}.csv")
            path = os.path.join(config.EXPORT_DIR, filename)
            info = write_csv(leads, path)
        export_id = db.record_export({
            "job_id": job_id, "kind": kind, "filename": filename, "path": path,
            "rows": info["rows"], "size_bytes": os.path.getsize(path),
        })
        return jsonify({"ok": True, "export_id": export_id, "filename": filename,
                        "rows": info["rows"]})

    @app.route("/api/exports/<export_id>/download")
    def export_download(export_id):
        rec = db.get_export(export_id)
        if not rec or not os.path.exists(rec["path"]):
            return jsonify({"ok": False, "error": "Export file not found"}), 404
        return send_file(rec["path"], as_attachment=True,
                         download_name=rec["filename"])

    # ---------- imports ----------
    @app.route("/api/imports", methods=["GET"])
    def imports_list():
        return jsonify({"ok": True, "imports": db.list_imports()})

    @app.route("/api/imports/upload", methods=["POST"])
    def import_upload():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "No file uploaded"}), 400
        low = f.filename.lower()
        if not low.endswith((".csv", ".xlsx", ".xlsm")):
            return jsonify({"ok": False, "error": "Upload a .csv or .xlsx file"}), 400
        max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
        data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            return jsonify({"ok": False,
                            "error": f"File too large (max {config.MAX_UPLOAD_MB} MB)"}), 400
        if len(data) == 0:
            return jsonify({"ok": False, "error": "File is empty"}), 400
        fname = safe_filename(f.filename)
        path = os.path.join(config.UPLOAD_DIR,
                            f"{int(time.time())}-{fname}")
        with open(path, "wb") as out:
            out.write(data)
        try:
            headers, rows = importer.read_upload(path, fname)
        except ValueError as exc:
            os.remove(path)
            return jsonify({"ok": False, "error": str(exc)}), 400
        mapping = importer.sniff_columns(headers)
        return jsonify({"ok": True, "upload_path": path, "filename": fname,
                        "headers": headers, "suggested_mapping": mapping,
                        "row_count": len(rows),
                        "available_fields": importer.ALL_FIELDS})

    @app.route("/api/imports/preview", methods=["POST"])
    def import_preview():
        data = request.get_json(force=True, silent=True) or {}
        path = data.get("upload_path", "")
        if not path.startswith(config.UPLOAD_DIR) or not os.path.exists(path):
            return jsonify({"ok": False, "error": "Upload not found"}), 400
        mapping = data.get("mapping") or {}
        try:
            _, rows = importer.read_upload(path, os.path.basename(path))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        clean, skipped, issues = importer.clean_rows(rows, mapping)
        merge = importer.preview_merge(db, clean)
        return jsonify({"ok": True, "clean_count": len(clean),
                        "skipped": skipped, "issues": issues[:20],
                        "merge_preview": {
                            "new_count": merge["new_count"],
                            "existing_count": merge["existing_count"],
                            "existing_sample": merge["already_in_database"][:10],
                        },
                        "sample": clean[:5]})

    @app.route("/api/imports/confirm", methods=["POST"])
    def import_confirm():
        data = request.get_json(force=True, silent=True) or {}
        path = data.get("upload_path", "")
        if not path.startswith(config.UPLOAD_DIR) or not os.path.exists(path):
            return jsonify({"ok": False, "error": "Upload not found"}), 400
        mapping = data.get("mapping") or {}
        try:
            _, rows = importer.read_upload(path, os.path.basename(path))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        clean, skipped, _ = importer.clean_rows(rows, mapping)
        imported, dup_skipped = importer.persist_import(db, clean, only_new=True)
        rid = db.record_import({
            "filename": os.path.basename(path), "rows_total": len(rows),
            "rows_imported": imported, "rows_skipped": skipped + dup_skipped,
            "status": "completed",
            "notes": f"{imported} new leads added; {dup_skipped} already in database.",
        })
        os.remove(path)
        return jsonify({"ok": True, "import_id": rid, "imported": imported,
                        "skipped": skipped + dup_skipped})

    # ---------- sources / settings ----------
    @app.route("/api/sources")
    def sources():
        return jsonify({"ok": True, "sources": db.list_sources()})

    @app.route("/api/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "GET":
            return jsonify({"ok": True, "settings": {
                "max_records_default": db.get_setting("max_records_default", "100"),
                "inspect_websites": db.get_setting("inspect_websites", "1"),
                "max_website_inspect": db.get_setting("max_website_inspect", "40"),
            }})
        data = request.get_json(force=True, silent=True) or {}
        for k in ("max_records_default", "inspect_websites", "max_website_inspect"):
            if k in data:
                db.set_setting(k, str(data[k])[:50])
        # apply to live config
        config.MAX_RECORDS_PER_JOB = clamp_int(
            db.get_setting("max_records_default", "100"), 100, 1, 500)
        config.MAX_WEBSITE_INSPECT = clamp_int(
            db.get_setting("max_website_inspect", "40"), 40, 0, 100)
        return jsonify({"ok": True})

    @app.route("/api/data/clear", methods=["POST"])
    def data_clear():
        db.clear_all_data()
        return jsonify({"ok": True})

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=5000, threaded=True)
