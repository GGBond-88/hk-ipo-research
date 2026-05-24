# Task 002: Write end-to-end black-box tests (RED)

## Project Overview

- **Goal:** Build a CLI-driven data pipeline plus React dashboard that locates "Use of Proceeds" sections in HKEX prospectus PDFs, extracts each use with a two-pass LLM, enriches with eight tag dimensions, persists to SQLite, and renders interactive charts from pre-baked JSON.
- **Architecture:** Eight-stage CLI pipeline (L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L7 -> dashboard). Each stage runs independently and is idempotent.
- **Tech Stack:** Python 3.10+, pydantic v2, OpenAI SDK + OpenRouter, SQLite, pytest. Frontend: Vite + React + ECharts.

## Task Objective

Write the end-to-end black-box tests that exercise the full pipeline (CLI invocations only — no internal imports) against a golden 3-PDF fixture corpus. These tests are expected to FAIL now (modules and the orchestrator do not yet exist) and pass after Task 026. This task implements the outer TDD loop per `superteam:black-box-testing`.

This is Task 2 of 27.

---

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_pipeline_e2e.py`
- Create: `tests/e2e/test_dashboard_build_e2e.py`
- Create: `tests/fixtures/golden_pdfs/README.md`
- Create: `pyproject.toml` modification (add `e2e` pytest marker)

- [ ] **Step 1: Add the `e2e` pytest marker to `pyproject.toml`**

Append after the `[tool.ruff.lint]` block:

```toml
[tool.pytest.ini_options]
markers = [
    "e2e: end-to-end black-box test invoking the full pipeline (slow, requires API key).",
]
testpaths = ["tests"]
```

Then run: `python -m pytest --markers | findstr e2e`
Expected: `@pytest.mark.e2e: end-to-end black-box test ...` listed.

- [ ] **Step 2: Document the golden-PDF fixture corpus**

Create `tests/fixtures/golden_pdfs/README.md`:

```markdown
# Golden PDF corpus for E2E tests

This directory must hold exactly THREE prospectus PDFs named after their HK
ticker, zero-padded to 5 digits:

  03690.pdf   — Meituan (already known to project, English, has TOC bookmark)
  ?????.pdf   — pick one other from data/raw_pdfs/ at execution time
  zh_demo.pdf — a Chinese-dominant PDF (used to test the language-skip path)

Do NOT commit PDF binaries here. Each task that needs to run the e2e suite
must copy three files from `data/raw_pdfs/` (or use symlinks).

The e2e tests skip when these files are missing.
```

- [ ] **Step 3: Write the `conftest.py` shared fixtures**

Create `tests/e2e/conftest.py`:

```python
"""Shared fixtures for end-to-end black-box pipeline tests.

These tests treat the project as a black box: they invoke the CLI exclusively
via subprocess and read pipeline outputs from disk. They do not import the
hk_ipo package directly (except to compute project paths).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = PROJECT_ROOT / "tests" / "fixtures" / "golden_pdfs"


@pytest.fixture(scope="session")
def golden_pdfs() -> list[Path]:
    """Return the list of golden PDF paths; skip if fewer than 3 present."""
    pdfs = sorted(GOLDEN_DIR.glob("*.pdf"))
    if len(pdfs) < 3:
        pytest.skip(f"Need >= 3 PDFs in {GOLDEN_DIR}; found {len(pdfs)}.")
    return pdfs


@pytest.fixture
def isolated_data_dir(tmp_path: Path, golden_pdfs: list[Path]) -> Iterator[Path]:
    """Make a clean copy of golden PDFs into tmp_path/data/raw_pdfs/.

    Returns the data directory root (parent of raw_pdfs/). Pipeline outputs
    accumulate inside this tmp directory and are torn down on exit.
    """
    raw_dir = tmp_path / "data" / "raw_pdfs"
    raw_dir.mkdir(parents=True)
    for pdf in golden_pdfs:
        shutil.copy(pdf, raw_dir / pdf.name)
    yield tmp_path / "data"


@pytest.fixture
def api_key_present() -> None:
    """Skip the test if OPENROUTER_API_KEY is not set in the env."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")


def run_pipeline_cli(*args: str, cwd: Path | None = None,
                     env_extra: dict[str, str] | None = None,
                     timeout: int = 1800) -> subprocess.CompletedProcess:
    """Invoke `python scripts/run_pipeline.py` with `args`.

    Always runs from PROJECT_ROOT unless `cwd` is given. Captures stdout/stderr
    text. Inherits the current env but allows overrides via `env_extra`.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    cmd = ["python", "scripts/run_pipeline.py", *args]
    return subprocess.run(
        cmd, cwd=cwd or PROJECT_ROOT, env=env,
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def run_stage_cli(module: str, *args: str, cwd: Path | None = None,
                  env_extra: dict[str, str] | None = None,
                  timeout: int = 600) -> subprocess.CompletedProcess:
    """Invoke `python -m hk_ipo.<module>` with args."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    cmd = ["python", "-m", f"hk_ipo.{module}", *args]
    return subprocess.run(
        cmd, cwd=cwd or PROJECT_ROOT, env=env,
        capture_output=True, text=True, timeout=timeout, check=False,
    )
