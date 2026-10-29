# GrabResult — Known Limitations & Feature Status

Honest accounting, as required. "Works" means verified by a real run.

## Implemented and verified ✓

- Natural-language planner (deterministic, no AI key needed)
- Live discovery: Nominatim geocoding + Overpass business POIs
- Website contact inspector (public emails/phones from business sites)
- Normalization, fuzzy dedupe + merge, transparent lead scoring (0–100)
- Quality statuses: discovered / qualified / verified / needs_review /
  duplicate / excluded (rules in `backend/research/quality.py`)
- Leads database with 10 filter dimensions
- CSV + XLSX import with column mapping, duplicate detection, conflict report
- Multi-sheet XLSX + CSV exports with source URLs and timestamps
- Research history with real statuses and progress messages
- Full web UI (8 sections, every button wired)
- SSRF protection, upload limits, safe parsing, env-based secrets
- 31 automated tests passing; production (gunicorn) serving verified

## Incomplete / unavailable — and why

1. **Social media connectors (Instagram, Facebook, LinkedIn, YouTube,
   TikTok)** — marked *unavailable*, not faked. There is no free, permitted,
   keyless way to extract these at scale; platform ToS and login walls block
   it. The adapter interface (`backend/research/adapters/base.py`) is ready
   for future authorized integrations (e.g., official APIs with user keys).
2. **Public deployment URL** — not deployed. Needs the owner's Render/GitHub
   account actions. All configs prepared and verified locally.
3. **PDF report export** — not built. XLSX "Research Summary" sheet covers the
   same content; PDF is a nice-to-have.
4. **Multi-user accounts / login** — single-user local tool by design. Don't
   expose it publicly without adding authentication.
5. **Background jobs across restarts** — jobs run in worker threads; a server
   restart cancels in-flight jobs (marked failed, resumable by re-running).

## Data limitations (inherent, not bugs)

- Discovery reflects **OpenStreetMap coverage**: only mapped businesses appear,
  and contact fields exist only where mappers added them. Dense Western cities
  return hundreds of records; smaller towns return fewer. The app reports
  exactly what it found.
- Overpass is a free shared service: it can be slow or busy. The app retries
  with backoff and returns partial results with an honest explanation.
- "Verified" status is conservative by design: format-valid ≠ verified. True
  verification (e.g., SMTP checks) is deliberately excluded — it would be
  intrusive and unreliable without user consent per target.
- Ratings/reviews are not collected: no free, permitted, keyless source
  provides them reliably.

## Dependency licenses (all permissive, no paid components)

- Flask 3.1.3 — BSD-3-Clause
- requests 2.34.2 — Apache-2.0
- beautifulsoup4 4.15.0 — MIT
- openpyxl 3.1.5 — MIT
- gunicorn 23.0.0 — MIT
- pytest 9.2.0 — MIT (dev only)
- GrabResult's own code — MIT (see LICENSE)

No copyleft components, no telemetry, no paid SDKs.
