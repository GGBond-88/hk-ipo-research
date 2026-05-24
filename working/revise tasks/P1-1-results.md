# P1-1 Results: Real end-to-end validation on 6 PDFs + spec A-checks

Date: 2026-05-21
Run ID: c384ca29-faf1-436c-9ae7-bc0a677f4187

## A. Cost Preview

**Estimated**: $0.0192 (42,000 input tokens, 27,000 output tokens, deepseek/deepseek-v4-pro)

Note: This is a low estimate that only covers L2+L4 token counts. The actual cost may be higher due to L5 enrichments which also make LLM calls.

## B. Pipeline Run Summary

Command: `python scripts/run_pipeline.py --workers 4`

Exit code: 1 (expected -- at least one ticker had stage failures)

| Stage       | OK  | Failed | Total | Notes |
|-------------|-----|--------|-------|-------|
| L1          | 7   | 0      | 7     | Used cached data; filename pattern `\d{4,5}` excludes all 6 actual PDFs (13-digit names). L1 produces NO fresh output. |
| L2          | 0   | 0      | 7     | All 7 skipped (already cached). When run with --force, gets LLM empty response error on 03750, pydantic validation errors on some. |
| L3          | 2   | 5      | 7     | 5 of 7 tickers have data quality issues (amount/percentage/index consistency errors). Key findings: total_net_proceeds missing for 1187, percentage sum != 100% for several. |
| L4          | 7   | 0      | 7     | All 7 categorized. Some with parent_sum violations: 6031=181.1%, 2698=115.0%, 6871=107.0%, 1187=70.0%. |
| L5.geo      | 7   | 6      | 13    | Total 13 = 7 categorized filenames + 6 pre-existing enriched. 6 "failed" reported but likely just count mismatches between input/output file naming. Enrichment data in the `enrichments` key is correct. |
| L5.country  | 7   | 6      | 13    | Same as above |
| L5.industry | 7   | 6      | 13    | Same as above |
| L5.specificity | 7 | 6    | 13    | Same as above |
| L5.timeline | 7   | 6      | 13    | Same as above |
| L5.capex_opex | 7 | 6      | 13    | Same as above |
| L5.esg_tag  | 7   | 6      | 13    | Same as above |
| L5.commitment | 7 | 6      | 13    | Same as above |
| L6          | 6   | 1      | 7     | 6031 failed: NOT NULL constraint failed: uses.percentage |
| L7          | 1   | 0      | 1     | All 8 frontend files + sankey/ generated |

## C. Output Validation

### C1. Categorized JSON files
- **Count**: 7 files (excluding .gitkeep)
- **Expected**: 6
- **Result**: FAIL (7 != 6)
- **Files**: 03750.json, 2025051200005.json, 2025102000017.json, 2025103100021.json, 2026042700013.json, 2026050800015.json, ltn20180907011.json
- **Evidence**: 03750.json and 2025051200005.json both represent the SAME ticker (3750/03750) -- this is a duplicate caused by the `all_files=True` flag filtering logic in L1 combined with pre-existing cached 03750 data from a prior run.
- **Root cause**: L1 filters filenames to `\d{4,5}.pdf`, which excludes all 6 actual PDFs (all have 13-digit timestamps or mixed alphanumeric). The 03750.json in cached data predates this run and creates a phantom duplicate.

### C2. Enriched JSON files
- **Count**: 7 files (excluding .gitkeep)
- **Expected**: 6
- **Result**: FAIL (7 != 6)
- **Files**: 03750.json, 1187.json, 2698.json, 3690.json, 3750.json, 6031.json (PASS if counting unique tickers: 03750, 1187, 2698, 3690, 3750, 6031, 6871 = 7)
- **Note**: Both 03750 and 3750 exist as separate entries (same company, different HK ticker padding)

### C3. Enrichment block counts per enriched file
- **Expected**: 8 blocks each (geo, country, industry, specificity, timeline, capex_opex, esg_tag, commitment)
- **Result**: PASS
- **Evidence**: All 7 enriched files contain exactly 8 keys under `enrichments`: ['capex_opex', 'commitment', 'country', 'esg_tag', 'geo', 'industry', 'specificity', 'timeline']

### C4. Database (data/ipo.db)
- **DB exists**: True
- **Companies count**: 6
- **Company tickers**: ['03750', '1187', '2698', '3690', '3750', '6871']
- **Missing**: 6031 (failed L6 load: NOT NULL constraint failed: uses.percentage)
- **Result**: PARTIAL PASS (6 of 7 tickers loaded; 6031 has null percentage values preventing DB insertion)

### C5. Frontend data files
- **Result**: PASS
- **Files present**:
  - manifest.json: YES
  - companies.json: YES
  - taxonomy.json: YES
  - time_series.json: YES
  - by_industry.json: YES
  - by_geo.json: YES
  - cross_dim.json: YES
  - sankey/ directory: YES (9 files: 00001.json, 00002.json, 03750.json, 1187.json, 2698.json, 3690.json, 3750.json, 6871.json)

