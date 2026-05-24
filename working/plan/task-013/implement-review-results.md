# Implement Review Results: Task-013

## Spec Review Issues

### SR-001: Classification algorithm deviates from task spec (two-phase vs single-phase)
- Status: Resolved
- Description: The task spec (Step 3) specifies a single-phase priority chain where `_SHORT_TERM_RE` is checked first, then `_MEDIUM_TERM_RE`, `_LONG_TERM_RE`, and `_VERY_LONG_RE` in order, with each pattern containing both numeric and qualitative phrases combined. The actual implementation uses a two-phase approach: Phase 1 checks only numeric regex patterns (longest horizon first), Phase 2 checks qualitative patterns only if no numeric match was found. This algorithmic change was necessary to fix a spec bug -- the spec's single-phase approach would classify "long-term investment to be deployed over 5 years" as "24-36m" because `_LONG_TERM_RE` (containing `long[\s-]term`) is checked before `_VERY_LONG_RE` (containing `5\s*year`), which would fail `test_very_long_36m_plus`. However, the algorithm change was not reflected in the task spec and represents an undocumented deviation.
- Decision Reason: Accepted the two-phase algorithm as the correct implementation. The spec's single-phase ordering is buggy (qualitative "long-term" would shadow numeric "5 years"). This deviation is documented as TI-003 in task-issues.md with the explicit assumption: "Numeric/explicit time spans should take priority over qualitative phrases."

### SR-002: Imprecise regex quantifier usage on word-level patterns
- Status: Resolved
- Description: In the numeric regex patterns, single-character `?` quantifiers are applied to individual letters in word stems: `two?` (makes 'o' optional, producing "tw"|"two"), `three?` (makes 'e' optional, producing "thre"|"three"), `four?` (makes 'r' optional, producing "fou"|"four"), `five?` (makes 'e' optional, producing "fiv"|"five"). The `?` quantifier in regex applies only to the immediately preceding character, not to the word stem as a whole. While word boundaries guard against most false positives in practice, these patterns are semantically incorrect -- they allow partial-word matches ("tw", "thre", "fou", "fiv") that are not valid English words and were not part of the task spec's patterns. The intended behavior (matching the spelled-out number words) works by coincidence because the optional character happens to be at the end.
- Decision Reason: Fixed by removing `?` from `two?`, `three?`, `four?`, `five?` in the numeric regex patterns (`_MEDIUM_NUMERIC_RE`, `_LONG_NUMERIC_RE`, `_VERY_LONG_NUMERIC_RE`). Changed to literal `two`, `three`, `four`, `five` which matches the task spec's original intent. Added `test_spelled_out_word_numbers` unit test to verify all four spelled-out number patterns.

## Code Review Issues

### CR-001: `--all` mode always globs from enriched_dir after mkdir, never falls back to categorized_dir
- Status: Resolved
- Description: `run()` calls `enriched_dir.mkdir(parents=True, exist_ok=True)` on line 93 (before the `--all` glob on line 113), so `enriched_dir` always exists. The glob expression `enriched_dir if enriched_dir.exists() else categorized_dir` always selects enriched_dir. If enriched_dir is newly created and empty (no `*.json` files), `--all` silently processes nothing. The reference implementation in `country.py` correctly guards with `enriched_dir.exists() and any(enriched_dir.glob("*.json"))`. Fixed by adopting the `country.py` pattern: check both existence AND non-emptiness before using enriched_dir. Also extracted `_enrich_one()` helper (matching `country.py`'s `_enrich_one`) and passed ticker through explicitly.
- Decision Reason:

### CR-002: `_MEDIUM_NUMERIC_RE` uses `1[89]` instead of `1[3-9]`, missing months 13-17
- Status: Resolved
- Description: The medium-term numeric regex uses `1[89]\s*months?\b` which only matches "18" or "19" months. Months 13-17 fall through all numeric checks to "unspecified", which is semantically wrong (13 months exceeds the 12-month short-term boundary). The task spec and the `country.py` pattern suggest `1[3-9]` was intended (covering 13-19 months). Fixed by changing `1[89]` to `1[3-9]` and removing the redundant `2[4]` alternate (already covered by `2[0-4]`).
- Decision Reason:

### CR-003: `_do()` derives ticker from record instead of using ticker passed to `run()`
- Status: Resolved
- Description: The inner `_do()` function used `tick = record.get("hk_ticker", "unknown")` to determine the output filename. When the CLI path computed `ticker = record.get("hk_ticker") or sf.stem` and passed it into `run()`, that ticker was never forwarded to `_do()`. If the record had no `hk_ticker` field, `_do()` saved to `unknown.json` instead of using the filename stem (e.g., `00300.json`). Fixed by refactoring `_do()` into `_enrich_one()` with an explicit `ticker` parameter, matching the `country.py` pattern of `tick = ticker or record.get("hk_ticker", "unknown")`.
- Decision Reason:

### CR-004: Ticker mode always loads from categorized_dir, missing enriched_dir fast path
- Status: Resolved
- Description: In single-ticker mode, `run()` called `load_enriched_or_categorized(categorized_dir, ticker)` unconditionally, always loading from categorized_dir. The reference `country.py` implementation checks if the enriched file already exists first: `load_enriched_or_categorized(enriched_dir if (enriched_dir / f"{ticker}.json").exists() else categorized_dir, ticker)`. This prevents incremental enrichment processing (where a previously enriched record should be the starting point). Fixed by adopting the `country.py` pattern.
- Decision Reason:

### CR-005: Numeric regex patterns use `\s*` (whitespace only) between number and unit, missing hyphenated forms
- Status: Resolved
- Description: All numeric patterns (e.g., `12\s*months?`, `5\s*years?`, `\d{2}\s*years?`) use `\s*` to join number and unit, matching only whitespace-separated forms ("12 months", "5 years"). Hyphenated forms ("12-month", "5-year", "10-year") are common in HKEX prospectus text but are silently missed. The qualitative patterns correctly use `[\s-]` (e.g., `near[\s-]term`). Black-box tests BB-L5-T-001 through BB-L5-T-040 work around this by using space-separated forms, but real-world data will include hyphenated phrases. Consider changing `\s*` to `[\s-]*` in all numeric regex patterns for better recall.
- Decision Reason: Fixed by changing all `\s*` to `[\s-]*` in the four numeric regex patterns (`_SHORT_NUMERIC_RE`, `_MEDIUM_NUMERIC_RE`, `_LONG_NUMERIC_RE`, `_VERY_LONG_NUMERIC_RE`). Added four hyphenated-form unit tests (`test_hyphenated_12_month_is_short_term`, `test_hyphenated_5_year_is_very_long`, `test_hyphenated_3_year_is_long_term`, `test_hyphenated_2_year_is_medium_term`) to verify the fix.

### CR-006: CLI single-file mode reloads record from standard paths, discarding the user-supplied file content
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/timeline.py` lines 155-161, the CLI single-file path loads a record from `args.categorized`, derives the ticker, then calls `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)`. Inside `run()` (lines 119-125), the record is reloaded via `load_enriched_or_categorized()`, discarding the originally-loaded content from the user-specified file. If a user passes a non-standard file path (e.g., `python -m hk_ipo.enrichments.timeline /tmp/custom_record.json`), the tool ignores that file's content and instead reloads from the standard categorized directory. If the ticker-derived file does not exist in the standard directory, `load_enriched_or_categorized()` raises `FileNotFoundError` -- even though the user passed a valid file path. The reference implementation in `country.py` lines 146-152 correctly calls `_enrich_one(record, ENRICHED, force=args.force, ticker=ticker)` directly with the already-loaded record, honoring whatever file the user specified.
- Decision Reason: Fixed by changing CLI `__main__` block to call `_enrich_one(record, ENRICHED, DIMENSION, force=args.force, ticker=ticker)` directly instead of `run(CATEGORIZED_DIR, ENRICHED, ticker=ticker, force=args.force)`, matching the `country.py` pattern. Added `test__enrich_one_processes_arbitrary_record` and `test_run_ticker_mode_uses_categorized_fallback` unit tests.

### CR-007: `_VERY_LONG_QUAL_RE` uses `\s*` while all other qual/numeric patterns use `[\s-]*`, missing hyphenated qualitative forms
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/timeline.py` lines 58-61, `_VERY_LONG_QUAL_RE` uses `\s*` (whitespace only) in both `very\s*long` and `extended\s*(period|horizon|timeline)`. All other qualitative regex patterns (`_SHORT_QUAL_RE` line 47, `_MEDIUM_QUAL_RE` line 51, `_LONG_QUAL_RE` line 55) use `[\s-]*`. All numeric patterns were updated to `[\s-]*` per the CR-005 fix. This inconsistency means hyphenated qualitative forms like "very-long" and "extended-horizon" are silently classified as "unspecified" rather than "36m+". The black-box test BB-L5-T-038 tests "very long term" with spaces (passes), but no test covers the hyphenated form.
- Decision Reason: Fixed by changing `\s*` to `[\s-]*` in `_VERY_LONG_QUAL_RE` for both `very[\s-]*long` and `extended[\s-]*(period|horizon|timeline)`. Added `test_hyphenated_very_long_qualitative` and `test_hyphenated_extended_horizon` unit tests.

### CR-008: Missing trailing `\b` on `within`, `first`, and `mo` sub-patterns in `_SHORT_NUMERIC_RE`
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/timeline.py` lines 23-27, three sub-patterns in `_SHORT_NUMERIC_RE` lack a trailing word boundary while all other numeric unit patterns use `\b`:
  - `within[\s-]*(a|1)[\s-]*year` (no `\b` after `year`) -- could match "yearly", "yearbook"
  - `first[\s-]*year` (no `\b` after `year`) -- same issue
  - `12[\s-]*mo` (no `\b` after `mo`) -- could match "model", "module", "mother", and also spuriously matches within "12 months" (which is redundant, already covered by `12[\s-]*months?\b`)
  - For comparison, `6[\s-]*months?\b` correctly uses `\b`
  In practice these false positives are unlikely in prospectus text, but the inconsistency with all other patterns in the file is a maintainability concern and could silently produce wrong classifications if edge-case input appears.
- Decision Reason: Fixed by adding trailing `\b` to the three sub-patterns: `within[\s-]*(a|1)[\s-]*year\b`, `first[\s-]*year\b`, and `12[\s-]*mo\b`. Added `test_yearly_not_matched_as_year`, `test_model_not_matched_as_mo`, and `test_first_yearbook_not_matched` unit tests.
