"""Black-box tests for L5 timeline enrichment CLI (Task 013).

These tests invoke ``python -m hk_ipo.enrichments.timeline`` via subprocess and
verify behaviour through exit codes, stdout/stderr, and filesystem artefacts.
They do NOT import hk_ipo internals directly.

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

    # Copy only the files necessary for the timeline enrichment CLI.
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")

    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "timeline.py", enrich_dst / "timeline.py")

    # Write config with DATA_DIR redirected into tmp_path.
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def _run_timeline_cli(
    *args: str,
    pythonpath_prefix: str,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.enrichments.timeline`` via subprocess."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.timeline", *args],
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


# -- Single-file mode: classification categories ------------------------------


def test_single_file_short_term_0_12m(tmp_path: Path) -> None:
    """BB-L5-T-001: Text with '12 months' classifies as 0-12m via full CLI pipeline."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00101",
        [
            _make_use(
                "u1",
                "We expect to complete within 12 months from listing.",
                source_text="Expected completion within 12 months.",
            ),
        ],
    )
    infile = cat_dir / "00101.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out_file = data_dir / "enriched" / "00101.json"
    assert out_file.exists(), (
        f"Missing {out_file}; enriched dir has: "
        f"{[f.name for f in (data_dir / 'enriched').glob('*')]}"
    )
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    block = loaded["enrichments"]["timeline"]
    assert block["version"] == 1
    assert block["by_use_id"]["u1"] == "0-12m"


def test_single_file_medium_term_12_24m(tmp_path: Path) -> None:
    """BB-L5-T-002: Text with '18 months' classifies as 12-24m via full CLI pipeline."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00102",
        [
            _make_use(
                "u1",
                "Deployment expected over the next 18 months.",
                source_text="Over the next 18 to 24 months.",
            ),
        ],
    )
    infile = cat_dir / "00102.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00102.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_single_file_long_term_24_36m(tmp_path: Path) -> None:
    """BB-L5-T-003: Text with '3 years' classifies as 24-36m via full CLI pipeline."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00103",
        [
            _make_use(
                "u1",
                "Three-year deployment plan for the new facility.",
                source_text="Enterprise expansion over 3 years.",
            ),
        ],
    )
    infile = cat_dir / "00103.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00103.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


def test_single_file_very_long_36m_plus(tmp_path: Path) -> None:
    """BB-L5-T-004: Text with '5 years' classifies as 36m+ via full CLI pipeline."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00104",
        [
            _make_use(
                "u1",
                "Long-term investment to be deployed over 5 years.",
                source_text="Deployment over the next 5 years.",
            ),
        ],
    )
    infile = cat_dir / "00104.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00104.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_single_file_unspecified_no_timeline(tmp_path: Path) -> None:
    """BB-L5-T-005: Text with no timeline mention classifies as 'unspecified'."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00105",
        [
            _make_use("u1", "General corporate purposes.", source_text=""),
        ],
    )
    infile = cat_dir / "00105.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00105.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "unspecified"


# -- Qualitative phrase matching ----------------------------------------------


