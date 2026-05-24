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


@pytest.fixture
def golden_pdfs(tmp_path: Path) -> list[Path]:
    """Return per-test isolated copies of the golden PDFs; skip if fewer than 3 present.

    Each test invocation receives its own writable copies inside ``tmp_path``
    so that a misbehaving test cannot corrupt the shared fixture directory or
    the copies seen by another test.
    """
    source_pdfs = sorted(GOLDEN_DIR.glob("*.pdf"))
    if len(source_pdfs) < 3:
        pytest.skip(f"Need >= 3 PDFs in {GOLDEN_DIR}; found {len(source_pdfs)}.")
    golden_tmp = tmp_path / "golden_pdfs"
    golden_tmp.mkdir(parents=True)
    copies: list[Path] = []
    for pdf in source_pdfs:
        dest = golden_tmp / pdf.name
        shutil.copy(pdf, dest)
        copies.append(dest)
    return copies


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


def run_pipeline_cli(
    *args: str,
    cwd: Path | None = None,
    env_extra: dict[str, str] | None = None,
    timeout: int = 1800,
) -> subprocess.CompletedProcess:
    """Invoke `python scripts/run_pipeline.py` with `args`.

    Always runs from PROJECT_ROOT unless `cwd` is given. Captures stdout/stderr
    text. Inherits the current env but allows overrides via `env_extra`.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    cmd = ["python", "scripts/run_pipeline.py", *args]
    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_stage_cli(
    module: str,
    *args: str,
    cwd: Path | None = None,
    env_extra: dict[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """Invoke `python -m hk_ipo.<module>` with args."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    cmd = ["python", "-m", f"hk_ipo.{module}", *args]
    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
