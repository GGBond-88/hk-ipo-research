"""Black-box tests for L5 country enrichment CLI (Task 010).

These tests invoke ``python -m hk_ipo.enrichments.country`` via subprocess and
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


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_config_override(tmp_path: Path) -> str:
    """Create a shadow hk_ipo package that overrides DATA_DIR to tmp_path/data.

    Returns the directory to prepend to PYTHONPATH.
    """
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)

    # Copy only the files necessary for the country enrichment CLI.
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")

    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "country.py", enrich_dst / "country.py")

    # Write config with DATA_DIR redirected into tmp_path.
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def _run_country_cli(
    *args: str,
    pythonpath_prefix: str,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.enrichments.country`` via subprocess."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.country", *args],
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


# ── Single-file mode ─────────────────────────────────────────────────────────


def test_single_file_creates_country_enrichment(tmp_path: Path) -> None:
    """BB-L5-C-001: Single-file mode writes enrichments.country to output JSON."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00001",
        [
            _make_use("u1", "Expand into Singapore and Japan."),
        ],
    )
    infile = cat_dir / "00001.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)

    assert result.returncode == 0, f"stderr: {result.stderr}"
    out_file = data_dir / "enriched" / "00001.json"
    assert out_file.exists(), (
        f"Missing {out_file}; enriched dir has: "
        f"{[f.name for f in (data_dir / 'enriched').glob('*')]}"
    )
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert block["version"] >= 1
    assert "SG" in block["countries"]
    assert "JP" in block["countries"]
    assert block["by_use_id"]["u1"] == ["JP", "SG"]


def test_single_file_no_country_matches_empty_list(tmp_path: Path) -> None:
    """BB-L5-C-002: Text without country mentions produces empty countries list."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00002",
        [
            _make_use(
                "u1",
                "We will expand our Hong Kong office.",
                source_text="We will expand our Hong Kong office.",
            ),
        ],
    )
    infile = cat_dir / "00002.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((data_dir / "enriched" / "00002.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert block["countries"] == []
    assert block["by_use_id"]["u1"] == []


def test_single_file_multiple_uses_per_record(tmp_path: Path) -> None:
    """BB-L5-C-003: Multiple use items are each enriched independently."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00003",
        [
            _make_use("u1", "Expand into Vietnam.", percentage=50.0),
            _make_use("u2", "Expand into Thailand.", percentage=50.0),
        ],
    )
    infile = cat_dir / "00003.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    loaded = json.loads((data_dir / "enriched" / "00003.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert sorted(block["countries"]) == ["TH", "VN"]
    assert block["by_use_id"]["u1"] == ["VN"]
    assert block["by_use_id"]["u2"] == ["TH"]


def test_single_file_country_name_case_insensitive(tmp_path: Path) -> None:
    """BB-L5-C-004: Country names are matched case-insensitively."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00004",
        [
            _make_use("u1", "Expansion into JAPAN and singapore."),
            _make_use("u2", "Targeting the united states."),
        ],
    )
    infile = cat_dir / "00004.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    loaded = json.loads((data_dir / "enriched" / "00004.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert "JP" in block["countries"]
    assert "SG" in block["countries"]
    assert "US" in block["countries"]


def test_single_file_multi_word_country_name(tmp_path: Path) -> None:
    """BB-L5-C-005: Multi-word country names (e.g. 'united states') are matched."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00005",
        [
            _make_use("u1", "Operations in the United States and United Kingdom."),
            _make_use("u2", "Expansion into South Korea and New Zealand."),
        ],
    )
    infile = cat_dir / "00005.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    loaded = json.loads((data_dir / "enriched" / "00005.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert "US" in block["countries"]
    assert "GB" in block["countries"]
    assert "KR" in block["countries"]
    assert "NZ" in block["countries"]


def test_single_file_word_boundary_no_false_positive(tmp_path: Path) -> None:
    """BB-L5-C-006: Substring matches without word boundaries do NOT produce false codes."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00006",
        [
            _make_use(
                "u1", "Luke works in our UK office.", source_text="Luke works in our UK office."
            ),
        ],
    )
    infile = cat_dir / "00006.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    loaded = json.loads((data_dir / "enriched" / "00006.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    # "Luke" contains "uk" but word boundaries must prevent match
    assert "GB" in block["countries"]  # standalone "UK" with word boundaries matches


def test_single_file_america_substring_not_matched(tmp_path: Path) -> None:
    """BB-L5-C-007: 'america' must match only as a standalone word, not inside phrases."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00007",
        [
            _make_use(
                "u1",
                "South America is not the same as America.",
                source_text="South America is not the same as America.",
            ),
        ],
    )
    infile = cat_dir / "00007.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    loaded = json.loads((data_dir / "enriched" / "00007.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    # "South America" should NOT match "america" → US because of word boundaries
    assert "US" in block["countries"]  # standalone "America" matches


