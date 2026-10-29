# GrabResult Resource Registry

**Purpose:** evidence-based record of every free/open resource evaluated for the
GrabResult research engine (zero-paid-API budget). Each entry states what was
*actually tested* — not what a marketing page claims.
**Evaluated:** 2026-10-29 · **Evaluator:** research-engineer subagent ·
**Method:** real HTTP requests (curl), real pip installs in a throwaway venv at
`/tmp/evalvenv` (project venv untouched), PyPI metadata checks, official docs.

**Verdict scale:** `INTEGRATE NOW` (tested, reliable, keyless) ·
`KEEP AS OPTIONAL` (works but needs a key, is flaky, or is situational) ·
`REJECT` (not usable under our constraints).

## Summary table

| # | Resource | Type | Free? | Key? | Verdict |
|---|----------|------|-------|------|---------|
| 1 | Overpass API (OpenStreetMap) | API | Yes | No | **INTEGRATE NOW** |
| 2 | Nominatim geocoding | API | Yes | No | **INTEGRATE NOW** |
| 3 | trafilatura (HTML→text) | Library | Yes (Apache-2.0) | No | **INTEGRATE NOW** |
| 4 | feedparser (RSS/Atom) | Library | Yes (BSD) | No | **INTEGRATE NOW** |
| 5 | Sitemap parsing via stdlib `xml.etree` | Library (stdlib) | Yes | No | **INTEGRATE NOW** |
| 6 | rapidfuzz (fuzzy matching) | Library | Yes (MIT) | No | **INTEGRATE NOW** |
| 7 | SQLite | Database | Yes (public domain) | No | **INTEGRATE NOW** (already in arch) |
| 8 | DuckDuckGo Instant Answer API | API | Yes | No | KEEP AS OPTIONAL |
| 9 | Wikipedia REST API | API | Yes | No | KEEP AS OPTIONAL |
| 10 | Wikidata SPARQL | API | Yes | No | KEEP AS OPTIONAL |
| 11 | Marginalia Search API | API | Freemium | `public` key (rate-limited) | KEEP AS OPTIONAL |
| 12 | Tavily Search API | API | Free tier | Yes | KEEP AS OPTIONAL |
| 13 | Brave Search API | API | Free credit | Yes (+card verify) | KEEP AS OPTIONAL |
| 14 | readability-lxml | Library | Yes (Apache-2.0) | No | KEEP AS OPTIONAL |
| 15 | Geofabrik OSM extracts | Dataset | Yes (ODbL) | No | KEEP AS OPTIONAL |
| 16 | Turso (hosted SQLite) | Hosted service | Free tier | Account | KEEP AS OPTIONAL |
| 17 | Neon (serverless Postgres) | Hosted service | Free tier | Account | KEEP AS OPTIONAL |
| 18 | Supabase (Postgres+BaaS) | Hosted service | Free tier | Account | KEEP AS OPTIONAL |
| 19 | SearXNG (self-hosted) | Software | Yes (AGPL-3.0) | No | KEEP AS OPTIONAL |
| 20 | ddgs (`duckduckgo-search`) | Library | Yes (MIT) | No | REJECT |
| 21 | SearXNG public instances | Hosted service | Yes | No | REJECT |
| 22 | Mojeek Search API | API | No (paid) | Yes (+card) | REJECT |
| 23 | Bing Web Search API | API | Retiring | Yes | REJECT |
| 24 | SerpApi / Serper / Exa / Firecrawl | API | Free tier | Yes | REJECT (as mandatory) |
| 25 | thefuzz | Library | Yes (MIT) | No | REJECT |
| 26 | python-dedupe | Library | Yes (MIT) | No | REJECT |
| 27 | jusText | Library | Yes (BSD-2) | No | REJECT |
| 28 | usp.tree (sitemap lib) | Library | — | — | REJECT |
| 29 | Local LLM via Ollama | Software | Yes | No | REJECT |

