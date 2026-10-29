"""Data normalization helpers: names, URLs, emails, phones, places, socials."""
import re
from urllib.parse import urlparse

LEGAL_SUFFIXES = re.compile(
    r"\b(ltd|limited|inc|incorporated|llc|plc|gmbh|corp|corporation|co|company"
    r"|sarl|sas|bv|pty|aps|ab|oy|ug|eurl|sl|s\.r\.l|s\.a\.|a\/s)\.?$",
    re.I,
)

COUNTRY_ALIASES = {
    "uk": "United Kingdom", "u.k.": "United Kingdom", "england": "United Kingdom",
    "usa": "United States", "u.s.": "United States", "u.s.a.": "United States",
    "uae": "United Arab Emirates",
}


def normalize_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name


def name_key(name: str) -> str:
    """Canonical key for duplicate comparison: lowercase, no legal suffix, alnum only."""
    n = normalize_name(name).lower()
    n = LEGAL_SUFFIXES.sub("", n).strip()
    n = re.sub(r"[^a-z0-9]", "", n)
    return n


def normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        p = urlparse(url)
        host = p.hostname or ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path.rstrip("/") if p.path not in ("", "/") else ""
        return f"{p.scheme.lower()}://{host}{path}"
    except Exception:
        return url


def domain_of(url: str) -> str:
    try:
        host = urlparse(normalize_url(url)).hostname or ""
        return host.lower()
    except Exception:
        return ""


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits or not (7 <= len(digits) <= 15):
        return ""
    return "+" + digits if (phone or "").strip().startswith("+") else digits


def normalize_country(country: str) -> str:
    c = (country or "").strip()
    return COUNTRY_ALIASES.get(c.lower(), c)


def normalize_city(city: str) -> str:
    return re.sub(r"\s+", " ", (city or "").strip()).title()


def normalize_socials(socials: dict) -> dict:
    out = {}
    for k, v in (socials or {}).items():
        k = k.lower().strip()
        v = normalize_url(v) if v else ""
        if v:
            out[k] = v
    return out


def normalize_record(rec: dict) -> dict:
    """Normalize a raw adapter record in place and return it."""
    rec["business_name"] = normalize_name(rec.get("business_name", ""))
    rec["website"] = normalize_url(rec.get("website", ""))
    rec["email"] = normalize_email(rec.get("email", ""))
    rec["phone"] = normalize_phone(rec.get("phone", ""))
    rec["country"] = normalize_country(rec.get("country", ""))
    rec["city"] = normalize_city(rec.get("city", ""))
    rec["category"] = (rec.get("category") or "").strip().title()
    rec["industry"] = (rec.get("industry") or "").strip().title()
    rec["address"] = re.sub(r"\s+", " ", (rec.get("address") or "").strip())
    rec["socials"] = normalize_socials(rec.get("socials") or {})
    return rec
