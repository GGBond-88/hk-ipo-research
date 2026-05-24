# Changes: Task-026

## Files
- [mod] tests/e2e/test_pipeline_e2e.py
- [mod] pyproject.toml
- [mod] src/hk_ipo/enrichments/capex_opex.py
- [mod] src/hk_ipo/enrichments/commitment.py
- [mod] src/hk_ipo/enrichments/esg_tag.py
- [mod] src/hk_ipo/enrichments/timeline.py
- [mod] src/hk_ipo/storage/loader.py
- [mod] tests/e2e/test_filterbar_exportbutton_e2e.py
- [mod] tests/test_analysis_export.py
- [mod] tests/test_enrichments_esg_tag.py
- [mod] tests/test_l4_categorize.py
- [mod] tests/e2e/test_l5_capex_opex_blackbox.py
- [mod] tests/e2e/test_l5_country_blackbox.py
- [mod] tests/e2e/test_l5_esg_tag_blackbox.py
- [mod] tests/e2e/test_l5_timeline_blackbox.py
- [mod] tests/test_l1_sectioning.py
- [mod] tests/test_l4_analysis.py
- [mod] tests/test_enrichments_capex_opex.py
- [mod] tests/test_enrichments_country.py
- [mod] tests/test_enrichments_geo.py
- [mod] tests/test_enrichments_industry.py
- [mod] tests/test_enrichments_specificity.py
- [mod] src/hk_ipo/l3_validation.py
- [mod] src/hk_ipo/l4_categorize.py
- [mod] src/hk_ipo/schema.py
- [mod] src/hk_ipo/schema_review.py
- [mod] src/hk_ipo/taxonomy.py

## Summary

E2E black-box verification and bug fixing pass. Key fixes:

1. **test_dry_run_cost_makes_no_api_calls**: Test assertion matched `"estimated tokens"` (space-separated) but the pipeline JSON output uses `"estimated_tokens"` (underscores). Fixed assertion to match actual output format.

2. **Playwright-anyio conflict**: `anyio` 4.13.0 (transitive dependency of `openai`) auto-registers as a pytest plugin and creates an asyncio event loop that conflicts with Playwright's sync API. Fixed by adding `-p no:anyio` to pytest addopts in pyproject.toml.

3. **Ruff lint clean-up**: Fixed all ruff violations (E702 semicolons, I001 unsorted imports, F401 unused imports, E501 line-too-long) across src/ and tests/.

4. **Three E2E test blocks remain unsolvable due to environment constraints** (documented in env-issues.md): frontend build OOM, Playwright browser tests OOM, pipeline tests skipping due to missing API key. All 472 unit tests pass; all ruff checks pass.
