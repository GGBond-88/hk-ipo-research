# Changes: Task-015

## Files
- [mod] src/hk_ipo/enrichments/esg_tag.py
- [mod] tests/test_enrichments_esg_tag.py
- [new] tests/e2e/test_l5_esg_tag_blackbox.py
- [mod] working/plan/task-015/implement-review-results.md
- [mod] src/hk_ipo/enrichments/capex_opex.py
- [mod] tests/test_enrichments_capex_opex.py
- [mod] src/hk_ipo/enrichments/country.py
- [mod] tests/test_enrichments_country.py
- [mod] src/hk_ipo/enrichments/geo.py
- [mod] tests/test_enrichments_geo.py
- [mod] src/hk_ipo/enrichments/specificity.py
- [mod] tests/test_enrichments_specificity.py
- [mod] src/hk_ipo/enrichments/timeline.py
- [mod] tests/test_enrichments_timeline.py

## Summary
Fixed 10 code review issues (CR-001 through CR-010) in the L5 esg_tag enrichment tool:

**Regex fixes (CR-001 to CR-005):** Unified multi-word keyword separator convention to `[\s-]+` (default, requiring at least one space/hyphen) and `[\s-]?` (for terms whose merged form is standard English: microfinance, anticorruption, antibribery, wastewater). Changed `ev\s` to `evs?` to match "EV.", "EVs", and "EV". Fixed `access\s*to\s` to `access[\s-]+to`.

**Test fixes (CR-006, CR-007):** Added missing governance assertion to `test_multiple_tags`. Added 4 edge-case unit tests: all three tags simultaneously, empty item dict, None field values, and case-insensitivity verification.

**E2E tests (CR-008):** Created `tests/e2e/test_l5_esg_tag_blackbox.py` with 18 black-box tests covering: single-file tagging per ESG dimension, multiple tags per use, no-tag items, multiple uses per record, error paths (nonexistent file, no args), --all mode, --force flag, idempotency, empty uses list, ticker derivation from filename, stdout reporting, and prior enrichment preservation.

**Regex stem fixes (CR-009):** Expanded four word-stem patterns that were silently broken by `\b` boundary: `energy[\s-]+efficien` -> `energy[\s-]+efficien(?:t|cy|cies|tly)`, `decarboni` -> `decarboni(?:zation|sation|zing|sing|zed|sed|ze|se)`, `charit` -> `charit(?:y|ies|able)`, `philanthrop` -> `philanthrop(?:y|ic|ist|ists|ies)`. Added 8 unit tests covering each expanded stem variant.

**use_id guard fix (CR-010):** Changed `u["use_id"]` to `u.get("use_id", "")` in `_enrich_one` to prevent KeyError on malformed use items. Added unit test `test_missing_use_id_no_key_error`.

**Implementation fixes:** Refactored `run()` and CLI in esg_tag.py to match the proven capex_opex.py pattern. Fixed `--all` mode to check `any(enriched_dir.glob("*.json"))` instead of just `enriched_dir.exists()`. Fixed single-file CLI path to load pre-existing enriched records to preserve prior enrichment blocks.

**CR-011 fix:** Added `zes` and `ses` to the `decarboni` alternation group in `_GREEN_KW` to match third-person singular verb forms "decarbonizes" and "decarbonises". Added 2 unit tests.

**CR-012 fix:** Changed `str(item.get(key, ""))` to `str(item.get(key) or "")` in `classify_esg` to prevent `None` values from producing literal "None" string in search text.

**CR-013 fix:** Added `import shutil` and a `finally` block with `shutil.rmtree(enriched_dir, ignore_errors=True)` in `test_missing_use_id_no_key_error` to clean up temp directory.

**CR-014 fix:** Expanded 7 keywords in `_GREEN_KW` and `_SOCIAL_KW` to non-capturing alternation groups to match common plural/inflected forms that were blocked by `\b` word boundary: `emission` -> `emissions?`, `recycling` -> `recycl(?:e|ed|es|ing)`, `patient` -> `patients?`, `hospital` -> `hospitals?`, `school` -> `schools?`, `clinic` -> `clinics?`, `university` -> `universit(?:y|ies)`. Added 9 clean unit tests (one per inflected/plural form) with keyword-only descriptions to avoid false positives from other ESG keywords.

**SR-001 fix:** Expanded 7 additional keywords that were still blocked by `\b` boundary for common plural/inflected forms: `electric[\s-]+vehicle` -> `electric[\s-]+vehicles?`, `environment` -> `environments?`, `community` -> `communit(?:y|ies)`, `audit` -> `audits?`, `internal[\s-]+control` -> `internal[\s-]+controls?`, `shareholder[\s-]+right` -> `shareholder[\s-]+rights?`, `whistleblower` -> `whistleblowers?`. Added 7 corresponding unit tests. Marked SR-001 as Resolved.

**CR-015 fix:** Propagated the CR-010 KeyError guard (`u["use_id"]` -> `u.get("use_id", "")`) to 5 sibling enrichment tools: capex_opex.py, country.py, geo.py, specificity.py, and timeline.py. Added `test_missing_use_id_no_key_error` test to each corresponding test file. All 5 new tests pass. Marked CR-015 as Resolved.

**CR-016 fix:** Propagated the CR-012 None-value guard (`str(item.get(key, ""))` -> `str(item.get(key) or "")`) to 5 sibling enrichment tools across all their `classify_*` functions: capex_opex.py (lines 59-61), country.py (lines 111-113), geo.py (lines 55-57), specificity.py (lines 42-43), and timeline.py (lines 66-67). Added 8 regression tests (`test_none_field_values_not_injected` and `test_none_field_values_with_real_keyword`) across the 5 sibling test files. All 8 tests pass. Marked CR-016 as Resolved.
