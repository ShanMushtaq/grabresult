"""Data-quality statuses for leads.

  discovered   - found by a source adapter, not yet assessed
  qualified    - matches the research criteria and has usable contact info
  verified     - a human (or a verified import) confirmed the key fields
  needs_review - conflicting or thin data; similar-name collision; source error
  duplicate    - merged into another record (kept for audit, hidden by default)
  excluded     - dropped by a filter (e.g. no website when website required)
"""
STATUSES = ["discovered", "qualified", "verified", "needs_review", "duplicate", "excluded"]

STATUS_DESCRIPTIONS = {
    "discovered": "Found by a source. Not yet assessed against your criteria.",
    "qualified": "Matches your criteria and has usable public contact info (website, email or phone).",
    "verified": "Key fields were confirmed — by you, or from a trusted import. A high score never implies this.",
    "needs_review": "Thin or conflicting data (e.g. two similar names, missing location). Check before outreach.",
    "duplicate": "Merged into another record. Kept for audit only.",
    "excluded": "Did not pass your filters (e.g. website required but missing).",
}


def assess_quality(lead: dict, criteria: dict) -> str:
    """Decide discovered/qualified/needs_review/excluded for a fresh lead."""
    # Exclusion filters first
    if criteria.get("require_website") and not lead.get("website"):
        return "excluded"
    if criteria.get("require_contact") and not (lead.get("email") or lead.get("phone")):
        return "excluded"

    has_contact = bool(lead.get("website") or lead.get("email") or lead.get("phone"))
    has_location = bool(lead.get("city") or lead.get("address"))
    has_name = bool(lead.get("business_name"))

    if not has_name:
        return "excluded"
    if has_contact and has_location:
        return "qualified"
    if has_contact or has_location:
        return "needs_review"
    return "discovered"
