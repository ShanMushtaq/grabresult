"""CSV/XLSX import: validation, column mapping, normalization, dedupe, merge preview.

Never silently discards master records: imports only ADD leads (or update empty
fields on exact duplicates); nothing existing is deleted.
"""
import csv
import io
import time

from openpyxl import load_workbook

from backend.research.dedupe import dedupe_records, is_duplicate
from backend.research.normalize import normalize_record
from backend.research.quality import assess_quality
from backend.research.scoring import score_lead

FIELD_ALIASES = {
    "business_name": {"business name", "name", "company", "company name", "business"},
    "description": {"description", "desc", "about"},
    "industry": {"industry", "sector"},
    "category": {"category", "type", "business type"},
    "website": {"website", "url", "site", "web"},
    "country": {"country"},
    "city": {"city", "town"},
    "address": {"address", "street address", "location"},
    "phone": {"phone", "telephone", "tel", "mobile"},
    "email": {"email", "e-mail", "mail"},
}

ALL_FIELDS = ["business_name", "description", "industry", "category", "website",
              "country", "city", "address", "phone", "email"]


def sniff_columns(headers: list) -> dict:
    """Map raw header names -> canonical field names (best-effort)."""
    mapping = {}
    for h in headers:
        hl = (h or "").strip().lower()
        for field, aliases in FIELD_ALIASES.items():
            if hl == field or hl in aliases:
                mapping[h] = field
                break
    return mapping


def read_upload(path: str, filename: str) -> tuple[list, list]:
    """Return (headers, rows as list of dicts). Raises ValueError on bad files."""
    low = filename.lower()
    if low.endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except Exception:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            headers = reader.fieldnames or []
            rows = [dict(r) for r in reader]
        return headers, rows
    if low.endswith((".xlsx", ".xlsm")):
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise ValueError("The Excel file is empty.")
        headers = [str(c) if c is not None else "" for c in rows[0]]
        data = [dict(zip(headers, [c if c is not None else "" for c in r])) for r in rows[1:]]
        return headers, data
    raise ValueError("Unsupported file type. Upload a .csv or .xlsx file.")


def clean_rows(rows: list, mapping: dict, criteria: dict | None = None):
    """Normalize + validate rows. Returns (clean_leads, skipped, issues)."""
    criteria = criteria or {}
    clean, skipped, issues = [], 0, []
    seen_new = []
    for i, raw in enumerate(rows, start=2):  # 1-based incl. header
        rec = {field: str(raw.get(src, "") or "").strip()
               for src, field in mapping.items() if field}
        rec = normalize_record(rec)
        if not rec.get("business_name"):
            skipped += 1
            issues.append(f"Row {i}: skipped — no business name.")
            continue
        # dedupe within the upload itself
        if any(is_duplicate(rec, s) for s in seen_new):
            skipped += 1
            issues.append(f"Row {i}: skipped — duplicate of another row in this file.")
            continue
        seen_new.append(rec)
        rec["lead_score"], rec["score_reasons"] = score_lead(rec, criteria)
        rec["verification_status"] = assess_quality(rec, criteria)
        rec["confidence"] = 0.5
        rec["source_name"] = "CSV/XLSX import"
        rec["discovered_at"] = time.time()
        clean.append(rec)
    # dedupe merged set once more (catches near-identical rows)
    clean, _ = dedupe_records(clean)
    return clean, skipped, issues


def preview_merge(db, clean_leads: list) -> dict:
    """Compare upload against the master DB: how many are new vs already present."""
    new, existing = [], []
    for rec in clean_leads:
        cands = db.find_duplicate_candidates(
            rec.get("business_name", "")[:24].lower(),
            (rec.get("website") or "").split("//")[-1].split("/")[0],
        )
        if any(is_duplicate(rec, c) for c in cands):
            existing.append(rec["business_name"])
        else:
            new.append(rec)
    return {"new": new, "already_in_database": existing,
            "new_count": len(new), "existing_count": len(existing)}


def persist_import(db, clean_leads: list, only_new: bool = True) -> tuple[int, int]:
    """Insert leads; returns (imported, skipped_as_existing)."""
    import json
    imported, skipped = 0, 0
    for rec in clean_leads:
        if only_new:
            cands = db.find_duplicate_candidates(
                rec.get("business_name", "")[:24].lower(),
                (rec.get("website") or "").split("//")[-1].split("/")[0],
            )
            if any(is_duplicate(rec, c) for c in cands):
                skipped += 1
                continue
        db.upsert_lead({
            "business_name": rec.get("business_name", ""),
            "description": rec.get("description", ""),
            "industry": rec.get("industry", ""),
            "category": rec.get("category", ""),
            "website": rec.get("website", ""),
            "country": rec.get("country", ""),
            "city": rec.get("city", ""),
            "address": rec.get("address", ""),
            "phone": rec.get("phone", ""),
            "email": rec.get("email", ""),
            "socials_json": json.dumps(rec.get("socials", {})),
            "source_url": "", "source_name": rec.get("source_name", "import"),
            "discovered_at": rec.get("discovered_at", time.time()),
            "verification_status": rec.get("verification_status", "discovered"),
            "confidence": rec.get("confidence", 0.5),
            "lead_score": rec.get("lead_score", 0),
            "score_reasons_json": json.dumps(rec.get("score_reasons", [])),
            "provenance_json": json.dumps({"import": True}),
            "notes": "",
        })
        imported += 1
    return imported, skipped
