# Implement Review Results: Task-015

## Spec Review Issues

### SR-001: Additional plural/inflected forms blocked by `\b` boundary -- same root cause as CR-014
- Status: Resolved
- Description: CR-014 fixed 7 keywords to match common plural/inflected forms that were silently blocked by the `\b` word boundary. However, 7 additional keywords still have the same defect -- their singular-only form cannot match common plural/inflected variants because `\b` expects a word boundary immediately after the keyword stem, but plural suffixes (`s`, `es`, `ies`) continue the word across that boundary. Verified via Python REPL -- all return `None`:

  **`_GREEN_KW` affected (2 keywords):**
  - `electric[\s-]+vehicle` (line 29) does NOT match "electric vehicles" -- extremely common plural
  - `environment` (line 28) does NOT match "environments" -- common plural in ESG ("protecting environments")

  **`_SOCIAL_KW` affected (1 keyword):**
  - `community` (line 36) does NOT match "communities" -- very common plural in social contexts

  **`_GOVERNANCE_KW` affected (4 keywords):**
  - `audit` (line 46) does NOT match "audits" -- common plural ("internal audits", "compliance audits")
  - `internal[\s-]+control` (line 47) does NOT match "internal controls" -- this IS the standard governance term; singular "internal control" is less common than the plural
  - `shareholder[\s-]+right` (line 47) does NOT match "shareholder rights" -- very common plural
  - `whistleblower` (line 48) does NOT match "whistleblowers" -- common plural

  Fix: apply the same pattern as CR-014 -- expand affected keywords to non-capturing alternation groups that include common inflected forms (e.g., `environments?`, `communit(?:y|ies)`, `audits?`, `electric[\s-]+vehicles?`, `internal[\s-]+controls?`, `shareholder[\s-]+rights?`, `whistleblowers?`).
- Decision Reason:

## Code Review Issues

