"""Black-box tests for L5 industry enrichment CLI (Task 011).

These tests invoke ``python -m hk_ipo.enrichments.industry`` via subprocess and
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

pytestmark = pytest.mark.e2e
SRC_PKG = PROJECT_ROOT / "src" / "hk_ipo"
REAL_CONFIG = SRC_PKG / "config.py"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_config_override(tmp_path: Path) -> str:
    """Create a shadow hk_ipo package that overrides DATA_DIR to tmp_path/data.

    Returns the directory to prepend to PYTHONPATH.
    """
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)

    # Copy only the files necessary for the industry enrichment CLI.
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")

    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "industry.py", enrich_dst / "industry.py")

    # Write config with DATA_DIR redirected into tmp_path.
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def _run_industry_cli(
    *args: str,
    pythonpath_prefix: str,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.enrichments.industry`` via subprocess."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.industry", *args],
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


def _write_overrides_csv(data_dir: Path, content: str) -> None:
    """Write an industry_overrides.csv file into data_dir."""
    csv_path = data_dir / "industry_overrides.csv"
    csv_path.write_text(content, encoding="utf-8")


# ── Manual source — single-file mode ─────────────────────────────────────────


def test_manual_single_file_uses_override(tmp_path: Path) -> None:
    """BB-L5-I-001: --source manual for a single file uses the CSV override value."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n01234,Software & Services\n03690,Retailing\n")

    record = _make_record(
        "01234",
        [
            _make_use("u1", "Develop enterprise SaaS platform for logistics."),
        ],
    )
    infile = cat_dir / "01234.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out_file = data_dir / "enriched" / "01234.json"
    assert out_file.exists(), (
        f"Missing {out_file}; enriched dir has: "
        f"{[f.name for f in (data_dir / 'enriched').glob('*')]}"
    )
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["version"] == 1
    assert block["primary"] == "Software & Services"
    assert block["source"] == "manual"


def test_manual_ticker_not_in_csv_yields_unknown(tmp_path: Path) -> None:
    """BB-L5-I-002: --source manual with ticker not in CSV produces primary='Unknown'."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n01234,Software & Services\n")

    record = _make_record(
        "99999",
        [
            _make_use("u1", "Build new manufacturing facility."),
        ],
    )
    infile = cat_dir / "99999.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "99999.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["primary"] == "Unknown"
    assert block["source"] == "manual"


def test_manual_no_csv_file_uses_unknown(tmp_path: Path) -> None:
    """BB-L5-I-003: --source manual without CSV file produces primary='Unknown'."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    # Do NOT create industry_overrides.csv — simulate missing file.

    record = _make_record(
        "00001",
        [
            _make_use("u1", "General corporate purposes."),
        ],
    )
    infile = cat_dir / "00001.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00001.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["primary"] == "Unknown"


# ── --all mode ───────────────────────────────────────────────────────────────