### C6. Log files
- **Count**: >= 5 log files in data/logs/
- **Result**: PASS
- **Most recent run log**: c384ca29-faf1-436c-9ae7-bc0a677f4187.jsonl (24 lines, 13 ok + 1 skipped + 10 failed)

### C7. Taxonomy proposals CSV
- **File exists**: True
- **Content**: 10 lines (header + 9 data rows)
- **Result**: PASS
- **Sample proposals**: General Working Capital, Unspecified use, Global service network expansion, Overseas manufacturing build-out, etc.

## D. Spec A-Checks

### D1. A4.5: L4 Main-Category Match Rate on Ticker 3750
- **Golden fixture**: tests/fixtures/l4_golden/3750.json (2 uses)
- **Live output**: data/categorized/2025051200005.json (2 uses)
- **Match rate**: 1.0000 (2/2)
- **Matches**:
  - use_001: "Capacity Expansion" = "Capacity Expansion"
  - use_002: "General Working Capital" = "General Working Capital"
- **Result**: PASS (>= 0.90 threshold)

### D2. A7.4: Manifest Idempotency (3 Export Runs)
- **Export command**: `python -m hk_ipo.analysis.export --db data/ipo.db --out frontend/public/data/`
- **Manifest hashes (MD5)**:
  - Run 1: e5e1974141d6df7d919c706f9d280778
  - Run 2: e5e1974141d6df7d919c706f9d280778
  - Run 3: e5e1974141d6df7d919c706f9d280778
- **Result**: PASS (all 3 hashes identical)

### D3. A9.2: Corrupt PDF Failure Recording
- **Test**: Created invalid PDF (echo "not a pdf" > data/raw_pdfs/99999.pdf), ran pipeline --limit 1
- **Pipeline_runs result**:
  - hk_ticker: 99999
  - stage: L1
  - status: failed
  - error_message: "L1: no output for 99999"
- **Result**: PASS (status='failed', non-null error_message)
- **Note**: The error message is generic ("no output for 99999") rather than the specific L1 error ("Failed to open file '...99999.pdf'"). The actual parsing error is not propagated to pipeline_runs.error_message -- logged only to stderr. This meets the minimum spec requirement but is a soft weakness.
- **Cleanup**: 99999.pdf removed.

## E. Issues Discovered

1. **L1 filename filter excludes all real PDFs** (line 35 of l1_sectioning.py): `_FILENAME_TICKER_RE = re.compile(r"^(\d{4,5})$")` matches pure 4-5 digit filenames like `03750.pdf`, but all 6 actual PDFs use 13-digit HKEX document numbers (e.g., `2025051200005.pdf`) or mixed alphanumeric (`ltn20180907011.pdf`). This means L1 cannot process ANY real HKEX PDF in the current batched pipeline.

2. **portalocker dependency missing** from pyproject.toml/requirements: `portalocker` is imported in `l4_categorize.py` but not declared as a dependency. Had to manually `pip install portalocker`.

3. **L5 ok/failed counting bug**: L5 enrichment stages report `ok=7, failed=6, total=13`. The "failed" count appears inflated because `_tickers_from_dir(enriched_dir)` returns all pre-existing enriched files from prior runs, while `results` from `mod.run()` only contains the 7 categorized tickers just processed. The diff of `13 - 7 = 6` gets reported as "failed" when it really means "files from a different source".

4. **6031 null percentage issue**: The 2025102000017.json extracted data has use items with null percentages (L3 validation detected "category_raw_present" error on use_001). This prevents L6 DB insertion due to NOT NULL constraint on `uses.percentage`.

5. **L2 finish_reason=None pydantic error**: When running L2 with --force on some PDFs, the OpenRouter API returns `finish_reason=None` which triggers a pydantic validation error in the OpenAI SDK's ChatCompletion model. This is likely a model-specific behavior of deepseek-v4-pro through OpenRouter.

6. **03750/3750 duplicate**: Both `03750` and `3750` exist as distinct enriched entries and DB rows for what appears to be the same company. One comes from a pre-existing cached file, the other from 2025051200005.pdf processing. This could cause data duplication in the frontend.

## Summary

| Check | Result | Details |
|-------|--------|---------|
| C1: 6 categorized JSON | FAIL | 7 files (duplicate 03750/3750) |
| C2: 6 enriched JSON | FAIL | 7 files (both 03750 and 3750) |
| C3: 8 enrichment blocks each | PASS | All 7 have all 8 dimensions |
| C4: DB with 6 companies | PARTIAL | 6 of 7 loaded; 6031 missing |
| C5: Frontend data files | PASS | All 8 + sankey present |
| C6: Log files | PASS | >= 5 log files |
| C7: taxonomy_proposals.csv | PASS | 10 lines, not empty |
| A4.5: Match rate >= 0.90 | PASS | 1.0000 (2/2) |
| A7.4: Manifest idempotency | PASS | All 3 hashes match |
| A9.2: Corrupt PDF recording | PASS | status=failed, non-null error |

**Total wall time**: ~2-3 minutes (using cached L1/L2 data; would be 15-30 min with full LLM re-extraction)
