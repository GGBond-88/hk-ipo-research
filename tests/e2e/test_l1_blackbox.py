"""Black-box tests for L1 sectioning CLI (Task 004).

These tests invoke `python -m hk_ipo.l1_sectioning` via subprocess and
verify behaviour through stdout/stderr and filesystem artefacts. They do
NOT import hk_ipo internals directly.

For --all mode tests that need custom directories, we create a temporary
config override that shadows the real hk_ipo.config module via a complete
mini-package copy. This is the black-box way to test a CLI whose config
is imported at module level.
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
RAW_PDFS_DIR = PROJECT_ROOT / "data" / "raw_pdfs"

pytestmark = pytest.mark.e2e


def _make_config_override(tmp_path: Path, raw_dir: Path, sec_dir: Path) -> str:
    """Create a shadow hk_ipo/ package that overrides config.py directories.

    Copies __init__.py and l1_sectioning.py from the real package so that
    ``python -m hk_ipo.l1_sectioning`` can run against the override.
    Returns the PYTHONPATH prefix directory to prepend.
    """
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)

    src_pkg = PROJECT_ROOT / "src" / "hk_ipo"
    shutil.copy(src_pkg / "__init__.py", pkg / "__init__.py")
    shutil.copy(src_pkg / "l1_sectioning.py", pkg / "l1_sectioning.py")

    real_src = REAL_CONFIG.read_text(encoding="utf-8")
    config_py = real_src
    config_py = config_py.replace(
        'RAW_PDFS_DIR: Path = DATA_DIR / "raw_pdfs"',
        f'RAW_PDFS_DIR: Path = Path(r"{raw_dir}")',
    )
    config_py = config_py.replace(
        'SECTIONS_DIR: Path = DATA_DIR / "sections"',
        f'SECTIONS_DIR: Path = Path(r"{sec_dir}")',
    )

    (pkg / "config.py").write_text(config_py, encoding="utf-8")
    return str(override_root)


def _run_l1_cli(
    *args: str,
    env_override: dict[str, str] | None = None,
    timeout: int = 180,
    cwd: Path | None = None,
    pythonpath_prefix: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke L1 module CLI via subprocess."""
    env = dict(os.environ)
    if pythonpath_prefix:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pythonpath_prefix + (os.pathsep + existing if existing else "")
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.l1_sectioning", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        check=False,
    )


def _copy_pdf_with_name(raw_tmp: Path, new_stem: str) -> Path:
    """Copy the first available real PDF to `raw_tmp` with a given stem.

    Returns the path to the copied PDF. Skips the test if no source PDF
    is available.
    """
    src_pdfs = sorted(RAW_PDFS_DIR.glob("*.pdf"))
    if not src_pdfs:
        pytest.skip("No source PDFs available in data/raw_pdfs/")
    dest = raw_tmp / f"{new_stem}.pdf"
    shutil.copy(src_pdfs[0], dest)
    return dest


