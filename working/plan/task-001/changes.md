# Changes: Task-001

## Files
- [new] src/hk_ipo/taxonomy.py
- [new] tests/test_taxonomy.py
- [mod] pyproject.toml
- [new] data/categorized/.gitkeep
- [new] data/enriched/.gitkeep
- [new] data/logs/.gitkeep
- [new] frontend/public/data/.gitkeep
- [new] frontend/public/data/sankey/.gitkeep
- [new] tests/fixtures/.gitkeep

## Summary
Project setup: created empty data directories with .gitkeep placeholders, implemented the taxonomy module as the single source of truth for Parent/Main vocabulary (4 parent categories, closed main categories, suggested sub categories with MAIN_TO_PARENT reverse map and taxonomy_sha utility), added langdetect>=1.0.9 dependency to pyproject.toml, and verified no regressions (all 140 tests pass).

## Review Fixes

### SR-001: Step 7 pip install not completed
**Fix:** Verified langdetect and pytest are installed. All 140 tests pass.

### CR-001: Unused `import pytest` in test_taxonomy.py
**Fix:** Removed unused `import pytest` from `tests/test_taxonomy.py`. Ruff confirms no lint errors. All tests pass.

### CR-002: No tests verify Working Capital and Others main categories
**Fix:** Added `test_working_capital_has_expected_mains` (verifies 4 mains) and `test_others_has_expected_mains` (verifies 3 mains). All 10 taxonomy tests pass.
