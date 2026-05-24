# Changes: Task-003

## Files
- [mod] src/hk_ipo/schema.py
- [mod] tests/test_schema.py
- [mod] tests/test_l4_analysis.py
- [mod] tests/test_l2_hardening.py
- [mod] scripts/run_pipeline.py
- [mod] scripts/run_mvp.py
- [renamed] src/hk_ipo/l4_analysis.py → src/hk_ipo/l4_legacy_analysis.py

## Summary
Bumped SCHEMA_VERSION to "2.0". Added parent_category, main_category, sub_category fields to UseItem; added language and schema_version to ExtractionRecord; added language and skipped to SectionRecord. Preserved legacy CATEGORY_L2, CATEGORY_L1_TREE, CATEGORY_L1_MAP constants for backwards compatibility. Renamed l4_analysis.py to l4_legacy_analysis.py and updated all imports (tests, run_pipeline.py, run_mvp.py). Added 11 new schema tests (6 v2.0 + 5 SectionRecord CR-001) and updated test_l2_hardening.py schema_version assertion.