### CR-001: Regex `\s*` causes false positives for concatenated non-words
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/esg_tag.py`, `_GREEN_KW` (lines 23-24) uses `clean\s*energy` (matches "cleanenergy") and `electric\s*vehicle` (matches "electricvehicle"). `_SOCIAL_KW` (line 32) uses `affordable\s*housing` (matches "affordablehousing"). `_GOVERNANCE_KW` (lines 42-43) uses `internal\s*control` (matches "internalcontrol"), `shareholder\s*right` (matches "shareholderright"), and `data\s*privacy` (matches "dataprivacy"). None of these concatenated forms are real English words. All six `\s*` patterns should use `\s+` or `[\s-]+` to require at least one separator between the words.
- Decision Reason:

### CR-002: Regex `ev\s` causes false negatives for "EV." and "EVs"
- Status: Resolved
- Description: In `_GREEN_KW` (line 26), `ev\s` requires a whitespace after "ev"/"EV", so it fails to match "EV." (end of sentence), "EVs" (plural), or "EV," (comma). The trailing `\s` is unnecessary since the outer `\b(...)\b` already enforces word boundaries. Verified: `_GREEN_KW.search('We use EV.')` returns `None` and `_GREEN_KW.search('We sell EVs.')` returns `None`. Should be just `ev`.
- Decision Reason:

### CR-003: Regex `[\s-]` causes false negatives for legitimate merged forms
- Status: Resolved
- Description: In `_SOCIAL_KW` (line 35), `micro[\s-]finance` does not match "microfinance" (a standard English compound word). In `_GOVERNANCE_KW` (lines 41-42), `anti[\s-]corruption` does not match "anticorruption" and `anti[\s-]bribery` does not match "antibribery" -- both are legitimate English words. The `[\s-]` quantifier (exactly one separator) should use `[\s-]?` or `[\s-]*` for terms that commonly appear both merged and hyphenated/spaced.
- Decision Reason:

### CR-004: `_SOCIAL_KW` pattern `access\s*to\s` consumes trailing word boundary
- Status: Resolved
- Description: In `_SOCIAL_KW` (lines 33-34), `access\s*to\s` ends with `\s` inside `\b(...)\b`. The trailing `\s` consumes a space after "to", and the outer `\b` anchors on the far side of that space. This means it only matches when "access to" is directly followed by another word (e.g., "access to healthcare") but fails for "access to." at end of sentence. Additionally, with `\s*` set to zero, it matches "accessto" followed by a space (e.g., "accessto schools"). The trailing `\s` should be removed; `\b(access\s+to)\b` would be sufficient.
- Decision Reason:

### CR-005: Inconsistent multi-word separator style across all three regexes
- Status: Resolved
- Description: Multi-word keywords use three different separator styles inconsistently: `\s*` (e.g., `clean\s*energy`, `affordable\s*housing`, `internal\s*control`), `[\s-]` (e.g., `carbon[\s-]neutral`, `risk[\s-]management`, `micro[\s-]finance`), and plain concatenation for others. There is no documented rationale for which style to use. This inconsistency directly causes the false positive and false negative bugs in CR-001 through CR-004. A unified convention (e.g., `[\s-]+` for all multi-word keywords) would prevent these bugs and make the keyword lists easier to audit.
- Decision Reason:

### CR-006: `test_multiple_tags` missing governance assertion
- Status: Resolved
- Description: In `tests/test_enrichments_esg_tag.py` (lines 44-53), the test item includes "governance" in both description and source_text, and `classify_esg` correctly returns all three tags `["green", "social", "governance"]`, but the test only asserts `"green"` and `"social"`. The test should also assert `"governance" in tags` to fully verify the expected behavior for this input.
- Decision Reason:

### CR-007: Missing unit test coverage for edge cases
- Status: Resolved
- Description: The test file lacks coverage for: (a) an item where all three tags (green + social + governance) apply simultaneously, (b) an empty item dict with no fields, (c) items where string fields are `None` rather than empty strings, and (d) explicit case-insensitivity verification (e.g., "SOLAR", "Healthcare", "GOVERNANCE"). These are real-world edge cases the `classify_esg` function must handle.
- Decision Reason:

### CR-008: No black-box / e2e tests for esg_tag CLI
- Status: Resolved
- Description: All other L5 enrichment tools have corresponding black-box tests in `tests/e2e/` (e.g., `test_l5_capex_opex_blackbox.py`, `test_l5_country_blackbox.py`, `test_l5_industry_blackbox.py`, `test_l5_timeline_blackbox.py`) that invoke the CLI via subprocess and verify behavior through exit codes, stdout/stderr, and filesystem artifacts. The esg_tag enrichment has no such black-box test. A file `tests/e2e/test_l5_esg_tag_blackbox.py` should be created covering: single-file tagging, --all mode, --force idempotency, missing-file error handling, stdout reporting, prior enrichment preservation, empty uses list, and tag correctness for each ESG dimension.
- Decision Reason:

### CR-009: Regex stem patterns broken by `\b` boundary -- silent false negatives
- Status: Resolved
- Description: Four word-stem patterns in `src/hk_ipo/enrichments/esg_tag.py` are shorter than the real words they intend to match, and the outer `\b(...)\b` group boundary requires a word boundary immediately after the stem. This makes all four effectively dead patterns that never match their intended targets:

  In `_GREEN_KW` (lines 30-31):
  - `energy[\s-]+efficien` does NOT match "energy efficient" or "energy efficiency" (stem "efficien" ends at `n`; `\b` expects boundary, but `c`/`y` follows in the real words)
  - `decarboni` does NOT match "decarbonization", "decarbonisation", or "decarbonizing" (same root cause)

  In `_SOCIAL_KW` (lines 39-40):
  - `charit` does NOT match "charity", "charitable", or "charities"
  - `philanthrop` does NOT match "philanthropy" or "philanthropic"

  Verified via Python REPL: `_GREEN_KW.search("energy efficient")` returns `None`; `_GREEN_KW.search("decarbonization")` returns `None`; `_SOCIAL_KW.search("charity")` returns `None`; `_SOCIAL_KW.search("philanthropy")` returns `None`.

  Fix: Remove the stems from inside the `\b(...)\b` alternation group and either list them as standalone prefix patterns without trailing `\b`, or expand them to full-word alternations (e.g., `(decarbonization|decarbonisation|decarbonizing|decarbonise|decarbonize)`).
- Decision Reason: Expanded all four stems to full-word alternations using non-capturing groups: `energy[\s-]+efficien(?:t|cy|cies|tly)`, `decarboni(?:zation|sation|zing|sing|zed|sed|ze|se)`, `charit(?:y|ies|able)`, `philanthrop(?:y|ic|ist|ists|ies)`. Added 8 new unit tests covering each expanded stem variant. All 19 unit tests and 18 blackbox e2e tests pass.

### CR-010: Missing `use_id` guard causes `KeyError` on malformed use items
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/esg_tag.py`, `_enrich_one` (line 83) accesses `u["use_id"]` directly without a `.get()` guard, while the containing loop already defensively handles a missing `"uses"` key via `record.get("uses", [])`. If any individual use item in the list is malformed (e.g., missing the `use_id` field), the function raises an unhandled `KeyError`, crashing the entire enrichment pipeline for that ticker. A defensive `u.get("use_id", "")` would be consistent with the rest of the codebase's style and prevent crashes from malformed data.
- Decision Reason: Changed `u["use_id"]` to `u.get("use_id", "")` in `_enrich_one` line 83. Added unit test `test_missing_use_id_no_key_error` that verifies no KeyError is raised when a use item lacks a use_id field. All tests pass.

