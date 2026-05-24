"""Black-box tests for L5 capex_opex enrichment CLI (Task 014).

These tests invoke ``python -m hk_ipo.enrichments.capex_opex`` via subprocess and
verify behaviour through exit codes, stdout/stderr, and filesystem artefacts.
They do NOT import hk_ipo internals (beyond the CLI module path needed for
the shadow-package config override).

For tests that need custom data directories, a temporary config override shadows
the real ``hk_ipo.config`` module so that ``DATA_DIR`` and ``CATEGORIZED_DIR``
point into ``tmp_path``.
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
SRC_PKG = PROJECT_ROOT / "src" / "hk_ipo"
REAL_CONFIG = SRC_PKG / "config.py"

pytestmark = pytest.mark.e2e


# -- Helpers ------------------------------------------------------------------


def _make_config_override(tmp_path: Path) -> str:
    """Create a shadow hk_ipo package that overrides DATA_DIR to tmp_path/data.

    Returns the directory to prepend to PYTHONPATH.
    """
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)

    # Copy only the files necessary for the capex_opex enrichment CLI.
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")

    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "capex_opex.py", enrich_dst / "capex_opex.py")

    # Write config with DATA_DIR redirected into tmp_path.
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def _run_capex_opex_cli(
    *args: str,
    pythonpath_prefix: str,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.enrichments.capex_opex`` via subprocess."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.capex_opex", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        check=False,
    )


def _make_record(
    hk_ticker: str,
    uses: list[dict[str, object]],
    company_name_en: str = "Test Corp",
) -> dict[str, object]:
    """Build a valid categorized/enriched record matching the external file format."""
    return {
        "hk_ticker": hk_ticker,
        "company_name_en": company_name_en,
        "schema_version": "2.0",
        "uses": uses,
        "enrichments": {},
    }


def _make_use(
    use_id: str,
    description: str,
    category_raw: str = "expansion",
    percentage: float = 100.0,
    source_text: str = "",
) -> dict[str, object]:
    """Build a single use item matching the external use-item schema."""
    return {
        "use_id": use_id,
        "description": description,
        "category_raw": category_raw,
        "percentage": percentage,
        "source_text": source_text or description,
    }


# -- Single-file mode: capex classification ----------------------------------


def test_single_file_capex_factory_construction(tmp_path: Path) -> None:
    """BB-L5-CO-001: Single-file mode classifies factory construction as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00001",
        [
            _make_use(
                "u1",
                "Construct a manufacturing plant with machinery.",
                category_raw="factory construction",
                source_text="We will build a new plant and install equipment.",
            ),
        ],
    )
    infile = cat_dir / "00001.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out_file = data_dir / "enriched" / "00001.json"
    assert out_file.exists(), (
        f"Missing {out_file}; enriched dir has: "
        f"{[f.name for f in (data_dir / 'enriched').glob('*')]}"
    )
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["version"] >= 1
    assert block["by_use_id"]["u1"] == "capex"


def test_single_file_opex_working_capital(tmp_path: Path) -> None:
    """BB-L5-CO-002: Single-file mode classifies working capital as opex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00002",
        [
            _make_use(
                "u1",
                "General working capital for day-to-day opex.",
                category_raw="working capital",
                source_text="Approximately 10% for general working capital and opex.",
            ),
        ],
    )
    infile = cat_dir / "00002.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00002.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "opex"


def test_single_file_financial_debt_repayment(tmp_path: Path) -> None:
    """BB-L5-CO-003: Single-file mode classifies debt repayment as financial."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00003",
        [
            _make_use(
                "u1",
                "Repay outstanding bank loans and bonds.",
                category_raw="debt repayment",
                source_text="Approximately 20% to repay bank loans and redeem bonds.",
            ),
        ],
    )
    infile = cat_dir / "00003.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00003.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "financial"


def test_single_file_default_capex_ambiguous(tmp_path: Path) -> None:
    """BB-L5-CO-004: Ambiguous text defaults to capex classification."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00004",
        [
            _make_use(
                "u1",
                "Something.",
                category_raw="general",
                source_text="Something without recognizable keywords.",
            ),
        ],
    )
    infile = cat_dir / "00004.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00004.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "capex", (
        "Default classification for unrecognized text must be 'capex'"
    )


# -- Single-file mode: multiple uses per record -----------------------------


def test_single_file_multiple_uses_per_record(tmp_path: Path) -> None:
    """BB-L5-CO-005: Multiple use items are each enriched independently."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00005",
        [
            _make_use(
                "u1",
                "Build a factory with equipment.",
                category_raw="factory construction",
                percentage=40.0,
            ),
            _make_use(
                "u2",
                "Working capital for day-to-day operations.",
                category_raw="working capital",
                percentage=30.0,
            ),
            _make_use(
                "u3",
                "Repay outstanding bank loans.",
                category_raw="debt repayment",
                percentage=30.0,
            ),
        ],
    )
    infile = cat_dir / "00005.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00005.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "capex"
    assert block["by_use_id"]["u2"] == "opex"
    assert block["by_use_id"]["u3"] == "financial"