def test_single_file_qualitative_near_term(tmp_path: Path) -> None:
    """BB-L5-T-006: 'near-term' (qualitative) classifies as 0-12m when no numeric mention."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00106",
        [
            _make_use(
                "u1",
                "Near-term operational improvements are planned.",
                source_text="Near-term improvements.",
            ),
        ],
    )
    infile = cat_dir / "00106.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00106.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


def test_single_file_qualitative_medium_term(tmp_path: Path) -> None:
    """BB-L5-T-007: 'medium-term' (qualitative) classifies as 12-24m when no numeric mention."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00107",
        [
            _make_use(
                "u1",
                "Medium-term technology upgrades planned.",
                source_text="Medium-term plans for infrastructure.",
            ),
        ],
    )
    infile = cat_dir / "00107.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00107.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_single_file_qualitative_long_term(tmp_path: Path) -> None:
    """BB-L5-T-008: 'long-term' (qualitative) classifies as 24-36m when no numeric mention."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00108",
        [
            _make_use(
                "u1",
                "Long-term strategic investments in R&D.",
                source_text="Long-term R&D investment strategy.",
            ),
        ],
    )
    infile = cat_dir / "00108.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00108.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


# -- Numeric priority over qualitative ----------------------------------------


def test_numeric_priority_over_qualitative(tmp_path: Path) -> None:
    """BB-L5-T-009: Numeric '5 years' wins over qualitative 'long-term' (36m+ not 24-36m)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00109",
        [
            _make_use(
                "u1",
                "Long-term investment to be deployed over 5 years.",
                source_text="5-year long-term strategic plan.",
            ),
        ],
    )
    infile = cat_dir / "00109.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00109.json").read_text(encoding="utf-8"))
    # "5 years" is numeric very-long (36m+); "long-term" is qualitative long (24-36m).
    # Numeric must take priority -> 36m+
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_shorter_numeric_with_qualitative_mismatch(tmp_path: Path) -> None:
    """BB-L5-T-010: Numeric '12 months' with qualitative 'medium-term' -> 0-12m (numeric wins)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00110",
        [
            _make_use(
                "u1",
                "Medium-term plan to complete within 12 months.",
                source_text="12-month medium-term deployment.",
            ),
        ],
    )
    infile = cat_dir / "00110.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00110.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Boundary cases in numeric ranges -----------------------------------------


def test_boundary_24_months_is_medium_term(tmp_path: Path) -> None:
    """BB-L5-T-011: '24 months' is medium-term (12-24m), not long-term."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00111",
        [
            _make_use(
                "u1", "Deployment will take 24 months.", source_text="24-month deployment timeline."
            ),
        ],
    )
    infile = cat_dir / "00111.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00111.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_boundary_25_months_is_long_term(tmp_path: Path) -> None:
    """BB-L5-T-012: '25 months' is long-term (24-36m), not medium-term."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00112",
        [
            _make_use(
                "u1", "Deployment will take 25 months.", source_text="25-month deployment timeline."
            ),
        ],
    )
    infile = cat_dir / "00112.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00112.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


def test_boundary_36_months_is_long_term(tmp_path: Path) -> None:
    """BB-L5-T-013: '36 months' is long-term (24-36m), not very-long."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00113",
        [
            _make_use(
                "u1", "Deployment will take 36 months.", source_text="36-month deployment timeline."
            ),
        ],
    )
    infile = cat_dir / "00113.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00113.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


def test_boundary_37_months_is_very_long(tmp_path: Path) -> None:
    """BB-L5-T-014: '37 months' is very-long (36m+), not long-term."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00114",
        [
            _make_use(
                "u1", "Deployment will take 37 months.", source_text="37-month deployment timeline."
            ),
        ],
    )
    infile = cat_dir / "00114.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00114.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


# -- Short-term sub-variants --------------------------------------------------


def test_within_a_year_is_short_term(tmp_path: Path) -> None:
    """BB-L5-T-015: 'within a year' classifies as 0-12m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00115",
        [
            _make_use(
                "u1",
                "We plan to complete this within a year.",
                source_text="Completion within a year.",
            ),
        ],
    )
    infile = cat_dir / "00115.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00115.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


def test_six_months_is_short_term(tmp_path: Path) -> None:
    """BB-L5-T-016: '6 months' classifies as 0-12m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00116",
        [
            _make_use("u1", "Quick deployment over 6 months.", source_text="6-month deployment."),
        ],
    )
    infile = cat_dir / "00116.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00116.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


def test_immediate_is_short_term(tmp_path: Path) -> None:
    """BB-L5-T-017: 'immediate' (qualitative) classifies as 0-12m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00117",
        [
            _make_use(
                "u1",
                "Immediate needs for working capital.",
                source_text="Immediate working capital requirements.",
            ),
        ],
    )
    infile = cat_dir / "00117.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00117.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Case insensitivity -------------------------------------------------------