def test_manual_all_processes_all_files(tmp_path: Path) -> None:
    """BB-L5-I-004: --all --source manual processes every JSON in categorized_dir."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(
        data_dir,
        ("ticker,industry\n00010,Software & Services\n00011,Pharmaceuticals\n00012,Real Estate\n"),
    )

    for ticker, desc in [
        ("00010", "Develop cloud platform."),
        ("00011", "Drug research and development."),
        ("00012", "Commercial property development."),
    ]:
        record = _make_record(ticker, [_make_use("u1", desc)])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_industry_cli("--all", "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"

    out10 = json.loads((data_dir / "enriched" / "00010.json").read_text(encoding="utf-8"))
    out11 = json.loads((data_dir / "enriched" / "00011.json").read_text(encoding="utf-8"))
    out12 = json.loads((data_dir / "enriched" / "00012.json").read_text(encoding="utf-8"))

    assert out10["enrichments"]["industry"]["primary"] == "Software & Services"
    assert out11["enrichments"]["industry"]["primary"] == "Pharmaceuticals"
    assert out12["enrichments"]["industry"]["primary"] == "Real Estate"


def test_all_falls_back_to_categorized_when_enriched_empty(tmp_path: Path) -> None:
    """BB-L5-I-005: --all falls back to categorized_dir when enriched_dir exists but empty."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)  # exists but empty
    _write_overrides_csv(data_dir, "ticker,industry\n00020,Capital Goods\n")

    record = _make_record("00020", [_make_use("u1", "Heavy machinery production.")])
    (cat_dir / "00020.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli("--all", "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((enr_dir / "00020.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["industry"]["primary"] == "Capital Goods"


def test_all_stdout_reports_industry_per_ticker(tmp_path: Path) -> None:
    """BB-L5-I-006: --all prints an [industry] line per processed ticker."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(
        data_dir, ("ticker,industry\n00030,Retailing\n00031,Food Beverage & Tobacco\n")
    )

    for ticker in ("00030", "00031"):
        record = _make_record(ticker, [_make_use("u1", "Business operations.")])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_industry_cli("--all", "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0
    assert "[industry] 00030:" in result.stdout
    assert "[industry] 00031:" in result.stdout


# ── --force flag ─────────────────────────────────────────────────────────────


def test_force_reprocesses_existing_enrichment(tmp_path: Path) -> None:
    """BB-L5-I-007: --force re-processes even when enrichment already exists.

    When the input record already has an enrichments.industry block (e.g. from a
    previous run), running without --force must preserve the existing block
    (early return, no save). Running with --force must re-process and overwrite.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00040,Software & Services\n")

    # Create a record with pre-existing enrichments.industry containing a wrong value.
    record = _make_record("00040", [_make_use("u1", "Enterprise software platform.")])
    record["enrichments"]["industry"] = {
        "version": 1,
        "primary": "Wrong Industry",
        "source": "manual",
    }
    infile = cat_dir / "00040.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    (enr_dir / "00040.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Run WITHOUT --force: existing enrichment must be preserved.
    r1 = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = json.loads((enr_dir / "00040.json").read_text(encoding="utf-8"))
    assert out1["enrichments"]["industry"]["primary"] == "Wrong Industry", (
        "Without --force, pre-existing enrichment should be preserved"
    )

    # Run WITH --force: enrichment must be recalculated from overrides.
    r2 = _run_industry_cli(str(infile), "--force", "--source", "manual", pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = json.loads((enr_dir / "00040.json").read_text(encoding="utf-8"))
    assert out2["enrichments"]["industry"]["primary"] == "Software & Services"
    assert out2["enrichments"]["industry"]["source"] == "manual"


# ── Error paths ──────────────────────────────────────────────────────────────


def test_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-I-008: Non-existent input file causes non-zero exit and stderr message."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    bad_path = data_dir / "nonexistent.json"
    result = _run_industry_cli(str(bad_path), pythonpath_prefix=prefix)

    assert result.returncode != 0, (
        f"Expected non-zero exit for missing file, got {result.returncode}"
    )
    assert "ERROR" in result.stderr or "Not found" in result.stderr, (
        f"stderr: {result.stderr[:300]}"
    )


def test_no_args_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-I-009: Calling with neither --all nor input path exits non-zero."""
    prefix = _make_config_override(tmp_path)
    result = _run_industry_cli(pythonpath_prefix=prefix)
    assert result.returncode != 0, f"Expected non-zero exit with no args, got {result.returncode}"


# ── Idempotency ──────────────────────────────────────────────────────────────


def test_single_file_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-I-010: Running the same input twice produces identical enriched output."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00050,Banks\n")

    record = _make_record("00050", [_make_use("u1", "Commercial banking services.")])
    infile = cat_dir / "00050.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    r1 = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = (data_dir / "enriched" / "00050.json").read_text(encoding="utf-8")

    r2 = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = (data_dir / "enriched" / "00050.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second run produced different output"


def test_all_mode_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-I-011: --all is idempotent: same input yields same output on re-run."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00060,Semiconductors\n")

    record = _make_record("00060", [_make_use("u1", "Chip fabrication plant.")])
    (cat_dir / "00060.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    _run_industry_cli("--all", "--source", "manual", pythonpath_prefix=prefix)
    out1 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    _run_industry_cli("--all", "--source", "manual", pythonpath_prefix=prefix)
    out2 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second --all run produced different output"


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_empty_uses_list_handled_gracefully(tmp_path: Path) -> None:
    """BB-L5-I-012: Record with empty uses list produces valid enrichment."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00070,Health Care Equipment\n")

    record = _make_record("00070", [])
    infile = cat_dir / "00070.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0
    loaded = json.loads((data_dir / "enriched" / "00070.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["version"] == 1
    assert block["primary"] == "Health Care Equipment"
    assert block["source"] == "manual"


def test_ticker_derived_from_filename_if_missing_in_record(tmp_path: Path) -> None:
    """BB-L5-I-013: If hk_ticker is absent, output filename is derived from input stem."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00080,Consumer Services\n")

    record = {
        "company_name_en": "No Ticker Corp",
        "schema_version": "2.0",
        "uses": [_make_use("u1", "Consumer delivery platform.")],
        "enrichments": {},
    }
    infile = cat_dir / "00080.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0
    # Output should be at enriched/00080.json since stem is "00080"
    out_file = data_dir / "enriched" / "00080.json"
    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["enrichments"]["industry"]["primary"] == "Consumer Services"


def test_stdout_reports_industry_for_single_file(tmp_path: Path) -> None:
    """BB-L5-I-014: Single-file mode prints '[industry] <ticker>: <industry>' to stdout."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00090,Pharmaceuticals\n")

    record = _make_record("00090", [_make_use("u1", "Biotech drug development.")])
    infile = cat_dir / "00090.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0
    assert "[industry] 00090: Pharmaceuticals (source=manual)" in result.stdout


def test_csv_with_whitespace_trimmed(tmp_path: Path) -> None:
    """BB-L5-I-015: CSV values with surrounding whitespace are properly trimmed."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n 00100 ,  Capital Goods  \n")

    record = _make_record("00100", [_make_use("u1", "Industrial equipment.")])
    infile = cat_dir / "00100.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0
    loaded = json.loads((data_dir / "enriched" / "00100.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["industry"]["primary"] == "Capital Goods"


def test_csv_blank_lines_skipped(tmp_path: Path) -> None:
    """BB-L5-I-016: CSV rows with empty ticker or industry are silently skipped."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    # Row with empty industry, empty ticker, and a valid row.
    _write_overrides_csv(data_dir, ("ticker,industry\n,Software\n00110,\n00110,Real Estate\n,\n"))

    record = _make_record("00110", [_make_use("u1", "Property leasing.")])
    infile = cat_dir / "00110.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(str(infile), "--source", "manual", pythonpath_prefix=prefix)

    assert result.returncode == 0
    loaded = json.loads((data_dir / "enriched" / "00110.json").read_text(encoding="utf-8"))
    assert loaded["enrichments"]["industry"]["primary"] == "Real Estate"


# ── Prospectus source (LLM) — requires API key ───────────────────────────────


def test_prospectus_single_file_classifies_via_llm(tmp_path: Path) -> None:
    """BB-L5-I-017: --source prospectus classification returns a non-empty industry name."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00200",
        [
            _make_use(
                "u1",
                "The company is a leading software-as-a-service provider. "
                "Proceeds will be used to expand cloud infrastructure and "
                "develop new enterprise software products.",
                source_text="Leading SaaS provider expanding cloud and enterprise software.",
            ),
        ],
        company_name_en="CloudSoft Technologies Ltd",
    )
    infile = cat_dir / "00200.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(
        str(infile), "--source", "prospectus", pythonpath_prefix=prefix, timeout=120
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00200.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["version"] == 1
    assert block["primary"] != "Unknown", (
        f"Expected a specific industry classification, got {block['primary']}"
    )
    assert isinstance(block["primary"], str) and len(block["primary"]) > 0
    assert block["source"] == "prospectus"


def test_prospectus_all_mode(tmp_path: Path) -> None:
    """BB-L5-I-018: --all --source prospectus processes multiple files via LLM."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for ticker, name, desc in [
        ("00210", "PharmaCorp Ltd", "Drug discovery and clinical trials for oncology treatments."),
        ("00211", "RetailMax Group", "Omnichannel retail platform for consumer goods."),
    ]:
        record = _make_record(
            ticker,
            [
                _make_use("u1", desc, source_text=desc),
            ],
            company_name_en=name,
        )
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_industry_cli(
        "--all", "--source", "prospectus", pythonpath_prefix=prefix, timeout=120
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out10 = json.loads((data_dir / "enriched" / "00210.json").read_text(encoding="utf-8"))
    out11 = json.loads((data_dir / "enriched" / "00211.json").read_text(encoding="utf-8"))
    assert out10["enrichments"]["industry"]["primary"] != "Unknown"
    assert out11["enrichments"]["industry"]["primary"] != "Unknown"
    assert out10["enrichments"]["industry"]["source"] == "prospectus"
    assert out11["enrichments"]["industry"]["source"] == "prospectus"


def test_prospectus_with_manual_override_takes_priority(tmp_path: Path) -> None:
    """BB-L5-I-019: --source prospectus still uses CSV override when ticker matches."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    _write_overrides_csv(data_dir, "ticker,industry\n00220,Semiconductors\n")

    # The uses text describes a pharmaceutical company, but CSV override
    # says Semiconductors — override must take priority via source=manual.
    record = _make_record(
        "00220",
        [
            _make_use(
                "u1",
                "Drug discovery platform for rare diseases.",
                source_text="Pharmaceutical drug discovery for rare diseases.",
            ),
        ],
        company_name_en="Pharma Biotech Inc",
    )
    infile = cat_dir / "00220.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(
        str(infile), "--source", "prospectus", pythonpath_prefix=prefix, timeout=120
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00220.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["primary"] == "Semiconductors", (
        f"Manual override should take priority, got {block['primary']}"
    )
    assert block["source"] == "manual", (
        f"Source should be 'manual' when override used, got {block['source']}"
    )


def test_prospectus_empty_uses_still_classifies(tmp_path: Path) -> None:
    """BB-L5-I-020: --source prospectus with empty uses still attempts classification."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    # Uses text is empty — LLM should still produce a response (possibly "Unknown").
    record = _make_record("00230", [], company_name_en="Mystery Holdings Ltd")
    infile = cat_dir / "00230.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(
        str(infile), "--source", "prospectus", pythonpath_prefix=prefix, timeout=120
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00230.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert block["version"] == 1
    assert isinstance(block["primary"], str)
    assert block["source"] == "prospectus"


def test_prospectus_llm_error_graceful_degradation(tmp_path: Path) -> None:
    """BB-L5-I-021: When LLM returns empty/None, primary becomes 'Unknown' without crash."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    # Provide extremely minimal/no info — LLM may return empty.
    record = _make_record(
        "00240",
        [
            _make_use("u1", ".", source_text="."),
        ],
        company_name_en=".",
    )
    infile = cat_dir / "00240.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_industry_cli(
        str(infile), "--source", "prospectus", pythonpath_prefix=prefix, timeout=120
    )

    # CLI should not crash; block should exist with primary field.
    assert result.returncode == 0, f"stderr: {result.stderr}"
    loaded = json.loads((data_dir / "enriched" / "00240.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["industry"]
    assert "primary" in block
    assert "version" in block
    assert "source" in block
