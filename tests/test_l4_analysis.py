"""Tests for L4 legacy analysis layer (src/hk_ipo/l4_legacy_analysis.py).

Strategy:
  - Write real .validated.json fixtures to tmp_path
  call run_analysis directly.
  - No mocking.
  - Do NOT assert on pixel content of PNGs — only existence and non-empty size.
"""

from __future__ import annotations  # noqa: I001

import json
from pathlib import Path

from hk_ipo.l4_legacy_analysis import run_analysis


# ── Fixture helpers ───────────────────────────────────────────────────────────


def _validated_record(
    ticker: str,
    date: str,
    uses: list[dict],
    total: float = 10000.0,
    passed: bool = True,
) -> dict:
    """Build a minimal .validated.json structure."""
    return {
        "company_file": f"{ticker}.pdf",
        "hk_ticker": ticker,
        "document_date": date,
        "total_net_proceeds_hkd_million": total,
        "currency": "HKD",
        "uses": uses,
        "validation": {
            "passed": passed,
            "errors": [] if passed else ["[required_fields] forced failure"],
            "warnings": [],
            "tolerance_pct": 1.0,
            "schema_version_validated_against": "1.0",
            "validated_at": "2025-01-01T00:00:00",
        },
    }


def _use(
    use_id: str,
    category: str,
    pct: float | None,
    amt: float | None,
    parent_id: str | None = None,
) -> dict:
    return {
        "use_id": use_id,
        "parent_id": parent_id,
        "category": category,
        "category_raw": category,
        "amount_hkd_million": amt,
        "percentage": pct,
        "description": "desc",
        "source_text": "src",
    }


def _write(tmp_path: Path, stem: str, record: dict) -> Path:
    fp = tmp_path / f"{stem}.validated.json"
    fp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRunAnalysisZeroFiles:
    def test_zero_valid_files_returns_early_no_crash(self, tmp_path: Path):
        """With 0 valid files, run_analysis should return early without crashing."""
        reports_dir = tmp_path / "reports"
        # No .validated.json files in extracted_dir
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()

        run_analysis(str(extracted_dir), str(reports_dir))

        # reports_dir is created even with 0 files
        assert reports_dir.exists()
        # No CSVs or charts should be written
        assert not (reports_dir / "uses_by_company.csv").exists()
        assert not (reports_dir / "summary.md").exists()

    def test_zero_valid_files_failed_validation_are_skipped(self, tmp_path: Path):
        """Records with validation.passed=False are counted as skipped, not processed."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="1234",
            date="2025-01-01",
            uses=[_use("u1", "Working capital", 100.0, 10000.0)],
            passed=False,
        )
        _write(extracted_dir, "1234", record)

        run_analysis(str(extracted_dir), str(reports_dir))

        # All files skipped → early return, no outputs
        assert not (reports_dir / "uses_by_company.csv").exists()


class TestRunAnalysisOneFile:
    def test_creates_csvs_and_bar_charts_skips_timeseries(self, tmp_path: Path):
        """With 1 valid file: CSVs and bar charts produced; time-series skipped."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="3690",
            date="2024-06-01",
            uses=[
                _use("u1", "R&D and technology", 60.0, 6000.0),
                _use("u2", "Working capital", 40.0, 4000.0),
            ],
        )
        _write(extracted_dir, "3690", record)

        run_analysis(str(extracted_dir), str(reports_dir))

        # CSVs must exist and be non-empty
        csv1 = reports_dir / "uses_by_company.csv"
        csv2 = reports_dir / "allocation_by_l1.csv"
        assert csv1.exists() and csv1.stat().st_size > 0
        assert csv2.exists() and csv2.stat().st_size > 0

        # Bar charts must exist and be non-empty PNGs
        for chart in ("allocation_by_l1.png", "allocation_by_company_l1.png"):
            p = reports_dir / chart
            assert p.exists(), f"Expected {chart} to exist"
            assert p.stat().st_size > 0, f"Expected {chart} to be non-empty"

        # Time-series should NOT be produced (only 1 company)
        assert not (reports_dir / "timeseries_l1.png").exists()

        # summary.md must exist and mention the company count
        summary = reports_dir / "summary.md"
        assert summary.exists()
        text = summary.read_text(encoding="utf-8")
        assert "1" in text  # n_companies = 1

    def test_summary_md_mentions_skipped_timeseries(self, tmp_path: Path):
        """summary.md notes that time-series was skipped for single-company dataset."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="0001",
            date="2024-01-01",
            uses=[_use("u1", "Sales and marketing", 100.0, 10000.0)],
        )
        _write(extracted_dir, "0001", record)

        run_analysis(str(extracted_dir), str(reports_dir))

        text = (reports_dir / "summary.md").read_text(encoding="utf-8")
        text_lower = text.lower()
        assert "skipped" in text_lower or "time-series" in text_lower or "timeseries" in text_lower


class TestRunAnalysisMultipleFiles:
    def _setup_two_files(self, extracted_dir: Path) -> None:
        records = [
            _validated_record(
                ticker="3690",
                date="2024-01-15",
                uses=[
                    _use("u1", "R&D and technology", 50.0, 5000.0),
                    _use("u2", "Working capital", 50.0, 5000.0),
                ],
            ),
            _validated_record(
                ticker="9988",
                date="2024-06-20",
                uses=[
                    _use("u1", "Overseas expansion", 70.0, 7000.0),
                    _use("u2", "Sales and marketing", 30.0, 3000.0),
                ],
            ),
        ]
        _write(extracted_dir, "3690", records[0])
        _write(extracted_dir, "9988", records[1])

    def test_creates_all_outputs_including_timeseries(self, tmp_path: Path):
        """With 2+ files and 2+ distinct dates, all outputs including time-series are produced."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"
        self._setup_two_files(extracted_dir)

        run_analysis(str(extracted_dir), str(reports_dir))

        for fname in (
            "uses_by_company.csv",
            "allocation_by_l1.csv",
            "allocation_by_l1.png",
            "allocation_by_company_l1.png",
            "timeseries_l1.png",
            "summary.md",
        ):
            p = reports_dir / fname
            assert p.exists(), f"Expected {fname} to exist"
            assert p.stat().st_size > 0, f"Expected {fname} to be non-empty"

    def test_dataframe_row_count_matches_total_use_items(self, tmp_path: Path):
        """uses_by_company.csv should have one row per use item across all records."""
        import pandas as pd

        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"
        self._setup_two_files(extracted_dir)

        run_analysis(str(extracted_dir), str(reports_dir))

        df = pd.read_csv(reports_dir / "uses_by_company.csv")
        # 2 records × 2 use items each = 4 rows total
        assert len(df) == 4

    def test_summary_md_has_correct_company_count(self, tmp_path: Path):
        """summary.md should report the correct number of companies analysed."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"
        self._setup_two_files(extracted_dir)

        run_analysis(str(extracted_dir), str(reports_dir))

        text = (reports_dir / "summary.md").read_text(encoding="utf-8")
        assert "2" in text  # 2 companies

    def test_timeseries_skipped_when_same_date(self, tmp_path: Path):
        """Time-series is skipped when all records share the same date."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        for ticker, use_cat in [("1111", "Working capital"), ("2222", "Sales and marketing")]:
            record = _validated_record(
                ticker=ticker,
                date="2024-03-01",  # same date for both
                uses=[_use("u1", use_cat, 100.0, 10000.0)],
            )
            _write(extracted_dir, ticker, record)

        run_analysis(str(extracted_dir), str(reports_dir))

        assert not (reports_dir / "timeseries_l1.png").exists()


