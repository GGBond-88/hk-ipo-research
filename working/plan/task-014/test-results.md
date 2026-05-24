# Test Results: Task-014

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_dimension_and_version | PASS | PASS | no | - |
| test_capex_factory_construction | PASS | PASS | no | - |
| test_opex_working_capital | PASS | PASS | no | - |
| test_financial_debt_repayment | PASS | PASS | no | - |
| test_capex_r_and_d_equipment | PASS | PASS | no | - |
| test_default_capex_when_ambiguous | PASS | PASS | no | - |
| test_capex_opex_preserves_prior_enrichments | PASS | PASS | no | CR-001 regression |
| test_capex_opex_run_integrates | PASS | PASS | no | CR-002: single-ticker run() |
| test_capex_opex_idempotent | PASS | PASS | no | CR-002: idempotency |
| test_capex_opex_all_files | PASS | PASS | no | CR-002: all_files returns dict |
| test_capex_opex_all_files_falls_back_empty_enriched | PASS | PASS | no | CR-002: all_files fallback |
| test_financial_repayment_morphology | PASS | PASS | no | CR-003: repayment variant |
| test_financial_repaying_morphology | PASS | PASS | no | CR-003: repaying variant |
| test_financial_bonds_plural | PASS | PASS | no | CR-003: bonds plural |
| test_financial_refinancing | PASS | PASS | no | CR-003: refinancing variant |
| test_capex_facility_morphology | PASS | PASS | no | CR-003: facility/facilities |
| test_financial_loans_plural | PASS | PASS | no | CR-003: loans plural |
| test_financial_leveraged | PASS | PASS | no | CR-003: leveraged variant |
| test_capex_buildings | PASS | PASS | no | CR-003: buildings variant |
| test_capex_acquiring | PASS | PASS | no | CR-003: acquiring variant |
| test_capex_purchasing | PASS | PASS | no | CR-003: purchasing variant |
| test_capex_renovating | PASS | PASS | no | CR-003: renovating variant |
| test_opex_salaries | PASS | PASS | no | CR-003: salaries variant |
| test_capex_opex_enrich_one_callable | PASS | PASS | no | CR-002: _enrich_one |
| test_opex_operating_expenses_plural | PASS | PASS | no | CR-004: operating expenses |
| test_opex_marketing_campaigns_plural | PASS | PASS | no | CR-004: marketing campaigns |
| test_capex_data_centers_plural | PASS | PASS | no | CR-004: data centers |
| test_capex_buildings_regex_actually_matches | PASS | PASS | no | CR-004: buildings regex |
| test_opex_sales_forces_plural | PASS | PASS | no | CR-004: sales forces |
| test_opex_sales_teams_plural | PASS | PASS | no | CR-004: sales teams |
| test_capex_new_stores_plural | PASS | PASS | no | CR-004: new stores |
| test_capex_new_branches_plural | PASS | PASS | no | CR-004: new branches |
| test_capex_new_offices_plural | PASS | PASS | no | CR-004: new offices |
| test_capex_manufacturing_plants_plural | PASS | PASS | no | CR-004: manufacturing plants |
| test_capex_manufacturing_lines_plural | PASS | PASS | no | CR-004: manufacturing lines |
| test_capex_r_and_d_centers_plural | PASS | PASS | no | CR-004: R&D centers |
| test_capex_r_and_d_labs_plural | PASS | PASS | no | CR-004: R&D labs |
| test_capex_fit_outs_hyphen_plural | PASS | PASS | no | CR-005: fit-outs hyphen |
| test_capex_fit_outs_space_plural | PASS | PASS | no | CR-005: fit outs space |
| test_capex_installations_plural | PASS | PASS | no | CR-006: installations |
| test_capex_regex_actively_matches_buildings | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_facility | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_facilities | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_acquiring | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_purchasing | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_renovating | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_data_centers | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_new_stores | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_new_branches | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_new_offices | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_manufacturing_plants | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_manufacturing_lines | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_r_and_d_centers | PASS | PASS | no | CR-007: regex guard |
| test_capex_regex_actively_matches_r_and_d_labs | PASS | PASS | no | CR-007: regex guard |
| test_capex_warehousing_gerund | PASS | PASS | no | CR-008: warehousing |
| test_opex_advertised_past | PASS | PASS | no | CR-008: advertised |
| test_capex_constructions_plural | PASS | PASS | no | CR-009: constructions |
| test_opex_rentals_plural | PASS | PASS | no | CR-009: rentals |
| test_financial_matured_morphology | PASS | PASS | no | CR-009: matured |
| test_capex_regex_actively_matches_constructions | PASS | PASS | no | CR-009: regex guard |
| test_opex_regex_actively_matches_rentals | PASS | PASS | no | CR-009: regex guard |
| test_financial_regex_actively_matches_matured | PASS | PASS | no | CR-009: regex guard |
| test_priority_opex_over_capex | PASS | PASS | no | CR-011: opex > capex priority |
| test_priority_financial_over_opex | PASS | PASS | no | CR-011: financial > opex priority |
| test_priority_financial_over_all | PASS | PASS | no | CR-011: financial > opex + capex priority |
| test_opex_rents_plural | PASS | PASS | no | CR-012: rent(s|als?|ing|ed)? fix |
| test_opex_regex_actively_matches_rents | PASS | PASS | no | CR-012: CR-007 guard for rent regex |
| test_cli_single_file_passes | PASS | PASS | no | CR-010: CLI single file |
| test_cli_missing_file_errors | PASS | PASS | no | CR-010: CLI error path |
| test_cli_no_args_errors | PASS | PASS | no | CR-010: CLI arg validation |
| test_cli_all_flag_runs | PASS | PASS | no | CR-010: CLI --all flag |
| test_cli_force_flag | PASS | PASS | no | CR-013: --force with version=VERSION isolation |
| test_cli_preserves_prior_enrichments | PASS | PASS | no | SR-002: CLI preserves prior enrichments |
| test_cli_idempotent_without_force | PASS | PASS | no | CR-013: idempotency without --force |
| Full suite (--ignore=tests/e2e) | PASS | PASS | no | 368 passed, 0 failed, 0 skipped |