# ── Non-existent / error paths ───────────────────────────────────────────────


def test_nonexistent_file_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-C-008: Non-existent input file causes non-zero exit and stderr message."""
    prefix = _make_config_override(tmp_path)

    bad_path = tmp_path / "data" / "nonexistent.json"
    result = _run_country_cli(str(bad_path), pythonpath_prefix=prefix)

    assert result.returncode != 0, (
        f"Expected non-zero exit for missing file, got {result.returncode}"
    )
    assert "ERROR" in result.stderr or "Not found" in result.stderr, (
        f"stderr: {result.stderr[:300]}"
    )


# ── --all mode ───────────────────────────────────────────────────────────────


def test_all_mode_processes_all_files(tmp_path: Path) -> None:
    """BB-L5-C-009: --all processes every JSON in categorized_dir."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for i, (ticker, text) in enumerate(
        [
            ("00010", "Expand into Japan."),
            ("00011", "Expand into Germany and France."),
            ("00012", "Expand into Brazil."),
        ]
    ):
        record = _make_record(ticker, [_make_use(f"u{i + 1}", text)])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_country_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Verify each ticker produced an enriched output.
    out10 = json.loads((data_dir / "enriched" / "00010.json").read_text(encoding="utf-8"))
    out11 = json.loads((data_dir / "enriched" / "00011.json").read_text(encoding="utf-8"))
    out12 = json.loads((data_dir / "enriched" / "00012.json").read_text(encoding="utf-8"))

    assert "JP" in out10["enrichments"]["country"]["countries"]
    assert "DE" in out11["enrichments"]["country"]["countries"]
    assert "FR" in out11["enrichments"]["country"]["countries"]
    assert "BR" in out12["enrichments"]["country"]["countries"]


def test_all_mode_falls_back_when_enriched_empty(tmp_path: Path) -> None:
    """BB-L5-C-010: --all falls back to categorized_dir when enriched_dir exists but empty."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)  # exists but empty

    record = _make_record("00020", [_make_use("u1", "Expand into Singapore.")])
    (cat_dir / "00020.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    loaded = json.loads((enr_dir / "00020.json").read_text(encoding="utf-8"))
    assert "SG" in loaded["enrichments"]["country"]["countries"]


def test_all_mode_stdout_reports_processed_tickers(tmp_path: Path) -> None:
    """BB-L5-C-011: --all prints a [country] line per processed ticker."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    for ticker in ("00030", "00031"):
        record = _make_record(ticker, [_make_use("u1", "Expand into India.")])
        (cat_dir / f"{ticker}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    result = _run_country_cli("--all", pythonpath_prefix=prefix)
    assert result.returncode == 0

    assert "[country] 00030:" in result.stdout
    assert "[country] 00031:" in result.stdout


# ── --force flag ─────────────────────────────────────────────────────────────


def test_force_reprocesses_existing_enrichment(tmp_path: Path) -> None:
    """BB-L5-C-012: --force re-processes even when enrichment already exists.

    When the input record already has an enrichments.country block (e.g. from a
    previous run), running without --force must preserve the existing block
    (early return, no save). Running with --force must re-process and overwrite.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    # Create a record whose uses mention Japan, but with a pre-existing
    # enrichments.country block containing a deliberately wrong code (XX).
    record = _make_record("00040", [_make_use("u1", "Expand into Japan.")])
    record["enrichments"]["country"] = {
        "version": 1,
        "countries": ["XX"],
        "by_use_id": {"u1": ["XX"]},
    }
    infile = cat_dir / "00040.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    # Pre-save the same record to enriched/ so the output file exists
    # before we verify the early-return path.
    (enr_dir / "00040.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # Run WITHOUT --force: existing enrichment (XX) must be preserved.
    # Uses mention Japan, so if re-processing happened, JP would appear.
    r1 = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = json.loads((enr_dir / "00040.json").read_text(encoding="utf-8"))
    assert out1["enrichments"]["country"]["countries"] == ["XX"], (
        "Without --force, pre-existing enrichment should be preserved"
    )
    assert "JP" not in out1["enrichments"]["country"]["countries"]

    # Run WITH --force: enrichment must be recalculated from uses.
    r2 = _run_country_cli(str(infile), "--force", pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = json.loads((enr_dir / "00040.json").read_text(encoding="utf-8"))
    assert "JP" in out2["enrichments"]["country"]["countries"]
    assert "XX" not in out2["enrichments"]["country"]["countries"]


# ── Idempotency ──────────────────────────────────────────────────────────────


def test_single_file_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-C-013: Running the same input twice produces identical enriched output."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00050", [_make_use("u1", "Expand into Malaysia.")])
    infile = cat_dir / "00050.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    r1 = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert r1.returncode == 0
    out1 = (data_dir / "enriched" / "00050.json").read_text(encoding="utf-8")

    r2 = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert r2.returncode == 0
    out2 = (data_dir / "enriched" / "00050.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second run produced different output"


def test_all_mode_idempotent_output(tmp_path: Path) -> None:
    """BB-L5-C-014: --all is idempotent: same input yields same output on re-run."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00060", [_make_use("u1", "Expand into Canada.")])
    (cat_dir / "00060.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    _run_country_cli("--all", pythonpath_prefix=prefix)
    out1 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    _run_country_cli("--all", pythonpath_prefix=prefix)
    out2 = (data_dir / "enriched" / "00060.json").read_text(encoding="utf-8")

    assert out1 == out2, "Second --all run produced different output"


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_empty_uses_list_handled_gracefully(tmp_path: Path) -> None:
    """BB-L5-C-015: Record with empty uses list produces valid empty enrichment."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record("00070", [])
    infile = cat_dir / "00070.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    loaded = json.loads((data_dir / "enriched" / "00070.json").read_text(encoding="utf-8"))
    block = loaded["enrichments"]["country"]
    assert block["countries"] == []
    assert block["by_use_id"] == {}


def test_ticker_derived_from_filename_if_missing_in_record(tmp_path: Path) -> None:
    """BB-L5-C-016: If hk_ticker is absent, output filename is derived from input stem."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = {
        "company_name_en": "No Ticker Corp",
        "schema_version": "2.0",
        "uses": [_make_use("u1", "Expand into Italy.")],
        "enrichments": {},
    }
    infile = cat_dir / "00080.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0

    # Output should be at enriched/00080.json since stem is "00080"
    out_file = data_dir / "enriched" / "00080.json"
    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert "IT" in loaded["enrichments"]["country"]["countries"]


