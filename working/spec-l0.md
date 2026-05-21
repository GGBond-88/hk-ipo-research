# L0 — HKEX IPO Prospectus Auto-Downloader

**Spec date:** 2026-05-21
**Status:** Draft for review
**Scope:** Build the L0 layer that auto-discovers and downloads IPO prospectus PDFs from HKEXnews.hk into `data/raw_pdfs/`, feeding the existing L1-L7 analysis pipeline.

---

## 1. Goal and scope

Replace the current "manual drop PDFs into `data/raw_pdfs/`" step with an automated CLI tool that discovers IPO prospectus filings via HKEX's title-search backend and downloads the final English-language prospectus for each ticker.

### Scope decisions baked in

- **Volume:** 2010-01-01 through present (~2,000-2,500 final prospectuses across Main Board + GEM).
- **Doc types:** Final Prospectus (Main Board) and final GEM Listing Document only. Application Proofs, PHIPs, supplemental prospectuses, annual reports, interims, and any other filing types are skipped.
- **One PDF per ticker:** keyed by 5-digit zero-padded HK ticker (`<ticker>.pdf`), matching the L1 convention.
- **Language:** English only. Bilingual filings: take the English PDF. Chinese-only filings: skip and record in manifest.
- **Integration posture:** L0 is a standalone subpackage with its own CLI. `scripts/run_pipeline.py` (L1-L7) is untouched. L0 feeds raw_pdfs/ which L1 then consumes.
- **State of record:** `data/raw_pdfs/manifest.json` — single JSON file, file-locked, schema-versioned. Not committed to git (regenerable).

### Explicitly out of scope (YAGNI)

- Non-IPO filings (annual reports, announcements, etc.).
- Pre-2010 backfill (possible later via `--since 1999-01-01`).
- Currency/FX handling (L5+ concern).
- Multi-version prospectus tracking (A1 vs PHIP vs final) — final only.
- Push notifications, Slack, web UI for manifest browsing.
- Backend service / daemon mode — invocation is CLI + optional cron.

---

## 2. Architecture

```
HKEXnews title-search backend
       |
       v
+-------------------------------------------------------------+
| discovery.py    JSON API (primary) + HTML fallback          |
|                 yields Filing objects per date window       |
+-------------------------------------------------------------+
       |  Filing(ticker, doc_id, url, title, language, type, date)
       v
+-------------------------------------------------------------+
| filter.py       is_english_prospectus() + should_skip()     |
|                 pure functions, no I/O                      |
+-------------------------------------------------------------+
       |  filtered Filings
       v
+-------------------------------------------------------------+
| downloader.py   bounded-concurrency pool, atomic writes,    |
|                 hash verification, exponential retry        |
+-------------------------------------------------------------+
       |  DownloadResult
       v
+-------------------------------------------------------------+
| manifest.py     read/write data/raw_pdfs/manifest.json      |
|                 file-locked, schema-versioned, atomic       |
+-------------------------------------------------------------+
       |
       v
data/raw_pdfs/<ticker>.pdf  +  data/raw_pdfs/manifest.json
       |
       v
[existing L1 l1_sectioning.py consumes raw_pdfs/]
```

---

## 3. Module layout

```
src/hk_ipo/l0/
├── __init__.py
├── __main__.py        # CLI entry: python -m hk_ipo.l0 <subcommand>
├── discovery.py       # HKEXDiscoveryClient (JSON + HTML)
├── filter.py          # is_english_prospectus(), should_skip()
├── downloader.py      # PDFDownloader, atomic + hashed
├── manifest.py        # ManifestStore (load, save, query, mutate)
└── models.py          # @dataclass Filing, ManifestEntry, DownloadResult
```

**Responsibilities (each module has one clear purpose):**

- **discovery.py** — Network I/O against HKEX. Given a date range, async-yields `Filing` objects. Holds JSON-vs-HTML fallback internally. Persists raw API responses per window to `data/logs/l0/discovery/YYYY-MM.json` for debugging.
- **filter.py** — Pure decision functions. Zero I/O. Fully unit-testable.
- **downloader.py** — Streaming HTTP download to `<ticker>.pdf.tmp`, SHA-256 hash, atomic rename on success. Exponential retry via `tenacity`. Cleans up orphan `.tmp` files at startup.
- **manifest.py** — JSON read/write with file lock (`portalocker`). API: `add_entry()`, `mark_failed()`, `mark_skipped()`, `get_status(ticker)`, `pending_filings(filings)`, `save()`. Schema-versioned for future migration.
- **__main__.py** — Argument parsing and orchestration only. Thin glue.
- **models.py** — Shared dataclasses. Avoids circular imports.

