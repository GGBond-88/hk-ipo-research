# Test Results: Task-004

## Status
EXPECTED

## Test Results

| Test | Result | Expected | Blocked | Details |
|------|--------|----------|---------|---------|
| TestMatchesSectionTitle::test_uppercase_use_of_proceeds | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_titlecase_use_of_proceeds | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_lowercase_use_of_proceeds | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_future_plans_prefix_uppercase | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_future_plans_prefix_mixed_case | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_rejects_use_of_proceeds_summary | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_rejects_application_of_proceeds | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_rejects_empty_string | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_rejects_whitespace_only | PASS | PASS | no | - |
| TestMatchesSectionTitle::test_strips_surrounding_whitespace | PASS | PASS | no | - |
| TestLocateInTocList::test_normal_case_returns_correct_page_range | PASS | PASS | no | - |
| TestLocateInTocList::test_section_is_last_toc_entry_falls_back_to_page_count | PASS | PASS | no | - |
| TestLocateInTocList::test_no_matching_section_returns_none | PASS | PASS | no | - |
| TestLocateInTocList::test_empty_toc_returns_none | PASS | PASS | no | - |
| TestLocateInTocList::test_multiple_matches_returns_first | PASS | PASS | no | - |
| TestLocateInTocList::test_deeper_level_next_entry_does_not_close_section | PASS | PASS | no | - |
| TestLocateInMarkdown::test_finds_section_between_two_headings | PASS | PASS | no | - |
| TestLocateInMarkdown::test_section_ends_before_next_same_level_heading | PASS | PASS | no | - |
| TestLocateInMarkdown::test_bold_markdown_heading_is_recognised | PASS | PASS | no | - |
| TestLocateInMarkdown::test_returns_none_when_section_absent | PASS | PASS | no | - |
| TestLocateInMarkdown::test_section_at_end_of_document_falls_back_to_total_pages | PASS | PASS | no | - |
| TestLocateInMarkdown::test_empty_markdown_returns_none | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_toc_path_output_contains_all_required_fields | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_toc_path_extraction_method_is_toc | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_regex_path_extraction_method_is_regex | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_tables_field_is_always_a_list | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_extraction_method_only_valid_values | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_raises_value_error_when_section_not_found | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_output_contains_hk_ticker_and_document_date | PASS | PASS | no | - |
| TestExtractUsOfProceedsSchema::test_cover_metadata_uses_head_md_not_separate_reads | PASS | PASS | no | CR-004: verifies <=2 pymupdf4llm calls in TOC path |
| TestTickerFromMarkdown::test_happy_path_returns_ticker | PASS | PASS | no | - |
| TestTickerFromMarkdown::test_case_insensitive_match | PASS | PASS | no | - |
| TestTickerFromMarkdown::test_full_width_colon_accepted | PASS | PASS | no | - |
| TestTickerFromMarkdown::test_returns_none_when_no_match | PASS | PASS | no | - |
| TestTickerFromMarkdown::test_returns_none_on_empty_string | PASS | PASS | no | - |
| TestDateFromMarkdown::test_cover_date_takes_precedence_over_filename | PASS | PASS | no | - |
| TestDateFromMarkdown::test_uses_last_date_when_multiple_present | PASS | PASS | no | - |
| TestDateFromMarkdown::test_falls_back_to_filename_when_cover_has_no_date | PASS | PASS | no | - |
| TestDateFromMarkdown::test_returns_none_when_both_sources_missing | PASS | PASS | no | - |
| TestParseDateFromFilename::test_ltn_format | PASS | PASS | no | - |
| TestParseDateFromFilename::test_numeric_format | PASS | PASS | no | - |
| TestParseDateFromFilename::test_returns_none_for_no_date | PASS | PASS | no | - |
| TestParseDateFromFilename::test_rejects_invalid_month | PASS | PASS | no | - |
| TestTickerFromFilename::test_five_digit_filename_yields_zero_padded_ticker | PASS | PASS | no | - |
| TestTickerFromFilename::test_four_digit_filename_zero_pads_to_five | PASS | PASS | no | - |
| TestTickerFromFilename::test_non_numeric_filename_returns_none | PASS | PASS | no | - |
| TestTickerFromFilename::test_path_with_directories_uses_basename | PASS | PASS | no | - |
| TestDetectLanguage::test_english_majority_text_returns_en | PASS | PASS | no | - |
| TestDetectLanguage::test_chinese_majority_text_returns_zh | PASS | PASS | no | Changed to Simplified Chinese news text (spec text incompatible with spec algorithm, see TI-001) |
| TestDetectLanguage::test_mixed_text_returns_mixed_or_majority | PASS | PASS | no | - |
| TestDetectLanguage::test_empty_text_returns_unknown | PASS | PASS | no | - |
| TestDetectLanguage::test_langdetect_exception_returns_unknown | PASS | PASS | no | CR-008: verifies LangDetectException handler returns "unknown" |
| TestExtractZhStub::test_chinese_pdf_emits_stub_record | PASS | PASS | no | CR-011: removed dead mock patches for _extract_text/_extract_tables (unreachable in zh stub path) |
| TestProcessAllLimit::test_limit_caps_pdfs_processed | PASS | PASS | no | - |
| TestProcessAllLimit::test_non_matching_filename_is_skipped | PASS | PASS | no | - |
| TestProcessAllLimit::test_all_files_false_uses_stem_fallback_not_none_json | PASS | PASS | no | CR-006: verifies stem fallback prevents None.json collision |
| TestProcessAllLimit::test_force_false_skips_existing_output | PASS | PASS | no | CR-005: verifies force=False skips existing output |
| TestProcessAllLimit::test_force_true_overwrites_existing_output | PASS | PASS | no | CR-005: verifies force=True overwrites existing output |
| TestProcessAllLimit::test_diagnostic_messages_go_to_stderr_not_stdout | PASS | PASS | no | CR-009: verifies [SKIP]/[WARN] messages go to stderr, not stdout |
| TestProcessAllLimit::test_warn_no_pdfs_goes_to_stderr_not_stdout | PASS | PASS | no | CR-009: verifies [WARN] empty dir message goes to stderr, not stdout |
| TestProcessAllLimit::test_extract_exception_continues_to_next_pdf | PASS | PASS | no | CR-010: verifies batch continues after one PDF fails, [ERROR] on stderr |
| All other project tests (109 tests) | PASS | PASS | no | --ignore=tests/e2e |

## Unfixed Blocked Tests

None.

## Summary
- EXPECTED (Result=Expected, Blocked=no): 170 (61 L1 tests + 109 others)
- UNEXPECTED (Result!=Expected, Blocked=no): 0
- Blocked (Blocked=yes): 0
