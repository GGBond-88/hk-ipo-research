# Test Results: Task-019

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_export_companies_json | PASS | PASS | no | - |
| test_export_sankey_for_ticker | PASS | PASS | no | - |
| test_export_time_series | PASS | PASS | no | CR-007: enhanced with structural assertions |
| test_export_by_industry | PASS | PASS | no | - |
| test_export_by_geo | PASS | PASS | no | CR-008: enhanced with geo region and aggregate value assertions |
| test_export_cross_dim | PASS | PASS | no | - |
| test_export_manifest | PASS | PASS | no | CR-002: asserts schema_version matches canonical import |
| test_export_manifest_generated_at_is_content_derived | PASS | PASS | no | - |
| test_full_export_writes_to_disk | PASS | PASS | no | - |
| test_export_taxonomy_dedicated | PASS | PASS | no | CR-012: new test validates taxonomy output keys, types, data equality |
| test_export_manifest_empty_db | PASS | PASS | no | CR-013: new test validates empty-DB fallback generated_at path |
| test_export_idempotent | PASS | PASS | no | - |
| test_export_by_industry_company_count_consistent | PASS | PASS | no | CR-001: regression test - 2 companies, parent undercount scenario |
| test_export_sankey_dedup_main_sub_links | PASS | PASS | no | CR-009: regression test - 2 uses sharing same (parent, main, sub) triple |
| test_export_sankey_accumulates_parent_value | PASS | PASS | no | CR-003: regression test - multiple uses under same parent |
| test_export_sankey_empty_ticker | PASS | PASS | no | CR-005: regression test - empty-case total_net_proceeds key |

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 16
- UNEXPECTED (Result!=Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0

## Full Suite (excluding e2e)
470 passed, 0 failed, 0 skipped in 13.79s.
