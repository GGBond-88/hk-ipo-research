# Implement Review Results: Task-006

## Spec Review Issues

### SR-001: Docstring count says "10 checks" but 11 are listed
- Status: Resolved
- Description: The module docstring header says "10 项检查（按 check_id 标识）" but the bullet list below enumerates 11 checks: required_fields, ticker_format, percentage_sum, amount_sum, item_consistency, no_duplicate_use_id, category_vocab, category_l1, category_raw_present, total_proceeds_present, schema_version. The count is off by one.
- Decision Reason:

### SR-002: `--strict` CLI flag has zero actual test coverage
- Status: Resolved
- Description: The `test_strict_mode_exits_nonzero` test does NOT test the `--strict` CLI flag at all. It only calls `validate_record()` with empty uses and asserts `isinstance(passed, bool)`. No test in the entire suite verifies that `--strict --all` actually causes `sys.exit(1)` when validation fails, nor that `--strict --single` does (or does not) exit non-zero. The `--strict` CLI behavior is completely untested.
- Decision Reason:

### SR-003: `--strict` flag silently ignored in `--single` mode
- Status: Resolved
- Description: When `--strict` is passed with `--single`, the flag is accepted by argparse but has no effect on exit code. If validation fails in single-file mode with `--strict`, the process still exits 0. This is inconsistent with the documented help text "Exit non-zero on any validation failure". Users passing `--strict --single` would reasonably expect non-zero exit on failure.
- Decision Reason:

### SR-004: Extra undocumented changes beyond task spec
- Status: Resolved
- Description: The implementation includes changes not specified in the task requirements: (a) `if cat is None: continue` exemption added to the `[category_vocab]` check in `validate_record()`, (b) a new `TestCategoryNullV2` test class with 2 tests (`test_category_none_no_category_vocab_warning`, `test_empty_category_string_still_warns`). These changes are functionally beneficial for the v2 pipeline (L2 sets category=None), but they are not mentioned in `changes.md` and were not required by the task spec's A3.1-A3.3 criteria.
- Decision Reason:

## Code Review Issues

### CR-001: `[total_proceeds_present]` falsy-check incorrectly flags `0` as missing
- Status: Resolved
- Description: At `src/hk_ipo/l3_validation.py:225`, the check uses `if not extracted.get("total_net_proceeds_hkd_million")` instead of `is None`. This treats `0` and `0.0` as missing/null, adding a false-positive error. The check's own comment says "must be non-null" but the code tests falsiness, not nullity. A value of `0` is a valid (if unusual) float for this field. Should use `is None` to match the stated intent.
- Decision Reason:

### CR-002: `str(None)` bypasses `category_raw` emptiness check at L3:217
- Status: Resolved
- Description: At `src/hk_ipo/l3_validation.py:217`, `cat_raw = str(u.get("category_raw", "")).strip()` converts a `None` value to the literal string `"None"`, which is non-empty and silently passes the `if not cat_raw` check. If a raw dict has `category_raw: None`, the validator accepts it without flagging. While the Pydantic `UseItem` model defaults `category_raw` to `""`, `validate_record()` accepts arbitrary dicts and should defensively handle `None`. Explicit `None` handling (e.g., treating `None` the same as empty string) is needed.
- Decision Reason:

### CR-003: `[total_proceeds_present]` duplicates `[required_fields]` error for `None` value
- Status: Resolved
- Description: When `total_net_proceeds_hkd_million` is `None`, both `[required_fields]` (lines 76-82) and `[total_proceeds_present]` (lines 225-228) fire as ERROR. This produces duplicate error messages for the same root cause. If CR-001 is fixed (changing to `is None`), the `[total_proceeds_present]` check becomes entirely redundant with `[required_fields]`, which already checks all `_REQUIRED_TOP_FIELDS` for missing-or-null. The check either needs a distinct scope (beyond what `[required_fields]` covers) or should be removed to avoid noise.
- Decision Reason:

### CR-004: Task 006 tests duplicate existing `TestSchemaVersion` coverage
- Status: Resolved
- Description: `TestTask006::test_schema_version_mismatch_warns` (test_l3_validation.py:628) and `TestTask006::test_schema_version_present_no_warning` (test_l3_validation.py:636) duplicate the same assertions already covered by `TestSchemaVersion::test_mismatched_schema_version_is_warning` (line 586) and `TestSchemaVersion::test_matching_schema_version_no_warning` (line 594). The only difference is the test class and the specific "old version" string used ("1.0" vs "0.9"), which exercises the same code path. Test duplication increases maintenance burden without adding coverage.
- Decision Reason:
