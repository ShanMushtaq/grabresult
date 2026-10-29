"""Transparent, rule-based lead scoring.

Score is 0-100 from additive rules; every rule that fires is recorded in
`score_reasons` so the user can see exactly why a lead scored what it did.
Scoring NEVER implies verification: verification_status is separate.
"""
from .normalize import domain_of

RULES = [
    ("website_present", 20, "Has a website"),
    ("email_present", 15, "Has a public business email"),
    ("phone_present", 15, "Has a public business phone"),
    ("address_present", 10, "Has a street address"),
    ("socials_present", 10, "Has official social profile links"),
    ("description_present", 5, "Has a business description"),
    ("category_match", 15, "Category matches the research request"),
    ("geo_match", 10, "City/country matches the research request"),
]


def score_lead(lead: dict, criteria: dict) -> tuple[int, list]:
    score, reasons = 0, []
    if lead.get("website") and domain_of(lead["website"]):
        score += 20; reasons.append("Has a website (+20)")
    if lead.get("email"):
        score += 15; reasons.append("Has a public business email (+15)")
    if lead.get("phone"):
        score += 15; reasons.append("Has a public business phone (+15)")
    if lead.get("address"):
        score += 10; reasons.append("Has a street address (+10)")
    if lead.get("socials"):
        score += 10; reasons.append("Has official social profile links (+10)")
    if lead.get("description"):
        score += 5; reasons.append("Has a business description (+5)")
    want_cat = (criteria.get("category") or "").lower()
    if want_cat and want_cat in (lead.get("category") or "").lower():
        score += 15; reasons.append("Category matches the research request (+15)")
    want_city = (criteria.get("city") or "").lower()
    want_country = (criteria.get("country") or "").lower()
    if (want_city and want_city in (lead.get("city") or "").lower()) or \
       (want_country and want_country in (lead.get("country") or "").lower()):
        score += 10; reasons.append("City/country matches the research request (+10)")
    return min(score, 100), reasons