**Totals:** 29 evaluated · **7 INTEGRATE NOW** · 12 KEEP AS OPTIONAL · 10 REJECT.

---

## INTEGRATE NOW

### 1. Overpass API (OpenStreetMap) — POI / business discovery
- **Type:** API · **Docs:** https://wiki.openstreetmap.org/w/index.php?title=Overpass_API&oldid=2183297
- **Free?** Yes. **Key?** No. **Account/card?** No. **Server?** No (public instances).
- **Rate limits (official wiki):** main instance (`overpass-api.de`, round-robins to
  `z`/`lz4`) ≈1M req/day capacity; safe under **10,000 queries/day and 5 GB/day**
  per project. French instance: ≤1,000 queries/day/project. Kumi Systems instance:
  no stated rate limit (notify before large-scale use).
- **License/commercial:** OSM data under **ODbL** — free for commercial use with
  attribution ("© OpenStreetMap contributors").
- **Maintained:** yes, active OSM community infrastructure.
- **Architecture fit:** pure HTTPS POST, returns JSON — trivial from Python `requests`.
- **Compliance:** legitimate public API with published fair-use policy; not scraping.
- **Tested 2026-10-29:** `curl -X POST https://overpass-api.de/api/interpreter`
  with `[amenity=cafe][name]` around London coords → **HTTP 502 "at capacity"**
  (all query workers busy). Retried with backoff on `overpass-api.de`,
  `z.overpass-api.de`, `overpass.kumi.systems` (connection failed),
  `overpass.nchc.org.tw` (connection failed) — **all public endpoints were
  saturated or unreachable during the test window.**
- **Verdict: INTEGRATE NOW** — it is the single best keyless source of real
  business POIs (name, amenity/shop tags, website, phone, address). The engine
  MUST implement: multi-endpoint failover, exponential backoff, small result
  caps (`out body N`), request spacing, and honest "source unavailable" status —
  because capacity errors are normal.

### 2. Nominatim — geocoding (city → coordinates/bounding box)
- **Type:** API · **Docs:** https://operations.osmfoundation.org/policies/nominatim/
- **Free?** Yes. **Key?** No. **Account/card?** No.
- **Rate limits (official policy):** absolute max **1 request/second**, single
  thread, valid application `User-Agent` (or Referer) required, attribution
  required, results must be cached, **no bulk/systematic geocoding** on the
  public server.
- **License:** data ODbL (wiki notes CC-BY-SA for some Nominatim output) —
  attribution required.
- **Tested 2026-10-29:** `GET nominatim.openstreetmap.org/search?q=London&format=json`
  → HTTP 200, correct lat/lon/boundingbox returned.
- **Verdict: INTEGRATE NOW** — with a ≥1s throttle, result caching, and use only
  for user-triggered geocoding (feeds bounding boxes to Overpass).

### 3. trafilatura — HTML → clean article text
- **Type:** Python library · **Docs:** https://pypi.org/project/trafilatura/
- **Free?** Yes, **Apache-2.0**. **Key/account?** No.
- **Maintained:** yes — v2.3.1 released 2026-10-06 (checked via PyPI JSON).
- **Tested 2026-10-29:** installed in throwaway venv; `trafilatura.extract()`
  on a fetched Wikipedia page → **73,846 chars** of clean text; on example.com →
  156 chars. (`fetch_url` failed on bbc.com — bot protection — so the app should
  fetch with `requests` and pass HTML to `trafilatura.extract()`.)
- **Verdict: INTEGRATE NOW** — for the website contact-page inspector
  (extract readable text before regexing emails/phones).

### 4. feedparser — RSS/Atom feeds
- **Type:** Python library · **Docs:** https://pypi.org/project/feedparser/
- **Free?** Yes, **BSD-2-Clause**. **Key/account?** No.
- **Maintained:** yes — v6.0.14 released 2026-07-30.
- **Tested 2026-10-29:** parsed `https://feeds.bbci.co.uk/news/rss.xml` →
  HTTP 200, **33 entries** with title/link, `bozo=False`.