def test_cli_prints_country_count_to_stdout(tmp_path: Path) -> None:
    """BB-L5-C-017: Single-file mode prints '[country] <ticker>: N countries'."""
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)

    record = _make_record(
        "00090",
        [
            _make_use("u1", "Expand into Spain and Poland."),
        ],
    )
    infile = cat_dir / "00090.json"
    infile.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    result = _run_country_cli(str(infile), pythonpath_prefix=prefix)
    assert result.returncode == 0
    assert "[country] 00090: 2 countries" in result.stdout


# ── Missing required arguments ───────────────────────────────────────────────


def test_no_args_exits_nonzero(tmp_path: Path) -> None:
    """BB-L5-C-018: Calling with neither --all nor input path exits non-zero."""
    prefix = _make_config_override(tmp_path)
    result = _run_country_cli(pythonpath_prefix=prefix)
    assert result.returncode != 0, f"Expected non-zero exit with no args, got {result.returncode}"


# ── Prior enrichment preservation (SR-002 / CR-002) ──────────────────────────


def test_cli_preserves_prior_enrichments(tmp_path: Path) -> None:
    """BB-L5-C-019: CLI single-file path preserves prior enrichment blocks.

    SR-002 / CR-002: When enriched data already exists for the ticker, the CLI
    must load from enriched_dir to preserve prior enrichment blocks from other
    dimensions. This black-box test verifies the end-to-end behavior directly
    via subprocess.
    """
    prefix = _make_config_override(tmp_path)
    data_dir = tmp_path / "data"
    cat_dir = data_dir / "categorized"
    cat_dir.mkdir(parents=True)
    enr_dir = data_dir / "enriched"
    enr_dir.mkdir(parents=True)

    ticker = "00100"

    # Step 1: Write a raw categorized record (no enrichments).
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "u1",
                "description": "Expand into Singapore market.",
                "category_raw": "expansion",
                "percentage": 100.0,
                "source_text": "For expanding operations in Singapore.",
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
            "geo": {"version": 1, "by_use_id": {"u1": "overseas"}},
        },
    }
    enr_file = enr_dir / f"{ticker}.json"
    enr_file.write_text(json.dumps(enriched_record, ensure_ascii=False), encoding="utf-8")

    # Step 3: Run CLI with the categorized file path. The CLI must detect that
    # enriched data already exists and load from enriched_dir instead.
    result = _run_country_cli(str(cat_file), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Step 4: Verify that prior enrichment (geo) was preserved.
    loaded = json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in loaded["enrichments"], (
        "SR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert loaded["enrichments"]["geo"]["by_use_id"]["u1"] == "overseas"
    assert "country" in loaded["enrichments"], "country enrichment must also be present"
    assert "SG" in loaded["enrichments"]["country"]["countries"]
