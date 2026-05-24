# Implement Review Results: Task-016

## Spec Review Issues

## Code Review Issues

### CR-001: Regex truncation bug -- `undertak` and `contingen` can never match real words
- Status: Resolved
- Description: The compiled regex patterns `_COMMITTED_KW` (line 21-28) and `_DISCRETIONARY_KW` (line 29-35) wrap the entire alternation group in `\b(...)\b`. The alternations `undertak` and `contingen` are partial stems -- in natural English they are always followed by more letters (e.g., "undertake", "undertaking", "contingent", "contingency"). Because `\b` requires a word boundary after the partial match, and the following letters ('e', 'i', 't', 'c') are all word characters, `\b` fails at that position. These two patterns will never match any valid English word, rendering them dead code. The fix would be to either use full word forms (`undertake|undertaking|undertaken|undertakes`), use `\w*` suffix (`undertak\w*`), or remove the trailing `\b` for these specific terms.
- Decision Reason:

### CR-002: Inconsistent `all_files` path fallback logic -- skips files on empty enriched_dir
- Status: Resolved
- Description: In `run()` (line 74-77), the `all_files` branch selects the data directory with `enriched_dir if enriched_dir.exists() else categorized_dir`. This is inconsistent with the established pattern used by 6 of the 7 other enrichment modules (capex_opex, country, esg_tag, geo, specificity, timeline), which all additionally check `any(enriched_dir.glob("*.json"))`. The missing condition means: if `enriched_dir` exists (e.g., was created by `mkdir` on line 54) but contains zero JSON files, commitment.py will glob an empty directory and process nothing, instead of falling back to `categorized_dir`. Every other enrichment module would correctly fall back in this scenario.
- Decision Reason:

### CR-003: `run()` ticker path does not load pre-existing enriched records
- Status: Resolved
- Description: In `run()` (line 71-73), when a ticker is specified, the function calls `load_enriched_or_categorized(categorized_dir, ticker)` which only searches `categorized_dir` for the JSON file. It never checks `enriched_dir` first. Four of the seven enrichment modules (capex_opex, country, timeline, esg_tag) correctly check `enriched_dir / f"{ticker}.json"` before falling back to `categorized_dir`. This means: if a prior enrichment tool has already written to `data/enriched/<ticker>.json`, running commitment.py for that ticker will load the bare categorized record, losing all previously written enrichment blocks from other tools (geo, country, specificity, etc.).
- Decision Reason:

### CR-004: CLI single-file path redundantly loads record then calls `run()` which re-loads from disk
- Status: Resolved
- Description: In the CLI `__main__` block (lines 105-112), the single-file path loads `record` from the user-specified file and from the enriched file (CR-003 fix), but then calls `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, ...)` which internally calls `load_enriched_or_categorized()` to re-load the record from disk. This has two consequences: (1) the CLI's file loading (lines 105-111) is redundant dead code — `run()` overwrites the variable anyway; (2) if a user specifies a JSON file located outside `CATEGORIZED_DIR`, `run()` will raise `FileNotFoundError` because it only searches `CATEGORIZED_DIR`/`enriched_dir`. All 7 other enrichment modules (capex_opex, country, esg_tag, geo, specificity, timeline, industry) avoid both issues by exposing a module-level `_enrich_one()` function and calling it directly from the CLI with the already-loaded `record` dict, bypassing `run()` and `load_enriched_or_categorized()` entirely.
- Decision Reason: Extracted `_enrich_one()` from the `_do` inner function following the capex_opex pattern. Updated `run()` ticker and all_files branches to call `_enrich_one()` directly. Updated CLI single-file path to call `_enrich_one(record, ENRICHED, force=args.force, ticker=ticker)` directly instead of `run()`. All 426 tests pass.
