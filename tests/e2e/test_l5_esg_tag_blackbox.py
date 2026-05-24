"""Black-box tests for L5 esg_tag enrichment CLI (Task 015).

These tests invoke ``python -m hk_ipo.enrichments.esg_tag`` via subprocess and
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

    # Copy only the files necessary for the esg_tag enrichment CLI.
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")

    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "esg_tag.py", enrich_dst / "esg_tag.py")

    # Write config with DATA_DIR redirected into tmp_path.
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def _run_esg_tag_cli(
    *args: str,
    pythonpath_prefix: str,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.enrichments.esg_tag`` via subprocess."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.esg_tag", *args],
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


# -- Single-file mode: green tag ----------------------------------------------


def test_single_file_green_renewable_energy(tmp_path: Path) -> None:
    """BB-L5-ESG-001: Single-file mode tags renewable energy as green."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00001",
        [
            _make_use(
                "u1",
                "Invest in solar panel manufacturing and wind energy projects.",
                category_raw="renewable energy investment",
                source_text="We will invest in solar panel and wind energy.",
            ),
        ],
    )
    infile = cat_dir / "00001.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out_file = data_dir / "enriched" / "00001.json"
    assert out_file.exists(), (
        f"Missing {out_file}; enriched dir has: "
        f"{[f.name for f in (data_dir / 'enriched').glob('*')]}"
    )
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert block["version"] == 1
    assert "green" in block["by_use_id"]["u1"]
    assert block["any_esg"] is True


# -- Single-file mode: social tag ---------------------------------------------


def test_single_file_social_healthcare(tmp_path: Path) -> None:
    """BB-L5-ESG-002: Single-file mode tags healthcare as social."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00002",
        [
            _make_use(
                "u1",
                "Build affordable healthcare clinics in rural areas.",
                category_raw="healthcare expansion",
                source_text="Expanding affordable healthcare access.",
            ),
        ],
    )
    infile = cat_dir / "00002.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00002.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert "social" in block["by_use_id"]["u1"]


# -- Single-file mode: governance tag -----------------------------------------


def test_single_file_governance_compliance(tmp_path: Path) -> None:
    """BB-L5-ESG-003: Single-file mode tags compliance as governance."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00003",
        [
            _make_use(
                "u1",
                "Implement company-wide compliance and risk management systems.",
                category_raw="compliance systems",
                source_text="Strengthening compliance and governance frameworks.",
            ),
        ],
    )
    infile = cat_dir / "00003.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00003.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert "governance" in block["by_use_id"]["u1"]


# -- Single-file mode: multiple tags ------------------------------------------


def test_single_file_multiple_tags(tmp_path: Path) -> None:
    """BB-L5-ESG-004: Single use can have multiple ESG tags simultaneously."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00004",
        [
            _make_use(
                "u1",
                "Green affordable housing project with governance oversight.",
                category_raw="sustainable affordable housing",
                source_text="Building green affordable housing with strong governance.",
            ),
        ],
    )
    infile = cat_dir / "00004.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00004.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert "green" in block["by_use_id"]["u1"]
    assert "social" in block["by_use_id"]["u1"]
    assert "governance" in block["by_use_id"]["u1"]
    assert block["any_esg"] is True


# -- Single-file mode: no tag -------------------------------------------------


def test_single_file_no_esg_tag(tmp_path: Path) -> None:
    """BB-L5-ESG-005: General corporate purposes receives no ESG tags."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00005",
        [
            _make_use(
                "u1",
                "General corporate purposes.",
                category_raw="general corporate purposes",
                source_text="For general corporate purposes.",
            ),
        ],
    )
    infile = cat_dir / "00005.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00005.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert block["by_use_id"]["u1"] == []
    assert block["any_esg"] is False


# -- Single-file mode: multiple uses per record -------------------------------


def test_single_file_multiple_uses_per_record(tmp_path: Path) -> None:
    """BB-L5-ESG-006: Multiple use items are each enriched independently."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00006",
        [
            _make_use(
                "u1",
                "Invest in solar energy projects.",
                category_raw="green investment",
                percentage=40.0,
            ),
            _make_use(
                "u2",
                "Build community healthcare clinics.",
                category_raw="social investment",
                percentage=30.0,
            ),
            _make_use(
                "u3", "General working capital.", category_raw="general corporate", percentage=30.0
            ),
        ],
    )
    infile = cat_dir / "00006.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00006.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert "green" in block["by_use_id"]["u1"]
    assert "social" in block["by_use_id"]["u2"]
    assert block["by_use_id"]["u3"] == []
    assert block["any_esg"] is True


# -- Non-existent / error paths -----------------------------------------------


def test_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-ESG-007: Non-existent input file causes non-zero exit and stderr message."""
    prefix = _make_config_override(tmp_path)

    bad_path = tmp_path / "data" / "nonexistent.json"
    result = _run_esg_tag_cli(str(bad_path), pythonpath_prefix=prefix)

    assert result.returncode != 0, (
        f"Expected non-zero exit for missing file, got {result.returncode}"
    )
    assert "ERROR" in result.stderr or "Not found" in result.stderr, (
        f"stderr: {result.stderr[:300]}"
    )