# -- Classification priority order -------------------------------------------


def test_single_file_priority_opex_over_capex(tmp_path: Path) -> None:
    """BB-L5-CO-006: Opex keywords override capex keywords (opex > capex)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00006",
        [
            _make_use(
                "u1",
                "Working capital for construction projects.",
                category_raw="mixed allocation",
                source_text="Funds for working capital and construct new facilities.",
            ),
        ],
    )
    infile = cat_dir / "00006.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00006.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "opex", (
        "Opex must override capex when both keywords are present"
    )


def test_single_file_priority_financial_over_opex(tmp_path: Path) -> None:
    """BB-L5-CO-007: Financial keywords override opex keywords (financial > opex)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00007",
        [
            _make_use(
                "u1",
                "Repay bank loans and supplement working capital.",
                category_raw="mixed allocation",
                source_text="Proceeds to repay bank loans and provide working capital.",
            ),
        ],
    )
    infile = cat_dir / "00007.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00007.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "financial", (
        "Financial must override opex when both keywords are present"
    )


def test_single_file_priority_financial_over_all(tmp_path: Path) -> None:
    """BB-L5-CO-008: Financial overrides both opex and capex when all three co-occur."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00008",
        [
            _make_use(
                "u1",
                "Repay debt, working capital, construct new plant.",
                category_raw="mixed allocation",
                source_text="Repay debt, fund working capital, and construct a new plant.",
            ),
        ],
    )
    infile = cat_dir / "00008.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00008.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u1"] == "financial", (
        "Financial must override both opex and capex when all three co-occur"
    )


# -- Morphological variants (black-box verification) ------------------------


def test_single_file_operating_expenses_plural_is_opex(tmp_path: Path) -> None:
    """BB-L5-CO-009: 'operating expenses' (plural) must classify as opex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00009",
        [
            _make_use(
                "u1",
                "Cover operating expenses.",
                category_raw="fund allocation",
                source_text="The proceeds will cover operating expenses for the firm.",
            ),
        ],
    )
    infile = cat_dir / "00009.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00009.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "opex"


def test_single_file_data_centers_plural_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-010: 'data centers' (plural) must classify as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00010",
        [
            _make_use(
                "u1",
                "Set up new data centers.",
                category_raw="technology program",
                source_text="The firm will set up new data centers for the region.",
            ),
        ],
    )
    infile = cat_dir / "00010.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00010.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_repayment_is_financial(tmp_path: Path) -> None:
    """BB-L5-CO-011: 'repayment' must classify as financial."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00011",
        [
            _make_use(
                "u1",
                "For the repayment plan.",
                category_raw="use of funds",
                source_text="For the repayment of our obligations.",
            ),
        ],
    )
    infile = cat_dir / "00011.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00011.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "financial"


def test_single_file_facilities_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-012: 'facilities' (plural) must classify as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00012",
        [
            _make_use(
                "u1",
                "Develop storage facilities.",
                category_raw="logistics",
                source_text="To develop storage facilities for our operations.",
            ),
        ],
    )
    infile = cat_dir / "00012.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00012.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_marketing_campaigns_plural_is_opex(tmp_path: Path) -> None:
    """BB-L5-CO-013: 'marketing campaigns' (plural) must classify as opex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00013",
        [
            _make_use(
                "u1",
                "Marketing campaigns for new products.",
                category_raw="promotion",
                source_text="Funds allocated to marketing campaigns for our products.",
            ),
        ],
    )
    infile = cat_dir / "00013.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00013.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "opex"