**New runtime dependencies:** `httpx`, `selectolax`, `tenacity`, `portalocker`. All added to `pyproject.toml`.

---

## 4. Discovery & filtering

### Primary path: JSON API

HKEX's title-search backend exposes a paginated JSON endpoint accepting a date range and document-type filter. Filter parameters used for "final IPO prospectus, Main Board + GEM":

- `t1code` (document category) = `40000` ("Listing Documents")
- `t2code` (document subtype) = `40100` (Prospectus / Listing Document); A1/PHIP/supplemental subtypes excluded
- `market` = `SEHK` (Main Board) and `GEM`
- `from` / `to` = month-sized date windows

> **Implementation note:** the exact `t1code`/`t2code` values are best-effort from the `simonplmak-cloud/hkex-filing-scraper` reference. They must be spot-checked during implementation against 5-10 known IPOs spanning 2010-2025 across MB+GEM. A golden fixture (`tests/fixtures/l0_known_ipos.json`) locks this in as a regression test.

`DiscoveryClient.list_filings(start, end)` is an async generator yielding `Filing` across all pages of all windows.

### Fallback path: HTML Title Search

Triggered when (a) the JSON endpoint returns 4xx/5xx for a window after exhausting retries, or (b) the JSON response schema doesn't match the parser. Hits `https://www1.hkexnews.hk/search/titleSearchServlet.do` with equivalent parameters. Parsed via `selectolax`. Same `Filing` dataclass — callers can't tell which path served them.

### Filter logic

```python
def is_english_prospectus(filing: Filing) -> bool:
    return (
        filing.doc_type in {"Prospectus", "Listing Document - GEM"}
        and filing.is_final  # exclude A1, PHIP, supplemental
        and has_english_version(filing)
    )
```

`has_english_version` priority order:
1. `LANGUAGE_CD` field from API response if present.
2. URL pattern: HKEX PDFs typically suffix `_e.pdf` (English) or `_c.pdf` (Chinese).
3. Title language detection: presence of Latin letters vs CJK characters.

If only Chinese exists, record `status=skipped_no_english` in manifest. No download. L1's existing zh-detection remains as a safety net for filings that slip through.

### De-duplication and re-attempt rules

Manifest keyed by `hk_ticker`. Per-mode re-attempt behavior:

| Existing status | `sync` / `backfill` | `retry-failed` | `refresh <ticker>` |
|---|---|---|---|
| (none — new filing) | download | n/a | download |
| `success` | skip | skip | re-download; overwrite if hash differs, else noop |
| `failed` | skip (will not retry) | retry | re-download |
| `skipped_no_english` | skip | skip | re-evaluate filter; download if now has EN |
| `skipped_wrong_doc_type` | skip | skip | re-evaluate; usually still skipped |
| `pending` (from crashed prior run) | retry | retry | re-download |

A filing that was `skipped_no_english` only gets re-evaluated on `refresh` (or if a future date-window backfill happens to re-discover it via the discovery API). This is intentional — `sync` is keyed by discovery date window, not by re-querying old tickers.

Prior versions are never kept on `refresh` — the file at `<ticker>.pdf` is overwritten.

---

## 5. Manifest schema

`data/raw_pdfs/manifest.json`:

```json
{
  "schema_version": 1,
  "last_full_sync": "2026-05-21T14:23:00Z",
  "last_incremental_sync": "2026-05-21T14:23:00Z",
  "entries": {
    "01234": {
      "status": "success",
      "hk_ticker": "01234",
      "company_name_en": "Example Holdings Limited",
      "listing_date": "2024-07-15",
      "market": "MB",
      "doc_id": "2024071500021",
      "doc_title": "Global Offering",
      "doc_url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0715/2024071500021.pdf",
      "language": "en",
      "file_path": "01234.pdf",
      "file_sha256": "ab12...",
      "file_size_bytes": 8421953,
      "downloaded_at": "2026-05-21T14:24:11Z",
      "discovered_at": "2026-05-21T14:23:05Z"
    },
    "02345": {
      "status": "skipped_no_english",
      "hk_ticker": "02345",
      "company_name_zh": "示例控股有限公司",
      "doc_id": "2024082200015",
      "doc_url": "https://...",
      "discovered_at": "2026-05-21T14:23:09Z",
      "skip_reason": "no_english_version_published"
    },
    "03456": {
      "status": "failed",
      "hk_ticker": "03456",
      "doc_url": "...",
      "error": "HTTPError: 503 after 5 retries",
      "first_attempted_at": "2026-05-21T14:24:30Z",
      "last_attempted_at": "2026-05-21T14:26:12Z",
      "attempt_count": 5
    }
  }
}
```

**Status vocabulary (closed):** `success`, `skipped_no_english`, `skipped_wrong_doc_type`, `failed`, `pending`.

