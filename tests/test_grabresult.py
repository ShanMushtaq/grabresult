"""GrabResult automated test suite. Run: .venv/bin/python -m pytest tests/ -v"""
import io
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP = tempfile.mkdtemp(prefix="grabresult-test-")
os.environ["GRABRESULT_DB_PATH"] = os.path.join(TMP, "test.db")
os.environ["GRABRESULT_UPLOAD_DIR"] = os.path.join(TMP, "uploads")
os.environ["GRABRESULT_EXPORT_DIR"] = os.path.join(TMP, "exports")

from backend.app import create_app  # noqa: E402
from backend.research import dedupe as dedupe_mod  # noqa: E402
from backend.research import normalize as norm  # noqa: E402
from backend.research import quality as qual  # noqa: E402
from backend.research import scoring as scoring_mod  # noqa: E402
from backend.research.adapters import overpass as overpass_mod  # noqa: E402
from backend.research.adapters import website as website_mod  # noqa: E402
from backend.research.planner import build_plan  # noqa: E402
from backend import security  # noqa: E402


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------- startup & health ----------
def test_app_starts_and_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_frontend_serves(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"GrabResult" in r.data


# ---------- research request validation ----------
def test_plan_rejects_short_request(client):
    r = client.post("/api/research/plan", json={"request_text": "find food"})
    assert r.status_code == 400
    assert "detail" in r.get_json()["error"].lower()


def test_plan_builds_from_natural_language():
    plan = build_plan(
        "Find independent restaurants in London with websites and phone numbers",
        {"max_records": 50},
    )
    assert plan["criteria"]["category"] == "restaurant"
    assert plan["max_records"] == 50
    assert "overpass" in plan["sources"]
    assert plan["limitations"]  # limitations always disclosed


def test_plan_respects_max_records_cap():
    plan = build_plan("Find shops in Paris with emails", {"max_records": 99999})
    assert plan["max_records"] == 500


# ---------- source adapter failures ----------
def test_overpass_requires_location():
    ad = overpass_mod.OverpassAdapter()
    res = ad.search({"category": "restaurant", "max_records": 10})
    assert res.status == "failed"
    assert "location" in res.message


def test_overpass_handles_endpoint_failure(monkeypatch):
    import requests as rq
    def boom(*a, **k):
        raise rq.ConnectionError("down")
    monkeypatch.setattr(rq, "post", boom)
    ad = overpass_mod.OverpassAdapter()
    res = ad.search({"bbox": {"south": 51.3, "north": 51.7, "west": -0.3, "east": 0.1},
                     "category": "restaurant", "max_records": 5})
    assert res.status == "failed"  # both endpoints tried, graceful failure
    assert res.records == []


def test_nominatim_empty_place():
    from backend.research.adapters.nominatim import NominatimAdapter
    ad = NominatimAdapter()
    res = ad.search({})
    assert res.status == "failed"


# ---------- data extraction ----------
class FakeResp:
    headers = {"Content-Type": "text/html"}
    text = """
    <html><body><h1>Acme Bakery</h1>
    <p>Call us on +44 20 7946 0018 or email hello@acmebakery.example.co.uk</p>
    <a href="https://instagram.com/acmebakery">IG</a>
    <a href="mailto:orders@acmebakery.example.co.uk">mail</a>
    </body></html>"""


def test_website_inspector_extracts_contacts(monkeypatch):
    monkeypatch.setattr(website_mod, "safe_fetch", lambda url, timeout=20: FakeResp())
    ad = website_mod.WebsiteInspectorAdapter()
    info = ad.inspect("https://acmebakery.example.co.uk")
    assert "hello@acmebakery.example.co.uk" in info["emails"]
    assert "orders@acmebakery.example.co.uk" in info["emails"]
    assert any("7946" in p for p in info["phones"])
    assert info["socials"].get("instagram") == "https://instagram.com/acmebakery"


def test_website_inspector_needs_websites():
    ad = website_mod.WebsiteInspectorAdapter()
    res = ad.search({})
    assert res.status == "unavailable"


# ---------- normalization ----------
def test_normalize_record():
    rec = norm.normalize_record({
        "business_name": "  Acme   Bakery LTD. ",
        "website": "WWW.AcmeBakery.example.co.uk/",
        "email": "Hello@AcmeBakery.example.co.uk ",
        "phone": "+44 (0)20 7946 0018",
        "country": "uk", "city": "  london ",
        "socials": {"Instagram": "instagram.com/acmebakery"},
    })
    assert rec["business_name"] == "Acme Bakery LTD."
    assert rec["website"] == "https://acmebakery.example.co.uk"
    assert rec["email"] == "hello@acmebakery.example.co.uk"
    assert rec["country"] == "United Kingdom"
    assert rec["city"] == "London"
    assert rec["socials"]["instagram"].startswith("https://")


def test_name_key_ignores_legal_suffix():
    assert norm.name_key("Acme Bakery Ltd") == norm.name_key("ACME BAKERY limited")


# ---------- duplicate detection ----------
def _rec(name, website="", city="", phone=""):
    return {"business_name": name, "website": website, "city": city, "phone": phone,
            "socials": {}, "source_name": "t"}


def test_duplicate_same_domain():
    assert dedupe_mod.is_duplicate(
        _rec("Acme", "https://acme.example.com"), _rec("Acme Different Name", "https://acme.example.com"))


def test_duplicate_same_name_and_city():
    assert dedupe_mod.is_duplicate(
        _rec("Acme Bakery", city="London"), _rec("Acme Bakery Ltd", city="London"))


def test_similar_names_alone_do_not_merge():
    a, b = _rec("Acme Bakery", city="London"), _rec("Acme Bakers", city="Manchester")
    assert not dedupe_mod.is_duplicate(a, b)


def test_dedupe_merges_and_keeps_provenance():
    recs = [_rec("Acme", "https://acme.example.com", "London"),
            _rec("Acme Ltd", "https://acme.example.com/", "London", phone="+441234")]
    unique, dup_info = dedupe_mod.dedupe_records(recs)
    assert len(unique) == 1
    assert unique[0]["phone"] == "+441234"  # filled from duplicate
    assert len(dup_info) == 1


# ---------- lead scoring ----------
def test_scoring_is_transparent_and_capped():
    lead = {"website": "https://x.example.com", "email": "a@x.example.com",
            "phone": "+1", "address": "1 Main St", "socials": {"instagram": "u"},
            "description": "d", "category": "Restaurant", "city": "London", "country": "United Kingdom"}
    score, reasons = scoring_mod.score_lead(lead, {"category": "restaurant", "city": "London"})
    assert score == 100
    assert len(reasons) >= 7
    assert all("(+" in r for r in reasons)  # every rule explained


def test_scoring_empty_lead_is_zero():
    score, reasons = scoring_mod.score_lead({}, {})
    assert score == 0 and reasons == []


def test_quality_statuses():
    assert qual.assess_quality({"business_name": "X", "website": "https://x.example.com",
                                "city": "Lahore"}, {}) == "qualified"
    assert qual.assess_quality({"business_name": "X"}, {"require_website": True}) == "excluded"
    assert qual.assess_quality({"business_name": ""}, {}) == "excluded"
    assert qual.assess_quality({"business_name": "X", "city": "Lahore"}, {}) == "needs_review"
    assert set(qual.STATUSES) == {"discovered", "qualified", "verified",
                                  "needs_review", "duplicate", "excluded"}


# ---------- database persistence ----------
def test_db_roundtrip(client):
    from backend.app import db
    lid = db.upsert_lead({"business_name": "Persisted Co", "city": "Lahore",
                          "discovered_at": 1.0, "verification_status": "discovered"})
    assert db.get_lead(lid)["business_name"] == "Persisted Co"
    total, leads = db.list_leads(search="Persisted")
    assert total >= 1
    db.delete_lead(lid)
    assert db.get_lead(lid) is None


def test_job_lifecycle(client):
    from backend.app import db
    jid = db.create_job("test request", {"objective": "x"})
    assert db.get_job(jid)["status"] == "queued"
    db.update_job(jid, status="running", progress=50)
    assert db.get_job(jid)["progress"] == 50


# ---------- imports ----------
def _upload(client, content: bytes, filename: str):
    return client.post("/api/imports/upload", data={"file": (io.BytesIO(content), filename)},
                       content_type="multipart/form-data")


def test_csv_import_end_to_end(client):
    csv_bytes = b"Company Name,Email,City\nAcme Bakery,hello@acme.example.com,London\n,Missing Name,X\nAcme Bakery,hello@acme.example.com,London\n"
    up = _upload(client, csv_bytes, "leads.csv")
    assert up.status_code == 200, up.get_json()
    body = up.get_json()
    assert body["suggested_mapping"]["Company Name"] == "business_name"

    pv = client.post("/api/imports/preview",
                     json={"upload_path": body["upload_path"], "mapping": body["suggested_mapping"]})
    assert pv.status_code == 200
    assert pv.get_json()["clean_count"] == 1  # 1 valid, 1 no-name skipped, 1 dup skipped

    cf = client.post("/api/imports/confirm",
                     json={"upload_path": body["upload_path"], "mapping": body["suggested_mapping"]})
    assert cf.status_code == 200
    assert cf.get_json()["imported"] == 1


def test_malformed_upload_rejected(client):
    r = _upload(client, b"\x00\x01\x02not a csv at all\xff", "evil.csv")
    # must not crash; either parsed-with-zero-rows or a clean 400
    assert r.status_code in (200, 400)


def test_wrong_file_type_rejected(client):
    r = _upload(client, b"hello", "notes.txt")
    assert r.status_code == 400


# ---------- exports ----------
def _seed_lead(client):
    from backend.app import db
    return db.upsert_lead({
        "business_name": "Export Test Ltd", "website": "https://export.example.com",
        "email": "info@export.example.com", "city": "London", "country": "United Kingdom",
        "category": "Restaurant", "discovered_at": 1700000000.0,
        "verification_status": "qualified", "confidence": 0.8, "lead_score": 75,
        "socials_json": "{}", "score_reasons_json": "[\"Has a website (+20)\"]",
        "provenance_json": "{}", "source_name": "test", "source_url": "",
        "description": "", "industry": "", "address": "", "phone": "", "notes": ""})


def test_xlsx_export_download(client):
    _seed_lead(client)
    r = client.post("/api/exports", json={"kind": "xlsx"})
    assert r.status_code == 200, r.get_json()
    dl = client.get(f"/api/exports/{r.get_json()['export_id']}/download")
    assert dl.status_code == 200
    assert dl.data[:2] == b"PK"  # real zip-based xlsx
    assert len(dl.data) > 4000


def test_csv_export_download(client):
    _seed_lead(client)
    r = client.post("/api/exports", json={"kind": "csv"})
    assert r.status_code == 200
    dl = client.get(f"/api/exports/{r.get_json()['export_id']}/download")
    assert dl.status_code == 200
    assert b"Export Test Ltd" in dl.data
    assert b"business_name" in dl.data.split(b"\n")[0]


def test_export_with_no_leads_is_honest(client):
    from backend.app import db
    db.clear_all_data()
    r = client.post("/api/exports", json={"kind": "xlsx"})
    assert r.status_code == 400  # refuses to fabricate an empty "successful" report


# ---------- engine: empty & partial results are honest ----------
def test_engine_empty_results_marked_partial(client, monkeypatch):
    from backend import app as appmod
    from backend.research import engine as eng
    import backend.config as cfg

    class DeadAdapter:
        def capability(self):
            return {"name": "dead", "kind": "test", "auth_required": "none",
                    "docs_url": "", "supported_fields": [], "limitations": []}

        def search(self, q):
            from backend.research.adapters.base import AdapterResult
            return AdapterResult(status="failed", message="simulated outage")
    monkeypatch.setattr(eng, "_adapter_instances",
                        lambda c: {"nominatim": DeadAdapter(), "overpass": DeadAdapter(),
                                   "website_inspector": DeadAdapter()})
    db = appmod.db
    jid = db.create_job("impossible request xyz", {"criteria": {}, "max_records": 10,
                                                   "sources": [], "inspect_websites": False,
                                                   "output_fields": []})
    summary = eng.run_research(db, cfg.Config(), jid,
                               {"criteria": {}, "max_records": 10, "sources": [],
                                "inspect_websites": False, "output_fields": []},
                               cancel_check=lambda: False)
    job = db.get_job(jid)
    assert job["status"] in ("partial", "failed")
    assert summary["records_discovered"] == 0
    assert "0" in json.dumps(summary)  # honest zero counts, no fiction


# ---------- security ----------
def test_ssrf_blocks_private_targets():
    with pytest.raises(ValueError):
        security.safe_fetch("http://127.0.0.1:5000/api/health", timeout=5)
    with pytest.raises(ValueError):
        security.safe_fetch("http://169.254.169.254/", timeout=5)
    with pytest.raises(ValueError):
        security.validate_url("file:///etc/passwd")


def test_xss_payload_stored_as_text(client):
    from backend.app import db
    lid = db.upsert_lead({"business_name": "<script>alert(1)</script>",
                          "discovered_at": 1.0, "verification_status": "discovered"})
    r = client.get(f"/api/leads/{lid}")
    assert r.status_code == 200
    # API returns the raw string; frontend renders via textContent (no execution)
    assert "<script>" in r.get_json()["lead"]["business_name"]
    db.delete_lead(lid)


def test_invalid_lead_status_rejected(client):
    lid = _seed_lead(client)
    r = client.patch(f"/api/leads/{lid}", json={"verification_status": "hacked"})
    assert r.status_code == 400
