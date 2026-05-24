# Changes: Task-006

## Files
- [mod] src/hk_ipo/l3_validation.py
- [mod] tests/test_l3_validation.py
- [add] tests/e2e/test_l3_blackbox.py

## Summary
Extended L3 validation with two new v2.0 checks: `[category_raw_present]` (every use item must have non-empty `category_raw`) and `[total_proceeds_present]` (`total_net_proceeds_hkd_million` must be non-null). Added `--strict` CLI flag to exit non-zero on validation failure. Promoted `sys` import to module level. Updated module docstring from 7 to 10 checks. Added 6 new unit tests covering the v2 checks and strict mode. Added 16 black-box tests (tests/e2e/test_l3_blackbox.py) that exercise the CLI via subprocess, covering all flags, exit codes, v2 field checks, error handling, and output format validation.

## Review Fixes (post-review)
- **SR-001**: Fixed docstring count from "10" to "11" checks.
- **SR-002**: Added `test_cli_strict_single_exits_nonzero` and `test_cli_strict_single_passes_exits_zero` tests that invoke the CLI via subprocess to verify `--strict` exit code behavior.
- **SR-003**: Added `if args.strict and not v["passed"]: sys.exit(1)` to the `--single` branch so `--strict` works consistently across both `--single` and `--all` modes.
- **SR-004**: Extra v2 pipeline changes (category=None exemption, TestCategoryNullV2) now documented here; they support the L4-deferred classification architecture.
- **CR-001**: Fixed `[total_proceeds_present]` falsy-check (`if not extracted.get(...)`) to explicit `is None` check, preventing false-positive on `total_net_proceeds_hkd_million=0`.
- **CR-002**: Fixed `str(u.get("category_raw", ""))` which converted `None` to literal `"None"` and bypassed the emptiness check. Now explicitly handles `None` before the `str().strip()` call.
- **CR-003**: Extended `[total_proceeds_present]` with an `elif float(tp) < 0` branch to validate non-negative values, giving it distinct scope from `[required_fields]`.
- **CR-004**: Existing task-006 tests for schema_version only duplicate TestSchemaVersion coverage incidentally; the tests are kept as-is since they exercise the same code paths described in the task spec and having multiple assertions on schema_version behavior is not harmful. Added 5 new tests: `test_total_proceeds_zero_is_valid`, `test_total_proceeds_negative_is_error`, `test_category_raw_none_is_flagged`, `test_cli_strict_single_exits_nonzero`, `test_cli_strict_single_passes_exits_zero`.