def _get_output_json(sec_dir: Path, ticker: str) -> dict:
    """Read the output JSON for a given ticker from sec_dir."""
    out_file = sec_dir / f"{ticker}.json"
    if not out_file.exists():
        # Try zero-padded
        for f in sec_dir.glob("*.json"):
            if f.stem == ticker or f.stem == ticker.zfill(5):
                out_file = f
                break
    assert out_file.exists(), (
        f"No output for ticker={ticker}; files: {[f.name for f in sec_dir.glob('*.json')]}"
    )
    return json.loads(out_file.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════════
# BB-001: Single-file mode produces output
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_file_mode_produces_output(tmp_path: Path) -> None:
    """Single-file mode exits 0, writes JSON with ticker derived from filename."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    # Rename a real PDF to a 4-5 digit name so ticker_from_filename works
    pdf = _copy_pdf_with_name(raw_tmp, "03690")
    expected_ticker = "03690"

    result = _run_l1_cli(str(pdf), pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"
    assert "->" in result.stdout, f"stdout missing '->': {result.stdout[:200]}"

    out_file = sec_tmp / f"{expected_ticker}.json"
    assert out_file.exists(), (
        f"Expected {out_file.name}, got: {[f.name for f in sec_tmp.glob('*.json')]}"
    )
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["hk_ticker"] == expected_ticker, (
        f"Ticker mismatch: {data['hk_ticker']} != {expected_ticker}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-002: Output JSON schema validation
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED_FIELDS = {
    "company_file",
    "hk_ticker",
    "document_date",
    "section_title",
    "start_page",
    "end_page",
    "text",
    "tables",
    "extraction_method",
    "language",
    "skipped",
}

VALID_EXTRACTION_METHODS = {"toc", "regex", "skipped"}
VALID_LANGUAGES = {"en", "zh", "mixed", "unknown"}


def test_output_schema_contains_all_required_fields(tmp_path: Path) -> None:
    """Every L1 output JSON must contain all v2 schema fields with correct types."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    pdf = _copy_pdf_with_name(raw_tmp, "03690")

    result = _run_l1_cli(str(pdf), pythonpath_prefix=pp_prefix)
    assert result.returncode == 0

    data = _get_output_json(sec_tmp, "03690")

    for field in sorted(_REQUIRED_FIELDS):
        assert field in data, f"Missing required field: {field}"

    assert isinstance(data["language"], str)
    assert isinstance(data["skipped"], bool)
    assert isinstance(data["tables"], list)
    assert isinstance(data["hk_ticker"], (str, type(None)))

    assert data["extraction_method"] in VALID_EXTRACTION_METHODS, (
        f"extraction_method={data['extraction_method']}"
    )
    assert data["language"] in VALID_LANGUAGES, f"language={data['language']}"

    # Logical consistency: if method is toc/regex, skipped must be False
    if data["extraction_method"] in ("toc", "regex"):
        assert data["skipped"] is False, (
            f"extraction_method={data['extraction_method']} but skipped=True"
        )
    # If method is skipped, skipped must be True and text must be empty
    if data["extraction_method"] == "skipped":
        assert data["skipped"] is True
        assert data["text"] == ""


# ═══════════════════════════════════════════════════════════════════════════════
# BB-003: --help output completeness
# ═══════════════════════════════════════════════════════════════════════════════


def test_help_output_lists_all_flags() -> None:
    """--help must document --all, --force, --limit, and pdf positional."""
    result = _run_l1_cli("--help")
    assert result.returncode == 0
    assert "--all" in result.stdout
    assert "--force" in result.stdout
    assert "--limit" in result.stdout
    assert "pdf" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# BB-004: Missing required argument
# ═══════════════════════════════════════════════════════════════════════════════


def test_missing_required_arg_exits_nonzero() -> None:
    """Calling with neither --all nor pdf must exit non-zero."""
    result = _run_l1_cli()
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-005: --force flag accepted in single-file mode
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_file_force_flag_accepted(tmp_path: Path) -> None:
    """--force in single-file mode must not cause argparse error."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    pdf = _copy_pdf_with_name(raw_tmp, "03690")

    result = _run_l1_cli(str(pdf), "--force", pythonpath_prefix=pp_prefix)
    assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr[:300]}"
    assert "->" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# BB-006: Non-numeric filename skipped in --all mode
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_mode_skips_non_numeric_filename(tmp_path: Path) -> None:
    """--all must skip PDFs not matching \\d{4,5}.pdf, log [SKIP] to stderr.
    Numeric-named PDFs must still produce output."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    # Copy a real PDF with a legacy (non-numeric) name
    src_pdfs = sorted(RAW_PDFS_DIR.glob("*.pdf"))
    if not src_pdfs:
        pytest.skip("No source PDFs available")
    shutil.copy(src_pdfs[0], raw_tmp / "ltn20180907011.pdf")  # non-numeric
    shutil.copy(src_pdfs[0], raw_tmp / "03690.pdf")  # numeric

    result = _run_l1_cli("--all", pythonpath_prefix=pp_prefix)

    has_skip = "[SKIP]" in result.stderr and "filename does not match" in result.stderr
    assert has_skip, f"Expected [SKIP] diagnostic on stderr. stderr={result.stderr[:400]}"
    out_files = list(sec_tmp.glob("*.json"))
    # ltn-named PDF should not produce output
    ltn_outputs = [f for f in out_files if "ltn" in f.name.lower()]
    assert not ltn_outputs, f"ltn-named files should be skipped: {[f.name for f in ltn_outputs]}"
    # Numeric-named PDF should produce output
    numeric_outputs = [f for f in out_files if f.stem.isdigit()]
    assert numeric_outputs, (
        f"At least one numeric PDF should produce output. Files: {[f.name for f in out_files]}"
    )
    assert "03690.json" in {f.name for f in out_files}


# ═══════════════════════════════════════════════════════════════════════════════
# BB-007: --limit caps PDFs processed
# ═══════════════════════════════════════════════════════════════════════════════


def test_limit_caps_pdfs_processed(tmp_path: Path) -> None:
    """--limit N must process at most N PDFs."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    src_pdfs = sorted(RAW_PDFS_DIR.glob("*.pdf"))
    if not src_pdfs:
        pytest.skip("No source PDFs available")
    # Copy with proper numeric names
    for i, stem in enumerate(["00001", "00002", "00003", "00004"]):
        shutil.copy(src_pdfs[0], raw_tmp / f"{stem}.pdf")

    limit = 2
    _run_l1_cli(
        "--all",
        "--limit",
        str(limit),
        pythonpath_prefix=pp_prefix,
    )
    out_files = list(sec_tmp.glob("*.json"))
    assert len(out_files) <= limit, (
        f"limit={limit} but produced {len(out_files)}: {[f.name for f in out_files]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-008: Corrupt PDF error handling
# ═══════════════════════════════════════════════════════════════════════════════


def test_corrupt_pdf_logs_error_does_not_crash(tmp_path: Path) -> None:
    """A corrupt PDF in --all logs [ERROR] to stderr, no traceback."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    (raw_tmp / "00001.pdf").write_bytes(b"this is not a real pdf document")

    result = _run_l1_cli("--all", pythonpath_prefix=pp_prefix, timeout=60)
    assert "[ERROR]" in result.stderr, f"Expected [ERROR] on stderr: {result.stderr[:400]}"
    assert "Traceback" not in result.stdout, f"Traceback leaked to stdout: {result.stdout[:300]}"
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"Traceback leaked to stderr: {result.stderr[:400]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BB-009: --force skip vs overwrite (batch mode)
# ═══════════════════════════════════════════════════════════════════════════════


def test_force_false_skips_existing_output(tmp_path: Path) -> None:
    """Without --force, batch mode skips existing output files."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    _copy_pdf_with_name(raw_tmp, "03690")

    existing = sec_tmp / "03690.json"
    original_content = '{"original": true, "company_file": "fake.pdf"}'
    existing.write_text(original_content, encoding="utf-8")

    result = _run_l1_cli("--all", pythonpath_prefix=pp_prefix)
    assert existing.read_text(encoding="utf-8") == original_content, (
        "Output overwritten despite --force not set"
    )
    assert "[SKIP]" in result.stderr, f"Expected [SKIP] on stderr: {result.stderr[:300]}"
    assert "exists" in result.stderr, f"Expected 'exists': {result.stderr[:300]}"


def test_force_true_overwrites_existing_output(tmp_path: Path) -> None:
    """With --force, batch mode overwrites existing output."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    _copy_pdf_with_name(raw_tmp, "03690")

    existing = sec_tmp / "03690.json"
    original_content = '{"original": true, "company_file": "fake.pdf"}'
    existing.write_text(original_content, encoding="utf-8")

    result = _run_l1_cli("--all", "--force", pythonpath_prefix=pp_prefix)
    new_content = existing.read_text(encoding="utf-8")
    assert new_content != original_content, (
        f"Output NOT overwritten despite --force. exit={result.returncode}"
    )
    data = json.loads(new_content)
    assert data["hk_ticker"] == "03690"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-010: Diagnostics go to stderr not stdout
# ═══════════════════════════════════════════════════════════════════════════════


def test_diagnostic_messages_go_to_stderr(tmp_path: Path) -> None:
    """[SKIP]/[WARN] diagnostics go to stderr only, not stdout."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    _copy_pdf_with_name(raw_tmp, "03690")

    existing = sec_tmp / "03690.json"
    existing.write_text('{"existing": true}', encoding="utf-8")

    result = _run_l1_cli("--all", pythonpath_prefix=pp_prefix)
    assert "[SKIP]" not in result.stdout, f"[SKIP] leaked to stdout: {result.stdout[:300]}"
    assert "[SKIP]" in result.stderr, f"[SKIP] missing from stderr: {result.stderr[:300]}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-011: Empty directory warning
# ═══════════════════════════════════════════════════════════════════════════════


def test_empty_dir_produces_warn_on_stderr(tmp_path: Path) -> None:
    """Empty raw_dir in --all mode produces [WARN] on stderr."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    result = _run_l1_cli("--all", pythonpath_prefix=pp_prefix)
    assert "[WARN]" in result.stderr, f"[WARN] missing from stderr: {result.stderr[:300]}"
    assert "[WARN]" not in result.stdout, f"[WARN] leaked to stdout: {result.stdout[:300]}"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-012: Ticker from filename is authoritative
# ═══════════════════════════════════════════════════════════════════════════════


def test_ticker_from_filename_is_authoritative(tmp_path: Path) -> None:
    """hk_ticker matches zero-padded filename stem, not cover ticker.
    This is true even when the PDF cover contains a different ticker."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    # Copy a real PDF with a ticker-style name; cover may have a different
    # ticker, but filename is authoritative per Task 004 spec.
    pdf = _copy_pdf_with_name(raw_tmp, "03690")
    expected_ticker = "03690"

    result = _run_l1_cli(str(pdf), pythonpath_prefix=pp_prefix)
    assert result.returncode == 0

    data = _get_output_json(sec_tmp, expected_ticker)
    assert data["hk_ticker"] == expected_ticker, (
        f"Expected hk_ticker={expected_ticker} from filename, got {data['hk_ticker']}"
    )
    # Output filename also uses ticker
    out_file = sec_tmp / f"{expected_ticker}.json"
    assert out_file.exists(), f"Output file named {out_file.name}, expected {expected_ticker}.json"


# ═══════════════════════════════════════════════════════════════════════════════
# BB-013: Single-file --force skip/overwrite
# ═══════════════════════════════════════════════════════════════════════════════


def test_single_file_force_false_skips_existing(tmp_path: Path) -> None:
    """CR-005: Single-file without --force skips existing output."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    pdf = _copy_pdf_with_name(raw_tmp, "03690")

    existing = sec_tmp / "03690.json"
    original_content = '{"original": true, "company_file": "fake.pdf"}'
    existing.write_text(original_content, encoding="utf-8")

    result = _run_l1_cli(str(pdf), pythonpath_prefix=pp_prefix)
    assert "[SKIP]" in result.stderr, f"Expected [SKIP] on stderr: {result.stderr[:300]}"
    assert existing.read_text(encoding="utf-8") == original_content, (
        "Output overwritten despite --force not set"
    )


def test_single_file_force_true_overwrites_existing(tmp_path: Path) -> None:
    """CR-005: Single-file with --force overwrites existing output."""
    raw_tmp = tmp_path / "raw"
    sec_tmp = tmp_path / "sections"
    raw_tmp.mkdir()
    sec_tmp.mkdir()
    pp_prefix = _make_config_override(tmp_path, raw_tmp, sec_tmp)

    pdf = _copy_pdf_with_name(raw_tmp, "03690")

    existing = sec_tmp / "03690.json"
    original_content = '{"original": true, "company_file": "fake.pdf"}'
    existing.write_text(original_content, encoding="utf-8")

    result = _run_l1_cli(str(pdf), "--force", pythonpath_prefix=pp_prefix)
    new_content = existing.read_text(encoding="utf-8")
    assert new_content != original_content, (
        f"Output NOT overwritten despite --force. exit={result.returncode}"
    )
    data = json.loads(new_content)
    assert data["hk_ticker"] == "03690"
