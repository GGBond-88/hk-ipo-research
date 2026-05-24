# Task Issues

## TI-001: Spec Simplified Chinese test text incompatible with spec detect_language algorithm
- **Description**: Task-004 Step 4 specifies `test_chinese_majority_text_returns_zh` using text `"本集团拟将全球发售所得款项净额用于以下用途。" * 20`. However, langdetect classifies this text as only ~57% zh-cn (43% ko), which is below the 80% threshold required by Step 5's `detect_language` implementation to return `"zh"`. The spec's test text and detection algorithm are mutually inconsistent.
- **Assumption**: Use longer, more varied Simplified Chinese text that langdetect reliably classifies with >= 80% zh probability (e.g., news-style content). The spec's intent is clearly to test Chinese language detection with Simplified Chinese, and the specific text choice is incidental.

## TI-002: "hong kong" entry in _COUNTRY_MAP contradicts test_extract_countries_no_match
- **Description**: Task-010 Step 3 includes `"hong kong": "HK"` in `_COUNTRY_MAP` with the comment "kept for completeness; geo tool handles HK specially". However, Step 1's `test_extract_countries_no_match` expects `extract_countries("We will expand our Hong Kong office.")` to return `[]` (no match). The code and test are mutually inconsistent.
- **Assumption**: The test is correct for the HKEX context where Hong Kong is not a foreign country for use-of-proceeds tracking. Remove the "hong kong" entry from `_COUNTRY_MAP` to match the test expectation.

## TI-003: Timeline regex priority order conflicts with test_very_long_36m_plus
- **Description**: Task-013's regex priority order (SHORT → MEDIUM → LONG → VERY LONG) matches qualitative "long-term" in `_LONG_TERM_RE` before numeric "5 years" in `_VERY_LONG_RE`. Text "Long-term investment to be deployed over 5 years" returns "24-36m" instead of expected "36m+". The code and test case in the task are mutually inconsistent.
- **Assumption**: Numeric/explicit time spans should take priority over qualitative phrases. Restructure classify_timeline into two phases: (1) check numeric patterns from longest to shortest, (2) if no numeric match, check qualitative patterns from longest to shortest.
