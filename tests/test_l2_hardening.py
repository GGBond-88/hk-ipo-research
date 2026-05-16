"""Tests for L2 pipeline hardening (Prompt 2).

Coverage:
  - 429 retry: mock openai.RateLimitError with Retry-After header → sleep called with that value
  - Skip logic: if output file exists and force=False, process_single skips
  - Anchor-failure warning: _extend_source_text logs WARNING when anchor not found
  - _extract_total_proceeds returns last match when multiple figures present
  - process_all returns correct summary dict shape
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from hk_ipo.l2_extraction import (
    _extend_source_text,
    _extract_total_proceeds,
    _run_with_retry,
    process_all,
    process_single,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_section_json(tmp_path: Path, stem: str = "test_section") -> Path:
    """Write a minimal section JSON file to tmp_path."""
    data = {
        "company_file": f"{stem}.pdf",
        "hk_ticker": "1234",
        "document_date": "2024-01-01",
        "section_title": "USE OF PROCEEDS",
        "start_page": 1,
        "end_page": 3,
        "text": (
            "We estimate that we will receive net proceeds of approximately "
            "HK$1000.0 million. We intend to use the net proceeds for the "
            "following purposes:\n\n"
            "- Approximately 100% or HK$1000.0 million will be used for "
            "working capital and general corporate purposes.\n"
        ),
        "tables": [],
        "extraction_method": "text",
    }
    path = tmp_path / f"{stem}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _make_extracted_json(tmp_path: Path, stem: str = "test_section") -> Path:
    """Write a minimal extracted (L2 output) JSON file to tmp_path."""
    data = {
        "company_file": f"{stem}.pdf",
        "hk_ticker": "1234",
        "document_date": "2024-01-01",
        "total_net_proceeds_hkd_million": 1000.0,
        "currency": "HKD",
        "uses": [
            {
                "use_id": "use_001",
                "parent_id": None,
                "category": "Working capital",
                "category_proposed": None,
                "category_raw": "working capital",
                "amount_hkd_million": 1000.0,
                "percentage": 100.0,
                "description": "Working capital.",
                "source_text": "Approximately 100%...",
            }
        ],
        "validation_preview": {
            "percentage_sum": 100.0,
            "top_level_count": 1,
            "total_items_count": 1,
        },
    }
    path = tmp_path / f"{stem}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ── Test: 429 retry with Retry-After header ───────────────────────────────────

class TestRateLimitRetry:
    def test_429_retry_sleeps_retry_after_value(self):
        """When RateLimitError has a Retry-After header, sleep that many seconds."""
        import openai

        # Build a mock response with Retry-After header
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "30"}

        # RateLimitError is a subclass of APIStatusError
        rate_limit_err = openai.RateLimitError(
            message="rate limit",
            response=mock_response,
            body=None,
        )

        call_count = 0

        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise rate_limit_err
            return "success"

        with patch("hk_ipo.l2_extraction.time.sleep") as mock_sleep:
            result = _run_with_retry(flaky_fn, max_retries=3)

        assert result == "success"
        # sleep should have been called with 30 (from Retry-After header)
        mock_sleep.assert_called_once_with(30.0)

    def test_429_retry_uses_backoff_when_no_retry_after(self):
        """When RateLimitError has no Retry-After header, use exponential backoff."""
        import openai

        mock_response = MagicMock()
        mock_response.headers = {}  # No Retry-After

        rate_limit_err = openai.RateLimitError(
            message="rate limit",
            response=mock_response,
            body=None,
        )

        call_count = 0

        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise rate_limit_err
            return "ok"

        with patch("hk_ipo.l2_extraction.time.sleep") as mock_sleep:
            result = _run_with_retry(flaky_fn, max_retries=3)

        assert result == "ok"
        # Backoff for attempt 0 → sleep(1) [2^0 = 1]
        mock_sleep.assert_called_once_with(1)

    def test_max_retries_is_5_by_default(self):
        """Default max_retries for _run_with_retry must be 5."""
        import inspect
        sig = inspect.signature(_run_with_retry)
        assert sig.parameters["max_retries"].default == 5


# ── Test: skip logic ──────────────────────────────────────────────────────────

class TestSkipLogic:
    def test_process_single_skips_if_output_exists(self, tmp_path: Path):
        """If output .json already exists and force=False, process_single skips."""
        sections_dir = tmp_path / "sections"
        extracted_dir = tmp_path / "extracted"
        sections_dir.mkdir()
        extracted_dir.mkdir()

        stem = "test_section"
        section_file = _make_section_json(sections_dir, stem)
        # Pre-create the output file
        _make_extracted_json(extracted_dir, stem)

        # process_single should skip without calling extract_section
        with patch("hk_ipo.l2_extraction.extract_section") as mock_extract:
            result = process_single(section_file, extracted_dir, force=False)

        mock_extract.assert_not_called()
        # result should be the pre-existing file contents
        assert result["hk_ticker"] == "1234"

    def test_process_single_processes_if_force_true(self, tmp_path: Path):
        """If force=True, process_single re-processes even if output exists."""
        sections_dir = tmp_path / "sections"
        extracted_dir = tmp_path / "extracted"
        sections_dir.mkdir()
        extracted_dir.mkdir()

        stem = "test_section"
        section_file = _make_section_json(sections_dir, stem)
        # Pre-create the output file
        _make_extracted_json(extracted_dir, stem)

        mock_result = {
            "company_file": f"{stem}.pdf",
            "hk_ticker": "1234",
            "document_date": "2024-01-01",
            "total_net_proceeds_hkd_million": 999.0,
            "currency": "HKD",
            "uses": [],
            "validation_preview": {
                "percentage_sum": 0.0,
                "top_level_count": 0,
                "total_items_count": 0,
            },
        }

        with patch("hk_ipo.l2_extraction.extract_section", return_value=mock_result):
            result = process_single(section_file, extracted_dir, force=True)

        assert result["total_net_proceeds_hkd_million"] == 999.0

    def test_process_all_skips_existing_and_returns_summary(self, tmp_path: Path):
        """process_all with existing output file → skipped count > 0, no API call."""
        sections_dir = tmp_path / "sections"
        extracted_dir = tmp_path / "extracted"
        sections_dir.mkdir()
        extracted_dir.mkdir()

        stem = "test_section"
        _make_section_json(sections_dir, stem)
        _make_extracted_json(extracted_dir, stem)

        with patch("hk_ipo.l2_extraction.extract_section") as mock_extract:
            summary = process_all(sections_dir, extracted_dir, max_workers=1, force=False)

        mock_extract.assert_not_called()
        assert summary["total"] == 1
        assert isinstance(summary, dict)
        assert "succeeded" in summary
        assert "failed" in summary
        assert "skipped" in summary


# ── Test: anchor failure warning ──────────────────────────────────────────────

class TestAnchorFailureWarning:
    def test_extend_source_text_warns_when_anchor_not_found(self, caplog):
        """When anchor text can't be found, a WARNING is logged."""
        text = "This text does not contain the extraction."
        extraction = "Some totally different text that is not in the document."

        with caplog.at_level(logging.WARNING, logger="hk_ipo.l2_extraction"):
            result = _extend_source_text(
                extraction, text, use_id="use_001", company_file="test.pdf"
            )

        # Should return the original extraction_text unchanged
        assert result == extraction
        # Should have logged a WARNING
        assert any(
            "anchor not found" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )

    def test_extend_source_text_no_warning_when_found(self, caplog):
        """When anchor IS found, no warning is logged."""
        extraction = "Approximately 35% will be used for R&D."
        text = f"Intro text.\n\n- {extraction}\n- Next bullet."

        with caplog.at_level(logging.WARNING, logger="hk_ipo.l2_extraction"):
            _extend_source_text(
                extraction, text, use_id="use_001", company_file="test.pdf"
            )

        anchor_warns = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "anchor not found" in r.message
        ]
        assert anchor_warns == []

    def test_extend_source_text_includes_use_id_in_warning(self, caplog):
        """Warning message includes the use_id for easy debugging."""
        text = "Something completely different."
        extraction = "Anchor that will not be found."

        with caplog.at_level(logging.WARNING, logger="hk_ipo.l2_extraction"):
            _extend_source_text(extraction, text, use_id="use_042", company_file="x.pdf")

        assert any(
            "use_042" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )


# ── Test: _extract_total_proceeds returns last match ─────────────────────────

class TestExtractTotalProceeds:
    def test_returns_last_match_when_multiple_figures(self):
        """When multiple HK$ figures appear, the LAST one is returned."""
        text = (
            "We expect net proceeds of approximately HK$500.0 million. "
            "After deducting fees, net proceeds of approximately HK$480.0 million "
            "will be received. "
            "The net proceeds are HK$450.0 million."
        )
        value, currency, candidates = _extract_total_proceeds(text)
        # Last match should be 450.0
        assert value == 450.0
        assert currency == "HKD"
        assert len(candidates) == 3

    def test_returns_none_when_no_match(self):
        """When no proceeds figure is found, returns (None, 'HKD', [])."""
        text = "This section discusses general corporate matters."
        value, currency, candidates = _extract_total_proceeds(text)
        assert value is None
        assert currency == "HKD"
        assert candidates == []

    def test_returns_single_match_directly(self):
        """With exactly one match, candidates has one entry and value == candidates[0]."""
        text = (
            "We estimate that we will receive net proceeds of approximately "
            "HK$31,123.0 million."
        )
        value, currency, candidates = _extract_total_proceeds(text)
        assert value == 31123.0
        assert candidates == [31123.0]

    def test_candidates_captures_all_distinct_values(self):
        """All found values appear in candidates (may include duplicates if repeated)."""
        text = (
            "Net proceeds of approximately HK$1000.0 million. "
            "Net proceeds of approximately HK$2000.0 million. "
            "Net proceeds of approximately HK$3000.0 million."
        )
        value, _, candidates = _extract_total_proceeds(text)
        assert value == 3000.0
        assert 1000.0 in candidates
        assert 2000.0 in candidates
        assert 3000.0 in candidates

    def test_returns_tuple_of_three(self):
        """Return value is a 3-tuple (value, currency, candidates)."""
        text = "Net proceeds of approximately HK$100.0 million."
        result = _extract_total_proceeds(text)
        assert len(result) == 3
