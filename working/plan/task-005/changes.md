# Changes: Task-005

## Files
- [mod] src/hk_ipo/l2_extraction.py
- [mod] src/hk_ipo/l3_validation.py
- [mod] tests/test_l2_hardening.py
- [mod] tests/test_l3_validation.py

## Summary
Updated the L2 extraction prompt and output logic for v2: (a) removed the mandatory L2 category vocabulary check from `_SYSTEM_PROMPT` (classification is now L4's responsibility); (b) `_parse_llm_output` now always emits `category_raw` and sets `category`/`category_proposed` to None, plus emits `parent_category`/`main_category`/`sub_category` as None (to be populated by L4); (c) `_build_result` already includes `schema_version` from Task 003. Added 7 new tests (4 v2 prompt tests + 3 self-correction retry verification tests). Fixed L3 `[category_vocab]` check to skip `category=None` items (v2 L2 defers classification to L4), preventing noisy warnings per use item. Added 2 tests for v2 category=None behavior. All 179 tests pass.