def test_no_args_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-ESG-008: Calling with neither --all nor input path exits non-zero."""
    prefix = _make_config_override(tmp_path)
    result = _run_esg_tag_cli(pythonpath_prefix=prefix)
    assert result.returncode != 0, f"Expected non-zero exit with no args, got {result.returncode}"


# -- --all mode ---------------------------------------------------------------


def test_all_mode_processes_all_files(tmp_path: Path) -> None:
    """BB-L5-ESG-009: --all processes every JSON in categorized_dir."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    test_cases = [
        ("00010", "Invest in solar energy and wind power."),
        ("00011", "Build affordable healthcare clinics for rural communities."),
        ("00012", "Strengthen corporate governance and compliance systems."),
    ]
    for i, (ticker, text) in enumerate(test_cases):
        record = _make_record(ticker, [_make_use(f"u{i + 1}", text)])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_esg_tag_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out10 = json.loads((data_dir / "enriched" / "00010.json").read_text(encoding="utf-8"))
    out11 = json.loads((data_dir / "enriched" / "00011.json").read_text(encoding="utf-8"))
    out12 = json.loads((data_dir / "enriched" / "00012.json").read_text(encoding="utf-8"))

    assert "green" in out10["enrichments"]["esg_tag"]["by_use_id"]["u1"]
    assert "social" in out11["enrichments"]["esg_tag"]["by_use_id"]["u2"]
    assert "governance" in out12["enrichments"]["esg_tag"]["by_use_id"]["u3"]


def test_all_mode_falls_back_when_enriched_empty(tmp_path: Path) -> None:
    """BB-L5-ESG-010: --all falls back to categorized_dir when enriched_dir exists but empty."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)  # exists but empty

    record = _make_record(
        "00020",
        [
            _make_use(
                "u1",
                "Invest in renewable energy and carbon-neutral infrastructure.",
                source_text="We will invest in clean energy and carbon-neutral solutions.",
            ),
        ],
    )
    (cat_dir / "00020.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((enr_dir / "00020.json").read_text(encoding="utf-8"))
    assert "green" in loaded["enrichments"]["esg_tag"]["by_use_id"]["u1"]


def test_all_mode_stdout_reports_processed_tickers(tmp_path: Path) -> None:
    """BB-L5-ESG-011: --all prints a [esg_tag] line per processed ticker."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for ticker in ("00030", "00031"):
        record = _make_record(
            ticker,
            [
                _make_use(
                    "u1", "Invest in solar energy.", source_text="We will invest in solar energy."
                )
            ],
        )
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_esg_tag_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert "[esg_tag] 00030:" in result.stdout
    assert "[esg_tag] 00031:" in result.stdout


# -- --force flag -------------------------------------------------------------


