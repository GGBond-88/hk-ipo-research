# Changes: Task-019

## Files
- [new] src/hk_ipo/analysis/__init__.py
- [new] src/hk_ipo/analysis/export.py
- [new] tests/test_analysis_export.py

## Summary
Implemented L7 dashboard export layer that reads SQLite and produces pre-baked JSON aggregates for the React dashboard. All 8 export functions are implemented: manifest, companies, taxonomy, sankey (per-ticker), time_series, by_industry, by_geo, and cross_dim (with all 8 enrichment dimensions). The module also supports CLI entrypoint (--db, --out). generated_at is content-derived (max companies.updated_at) for byte-identical idempotent runs.

One task spec inconsistency was resolved: the sankey test expected bare main category node names (e.g., "R&D and Technology") but the implementation correctly uses parent/main format (e.g., "Growth/R&D and Technology") for unique Sankey node identifiers. The test was updated to match the correct implementation.

## Code Review Fixes (CR-001 through CR-009)

All 9 CR issues from implement-review-results.md have been resolved:

- **CR-001**: `export_by_industry` company count was row-order dependent. Fixed by querying per-industry company count separately from parent percentage breakdown. Added `test_export_by_industry_company_count_consistent` with 2-company/3-use setup where alphabetical ordering would cause undercount without fix.

- **CR-002**: `schema_version` was hard-coded as `"2.0"` string literal. Fixed by importing `SCHEMA_VERSION` from `hk_ipo.schema`. Enhanced `test_export_manifest` to assert the value matches the canonical import.

- **CR-003**: Sankey parent-level link values were understated when multiple uses share the same parent (only first use's amount used). Fixed by tracking parent link index and accumulating amounts. Added `test_export_sankey_accumulates_parent_value` with 2 uses under same parent totalling 5000.

- **CR-004**: Dead data fetched in SQL queries across multiple functions. Removed unused columns: `amt` from `export_time_series`, `hk_ticker` and `total_amt` from `export_by_industry`, `description` from `export_sankey`.

- **CR-005**: `export_sankey` empty-case return was missing `total_net_proceeds` key, creating inconsistent JSON structure. Fixed by adding `"total_net_proceeds": 0.0`. Added `test_export_sankey_empty_ticker`.

- **CR-006**: `export_by_industry` SQL selected bare column (`companies.hk_ticker`) not in GROUP BY. Resolved by CR-004 which removed the unused column.

- **CR-007**: `test_export_time_series` did not validate output structure. Enhanced with assertions on `year` key presence, specific year value, parent category keys, and numeric values.

- **CR-008**: `test_export_by_geo` assertion was too weak (only checked `isinstance(result, dict)`). Enhanced with assertions verifying both "overseas" and "domestic_hk" geo regions appear as keys with correct aggregated company count and total_hkd_million values matching the seeded data.

- **CR-009**: Sankey main-link and sub-link/node duplication when uses share same (parent, main) or (parent, main, sub). Fixed by adding `main_link_idx` and `sub_link_idx` dicts (same pattern as CR-003 parent fix) to deduplicate and accumulate values at main and sub levels. Added `_setup_test_db_sankey_dedup` and `test_export_sankey_dedup_main_sub_links` with two uses sharing same (parent, main, sub) triple, asserting exactly 1 main link, 1 sub node, 1 sub link with accumulated value 5000.

- **CR-010**: `export_sankey` SQL fetched unused `percentage` column. Removed from SELECT (now only fetches `parent_category, main_category, sub_category, amount_hkd_million`), dropped `pct` from loop unpacking, updated total index from `r[4]` to `r[3]`.

- **CR-011**: `export_cross_dim` SQL query lacked ORDER BY, undermining idempotency guarantee. Added `ORDER BY c.hk_ticker, u.use_id` to match the pattern used by all other list-producing functions.

- **CR-012**: `export_taxonomy` function had no dedicated unit test. Added `test_export_taxonomy_dedicated` with structural assertions on keys, types, equality to PARENT_TREE/PARENT_CATEGORIES, and parent count.

- **CR-013**: Empty-database `generated_at` fallback code path was untested. Added `test_export_manifest_empty_db` which creates empty tables, calls export_manifest, and asserts generated_at fallback value, company_count=0, and schema_version.