### CR-011: `decarboni` stem regex missing third-person singular verb forms
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/esg_tag.py` line 31, the `_GREEN_KW` regex pattern `decarboni(?:zation|sation|zing|sing|zed|sed|ze|se)` omits the third-person singular verb forms `zes` (US: "decarbonizes") and `ses` (UK: "decarbonises"). Verified via REPL: `_GREEN_KW.search("decarbonizes")` returns `None` and `_GREEN_KW.search("decarbonises")` returns `None`. These are real English words that should match the green tag. Fix: add `zes` and `ses` to the alternation: `decarboni(?:zation|sation|zing|sing|zed|sed|zes|ses|ze|se)`.
- Decision Reason: Added `zes` and `ses` to the `decarboni` alternation group. Added two new unit tests (`test_green_stem_decarbonizes`, `test_green_stem_decarbonises`) that verify matching of third-person singular verb forms. All 21 unit tests and full test suite (389 tests) pass.

### CR-012: `classify_esg` converts `None` field values to literal string `"None"`
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/esg_tag.py` lines 54-57, `classify_esg` builds the search text via `str(item.get("description", ""))`. When a key exists with value `None` (e.g., `{"description": None}`), `dict.get()` returns `None` (the default `""` only applies when the key is absent), and `str(None)` produces the literal string `"None"`. This injects the word "None" into the regex search space. While no current ESG keyword matches "None", this is incorrect behavior that could produce silent false matches if future keywords are added. The existing test `test_none_field_values` passes only because `"None"` happens not to match any keyword. Fix: use `str(item.get("description") or "")` to treat `None` as empty string.
- Decision Reason: Changed all three `str(item.get(key, ""))` calls to `str(item.get(key) or "")` in `classify_esg`. The `or ""` operator correctly treats both missing keys (where `.get()` returns `""` from default) and existing keys with `None` values (where `.get()` returns `None`, and `None or ""` evaluates to `""`) as empty strings. All 21 unit tests pass.

### CR-013: `test_missing_use_id_no_key_error` leaks temp directory
- Status: Resolved
- Description: In `tests/test_enrichments_esg_tag.py` lines 185-201, the test calls `tempfile.mkdtemp()` (line 196) to create a temp directory, then passes it to `_enrich_one` which writes a JSON file inside it via `save_enriched`. The test never removes the temp directory or its contents. While the OS will eventually clean it, tests should clean up their own resources. The test should use a `try/finally` with `shutil.rmtree()` or leverage `tmp_path` (pytest fixture) which auto-cleans up.
- Decision Reason: Added `import shutil` and a `finally` block with `shutil.rmtree(enriched_dir, ignore_errors=True)` to ensure the temp directory is always cleaned up after the test, regardless of success or failure.

### CR-014: `\b` word boundary prevents matching plural/inflected forms of multiple ESG keywords
- Status: Resolved
- Description: In `src/hk_ipo/enrichments/esg_tag.py`, all keywords inside `\b(...)\b` alternation groups fail to match their plural or inflected forms because `\b` requires a word boundary immediately after the keyword stem, but plural suffixes (`s`, `es`, `ies`) and other inflected suffixes continue the word across that position. This is the same root cause as CR-009 but affects common singular nouns rather than stems. Verified via REPL -- all return `None`:

  **Green keywords affected:**
  - `emission` (line 28) does NOT match "emissions" -- extremely common: "carbon emissions", "greenhouse gas emissions", "reduce emissions". The word "emission" in singular form is rare in corporate prose; virtually all real-world usage is plural.
  - `recycling` (line 29) does NOT match "recycle", "recycled", "recycles" -- common verb/adjective forms like "recycle materials" or "recycled water".

  **Social keywords affected:**
  - `patient` (line 38) does NOT match "patients" -- overwhelmingly more common plural form in healthcare contexts.
  - `hospital` (line 38) does NOT match "hospitals" -- equally common plural.
  - `school` (line 38) does NOT match "schools" -- equally common plural.
  - `clinic` (line 38) does NOT match "clinics" -- equally common plural.
  - `university` (line 38) does NOT match "universities" -- moderately common.

  The fix pattern is the same as CR-009/CR-011: expand each affected keyword to a non-capturing alternation group that includes common inflected forms (e.g., `emissions?`, `patients?`, `hospitals?`, `schools?`, `clinics?`, `recycl(?:e|ed|es|ing)`, `universit(?:y|ies)`). Unlike CR-009 where the stems matched NOTHING at all, these keywords DO match their singular forms, but the plural forms are at least as common and their absence substantially impairs tag coverage.