def test_single_file_warehousing_gerund_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-014: 'warehousing' (gerund) must classify as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00014",
        [
            _make_use(
                "u1",
                "Warehousing and logistics project.",
                category_raw="logistics",
                source_text="The project involves warehousing and logistics.",
            ),
        ],
    )
    infile = cat_dir / "00014.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00014.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_advertised_past_is_opex(tmp_path: Path) -> None:
    """BB-L5-CO-015: 'advertised' (past tense) must classify as opex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00015",
        [
            _make_use(
                "u1",
                "Advertised promotions.",
                category_raw="marketing spend",
                source_text="Funds were used for advertised promotions across media.",
            ),
        ],
    )
    infile = cat_dir / "00015.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00015.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "opex"


# -- Non-existent / error paths -----------------------------------------------


def test_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-CO-016: Non-existent input file causes non-zero exit and stderr message."""
    prefix = _make_config_override(tmp_path)

    bad_path = tmp_path / "data" / "nonexistent.json"
    result = _run_capex_opex_cli(str(bad_path), pythonpath_prefix=prefix)

    assert result.returncode != 0, (
        f"Expected non-zero exit for missing file, got {result.returncode}"
    )
    assert "ERROR" in result.stderr or "Not found" in result.stderr, (
        f"stderr: {result.stderr[:300]}"
    )


def test_no_args_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-CO-017: Calling with neither --all nor input path exits non-zero."""
    prefix = _make_config_override(tmp_path)
    result = _run_capex_opex_cli(pythonpath_prefix=prefix)
    assert result.returncode != 0, f"Expected non-zero exit with no args, got {result.returncode}"


# -- --all mode --------------------------------------------------------------


def test_all_mode_processes_all_files(tmp_path: Path) -> None:
    """BB-L5-CO-018: --all processes every JSON in categorized_dir."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    test_cases = [
        ("00020", "Build factory equipment."),
        ("00021", "Working capital for daily operations."),
        ("00022", "Repay outstanding bank loans."),
    ]
    for i, (ticker, text) in enumerate(test_cases):
        record = _make_record(ticker, [_make_use(f"u{i + 1}", text)])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_capex_opex_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out20 = json.loads((data_dir / "enriched" / "00020.json").read_text(encoding="utf-8"))
    out21 = json.loads((data_dir / "enriched" / "00021.json").read_text(encoding="utf-8"))
    out22 = json.loads((data_dir / "enriched" / "00022.json").read_text(encoding="utf-8"))

    assert out20["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"
    assert out21["enrichments"]["capex_opex"]["by_use_id"]["u2"] == "opex"
    assert out22["enrichments"]["capex_opex"]["by_use_id"]["u3"] == "financial"


def test_all_mode_falls_back_when_enriched_empty(tmp_path: Path) -> None:
    """BB-L5-CO-019: --all falls back to categorized_dir when enriched_dir exists but empty."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)  # exists but empty

    record = _make_record(
        "00030",
        [
            _make_use(
                "u1",
                "Construct a new manufacturing plant.",
                source_text="We will construct a new manufacturing plant.",
            ),
        ],
    )
    (cat_dir / "00030.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((enr_dir / "00030.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_all_mode_stdout_reports_processed_tickers(tmp_path: Path) -> None:
    """BB-L5-CO-020: --all prints a [capex_opex] line per processed ticker."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for ticker in ("00040", "00041"):
        record = _make_record(
            ticker,
            [
                _make_use(
                    "u1", "Build office buildings.", source_text="We will build office buildings."
                )
            ],
        )
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_capex_opex_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert "[capex_opex] 00040:" in result.stdout
    assert "[capex_opex] 00041:" in result.stdout


# -- --force flag ------------------------------------------------------------


def test_force_reprocesses_existing_enrichment(tmp_path: Path) -> None:
    """BB-L5-CO-021: --force re-processes even when enrichment already exists.

    When the input record already has an enrichments.capex_opex block with
    the current version, running without --force must preserve the existing
    block (idempotency).  Running with --force must re-process and overwrite.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    # Create a record whose uses clearly indicate capex (factory construction)
    # but with a pre-existing enrichments.capex_opex block containing a
    # deliberately wrong tag ("opex") at the current version.
    record = _make_record(
        "00050",
        [
            _make_use(
                "u1",
                "Build a factory with equipment.",
                source_text="We will build a factory and install machinery.",
            ),
        ],
    )
    # VERSION is 1 as per the public contract; discoverable from
    # any successful enrichment output.  No internal import needed.
    record["enrichments"]["capex_opex"] = {
        "version": 1,
        "by_use_id": {"u1": "opex"},  # intentionally wrong
    }
    infile = cat_dir / "00050.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    # Pre-save to enriched/ so the output file exists
    (enr_dir / "00050.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Run WITHOUT --force: existing enrichment (opex) must be preserved
    r1 = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    out1 = json.loads((enr_dir / "00050.json").read_text(encoding="utf-8"))
    assert out1["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "opex", (
        "Without --force, pre-existing (wrong) enrichment should be preserved"
    )

    # Run WITH --force: enrichment must be recalculated from uses
    r2 = _run_capex_opex_cli(str(infile), "--force", pythonpath_prefix=prefix)
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    out2 = json.loads((enr_dir / "00050.json").read_text(encoding="utf-8"))
    assert out2["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex", (
        "--force must re-run classifier and correct the wrong 'opex' tag"
    )


# -- Idempotency -------------------------------------------------------------


def test_single_file_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-CO-022: Running the same input twice produces identical enriched output."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00060",
        [
            _make_use(
                "u1",
                "Purchase R&D equipment and laboratory facilities.",
                category_raw="R&D equipment",
                source_text="To purchase R&D equipment, servers, and lab equipment.",
            ),
        ],
    )
    infile = cat_dir / "00060.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    r1 = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    r2 = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second run produced different output"


def test_all_mode_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-CO-023: --all is idempotent: same input yields same output on re-run."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00070",
        [
            _make_use(
                "u1",
                "Construct new offices and data centers.",
                source_text="We will construct new offices and data centers.",
            ),
        ],
    )
    (cat_dir / "00070.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    _run_capex_opex_cli("--all", pythonpath_prefix=prefix)
    out1 = (data_dir / "enriched" / "00070.json").read_text(encoding="utf-8")

    _run_capex_opex_cli("--all", pythonpath_prefix=prefix)
    out2 = (data_dir / "enriched" / "00070.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second --all run produced different output"


# -- Edge cases --------------------------------------------------------------


def test_empty_uses_list_handled_gracefully(tmp_path: Path) -> None:
    """BB-L5-CO-024: Record with empty uses list produces valid empty enrichment."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00080", [])
    infile = cat_dir / "00080.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00080.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["version"] >= 1
    assert block["by_use_id"] == {}


