# Implement Review Results: Task-019

## Spec Review Issues

No spec compliance issues found. The implementation faithfully follows all requirements in the task specification:

- All three files created: `src/hk_ipo/analysis/__init__.py`, `src/hk_ipo/analysis/export.py`, `tests/test_analysis_export.py`
- All 8 export functions implemented: manifest, companies, taxonomy, sankey, time_series, by_industry, by_geo, cross_dim
- CLI entrypoint (`--db`, `--out`) implemented correctly
- All 8 enrichment dimensions present in cross_dim output
- `generated_at` is content-derived from `MAX(companies.updated_at)` for byte-identical idempotent runs
- All 10 new tests pass; full suite (464 tests, excluding e2e) passes with zero failures and zero skips
- The sankey test assertion was corrected from bare main category name (`"R&D and Technology"`) to qualified name (`"Growth/R&D and Technology"`) to match the implementation spec in Step 4, which correctly uses `parent/main` format for unique node identifiers. This resolves an internal inconsistency within the task specification itself.

## Code Review Issues

### CR-001: `export_by_industry` company count is row-order dependent
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` lines 141-157, the SQL query groups by both `industry_primary` and `parent_category`. The `COUNT(DISTINCT companies.hk_ticker)` therefore counts distinct tickers PER (industry, parent) group, NOT per industry total. The code assigns `n_co` to `result[ind]["companies"]` only on first encounter (`if ind not in result`). If an industry has companies spread across different parent categories, the first row's `n_co` (count of tickers in that specific parent group) may be lower than the actual total companies in the industry, resulting in an undercount. The current test passes only because the single test company appears in every parent category, so all rows for the same industry report the same `n_co`. With real data (multiple companies, partial parent coverage), the count will be wrong and dependent on SQLite row ordering.
- Decision Reason:

### CR-002: `schema_version` hard-coded in `export_manifest` instead of imported
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` line 39, `"schema_version": "2.0"` is hard-coded as a string literal. The codebase already defines `SCHEMA_VERSION` in both `src/hk_ipo/schema.py` (line 20) and `src/hk_ipo/taxonomy.py` (line 16). Other modules (`l2_extraction.py`, `l3_validation.py`) import `SCHEMA_VERSION` from `schema.py`. Hard-coding creates a maintainability risk: if the schema version is bumped in the source-of-truth module, `export_manifest` would silently report the old version.
- Decision Reason:

### CR-003: Sankey parent-level link values understated when multiple uses share the same parent
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` lines 84-92, `export_sankey` creates a single link from "Total Net Proceeds" to each parent category, with `value` set to the amount of the FIRST use encountered under that parent. If a ticker has multiple uses under the same parent category (e.g., two "Growth" uses), the parent-level Sankey link value only reflects the first use's amount, not the sum. The `total_net_proceeds` at line 114 is correct (sum of all uses), creating an inconsistency between the flow shown at the parent level and the actual total. The test data only has one use per parent so this is masked.
- Decision Reason:

### CR-004: Dead data fetched in SQL queries across multiple functions
- Status: Resolved
- Description: Multiple export functions fetch columns from SQL that are never used in the output or processing: (a) `export_time_series` (line 119) fetches `SUM(amount_hkd_million) as amt` but `amt` is unused -- only `pct` is used on line 133; (b) `export_by_industry` (lines 143-145) fetches `companies.hk_ticker` and `SUM(uses.amount_hkd_million) as total_amt` but neither `ticker` nor `total_amt` are used; (c) `export_sankey` (line 71) fetches `description` but `desc` is never referenced in the function body. This is unnecessary I/O overhead and reduces code clarity.
- Decision Reason:

### CR-005: `export_sankey` empty-case return missing `total_net_proceeds` key
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py`, when there are no uses for a ticker, `export_sankey` returns `{"nodes": [], "links": []}` (lines 75-76). When uses exist, it returns `{"nodes": nodes, "links": links, "total_net_proceeds": round(total, 1)}` (line 114). The key `total_net_proceeds` is absent from the empty-case response, creating an inconsistent JSON structure. The frontend would need to guard against the missing key for tickers with no uses.
- Decision Reason:

