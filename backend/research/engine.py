"""Research engine: runs a plan through source adapters, normalizes, dedupes,
scores and quality-assesses the records, then persists leads.

Runs inside a background thread via jobs.py; reports real progress through
the job row. Never fabricates records: every lead carries source provenance,
and the summary counts come from actual collected data.
"""
import time

from backend.research.adapters.nominatim import NominatimAdapter
from backend.research.adapters.overpass import OverpassAdapter
from backend.research.adapters.website import WebsiteInspectorAdapter
from backend.research.dedupe import dedupe_records, is_similar_name
from backend.research.normalize import normalize_record
from backend.research.quality import assess_quality
from backend.research.scoring import score_lead


def _adapter_instances(config):
    timeout = config.HTTP_TIMEOUT
    ua = config.USER_AGENT
    return {
        "nominatim": NominatimAdapter(http_timeout=timeout, user_agent=ua),
        "overpass": OverpassAdapter(http_timeout=timeout, user_agent=ua),
        "website_inspector": WebsiteInspectorAdapter(http_timeout=timeout, user_agent=ua),
    }


def _source_registry_rows(adapters: dict) -> list:
    rows = []
    for key, ad in adapters.items():
        cap = ad.capability()
        rows.append({
            "name": cap["name"], "adapter": key, "kind": cap["kind"],
            "auth_required": cap["auth_required"], "status": "unknown",
            "last_checked": None, "last_success": None,
            "fields_json": __import__("json").dumps(cap["supported_fields"]),
            "limitations": "; ".join(cap["limitations"]),
            "docs_url": cap["docs_url"],
        })
    return rows


