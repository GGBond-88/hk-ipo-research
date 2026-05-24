# Test Results: Task-007

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| TestParentCategorization::test_assign_parent_returns_valid_parent | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestParentCategorization::test_assign_parent_unknown_returns_others | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_parent_level_delta_within_tolerance | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_exact_sum_passes_through | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_delta_exceeds_tolerance_returns_original | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_empty_returns_empty | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_main_level_custom_target | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_main_level_exceeds_tolerance_returns_original | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_tie_breaks_alphabetically | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_negative_delta_within_tolerance | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestRebalanceLogic::test_rebalance_negative_delta_exceeds_tolerance | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestParentSumValidation::test_parent_sum_within_tolerance_passes | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestParentSumValidation::test_parent_sum_exceeds_tolerance_flags | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestParentSumValidation::test_validate_parent_sums_empty_returns_empty | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestMainSumValidation::test_main_sum_under_parent_within_tolerance_passes | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestMainSumValidation::test_main_sum_exceeds_tolerance_flags | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestMainSumValidation::test_validate_main_sums_empty_returns_empty | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestSubLabelProposals::test_new_sub_label_recorded | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestSubLabelProposals::test_existing_sub_label_not_duplicated | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestSubLabelProposals::test_sub_label_in_closed_vocab_not_recorded | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorized::test_output_has_all_required_fields | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorized::test_output_preserves_uses_and_metadata | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorized::test_output_appends_taxonomy_proposals_to_csv | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorized::test_output_appends_empty_proposals_no_file_created | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorized::test_output_appends_to_existing_csv | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorizationPrompt::test_prompt_includes_taxonomy | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestBuildCategorizationPrompt::test_prompt_includes_use_items | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_golden_fixture_loader | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_load_golden_fixture_file_not_found | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_load_golden_fixture_malformed_json | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_load_golden_fixture_missing_uses_key | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_compute_main_category_match_rate | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_match_rate_perfect | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_match_rate_empty | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_match_rate_mismatched_sizes_expected_nonempty_predicted_empty | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestGoldenFixture::test_match_rate_mismatched_sizes_predicted_nonempty_expected_empty | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_all_flag_parsed | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_single_file_parsed | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_limit_flag_parsed | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_model_flag_parsed | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_limit_non_integer_raises_system_exit | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_unknown_flag_raises_system_exit | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |
| TestCLIParseArgs::test_no_arguments_raises_system_exit | FAIL | FAIL | no | ModuleNotFoundError: No module named 'hk_ipo.l4_categorize' |

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 43
- UNEXPECTED (Result≠Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0
