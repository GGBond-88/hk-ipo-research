# Test Results: Task-006

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_empty_category_raw_flags_error | PASS | PASS | no | - |
| test_all_category_raw_non_empty_passes | PASS | PASS | no | - |
| test_missing_total_net_proceeds_flags_error | PASS | PASS | no | - |
| test_schema_version_mismatch_warns | PASS | PASS | no | - |
| test_schema_version_present_no_warning | PASS | PASS | no | - |
| test_strict_mode_exits_nonzero | PASS | PASS | no | - |
| test_total_proceeds_zero_is_valid | PASS | PASS | no | - |
| test_total_proceeds_negative_is_error | PASS | PASS | no | - |
| test_category_raw_none_is_flagged | PASS | PASS | no | - |
| test_cli_strict_single_exits_nonzero | PASS | PASS | no | - |
| test_cli_strict_single_passes_exits_zero | PASS | PASS | no | - |
| TestHappyPath::test_meituan_all_four_uses_passes | PASS | PASS | no | - |
| TestHappyPath::test_meituan_no_unexpected_warnings | PASS | PASS | no | - |
| TestRequiredFields::test_missing_uses_key_is_error | PASS | PASS | no | - |
| TestRequiredFields::test_null_hk_ticker_is_error | PASS | PASS | no | - |
| TestRequiredFields::test_null_document_date_is_error | PASS | PASS | no | - |
| TestTickerFormat::test_alpha_ticker_is_error | PASS | PASS | no | - |
| TestTickerFormat::test_three_digit_ticker_is_error | PASS | PASS | no | - |
| TestTickerFormat::test_four_digit_ticker_passes | PASS | PASS | no | - |
| TestTickerFormat::test_five_digit_ticker_passes | PASS | PASS | no | - |
| TestPercentageSum::test_sum_70_fails_at_default_tolerance | PASS | PASS | no | - |
| TestPercentageSum::test_sum_100_passes | PASS | PASS | no | - |
| TestPercentageSum::test_sum_exactly_at_tolerance_boundary_passes | PASS | PASS | no | - |
| TestAmountSum::test_amounts_sum_too_high_is_error | PASS | PASS | no | - |
| TestAmountSum::test_amounts_within_1pct_passes | PASS | PASS | no | - |
| TestItemConsistency::test_one_item_wildly_off_is_error | PASS | PASS | no | - |
| TestItemConsistency::test_consistent_items_no_error | PASS | PASS | no | - |
| TestNoDuplicateUseId::test_duplicate_use_id_is_error | PASS | PASS | no | - |
| TestNoDuplicateUseId::test_all_unique_use_ids_no_error | PASS | PASS | no | - |
| TestWarningOnly::test_null_percentage_downgrades_to_warning | PASS | PASS | no | - |
| TestWarningOnly::test_null_amount_downgrades_to_warning | PASS | PASS | no | - |
| TestWarningOnly::test_out_of_vocab_category_is_warning_not_error | PASS | PASS | no | - |
| TestMultiError::test_three_simultaneous_failures | PASS | PASS | no | - |
| TestToleranceBoundary::test_985_pct_fails_at_tolerance_1 | PASS | PASS | no | - |
| TestToleranceBoundary::test_985_pct_passes_at_tolerance_2 | PASS | PASS | no | - |
| TestValidateFile::test_writes_validated_json_with_validation_block | PASS | PASS | no | - |
| TestValidateFile::test_return_value_matches_written_file | PASS | PASS | no | - |
| TestIdempotence::test_calling_validate_record_twice_gives_same_result | PASS | PASS | no | - |
| TestIdempotence::test_record_not_mutated_by_validate_record | PASS | PASS | no | - |
| TestCategoryL1::test_out_of_vocab_category_deferred_to_category_vocab_not_l1 | PASS | PASS | no | - |
| TestCategoryL1::test_category_l1_exempt_when_category_proposed_set | PASS | PASS | no | - |
| TestCategoryL1::test_all_standard_category_l2_values_pass_l1_check | PASS | PASS | no | - |
| TestCategoryNullV2::test_category_none_no_category_vocab_warning | PASS | PASS | no | - |
| TestCategoryNullV2::test_empty_category_string_still_warns | PASS | PASS | no | - |
| TestSchemaVersion::test_absent_schema_version_is_warning | PASS | PASS | no | - |
| TestSchemaVersion::test_mismatched_schema_version_is_warning | PASS | PASS | no | - |
| TestSchemaVersion::test_matching_schema_version_no_warning | PASS | PASS | no | - |

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 47
- UNEXPECTED (Result!=Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0

## Black-Box Tests (tests/e2e/test_l3_blackbox.py)

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_help_output_lists_all_flags | PASS | PASS | no | All 4 flags documented |
| test_missing_required_arg_exits_nonzero | PASS | PASS | no | Neither --single nor --all |
| test_single_valid_record_exits_zero | PASS | PASS | no | PASS stdout, .validated.json with passed=True |
| test_single_invalid_record_exits_zero_without_strict | PASS | PASS | no | FAIL stdout, errors, exit 0 |
| test_strict_single_invalid_exits_nonzero | PASS | PASS | no | --strict + invalid -> exit != 0 |
| test_strict_single_valid_exits_zero | PASS | PASS | no | --strict + valid -> exit 0 |
| test_all_mode_processes_multiple_files | PASS | PASS | no | 2 passed, 1 failed summary |
| test_all_strict_exits_nonzero_on_any_failure | PASS | PASS | no | --all --strict non-zero on failure |
| test_all_empty_dir_produces_warn | PASS | PASS | no | WARN on empty directory |
| test_tolerance_pct_alters_validation_outcome | PASS | PASS | no | tol=1 FAIL, tol=5 PASS |
| test_empty_category_raw_produces_error | PASS | PASS | no | [category_raw_present] in errors |
| test_null_total_proceeds_produces_error | PASS | PASS | no | [total_proceeds_present] in errors |
| test_schema_version_mismatch_produces_warning | PASS | PASS | no | PASS with [schema_version] warning |
| test_validated_json_has_complete_validation_block | PASS | PASS | no | All 6 validation fields present |
| test_single_nonexistent_file_exits_nonzero | PASS | PASS | no | "Not found" error, exit != 0 |
| test_all_skips_validated_files | PASS | PASS | no | *.validated.json skipped in --all |

## Black-Box Summary
- EXPECTED: 16
- UNEXPECTED: 0
- Blocked: 0
