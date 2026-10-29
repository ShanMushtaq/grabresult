"""CSV export (stdlib csv module)."""
import csv
import json
import time

HEADERS = [
    "business_name", "description", "industry", "category", "website",
    "country", "city", "address", "phone", "email", "socials",
    "source_name", "source_url", "discovered_at", "verification_status",
    "confidence", "lead_score", "score_reasons", "notes",
]


def write_csv(leads: list, path: str) -> dict:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        for lead in leads:
            try:
                socials = json.loads(lead.get("socials_json") or "{}")
            except Exception:
                socials = {}
            try:
                reasons = json.loads(lead.get("score_reasons_json") or "[]")
            except Exception:
                reasons = []
            w.writerow({
                "business_name": lead.get("business_name", ""),
                "description": lead.get("description", ""),
                "industry": lead.get("industry", ""),
                "category": lead.get("category", ""),
                "website": lead.get("website", ""),
                "country": lead.get("country", ""),
                "city": lead.get("city", ""),
                "address": lead.get("address", ""),
                "phone": lead.get("phone", ""),
                "email": lead.get("email", ""),
                "socials": "; ".join(f"{k}: {v}" for k, v in socials.items()),
                "source_name": lead.get("source_name", ""),
                "source_url": lead.get("source_url", ""),
                "discovered_at": time.strftime("%Y-%m-%d %H:%M",
                                               time.localtime(lead.get("discovered_at") or 0)),
                "verification_status": lead.get("verification_status", ""),
                "confidence": lead.get("confidence", ""),
                "lead_score": lead.get("lead_score", ""),
                "score_reasons": "; ".join(reasons),
                "notes": lead.get("notes", ""),
            })
    return {"rows": len(leads)}
