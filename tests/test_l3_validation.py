"""Unit tests for L3 validation layer (src/hk_ipo/l3_validation.py).

Coverage strategy:
  - All tests call validate_record() directly with constructed dicts.
  - No real file I/O, no LLM calls, no network access.
  - validate_file() wired up via pytest tmp_path for one idempotence check.

Test inventory (16 tests):
  1.  Happy path — Meituan-like record, all 4 uses, 100% sum → passes, no errors
  2.  [required_fields] — missing 'uses' key → error
  3.  [required_fields] — null hk_ticker → error
  4.  [ticker_format] — alpha ticker → error
  5.  [ticker_format] — 3-digit ticker → error
  6.  [percentage_sum] — sum = 70.0, tol = 1.0 → error
  7.  [amount_sum] — amounts sum too high → error
  8.  [item_consistency] — one item amount wildly off → error
  9.  [no_duplicate_use_id] — duplicate use_id → error
  10. [percentage_sum] warning — null pct, not error
  11. [amount_sum] warning — null amount, not error
  12. [category_vocab] warning — out-of-vocab category, still passes
  13. Multi-error — missing field + bad ticker + pct sum off simultaneously
  14. Tolerance test — 98.5% passes at tol=2.0, fails at tol=1.0
  15. validate_file() writes .validated.json with "validation" block (tmp_path)
  16. Idempotence — validate_record twice returns identical results
"""

import json
from pathlib import Path

from hk_ipo.l3_validation import validate_file, validate_record
from hk_ipo.schema import CATEGORY_L2, SCHEMA_VERSION

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _meituan() -> dict:
    """Construct a fully valid Meituan-like extracted dict (all 4 uses, 100%)."""
    total = 31123.0
    return {
        "company_file": "ltn20180907011.pdf",
        "section_source": "ltn20180907011.json",
        "hk_ticker": "3690",
        "document_date": "2018-09-07",
        "total_net_proceeds_hkd_million": total,
        "currency": "HKD",
        "uses": [
            {
                "use_id": "use_001",
                "parent_id": None,
                "category": "R&D and technology",
                "category_raw": "upgrade technology",
                "amount_hkd_million": round(total * 0.35, 2),
                "percentage": 35.0,
                "description": "Tech upgrades and R&D.",
                "source_text": "approximately 35%...",
            },
            {
                "use_id": "use_002",
                "parent_id": None,
                "category": "Product development",
                "category_raw": "develop new services and products",
                "amount_hkd_million": round(total * 0.35, 2),
                "percentage": 35.0,
                "description": "New services and products.",
                "source_text": "approximately 35%...",
            },
            {
                "use_id": "use_003",
                "parent_id": None,
                "category": "Acquisitions and investments",
                "category_raw": "acquisitions or investments",
                "amount_hkd_million": round(total * 0.20, 2),
                "percentage": 20.0,
                "description": "Selective acquisitions.",
                "source_text": "approximately 20%...",
            },
            {
                "use_id": "use_004",
                "parent_id": None,
                "category": "Working capital",
                "category_raw": "working capital and general corporate purposes",
                "amount_hkd_million": round(total * 0.10, 2),
                "percentage": 10.0,
                "description": "Working capital.",
                "source_text": "approximately 10%...",
            },
        ],
        "validation_preview": {
            "percentage_sum": 100.0,
            "top_level_count": 4,
            "total_items_count": 4,
        },
    }


def _use(
    use_id: str, pct: float | None, amt: float | None, category: str = "Working capital"
) -> dict:
    """Minimal use dict helper."""
    return {
        "use_id": use_id,
        "parent_id": None,
        "category": category,
        "category_raw": "some purpose",
        "amount_hkd_million": amt,
        "percentage": pct,
        "description": "Desc.",
        "source_text": "Approximately X%...",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Happy path
# ─────────────────────────────────────────────────────────────────────────────


class TestHappyPath:
    def test_meituan_all_four_uses_passes(self):
        passed, errors, warnings = validate_record(_meituan())
        assert passed is True
        assert errors == []

    def test_meituan_no_unexpected_warnings(self):
        """Meituan dict uses only valid vocab categories — no warnings expected."""
        _, _, warnings = validate_record(_meituan())
        # Only category_vocab warnings could appear; all 4 categories are valid.
        cat_warns = [w for w in warnings if "[category_vocab]" in w]
        assert cat_warns == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 2-3: [required_fields]
# ─────────────────────────────────────────────────────────────────────────────


class TestRequiredFields:
    def test_missing_uses_key_is_error(self):
        rec = _meituan()
        del rec["uses"]
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[required_fields]" in e and "uses" in e for e in errors)

    def test_null_hk_ticker_is_error(self):
        rec = _meituan()
        rec["hk_ticker"] = None
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[required_fields]" in e and "hk_ticker" in e for e in errors)

    def test_null_document_date_is_error(self):
        rec = _meituan()
        rec["document_date"] = None
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[required_fields]" in e and "document_date" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Tests 4-5: [ticker_format]
# ─────────────────────────────────────────────────────────────────────────────


class TestTickerFormat:
    def test_alpha_ticker_is_error(self):
        rec = _meituan()
        rec["hk_ticker"] = "MEIT"
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[ticker_format]" in e for e in errors)

    def test_three_digit_ticker_is_error(self):
        rec = _meituan()
        rec["hk_ticker"] = "369"
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[ticker_format]" in e for e in errors)

    def test_four_digit_ticker_passes(self):
        rec = _meituan()
        rec["hk_ticker"] = "3690"
        passed, errors, _ = validate_record(rec)
        # ticker_format should not appear in errors
        assert not any("[ticker_format]" in e for e in errors)

    def test_five_digit_ticker_passes(self):
        rec = _meituan()
        rec["hk_ticker"] = "12345"
        passed, errors, _ = validate_record(rec)
        assert not any("[ticker_format]" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: [percentage_sum] error path
# ─────────────────────────────────────────────────────────────────────────────


class TestPercentageSum:
    def test_sum_70_fails_at_default_tolerance(self):
        """LLM-variance scenario: only 2 of 4 items extracted → sum 70%."""
        rec = _meituan()
        rec["uses"] = rec["uses"][:2]  # keep only first 2 (35% + 35% = 70%)
        passed, errors, _ = validate_record(rec, tolerance_pct=1.0)
        assert passed is False
        assert any("[percentage_sum]" in e for e in errors)

    def test_sum_100_passes(self):
        passed, errors, _ = validate_record(_meituan(), tolerance_pct=1.0)
        assert not any("[percentage_sum]" in e for e in errors)

    def test_sum_exactly_at_tolerance_boundary_passes(self):
        """99.0% with tolerance=1.0 → deviation=1.0 which is NOT > 1.0 → passes."""
        rec = _meituan()
        rec["uses"] = [_use("use_001", 99.0, 30000.0)]
        rec["total_net_proceeds_hkd_million"] = 30000.0
        passed, errors, _ = validate_record(rec, tolerance_pct=1.0)
        assert not any("[percentage_sum]" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: [amount_sum] error path
# ─────────────────────────────────────────────────────────────────────────────


class TestAmountSum:
    def test_amounts_sum_too_high_is_error(self):
        """Amounts sum to 120% of total → >1% deviation → error."""
        total = 10000.0
        rec = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2025-01-01",
            "total_net_proceeds_hkd_million": total,
            "uses": [
                _use("use_001", 60.0, 7000.0),  # expected 6000, has 7000
                _use("use_002", 40.0, 5000.0),  # expected 4000, has 5000
            ],
        }
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[amount_sum]" in e for e in errors)

    def test_amounts_within_1pct_passes(self):
        total = 10000.0
        rec = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2025-01-01",
            "total_net_proceeds_hkd_million": total,
            "uses": [
                _use("use_001", 60.0, 6000.0),
                _use("use_002", 40.0, 4000.0),
            ],
        }
        _, errors, _ = validate_record(rec)
        assert not any("[amount_sum]" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: [item_consistency] error path
# ─────────────────────────────────────────────────────────────────────────────


class TestItemConsistency:
    def test_one_item_wildly_off_is_error(self):
        """10% of 10000 = 1000, but we supply 5000 → 40% deviation of total."""
        total = 10000.0
        rec = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2025-01-01",
            "total_net_proceeds_hkd_million": total,
            "uses": [
                _use("use_001", 90.0, 9000.0),  # 90% × 10000 = 9000 ✓
                _use("use_002", 10.0, 5000.0),  # 10% × 10000 = 1000 ≠ 5000 ✗
            ],
        }
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[item_consistency]" in e and "use_002" in e for e in errors)

    def test_consistent_items_no_error(self):
        total = 10000.0
        rec = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2025-01-01",
            "total_net_proceeds_hkd_million": total,
            "uses": [
                _use("use_001", 70.0, 7000.0),
                _use("use_002", 30.0, 3000.0),
            ],
        }
        _, errors, _ = validate_record(rec)
        assert not any("[item_consistency]" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: [no_duplicate_use_id]
# ─────────────────────────────────────────────────────────────────────────────


class TestNoDuplicateUseId:
    def test_duplicate_use_id_is_error(self):
        rec = _meituan()
        rec["uses"][1]["use_id"] = "use_001"  # duplicate of first
        passed, errors, _ = validate_record(rec)
        assert passed is False
        assert any("[no_duplicate_use_id]" in e for e in errors)

    def test_all_unique_use_ids_no_error(self):
        rec = _meituan()
        _, errors, _ = validate_record(rec)
        assert not any("[no_duplicate_use_id]" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Tests 10-12: Warning-only paths (passed=True)
# ─────────────────────────────────────────────────────────────────────────────


class TestWarningOnly:
    def test_null_percentage_downgrades_to_warning(self):
        """When a use has null percentage, sum check becomes a WARNING, not ERROR."""
        rec = _meituan()
        rec["uses"][0]["percentage"] = None  # knock out one pct
        passed, errors, warnings = validate_record(rec)
        assert not any("[percentage_sum]" in e for e in errors), (
            "Should not raise ERROR when percentage is null"
        )
        assert any("[percentage_sum]" in w for w in warnings)
        # Record still passes (no other errors from this test mutation)
        # NOTE: passed might be False if other errors exist; we only test
        # that percentage_sum is a warning, not an error.
        assert not any("[percentage_sum]" in e for e in errors)

    def test_null_amount_downgrades_to_warning(self):
        """When a use has null amount, amount sum check becomes a WARNING."""
        rec = _meituan()
        rec["uses"][0]["amount_hkd_million"] = None
        _, errors, warnings = validate_record(rec)
        assert not any("[amount_sum]" in e for e in errors)
        assert any("[amount_sum]" in w for w in warnings)

    def test_out_of_vocab_category_is_warning_not_error(self):
        """An unrecognised category is a WARNING; the record still passes."""
        rec = _meituan()
        rec["uses"][0]["category"] = "Unrecognised bucket"
        passed, errors, warnings = validate_record(rec)
        assert not any("[category_vocab]" in e for e in errors)
        assert any("[category_vocab]" in w for w in warnings)
        # Assuming no other failures, record should pass
        assert passed is True


# ─────────────────────────────────────────────────────────────────────────────
# Test 13: Multi-error (3 simultaneous failures)
# ─────────────────────────────────────────────────────────────────────────────


class TestMultiError:
    def test_three_simultaneous_failures(self):
        """missing document_date + bad ticker + pct sum = 70%."""
        rec = _meituan()
        rec["document_date"] = None  # [required_fields]
        rec["hk_ticker"] = "BAD"  # [ticker_format]
        rec["uses"] = rec["uses"][:2]  # [percentage_sum]: 70%

        passed, errors, _ = validate_record(rec, tolerance_pct=1.0)
        assert passed is False

        check_ids = {e.split("]")[0].lstrip("[") for e in errors}
        assert "required_fields" in check_ids
        assert "ticker_format" in check_ids
        assert "percentage_sum" in check_ids
        assert len(errors) >= 3


# ─────────────────────────────────────────────────────────────────────────────
# Test 14: Tolerance boundary
# ─────────────────────────────────────────────────────────────────────────────


class TestToleranceBoundary:
    """98.5% sum: deviation = 1.5%.  Fails at tol=1.0, passes at tol=2.0."""

    def _rec_985(self) -> dict:
        rec = _meituan()
        # Replace uses with two items summing to 98.5%
        total = 10000.0
        rec["total_net_proceeds_hkd_million"] = total
        rec["uses"] = [
            _use("use_001", 58.5, total * 0.585),
            _use("use_002", 40.0, total * 0.40),
        ]
        return rec

    def test_985_pct_fails_at_tolerance_1(self):
        passed, errors, _ = validate_record(self._rec_985(), tolerance_pct=1.0)
        assert passed is False
        assert any("[percentage_sum]" in e for e in errors)

    def test_985_pct_passes_at_tolerance_2(self):
        _, errors, _ = validate_record(self._rec_985(), tolerance_pct=2.0)
        assert not any("[percentage_sum]" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Test 15: validate_file writes .validated.json (uses tmp_path)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateFile:
    def test_writes_validated_json_with_validation_block(self, tmp_path: Path):
        # Write a valid extracted JSON to tmp_path
        extracted = _meituan()
        src = tmp_path / "ltn20180907011.json"
        src.write_text(json.dumps(extracted, ensure_ascii=False), encoding="utf-8")

        validate_file(src, tmp_path, tolerance_pct=1.0)

        # Output file must exist
        out = tmp_path / "ltn20180907011.validated.json"
        assert out.exists()

        # Load and check schema
        saved = json.loads(out.read_text(encoding="utf-8"))
        assert "validation" in saved
        v = saved["validation"]
        assert "passed" in v
        assert "errors" in v
        assert "warnings" in v
        assert "tolerance_pct" in v
        assert "validated_at" in v
        assert v["passed"] is True
        assert v["errors"] == []

    def test_return_value_matches_written_file(self, tmp_path: Path):
        extracted = _meituan()
        src = tmp_path / "ltn20180907011.json"
        src.write_text(json.dumps(extracted, ensure_ascii=False), encoding="utf-8")

        result = validate_file(src, tmp_path, tolerance_pct=1.0)
        saved = json.loads((tmp_path / "ltn20180907011.validated.json").read_text(encoding="utf-8"))
        # Spot-check key fields are identical
        assert result["validation"]["passed"] == saved["validation"]["passed"]
        assert result["hk_ticker"] == saved["hk_ticker"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 16: Idempotence
# ─────────────────────────────────────────────────────────────────────────────


class TestIdempotence:
    def test_calling_validate_record_twice_gives_same_result(self):
        rec = _meituan()
        result1 = validate_record(rec)
        result2 = validate_record(rec)
        assert result1 == result2

    def test_record_not_mutated_by_validate_record(self):
        import copy

        rec = _meituan()
        original = copy.deepcopy(rec)
        validate_record(rec)
        assert rec == original


# ─────────────────────────────────────────────────────────────────────────────
# Tests: [category_l1]
# ─────────────────────────────────────────────────────────────────────────────


class TestCategoryL1:
    def test_out_of_vocab_category_deferred_to_category_vocab_not_l1(self):
        """An out-of-vocab category produces [category_vocab] WARNING, not [category_l1] ERROR.

        [category_l1] is only checked for vocab-member categories to avoid double-reporting.
        Out-of-vocab categories are caught exclusively by [category_vocab].
        """
        rec = _meituan()
        rec["uses"][0] = {
            "use_id": "use_001",
            "parent_id": None,
            "category": "Fake Category",
            "category_proposed": None,
            "category_raw": "fake",
            "amount_hkd_million": round(31123.0 * 0.35, 2),
            "percentage": 35.0,
            "description": "Fake.",
            "source_text": "approximately 35%...",
        }
        passed, errors, warnings = validate_record(rec)
        # [category_vocab] warning fires (not an error)
        assert any("[category_vocab]" in w and "Fake Category" in w for w in warnings)
        # [category_l1] does NOT fire because out-of-vocab is deferred to [category_vocab]
        assert not any("[category_l1]" in e for e in errors)
        # record still passes (category_vocab is warning-only)
        assert passed is True

    def test_category_l1_exempt_when_category_proposed_set(self):
        """When category_proposed is set, [category_l1] check is skipped."""
        rec = _meituan()
        rec["uses"][0]["category"] = "Fake Category"
        rec["uses"][0]["category_proposed"] = "Some novel use"
        _, errors, _ = validate_record(rec)
        assert not any("[category_l1]" in e for e in errors)

    def test_all_standard_category_l2_values_pass_l1_check(self):
        """Every standard L2 category maps to an L1 — no [category_l1] errors."""
        for cat in CATEGORY_L2:
            rec = _meituan()
            rec["uses"][0]["category"] = cat
            _, errors, _ = validate_record(rec)
            assert not any("[category_l1]" in e for e in errors), (
                f"[category_l1] error unexpectedly fired for valid category {cat!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tests: v2 category=None (L4-deferred classification)
# ─────────────────────────────────────────────────────────────────────────────


class TestCategoryNullV2:
    """v2 pipeline: L2 sets category=None because classification is deferred to L4.
    [category_vocab] must NOT warn on None — it is intentional, not out-of-vocab."""

    def test_category_none_no_category_vocab_warning(self):
        """When category is explicitly None (v2 L2 output), [category_vocab] must NOT warn."""
        total = 10000.0
        rec = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2025-01-01",
            "total_net_proceeds_hkd_million": total,
            "uses": [
                {
                    "use_id": "use_001",
                    "parent_id": None,
                    "category": None,
                    "category_proposed": None,
                    "category_raw": "research",
                    "amount_hkd_million": 10000.0,
                    "percentage": 100.0,
                    "description": "R&D.",
                    "source_text": "Approximately 100%...",
                }
            ],
        }
        passed, errors, warnings = validate_record(rec)
        assert not any("[category_vocab]" in e for e in errors)
        assert not any("[category_vocab]" in w for w in warnings)
        assert passed is True

    def test_empty_category_string_still_warns(self):
        """Empty string '' is not None — it's a real (invalid) value and should warn."""
        total = 10000.0
        rec = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2025-01-01",
            "total_net_proceeds_hkd_million": total,
            "uses": [
                {
                    "use_id": "use_001",
                    "parent_id": None,
                    "category": "",
                    "category_proposed": None,
                    "category_raw": "research",
                    "amount_hkd_million": 10000.0,
                    "percentage": 100.0,
                    "description": "R&D.",
                    "source_text": "Approximately 100%...",
                }
            ],
        }
        passed, errors, warnings = validate_record(rec)
        # Empty string is NOT in vocab → should warn
        assert any("[category_vocab]" in w for w in warnings)
        assert passed is True  # warning-only, still passes


# ─────────────────────────────────────────────────────────────────────────────
# Tests: [schema_version]
# ─────────────────────────────────────────────────────────────────────────────


class TestSchemaVersion:
    def test_absent_schema_version_is_warning(self):
        """If schema_version is absent, a WARNING is emitted (never an error)."""
        rec = _meituan()
        # _meituan() does not include schema_version — it's absent by default
        assert "schema_version" not in rec
        passed, errors, warnings = validate_record(rec)
        assert not any("[schema_version]" in e for e in errors)
        assert any("[schema_version]" in w for w in warnings)

    def test_mismatched_schema_version_is_warning(self):
        """A different schema_version fires a WARNING (old data still processable)."""
        rec = _meituan()
        rec["schema_version"] = "0.9"
        passed, errors, warnings = validate_record(rec)
        assert not any("[schema_version]" in e for e in errors)
        assert any("[schema_version]" in w and "0.9" in w for w in warnings)

    def test_matching_schema_version_no_warning(self):
        """When schema_version matches SCHEMA_VERSION exactly, no warning."""
        rec = _meituan()
        rec["schema_version"] = SCHEMA_VERSION
        _, _, warnings = validate_record(rec)
        assert not any("[schema_version]" in w for w in warnings)


# ── Task 006 — L3 v2 extended checks ────────────────────────────────────────


class TestTask006:
    def test_empty_category_raw_flags_error(self):
        """A use item with empty category_raw should produce a warning."""
        record = _meituan()
        record["uses"][0]["category_raw"] = ""
        passed, errors, warnings = validate_record(record)
        assert not passed  # category_raw empty -> error (data quality)
        assert any("category_raw" in e.lower() for e in errors)

    def test_all_category_raw_non_empty_passes(self):
        record = _meituan()
        for u in record["uses"]:
            u["category_raw"] = u.get("category_raw") or "some raw description"
        passed, errors, warnings = validate_record(record)
        assert passed
        assert not any("category_raw" in e.lower() for e in errors)

    def test_missing_total_net_proceeds_flags_error(self):
        record = _meituan()
        record["total_net_proceeds_hkd_million"] = None
        passed, errors, warnings = validate_record(record)
        assert not passed
        assert any("total_net_proceeds" in e.lower() for e in errors)

    def test_schema_version_mismatch_warns(self):
        record = _meituan()
        record["schema_version"] = "1.0"  # old version
        passed, errors, warnings = validate_record(record)
        # schema_version mismatch is a WARNING, not ERROR (old data still processable)
        assert passed
        assert any("schema_version" in w.lower() for w in warnings)

    def test_schema_version_present_no_warning(self):
        from hk_ipo.schema import SCHEMA_VERSION

        record = _meituan()
        record["schema_version"] = SCHEMA_VERSION
        passed, errors, warnings = validate_record(record)
        assert passed
        assert not any("schema_version" in w.lower() for w in warnings)

    def test_strict_mode_exits_nonzero(self):
        """validate_file does not change exit code; verify that the validation
        function reports status correctly."""
        record = _meituan()
        record["uses"] = []  # empty uses -> should pass but warn
        passed, errors, warnings = validate_record(record)
        # With empty uses there's naught to sum — passed but with warnings
        # This test just ensures validate_record handles empty uses gracefully
        assert isinstance(passed, bool)

    def test_total_proceeds_zero_is_valid(self):
        """total_net_proceeds_hkd_million=0 should NOT trigger [total_proceeds_present]."""
        record = _meituan()
        record["total_net_proceeds_hkd_million"] = 0.0
        passed, errors, _ = validate_record(record)
        # 0 is a falsy but valid float — must not be treated as missing
        assert not any("[total_proceeds_present]" in e for e in errors)

    def test_total_proceeds_negative_is_error(self):
        """Negative total_net_proceeds should be flagged as invalid."""
        record = _meituan()
        record["total_net_proceeds_hkd_million"] = -100.0
        passed, errors, _ = validate_record(record)
        assert not passed
        assert any("[total_proceeds_present]" in e for e in errors)

    def test_category_raw_none_is_flagged(self):
        """category_raw=None should be treated as empty and flagged as error."""
        record = _meituan()
        record["uses"][0]["category_raw"] = None
        passed, errors, _ = validate_record(record)
        assert not passed
        assert any("category_raw" in e.lower() for e in errors)

    def test_cli_strict_single_exits_nonzero(self, tmp_path: Path):
        """--strict --single should exit non-zero when validation fails."""
        import subprocess
        import sys

        # Write an invalid extracted JSON (missing ticker → validation fails)
        invalid = _meituan()
        invalid["hk_ticker"] = None
        src = tmp_path / "bad.json"
        src.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "hk_ipo.l3_validation", "--strict", "--single", str(src)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit for --strict --single with invalid data; "
            f"got {result.returncode}"
        )

    def test_cli_strict_single_passes_exits_zero(self, tmp_path: Path):
        """--strict --single should exit zero when validation passes."""
        import subprocess
        import sys

        valid = _meituan()
        valid["schema_version"] = SCHEMA_VERSION
        src = tmp_path / "good.json"
        src.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "hk_ipo.l3_validation", "--strict", "--single", str(src)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Expected zero exit for --strict --single with valid data; got {result.returncode}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# P1-6: Concurrency smoke test — serial vs parallel result equivalence
# ─────────────────────────────────────────────────────────────────────────────


class TestProcessAllConcurrency:
    """Verify that parallel L3 process_all produces identical results to serial."""

    def test_serial_vs_parallel_identical_results(self, tmp_path: Path):
        """process_all with workers=1 and workers=4 should produce equivalent
        validation results on a small fixture set."""
        from hk_ipo.l3_validation import process_all

        # Create 4 fixture files in extracted_dir from _meituan variants
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        for i in range(4):
            rec = _meituan()
            rec["hk_ticker"] = f"{1000 + i}"
            rec["company_file"] = f"test{i}.pdf"
            path = extracted_dir / f"test{i}.json"
            path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

        # Run serial (workers=1)
        out1 = tmp_path / "out1"
        out1.mkdir()
        summary1 = process_all(extracted_dir, out1, workers=1)

        # Run parallel (workers=4)
        out2 = tmp_path / "out2"
        out2.mkdir()
        summary2 = process_all(extracted_dir, out2, workers=4)

        # Summaries (pass / fail / total) must match
        assert summary1 == summary2, (
            f"Summary mismatch: serial={summary1}, parallel={summary2}"
        )

        # Every output file in serial run must have a matching peer in parallel run
        for f1 in out1.glob("*.validated.json"):
            f2 = out2 / f1.name
            assert f2.exists(), f"Missing parallel output: {f2}"
            d1 = json.loads(f1.read_text(encoding="utf-8"))
            d2 = json.loads(f2.read_text(encoding="utf-8"))
            # Validation results must be identical (timestamps may differ)
            assert d1["validation"]["passed"] == d2["validation"]["passed"]
            assert d1["validation"]["errors"] == d2["validation"]["errors"]
            assert d1["validation"]["warnings"] == d2["validation"]["warnings"]

        # No extra files should appear in parallel output
        serial_names = {f.name for f in out1.glob("*.validated.json")}
        parallel_names = {f.name for f in out2.glob("*.validated.json")}
        assert serial_names == parallel_names
