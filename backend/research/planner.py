"""Research planner: turns a natural-language request + optional filters into a
structured research plan. Fully deterministic (no AI model required) so the
core product works offline from any model API.

The plan is shown to the user before execution and stored with the job.
"""
import re

CATEGORY_HINTS = {
    "restaurant": "restaurant", "restaurants": "restaurant",
    "cafe": "cafe", "cafes": "cafe", "coffee": "cafe",
    "bar": "bar", "bars": "bar", "pub": "pub", "pubs": "pub",
    "hotel": "hotel", "hotels": "hotel", "hostel": "hostel",
    "shop": "shop", "shops": "shop", "store": "shop", "stores": "shop",
    "retail": "retail", "boutique": "retail", "clothing": "retail",
    "bakery": "bakery", "bakeries": "bakery",
    "pharmacy": "pharmacy", "pharmacies": "pharmacy",
    "gym": "gym", "gyms": "gym", "fitness": "fitness",
    "salon": "salon", "salons": "salon", "barber": "salon",
    "dentist": "dentist", "clinic": "clinic", "doctor": "clinic",
    "agency": "agency", "agencies": "agency",
    "startup": "startup", "startups": "startup",
    "saas": "software", "software": "software",
    "fast food": "fast food",
}

OUTPUT_FIELD_ALIASES = {
    "email": "email", "emails": "email",
    "phone": "phone", "phones": "phone", "telephone": "phone",
    "website": "website", "websites": "website",
    "address": "address", "addresses": "address",
    "social": "socials", "socials": "socials",
    "rating": "rating", "ratings": "rating",
}

DEFAULT_OUTPUT_FIELDS = [
    "business_name", "category", "website", "email", "phone",
    "address", "city", "country", "socials", "source_url",
]


def _detect_category(text: str) -> str:
    low = text.lower()
    for hint, cat in CATEGORY_HINTS.items():
        if re.search(r"\b" + re.escape(hint) + r"s?\b", low):
            return cat
    return ""


def _detect_output_fields(text: str) -> list:
    low = text.lower()
    fields = ["business_name"]
    for hint, field in OUTPUT_FIELD_ALIASES.items():
        if hint in low and field not in fields:
            fields.append(field)
    for f in ("category", "city", "country", "address", "source_url"):
        if f not in fields:
            fields.append(f)
    return fields


def build_plan(request_text: str, filters: dict | None = None) -> dict:
    filters = filters or {}
    text = (request_text or "").strip()
    if len(text) < 10:
        raise ValueError("Please describe what you want to research in a little more detail.")

    category = filters.get("category") or _detect_category(text)
    output_fields = filters.get("output_fields") or _detect_output_fields(text)
    max_records = int(filters.get("max_records") or 100)
    max_records = max(1, min(max_records, 500))

    plan = {
        "objective": text[:500],
        "criteria": {
            "keywords": filters.get("keywords") or "",
            "country": filters.get("country") or "",
            "city": filters.get("city") or "",
            "industry": filters.get("industry") or "",
            "category": category,
            "require_website": bool(filters.get("require_website")),
            "require_contact": bool(filters.get("require_contact")),
        },
        "sources": ["overpass", "nominatim", "website_inspector"],
        "output_fields": output_fields,
        "max_records": max_records,
        "inspect_websites": bool(filters.get("inspect_websites", True)),
        "limitations": [
            "Discovery uses OpenStreetMap POI data — only mapped businesses appear.",
            "Contact details come from OSM tags and the business's own public website.",
            "No paid search or data APIs are used; results reflect public sources only.",
        ],
    }
    return plan