- **Verdict: INTEGRATE NOW** — powers the "news/updates" enrichment source and
  any RSS-based discovery; dependency-light.

### 5. Sitemap parsing via stdlib `xml.etree`
- **Type:** stdlib (no new dependency).
- **Tested 2026-10-29:** fetched `https://www.sitemaps.org/sitemap.xml`,
  parsed with `xml.etree.ElementTree` → **84 `<loc>` URLs** extracted.
- **Verdict: INTEGRATE NOW** — sitemap discovery needs no third-party lib;
  handle `sitemapindex` recursion and `.xml.gz` in code.

### 6. rapidfuzz — fuzzy string matching (dedupe engine)
- **Type:** Python library · **Docs:** https://pypi.org/project/rapidfuzz/
- **Free?** Yes, **MIT**. **Key/account?** No. Fast (C++ backend).
- **Maintained:** yes — v3.14.6 released 2026-08-30.
- **Tested 2026-10-29:** `token_sort_ratio("Cafe Nero Soho","Caffè Nero - Soho")`
  → **83.9**; vs unrelated name → **~23–27**; `extractOne` best-match → 96.6.
  Clear separation between duplicates and non-duplicates.
- **Verdict: INTEGRATE NOW** — core of duplicate detection (name similarity +
  domain/address exact rules on top).

### 7. SQLite — primary database
- Already the chosen architecture (Python stdlib `sqlite3`, public domain,
  zero-config, file-backed). No hosted dependency for local-first operation.
- **Verdict: INTEGRATE NOW** (already). Hosted options below are optional
  upgrades for deployment, never requirements.

---

## KEEP AS OPTIONAL

### 8. DuckDuckGo Instant Answer API — quick fact enrichment
- **Type:** API · **Endpoint pattern:** `https://api.duckduckgo.com/?q=...&format=json`
  (no official docs page; long-standing unofficial-but-tolerated endpoint).
- **Free/keyless**, no account. Returns `Abstract`, `AbstractText`,
  `RelatedTopics`, `Infobox`.
- **Tested 2026-10-29:** `?q=Python+programming&format=json` → HTTP 200,
  non-empty Abstract + 21 RelatedTopics.
- **Limitations:** not a web-search API (no ranked result list for arbitrary
  business queries); unofficial — could change without notice.
- **Verdict: KEEP AS OPTIONAL** — enrichment sidebar only, never a discovery source.

### 9. Wikipedia REST API — company background enrichment
- **Type:** API · keyless, no account. Content under CC BY-SA.
- **Tested 2026-10-29:** `/api/rest_v1/page/summary/OpenStreetMap` → HTTP 200,
  valid summary JSON.
- **Verdict: KEEP AS OPTIONAL** — "about the company" enrichment for notable firms.

### 10. Wikidata SPARQL — structured facts
- **Type:** API · **Endpoint:** `https://query.wikidata.org/sparql` · keyless,
  CC0 data. Fair-use: throttle, descriptive User-Agent.
- **Tested 2026-10-29:** simple SPARQL (`wd:Q95 wdt:P17 ?item`, LIMIT 3) →
  HTTP 200, valid bindings. (An earlier heavy query returned empty — keep
  queries small with LIMITs and timeouts.)
- **Verdict: KEEP AS OPTIONAL** — structured enrichment (industry, inception,
  HQ) for notable companies only.

### 11. Marginalia Search API — independent web index
- **Type:** API · **Docs:** https://about.marginalia-search.com/article/api/
- **Free?** Freemium. Offers a **`public` API key** (no signup) but docs warn it
  "often hits a rate limit"; real keys negotiated via email
  (contact@marginalia-search.com). No credit card mentioned.
