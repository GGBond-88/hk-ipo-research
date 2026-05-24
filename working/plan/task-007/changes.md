# Changes: Task-007

## Files
- [new] tests/test_l4_categorize.py
- [mod] tests/test_l4_categorize.py
- [mod] working/plan/task-007/implement-review-results.md

## Summary
Created the full unit test suite (43 tests) for the L4 hierarchical categorizer as the RED phase of TDD. All 43 tests fail with `ModuleNotFoundError: No module named 'hk_ipo.l4_categorize'` since the module does not exist yet.

### Issue Fixes (from implement-review-results.md)
- **SR-001**: Removed misleading "The LLM call is mocked." from docstring; test file covers only pure-logic functions.
- **CR-004**: Updated `test_golden_fixture_loader` to write fixture data to a `tmp_path` JSON file and pass the `Path` to `load_golden_fixture`, making the API contract unambiguous (accepts file path, returns parsed dict). Added `import json` (now actually used).
- **CR-005**: Added two negative-delta rebalance tests: `test_rebalance_negative_delta_within_tolerance` (surplus within tolerance = subtract from largest) and `test_rebalance_negative_delta_exceeds_tolerance` (surplus exceeds tolerance = no rebalance).
- **CR-006**: Updated `test_parent_sum_within_tolerance_passes` (sum=99.7, delta=0.3 vs tolerance=0.5) and `test_main_sum_under_parent_within_tolerance_passes` (main sum=64.8 vs parent=65.0, delta=0.2) to use non-zero within-tolerance deltas, exercising the tolerance comparison logic.
- **CR-007**: Added `test_output_appends_to_existing_csv` which calls `append_sub_proposals_csv` twice on the same file path, asserting 1 header + 2 data rows, no duplicate header, and correct data order.
- **CR-008**: Added `test_validate_parent_sums_empty_returns_empty` and `test_validate_main_sums_empty_returns_empty` -- empty inputs are vacuously valid (no violations).
- **CR-009**: Added `test_match_rate_mismatched_sizes_expected_nonempty_predicted_empty` and `test_match_rate_mismatched_sizes_predicted_nonempty_expected_empty` -- mismatched dict sizes return 0.0.
- **CR-010**: Added `test_load_golden_fixture_file_not_found`, `test_load_golden_fixture_malformed_json`, and `test_load_golden_fixture_missing_uses_key` -- error-path contracts for file I/O.
- **CR-011**: Added `test_limit_non_integer_raises_system_exit`, `test_unknown_flag_raises_system_exit`, and `test_no_arguments_raises_system_exit` -- error-path contracts for CLI argument parsing.
- **CR-012**: Added `test_output_appends_empty_proposals_no_file_created` -- empty proposals list must not create a header-only file.