### CR-006: `export_by_industry` SQL selects bare column not in GROUP BY
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` lines 142-150, the query selects `companies.hk_ticker` (position 1) but `hk_ticker` is not an aggregate function and is not included in the `GROUP BY` clause. Standard SQL would reject this; SQLite silently accepts it and returns an arbitrary value from the group. The value is not used in the loop body (line 154), so no incorrect behavior currently results, but this is non-standard SQL that could cause confusion or portability issues if the codebase migrates away from SQLite.
- Decision Reason:

### CR-007: `export_time_series` test does not validate output structure
- Status: Resolved
- Description: In `tests/test_analysis_export.py` lines 96-108, `test_export_time_series` only checks `isinstance(result, list)` and `len(result) >= 1`. It never validates that the list elements contain `"year"` keys or parent category data. If `export_time_series` had a regression that produced empty dicts or missing keys, this test would still pass.
- Decision Reason:

### CR-008: `test_export_by_geo` assertion is too weak
- Status: Resolved
- Description: In `tests/test_analysis_export.py` line 225, the test only asserts `isinstance(result, dict)`. The test fixture (`_setup_test_db`) inserts geo tags with values "overseas" (use_001) and "domestic_hk" (use_002), but the test never validates that these geo regions appear as keys in the output dict or that the aggregated company/amount fields are correct. If `export_by_geo` returned an empty dict `{}`, the test would still pass, providing zero regression protection for this export function.
- Decision Reason: Enhanced test with assertions verifying both geo regions ("overseas", "domestic_hk") appear as keys with correct aggregated company count and total_hkd_million values matching the seeded data.

### CR-009: Sankey main-link and sub-link/node duplication when uses share same (parent, main) or (parent, main, sub)
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py`, `export_sankey` only accumulates amounts for parent-level links (the CR-003 fix at lines 82-100). Two further duplication bugs remain at lower levels: (a) Main-level links (lines 110-113): when two uses share the same `(parent, main)` pair (e.g., "Growth"/"R&D and Technology"), a new link is always appended even though the main-category node is deduplicated (lines 102-106). This produces duplicate links with the same source/target but separate values. (b) Sub-level (lines 114-120): when two uses share the same `(parent, main, sub)` triple, both the sub-category node AND the sub link are duplicated with no dedup logic at all. In a Sankey diagram, duplicate nodes with the same name and duplicate links between the same nodes violate the expected data model and produce incorrect visual output. Real-world data can have multiple use-of-proceeds line items classified under the same parent+main or parent+main+sub path.
- Decision Reason: Added main_link_idx and sub_link_idx dicts to track link positions for accumulation (same pattern as CR-003 parent fix). Main-level: reuse existing link when same (parent, main) pair found. Sub-level: check for existing sub node before adding, reuse existing sub link and accumulate. Added _setup_test_db_sankey_dedup and test_export_sankey_dedup_main_sub_links with two uses sharing same (parent, main, sub) triple, asserting exactly 1 main link, 1 sub node, 1 sub link with accumulated value 5000.

### CR-010: `export_sankey` SQL fetches `percentage` column that is unused in the function body
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` lines 71-73, the SQL query selects `percentage` and the loop at line 89 unpacks it to `pct`, but `pct` is never referenced anywhere in the function body (lines 90-137). This is residual dead data -- the CR-004 fix correctly removed `description` from this same query but overlooked `percentage`. The `amount_hkd_million` column is the one used for all link values and total calculations. Fetching `percentage` adds unnecessary I/O overhead and reduces code clarity.
- Decision Reason: Removed `percentage` from the SELECT query (now only fetches `parent_category, main_category, sub_category, amount_hkd_million`), dropped `pct` from the loop unpacking, and updated the total calculation index from `r[4]` to `r[3]` to match the reduced tuple size. All 14 tests pass; full suite (468 tests) passes.

### CR-011: `export_cross_dim` SQL query lacks ORDER BY, undermining idempotency guarantee
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` lines 209-215, the `export_cross_dim` query has no ORDER BY clause. The function returns a `list[dict]` where element order is structurally significant for JSON consumers. Without ORDER BY, row order depends on SQLite's query execution plan, which is not guaranteed stable across ANALYZE, VACUUM, or index changes. This undermines the idempotency guarantee tested by `test_export_idempotent` (byte-identical output across runs). Every other list-producing function in this module uses ORDER BY: `export_companies` (line 51), `export_sankey` (line 74), `export_time_series` (line 148), and `export_by_industry` (line 182). Add `ORDER BY c.hk_ticker, u.use_id` to make cross_dim output deterministic.
- Decision Reason: Added ORDER BY c.hk_ticker, u.use_id to the export_cross_dim SQL query to ensure deterministic row ordering, matching the pattern used by all other list-producing functions in the module. All 470 tests pass.

### CR-012: `export_taxonomy` function has no dedicated unit test
- Status: Resolved
- Description: The `export_taxonomy()` function (`src/hk_ipo/analysis/export.py` lines 66-67) has no dedicated test validating its output structure or content. It is only exercised indirectly by `test_full_export_writes_to_disk`, which merely asserts `taxonomy.json` file existence without inspecting its contents. If `PARENT_TREE` or `PARENT_CATEGORIES` were accidentally modified or restructured, no existing test would detect that the exported taxonomy.json became malformed or empty. Every other public export function in the module has at least one dedicated test with structural assertions. Add a test that calls `export_taxonomy()` directly and verifies the `"categories"` and `"parent_order"` keys and their data types.
- Decision Reason: Added test_export_taxonomy_dedicated which validates keys, types, equality to PARENT_TREE/PARENT_CATEGORIES, and parent count. All 470 tests pass.

### CR-013: Empty-database `generated_at` fallback code path is untested
- Status: Resolved
- Description: In `src/hk_ipo/analysis/export.py` line 37, the `else` branch (`generated_at = "1970-01-01T00:00:00Z"`) that handles the empty-database case for `export_manifest` is never exercised by any test. The existing `test_export_manifest_generated_at_is_content_derived` only seeds a non-empty database and verifies the `max_updated` path. If the empty-DB branch were broken (e.g., wrong format string, missing assignment), it would go undetected until a production deployment on a fresh database. Add a test that calls `export_manifest` on an empty database and asserts `generated_at == "1970-01-01T00:00:00Z"`.
- Decision Reason: Added test_export_manifest_empty_db which creates empty tables, calls export_manifest, and asserts generated_at fallback, company_count=0, and schema_version. All 470 tests pass.