def test_ticker_derived_from_filename_if_missing_in_record(tmp_path: Path) -> None:
    """BB-L5-CO-025: If hk_ticker is absent, output filename is derived from input stem."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record: dict[str, object] = {
        "company_name_en": "No Ticker Corp",
        "schema_version": "2.0",
        "uses": [
            _make_use(
                "u1",
                "Build factory equipment.",
                source_text="We will build a factory with equipment.",
            )
        ],
        "enrichments": {},
    }
    infile = cat_dir / "00090.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Output should be at enriched/00090.json since stem is "00090"
    out_file = data_dir / "enriched" / "00090.json"
    assert out_file.exists(), f"Expected output at {out_file}"
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_cli_prints_capex_opex_count_to_stdout(tmp_path: Path) -> None:
    """BB-L5-CO-026: Single-file mode prints '[capex_opex] <ticker>: N uses tagged'."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00100",
        [
            _make_use("u1", "Build factory."),
            _make_use("u2", "Working capital."),
            _make_use("u3", "Repay loans."),
        ],
    )
    infile = cat_dir / "00100.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "[capex_opex] 00100: 3 uses tagged" in result.stdout


def test_single_file_use_id_names_match_input(tmp_path: Path) -> None:
    """BB-L5-CO-027: The by_use_id keys match the use_id values from the input."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00110",
        [
            _make_use(
                "procure_tech_001",
                "Purchase technology infrastructure.",
                category_raw="technology procurement",
                source_text="For purchasing server hardware and infrastructure.",
            ),
            _make_use(
                "work_cap_002",
                "Working capital for operations.",
                category_raw="working capital",
                source_text="For general working capital purposes.",
            ),
            _make_use(
                "debt_003",
                "Repay debt obligations.",
                category_raw="debt service",
                source_text="For repayment of outstanding debt obligations.",
            ),
        ],
    )
    infile = cat_dir / "00110.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00110.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert set(block["by_use_id"].keys()) == {"procure_tech_001", "work_cap_002", "debt_003"}
    assert block["by_use_id"]["procure_tech_001"] == "capex"
    assert block["by_use_id"]["work_cap_002"] == "opex"
    assert block["by_use_id"]["debt_003"] == "financial"


# -- Prior enrichment preservation (SR-002 / CR-001) -------------------------


def test_cli_preserves_prior_enrichments(tmp_path: Path) -> None:
    """BB-L5-CO-028: CLI single-file path preserves prior enrichment blocks.

    SR-002 / CR-001: When enriched data already exists for the ticker, the CLI
    must load from enriched_dir to preserve prior enrichment blocks (geo,
    country, etc.). This black-box test verifies the end-to-end behavior
    directly via subprocess.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    ticker = "00120"

    # Step 1: Write a raw categorized record (no enrichments).
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "u1",
                "description": "Build a factory",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory.",
            },
        ],
    }
    cat_file = cat_dir / f"{ticker}.json"
    cat_file.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")

    # Step 2: Pre-populate enriched_dir with prior enrichment (simulating
    # that another enrichment like geo has already run).
    enriched_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": raw_record["uses"],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"u1": "mainland"}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(json.dumps(enriched_record, ensure_ascii=False), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path. The CLI must detect
    # that enriched data already exists and load from enriched_dir instead.
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(input_file), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Step 4: Verify that prior enrichment (geo) was preserved.
    loaded = json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in loaded["enrichments"], (
        "SR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert loaded["enrichments"]["geo"]["by_use_id"]["u1"] == "mainland"
    assert "capex_opex" in loaded["enrichments"], "capex_opex enrichment must also be present"
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


# -- Mixed categories across uses in same record ----------------------------


def test_all_three_categories_one_record(tmp_path: Path) -> None:
    """BB-L5-CO-029: One record with capex, opex, and financial uses tags each correctly."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00130",
        [
            _make_use(
                "u_a",
                "Construct new factory building.",
                category_raw="capital expenditure",
                source_text="Construct a new factory.",
            ),
            _make_use(
                "u_b",
                "Staff salaries and payroll.",
                category_raw="operational expenditure",
                source_text="For payment of staff salaries and payroll.",
            ),
            _make_use(
                "u_c",
                "Refinancing of existing debt.",
                category_raw="financial",
                source_text="For refinancing of existing debt.",
            ),
        ],
    )
    infile = cat_dir / "00130.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00130.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["capex_opex"]
    assert block["by_use_id"]["u_a"] == "capex"
    assert block["by_use_id"]["u_b"] == "opex"
    assert block["by_use_id"]["u_c"] == "financial"


# -- Additional morphological edge cases -------------------------------------


def test_single_file_installations_plural_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-030: 'installations' (plural of installation) classifies as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00140",
        [
            _make_use(
                "u1",
                "New installations at our production sites.",
                category_raw="asset program",
                source_text="For new installations at our production sites.",
            ),
        ],
    )
    infile = cat_dir / "00140.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00140.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_constructions_plural_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-031: 'constructions' (plural) classifies as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00150",
        [
            _make_use(
                "u1",
                "Campus constructions project.",
                category_raw="capital program",
                source_text="The plan covers campus constructions.",
            ),
        ],
    )
    infile = cat_dir / "00150.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00150.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_matured_past_is_financial(tmp_path: Path) -> None:
    """BB-L5-CO-032: 'matured' (past tense) classifies as financial."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00160",
        [
            _make_use(
                "u1",
                "Matured obligations require settlement.",
                category_raw="debt service",
                source_text="The matured obligations require settlement.",
            ),
        ],
    )
    infile = cat_dir / "00160.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00160.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "financial"