def test_case_insensitive_matching(tmp_path: Path) -> None:
    """BB-L5-T-018: Timeline keywords are matched case-insensitively."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00118",
        [
            _make_use(
                "u1",
                "NEAR-TERM priorities for expansion.",
                source_text="SHORT-TERM cash deployment.",
            ),
            _make_use(
                "u2", "MEDIUM-TERM technology roadmap.", source_text="Medium-Term milestones."
            ),
        ],
    )
    infile = cat_dir / "00118.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00118.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["timeline"]
    assert block["by_use_id"]["u1"] == "0-12m"
    assert block["by_use_id"]["u2"] == "12-24m"


# -- Multiple uses per record -------------------------------------------------


def test_multiple_uses_each_classified(tmp_path: Path) -> None:
    """BB-L5-T-019: Multiple use items are each enriched independently."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00119",
        [
            _make_use("u1", "Immediate working capital needs.", percentage=30.0),
            _make_use("u2", "Medium-term facility upgrade.", percentage=40.0),
            _make_use("u3", "Deployment over 5 years.", percentage=30.0),
        ],
    )
    infile = cat_dir / "00119.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00119.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["timeline"]
    assert block["by_use_id"]["u1"] == "0-12m"
    assert block["by_use_id"]["u2"] == "12-24m"
    assert block["by_use_id"]["u3"] == "36m+"
    assert len(block["by_use_id"]) == 3


# -- Stdout reporting ---------------------------------------------------------


def test_single_file_stdout_reports_uses_tagged(tmp_path: Path) -> None:
    """BB-L5-T-020: Single-file mode prints '[timeline] <ticker>: N uses tagged' to stdout."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00120",
        [
            _make_use("u1", "Complete within 12 months.", source_text="12-month plan."),
            _make_use("u2", "General purposes.", source_text=""),
        ],
    )
    infile = cat_dir / "00120.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "[timeline] 00120: 2 uses tagged" in result.stdout


# -- Idempotency --------------------------------------------------------------


def test_single_file_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-T-021: Running the same input twice produces identical enriched JSON output."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00121",
        [
            _make_use("u1", "Deployment over 18 months.", source_text="18-month plan."),
        ],
    )
    infile = cat_dir / "00121.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    r1 = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = (data_dir / "enriched" / "00121.json").read_text(encoding="utf-8")

    r2 = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = (data_dir / "enriched" / "00121.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second run produced different output"


# -- --all mode ---------------------------------------------------------------


def test_all_mode_processes_all_files(tmp_path: Path) -> None:
    """BB-L5-T-022: --all processes every JSON file in categorized_dir."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for ticker, text in [
        ("00200", "Complete within 6 months."),
        ("00201", "Deployment over 24 months."),
        ("00202", "Three years expansion plan."),
    ]:
        record = _make_record(ticker, [_make_use("u1", text)])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_timeline_cli("--all", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"

    out0 = json.loads((data_dir / "enriched" / "00200.json").read_text(encoding="utf-8"))
    out1 = json.loads((data_dir / "enriched" / "00201.json").read_text(encoding="utf-8"))
    out2 = json.loads((data_dir / "enriched" / "00202.json").read_text(encoding="utf-8"))

    assert out0["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"
    assert out1["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"
    assert out2["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


def test_all_mode_falls_back_when_enriched_empty(tmp_path: Path) -> None:
    """BB-L5-T-023: --all falls back to categorized_dir when enriched_dir exists but empty."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)  # exists but empty

    record = _make_record("00210", [_make_use("u1", "Complete within 12 months.")])
    (cat_dir / "00210.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli("--all", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((enr_dir / "00210.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


def test_all_mode_stdout_reports_processed_tickers(tmp_path: Path) -> None:
    """BB-L5-T-024: --all prints a [timeline] line per processed ticker."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for ticker in ("00220", "00221"):
        record = _make_record(ticker, [_make_use("u1", "Expand within 12 months.")])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_timeline_cli("--all", pythonpath_prefix=prefix)

    assert result.returncode == 0
    assert "[timeline] 00220:" in result.stdout
    assert "[timeline] 00221:" in result.stdout


def test_all_mode_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-T-025: --all is idempotent: same input yields same output on re-run."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00230", [_make_use("u1", "Deploy over 3 years.")])
    (cat_dir / "00230.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    _run_timeline_cli("--all", pythonpath_prefix=prefix)
    out1 = (data_dir / "enriched" / "00230.json").read_text(encoding="utf-8")

    _run_timeline_cli("--all", pythonpath_prefix=prefix)
    out2 = (data_dir / "enriched" / "00230.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second --all run produced different output"


# -- --force flag -------------------------------------------------------------


def test_force_reprocesses_existing_enrichment(tmp_path: Path) -> None:
    """BB-L5-T-026: --force re-processes even when enrichment already exists.

    When the input record already has an enrichments.timeline block (e.g. from a
    previous run), running without --force must preserve the existing block
    (early return, no save). Running with --force must re-process and overwrite.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    # Create a record whose uses mention "5 years" (should be 36m+),
    # but with a pre-existing enrichments.timeline block containing a wrong value.
    record = _make_record("00240", [_make_use("u1", "Deploy over 5 years.")])
    record["enrichments"]["timeline"] = {
        "version": 1,
        "by_use_id": {"u1": "unspecified"},
    }
    infile = cat_dir / "00240.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    (enr_dir / "00240.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Run WITHOUT --force: existing enrichment (unspecified) must be preserved.
    r1 = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = json.loads((enr_dir / "00240.json").read_text(encoding="utf-8"))
    assert out1["enrichments"]["timeline"]["by_use_id"]["u1"] == "unspecified", (
        "Without --force, pre-existing enrichment should be preserved"
    )
    assert "36m+" not in out1["enrichments"]["timeline"]["by_use_id"]["u1"]

    # Run WITH --force: enrichment must be recalculated from uses.
    r2 = _run_timeline_cli(str(infile), "--force", pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = json.loads((enr_dir / "00240.json").read_text(encoding="utf-8"))
    assert out2["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"
    assert "unspecified" not in out2["enrichments"]["timeline"]["by_use_id"]["u1"]


# -- Error paths --------------------------------------------------------------


def test_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-T-027: Non-existent input file causes non-zero exit and stderr message."""
    prefix = _make_config_override(tmp_path)

    bad_path = tmp_path / "data" / "nonexistent.json"
    result = _run_timeline_cli(str(bad_path), pythonpath_prefix=prefix)

    assert result.returncode != 0, (
        f"Expected non-zero exit for missing file, got {result.returncode}"
    )
    assert "ERROR" in result.stderr or "Not found" in result.stderr, (
        f"stderr: {result.stderr[:300]}"
    )


def test_no_args_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-T-028: Calling with neither --all nor input path exits non-zero."""
    prefix = _make_config_override(tmp_path)
    result = _run_timeline_cli(pythonpath_prefix=prefix)

    assert result.returncode != 0, f"Expected non-zero exit with no args, got {result.returncode}"


# -- Edge cases ---------------------------------------------------------------


def test_empty_uses_list_handled_gracefully(tmp_path: Path) -> None:
    """BB-L5-T-029: Record with empty uses list produces valid empty enrichment."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00290", [])
    infile = cat_dir / "00290.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00290.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["timeline"]
    assert block["version"] == 1
    assert block["by_use_id"] == {}


def test_ticker_derived_from_filename_if_missing_in_record(tmp_path: Path) -> None:
    """BB-L5-T-030: If hk_ticker is absent, output filename is derived from input stem."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = {
        "company_name_en": "No Ticker Corp",
        "schema_version": "2.0",
        "uses": [_make_use("u1", "Deploy within 12 months.")],
        "enrichments": {},
    }
    infile = cat_dir / "00300.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out_file = data_dir / "enriched" / "00300.json"
    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Extended horizon phrases -------------------------------------------------


def test_extended_horizon_is_very_long(tmp_path: Path) -> None:
    """BB-L5-T-031: 'extended horizon' (qualitative) classifies as 36m+."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00310",
        [
            _make_use(
                "u1",
                "Extended horizon investments for future growth.",
                source_text="Extended timeline for strategic deployment.",
            ),
        ],
    )
    infile = cat_dir / "00310.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00310.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_two_years_is_medium_term(tmp_path: Path) -> None:
    """BB-L5-T-032: '2 years' or 'two years' classifies as 12-24m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00320",
        [
            _make_use(
                "u1",
                "Two-year technology refresh cycle.",
                source_text="Technology refresh over 2 years.",
            ),
        ],
    )
    infile = cat_dir / "00320.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00320.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_ten_years_is_very_long(tmp_path: Path) -> None:
    """BB-L5-T-033: '10 years' (two-digit) classifies as 36m+."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00330",
        [
            _make_use(
                "u1",
                "We plan a 10 year infrastructure programme.",
                source_text="10 year long-term infrastructure plan.",
            ),
        ],
    )
    infile = cat_dir / "00330.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00330.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_four_years_is_very_long(tmp_path: Path) -> None:
    """BB-L5-T-034: '4 years' classifies as 36m+ (boundary case)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00340",
        [
            _make_use(
                "u1", "Deployment over four years.", source_text="4-year deployment programme."
            ),
        ],
    )
    infile = cat_dir / "00340.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00340.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_13_months_is_medium_term(tmp_path: Path) -> None:
    """BB-L5-T-035: '13 months' is medium-term (exceeds 12-month short-term boundary)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00350",
        [
            _make_use("u1", "Deployment over 13 months.", source_text="13-month deployment."),
        ],
    )
    infile = cat_dir / "00350.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00350.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_three_years_is_long_term(tmp_path: Path) -> None:
    """BB-L5-T-036: 'three years' classifies as 24-36m (boundary: not very-long)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00360",
        [
            _make_use(
                "u1",
                "Three years for full deployment.",
                source_text="Three-year deployment schedule.",
            ),
        ],
    )
    infile = cat_dir / "00360.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00360.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


def test_source_text_only_used_for_classification(tmp_path: Path) -> None:
    """BB-L5-T-037: Timeline found only in source_text still classifies correctly."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00370",
        [
            _make_use(
                "u1", "General business expansion.", source_text="Expected to complete in 6 months."
            ),
        ],
    )
    infile = cat_dir / "00370.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00370.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