**Concurrency safety:** manifest writes guarded by `portalocker` cross-process file lock. Within a single run, the downloader pool serializes writes through `ManifestStore`.

**Crash safety:** writes are atomic (tmp + rename). Persistence cadence: after every successful download, or every 10 skips/failures. Maximum 10 status updates lost on hard kill; downloaded PDFs are never lost (atomic).

**Downstream connection:** L1 already keys outputs by 5-digit ticker. The manifest is available as a metadata source for L1+ (listing date, company name) but is not a hard dependency.

---

## 6. CLI surface

```bash
# Historical backfill
python -m hk_ipo.l0 backfill [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                             [--workers 4] [--dry-run] [--limit N]

# Incremental sync since last run
python -m hk_ipo.l0 sync     [--workers 4] [--dry-run]

# Retry past failures
python -m hk_ipo.l0 retry-failed [--workers 4] [--max-age-days 30]

# Force re-download specific tickers
python -m hk_ipo.l0 refresh <ticker> [<ticker> ...] [--workers 4]

# Read-only manifest inspection
python -m hk_ipo.l0 status [--json]

# Verify on-disk files match manifest hashes
python -m hk_ipo.l0 verify [--repair]
```

**Common flags:**
- `--workers N` (default `4`)
- `--dry-run` — discover and filter, write nothing
- `--log-level DEBUG|INFO|WARN`
- `--manifest PATH` — override default

**Mode semantics:**

- **`backfill`** — iterates date range in monthly windows; idempotent on re-run; updates `last_full_sync`. Default range: `--since 2010-01-01 --until <today>`.
- **`sync`** — queries from `last_incremental_sync` to now; safe to cron weekly.
- **`retry-failed`** — re-attempts `status=failed` entries; `--max-age-days` skips ancient failures.
- **`refresh <ticker>`** — targeted re-download; overwrites if hash differs.
- **`status`** — counts by status, recent failures, age of last sync.
- **`verify`** — re-hashes on-disk PDFs, flags drift; `--repair` triggers re-download.

**Output convention (final summary every run):**

```
L0 sync complete (elapsed 3m 14s)
  Discovered:      127 filings
  Downloaded:       43 new PDFs (412.7 MB)
  Skipped:          78 (already-have: 65, no-english: 13)
  Failed:            6 (see manifest for details)
  Manifest:        2,341 success / 412 skipped / 14 failed
```

---

## 7. Politeness, retries, error handling

### HTTP politeness defaults

- **Concurrency cap:** 4 download workers. Discovery queries are serial (one window at a time).
- **Inter-request jitter:** 0.3-0.8s random per worker between downloads.
- **User-Agent:** `hk-ipo-research/0.1 (research; +<HKEX_CONTACT_EMAIL>)` — email from env, optional.
- **Discovery pacing:** 1-2s between API windows.

### Retry policy (per request, via `tenacity`)

| Error class | Retryable? | Strategy |
|---|---|---|
| Connection error, timeout | Yes | Exponential: 1s, 2s, 4s, 8s, 16s (5 attempts) |
| HTTP 5xx | Yes | Same |
| HTTP 429 | Yes | Respect `Retry-After`; else 30s, 60s, 120s (3 attempts) |
| HTTP 4xx (not 429) | No | Terminal; manifest records failure |
| Partial download / hash mismatch | Yes | 2 attempts, then terminal |
| Schema parse failure | Yes (once) | Fall back to alternate discovery path |

After in-pool retries exhaust, the entry lands in `status=failed`. `retry-failed` mode picks it up later.

### Failure quarantine

- Partial downloads write to `<ticker>.pdf.tmp` → `os.replace()` on success. Orphan `.tmp` files swept at startup.
- A failed discovery *window* (e.g., "March 2018") is logged to `data/logs/l0/failed_windows.json` and skipped — one bad window does not halt the job. Re-runnable via `backfill --since 2018-03-01 --until 2018-04-01`.

### Observability

- Per-run log: `data/logs/l0/run-<timestamp>.log` via existing `logging_setup.py`.
- Structured fields per request: `phase` (discovery/download), `ticker`, `attempt`, `elapsed_ms`, `outcome`.

---

## 8. Testing strategy

### Unit tests (`tests/test_l0_*.py`)

- `test_l0_filter.py` — `is_english_prospectus()` truth table (20+ fixtures: final EN, final TC-only, bilingual, A1, PHIP, supplemental, GEM, wrong doc type).
- `test_l0_manifest.py` — round-trip load/save, schema_version handling, file lock, atomic-replace.
- `test_l0_models.py` — `Filing` and `ManifestEntry` field validation; 4-digit tickers padded to 5; non-ASCII company names.
- `test_l0_downloader.py` — atomic write, hash verification, retry budget, partial-download cleanup. Uses `respx` to mock httpx.