- **Tested 2026-10-29:** two requests with `API-Key: public` →
  **HTTP 429 "QPM Limit Exceeded" both times** (shared key saturated).
- **Verdict: KEEP AS OPTIONAL** — code the adapter behind a user-supplied key
  setting; do not rely on the `public` key.

### 12. Tavily Search API — AI-oriented search
- **Type:** API (key required, free signup). **Free tier:** 1,000 credits/month,
  **no credit card** (per third-party comparison 2026-10-25;
  verify at tavily.com before promising).
- **Verdict: KEEP AS OPTIONAL** — adapter slot only; user supplies their own key.

### 13. Brave Search API — independent web index
- **Type:** API (key required). **Free tier changed over time:** older docs said
  2,000 queries/month; 2026 reports say it became **$5/month account credit**
  (~1,000 queries). **Credit card required for verification** (anti-fraud).
  Get key at https://api.search.brave.com/ (per vendor-linked docs).
- **Verdict: KEEP AS OPTIONAL** — the user cannot provide keys/cards, so this
  stays an optional user-keyed adapter, never mandatory.

### 14. readability-lxml — fallback HTML extractor
- **Type:** Python library · **Docs:** https://pypi.org/project/readability-lxml/
- **Free?** Apache-2.0. Maintained (v0.9, 2026-08-27). Not install-tested
  (trafilatura covers the need).
- **Verdict: KEEP AS OPTIONAL** — fallback if trafilatura misses content.

### 15. Geofabrik OSM extracts — bulk offline POI data
- **Type:** dataset download (geofabrik.de). **Free**, **ODbL** license
  (attribution + share-alike). Country extracts are GB-scale
  (e.g. UK extract is multiple GB compressed) — not downloaded in testing.
- **Verdict: KEEP AS OPTIONAL** — for a future "bulk import" feature; too heavy
  for v1, but the only honest bulk-POI route (no API limits).

### 16–18. Hosted databases (Turso / Neon / Supabase)
- All have genuine free tiers, **no credit card** (per 2026 comparisons;
  verify on official pricing before launch):
  - **Turso** (SQLite/libSQL): ~5 GB storage, 500M row reads/month, 100 DBs.
    Most natural upgrade path from SQLite. https://www.pkgpulse.com/guides/neon-vs-supabase-vs-turso-2026
  - **Neon** (serverless Postgres): 0.5 GB storage, 100 CU-hours/month,
    scales to zero (~500 ms cold start); compute suspends when quota exhausted.
  - **Supabase** (Postgres + auth/storage): 500 MB DB, 2 projects,
    **projects pause after 7 days of inactivity** (manual resume) — bad fit for
    an always-ready demo.
- **Verdict: KEEP AS OPTIONAL** — local SQLite remains the default; document
  Turso as the recommended hosted upgrade (SQLite-compatible, no schema rewrite).

### 19. SearXNG (self-hosted) — metasearch engine
- **Type:** software, **AGPL-3.0**, Python. **Docs:**
  https://github.com/LearningCircuit/local-deep-research/blob/main/docs/SearXNG-Setup.md
- Free and keyless **if you run it yourself** (Docker one-liner), JSON API
  enabled via `settings.yml`. Needs a continuously running server — conflicts
  with zero-config and free-hosting limits.
- **Verdict: KEEP AS OPTIONAL** — advanced/power-user route only.

---

## REJECT

### 20. ddgs (`duckduckgo-search`) — keyless metasearch library — REJECT
- **Docs:** https://pypi.org/project/websearch-skill/0.6.0/ (describes the
  `ddgs` engine family).
- **Tested 2026-10-29:** installed OK, but live searches failed —
  `brave` backend timed out, `duckduckgo` backend hit **DNS resolution failure**,
  `mojeek` backend returned "No results found".
- **Reasons:** (1) failed in this environment; (2) works by scraping search
  engines' HTML, which violates those engines' ToS — incompatible with the
  project's no-ToS-violation rule; (3) upstream breakage is frequent and silent.