def test_very_long_qualitative_only(tmp_path: Path) -> None:
    """BB-L5-T-038: 'very long term' (qualitative, no numeric) -> 36m+."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00380",
        [
            _make_use(
                "u1",
                "Very long term strategic vision for the company.",
                source_text="Very long term positioning.",
            ),
        ],
    )
    infile = cat_dir / "00380.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00380.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_mid_term_is_medium_term(tmp_path: Path) -> None:
    """BB-L5-T-039: 'mid-term' (qualitative) classifies as 12-24m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00390",
        [
            _make_use(
                "u1",
                "Mid-term capital expenditure plan.",
                source_text="Mid-term capex requirements.",
            ),
        ],
    )
    infile = cat_dir / "00390.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00390.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_first_year_is_short_term(tmp_path: Path) -> None:
    """BB-L5-T-040: 'first year' classifies as 0-12m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00400",
        [
            _make_use(
                "u1",
                "First year deployment of the new system.",
                source_text="First year operational rollout.",
            ),
        ],
    )
    infile = cat_dir / "00400.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00400.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Longest numeric horizon wins (multiple numerics in same text) ------------


def test_longest_numeric_horizon_wins_same_use(tmp_path: Path) -> None:
    """BB-L5-T-041: '6 months and 3 years' in same use -> 24-36m (longest numeric wins)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00410",
        [
            _make_use(
                "u1",
                "Phase 1 in 6 months, then phase 2 over 3 years.",
                source_text="6-month initial, 3-year full deployment.",
            ),
        ],
    )
    infile = cat_dir / "00410.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00410.json").read_text(encoding="utf-8"))
    # 3 years (24-36m) is longer than 6 months (0-12m); longest wins
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"


def test_numeric_wins_over_qualitative_when_both_present(tmp_path: Path) -> None:
    """BB-L5-T-042: Numeric '18 months' wins over qualitative 'long-term' in same text."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00420",
        [
            _make_use(
                "u1",
                "Long-term strategic initiative to deploy over 18 months.",
                source_text="18-month deployment under long-term strategy.",
            ),
        ],
    )
    infile = cat_dir / "00420.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00420.json").read_text(encoding="utf-8"))
    # 18 months is numeric medium (12-24m) and must take priority over qualitative long-term
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "12-24m"


def test_numeric_5_years_wins_over_3_years_in_same_text(tmp_path: Path) -> None:
    """BB-L5-T-043: '3 years and 5 years' in same use -> 36m+ (5 years is longest)."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00430",
        [
            _make_use(
                "u1",
                "Phase one over 3 years, full deployment over 5 years.",
                source_text="3-year phase, 5-year programme.",
            ),
        ],
    )
    infile = cat_dir / "00430.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00430.json").read_text(encoding="utf-8"))
    # 5 years (36m+) checked before 3 years (24-36m); longest wins
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


