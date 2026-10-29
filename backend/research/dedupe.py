"""Duplicate detection for GrabResult.

Two records are duplicates when they share a strong identifier:
  1. same website domain, or
  2. same normalized name key AND (same city OR same phone digits)

Similar names alone NEVER merge records — that only flags 'needs review'.
"""
import difflib

from .normalize import domain_of, name_key, normalize_phone


def is_duplicate(a: dict, b: dict) -> bool:
    da, db = domain_of(a.get("website", "")), domain_of(b.get("website", ""))
    if da and db and da == db:
        return True
    ka, kb = name_key(a.get("business_name", "")), name_key(b.get("business_name", ""))
    if ka and kb and ka == kb:
        pa, pb = normalize_phone(a.get("phone", "")), normalize_phone(b.get("phone", ""))
        if pa and pb and pa == pb:
            return True
        ca, cb = (a.get("city") or "").lower(), (b.get("city") or "").lower()
        if ca and cb and ca == cb:
            return True
    return False


def is_similar_name(a: dict, b: dict, threshold: float = 0.85) -> bool:
    ka, kb = name_key(a.get("business_name", "")), name_key(b.get("business_name", ""))
    if not ka or not kb or ka == kb:
        return False
    return difflib.SequenceMatcher(None, ka, kb).ratio() >= threshold


def merge_records(primary: dict, duplicate: dict) -> dict:
    """Merge duplicate into primary, filling empty fields and keeping provenance."""
    prov = dict(primary.get("provenance") or {})
    for field in ("website", "phone", "email", "address", "description",
                  "category", "industry", "city", "country"):
        if not primary.get(field) and duplicate.get(field):
            primary[field] = duplicate[field]
            prov[field] = duplicate.get("source_name", "merged")
    psoc = dict(primary.get("socials") or {})
    for k, v in (duplicate.get("socials") or {}).items():
        psoc.setdefault(k, v)
    primary["socials"] = psoc
    srcs = set((primary.get("notes") or "").split("; ") if primary.get("notes") else set())
    if duplicate.get("source_name"):
        srcs.add(f"merged from: {duplicate['source_name']}")
    primary["notes"] = "; ".join(s for s in srcs if s)
    primary["provenance"] = prov
    return primary


def dedupe_records(records: list) -> tuple[list, list]:
    """Return (unique_records, duplicate_pairs_info). Mutates via merge."""
    unique, dup_info = [], []
    for rec in records:
        match = next((u for u in unique if is_duplicate(u, rec)), None)
        if match:
            merge_records(match, rec)
            dup_info.append((rec.get("business_name"), match.get("business_name")))
            rec["_duplicate_of"] = match.get("business_name")
        else:
            unique.append(rec)
    return unique, dup_info
