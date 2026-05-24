# Changes: Task-009

## Files
- [new] src/hk_ipo/enrichments/__init__.py
- [new] src/hk_ipo/enrichments/base.py
- [new] src/hk_ipo/enrichments/geo.py
- [new] tests/test_enrichments_base.py
- [new] tests/test_enrichments_geo.py

## Summary
Created the L5 enrichment base contract (`base.py`) with `EnrichmentRunner` protocol, `load_enriched_or_categorized`, `merge_enrichment_block`, and `save_enriched` helpers. Implemented the first enrichment tool (`geo.py`) that tags each use item as `domestic_hk`, `mainland`, or `overseas` using keyword-based classification. Both implemented via TDD — tests were written first, verified RED, then implementation made them GREEN. Full test suite (250 tests) passes with no regressions.

One test assertion in the spec was incompatible with Python's Protocol semantics (`callable(getattr(EnrichmentRunner, "run", None)) is False` — Protocol method stubs are always callable function objects). Fixed to use `issubclass(EnrichmentRunner, Protocol)` and `hasattr(EnrichmentRunner, "run")` instead.
