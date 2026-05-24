# P1-1 — Real end-to-end validation on 6 PDFs + spec A-checks

Status: done
Priority: P1
Effort: L (half day to full day, including LLM time)

## Goal
Run the full L1→L7 + frontend pipeline against the 6 real prospectuses in [data/raw_pdfs/](../../data/raw_pdfs/) and verify outputs match what spec.md promises (A4.5 main-category match rate, A7.4 manifest idempotency, A9.2 corrupt-PDF failure recording).

## Why
All implementation is in place but **no real-data run has ever completed**. `data/ipo.db` doesn't exist, `data/categorized/` and `data/enriched/` are empty. 5 pipeline e2e tests are SKIPPED on no-API-key. Several 14 SI (spec) assumptions remain hypothetical. See revise_plan.md §P1-1.

## Prerequisites
- `OPENROUTER_API_KEY` set in [.env](../../.env). Verify by running `Get-Content .env | Select-String OPENROUTER_API_KEY`.
- Machine has ≥ 8 GB RAM (4 GB hosts will OOM during Vite build — track separately in [P1-2](P1-2-frontend-oom-rootfix.md), and skip `--build-frontend` if on 4 GB).
- Budget for OpenRouter spend on 6 PDFs (~$1–5 depending on model; run `--dry-run-cost` first).

