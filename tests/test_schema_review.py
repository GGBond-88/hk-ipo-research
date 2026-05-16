"""Tests for src/hk_ipo/schema_review.py — batch category_proposed reporter."""

from __future__ import annotations

import json
from pathlib import Path

from hk_ipo.schema_review import _scan_dir, generate_report

# ── Tests: empty directory ────────────────────────────────────────────────────

class TestEmptyDirectory:
    def test_report_runs_without_crashing_on_empty_dir(self, tmp_path: Path):
        """generate_report on an empty directory must not raise."""
        report = generate_report(tmp_path)
        assert isinstance(report, str)

    def test_report_mentions_zero_files(self, tmp_path: Path):
        report = generate_report(tmp_path)
        assert "Files scanned     : 0" in report

    def test_report_mentions_no_proposed(self, tmp_path: Path):
        report = generate_report(tmp_path)
        assert "No category_proposed" in report

    def test_scan_dir_empty(self, tmp_path: Path):
        result = _scan_dir(tmp_path)
        assert result["files_scanned"] == 0
        assert result["total_uses"] == 0
        assert result["uses_with_proposed"] == 0
        assert result["proposed_values"] == []


# ── Tests: files with category_proposed values ────────────────────────────────

def _write_extracted(tmp_path: Path, stem: str, uses: list[dict]) -> Path:
    """Write a minimal extracted JSON file to tmp_path."""
    data = {
        "company_file": f"{stem}.pdf",
        "hk_ticker": "1234",
        "document_date": "2024-01-01",
        "total_net_proceeds_hkd_million": 1000.0,
        "currency": "HKD",
        "uses": uses,
    }
    path = tmp_path / f"{stem}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class TestCategoryProposedDetection:
    def test_finds_category_proposed_values(self, tmp_path: Path):
        uses = [
            {
                "use_id": "use_001",
                "parent_id": None,
                "category": "Working capital",
                "category_proposed": "IPO listing expenses",
                "category_raw": "listing costs",
                "amount_hkd_million": 100.0,
                "percentage": 10.0,
                "description": "Listing costs.",
                "source_text": "approximately 10%...",
            }
        ]
        _write_extracted(tmp_path, "company_a", uses)
        result = _scan_dir(tmp_path)
        assert result["files_scanned"] == 1
        assert result["uses_with_proposed"] == 1
        assert "IPO listing expenses" in result["proposed_values"]

    def test_skips_validated_and_error_files(self, tmp_path: Path):
        """Files matching *.validated.json and *.error.json must be skipped."""
        uses = [{"use_id": "use_001", "parent_id": None, "category": "Working capital",
                 "category_proposed": "something", "category_raw": "x",
                 "amount_hkd_million": 100.0, "percentage": 10.0,
                 "description": "x", "source_text": "x"}]
        data = {
            "company_file": "x.pdf",
            "hk_ticker": "1234",
            "document_date": "2024-01-01",
            "total_net_proceeds_hkd_million": 1000.0,
            "currency": "HKD",
            "uses": uses,
        }
        # Write as validated and error variants — these should be skipped
        (tmp_path / "company_a.validated.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        (tmp_path / "company_a.error.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        result = _scan_dir(tmp_path)
        assert result["files_scanned"] == 0
        assert result["uses_with_proposed"] == 0

    def test_aggregates_across_multiple_files(self, tmp_path: Path):
        uses_a = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital",
                "category_proposed": "Environmental compliance costs",
                "category_raw": "env costs", "amount_hkd_million": 100.0,
                "percentage": 10.0, "description": "Env.", "source_text": "~10%",
            }
        ]
        uses_b = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital",
                "category_proposed": "Environmental compliance costs",
                "category_raw": "env costs", "amount_hkd_million": 200.0,
                "percentage": 20.0, "description": "Env.", "source_text": "~20%",
            }
        ]
        _write_extracted(tmp_path, "company_a", uses_a)
        _write_extracted(tmp_path, "company_b", uses_b)
        result = _scan_dir(tmp_path)
        assert result["files_scanned"] == 2
        assert result["uses_with_proposed"] == 2
        assert result["proposed_values"].count("Environmental compliance costs") == 2

    def test_report_includes_recommendation_for_multi_file_cluster(self, tmp_path: Path):
        """When the same proposed value appears in ≥2 files, the report recommends promotion."""
        uses_a = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital",
                "category_proposed": "Environmental compliance costs",
                "category_raw": "env costs", "amount_hkd_million": 100.0,
                "percentage": 10.0, "description": "Env.", "source_text": "~10%",
            }
        ]
        uses_b = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital",
                "category_proposed": "Environmental compliance costs",
                "category_raw": "env costs", "amount_hkd_million": 200.0,
                "percentage": 20.0, "description": "Env.", "source_text": "~20%",
            }
        ]
        _write_extracted(tmp_path, "company_a", uses_a)
        _write_extracted(tmp_path, "company_b", uses_b)
        report = generate_report(tmp_path)
        assert "Recommendation" in report or "recommendation" in report.lower()
        assert "≥2 files" in report

    def test_report_does_not_recommend_for_single_file_cluster(self, tmp_path: Path):
        """When a proposed value appears only in 1 file, no promotion recommendation."""
        uses = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital",
                "category_proposed": "Very unique purpose",
                "category_raw": "unique", "amount_hkd_million": 100.0,
                "percentage": 10.0, "description": "Unique.", "source_text": "~10%",
            }
        ]
        _write_extracted(tmp_path, "company_a", uses)
        report = generate_report(tmp_path)
        # Should mention "Very unique purpose" in report but not recommend promoting
        assert "Very unique purpose" in report
        assert "≥2 files" not in report

    def test_report_counts_correct_files_and_uses(self, tmp_path: Path):
        uses_no_proposed = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital", "category_proposed": None,
                "category_raw": "wc", "amount_hkd_million": 100.0,
                "percentage": 10.0, "description": "WC.", "source_text": "~10%",
            }
        ]
        uses_with_proposed = [
            {
                "use_id": "use_001", "parent_id": None,
                "category": "Working capital",
                "category_proposed": "Novel purpose",
                "category_raw": "novel", "amount_hkd_million": 200.0,
                "percentage": 20.0, "description": "Novel.", "source_text": "~20%",
            }
        ]
        _write_extracted(tmp_path, "company_a", uses_no_proposed)
        _write_extracted(tmp_path, "company_b", uses_with_proposed)
        result = _scan_dir(tmp_path)
        assert result["files_scanned"] == 2
        assert result["total_uses"] == 2
        assert result["uses_with_proposed"] == 1