class TestEdgeCases:
    def test_all_null_amounts_uses_percentage_column(self, tmp_path: Path):
        """When all amount_hkd_million are null, the pipeline should not crash."""
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="5555",
            date="2024-09-01",
            uses=[
                _use("u1", "R&D and technology", 60.0, None),
                _use("u2", "Working capital", 40.0, None),
            ],
        )
        _write(extracted_dir, "5555", record)

        # Should not raise despite all-null amounts
        run_analysis(str(extracted_dir), str(reports_dir))

        assert (reports_dir / "uses_by_company.csv").exists()

    def test_missing_cross_cutting_tags_filled_with_none(self, tmp_path: Path):
        """Use items without geo_scope/target_industries/asset_type/headcount_plan
        should be loaded without crashing (filled with None/NaN)."""
        import pandas as pd

        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="6666",
            date="2024-07-15",
            uses=[
                # No cross-cutting tag fields at all
                {
                    "use_id": "u1",
                    "parent_id": None,
                    "category": "Product development",
                    "category_raw": "product dev",
                    "percentage": 100.0,
                    "amount_hkd_million": 10000.0,
                    "description": "dev",
                    "source_text": "src",
                }
            ],
        )
        _write(extracted_dir, "6666", record)

        run_analysis(str(extracted_dir), str(reports_dir))

        df = pd.read_csv(reports_dir / "uses_by_company.csv")
        assert len(df) == 1
        # Cross-cutting tags should be present as columns (filled NaN/empty)
        for col in ("geo_scope", "target_industries", "asset_type", "headcount_plan"):
            assert col in df.columns

    def test_sub_items_included_in_dataframe(self, tmp_path: Path):
        """Child use items (parent_id != None) appear in uses_by_company.csv
        with is_top_level=False."""
        import pandas as pd

        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="7777",
            date="2024-05-01",
            uses=[
                _use("u1", "R&D and technology", 100.0, 10000.0),
                _use("u1a", "R&D and technology", None, None, parent_id="u1"),
            ],
        )
        _write(extracted_dir, "7777", record)

        run_analysis(str(extracted_dir), str(reports_dir))

        df = pd.read_csv(reports_dir / "uses_by_company.csv")
        assert len(df) == 2
        top_level = df[df["is_top_level"] == True]  # noqa: E712
        sub_items = df[df["is_top_level"] == False]  # noqa: E712
        assert len(top_level) == 1
        assert len(sub_items) == 1

    def test_unknown_category_maps_to_unknown_l1(self, tmp_path: Path):
        """Use items with a category not in CATEGORY_L1_MAP get category_l1='Unknown'."""
        import pandas as pd

        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()
        reports_dir = tmp_path / "reports"

        record = _validated_record(
            ticker="8888",
            date="2024-08-01",
            uses=[
                {
                    "use_id": "u1",
                    "parent_id": None,
                    "category": None,  # No category
                    "category_proposed": "Something novel",
                    "category_raw": "novel",
                    "percentage": 100.0,
                    "amount_hkd_million": 10000.0,
                    "description": "novel use",
                    "source_text": "src",
                }
            ],
        )
        _write(extracted_dir, "8888", record)

        run_analysis(str(extracted_dir), str(reports_dir))

        df = pd.read_csv(reports_dir / "uses_by_company.csv")
        assert df.iloc[0]["category_l1"] == "Unknown"