# -- Additional numeric/qualitative pattern variants --------------------------


def test_within_1_year_digit_form(tmp_path: Path) -> None:
    """BB-L5-T-044: 'within 1 year' (digit form) classifies as 0-12m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00440",
        [
            _make_use(
                "u1",
                "Expected to complete within 1 year from listing.",
                source_text="Within 1 year of listing date.",
            ),
        ],
    )
    infile = cat_dir / "00440.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00440.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


def test_extended_period_is_very_long(tmp_path: Path) -> None:
    """BB-L5-T-045: 'extended period' (qualitative) classifies as 36m+."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00450",
        [
            _make_use(
                "u1",
                "Extended period of investment for long-term growth.",
                source_text="Extended period capital allocation strategy.",
            ),
        ],
    )
    infile = cat_dir / "00450.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00450.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_extended_timeline_is_very_long(tmp_path: Path) -> None:
    """BB-L5-T-046: 'extended timeline' (standalone qualitative) classifies as 36m+."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00460",
        [
            _make_use("u1", "Extended timeline for strategic deployment.", source_text=""),
        ],
    )
    infile = cat_dir / "00460.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00460.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


# -- Hyphenated qualitative forms through CLI (CR-007) ------------------------


def test_hyphenated_very_long_qualitative_cli(tmp_path: Path) -> None:
    """BB-L5-T-047: 'very-long' (hyphenated qualitative) classifies as 36m+ through CLI."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00470",
        [
            _make_use("u1", "Very-long term strategic investment horizon.", source_text=""),
        ],
    )
    infile = cat_dir / "00470.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00470.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


def test_hyphenated_extended_horizon_cli(tmp_path: Path) -> None:
    """BB-L5-T-048: 'extended-horizon' (hyphenated qualitative) classifies as 36m+ through CLI."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00480",
        [
            _make_use("u1", "Extended-horizon infrastructure deployment plan.", source_text=""),
        ],
    )
    infile = cat_dir / "00480.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00480.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


# -- Qualitative "short term" with space separator ----------------------------


def test_short_term_space_separated(tmp_path: Path) -> None:
    """BB-L5-T-049: 'short term' (space-separated, not hyphenated) classifies as 0-12m."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00490",
        [
            _make_use(
                "u1",
                "Short term working capital requirements.",
                source_text="Short term cash needs.",
            ),
        ],
    )
    infile = cat_dir / "00490.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00490.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Preservation of other enrichment dimensions ------------------------------


def test_preserves_existing_enrichment_dimensions(tmp_path: Path) -> None:
    """BB-L5-T-050: Timeline enrichment must not clobber existing country/industry enrichments."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00500",
        [
            _make_use(
                "u1",
                "Expand into Singapore within 12 months.",
                source_text="12-month Singapore expansion.",
            ),
        ],
    )
    # Pre-populate non-timeline enrichments as if other L5 tools ran first
    record["enrichments"] = {
        "country": {
            "version": 1,
            "countries": ["SG"],
            "by_use_id": {"u1": ["SG"]},
        },
        "industry": {
            "version": 1,
            "industries": ["Technology"],
            "by_use_id": {"u1": ["Technology"]},
        },
    }
    infile = cat_dir / "00500.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Run with --force to ensure timeline writes even though enrichment already exists
    result = _run_timeline_cli(str(infile), "--force", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00500.json").read_text(encoding="utf-8"))

    # Timeline enrichment must be present
    assert "timeline" in loaded["enrichments"]
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"

    # Pre-existing enrichments must be preserved unmodified
    assert "country" in loaded["enrichments"]
    assert loaded["enrichments"]["country"]["countries"] == ["SG"]
    assert loaded["enrichments"]["country"]["by_use_id"] == {"u1": ["SG"]}

    assert "industry" in loaded["enrichments"]
    assert loaded["enrichments"]["industry"]["industries"] == ["Technology"]
    assert loaded["enrichments"]["industry"]["by_use_id"] == {"u1": ["Technology"]}


# -- Spelled-out number words through CLI -------------------------------------


def test_five_years_spelled_out_cli(tmp_path: Path) -> None:
    """BB-L5-T-051: 'five years' (spelled out) classifies as 36m+ through CLI."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00510",
        [
            _make_use(
                "u1",
                "Five years expansion programme for new markets.",
                source_text="Five years market development plan.",
            ),
        ],
    )
    infile = cat_dir / "00510.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00510.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "36m+"


