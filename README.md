# GrabResult — Autonomous Research & Lead-Generation Platform

GrabResult turns a plain-English research request into a structured,
deduplicated lead database with one-click Excel/CSV exports — using only
**free, public sources**. No paid APIs, no API keys, no credit card.

Example request:

> "Find 300 independent restaurants in London and Manchester. Collect business
> names, websites, publicly listed business emails, phone numbers, addresses,
> categories, ratings where available, and official social media links. Remove
> duplicates and export the results to Excel."

GrabResult interprets the request, searches public sources, normalizes and
deduplicates the records, scores each lead, and produces a downloadable
workbook — while honestly reporting what it could and could not find.

## What works today (verified 2026-10-29)

- **Natural-language research planner** — deterministic, no AI model needed.
- **Real discovery** via OpenStreetMap Nominatim (geocoding) + Overpass API
  (business POIs): names, categories, addresses, phones, websites, opening
  hours where mapped. Verified live: 15 real cafes in Lahore discovered,
  scored and saved in ~34 seconds.
- **Website contact inspector** — visits discovered business websites and
  extracts publicly listed emails/phones (SSRF-protected).
- **Data engine** — normalization, fuzzy duplicate detection & merging,
  transparent lead scoring (0–100 with reasons), quality statuses
  (discovered / qualified / verified / needs_review / duplicate / excluded).
- **Master leads database** (SQLite) with filters: country, city, industry,
  category, keyword, website/email/phone availability, source, verification
  status, minimum score.
- **CSV/XLSX import** with column mapping, duplicate detection and conflict
  reporting — existing records are never silently overwritten.
- **Real Excel exports** — multi-sheet workbooks (All Results, Qualified
  Leads, Needs Review, per-country, per-city, Sources & Evidence, Research
  Summary) with filters, formatting and source URLs. Verified: opened and
  read back with openpyxl. CSV exports verified too.
- **Research history** — every job stored with status (queued / running /
  completed / partially completed / failed / cancelled), progress messages,
  source log, summary and reopenable results.
- **Web UI** — Dashboard, New Research, Research History, Leads Database,
  Imports, Exports, Settings, Help. All buttons do real work.
- **Security** — SSRF protection on every outbound fetch (blocks
  private/loopback/link-local targets on every redirect hop), URL validation,
  upload size limits, safe file parsing, no secrets in frontend code.
- **31 automated tests, all passing.**

## Quick start (no technical background needed)

You need **Python 3.10+** installed — that's it.

**Windows**
1. Download and unzip `grabresult.zip`.
2. Double-click `start-windows.bat`.
3. Your browser opens at `http://127.0.0.1:5000`.

**Mac / Linux**
1. Download and unzip `grabresult.zip`.
2. Open a terminal in the folder and run: `./start.sh`
   (or: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python run.py`)
3. Open `http://127.0.0.1:5000` in your browser.

Full step-by-step guide: **[docs/SETUP.md](docs/SETUP.md)**.
Putting it on the internet: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

## Project layout

```
grabresult/
├── run.py                  # entry point: python run.py
├── requirements.txt        # pinned Python dependencies
├── Procfile / render.yaml / Dockerfile   # deployment configs
├── backend/
│   ├── app.py              # Flask app + all API routes
│   ├── config.py           # env-based configuration
│   ├── db.py               # SQLite persistence layer
│   ├── jobs.py             # background research job runner
│   ├── security.py         # SSRF protection, URL validation, safe fetch
│   ├── research/
│   │   ├── planner.py      # natural-language → structured plan
│   │   ├── engine.py       # orchestrates adapters → normalize → dedupe
│   │   ├── normalize.py / dedupe.py / scoring.py / quality.py
│   │   └── adapters/
│   │       ├── overpass.py     # OpenStreetMap business POIs (live ✓)
│   │       ├── nominatim.py    # geocoding (live ✓)
│   │       ├── website.py      # contact-page inspector (live ✓)
│   │       └── base.py         # adapter contract for future sources
│   ├── exports/            # real XLSX (openpyxl) + CSV writers
│   └── imports/            # CSV/XLSX import, mapping, conflict reports
├── frontend/               # single-page UI (index.html + app.js + styles.css)
├── instance/               # SQLite DB, uploads, exports (created at runtime)
├── tests/                  # 31 automated tests (pytest)
└── docs/
    ├── SETUP.md            # beginner setup guide
    ├── DEPLOYMENT.md       # hosting guide (free tiers)
    ├── resource-registry.md# every source evaluated: docs, auth, limits
    ├── TEST_RESULTS.md     # actual test evidence
    └── KNOWN_LIMITATIONS.md# honest limits + not-yet-built list
```

## Data honesty rules (built in)

- Never invents records, emails, phones, ratings or follower counts.
- Anything unconfirmed is marked `needs_review` or `not found` — never guessed.
- Every record keeps its source URL and collection timestamp.
- If fewer records are found than requested, it returns what exists and says so.
- An email is **not** labelled "verified" just because its format looks right.

## Tech choices (why)

| Choice | Reason |
|---|---|
| Python + Flask | Small, readable, runs anywhere; user can inspect it |
| SQLite | Zero-setup persistent database, single file |
| OpenStreetMap (Nominatim + Overpass) | Free, no key, generous public use; real business POIs |
| openpyxl | Real Excel workbooks, no paid library |
| Background threads + polling | Honest progress without extra infrastructure |

## License

MIT — see `LICENSE` (dependencies: Flask BSD-3, requests Apache-2,
beautifulsoup4 MIT, openpyxl MIT — all permissive; details in
docs/KNOWN_LIMITATIONS.md "Dependency licenses").
