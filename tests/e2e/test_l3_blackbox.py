"""Black-box tests for L3 validation CLI (Task 006).

These tests invoke ``python -m hk_ipo.l3_validation`` via subprocess and
verify behaviour through exit codes, stdout/stderr, and filesystem artefacts.
They do NOT import hk_ipo internals directly.

For --all mode tests that need custom directories, a temporary config override
shadows the real hk_ipo.config module so EXTRACTED_DIR points into tmp_path.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_CONFIG = PROJECT_ROOT / "src" / "hk_ipo" / "config.py"

pytestmark = pytest.mark.e2e


# ── Test data builders (black-box: define JSON structures from the external
#    file format specification, NOT from internal helpers) ───────────────────


def _valid_extraction_record() -> dict:
    """A fully-valid L2 extraction record matching the external file format."""
    total = 31123.0
    return {
        "company_file": "ltn20180907011.pdf",
        "section_source": "ltn20180907011.json",
        "hk_ticker": "3690",
        "document_date": "2018-09-07",
        "total_net_proceeds_hkd_million": total,
        "currency": "HKD",
        "schema_version": "2.0",
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


def _minimal_valid_record() -> dict:
    """Minimal valid record: one use, 100% allocation."""
    return {
        "company_file": "test.pdf",
        "hk_ticker": "1234",
        "document_date": "2025-01-01",
        "total_net_proceeds_hkd_million": 10000.0,
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "parent_id": None,
                "category": "Working capital",
                "category_raw": "general purposes",
                "amount_hkd_million": 10000.0,
                "percentage": 100.0,
                "description": "Working capital.",
                "source_text": "Approximately 100%...",
            }
        ],
    }


# ── Config override (same pattern as test_l1_blackbox.py) ──────────────────


def _make_l3_config_override(tmp_path: Path, extracted_dir: Path) -> str:
    """Create a shadow hk_ipo/ package that overrides config.py EXTRACTED_DIR.

    Returns the PYTHONPATH prefix directory to prepend.
    """
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)

    src_pkg = PROJECT_ROOT / "src" / "hk_ipo"
    shutil.copy(src_pkg / "__init__.py", pkg / "__init__.py")
    shutil.copy(src_pkg / "l3_validation.py", pkg / "l3_validation.py")
    shutil.copy(src_pkg / "schema.py", pkg / "schema.py")

    real_src = REAL_CONFIG.read_text(encoding="utf-8")
    config_py = real_src
    config_py = config_py.replace(
        'EXTRACTED_DIR: Path = DATA_DIR / "extracted"',
        f'EXTRACTED_DIR: Path = Path(r"{extracted_dir}")',
    )

    (pkg / "config.py").write_text(config_py, encoding="utf-8")
    return str(override_root)


def _run_l3_cli(
    *args: str,
    pythonpath_prefix: str | None = None,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke L3 module CLI via subprocess."""
    env = dict(os.environ)
    if pythonpath_prefix:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.l3_validation", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        check=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-001: --help output completeness
# ═══════════════════════════════════════════════════════════════════════════════


def test_help_output_lists_all_flags() -> None:
    """--help must document --single, --all, --tolerance-pct, and --strict."""
    result = _run_l3_cli("--help")
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "--single" in result.stdout, f"--single missing from help: {result.stdout[:400]}"
    assert "--all" in result.stdout, f"--all missing from help: {result.stdout[:400]}"
    assert "--tolerance-pct" in result.stdout, (
        f"--tolerance-pct missing from help: {result.stdout[:400]}"
    )
    assert "--strict" in result.stdout, f"--strict missing from help: {result.stdout[:400]}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-002: Missing required arguments
# ═══════════════════════════════════════════════════════════════════════════════


def test_missing_required_arg_exits_nonzero() -> None:
    """Calling with neither --single nor --all must exit non-zero."""
    result = _run_l3_cli()
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-003: --single valid record exits 0, writes .validated.json with PASS
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_valid_record_exits_zero(tmp_path: Path) -> None:
    """Valid record: --single exits 0, stdout contains PASS, output file is
    written with passed=True."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _valid_extraction_record()
    src = extracted_dir / "test_valid.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli("--single", "test_valid.json", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"
    assert "PASS" in result.stdout, f"Expected PASS in stdout: {result.stdout[:300]}"

    out_file = extracted_dir / "test_valid.validated.json"
    assert out_file.exists(), f"Expected {out_file}"
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["validation"]["passed"] is True
    assert saved["validation"]["errors"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# BB-004: --single invalid record exits 0 (no --strict), FAIL + errors in stdout
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_invalid_record_exits_zero_without_strict(tmp_path: Path) -> None:
    """Without --strict, invalid record still exits 0.
    stdout contains FAIL and the error messages."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _valid_extraction_record()
    record["uses"][0]["category_raw"] = ""  # triggers [category_raw_present]
    record["total_net_proceeds_hkd_million"] = (
        None  # triggers [total_proceeds_present] and [required_fields]
    )
    src = extracted_dir / "test_invalid.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli("--single", "test_invalid.json", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, (
        f"Without --strict, exit should be 0 even on FAIL. "
        f"exit={result.returncode} stderr={result.stderr[:300]}"
    )
    assert "FAIL" in result.stdout, f"Expected FAIL in stdout: {result.stdout[:300]}"
    assert "category_raw_present" in result.stdout, (
        f"Expected [category_raw_present] error: {result.stdout[:300]}"
    )
    assert "total_proceeds_present" in result.stdout, (
        f"Expected [total_proceeds_present] error: {result.stdout[:300]}"
    )

    out_file = extracted_dir / "test_invalid.validated.json"
    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["validation"]["passed"] is False
    assert len(saved["validation"]["errors"]) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# BB-005: --strict --single invalid record exits non-zero
# ═══════════════════════════════════════════════════════════════════════════════


def test_strict_single_invalid_exits_nonzero(tmp_path: Path) -> None:
    """--strict --single with invalid record exits non-zero."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _valid_extraction_record()
    record["hk_ticker"] = None  # triggers [required_fields]
    record["uses"][0]["category_raw"] = ""  # triggers [category_raw_present]
    src = extracted_dir / "test_strict_fail.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli(
        "--strict",
        "--single",
        "test_strict_fail.json",
        pythonpath_prefix=pp_prefix,
    )
    assert result.returncode != 0, (
        f"Expected non-zero exit with --strict on invalid record. exit={result.returncode}"
    )
    assert "FAIL" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# BB-006: --strict --single valid record exits 0
# ═══════════════════════════════════════════════════════════════════════════════


def test_strict_single_valid_exits_zero(tmp_path: Path) -> None:
    """--strict --single with valid record exits 0."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _valid_extraction_record()
    src = extracted_dir / "test_strict_pass.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli(
        "--strict",
        "--single",
        "test_strict_pass.json",
        pythonpath_prefix=pp_prefix,
    )
    assert result.returncode == 0, (
        f"Expected exit 0 with --strict on valid record. exit={result.returncode}"
    )
    assert "PASS" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# BB-007: --all mode processes multiple files
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_mode_processes_multiple_files(tmp_path: Path) -> None:
    """--all validates every .json in extracted_dir, creates .validated.json
    for each, and prints a summary with pass/fail counts."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    # Create 3 files: 2 valid, 1 invalid
    for i in range(2):
        rec = _minimal_valid_record()
        rec["company_file"] = f"valid_{i}.pdf"
        rec["uses"][0]["use_id"] = f"use_{i}"
        (extracted_dir / f"valid_{i}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )

    invalid = _minimal_valid_record()
    invalid["company_file"] = "invalid.pdf"
    invalid["uses"][0]["category_raw"] = ""
    (extracted_dir / "invalid.json").write_text(
        json.dumps(invalid, ensure_ascii=False), encoding="utf-8"
    )

    result = _run_l3_cli("--all", pythonpath_prefix=pp_prefix)

    # Should produce .validated.json for all 3
    out_files = list(extracted_dir.glob("*.validated.json"))
    assert len(out_files) == 3, (
        f"Expected 3 validated outputs, got {len(out_files)}: {[f.name for f in out_files]}"
    )

    # Summary line should show 2 passed, 1 failed
    assert "2 passed" in result.stdout, f"Expected '2 passed' in summary: {result.stdout}"
    assert "1 failed" in result.stdout, f"Expected '1 failed' in summary: {result.stdout}"

    # Exit 0 (no --strict)
    assert result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════════════
# BB-008: --all --strict exits non-zero when any failures exist
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_strict_exits_nonzero_on_any_failure(tmp_path: Path) -> None:
    """--all --strict exits non-zero when at least one file fails validation."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    # 1 valid, 1 invalid
    valid = _minimal_valid_record()
    (extracted_dir / "valid.json").write_text(
        json.dumps(valid, ensure_ascii=False), encoding="utf-8"
    )

    invalid = _minimal_valid_record()
    invalid["uses"][0]["category_raw"] = ""
    (extracted_dir / "invalid.json").write_text(
        json.dumps(invalid, ensure_ascii=False), encoding="utf-8"
    )

    result = _run_l3_cli("--all", "--strict", pythonpath_prefix=pp_prefix)
    assert result.returncode != 0, (
        f"Expected non-zero exit with --strict when failures exist. exit={result.returncode}"
    )
    assert "1 failed" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# BB-009: --all with empty directory produces WARN
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_empty_dir_produces_warn(tmp_path: Path) -> None:
    """Empty extracted_dir in --all mode produces a WARN message."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    result = _run_l3_cli("--all", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0
    assert "WARN" in result.stdout or "WARN" in result.stderr, (
        f"Expected [WARN] diagnostic. stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
    )
    assert "No extracted JSON" in (result.stdout + result.stderr), (
        f"Expected 'No extracted JSON' message: {result.stdout[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-010: --tolerance-pct alters validation outcome
# ═══════════════════════════════════════════════════════════════════════════════


def test_tolerance_pct_alters_validation_outcome(tmp_path: Path) -> None:
    """A record with 97% sum fails at tolerance=1 but passes at tolerance=5."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    # 97% sum (2 items: 60% + 37%), total matches amount sum to avoid
    # triggering [amount_sum] which has a hard-coded 1% threshold.
    total = 9700.0
    record = _minimal_valid_record()
    record["total_net_proceeds_hkd_million"] = total
    record["uses"] = [
        {
            "use_id": "use_001",
            "parent_id": None,
            "category": "Working capital",
            "category_raw": "wc",
            "amount_hkd_million": 6000.0,
            "percentage": 60.0,
            "description": "WC.",
            "source_text": "~60%...",
        },
        {
            "use_id": "use_002",
            "parent_id": None,
            "category": "R&D and technology",
            "category_raw": "rd",
            "amount_hkd_million": 3700.0,
            "percentage": 37.0,
            "description": "R&D.",
            "source_text": "~37%...",
        },
    ]

    # Tolerance 1 → deviation 3% → should fail
    src_fail = extracted_dir / "test_tol_fail.json"
    src_fail.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    result1 = _run_l3_cli(
        "--single",
        "test_tol_fail.json",
        "--tolerance-pct",
        "1",
        pythonpath_prefix=pp_prefix,
    )
    assert "FAIL" in result1.stdout, f"Expected FAIL at tolerance=1: {result1.stdout[:300]}"
    assert "[percentage_sum]" in result1.stdout, (
        f"Expected [percentage_sum] error: {result1.stdout[:300]}"
    )

    # Tolerance 5 → deviation 3% < 5% → should pass
    src_pass = extracted_dir / "test_tol_pass.json"
    src_pass.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    result2 = _run_l3_cli(
        "--single",
        "test_tol_pass.json",
        "--tolerance-pct",
        "5",
        pythonpath_prefix=pp_prefix,
    )
    assert "PASS" in result2.stdout, f"Expected PASS at tolerance=5: {result2.stdout[:300]}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-011: v2 field — empty category_raw produces error
# ═══════════════════════════════════════════════════════════════════════════════


def test_empty_category_raw_produces_error(tmp_path: Path) -> None:
    """Empty category_raw on any use item produces [category_raw_present] error."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _minimal_valid_record()
    record["uses"][0]["category_raw"] = ""
    src = extracted_dir / "test_catraw.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli("--single", "test_catraw.json", pythonpath_prefix=pp_prefix)
    assert "FAIL" in result.stdout
    assert "category_raw_present" in result.stdout, (
        f"Expected [category_raw_present] in output: {result.stdout[:400]}"
    )

    saved = json.loads((extracted_dir / "test_catraw.validated.json").read_text(encoding="utf-8"))
    assert not saved["validation"]["passed"]
    assert any("category_raw_present" in e for e in saved["validation"]["errors"])


# ═══════════════════════════════════════════════════════════════════════════════
# BB-012: v2 field — null total_net_proceeds produces error
# ═══════════════════════════════════════════════════════════════════════════════


def test_null_total_proceeds_produces_error(tmp_path: Path) -> None:
    """Null total_net_proceeds_hkd_million produces
    [total_proceeds_present] error."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _minimal_valid_record()
    record["total_net_proceeds_hkd_million"] = None
    src = extracted_dir / "test_proceeds.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli("--single", "test_proceeds.json", pythonpath_prefix=pp_prefix)
    assert "FAIL" in result.stdout
    assert "total_proceeds_present" in result.stdout, (
        f"Expected [total_proceeds_present] in output: {result.stdout[:400]}"
    )

    saved = json.loads((extracted_dir / "test_proceeds.validated.json").read_text(encoding="utf-8"))
    assert not saved["validation"]["passed"]
    assert any("total_proceeds_present" in e for e in saved["validation"]["errors"])


# ═══════════════════════════════════════════════════════════════════════════════
# BB-013: v2 field — schema_version mismatch produces warning
# ═══════════════════════════════════════════════════════════════════════════════


def test_schema_version_mismatch_produces_warning(tmp_path: Path) -> None:
    """A record with an old schema_version should produce a WARNING and still pass."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _minimal_valid_record()
    record["schema_version"] = "1.0"  # old version, current is 2.0
    src = extracted_dir / "test_schema_old.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l3_cli("--single", "test_schema_old.json", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, (
        f"Schema version warning should not cause non-zero exit "
        f"(without --strict). exit={result.returncode}"
    )
    assert "PASS" in result.stdout, (
        f"Expected PASS despite schema_version warning: {result.stdout[:300]}"
    )
    assert "schema_version" in result.stdout, (
        f"Expected [schema_version] in output: {result.stdout[:400]}"
    )

    saved = json.loads(
        (extracted_dir / "test_schema_old.validated.json").read_text(encoding="utf-8")
    )
    assert saved["validation"]["passed"] is True
    assert any("schema_version" in w for w in saved["validation"]["warnings"])


# ═══════════════════════════════════════════════════════════════════════════════
# BB-014: .validated.json has complete validation block
# ═══════════════════════════════════════════════════════════════════════════════

_VALIDATION_BLOCK_FIELDS = {
    "passed",
    "errors",
    "warnings",
    "tolerance_pct",
    "schema_version_validated_against",
    "validated_at",
}


def test_validated_json_has_complete_validation_block(tmp_path: Path) -> None:
    """The .validated.json file must contain a 'validation' block with all
    required fields: passed, errors, warnings, tolerance_pct,
    schema_version_validated_against, validated_at."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    record = _valid_extraction_record()
    src = extracted_dir / "test_block.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    _run_l3_cli("--single", "test_block.json", pythonpath_prefix=pp_prefix)

    out = extracted_dir / "test_block.validated.json"
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))

    assert "validation" in saved, "Output missing 'validation' key"
    v = saved["validation"]

    for field in sorted(_VALIDATION_BLOCK_FIELDS):
        assert field in v, f"validation block missing field: {field}"

    assert isinstance(v["passed"], bool)
    assert isinstance(v["errors"], list)
    assert isinstance(v["warnings"], list)
    assert isinstance(v["tolerance_pct"], (int, float))
    assert isinstance(v["schema_version_validated_against"], str)
    assert isinstance(v["validated_at"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# BB-015: --single with non-existent file exits non-zero
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """--single with a file that doesn't exist exits non-zero with error."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    result = _run_l3_cli("--single", "nonexistent.json", pythonpath_prefix=pp_prefix)
    assert result.returncode != 0, (
        f"Expected non-zero exit for non-existent file. exit={result.returncode}"
    )
    assert "Not found" in (result.stdout + result.stderr), (
        f"Expected 'Not found' error: stdout={result.stdout[:200]} stderr={result.stderr[:200]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-016: --all skips already-validated files (idempotency)
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_skips_validated_files(tmp_path: Path) -> None:
    """--all must skip *.validated.json files (they are output, not input)."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    pp_prefix = _make_l3_config_override(tmp_path, extracted_dir)

    # Only a .validated.json file — no raw input files
    validated_content = json.dumps(_minimal_valid_record(), ensure_ascii=False)
    (extracted_dir / "existing.validated.json").write_text(validated_content, encoding="utf-8")

    result = _run_l3_cli("--all", pythonpath_prefix=pp_prefix)
    # Should warn that no files were found (validated files are skipped)
    assert "No extracted JSON" in (result.stdout + result.stderr), (
        f"Expected skip of validated files: stdout={result.stdout[:300]}"
    )
