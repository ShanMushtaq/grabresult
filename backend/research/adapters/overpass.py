"""Overpass API (OpenStreetMap) POI discovery adapter.

Free, no API key. Queries OpenStreetMap for mapped businesses (nodes/ways with
names) by category tag inside a bounding box. Respects the public instance's
fair-use policy: small result caps, timeouts, single instance, backoff on 429/504.
Docs: https://wiki.openstreetmap.org/wiki/Overpass_API
"""
import time
from urllib.parse import urlparse

import requests

from .base import AdapterResult, BaseAdapter

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# user keyword/category -> OSM tag filters (each a list of (key, value) pairs)
CATEGORY_TAGS = {
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "coffee": [("amenity", "cafe")],
    "bar": [("amenity", "bar")],
    "pub": [("amenity", "pub")],
    "fast food": [("amenity", "fast_food")],
    "bakery": [("shop", "bakery")],
    "hotel": [("tourism", "hotel")],
    "hostel": [("tourism", "hostel")],
    "guest house": [("tourism", "guest_house")],
    "shop": [("shop", None)],
    "retail": [("shop", None)],
    "clothes": [("shop", "clothes")],
    "supermarket": [("shop", "supermarket")],
    "convenience": [("shop", "convenience")],
    "pharmacy": [("amenity", "pharmacy")],
    "bank": [("amenity", "bank")],
    "dentist": [("amenity", "dentist")],
    "doctor": [("amenity", "doctors")],
    "clinic": [("amenity", "clinic")],
    "gym": [("leisure", "fitness_centre")],
    "fitness": [("leisure", "fitness_centre")],
    "salon": [("shop", "hairdresser")],
    "hairdresser": [("shop", "hairdresser")],
    "beauty": [("shop", "beauty")],
    "car": [("shop", "car")],
    "car repair": [("shop", "car_repair")],
    "school": [("amenity", "school")],
    "university": [("amenity", "university")],
    "office": [("office", None)],
    "company": [("office", None)],
    "it": [("office", "it")],
    "coworking": [("office", "coworking")],
    "agency": [("office", None)],
}


def tags_for(category: str, keywords: str):
    text = f"{category or ''} {keywords or ''}".lower()
    for label, tags in CATEGORY_TAGS.items():
        if label in text:
            return tags
    return [("shop", None), ("amenity", None), ("office", None), ("tourism", None)]


class OverpassAdapter(BaseAdapter):
    name = "OpenStreetMap Overpass"
    kind = "poi_directory"
    auth_required = "none"
    docs_url = "https://wiki.openstreetmap.org/wiki/Overpass_API"
    supported_fields = [
        "business_name", "category", "website", "phone", "address",
        "city", "country", "lat", "lon", "source_url",
    ]
    limitations = [
        "Only businesses mapped in OpenStreetMap; coverage varies by city.",
        "OSM rarely stores emails; websites/phones present only if mapped.",
        "Public instance fair-use: small queries, backoff on 429/504.",
        "Data (c) OpenStreetMap contributors, ODbL 1.0 — attribution required.",
    ]

    def _query(self, ql: str, timeout: int):
        last_err = ""
        for endpoint in ENDPOINTS:
            try:
                resp = requests.post(
                    endpoint, data={"data": ql},
                    headers={"User-Agent": self.user_agent},
                    timeout=timeout + 15,
                )
                if resp.status_code in (429, 504):
                    last_err = f"{endpoint}: HTTP {resp.status_code} (rate limited)"
                    time.sleep(3)
                    continue
                resp.raise_for_status()
                return resp.json(), ""
            except Exception as exc:
                last_err = f"{endpoint}: {exc}"
        return None, last_err

    def search(self, query: dict) -> AdapterResult:
        lat, lon = query.get("lat"), query.get("lon")
        bbox = query.get("bbox")
        if lat is None and not bbox:
            return AdapterResult(
                status="failed",
                message="Overpass needs a location (geocode the city first).",
            )
        max_records = min(int(query.get("max_records", 100)), 500)
        tags = tags_for(query.get("category", ""), query.get("keywords", ""))
        radius = int(query.get("radius_m", 20000))

        def build_ql(area: str) -> str:
            clauses = []
            for key, value in tags:
                filt = f'["{key}"]' if value is None else f'["{key}"="{value}"]'
                clauses.append(f"nwr{filt}{area};")
            return "[out:json][timeout:25];(" + "".join(clauses) + ");out center tags;"

        data, err, used = None, "", ""
        # Shrink the search area on timeout/rate-limit: at most 3 attempts.
        for attempt in range(3):
            if lat is not None:
                area = f"(around:{radius},{lat},{lon})"
                used = f"{radius / 1000:.0f} km around city center"
            else:
                area = (f"({bbox['south']},{bbox['west']},"
                        f"{bbox['north']},{bbox['east']})")
                used = "bounding box"
            data, err = self._query(build_ql(area), 25)
            if not err:
                break
            if "timed out" in err or "429" in err or "504" in err:
                radius = max(2000, radius // 2)  # shrink and retry once more
                continue
            break

        if err:
            return AdapterResult(
                status="failed",
                message=f"Overpass query failed after retries ({used}): {err[:160]}",
            )

        records = []
        for el in data.get("elements", []):
            tags_d = el.get("tags", {})
            name = tags_d.get("name")
            if not name:
                continue
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            website = tags_d.get("website") or tags_d.get("contact:website") or ""
            if website and not website.startswith(("http://", "https://")):
                website = "https://" + website
            addr_parts = [
                tags_d.get("addr:housenumber", ""), tags_d.get("addr:street", ""),
                tags_d.get("addr:city", ""), tags_d.get("addr:postcode", ""),
            ]
            address = " ".join(p for p in addr_parts if p).strip()
            osm_url = f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}"
            records.append({
                "business_name": name,
                "description": "",
                "industry": "",
                "category": query.get("category", "") or tags_d.get("shop") or tags_d.get("amenity") or "",
                "website": website,
                "country": query.get("country", ""),
                "city": tags_d.get("addr:city") or query.get("city", ""),
                "address": address,
                "phone": tags_d.get("phone") or tags_d.get("contact:phone") or "",
                "email": tags_d.get("email") or tags_d.get("contact:email") or "",
                "socials": {},
                "source_url": osm_url,
                "source_name": self.name,
                "lat": lat, "lon": lon,
                "confidence": 0.6,
                "notes": "Mapped in OpenStreetMap; fields reflect OSM tags only.",
            })
            if len(records) >= max_records:
                break

        status = "ok" if records else "partial"
        msg = f"Found {len(records)} named places in OpenStreetMap."
        if not records:
            msg = ("Overpass returned no named places for these filters. "
                   "Try a broader category or a larger city.")
        return AdapterResult(records=records, status=status, message=msg)
