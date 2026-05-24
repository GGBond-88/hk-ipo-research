# Changes: Task-008

## Files
- [mod] src/hk_ipo/config.py
- [new] src/hk_ipo/l4_categorize.py
- [new] data/taxonomy_proposals.csv
- [new] tests/fixtures/l4_golden/3750.json
- [mod] tests/test_l4_categorize.py

## Summary
Implemented L4 hierarchical categorisation module (`l4_categorize.py`) with pure-logic helpers (assign_parent, rebalance_layer, validate_parent_sums, validate_main_sums, record_sub_proposal, append_sub_proposals_csv), LLM pipeline (build_categorization_prompt, call_l4_llm, categorize_one), CLI (parse_args, process_single, process_all), and golden-fixture infrastructure (load_golden_fixture, compute_main_category_match_rate). Added CATEGORIZED_DIR to config, created empty taxonomy_proposals.csv, hand-labelled golden fixture for ticker 3750, and added A4.5 acceptance test (mocked LLM).

Post-review fixes (15 issues resolved):
- CR-001: assign_parent now validates candidate against parent_categories parameter
- CR-002: validate_parent_sums now validates against adjusted_breakdown (post-rebalance)
- CR-003: build_categorized_output uses unconditional extraction_metadata per spec
- CR-004: sub_proposals included in build_categorized_output output
- CR-005: process_single reuses result.get("sub_proposals") instead of re-deriving
- CR-006: removed dead try/except in load_golden_fixture
- CR-007: defensive c.get("use_id") with continue-on-missing in categorize_one
- CR-008: _tiebreak_key handles non-ASCII characters safely
- CR-009: removed dead sub_sums parameter from build_categorized_output
- CR-010: process_single catches JSONDecodeError on corrupted cached output
- CR-011: build_categorization_prompt uses defensive u.get("use_id", "")
- CR-012: categorize_one produces structurally complete output for empty uses
- CR-013: fixed docstring in compute_main_category_match_rate
- CR-014: changed encoding="utf-8" to "utf-8-sig" in append_sub_proposals_csv read path; added BOM-specific test
- SR-005: extraction_metadata unconditionally set per spec
- SR-006: self-import already absent in actual implementation

Don't Fix (4 issues - tests define the contract):
- SR-001: path-based load_golden_fixture (tests require it)
- SR-002: dict-based validate_parent_sums (tests require structured format)
- SR-003: dict-based validate_main_sums (same as SR-002)
- SR-004: compute_main_category_match_rate edge case (test-defined behavior)

All 236 tests pass with zero regressions.