### Integration tests (`tests/test_l0_discovery_integration.py`)

- `pytest-recording` captures real HKEX JSON API responses for a known small window; replayed on every CI run; recordings refreshed quarterly.
- Covers JSON-path happy case and JSON-malformed → HTML-fallback path.

### End-to-end (`tests/e2e/test_l0_e2e.py`, marker `@e2e`)

- Real network; hits HKEX live for the last 7 days. Asserts ≥1 filing discovered, filter doesn't crash, dry-run writes no files. Skipped in default `pytest`; included in `pytest -m e2e`.

### Golden ticker spot-check

- `tests/fixtures/l0_known_ipos.json` — ~10 hand-verified `(ticker, doc_id, expected_doc_url)` tuples spanning 2010-2025 across MB+GEM.
- A test asserts discovery returns each one for the covering date window. Primary regression guard against HKEX changing the `t1code`/`t2code` scheme.

---

## 9. Configuration

Additions to `src/hk_ipo/config.py`:

```python
RAW_PDFS_DIR              # already exists
L0_MANIFEST_PATH = RAW_PDFS_DIR / "manifest.json"
L0_LOG_DIR       = DATA_DIR / "logs" / "l0"

# Discovery endpoints — primary JSON, fallback HTML
L0_JSON_API_BASE = os.getenv(
    "HKEX_JSON_API_BASE",
    "https://www1.hkexnews.hk/search/titlesearchservlet.do",  # placeholder; exact path verified during implementation against the reference repo
)
L0_HTML_SEARCH_BASE = os.getenv(
    "HKEX_HTML_SEARCH_BASE",
    "https://www1.hkexnews.hk/search/titlesearch.xhtml",
)

L0_CONTACT_EMAIL = os.getenv("HKEX_CONTACT_EMAIL", "")
L0_DEFAULT_WORKERS = int(os.getenv("L0_WORKERS", "4"))
L0_BACKFILL_START_DATE = "2010-01-01"
```

> **Note on `L0_JSON_API_BASE`:** the exact JSON endpoint path is reverse-engineered from network traffic on the HKEX search page and from the `simonplmak-cloud/hkex-filing-scraper` reference. The default value above is illustrative; the implementing task confirms the exact URL during the spot-check phase (Section 4).

`.gitignore` additions:

```
data/raw_pdfs/manifest.json
data/raw_pdfs/*.pdf
data/raw_pdfs/*.pdf.tmp
data/logs/l0/
```

---

## 10. Acceptance criteria

The L0 implementation is considered complete when:

1. `python -m hk_ipo.l0 backfill --since 2024-01-01 --dry-run` discovers ≥30 final English prospectuses for 2024 H1, prints them, writes nothing.
2. `python -m hk_ipo.l0 backfill --since 2024-01-01 --limit 5` downloads exactly 5 PDFs, writes 5 entries to manifest, all `status=success`, all 5 PDFs open as valid PDF and have non-zero `file_sha256`.
3. Re-running the same `backfill` command immediately is a noop (idempotent — skips all 5 as `already-have`).
4. `python -m hk_ipo.l0 status` reports counts matching manifest contents.
5. `python -m hk_ipo.l0 verify` passes on all downloaded files.
6. All 10 golden-fixture tickers (`tests/fixtures/l0_known_ipos.json`) are discoverable.
7. Unit tests pass. Integration tests (recorded fixtures) pass in CI.
8. Manually killing the process mid-backfill, then re-running, resumes cleanly with no orphan `.tmp` files and no manifest corruption.
9. A downloaded prospectus PDF, when passed to `python -m hk_ipo.l1_sectioning <ticker>.pdf`, produces a valid `data/sections/<ticker>.json` (proves the L0→L1 contract holds).

---

## 11. Open items (resolved decisions, recorded for traceability)

| Item | Decision |
|---|---|
| Spec file path | `working/spec-l0.md` (don't clobber `working/spec.md` which holds the L1-L7 canonical spec). |
| Concurrent download workers default | 4. Bump after observing steady-state behavior. |
| Discovery date windowing | Monthly. ~192 windows for the full 16-year backfill. |
| `t1code`/`t2code` values | Best-effort from reference repo; spot-checked against golden fixture during implementation. |
| Manifest commit policy | Excluded from git via `.gitignore`. |
| Multi-version prospectus handling | Final only. Bumped if needed in a future spec. |
| Python version | 3.11+ (matches `pyproject.toml`). |
| New runtime deps | `httpx`, `selectolax`, `tenacity`, `portalocker`. |