# -- Abbreviation pattern -----------------------------------------------------


def test_12_mo_abbreviation_is_short_term(tmp_path: Path) -> None:
    """BB-L5-T-052: '12 mo' abbreviation classifies as 0-12m through CLI."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00520",
        [
            _make_use(
                "u1",
                "Complete deployment within 12 mo from commencement.",
                source_text="12 mo deployment timeline.",
            ),
        ],
    )
    infile = cat_dir / "00520.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00520.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Negative scenarios -------------------------------------------------------


def test_malformed_json_input_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-T-053: Malformed JSON input causes non-zero exit."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    bad_file = cat_dir / "00530.json"
    bad_file.write_text("{this is not valid json at all", encoding="utf-8")

    result = _run_timeline_cli(str(bad_file), pythonpath_prefix=prefix)

    assert result.returncode != 0, (
        f"Expected non-zero exit for malformed JSON, got {result.returncode}"
    )


def test_record_without_enrichments_key_handled(tmp_path: Path) -> None:
    """BB-L5-T-054: Record lacking 'enrichments' key is handled gracefully."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    # Build a record with NO enrichments key at all (not even empty dict)
    record: dict[str, object] = {
        "hk_ticker": "00540",
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "u1",
                "description": "Deploy within 12 months.",
                "category_raw": "expansion",
                "percentage": 100.0,
                "source_text": "12-month plan.",
            },
        ],
    }
    infile = cat_dir / "00540.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00540.json").read_text(encoding="utf-8"))
    assert "enrichments" in loaded
    assert "timeline" in loaded["enrichments"]
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"


# -- Whitespace variation -----------------------------------------------------


def test_multiple_spaces_between_number_and_unit(tmp_path: Path) -> None:
    """BB-L5-T-055: Multiple spaces between number and month/year unit still matches."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00550",
        [
            _make_use("u1", "Deployment over 36    months.", source_text="36   months timeline."),
            _make_use("u2", "Expansion over 5     years.", source_text="5   years programme."),
        ],
    )
    infile = cat_dir / "00550.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_timeline_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00550.json").read_text(encoding="utf-8"))
    # 36 months -> long term (24-36m), 5 years -> very long (36m+)
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "24-36m"
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u2"] == "36m+"


# -- Prior enrichment preservation (SR-002 / CR-001) -------------------------


def test_cli_preserves_prior_enrichments(tmp_path: Path) -> None:
    """BB-L5-T-056: CLI single-file path preserves prior enrichment blocks.

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

    ticker = "00560"

    # Step 1: Write a raw categorized record (no enrichments).
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "u1",
                "description": "Complete the facility within 12 months.",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We expect to complete within 12 months from listing.",
            },
        ],
    }
    cat_file = cat_dir / f"{ticker}.json"
    cat_file.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")

    # Step 2: Pre-populate enriched_dir with prior enrichment (simulating that
    # geo has already run).
    enriched_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": raw_record["uses"],
        "enrichments": {
            "geo": {"version": 1, "by_use_id": {"u1": "domestic_hk"}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(json.dumps(enriched_record, ensure_ascii=False), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path. The CLI must detect that
    # enriched data already exists and load from enriched_dir instead.
    result = _run_timeline_cli(str(cat_file), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Step 4: Verify that prior enrichment (geo) was preserved.
    loaded = json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in loaded["enrichments"], (
        "SR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert loaded["enrichments"]["geo"]["by_use_id"]["u1"] == "domestic_hk"
    assert "timeline" in loaded["enrichments"], "timeline enrichment must also be present"
    assert loaded["enrichments"]["timeline"]["by_use_id"]["u1"] == "0-12m"
