"""Website contact inspector adapter.

Given a business website URL, fetches the homepage plus likely contact/about
pages (same site only) and extracts publicly listed business emails, phone
numbers, addresses and official social links from the HTML.

Safety: all fetches go through security.safe_fetch (SSRF-guarded, size-capped).
Only same-host pages are followed. Page content is treated as untrusted data.
"""
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from backend.security import safe_fetch

from .base import AdapterResult, BaseAdapter

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?[0-9][0-9 .\-()]{6,}[0-9]")
CANDIDATE_PATHS = ["", "/contact", "/contact-us", "/about", "/about-us", "/impressum"]
MAX_PAGES = 4

SOCIAL_HOSTS = {
    "facebook.com": "facebook", "fb.com": "facebook",
    "instagram.com": "instagram", "linkedin.com": "linkedin",
    "twitter.com": "twitter", "x.com": "twitter",
    "youtube.com": "youtube", "tiktok.com": "tiktok",
}

NOISE_EMAILS = {"example.com", "email.com", "sentry.io", "wix.com"}


class WebsiteInspectorAdapter(BaseAdapter):
    name = "Website Contact Inspector"
    kind = "website_extraction"
    auth_required = "none"
    docs_url = ""
    supported_fields = ["email", "phone", "address", "socials", "description"]
    limitations = [
        "Only inspects the business's own public website (homepage + contact/about).",
        "JavaScript-rendered contact details may not be visible in static HTML.",
        "Extracted emails/phones are 'discovered', not verified.",
    ]

    def _pages(self, base_url: str):
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        seen = set()
        for path in CANDIDATE_PATHS[:MAX_PAGES]:
            url = base_url.rstrip("/") + path if path else base_url
            if url in seen:
                continue
            seen.add(url)
            try:
                resp = safe_fetch(url, timeout=self.http_timeout)
            except Exception:
                continue
            if "text/html" not in resp.headers.get("Content-Type", "text/html"):
                continue
            yield url, resp.text, host

    def inspect(self, base_url: str) -> dict:
        emails, phones, socials, texts = set(), set(), {}, []
        for url, html, host in self._pages(base_url):
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            texts.append(text[:2000])
            for m in EMAIL_RE.findall(text):
                domain = m.split("@")[-1].lower()
                if domain not in NOISE_EMAILS and not m.lower().startswith(("noreply@", "no-reply@")):
                    emails.add(m)
            for m in PHONE_RE.findall(text):
                digits = re.sub(r"\D", "", m)
                if 7 <= len(digits) <= 15:
                    phones.add(m.strip())
            for a in soup.find_all("a", href=True):
                href = a["href"]
                h = (urlparse(href).hostname or "").lower()
                for shost, sname in SOCIAL_HOSTS.items():
                    if h == shost or h.endswith("." + shost):
                        socials.setdefault(sname, href)
            # also catch mailto: links
            for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
                addr = a["href"].split(":", 1)[1].split("?")[0]
                if EMAIL_RE.fullmatch(addr):
                    emails.add(addr)
        return {
            "emails": sorted(emails)[:5],
            "phones": sorted(phones)[:5],
            "socials": socials,
            "description": " ".join(texts)[:500],
        }

    def search(self, query: dict) -> AdapterResult:
        # This adapter enriches known websites rather than discovering new ones.
        websites = query.get("websites", [])
        if not websites:
            return AdapterResult(
                status="unavailable",
                message="Website inspector needs website URLs (from discovery step).",
            )
        enriched = []
        errors = []
        for site in websites[: int(query.get("max_records", 40))]:
            try:
                info = self.inspect(site)
                enriched.append({"website": site, **info})
            except Exception as exc:
                errors.append(f"{site}: {exc}")
        status = "ok" if enriched else "failed"
        return AdapterResult(
            records=enriched, status=status,
            message=f"Inspected {len(enriched)} websites.",
            errors=errors,
        )
