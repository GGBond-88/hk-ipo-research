"""Black-box tests for L5 specificity enrichment CLI.

These tests invoke ``python -m hk_ipo.enrichments.specificity`` via subprocess
and verify behaviour through exit codes, stdout/stderr, and filesystem
artefacts. They do NOT import hk_ipo internals directly.

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

    # Copy only the files necessary for the specificity enrichment CLI.
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")

    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "specificity.py", enrich_dst / "specificity.py")

    # Write config with DATA_DIR redirected into tmp_path.
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def _run_specificity_cli(
    *args: str,
    pythonpath_prefix: str,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m hk_ipo.enrichments.specificity`` via subprocess."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.specificity", *args],
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


# -- Prior enrichment preservation (SR-002 / CR-002) -------------------------


def test_cli_preserves_prior_enrichments(tmp_path: Path) -> None:
    """BB-L5-S-001: CLI single-file path preserves prior enrichment blocks.

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

    ticker = "00001"

    # Step 1: Write a raw categorized record (no enrichments).
    raw_record: dict[str, object] = {
        "hk_ticker": ticker,
        "company_name_en": "Test Corp",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "u1",
                "description": "General working capital purposes.",
                "category_raw": "working capital",
                "percentage": 100.0,
                "source_text": "For general working capital purposes.",
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
    result = _run_specificity_cli(str(cat_file), pythonpath_prefix=prefix)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Step 4: Verify that prior enrichment (geo) was preserved.
    loaded = json.loads(enr_file.read_text(encoding="utf-8"))
    assert "geo" in loaded["enrichments"], (
        "SR-002 regression: prior 'geo' enrichment was silently dropped by CLI single-file path"
    )
    assert loaded["enrichments"]["geo"]["by_use_id"]["u1"] == "domestic_hk"
    assert "specificity" in loaded["enrichments"], "specificity enrichment must also be present"
    # "general working capital purposes" triggers the GENERAL_MARKERS pattern -> "general"
    assert loaded["enrichments"]["specificity"]["by_use_id"]["u1"] == "general"