- Decision Reason: Expanded 7 affected keywords to non-capturing alternation groups to include common inflected/plural forms: `emission` -> `emissions?`, `recycling` -> `recycl(?:e|ed|es|ing)`, `patient` -> `patients?`, `hospital` -> `hospitals?`, `school` -> `schools?`, `clinic` -> `clinics?`, `university` -> `universit(?:y|ies)`. Added 9 new unit tests (one per inflected/plural form) with clean keyword-only text to avoid false passes from other keywords. All 30 unit tests, 18 e2e blackbox tests, and full test suite (398 tests) pass.

### CR-015: CR-010 KeyError guard not applied to 5 sibling enrichment tools
- Status: Resolved
- Description: CR-010 identified that direct `u["use_id"]` access without a `.get()` guard causes an unhandled `KeyError` on malformed use items. The fix (`u.get("use_id", "")`) was applied to `src/hk_ipo/enrichments/esg_tag.py:83` but the identical vulnerable pattern still exists in 5 other enrichment tools:

  - `src/hk_ipo/enrichments/capex_opex.py:84` — `by_use_id[u["use_id"]] = classify_capex_opex(u)`
  - `src/hk_ipo/enrichments/country.py:115` — `by_use_id[u["use_id"]] = codes`
  - `src/hk_ipo/enrichments/geo.py:120` — `by_use_id[u["use_id"]] = classify_geo(u, company)`
  - `src/hk_ipo/enrichments/specificity.py:104` — `by_use_id[u["use_id"]] = classify_specificity(u)`
  - `src/hk_ipo/enrichments/timeline.py:104` — `by_use_id[u["use_id"]] = classify_timeline(u)`

  Any of these tools will crash with an unhandled `KeyError` if a malformed use item missing the `use_id` field is encountered. Since CR-010 established this as a recognized defect pattern, the fix should be propagated to all affected files for consistency and robustness.
- Decision Reason:

### CR-016: CR-012 None-value guard not propagated to 5 sibling enrichment tools
- Status: Resolved
- Description: CR-012 identified that `str(item.get(key, ""))` produces the literal string `"None"` when a key exists with value `None`, because `dict.get(key, default)` only applies the default when the key is absent. The fix (`str(item.get(key) or "")`) was applied to `src/hk_ipo/enrichments/esg_tag.py:55-57` but the identical vulnerable pattern still exists in all 5 sibling enrichment tools that were also modified by this task:

  - `src/hk_ipo/enrichments/capex_opex.py:59-61` — `str(item.get("description", ""))`, `str(item.get("category_raw", ""))`, `str(item.get("source_text", ""))`
  - `src/hk_ipo/enrichments/country.py:111-113` — `str(u.get("description", ""))`, `str(u.get("category_raw", ""))`, `str(u.get("source_text", ""))`
  - `src/hk_ipo/enrichments/geo.py:55-57` — `str(item.get("description", ""))`, `str(item.get("category_raw", ""))`, `str(item.get("source_text", ""))`
  - `src/hk_ipo/enrichments/specificity.py:42-43` — `str(item.get("description", ""))`, `str(item.get("source_text", ""))`
  - `src/hk_ipo/enrichments/timeline.py:66-67` — `str(item.get("description", ""))`, `str(item.get("source_text", ""))`

  When any of these text fields exists with a `None` value, `str(None)` produces `"None"` and injects it into the regex search space. While no current keyword matches "None", this is incorrect behavior that could produce silent false matches if future keywords are added. This is the same propagation gap pattern as CR-015 (where the CR-010 use_id guard had to be propagated). Fix: change all `str(item.get(key, ""))` to `str(item.get(key) or "")` across all 5 sibling tools.
- Decision Reason:
