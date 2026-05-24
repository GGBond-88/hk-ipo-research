"""Black-box tests for L4 categorizer CLI (Task 008).

These tests invoke ``python -m hk_ipo.l4_categorize`` via subprocess and
verify behaviour through exit codes, stdout/stderr, and filesystem artefacts.
They do NOT import hk_ipo internals directly (except for path resolution).

For --all and single-file mode tests that need custom directories, a temporary
config override shadows the real hk_ipo.config module so EXTRACTED_DIR,
CATEGORIZED_DIR, and DATA_DIR point into tmp_path.
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


def _minimal_l2_record(hk_ticker: str = "01234") -> dict:
    """A minimal valid L2 extraction record (post-L2 flat extraction)."""
    return {
        "company_file": f"{hk_ticker}.pdf",
        "section_source": f"{hk_ticker}.json",
        "hk_ticker": hk_ticker,
        "document_date": "2025-01-01",
        "total_net_proceeds_hkd_million": 10000.0,
        "currency": "HKD",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "parent_id": None,
                "category": "R&D and technology",
                "category_raw": "research and development",
                "amount_hkd_million": 10000.0,
                "percentage": 100.0,
                "description": "Core product R&D.",
                "source_text": "Approximately 100%...",
            }
        ],
        "validation_preview": {
            "percentage_sum": 100.0,
            "top_level_count": 1,
            "total_items_count": 1,
        },
    }


# ── Config override (same pattern as test_l1_blackbox.py) ──────────────────


def _make_l4_config_override(
    tmp_path: Path,
    extracted_dir: Path,
    categorized_dir: Path,
) -> str:
    """Create a shadow hk_ipo/ package that overrides config.py directories.

    Copies __init__.py, l4_categorize.py, and taxonomy.py from the real
    package so that ``python -m hk_ipo.l4_categorize`` can run against
    the override.

    Returns the PYTHONPATH prefix directory to prepend.
    """
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)

    src_pkg = PROJECT_ROOT / "src" / "hk_ipo"
    shutil.copy(src_pkg / "__init__.py", pkg / "__init__.py")
    shutil.copy(src_pkg / "l4_categorize.py", pkg / "l4_categorize.py")
    shutil.copy(src_pkg / "taxonomy.py", pkg / "taxonomy.py")

    real_src = REAL_CONFIG.read_text(encoding="utf-8")
    config_py = real_src
    # Override DATA_DIR first so EXTRACTED_DIR and CATEGORIZED_DIR can
    # reference it.  We use a dedicated data dir under tmp_path.
    data_tmp = tmp_path / "data"
    config_py = config_py.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_tmp}")',
    )
    # Now override the derived dirs in case they were defined with explicit
    # paths (the default definitions use DATA_DIR, which we already patched).
    config_py = config_py.replace(
        'EXTRACTED_DIR: Path = DATA_DIR / "extracted"',
        f'EXTRACTED_DIR: Path = Path(r"{extracted_dir}")',
    )
    config_py = config_py.replace(
        'CATEGORIZED_DIR: Path = DATA_DIR / "categorized"',
        f'CATEGORIZED_DIR: Path = Path(r"{categorized_dir}")',
    )

    (pkg / "config.py").write_text(config_py, encoding="utf-8")
    return str(override_root)


def _run_l4_cli(
    *args: str,
    pythonpath_prefix: str | None = None,
    cwd: Path | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Invoke L4 module CLI via subprocess."""
    env = dict(os.environ)
    if pythonpath_prefix:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.l4_categorize", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        check=False,
    )


# ── Fixture: skip when API key is absent ──────────────────────────────────


@pytest.fixture
def api_key_present() -> None:
    """Skip the test if OPENROUTER_API_KEY is not set in the env."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")


# ═══════════════════════════════════════════════════════════════════════════════
# BB-001: --help output completeness
# ═══════════════════════════════════════════════════════════════════════════════


def test_help_output_lists_all_flags() -> None:
    """--help must document --all, --force, --limit, --model, and the file
    positional argument."""
    result = _run_l4_cli("--help")
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    assert "--all" in result.stdout, f"--all missing from help: {result.stdout[:400]}"
    assert "--force" in result.stdout, f"--force missing from help: {result.stdout[:400]}"
    assert "--limit" in result.stdout, f"--limit missing from help: {result.stdout[:400]}"
    assert "--model" in result.stdout, f"--model missing from help: {result.stdout[:400]}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-002: Missing required arguments
# ═══════════════════════════════════════════════════════════════════════════════


def test_missing_required_arg_exits_nonzero() -> None:
    """Calling with neither --all nor a positional file must exit non-zero."""
    result = _run_l4_cli()
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-003: --all with empty directory produces WARN
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_empty_dir_produces_warn(tmp_path: Path) -> None:
    """Empty extracted_dir in --all mode produces a [WARN] message and exits 0."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    result = _run_l4_cli("--all", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, f"Empty dir should exit 0, got {result.returncode}"
    combined = result.stdout + result.stderr
    assert "[WARN]" in combined, (
        f"Expected [WARN] diagnostic. stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
    )
    assert "No extracted JSON" in combined, (
        f"Expected 'No extracted JSON' message: stdout={result.stdout[:300]} "
        f"stderr={result.stderr[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-004: Single-file with nonexistent file exits non-zero
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """--single with a file that doesn't exist exits non-zero with error."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    result = _run_l4_cli(
        "nonexistent_file.json",
        pythonpath_prefix=pp_prefix,
    )
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
    combined = result.stdout + result.stderr
    assert "Not found" in combined or "ERROR" in combined, (
        f"Expected error message. stdout={result.stdout[:200]} stderr={result.stderr[:200]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-005: Single-file --force false skips existing output (no API call needed)
# ═══════════════════════════════════════════════════════════════════════════════


def test_force_false_skips_existing_output(tmp_path: Path) -> None:
    """Without --force in single-file mode, an existing categorized output is
    skipped and the original content is preserved.  This test does NOT require
    an API key because the skip happens before any LLM call."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    # Create an L2 extraction record
    record = _minimal_l2_record("01234")
    src = extracted_dir / "01234.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Pre-create a categorized output file
    out_file = categorized_dir / "01234.json"
    original_content = '{"original": true, "hk_ticker": "01234"}'
    out_file.write_text(original_content, encoding="utf-8")

    result = _run_l4_cli(str(src), pythonpath_prefix=pp_prefix)
    # Exit should be 0 (skip is not an error)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"
    # Output file must NOT be overwritten
    assert out_file.read_text(encoding="utf-8") == original_content, (
        "Output overwritten despite --force not set"
    )
    # [SKIP] appears on stdout per the L4 spec (unlike L1 which uses stderr)
    assert "[SKIP]" in result.stdout, (
        f"Expected [SKIP] on stdout/stderr: stdout={result.stdout[:200]} "
        f"stderr={result.stderr[:200]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-006: Single-file --force true overwrites existing output (needs API key)
# ═══════════════════════════════════════════════════════════════════════════════


def test_force_true_overwrites_existing_output(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """With --force in single-file mode, an existing categorized output is
    overwritten with fresh LLM results."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    record = _minimal_l2_record("01234")
    src = extracted_dir / "01234.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Pre-create a stale output file
    out_file = categorized_dir / "01234.json"
    original_content = '{"original": true, "hk_ticker": "01234"}'
    out_file.write_text(original_content, encoding="utf-8")

    result = _run_l4_cli(str(src), "--force", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"
    # Output must be overwritten
    new_content = out_file.read_text(encoding="utf-8")
    assert new_content != original_content, (
        f"Output NOT overwritten despite --force. exit={result.returncode}"
    )
    data = json.loads(new_content)
    assert data["hk_ticker"] == "01234"
    assert "uses" in data
    assert "validation" in data


# ═══════════════════════════════════════════════════════════════════════════════
# BB-007: --all mode processes multiple files (needs API key)
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_mode_processes_multiple_files(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """--all categorizes every .json in extracted_dir and writes corresponding
    categorized outputs.  Exits 0 on success."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    # Create 2 extraction records
    for ticker in ("00001", "00002"):
        rec = _minimal_l2_record(ticker)
        (extracted_dir / f"{ticker}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_l4_cli("--all", pythonpath_prefix=pp_prefix, timeout=600)
    assert result.returncode == 0, (
        f"exit={result.returncode}\nstdout={result.stdout[:500]}\nstderr={result.stderr[:500]}"
    )

    out_files = sorted(categorized_dir.glob("*.json"))
    assert len(out_files) == 2, (
        f"Expected 2 output files, got {len(out_files)}: {[f.name for f in out_files]}"
    )
    for out_f in out_files:
        data = json.loads(out_f.read_text(encoding="utf-8"))
        assert "uses" in data
        assert "validation" in data
        assert "schema_version" in data

    # Summary line should show success counts
    combined = result.stdout + result.stderr
    assert "succeeded" in combined.lower(), (
        f"Expected success summary: stdout={result.stdout[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-008: --limit caps number of files processed (needs API key)
# ═══════════════════════════════════════════════════════════════════════════════


def test_limit_caps_files_processed(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """--limit N must categorize at most N files."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    # Create 3 extraction records
    for ticker in ("00001", "00002", "00003"):
        rec = _minimal_l2_record(ticker)
        (extracted_dir / f"{ticker}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )

    limit = 2
    _run_l4_cli(
        "--all",
        "--limit",
        str(limit),
        pythonpath_prefix=pp_prefix,
        timeout=600,
    )
    out_files = list(categorized_dir.glob("*.json"))
    assert len(out_files) <= limit, (
        f"limit={limit} but produced {len(out_files)}: {[f.name for f in out_files]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-009: Output JSON has required schema fields (needs API key)
# ═══════════════════════════════════════════════════════════════════════════════

_CATEGORIZED_REQUIRED_TOP_FIELDS = {
    "company_file",
    "hk_ticker",
    "document_date",
    "schema_version",
    "uses",
    "validation",
}

_CATEGORIZED_VALIDATION_FIELDS = {
    "parent_sum",
    "parent_breakdown",
    "main_sums_by_parent",
    "rebalanced",
    "violations",
}

_CATEGORIZED_USE_FIELDS = {
    "use_id",
    "parent_category",
    "main_category",
    "sub_category",
    "percentage",
    "description",
}


def test_output_json_schema_contains_required_fields(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """Every L4 categorized output JSON must contain all v2 schema fields
    with correct types."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    record = _minimal_l2_record("01234")
    src = extracted_dir / "01234.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l4_cli(str(src), pythonpath_prefix=pp_prefix, timeout=300)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"

    out_file = categorized_dir / "01234.json"
    assert out_file.exists(), f"Expected {out_file}"
    data = json.loads(out_file.read_text(encoding="utf-8"))

    # Top-level fields
    for field in sorted(_CATEGORIZED_REQUIRED_TOP_FIELDS):
        assert field in data, f"Missing top-level field: {field}"

    assert data["schema_version"] == "2.0"
    assert isinstance(data["uses"], list)
    assert len(data["uses"]) >= 1
    assert isinstance(data["validation"], dict)

    # Validation block fields
    v = data["validation"]
    for field in sorted(_CATEGORIZED_VALIDATION_FIELDS):
        assert field in v, f"Missing validation field: {field}"
    assert isinstance(v["parent_sum"], (int, float))
    assert isinstance(v["parent_breakdown"], dict)
    assert isinstance(v["main_sums_by_parent"], dict)
    assert isinstance(v["rebalanced"], list)
    assert isinstance(v["violations"], list)

    # Each use item has required hierarchy fields
    for use in data["uses"]:
        for field in sorted(_CATEGORIZED_USE_FIELDS):
            assert field in use, f"Missing use-item field: {field}"
        assert use["parent_category"] in (
            "Growth",
            "Financing",
            "Working Capital",
            "Others",
        ), f"Invalid parent_category: {use['parent_category']}"
        assert isinstance(use["percentage"], (int, float))


# ═══════════════════════════════════════════════════════════════════════════════
# BB-010: [ERROR] diagnostics go to stderr
# ═══════════════════════════════════════════════════════════════════════════════


def test_error_diagnostics_go_to_stderr(tmp_path: Path) -> None:
    """When L4 encounters a processing error (e.g. malformed JSON), the
    [ERROR] diagnostic must appear on stderr."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    # Create a malformed JSON file that will cause a JSON decode error
    (extracted_dir / "bad.json").write_text("{this is not valid json at all!!!", encoding="utf-8")

    result = _run_l4_cli("--all", pythonpath_prefix=pp_prefix)
    # [ERROR] must appear on stderr (the implementation uses
    # print(..., file=sys.stderr) for errors)
    assert "[ERROR]" in result.stderr, (
        f"[ERROR] missing from stderr: stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-011: --all skips .validated.json and .error.json files
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_skips_validated_and_error_files(tmp_path: Path) -> None:
    """--all must skip *.validated.json and *.error.json files (they are
    output artefacts from other stages, not raw L2 extraction input)."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    # Only put non-input files in the extracted directory
    (extracted_dir / "existing.validated.json").write_text(
        json.dumps(_minimal_l2_record("00001"), ensure_ascii=False),
        encoding="utf-8",
    )
    (extracted_dir / "existing.error.json").write_text(
        '{"error": "something went wrong"}',
        encoding="utf-8",
    )

    result = _run_l4_cli("--all", pythonpath_prefix=pp_prefix)
    combined = result.stdout + result.stderr
    assert "No extracted JSON" in combined, (
        f"Expected skip of validated/error files: stdout={result.stdout[:300]} "
        f"stderr={result.stderr[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-012: Single-file mode processes a valid file (needs API key)
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_file_mode_produces_categorized_output(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """Single-file mode exits 0, writes categorized JSON with hierarchy fields."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    record = _minimal_l2_record("01234")
    src = extracted_dir / "01234.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l4_cli(str(src), pythonpath_prefix=pp_prefix, timeout=300)
    assert result.returncode == 0, (
        f"exit={result.returncode}\nstdout={result.stdout[:400]}\nstderr={result.stderr[:400]}"
    )
    assert "->" in result.stdout, f"stdout missing '->' processing indicator: {result.stdout[:200]}"
    assert "saved to" in result.stdout.lower(), f"stdout missing 'saved to': {result.stdout[:200]}"

    out_file = categorized_dir / "01234.json"
    assert out_file.exists(), f"Expected {out_file}"
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["hk_ticker"] == "01234"
    assert len(data["uses"]) >= 1
    # Every use must have parent_category populated
    for u in data["uses"]:
        assert "parent_category" in u
        assert u["parent_category"] in (
            "Growth",
            "Financing",
            "Working Capital",
            "Others",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-013: Taxonomy proposals CSV is created when novel sub-labels are found
# ═══════════════════════════════════════════════════════════════════════════════


def test_taxonomy_proposals_csv_created_for_novel_subs(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """When the LLM proposes novel sub-category labels, they are appended
    to DATA_DIR/taxonomy_proposals.csv."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    record = _minimal_l2_record("01234")
    src = extracted_dir / "01234.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l4_cli(str(src), pythonpath_prefix=pp_prefix, timeout=300)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"

    proposals_csv = tmp_path / "data" / "taxonomy_proposals.csv"
    # The CSV may or may not exist depending on whether LLM proposed novel
    # subs, but if it exists it must have the correct header.
    if proposals_csv.exists():
        content = proposals_csv.read_text(encoding="utf-8")
        assert "proposed_label" in content, f"CSV missing required header: {content[:200]}"
        assert "parent_category" in content
        assert "main_category" in content


# ═══════════════════════════════════════════════════════════════════════════════
# BB-014: --model flag is accepted without error (needs API key)
# ═══════════════════════════════════════════════════════════════════════════════


def test_model_flag_accepted(
    tmp_path: Path,
    api_key_present: None,
) -> None:
    """The --model flag should be accepted and not cause an argparse error."""
    extracted_dir = tmp_path / "extracted"
    categorized_dir = tmp_path / "categorized"
    extracted_dir.mkdir()
    categorized_dir.mkdir()
    pp_prefix = _make_l4_config_override(tmp_path, extracted_dir, categorized_dir)

    record = _minimal_l2_record("01234")
    src = extracted_dir / "01234.json"
    src.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_l4_cli(
        str(src),
        "--model",
        "openai/gpt-4o",
        pythonpath_prefix=pp_prefix,
        timeout=300,
    )
    # argparse should not reject --model
    assert "unrecognized arguments" not in result.stderr.lower(), (
        f"Unexpected argparse error: {result.stderr[:400]}"
    )
    # Should either succeed (API key works) or fail with an API error
    # (not an argparse error)
    if result.returncode != 0:
        assert (
            "model" not in result.stderr.lower().split("error")[0]
            if "error" in result.stderr.lower()
            else True
        )