def test_force_reprocesses_existing_enrichment(tmp_path: Path) -> None:
    """BB-L5-ESG-012: --force re-processes even when enrichment already exists.

    When the input record already has an enrichments.esg_tag block with
    the current version, running without --force must preserve the existing
    block (idempotency).  Running with --force must re-process and overwrite.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    # Create a record whose uses clearly indicate green (solar energy)
    # but with a pre-existing enrichments.esg_tag block containing
    # deliberately wrong tags (empty) at the current version.
    record = _make_record(
        "00040",
        [
            _make_use(
                "u1",
                "Invest in solar panel manufacturing.",
                source_text="We will invest in solar panel manufacturing.",
            ),
        ],
    )
    # VERSION is 1 as per the public contract.
    record["enrichments"]["esg_tag"] = {
        "version": 1,
        "any_esg": False,
        "by_use_id": {"u1": []},  # intentionally wrong
    }
    infile = cat_dir / "00040.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    # Pre-save to enriched/ so the output file exists
    (enr_dir / "00040.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Run WITHOUT --force: existing enrichment (empty) must be preserved
    r1 = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    out1 = json.loads((enr_dir / "00040.json").read_text(encoding="utf-8"))
    assert out1["enrichments"]["esg_tag"]["by_use_id"]["u1"] == [], (
        "Without --force, pre-existing (wrong) enrichment should be preserved"
    )

    # Run WITH --force: enrichment must be recalculated from uses
    r2 = _run_esg_tag_cli(str(infile), "--force", pythonpath_prefix=prefix)
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    out2 = json.loads((enr_dir / "00040.json").read_text(encoding="utf-8"))
    assert "green" in out2["enrichments"]["esg_tag"]["by_use_id"]["u1"], (
        "--force must re-run classifier and add the correct 'green' tag"
    )


# -- Idempotency --------------------------------------------------------------


def test_single_file_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-ESG-013: Running the same input twice produces identical enriched output."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00050",
        [
            _make_use(
                "u1",
                "Invest in renewable energy and healthcare projects.",
                category_raw="ESG program",
                source_text="To invest in renewable energy and community healthcare.",
            ),
        ],
    )
    infile = cat_dir / "00050.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    r1 = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = (data_dir / "enriched" / "00050.json").read_text(encoding="utf-8")

    r2 = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = (data_dir / "enriched" / "00050.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second run produced different output"


def test_all_mode_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-ESG-014: --all is idempotent: same input yields same output on re-run."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00060",
        [
            _make_use(
                "u1",
                "Strengthen governance and compliance frameworks.",
                source_text="We will strengthen governance and compliance.",
            ),
        ],
    )
    (cat_dir / "00060.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    _run_esg_tag_cli("--all", pythonpath_prefix=prefix)
    out1 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    _run_esg_tag_cli("--all", pythonpath_prefix=prefix)
    out2 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second --all run produced different output"


# -- Edge cases ---------------------------------------------------------------


def test_empty_uses_list_handled_gracefully(tmp_path: Path) -> None:
    """BB-L5-ESG-015: Record with empty uses list produces valid empty enrichment."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00070", [])
    infile = cat_dir / "00070.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00070.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["esg_tag"]
    assert block["version"] == 1
    assert block["by_use_id"] == {}
    assert block["any_esg"] is False


def test_ticker_derived_from_filename_if_missing_in_record(tmp_path: Path) -> None:
    """BB-L5-ESG-016: If hk_ticker is absent, output filename is derived from input stem."""
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
                "Invest in solar energy and wind projects.",
                source_text="We will invest in solar and wind energy.",
            )
        ],
        "enrichments": {},
    }
    infile = cat_dir / "00080.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    out_file = data_dir / "enriched" / "00080.json"
    assert out_file.exists(), f"Expected output at {out_file}"
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert "green" in loaded["enrichments"]["esg_tag"]["by_use_id"]["u1"]


def test_cli_prints_esg_tag_count_to_stdout(tmp_path: Path) -> None:
    """BB-L5-ESG-017: Single-file mode prints '[esg_tag] <ticker>: N/M uses have ESG tags'."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00090",
        [
            _make_use("u1", "Invest in solar energy."),
            _make_use("u2", "Build community healthcare clinics."),
            _make_use("u3", "General corporate purposes."),
        ],
    )
    infile = cat_dir / "00090.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "[esg_tag] 00090: 2/3 uses have ESG tags" in result.stdout


# -- Prior enrichment preservation --------------------------------------------


def test_cli_preserves_prior_enrichments(tmp_path: Path) -> None:
    """BB-L5-ESG-018: CLI single-file path preserves prior enrichment blocks.

    When enriched data already exists for the ticker, the CLI must load from
    enriched_dir to preserve prior enrichment blocks (geo, country, etc.).
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    ticker = "00100"

    # Step 1: Write a raw categorized record.
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "u1",
                "description": "Invest in solar energy.",
                "category_raw": "green",
                "percentage": 100.0,
                "source_text": "We will invest in solar energy.",
            },
        ],
    }
    cat_file = cat_dir / f"{ticker}.json"
    cat_file.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")

    # Step 2: Pre-populate enriched_dir with prior enrichment.
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

    # Step 3: Run CLI with the categorized file path.
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(raw_record, ensure_ascii=False), encoding="utf-8")

    result = _run_esg_tag_cli(str(input_file), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Step 4: Verify prior enrichment (geo) was preserved.
    loaded = json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in loaded["enrichments"], (
        "Prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert loaded["enrichments"]["geo"]["by_use_id"]["u1"] == "mainland"
    assert "esg_tag" in loaded["enrichments"], "esg_tag enrichment must also be present"
    assert "green" in loaded["enrichments"]["esg_tag"]["by_use_id"]["u1"]
