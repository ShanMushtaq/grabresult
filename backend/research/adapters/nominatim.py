"""Nominatim (OpenStreetMap) geocoding adapter.

Free, no API key. Usage policy: max 1 request/second, valid HTTP Referer/User-Agent,
data (c) OpenStreetMap contributors, ODbL. Used to turn "city, country" into a
bounding box for POI discovery.
Docs: https://nominatim.org/release-docs/latest/api/Overview/
"""
import time

import requests

from .base import AdapterResult, BaseAdapter

_last_call = 0.0


class NominatimAdapter(BaseAdapter):
    name = "OpenStreetMap Nominatim"
    kind = "geocoding"
    auth_required = "none"
    docs_url = "https://nominatim.org/release-docs/latest/api/Overview/"
    supported_fields = ["city", "country", "bbox", "lat", "lon"]
    limitations = [
        "Rate limit: 1 request/second (usage policy).",
        "Returns places, not business listings — used only for geocoding.",
        "Data (c) OpenStreetMap contributors, ODbL 1.0.",
    ]

    def _polite_get(self, url, params):
        global _last_call
        wait = 1.1 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        resp = requests.get(
            url, params=params,
            headers={"User-Agent": self.user_agent},
            timeout=self.http_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def geocode(self, place: str):
        """Return dict with lat, lon, bbox, display_name or None."""
        try:
            data = self._polite_get(
                "https://nominatim.openstreetmap.org/search",
                {"q": place, "format": "json", "limit": 1},
            )
        except Exception as exc:
            return None, f"Nominatim request failed: {exc}"
        if not data:
            return None, f"No geocoding result for '{place}'"
        item = data[0]
        try:
            bbox = [float(x) for x in item["boundingbox"]]  # s,n,w,e
        except (KeyError, ValueError):
            return None, "Geocoding result had no bounding box"
        return {
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "bbox": {"south": bbox[0], "north": bbox[1], "west": bbox[2], "east": bbox[3]},
            "display_name": item.get("display_name", place),
        }, ""

    def search(self, query: dict) -> AdapterResult:
        place = query.get("city") or query.get("country") or query.get("keywords") or ""
        if not place:
            return AdapterResult(status="failed", message="No place to geocode")
        result, err = self.geocode(place)
        if err:
            return AdapterResult(status="failed", message=err)
        return AdapterResult(records=[result], message=f"Geocoded '{place}'")
