# Test Results: Task-013

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_dimension_and_version | PASS | PASS | no | - |
| test_short_term_0_12m | PASS | PASS | no | - |
| test_medium_term_12_24m | PASS | PASS | no | - |
| test_long_term_24_36m | PASS | PASS | no | - |
| test_very_long_36m_plus | PASS | PASS | no | - |
| test_unspecified_no_timeline | PASS | PASS | no | - |
| test_hyphenated_12_month_is_short_term | PASS | PASS | no | Added for CR-005 fix verification |
| test_hyphenated_5_year_is_very_long | PASS | PASS | no | Added for CR-005 fix verification |
| test_hyphenated_3_year_is_long_term | PASS | PASS | no | Added for CR-005 fix verification |
| test_hyphenated_2_year_is_medium_term | PASS | PASS | no | Added for CR-005 fix verification |
| test_spelled_out_word_numbers | PASS | PASS | no | Added for SR-002 fix verification |
| test_hyphenated_very_long_qualitative | PASS | PASS | no | Added for CR-007 fix verification |
| test_hyphenated_extended_horizon | PASS | PASS | no | Added for CR-007 fix verification |
| test_yearly_not_matched_as_year | PASS | PASS | no | Added for CR-008 fix verification |
| test_model_not_matched_as_mo | PASS | PASS | no | Added for CR-008 fix verification |
| test_first_yearbook_not_matched | PASS | PASS | no | Added for CR-008 fix verification |
| test__enrich_one_processes_arbitrary_record | PASS | PASS | no | Added for CR-006 fix verification |
| test_run_ticker_mode_uses_categorized_fallback | PASS | PASS | no | Added for CR-006 fix verification |

## Full Suite (except e2e)

294 passed in 9.86s. No regressions.

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 18
- UNEXPECTED (Result≠Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0
