# Changes: Task-014

## Files
- [new] src/hk_ipo/enrichments/capex_opex.py
- [mod] tests/test_enrichments_capex_opex.py

## Summary
Implemented L5 enrichment capex_opex tool: rules-based keyword classifier that tags each use-of-proceeds item as `capex`, `opex`, or `financial`. Followed TDD: 6 unit tests written first and verified failing (ModuleNotFoundError), then implementation written and verified passing.

CR-001 fix: Single-ticker path now checks enriched_dir first (matching country.py pattern), preventing silent loss of prior enrichment data when capex_opex runs after other enrichment tools.

CR-002 fix: Extracted nested `_do` to module-level `_enrich_one` for testability and consistency. Added 6 integration tests covering: run() single-ticker path, run() all_files path with results dict, all_files fallback to categorized_dir, idempotency, _enrich_one direct callability, and prior enrichment preservation regression test.

CR-003 fix: Replaced bare-stem regex patterns in all three keyword groups (_FINANCIAL_KW, _OPEX_KW, _CAPEX_KW) with comprehensive morphological alternations covering plurals (-s/-es), gerunds (-ing), past participles (-ed), derived nouns (-ment/-tion/-sion), and y/ies alternations. Added 11 targeted tests for specific morphological variant gaps (repayment, repaying, bonds, refinancing, facilities, loans, leveraged, buildings, acquiring, purchasing, renovating, salaries).

CR-004 fix: Fixed multi-word regex patterns in _OPEX_KW and _CAPEX_KW where the final word's plural form was not matched due to `\b` word boundary constraints. Changes: `operating\s*expense` -> `operating\s*expenses?`, `marketing\s*campaign` -> `marketing\s*campaigns?`, `sales\s*force` -> `sales\s*forces?`, `sales\s*team` -> `sales\s*teams?` (OPEX); `build(ing|s)?` -> `build(ings?|s)?`, `data\s*center` -> `data\s*centers?`, `new\s*(store|branch|office)` -> `new\s*(stores?|branch(es)?|offices?)`, `manufacturing\s*(plant|line|facility)` -> `manufacturing\s*(plants?|lines?|facilit(y|ies))`, `r\s*&\s*d\s*(center|facility|lab)` -> `r\s*&\s*d\s*(centers?|facilit(y|ies)|labs?)` (CAPEX). Added 13 targeted tests for multi-word final-plural gaps.

CR-005 fix: Fixed `fit[\s-]out` to `fit[\s-]outs?` in _CAPEX_KW to match plural forms "fit-outs" and "fit outs". Added 2 classification tests with CR-007 regex guards.

CR-006 fix: Fixed `install(ing|ed|s|ation)?` to `install(?:ing|ed|s|ations?)?` in _CAPEX_KW (changed capturing group to non-capturing, added `s?` to the `ation` alternation) to match "installations" (plural of "installation"). Added 1 classification test with CR-007 regex guard.

CR-007 fix: Added 14 dedicated regex-level assertion tests (`test_capex_regex_actively_matches_*`) that directly verify `_CAPEX_KW.search(text) is not None` for each CAPEX morphological variant and multi-word phrase, preventing tests from falsely passing via the `classify_capex_opex` default "capex" fallback when the regex fails to match the intended word. Also added CR-007 regex guards inside the 3 new CR-005/CR-006 tests.

CR-008 fix: Fixed two remaining morphological regex gaps: (1) `warehouse(s|ing)?` changed to `warehous(e(?:s)?|ing|ed)?` in _CAPEX_KW to match "warehousing" (gerund form drops 'e') and "warehoused" (past participle); (2) `advertis(e|ing|ements?)?` changed to `advertis(e|ed|ing|ements?)?` in _OPEX_KW to match "advertised" (missing 'ed' alternation). Added regression tests `test_capex_warehousing_gerund` and `test_opex_advertised_past` with CR-007-style regex-assertion guards.

CR-009 fix: Fixed three morphological suffix gaps: (1) `construct(ion|ing|ed|s)?` changed to `construct(ions?|ing|ed|s)?` in _CAPEX_KW to match "constructions" (plural of construction needs two suffix levels: ion + s); (2) `rent(al|ing|s|ed)?` changed to `rent(als?|ing|ed)?` in _OPEX_KW to match "rentals" (plural of rental needs two suffix levels: al + s); (3) `matur(e|ing|ity)` changed to `matur(e|ing|ed|ity)` in _FINANCIAL_KW to match "matured" (missing 'ed' alternation for past tense). Added 6 targeted tests: 3 classification tests with regex-assertion guards and 3 dedicated regex-active guard tests. Test texts carefully isolated to ensure the target word is the only keyword match, preventing CR-007 default-fallback false passes.

CR-010 fix: Added 5 CLI `__main__` entrypoint tests using monkeypatch + runpy.run_module to exercise all argparse code paths: single-file enrichment (test_cli_single_file_passes), missing file error with SystemExit(1) (test_cli_missing_file_errors), mutually-exclusive group enforcement (test_cli_no_args_errors), --all flag processing all tickers (test_cli_all_flag_runs), and --force flag overwriting existing enrichment blocks (test_cli_force_flag).

CR-011 fix: Added 3 classification priority order tests covering all pairwise combinations (opex > capex, financial > opex, financial > opex + capex). Each test includes CR-007 regex-assertion guards verifying that keywords from both competing categories actively match, then asserts the higher-priority category wins. Confirms the existing if-elif chain (financial -> opex -> capex) is correct and prevents regression if the chain is reordered.

CR-012 fix: Fixed OPEX regex `rent(als?|ing|ed)?` to `rent(s|als?|ing|ed)?` on line 30 of capex_opex.py to match the simple plural "rents" (previously unmatcheable due to `\b` word boundary gap). Added 2 tests: classification test with CR-007 regex guard and dedicated regex-active guard test.

SR-002 fix (second pass): CLI `__main__` single-file path was loading from the user-specified categorized file and calling `_enrich_one()` directly, bypassing `run()` entirely. If enriched data already existed for the ticker, prior enrichment blocks (geo, country, etc.) were silently dropped. Fixed by adding an enriched_dir existence check in the CLI single-file path (lines 140-143): after determining the ticker, if an enriched file already exists, load from there instead of from the raw categorized input. Added `test_cli_preserves_prior_enrichments` test verifying that CLI single-file path preserves prior enrichments when enriched data already exists.

CR-013 fix (second pass): `test_cli_force_flag` was using `version: 99` (non-current), which triggered re-processing regardless of `--force`. Changed to use `version: VERSION (1)` with an intentionally wrong tag ("opex" for a capex item) so that `--force` is truly required. Added companion test `test_cli_idempotent_without_force` verifying that without `--force`, the idempotency check preserves the existing enrichment block unchanged. Both tests isolate `--force` semantics from version mismatch.
