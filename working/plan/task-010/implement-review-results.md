# Implement Review Results: Task-010

## Spec Review Issues

### SR-001: _COUNTRY_MAP missing "hong kong": "HK" entry specified by task
- Status: Don't Fix
- Description: The task spec (Step 3) explicitly includes `"hong kong": "HK"` in `_COUNTRY_MAP` with the comment "# kept for completeness; geo tool handles HK specially". The actual implementation at `src/hk_ipo/enrichments/country.py` line 26-45 removes this entry. Grep confirms zero occurrences of "hong kong" in the file. The task spec is internally contradictory — it includes this map entry while also specifying `test_extract_countries_no_match` that expects `codes == []` for text containing "Hong Kong" — but the explicit code in Step 3 should be implemented as written. If the map entry is intentionally excluded, the deviation from the spec code must be justified and the contradiction in the task spec itself should be acknowledged. Previously marked "Resolved" but the fix was never applied (the code was not changed); reverted to Pending.
- Decision Reason: Tried 3 approaches: (1) Add "hong kong": "HK" to _COUNTRY_MAP keeping test unchanged — test_extract_countries_no_match FAILS because "Hong Kong" in text matches the map entry, returning ["HK"] instead of []. (2) Add "hong kong": "HK" plus _DOMESTIC_CODES exclusion set that filters HK from results — PASSES but adds unnecessary special-case code not in the task spec, defeating the purpose of having the map entry. (3) Add "hong kong": "HK" and change test to expect "HK" in results — PASSES but removes the valid "no match" test scenario and makes the test name misleading; violates TDD by changing tests to match implementation. Resolution: TI-002 documents that for HKEX IPO use-of-proceeds analysis, Hong Kong is the home market not a foreign country. The test correctly specifies that HK mentions should not produce country codes. The task spec must resolve this internal contradiction before the map entry can be added.

## Code Review Issues

### CR-001: Substring matching without word boundaries produces false positives
- Status: Resolved
- Description: `extract_countries()` at country.py:52-53 uses Python's `in` operator (plain substring matching) to detect country names. This causes false positives: "america" matches inside "South America" (mapped to US), "uk" matches inside words like "Luke" or "dukedom" (mapped to GB), "laos" matches inside "Galapagos" (mapped to LA). The sibling `geo.py` tool uses `re.compile` with `\b` word-boundary anchors for the same kind of text scanning, which avoids this class of bug. The current approach will silently assign incorrect country codes to use items that happen to contain these letter sequences.
- Decision Reason:

### CR-002: Unused import `re`
- Status: Resolved
- Description: country.py:10 imports `import re`, but the `re` module is never referenced anywhere in the file (confirmed by grep: zero matches for `re.`). Dead imports add noise and can confuse readers into thinking regex is being used for country detection when it is not.
- Decision Reason:

### CR-003: `all_files` path returns None and discards per-ticker results, inconsistent with geo.py
- Status: Resolved
- Description: In `run()` at country.py:96-101, when `all_files=True`, each `_do(record)` return value is discarded and the function returns `None`. The sibling `geo.py` collects results into a `dict[str, dict]` keyed by ticker and returns it, making batch runs inspectable by callers. This inconsistency means programmatic callers of `country.run(all_files=True)` cannot observe what was processed (e.g., for logging, metrics, or downstream workflows).
- Decision Reason:

### CR-004: `all_files` glob logic differs from geo.py; empty enriched_dir causes silent no-op
- Status: Resolved
- Description: country.py:97 chooses the glob source as `enriched_dir if enriched_dir.exists() else categorized_dir`. geo.py:95-97 uses `enriched_dir if enriched_dir.exists() and any(enriched_dir.glob("*.json")) else categorized_dir` -- it checks for actual JSON files, not just directory existence. When `enriched_dir` exists but is empty (e.g., after a clean setup), country.py's `all_files` path will glob an empty directory and silently process zero records instead of falling back to `categorized_dir`. This is a silent data loss scenario.
- Decision Reason:

### CR-005: Core enrichment logic is a nested closure, not independently testable
- Status: Resolved
- Description: The `_do` function at country.py:67-91 is defined as a closure inside `run()`, capturing `enriched_dir` and `force` from the outer scope. In contrast, geo.py defines `_enrich_one` as a module-level function that takes all dependencies as explicit parameters. The nested closure pattern makes `_do` impossible to unit-test in isolation -- you cannot call it directly without going through `run()`. This also makes the function harder to refactor and reason about, since its dependencies are implicit.
- Decision Reason:

### CR-006: _enrich_one re-derives ticker from record, ignoring caller-computed ticker
- Status: Resolved
- Description: Black-box test BB-L5-C-016 revealed that when a record lacks `hk_ticker`, `_enrich_one` at country.py:117 uses `record.get("hk_ticker", "unknown")` → `"unknown"`, discarding the ticker correctly computed by the CLI (`record.get("hk_ticker") or sf.stem`) or by `run()` (`record.get("hk_ticker") or jf.stem`). The CLI and `run()` both compute the correct ticker but never pass it to `_enrich_one`, which independently re-derives it. For records without `hk_ticker`, this causes the output to be saved as `enriched/unknown.json` instead of `enriched/<stem>.json`. Fixed by adding an optional `ticker` parameter to `_enrich_one` and propagating it from all three call sites (CLI single-file, `run()` ticker path, `run()` all_files path).
