"""Tests for L2 pipeline hardening.

Coverage:
  - 429 retry: mock openai.RateLimitError with Retry-After header -> sleep called with that value
  - Skip logic: if output file exists and force=False, process_single skips
  - extract_section: correct structure, drops items without financials
  - Self-correction loop: retries once on L3 failure, marks needs_human_review on double failure
  - process_single no API call when output file already exists
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from hk_ipo.l2_extraction import (
    _run_with_retry,
    extract_section,
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
        # Backoff for attempt 0 -> sleep(1) [2^0 = 1]
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
        """process_all with existing output file -> skipped count > 0, no API call."""
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


# ── Test: extract_section ─────────────────────────────────────────────────────

class TestExtractSection:
    """Tests for the new direct-LLM extract_section."""

    def _llm_ok(self) -> dict:
        """A valid LLM response that will pass L3."""
        return {
            "total_net_proceeds_hkd_million": 1000.0,
            "uses": [
                {
                    "category": "Working capital",
                    "category_proposed": None,
                    "category_raw": "working capital and general corporate purposes",
                    "percentage": 100.0,
                    "amount_hkd_million": 1000.0,
                    "description": "General working capital.",
                    "source_text": "Approximately 100% or HK$1,000 million for working capital.",
                }
            ],
        }

    def _llm_bad(self) -> dict:
        """An LLM response that fails L3 (pct sum != 100)."""
        return {
            "total_net_proceeds_hkd_million": 1000.0,
            "uses": [
                {
                    "category": "Working capital",
                    "category_proposed": None,
                    "category_raw": "working capital",
                    "percentage": 50.0,
                    "amount_hkd_million": 500.0,
                    "description": "Only half.",
                    "source_text": "Approximately 50% for working capital.",
                }
            ],
        }

    def _section(self) -> dict:
        return {
            "company_file": "test.pdf",
            "hk_ticker": "1234",
            "document_date": "2024-01-01",
            "section_title": "USE OF PROCEEDS",
            "start_page": 1,
            "end_page": 2,
            "text": (
                "We estimate net proceeds of approximately HK$1,000 million.\n\n"
                "- Approximately 100% or HK$1,000 million for working capital "
                "and general corporate purposes.\n"
            ),
            "tables": [],
            "extraction_method": "toc",
        }

    def test_returns_correct_structure(self):
        with patch("hk_ipo.l2_extraction._call_llm", return_value=self._llm_ok()):
            result = extract_section(self._section())
        assert result["total_net_proceeds_hkd_million"] == 1000.0
        assert len(result["uses"]) == 1
        assert result["uses"][0]["use_id"] == "use_001"
        assert "validation_preview" in result
        assert result.get("schema_version") == "1.0"

    def test_drops_items_with_no_financials(self):
        response = {
            "total_net_proceeds_hkd_million": 1000.0,
            "uses": [
                {"category": "Working capital", "category_raw": "wc",
                 "percentage": None, "amount_hkd_million": None,
                 "description": "empty", "source_text": "..."},
                {"category": "Working capital", "category_raw": "wc",
                 "percentage": 100.0, "amount_hkd_million": 1000.0,
                 "description": "real", "source_text": "Approximately 100%..."},
            ],
        }
        with patch("hk_ipo.l2_extraction._call_llm", return_value=response):
            result = extract_section(self._section())
        assert len(result["uses"]) == 1

    def test_self_correction_retries_on_l3_failure(self):
        """First call fails L3; second call (correction) succeeds -- two LLM calls total."""
        call_count = 0

        def fake_call_llm(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return self._llm_bad() if call_count == 1 else self._llm_ok()

        with patch("hk_ipo.l2_extraction._call_llm", side_effect=fake_call_llm), \
             patch("hk_ipo.l2_extraction._call_llm_with_prompt", side_effect=fake_call_llm):
            result = extract_section(self._section())

        assert call_count == 2
        assert result.get("needs_human_review") is not True

    def test_marks_needs_human_review_when_both_calls_fail(self):
        """Both calls fail L3 -> needs_human_review=True."""
        with patch("hk_ipo.l2_extraction._call_llm", return_value=self._llm_bad()), \
             patch("hk_ipo.l2_extraction._call_llm_with_prompt", return_value=self._llm_bad()):
            result = extract_section(self._section())
        assert result.get("needs_human_review") is True

    def test_no_api_call_when_skipped(self, tmp_path):
        """process_single skips existing output without calling LLM."""
        sections_dir = tmp_path / "sections"
        extracted_dir = tmp_path / "extracted"
        sections_dir.mkdir()
        extracted_dir.mkdir()
        section_file = _make_section_json(sections_dir)
        _make_extracted_json(extracted_dir)
        with patch("hk_ipo.l2_extraction._call_llm") as mock_llm:
            process_single(section_file, extracted_dir, force=False)
        mock_llm.assert_not_called()


# ── Test: empty-response guard ────────────────────────────────────────────────

class TestEmptyResponseGuard:
    """_call_llm and _call_llm_with_prompt must raise ValueError on empty content."""

    def _mock_response(self, content: str) -> MagicMock:
        choice = MagicMock()
        choice.message.content = content
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    def test_call_llm_raises_on_empty_content(self):
        import pytest

        from hk_ipo.l2_extraction import _call_llm

        with patch(
            "hk_ipo.l2_extraction._openai_client"
        ) as mock_client:
            mock_client.chat.completions.create.return_value = self._mock_response("")
            with pytest.raises(ValueError, match="empty response"):
                _call_llm("some text")

    def test_call_llm_with_prompt_raises_on_empty_content(self):
        import pytest

        from hk_ipo.l2_extraction import _call_llm_with_prompt

        with patch(
            "hk_ipo.l2_extraction._openai_client"
        ) as mock_client:
            mock_client.chat.completions.create.return_value = self._mock_response("   ")
            with pytest.raises(ValueError, match="empty response"):
                _call_llm_with_prompt("some prompt")

    def test_self_correction_empty_response_sets_needs_human_review(self):
        """If correction call returns empty (ValueError), mark needs_human_review=True."""
        section = {
            "company_file": "test.pdf",
            "hk_ticker": "9999",
            "document_date": "2024-01-01",
            "section_title": "USE OF PROCEEDS",
            "start_page": 1,
            "end_page": 2,
            "text": "Net proceeds HK$1,000M.\n- 50% or HK$500M for working capital.\n",
            "tables": [],
            "extraction_method": "toc",
        }
        bad_response = {
            "total_net_proceeds_hkd_million": 1000.0,
            "uses": [{"category": "Working capital", "category_raw": "wc",
                       "percentage": 50.0, "amount_hkd_million": 500.0,
                       "description": "wc", "source_text": "50%..."}],
        }

        with patch("hk_ipo.l2_extraction._call_llm", return_value=bad_response), \
             patch(
                 "hk_ipo.l2_extraction._call_llm_with_prompt",
                 side_effect=ValueError("LLM returned empty response (possible context overflow)"),
             ):
            result = extract_section(section)

        assert result.get("needs_human_review") is True
