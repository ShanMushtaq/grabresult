"""Security helpers: SSRF protection, input validation, safe fetching.

Every outbound HTTP fetch in GrabResult goes through `safe_fetch`, which:
  * allows only http/https schemes,
  * blocks credentials in URLs,
  * resolves the hostname and refuses private/loopback/link-local/multicast
    addresses (checked on every redirect hop too),
  * caps response size and timeout.
"""
import ipaddress
import re
import socket
from urllib.parse import urlparse

import requests

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB cap per fetched page

_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "javascript"}

_WS_RE = re.compile(r"\s")


def validate_url(url: str) -> str:
    """Return a cleaned URL or raise ValueError if it is not fetchable."""
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    url = url.strip()
    if len(url) > 2048:
        raise ValueError("URL too long")
    if _WS_RE.search(url):
        raise ValueError("URL must not contain whitespace")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or '(none)'}")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")
    return url


def _host_is_public(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def safe_fetch(url: str, timeout: int = 20, headers: dict | None = None) -> requests.Response:
    """Fetch a URL with SSRF protections. Raises ValueError/RuntimeError on problems."""
    url = validate_url(url)
    # Pre-flight check: never even open a connection to a non-public target.
    first_host = urlparse(url).hostname or ""
    if not _host_is_public(first_host):
        raise ValueError(f"Blocked request to non-public address: {first_host}")
    session = requests.Session()
    session.max_redirects = 5
    req_headers = {"User-Agent": "GrabResult/1.0 (research tool)"}
    if headers:
        req_headers.update(headers)
    try:
        resp = session.get(url, timeout=timeout, headers=req_headers, stream=True)
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc

    # Re-check every hop in the redirect chain for SSRF.
    for r in [resp] + list(resp.history):
        host = urlparse(r.url).hostname or ""
        if not _host_is_public(host):
            resp.close()
            raise ValueError(f"Blocked request to non-public address: {host}")

    # Cap download size.
    content = b""
    try:
        for chunk in resp.iter_content(chunk_size=65536):
            content += chunk
            if len(content) > MAX_RESPONSE_BYTES:
                break
    finally:
        resp.close()
    resp._content = content  # noqa: SLF001 - attach capped body to the response
    return resp


_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def safe_filename(name: str) -> str:
    name = _FILENAME_RE.sub("_", name or "file")[:120] or "file"
    return name


def clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))
