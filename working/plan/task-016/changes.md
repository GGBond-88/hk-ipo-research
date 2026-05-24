# Changes: Task-016

## Files
- [new] src/hk_ipo/enrichments/commitment.py
- [new] tests/test_enrichments_commitment.py
- [mod] src/hk_ipo/enrichments/commitment.py
- [mod] tests/test_enrichments_commitment.py

## Summary
Implemented L5 commitment enrichment tool that classifies each use item as `committed` or `discretionary` based on regex-based language strength analysis. Followed TDD: tests written first (6 cases), verified RED, implemented module, verified GREEN (all 424 tests pass).

### Post-review fixes (CR-001, CR-002, CR-003, CR-004)
- **CR-001**: Fixed regex truncation bug — `undertak` and `contingen` partial stems changed to `undertak\w*` and `contingen\w*` so they match full word forms (e.g. "undertaking", "contingent"). Added 2 TDD-verified tests.
- **CR-002**: Added `any(enriched_dir.glob("*.json"))` check in `all_files` branch to match the established pattern used by capex_opex, country, esg_tag, geo, specificity, and timeline.
- **CR-003**: Fixed `run()` ticker path to check `enriched_dir / f"{ticker}.json"` first before falling back to `categorized_dir`, preserving prior enrichment blocks. Also fixed CLI single-file path.
- **CR-004**: Extracted `_enrich_one()` module-level function from inner `_do()`, following the capex_opex/geo/country/etc. pattern. CLI single-file path now calls `_enrich_one(record, ENRICHED, ...)` directly instead of `run()`, eliminating redundant disk re-load. Also fixes the bug where specifying a file outside `CATEGORIZED_DIR` caused `FileNotFoundError`.