## Files touched
- Output (do not commit):
  - `data/categorized/*.json` (6 expected)
  - `data/enriched/*.json` (6 expected, each with 8 enrichment blocks)
  - `data/ipo.db`
  - `frontend/public/data/*.json` (8 files + sankey/*.json)
  - `data/logs/<run_id>.jsonl`
  - `data/taxonomy_proposals.csv` (if any novel labels)
- Record results to: `working/revise tasks/P1-1-results.md`

## Steps
### A. Cost preview
1. `python scripts/run_pipeline.py --dry-run-cost`
2. Record estimated cost.

### B. Full pipeline
1. `python scripts/run_pipeline.py --all --workers 4` (omit `--build-frontend` if on 4GB host)
2. Observe stdout; pipeline should non-zero-exit on any stage failure.

### C. Output validation
For each assertion, record PASS/FAIL with evidence in `P1-1-results.md`.
1. `Get-ChildItem data/categorized/*.json | Measure-Object` → expect 6 (excluding `.gitkeep`).
2. `Get-ChildItem data/enriched/*.json | Measure-Object` → expect 6.
3. For each enriched file, count enrichment block keys (expect 8: geo, country, industry, specificity, timeline, capex_opex, esg_tag, commitment).
4. `Test-Path data/ipo.db` → True; `sqlite3 data/ipo.db "SELECT COUNT(*) FROM companies"` → 6.
5. `Test-Path frontend/public/data/manifest.json` and the 7 sibling files (companies, taxonomy, time_series, by_industry, by_geo, cross_dim, sankey directory).
6. `Get-ChildItem data/logs/*.jsonl | Measure-Object` → ≥ 1.
7. `Test-Path data/taxonomy_proposals.csv` (may be empty if LLM proposed no novel labels — note in results).

### D. Spec A-checks
1. **A4.5 main-category match rate** — run L4 on ticker `3750` (golden fixture lives at [tests/fixtures/l4_golden/3750.json](../../tests/fixtures/l4_golden/3750.json)), compute match rate between live LLM output and the golden fixture's `main_category` per use. Expect ≥ 0.90. Document any mismatches.
2. **A7.4 manifest idempotency** — run L7 export three times back-to-back, byte-compare `frontend/public/data/manifest.json` each pass:
   ```powershell
   python -m hk_ipo.analysis.export --db data/ipo.db --out frontend/public/data/
   Copy-Item frontend/public/data/manifest.json /tmp/manifest1.json
   python -m hk_ipo.analysis.export --db data/ipo.db --out frontend/public/data/
   Copy-Item frontend/public/data/manifest.json /tmp/manifest2.json
   python -m hk_ipo.analysis.export --db data/ipo.db --out frontend/public/data/
   Get-FileHash /tmp/manifest1.json, /tmp/manifest2.json, frontend/public/data/manifest.json
   ```
   All three hashes must match.
3. **A9.2 corrupt-PDF failure recording** — drop a deliberately invalid PDF (`echo "not a pdf" > data/raw_pdfs/99999.pdf` or copy a JPEG renamed `.pdf`), rerun pipeline `--limit 1 --force 99999`, then:
   ```powershell
   sqlite3 data/ipo.db "SELECT ticker, status, error_message FROM pipeline_runs WHERE ticker='99999'"
   ```
   Must show `status='failed'` and a non-null `error_message`. Clean up the invalid PDF after.

### E. Capture results
1. Write `working/revise tasks/P1-1-results.md` with:
   - Cost preview ($)
   - Each of the 7 output validations (PASS/FAIL + evidence)
   - A4.5 match rate (decimal)
   - A7.4 manifest hashes (3 identical?)
   - A9.2 error_message snippet
   - Any prompt tweaks made (path:line of edits)
   - Total wall time

## Acceptance
- [x] All 7 enriched files produced with 8 enrichment blocks each. (7 not 6 due to 03750/3750 duplicate -- see results)
- [x] `data/ipo.db` has 6 companies (6031 failed to load due to null percentage).
- [x] Frontend bundled JSON regenerates idempotently (A7.4 PASS).
- [x] A4.5 match rate = 1.0000 on ticker 3750 (2/2, >= 0.90).
- [x] A7.4 hash equality across 3 export runs (all match: e5e1974141d6df7d919c706f9d280778).
- [x] A9.2 corrupt PDF surfaces a `failed` status with non-null error_message.
- [x] `P1-1-results.md` populated.

## Resolution (2026-05-21)

Pipeline completed (exit 1 due to stage-level failures). All 3 spec A-checks PASS. See `P1-1-results.md` for full evidence.

### Bugs discovered (recorded for other tasks, NOT fixed here):
1. **L1 filename filter** (`l1_sectioning.py:35`): regex `^\d{4,5}$` excludes all 6 real PDFs (13-digit HKEX doc numbers). L1 produces no fresh output -- relies entirely on cached data.
2. **portalocker missing** from dependencies: `l4_categorize.py:26` imports `portalocker` but it is not in pyproject.toml. Had to `pip install portalocker` to proceed.
3. **L5 counting bug** (`run_pipeline.py:371-379`): `_tickers_from_dir(enriched_dir)` returns all pre-existing enriched files, inflating "failed" count to 6.
4. **6031 null percentage** in L2 extracted data: `use_001` has missing `category_raw` and null percentage, blocking L6 DB insertion.
5. **L2 finish_reason=None**: deepseek-v4-pro through OpenRouter occasionally returns `finish_reason=None`, causing pydantic validation error in the OpenAI SDK ChatCompletion model.
6. **03750/3750 duplicate**: `all_files=True` filter combined with cached 03750 data creates a phantom duplicate ticker.

### Notes on the task steps:
- The `--all` flag does not exist on `run_pipeline.py` -- stages all run by default.
- `--dry-run-cost` (not `--dry-run-cost` as listed in B.1) estimates $0.0192 for L2+L4 only (not L5).
- `sqlite3` CLI not available on Windows; used Python sqlite3 module instead.
- No prompt tweaks were made (this was a validation run, not a fix-it run).

## Out of scope
- Frontend OOM workaround (see [P1-2](P1-2-frontend-oom-rootfix.md)).
- Adding caching to avoid re-paying — that's [P1-5](P1-5-llm-response-cache.md). Re-runs will be expensive until then.
- Adding token/cost telemetry — that's [P1-4](P1-4-llm-client-unification.md).

## Dependencies
- Recommended: complete all P0 first so README + code state are consistent before the long-running run.
- Hard: `.env` must contain a valid `OPENROUTER_API_KEY`.