- **One-line reason:** unreliable in testing and ToS-gray scraping — not a
  foundation to build on.

### 21. SearXNG public instances — REJECT (as a default source)
- Most public instances **disable the JSON API** and aggressively rate-limit
  automated clients (per SearXNG setup docs and multiple guides). Depending on
  volunteers' servers for production traffic is neither reliable nor ethical.
- **One-line reason:** JSON usually disabled + rate-limited; self-host or skip.

### 22. Mojeek Search API — REJECT (as mandatory)
- **Docs:** https://www.mojeek.com/services/search/web-search-api/ —
  paid API; free test credit exists but **requires signup + bank card**.
- **One-line reason:** needs key + card the user can't provide.

### 23. Bing Web Search API — REJECT
- Microsoft is **retiring/repricing** the standalone API (2026 reports); key required.
- **One-line reason:** deprecated path, key required.

### 24. SerpApi / Serper / Exa / Firecrawl — REJECT (as mandatory)
- All require API keys; free tiers are small (SerpApi ~250/mo) or need signup.
- **One-line reason:** key-required; keep as future user-keyed adapters at most.

### 25. thefuzz — REJECT
- **Docs:** https://pypi.org/project/thefuzz/ — v0.22.1, last release
  **2024-01-19**; superseded upstream by rapidfuzz (same API, faster).
- **One-line reason:** stale; rapidfuzz does the same job better.

### 26. python-dedupe — REJECT
- **Docs:** https://pypi.org/project/dedupe/ — v3.0.3 (2024-08-15), MIT, but
  requires **labelled training data**, heavy ML dependencies, and slow upkeep.
- **One-line reason:** overkill — rapidfuzz + deterministic rules fit the
  dedupe need without ML training burden.

### 27. jusText — REJECT
- **Docs:** https://pypi.org/project/justext/ — v3.0.2 (2025-02-25), BSD-2.
  Decent but slower-moving than trafilatura and redundant with it.
- **One-line reason:** redundant — trafilatura tested better and is actively maintained.

### 28. usp.tree — REJECT
- Not found on PyPI (404 on `https://pypi.org/pypi/usp.tree/json`,
  2026-10-29). Sitemap parsing is covered by stdlib (see #5).
- **One-line reason:** unavailable + unnecessary.

### 29. Local LLM via Ollama — REJECT (for v1)
- Checked `free -g`: **7 GB total RAM, 0 GB free** in this environment; 2 vCPUs.
  Even a small 3–4B model needs ~4–8 GB free RAM plus multi-GB downloads, and
  free hosts (Render/Railway) don't provide GPU or spare RAM.
- **One-line reason:** hardware can't support it and it breaks zero-config —
  the deterministic rules engine (scoring, normalization, templates) covers v1.

---

## Notes for the builder
1. **Source adapter priority for v1:** Overpass (discovery) → Nominatim
   (geocode city to bbox, cached, ≥1 s spacing) → website contact inspector
   (requests + trafilatura + regex, SSRF-guarded) → optional enrichment
   (DDG IA / Wikipedia / Wikidata).
2. **Resilience is a feature:** Overpass returned 502 on every public endpoint
   during evaluation — the job runner must treat "source at capacity" as a
   normal, honestly-reported outcome with retry/backoff, never a silent empty.
3. **Attribution strings to ship in the app:** "© OpenStreetMap contributors"
   (ODbL) wherever Overpass/Nominatim data is shown; User-Agent like
   `GrabResult/1.0 (contact: <support email>)`.
4. **Do not add** ddgs-style engine scraping, public SearXNG instances, or any
   key-required service as a *default* path — they fail the ToS/reliability bar.
5. **Re-verify before launch:** free-tier numbers move (Brave's tier changed
   twice in two years). The "KEEP AS OPTIONAL" hosted items need a pricing-page
   check at release time.