def run_research(db, config, job_id: str, plan: dict, cancel_check):
    """Execute the plan. cancel_check() -> True means the user cancelled."""
    import json

    adapters = _adapter_instances(config)
    for row in _source_registry_rows(adapters):
        db.upsert_source(row)

    def progress(pct, message, status=None):
        fields = {"progress": pct, "progress_message": message}
        if status:
            fields["status"] = status
        db.update_job(job_id, **fields)

    def mark_source(name, ok):
        db.upsert_source({
            "name": name, "adapter": name, "kind": "", "auth_required": "none",
            "status": "available" if ok else "error",
            "last_checked": time.time(),
            "last_success": time.time() if ok else None,
            "fields_json": "[]", "limitations": "", "docs_url": "",
        })

    criteria = plan["criteria"]
    source_log = []
    t0 = time.time()

    progress(2, "Starting research…", status="running")
    db.update_job(job_id, started_at=t0)
    if cancel_check():
        return _finish(db, job_id, "cancelled", "Cancelled by user.", [], source_log, t0)

    # Step 1: geocode city/country -> bbox
    bbox, display_name, geo_lat, geo_lon = None, "", None, None
    place = criteria.get("city") or criteria.get("country")
    if place:
        progress(8, f"Locating '{place}'…")
        geo = adapters["nominatim"].search({"city": place})
        ok = geo.status == "ok"
        mark_source("OpenStreetMap Nominatim", ok)
        source_log.append({"source": "OpenStreetMap Nominatim", "status": geo.status,
                           "message": geo.message})
        if ok:
            bbox = geo.records[0]["bbox"]
            geo_lat, geo_lon = geo.records[0]["lat"], geo.records[0]["lon"]
            display_name = geo.records[0]["display_name"]
            if not criteria.get("city"):
                criteria["city"] = place
        else:
            progress(10, geo.message)
    if cancel_check():
        return _finish(db, job_id, "cancelled", "Cancelled by user.", [], source_log, t0)

    # Step 2: POI discovery
    progress(20, "Discovering businesses in OpenStreetMap…")
    query = {
        "keywords": criteria.get("keywords"), "category": criteria.get("category"),
        "city": criteria.get("city"), "country": criteria.get("country"),
        "bbox": bbox, "lat": geo_lat, "lon": geo_lon,
        "max_records": plan["max_records"],
    }
    disc = adapters["overpass"].search(query)
    mark_source("OpenStreetMap Overpass", disc.status in ("ok", "partial"))
    source_log.append({"source": "OpenStreetMap Overpass", "status": disc.status,
                       "message": disc.message, "errors": disc.errors})
    records = list(disc.records)
    progress(45, f"Discovered {len(records)} candidate businesses.")
    if cancel_check():
        return _finish(db, job_id, "cancelled", "Cancelled by user.", [], source_log, t0)

    # Step 3: website contact enrichment (optional)
    if plan.get("inspect_websites") and records:
        with_www = [r for r in records if r.get("website")]
        cap = min(len(with_www), config.MAX_WEBSITE_INSPECT)
        progress(50, f"Inspecting {cap} business websites for public contact info…")
        inspected = adapters["website_inspector"].search(
            {"websites": [r["website"] for r in with_www[:cap]],
             "max_records": cap})
        mark_source("Website Contact Inspector", inspected.status in ("ok", "partial"))
        source_log.append({"source": "Website Contact Inspector",
                           "status": inspected.status, "message": inspected.message,
                           "errors": inspected.errors})
        by_site = {e["website"]: e for e in inspected.records}
        for r in records:
            info = by_site.get(r.get("website"))
            if not info:
                continue
            if info["emails"] and not r.get("email"):
                r["email"] = info["emails"][0]
            if info["phones"] and not r.get("phone"):
                r["phone"] = info["phones"][0]
            for k, v in info["socials"].items():
                r.setdefault("socials", {}).setdefault(k, v)
            if info["description"] and not r.get("description"):
                r["description"] = info["description"][:300]
    if cancel_check():
        return _finish(db, job_id, "cancelled", "Cancelled by user.", [], source_log, t0)

    # Step 4: normalize -> dedupe -> score -> quality
    progress(70, "Normalizing and de-duplicating…")
    normed = []
    for r in records:
        r = normalize_record(r)
        if not r.get("business_name"):
            continue
        r["provenance"] = {f: r.get("source_name", "") for f in r if r.get(f)}
        normed.append(r)
    unique, dup_info = dedupe_records(normed)

    progress(82, "Scoring and assessing quality…")
    for r in unique:
        r["lead_score"], r["score_reasons"] = score_lead(r, criteria)
        r["verification_status"] = assess_quality(r, criteria)
        r["confidence"] = round(min(0.95, 0.5 + 0.1 * len([v for v in
            [r.get("website"), r.get("email"), r.get("phone"), r.get("address")] if v])), 2)
    # flag similar-name collisions for review
    for i, a in enumerate(unique):
        for b in unique[i + 1:]:
            if is_similar_name(a, b) and a["verification_status"] == "qualified":
                a["verification_status"] = "needs_review"
                a["notes"] = (a.get("notes") or "") + \
                    f" Similar name to '{b.get('business_name')}' — verify identity."

    # Step 5: persist
    progress(90, f"Saving {len(unique)} leads…")
    saved = 0
    for r in unique:
        if cancel_check():
            return _finish(db, job_id, "cancelled", "Cancelled by user.", [], source_log, t0)
        lead_row = {
            "business_name": r.get("business_name", ""),
            "description": r.get("description", ""),
            "industry": r.get("industry", ""),
            "category": r.get("category", ""),
            "website": r.get("website", ""),
            "country": r.get("country", ""),
            "city": r.get("city", ""),
            "address": r.get("address", ""),
            "phone": r.get("phone", ""),
            "email": r.get("email", ""),
            "socials_json": json.dumps(r.get("socials", {})),
            "source_url": r.get("source_url", ""),
            "source_name": r.get("source_name", ""),
            "discovered_at": time.time(),
            "verification_status": r.get("verification_status", "discovered"),
            "confidence": r.get("confidence", 0),
            "lead_score": r.get("lead_score", 0),
            "score_reasons_json": json.dumps(r.get("score_reasons", [])),
            "provenance_json": json.dumps(r.get("provenance", {})),
            "notes": r.get("notes", ""),
        }
        lead_id = db.upsert_lead(lead_row)
        db.link_lead_to_job(job_id, lead_id)
        saved += 1

    final_status = "completed" if unique else "partial"
    note = f"Saved {saved} leads ({len(dup_info)} duplicates merged)."
    return _finish(db, job_id, final_status, note, unique, source_log, t0)


def _finish(db, job_id, status, note, records, source_log, t0):
    import json
    with_www = sum(1 for r in records if r.get("website"))
    with_email = sum(1 for r in records if r.get("email"))
    with_phone = sum(1 for r in records if r.get("phone"))
    by_status, by_city, by_country = {}, {}, {}
    for r in records:
        by_status[r.get("verification_status", "?")] = by_status.get(r.get("verification_status", "?"), 0) + 1
        by_city[r.get("city") or "Unknown"] = by_city.get(r.get("city") or "Unknown", 0) + 1
        by_country[r.get("country") or "Unknown"] = by_country.get(r.get("country") or "Unknown", 0) + 1
    summary = {
        "records_discovered": len(records),
        "unique_businesses": len(records),
        "with_websites": with_www,
        "with_emails": with_email,
        "with_phones": with_phone,
        "by_status": by_status,
        "by_city": by_city,
        "by_country": by_country,
        "note": note,
        "duration_seconds": round(time.time() - t0, 1),
    }
    db.update_job(
        job_id, status=status, progress=100 if status in ("completed", "partial") else 0,
        progress_message=note, finished_at=time.time(),
        summary_json=json.dumps(summary), source_log_json=json.dumps(source_log),
    )
    return summary
