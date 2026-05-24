# Test Results: Task-015

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| test_dimension_and_version | PASS | PASS | no | - |
| test_green_renewable_energy | PASS | PASS | no | - |
| test_social_healthcare | PASS | PASS | no | - |
| test_governance_compliance | PASS | PASS | no | - |
| test_multiple_tags | PASS | PASS | no | - |
| test_no_esg_tag | PASS | PASS | no | - |
| test_all_three_tags_simultaneously | PASS | PASS | no | CR-007(a): all three tags on one use |
| test_empty_item_dict | PASS | PASS | no | CR-007(b): empty dict returns [] |
| test_none_field_values | PASS | PASS | no | CR-007(c): None values handled gracefully; CR-012: str(item.get(key) or "") |
| test_case_insensitivity | PASS | PASS | no | CR-007(d): uppercase keywords match |
| test_green_stem_energy_efficiency | PASS | PASS | no | CR-009: energy[\s-]+efficien(?:t|cy|cies|tly) |
| test_green_stem_energy_efficient | PASS | PASS | no | CR-009: energy[\s-]+efficien(?:t|cy|cies|tly) |
| test_green_stem_decarbonization | PASS | PASS | no | CR-009: decarboni alternation |
| test_green_stem_decarbonising | PASS | PASS | no | CR-009: decarboni alternation |
| test_green_stem_decarbonizes | PASS | PASS | no | CR-011: "decarbonizes" (3rd person singular US) |
| test_green_stem_decarbonises | PASS | PASS | no | CR-011: "decarbonises" (3rd person singular UK) |
| test_social_stem_charity | PASS | PASS | no | CR-009: charit(?:y|ies|able) |
| test_social_stem_charitable | PASS | PASS | no | CR-009: charit(?:y|ies|able) |
| test_social_stem_philanthropy | PASS | PASS | no | CR-009: philanthrop alternation |
| test_social_stem_philanthropic | PASS | PASS | no | CR-009: philanthrop alternation |
| test_missing_use_id_no_key_error (esg_tag) | PASS | PASS | no | CR-010: u.get("use_id", "") guard; CR-013: temp dir cleanup via finally block |
| test_green_emissions_plural | PASS | PASS | no | CR-014: emission -> emissions? |
| test_green_recycle_verb | PASS | PASS | no | CR-014: recycling -> recycl(?:e|ed|es|ing) |
| test_green_recycled_adjective | PASS | PASS | no | CR-014: recycling -> recycl(?:e|ed|es|ing) |
| test_green_recycles_verb | PASS | PASS | no | CR-014: recycling -> recycl(?:e|ed|es|ing) |
| test_social_patients_plural | PASS | PASS | no | CR-014: patient -> patients? |
| test_social_hospitals_plural | PASS | PASS | no | CR-014: hospital -> hospitals? |
| test_social_schools_plural | PASS | PASS | no | CR-014: school -> schools? |
| test_social_clinics_plural | PASS | PASS | no | CR-014: clinic -> clinics? |
| test_social_universities_plural | PASS | PASS | no | CR-014: university -> universit(?:y|ies) |
| test_green_electric_vehicles_plural | PASS | PASS | no | SR-001: electric[\s-]+vehicle -> electric[\s-]+vehicles? |
| test_green_environments_plural | PASS | PASS | no | SR-001: environment -> environments? |
| test_social_communities_plural | PASS | PASS | no | SR-001: community -> communit(?:y|ies) |
| test_governance_audits_plural | PASS | PASS | no | SR-001: audit -> audits? |
| test_governance_internal_controls_plural | PASS | PASS | no | SR-001: internal[\s-]+control -> internal[\s-]+controls? |
| test_governance_shareholder_rights_plural | PASS | PASS | no | SR-001: shareholder[\s-]+right -> shareholder[\s-]+rights? |
| test_governance_whistleblowers_plural | PASS | PASS | no | SR-001: whistleblower -> whistleblowers? |
| test_single_file_green_renewable_energy (e2e) | PASS | PASS | no | BB-L5-ESG-001: e2e single-file green |
| test_single_file_social_healthcare (e2e) | PASS | PASS | no | BB-L5-ESG-002: e2e single-file social |
| test_single_file_governance_compliance (e2e) | PASS | PASS | no | BB-L5-ESG-003: e2e single-file governance |
| test_single_file_multiple_tags (e2e) | PASS | PASS | no | BB-L5-ESG-004: e2e multiple tags |
| test_single_file_no_esg_tag (e2e) | PASS | PASS | no | BB-L5-ESG-005: e2e no tag |
| test_single_file_multiple_uses_per_record (e2e) | PASS | PASS | no | BB-L5-ESG-006: e2e multiple uses |
| test_nonexistent_file_exits_nonzero (e2e) | PASS | PASS | no | BB-L5-ESG-007: e2e error path |
| test_no_args_exits_nonzero (e2e) | PASS | PASS | no | BB-L5-ESG-008: e2e no args |
| test_all_mode_processes_all_files (e2e) | PASS | PASS | no | BB-L5-ESG-009: e2e --all mode |
| test_all_mode_falls_back_when_enriched_empty (e2e) | PASS | PASS | no | BB-L5-ESG-010: e2e --all fallback |
| test_all_mode_stdout_reports_processed_tickers (e2e) | PASS | PASS | no | BB-L5-ESG-011: e2e --all stdout |
| test_force_reprocesses_existing_enrichment (e2e) | PASS | PASS | no | BB-L5-ESG-012: e2e --force |
| test_single_file_idempotent_output (e2e) | PASS | PASS | no | BB-L5-ESG-013: e2e idempotency |
| test_all_mode_idempotent_output (e2e) | PASS | PASS | no | BB-L5-ESG-014: e2e --all idempotency |
| test_empty_uses_list_handled_gracefully (e2e) | PASS | PASS | no | BB-L5-ESG-015: e2e empty uses |
| test_ticker_derived_from_filename_if_missing_in_record (e2e) | PASS | PASS | no | BB-L5-ESG-016: e2e ticker from filename |
| test_cli_prints_esg_tag_count_to_stdout (e2e) | PASS | PASS | no | BB-L5-ESG-017: e2e stdout count |
| test_cli_preserves_prior_enrichments (e2e) | PASS | PASS | no | BB-L5-ESG-018: e2e prior enrichment preserved |
| test_missing_use_id_no_key_error (capex_opex) | PASS | PASS | no | CR-015: u.get("use_id", "") guard in capex_opex.py |
| test_missing_use_id_no_key_error (country) | PASS | PASS | no | CR-015: u.get("use_id", "") guard in country.py |
| test_missing_use_id_no_key_error (geo) | PASS | PASS | no | CR-015: u.get("use_id", "") guard in geo.py |
| test_missing_use_id_no_key_error (specificity) | PASS | PASS | no | CR-015: u.get("use_id", "") guard in specificity.py |
| test_missing_use_id_no_key_error (timeline) | PASS | PASS | no | CR-015: u.get("use_id", "") guard in timeline.py |
| CR-016: test_none_field_values_not_injected (capex_opex) | PASS | PASS | no | str(item.get(key) or "") in capex_opex.py classify_capex_opex |
| CR-016: test_none_field_values_with_real_keyword (capex_opex) | PASS | PASS | no | None values do not prevent keyword matching |
| CR-016: test_none_field_values_not_injected (country) | PASS | PASS | no | str(u.get(key) or "") in country.py _enrich_one |
| CR-016: test_none_field_values_with_real_keyword (country) | PASS | PASS | no | None values do not prevent country keyword matching |
| CR-016: test_none_field_values_not_injected (geo) | PASS | PASS | no | str(item.get(key) or "") in geo.py classify_geo |
| CR-016: test_none_field_values_with_real_keyword (geo) | PASS | PASS | no | None values do not prevent geo keyword matching |
| CR-016: test_none_field_values_not_injected (specificity) | PASS | PASS | no | str(item.get(key) or "") in specificity.py classify_specificity |
| CR-016: test_none_field_values_not_injected (timeline) | PASS | PASS | no | str(item.get(key) or "") in timeline.py classify_timeline |
| Full suite (--ignore=tests/e2e) | PASS | PASS | no | 418 passed in 9.73s |

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 69
- UNEXPECTED (Result≠Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0