## Black-box (e2e) Tests

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_single_file_capex_factory_construction | PASS | PASS | no | BB-L5-CO-001 |
| test_single_file_opex_working_capital | PASS | PASS | no | BB-L5-CO-002 |
| test_single_file_financial_debt_repayment | PASS | PASS | no | BB-L5-CO-003 |
| test_single_file_default_capex_ambiguous | PASS | PASS | no | BB-L5-CO-004 |
| test_single_file_multiple_uses_per_record | PASS | PASS | no | BB-L5-CO-005 |
| test_single_file_priority_opex_over_capex | PASS | PASS | no | BB-L5-CO-006 |
| test_single_file_priority_financial_over_opex | PASS | PASS | no | BB-L5-CO-007 |
| test_single_file_priority_financial_over_all | PASS | PASS | no | BB-L5-CO-008 |
| test_single_file_operating_expenses_plural_is_opex | PASS | PASS | no | BB-L5-CO-009 |
| test_single_file_data_centers_plural_is_capex | PASS | PASS | no | BB-L5-CO-010 |
| test_single_file_repayment_is_financial | PASS | PASS | no | BB-L5-CO-011 |
| test_single_file_facilities_is_capex | PASS | PASS | no | BB-L5-CO-012 |
| test_single_file_marketing_campaigns_plural_is_opex | PASS | PASS | no | BB-L5-CO-013 |
| test_single_file_warehousing_gerund_is_capex | PASS | PASS | no | BB-L5-CO-014 |
| test_single_file_advertised_past_is_opex | PASS | PASS | no | BB-L5-CO-015 |
| test_nonexistent_file_exits_nonzero | PASS | PASS | no | BB-L5-CO-016 |
| test_no_args_exits_nonzero | PASS | PASS | no | BB-L5-CO-017 |
| test_all_mode_processes_all_files | PASS | PASS | no | BB-L5-CO-018 |
| test_all_mode_falls_back_when_enriched_empty | PASS | PASS | no | BB-L5-CO-019 |
| test_all_mode_stdout_reports_processed_tickers | PASS | PASS | no | BB-L5-CO-020 |
| test_force_reprocesses_existing_enrichment | PASS | PASS | no | BB-L5-CO-021 |
| test_single_file_idempotent_output | PASS | PASS | no | BB-L5-CO-022 |
| test_all_mode_idempotent_output | PASS | PASS | no | BB-L5-CO-023 |
| test_empty_uses_list_handled_gracefully | PASS | PASS | no | BB-L5-CO-024 |
| test_ticker_derived_from_filename_if_missing_in_record | PASS | PASS | no | BB-L5-CO-025 |
| test_cli_prints_capex_opex_count_to_stdout | PASS | PASS | no | BB-L5-CO-026 |
| test_single_file_use_id_names_match_input | PASS | PASS | no | BB-L5-CO-027 |
| test_cli_preserves_prior_enrichments | PASS | PASS | no | BB-L5-CO-028 |
| test_all_three_categories_one_record | PASS | PASS | no | BB-L5-CO-029 |
| test_single_file_installations_plural_is_capex | PASS | PASS | no | BB-L5-CO-030 |
| test_single_file_constructions_plural_is_capex | PASS | PASS | no | BB-L5-CO-031 |
| test_single_file_matured_past_is_financial | PASS | PASS | no | BB-L5-CO-032 |
| test_single_file_rents_plural_is_opex | PASS | PASS | no | BB-L5-CO-033 |
| test_single_file_fit_outs_plural_is_capex | PASS | PASS | no | BB-L5-CO-034 |
| test_single_file_new_stores_plural_is_capex | PASS | PASS | no | BB-L5-CO-035 |
| test_single_file_sales_teams_plural_is_opex | PASS | PASS | no | BB-L5-CO-036 |
| All e2e tests (163 passed, 1 pre-existing fail, 18 skipped) | PASS | PASS | no | 36/36 capex_opex e2e passed |

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 110 (74 unit + 36 black-box)
- UNEXPECTED (Result≠Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0