```

- [ ] **Step 4: Write `tests/e2e/__init__.py` (empty marker file)**

Create `tests/e2e/__init__.py` with a single line:

```python
"""End-to-end black-box pipeline tests (see tests/e2e/conftest.py)."""
```

- [ ] **Step 5: Write the main E2E pipeline test**

Create `tests/e2e/test_pipeline_e2e.py`:

```python
"""End-to-end black-box tests for the HK IPO pipeline.

These tests run the full L1 -> L7 pipeline via `scripts/run_pipeline.py`
against a 3-PDF golden corpus, then assert on the resulting filesystem
artefacts and SQLite DB contents.

Mark every test with @pytest.mark.e2e. Run with `pytest -m e2e`.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from .conftest import run_pipeline_cli, run_stage_cli

pytestmark = pytest.mark.e2e


# ── A9.1 — End-to-end run produces a populated dashboard ────────────────────

def test_full_pipeline_produces_all_outputs(
    isolated_data_dir: Path, api_key_present: None
) -> None:
    """Run --build-frontend and assert each stage's outputs exist."""
    db_path = isolated_data_dir / "ipo.db"
    result = run_pipeline_cli(
        "--pdf-dir", str(isolated_data_dir / "raw_pdfs"),
        "--db", str(db_path),
        "--limit", "3",
    )
    assert result.returncode == 0, (
        f"pipeline exit={result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # L1 sections exist for each English PDF
    sections_dir = isolated_data_dir / "sections"
    assert sections_dir.exists()
    assert len(list(sections_dir.glob("*.json"))) >= 1

    # L2 extracted exists
    extracted_dir = isolated_data_dir / "extracted"
    assert len(list(extracted_dir.glob("*.json"))) >= 1

    # L4 categorized exists
    categorized_dir = isolated_data_dir / "categorized"
    assert len(list(categorized_dir.glob("*.json"))) >= 1

    # L5 enriched exists with all 8 enrichment blocks
    enriched_files = sorted((isolated_data_dir / "enriched").glob("*.json"))
    assert enriched_files, "no enriched files produced"
    sample = json.loads(enriched_files[0].read_text(encoding="utf-8"))
    expected_dims = {"geo", "country", "industry", "specificity",
                     "timeline", "capex_opex", "esg_tag", "commitment"}
    assert set(sample["enrichments"].keys()) >= expected_dims

    # L6 DB exists with all required tables
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    for required in (
        "companies", "uses", "use_tags", "company_tags",
        "pipeline_runs", "taxonomy_proposals",
    ):
        assert required in tables, f"missing table: {required}"


# ── A1.2 — Chinese-dominant PDF is skipped ─────────────────────────────────

def test_chinese_pdf_skipped_with_stub(
    isolated_data_dir: Path, api_key_present: None
) -> None:
    """A Chinese-dominant PDF produces a section JSON with language='zh' and
    `skipped=True`; downstream stages do not produce extracted/categorized
    files for it."""
    result = run_pipeline_cli(
        "--pdf-dir", str(isolated_data_dir / "raw_pdfs"),
        "--db", str(isolated_data_dir / "ipo.db"),
        "--only", "L1",
        "--limit", "3",
    )
    assert result.returncode == 0

    zh_section_files = [
        p for p in (isolated_data_dir / "sections").glob("*.json")
        if (data := json.loads(p.read_text(encoding="utf-8")))
        and data.get("language") == "zh"
    ]
    assert zh_section_files, "no zh section stub found"
    for p in zh_section_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["skipped"] is True
        assert data.get("text", "") == ""


# ── A9.2 — One failed PDF does not block the others ─────────────────────────

def test_corrupt_pdf_does_not_block_other_tickers(
    isolated_data_dir: Path, api_key_present: None
) -> None:
    """Drop a corrupt PDF into raw_pdfs/ alongside the golden ones; full run
    must finish with a non-empty error_message row in pipeline_runs for the
    corrupt ticker and successful rows for the others."""
    raw_dir = isolated_data_dir / "raw_pdfs"
    corrupt = raw_dir / "99999.pdf"
    corrupt.write_bytes(b"not a real pdf")
    db_path = isolated_data_dir / "ipo.db"

    result = run_pipeline_cli(
        "--pdf-dir", str(raw_dir),
        "--db", str(db_path),
        "--limit", "5",
    )
    # exit non-zero (one failure), but other tickers still produced outputs
    assert result.returncode != 0
    assert len(list((isolated_data_dir / "extracted").glob("*.json"))) >= 1
    with sqlite3.connect(db_path) as conn:
        rows = list(conn.execute(
            "SELECT hk_ticker, status, error_message FROM pipeline_runs "
            "WHERE hk_ticker = '99999' AND error_message IS NOT NULL"
        ))
    assert rows, "99999 should have an error row"


# ── A9.3 — Resumability: re-run after partial completion is a no-op ─────────

def test_rerun_is_idempotent(
    isolated_data_dir: Path, api_key_present: None
) -> None:
    db_path = isolated_data_dir / "ipo.db"
    args = (
        "--pdf-dir", str(isolated_data_dir / "raw_pdfs"),
        "--db", str(db_path),
        "--limit", "3",
    )
    first = run_pipeline_cli(*args)
    assert first.returncode == 0
    enriched_dir = isolated_data_dir / "enriched"
    snap_first = {p.name: p.stat().st_mtime_ns
                  for p in enriched_dir.glob("*.json")}

    second = run_pipeline_cli(*args)
    assert second.returncode == 0
    snap_second = {p.name: p.stat().st_mtime_ns
                   for p in enriched_dir.glob("*.json")}
    # Outputs are not rewritten when inputs are unchanged.
    assert snap_first == snap_second


# ── A9.4 — `--dry-run-cost` exits without making API calls ──────────────────

def test_dry_run_cost_makes_no_api_calls(
    isolated_data_dir: Path
) -> None:
    """Set OPENROUTER_API_KEY to an obviously-broken value; --dry-run-cost
    must still exit 0 because it must not call the API."""
    result = run_pipeline_cli(
        "--pdf-dir", str(isolated_data_dir / "raw_pdfs"),
        "--db", str(isolated_data_dir / "ipo.db"),
        "--dry-run-cost",
        "--limit", "3",
        env_extra={"OPENROUTER_API_KEY": "broken-on-purpose"},
    )
    assert result.returncode == 0
    assert "estimated tokens" in result.stdout.lower() \
        or "estimated cost" in result.stdout.lower()


# ── A6.5 — loader --dry-run does not write to the DB ────────────────────────

def test_loader_dry_run_does_not_modify_db(
    isolated_data_dir: Path, api_key_present: None
) -> None:
    """Run L1-L5 first; then run the loader with --dry-run and assert the
    DB file is either absent or unchanged."""
    db_path = isolated_data_dir / "ipo.db"
    pre = run_pipeline_cli(
        "--pdf-dir", str(isolated_data_dir / "raw_pdfs"),
        "--db", str(db_path),
        "--skip", "L6,L7",
        "--limit", "3",
    )
    assert pre.returncode == 0
    assert not db_path.exists() or db_path.stat().st_size == 0

    dry = run_stage_cli(
        "storage.loader", "--all",
        "--db", str(db_path),
        "--dry-run",
    )
    assert dry.returncode == 0
    assert not db_path.exists() or db_path.stat().st_size == 0
```

- [ ] **Step 6: Write the dashboard-build smoke test**

Create `tests/e2e/test_dashboard_build_e2e.py`:

```python
"""Black-box smoke test for the frontend dashboard build (A8.5)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = pytest.mark.e2e


def _have_npm() -> bool:
    return shutil.which("npm") is not None


@pytest.mark.skipif(not _have_npm(), reason="npm not installed")
def test_frontend_build_produces_dist_folder() -> None:
    """`npm install && npm run build` inside frontend/ produces a dist/ dir
    with index.html and at least one JS chunk."""
    frontend = PROJECT_ROOT / "frontend"
    assert frontend.exists(), "frontend/ directory must exist before this test"

    install = subprocess.run(
        ["npm", "install"], cwd=frontend,
        capture_output=True, text=True, timeout=600, check=False,
    )
    assert install.returncode == 0, install.stderr

    build = subprocess.run(
        ["npm", "run", "build"], cwd=frontend,
        capture_output=True, text=True, timeout=600, check=False,
    )
    assert build.returncode == 0, build.stderr

    dist = frontend / "dist"
    assert (dist / "index.html").exists()
    assert any(dist.glob("assets/*.js")), "no JS chunks built"
```

- [ ] **Step 7: Run the new tests and verify they ALL FAIL or SKIP**

Run: `python -m pytest tests/e2e -m e2e -v`
Expected:
- All tests either FAIL or SKIP.
- Failures should NOT be due to test syntax errors; they should be due to missing pipeline modules / scripts / frontend (the implementations come in later tasks).
- Skips are acceptable when fewer than 3 golden PDFs exist or `OPENROUTER_API_KEY` is not set.

This is the RED phase of the outer black-box TDD loop. Do NOT attempt to fix these; later tasks will.

- [ ] **Step 8: Run the full suite (sans `-m e2e`) to verify no regression**

Run: `python -m pytest -v --ignore=tests/e2e`
Expected: all previously-passing unit tests still pass.