def test_single_file_rents_plural_is_opex(tmp_path: Path) -> None:
    """BB-L5-CO-033: 'rents' (simple plural) classifies as opex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00170",
        [
            _make_use(
                "u1",
                "Property rents for retail spaces.",
                category_raw="operational costs",
                source_text="The firm pays rents for several retail properties.",
            ),
        ],
    )
    infile = cat_dir / "00170.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00170.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "opex"


def test_single_file_fit_outs_plural_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-034: 'fit-outs' (hyphenated plural) classifies as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00180",
        [
            _make_use(
                "u1",
                "Completion of retail fit-outs.",
                category_raw="interior works",
                source_text="For the completion of retail fit-outs across all stores.",
            ),
        ],
    )
    infile = cat_dir / "00180.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00180.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_new_stores_plural_is_capex(tmp_path: Path) -> None:
    """BB-L5-CO-035: 'new stores' (plural) classifies as capex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00190",
        [
            _make_use(
                "u1",
                "Open new stores across the market.",
                category_raw="growth plan",
                source_text="To open new stores across the region.",
            ),
        ],
    )
    infile = cat_dir / "00190.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00190.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "capex"


def test_single_file_sales_teams_plural_is_opex(tmp_path: Path) -> None:
    """BB-L5-CO-036: 'sales teams' (plural) classifies as opex."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00200",
        [
            _make_use(
                "u1",
                "Organize new sales teams.",
                category_raw="operations plan",
                source_text="To organize new sales teams for product distribution.",
            ),
        ],
    )
    infile = cat_dir / "00200.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_capex_opex_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00200.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["capex_opex"]["by_use_id"]["u1"] == "opex"
