"""Base class for GrabResult source adapters.

Every source adapter declares:
  * name / kind / auth requirements / docs URL
  * which lead fields it can provide
  * a `search()` method returning (records, source_report)

Records are plain dicts with lead fields. source_report describes what happened:
  {"status": "ok|partial|failed|unavailable", "records": n, "message": str,
   "limitations": [...], "errors": [...]}
"""
from dataclasses import dataclass, field


@dataclass
class AdapterResult:
    records: list = field(default_factory=list)
    status: str = "ok"           # ok | partial | failed | unavailable
    message: str = ""
    limitations: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class BaseAdapter:
    name = "base"
    kind = "api"
    auth_required = "none"       # none | user_authorization | paid_key
    docs_url = ""
    supported_fields: list = []
    limitations: list = []

    def __init__(self, http_timeout=20, user_agent="GrabResult/1.0"):
        self.http_timeout = http_timeout
        self.user_agent = user_agent

    def capability(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "auth_required": self.auth_required,
            "docs_url": self.docs_url,
            "supported_fields": self.supported_fields,
            "limitations": self.limitations,
        }

    def search(self, query: dict) -> AdapterResult:
        """query: dict with keys like keywords, city, country, category, bbox, max_records."""
        raise NotImplementedError
