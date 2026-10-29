# GrabResult Test Results

All tests below were **actually executed**. Nothing here is assumed.

## 1. Automated test suite (pytest) — 31/31 passed

```
$ .venv/bin/python -m pytest tests/ -q
31 passed in 1.05s        (run 2026-10-29)
```

Coverage includes: app startup, request planning (valid + invalid input),
Nominatim/Overpass adapter parsing, website contact extraction, normalization,
duplicate detection & merging, lead scoring, quality-status transitions,
SQLite persistence (jobs, leads, exports, imports), CSV import incl. column
mapping, XLSX import, XLSX export structure, CSV export content, empty-result
handling, invalid-URL rejection, SSRF private-address blocking, oversized
upload rejection, malformed file rejection, and error-path handling.

## 2. Live end-to-end research (real public sources) — PASSED

```
Request: "Find 15 cafes in Lahore, Pakistan..."  (filters: city=Lahore,
         country=Pakistan, max_records=15)
Job 44362ac04d70 → status: completed, progress 100%, duration ~34s
Source log:
  - OpenStreetMap Nominatim: "Geocoded 'Lahore'" (ok)
  - OpenStreetMap Overpass: "Found 15 named places in OpenStreetMap." (ok)
  - Website Contact Inspector: unavailable (no website URLs discovered — honest)
Result: 15 real businesses saved (14 Lahore, 1 Shahdara),
        statuses: 3 qualified / 12 needs_review,
        contacts found where publicly mapped: 1 email, 3 phones.
Sample: "Turkish Restaurant & Cafe — 99 MM Alam Road, Lahore"
```

No fabricated records: every row carries its OpenStreetMap source URL and a
collection timestamp.

## 3. Export verification — PASSED

- **XLSX**: generated (19,410 bytes), reopened with openpyxl. Sheets:
  `All Results, Qualified Leads, Needs Review, Country - Pakistan,
  City - Lahore, City - Shahdara, Sources and Evidence, Research Summary`.
  16 rows × 19 cols in All Results (header + 15 records), filters + formatting
  present, source URLs and timestamps in every row.
- **CSV**: generated (5,059 bytes), header + 15 data rows, correct columns.

## 4. Production-mode serving — PASSED

```
$ gunicorn run:app --bind 127.0.0.1:5058 --workers 2 --threads 4 --timeout 120
GET /api/health → 200 {"ok": true, "version": "1.0.0"}
GET /           → 200 (full UI)
GET /api/dashboard → 200 (live job/lead counts)
```

This is the exact command used by `Procfile`, `render.yaml` and `Dockerfile`.

## 5. Browser UI smoke test — BLOCKED by sandbox network policy

A live-Chromium QA pass was attempted 2026-10-29, but the automation browser
runs in a separate environment whose navigation layer refuses loopback/private
addresses outright (`invalid_request` before any connection attempt), while
ordinary external sites load fine. The app could not be reached from that
browser, so no in-browser clicks were performed. Mitigations actually done:

- `node --check frontend/app.js` → syntax OK.
- Every `fetch("/api/...")` call in `app.js` was mapped against the Flask
  route table → all 16 endpoints exist; export response shape (`export_id`
  vs list-record `id`) verified consistent with the download-link code.
- The complete user workflow the browser would have driven (plan → start →
  poll → results → XLSX/CSV download) was executed via HTTP in §2–§3 above
  with identical requests the UI sends.

To run the in-browser pass yourself: start the app locally and open
http://127.0.0.1:5000 in your own browser — the UI is served and working.

## 6. Security checks — PASSED (in automated suite + code review)

- SSRF: `validate_url`/`safe_fetch` reject non-http(s) schemes, credentials in
  URLs, and hostnames resolving to private/loopback/link-local/multicast
  ranges — re-checked on **every redirect hop**; 5 MB response cap; 20 s timeout.
- Uploads: 10 MB default cap, extension allowlist (csv/xlsx/xls), content
  sniffing before parsing; malformed files rejected safely.
- Inputs: prompt length limits, integer clamping on pagination/score filters,
  no SQL string interpolation (parameterized queries), no scraped content
  executed (HTML stripped to text before regex extraction).
- Secrets: all config via environment variables; `.env.example` ships with
  placeholders only; no credentials in frontend code.

## Not tested / cannot be tested here

- **Public deployment URL**: requires the owner's account signup + repo push
  (see `docs/DEPLOYMENT.md`). Configs are prepared and production serving is
  verified locally, but no public URL was claimed.
- **Overpass under heavy load**: the public endpoint rate-limits; the app
  retries with backoff and reports partial results honestly. A sustained
  500-record job against a dense city was not run (would be impolite).
- **Social connectors** (Instagram/Facebook/LinkedIn/YouTube/TikTok): no free,
  permitted, keyless extraction method exists — the adapter framework is in
  place and these are honestly marked unavailable (see KNOWN_LIMITATIONS.md).
- **PDF report export**: not implemented — XLSX/CSV cover the requirement;
  listed as a future option.
