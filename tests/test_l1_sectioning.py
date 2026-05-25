"""Unit tests for L1 sectioning layer (src/hk_ipo/l1_sectioning.py).

Coverage strategy:
  - Pure functions tested directly with constructed inputs (no PDF I/O).
  - PDF-coupled functions (extract_use_of_proceeds) tested via mock to
    verify output schema without touching real files.
  - Regex fallback path (_locate_in_markdown) receives extra attention
    because it has never been triggered by a real PDF yet.
"""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from hk_ipo.l1_sectioning import (
    _date_from_markdown,
    _locate_in_markdown,
    _locate_in_toc_list,
    _matches_section_title,
    _parse_date_from_filename,
    _ticker_from_markdown,
    extract_use_of_proceeds,
)

# ─────────────────────────────────────────────────────────────────────────────
# Part 1a: _matches_section_title
# ─────────────────────────────────────────────────────────────────────────────


class TestMatchesSectionTitle:
    def test_uppercase_use_of_proceeds(self):
        assert _matches_section_title("USE OF PROCEEDS") is True

    def test_titlecase_use_of_proceeds(self):
        assert _matches_section_title("Use of Proceeds") is True

    def test_lowercase_use_of_proceeds(self):
        assert _matches_section_title("use of proceeds") is True

    def test_future_plans_prefix_uppercase(self):
        # All 4 real prospectuses use this exact heading
        assert _matches_section_title("FUTURE PLANS AND USE OF PROCEEDS") is True

    def test_future_plans_prefix_mixed_case(self):
        assert _matches_section_title("Future Plans and Use of Proceeds") is True

    def test_rejects_use_of_proceeds_summary(self):
        # Sub-section that appears in some prospectuses — must NOT match
        assert _matches_section_title("Use of Proceeds Summary") is False

    def test_rejects_application_of_proceeds(self):
        # Different phrasing — not in scope
        assert _matches_section_title("Application of Proceeds") is False

    def test_rejects_empty_string(self):
        assert _matches_section_title("") is False

    def test_rejects_whitespace_only(self):
        assert _matches_section_title("   ") is False

    def test_strips_surrounding_whitespace(self):
        # Titles from TOC sometimes have leading/trailing spaces
        assert _matches_section_title("  USE OF PROCEEDS  ") is True

    # ── 2026-05-25 audit: relaxed-regex variants ────────────────────────
    # The original regex missed ~24% of real prospectuses because real
    # filings vary the heading. These cases lock the relaxed pattern.

    def test_use_of_net_proceeds(self):
        assert _matches_section_title("USE OF NET PROCEEDS") is True

    def test_future_plans_and_use_of_net_proceeds(self):
        assert _matches_section_title("FUTURE PLANS AND USE OF NET PROCEEDS") is True

    def test_future_plans_use_of_net_proceeds_with_offering_suffix(self):
        # Common in main-board prospectuses (e.g. 00312.pdf)
        assert _matches_section_title(
            "FUTURE PLANS AND USE OF NET PROCEEDS FROM THE GLOBAL OFFERING"
        ) is True

    def test_use_of_net_proceeds_from_the_placing(self):
        # Placing variant (placing memoranda)
        assert _matches_section_title("USE OF NET PROCEEDS FROM THE PLACING") is True

    def test_reasons_for_the_placing_and_use_of_proceeds(self):
        # Placing memorandum variant (e.g. 00162.pdf, 00343.pdf)
        assert _matches_section_title(
            "Reasons for the Placing and use of proceeds"
        ) is True

    def test_rejects_net_proceeds_alone(self):
        # Substring of valid match but not a full title
        assert _matches_section_title("Net Proceeds") is False


# ─────────────────────────────────────────────────────────────────────────────
# Part 1b: _locate_in_toc_list
# ─────────────────────────────────────────────────────────────────────────────


class TestLocateInTocList:
    """TOC format mirrors PyMuPDF get_toc(): [[level, title, page_1based], ...]"""

    def test_normal_case_returns_correct_page_range(self):
        toc = [
            [1, "CORNERSTONE INVESTORS", 380],
            [1, "FUTURE PLANS AND USE OF PROCEEDS", 400],
            [1, "UNDERWRITING", 410],
            [1, "STRUCTURE OF THE GLOBAL OFFERING", 425],
        ]
        result = _locate_in_toc_list(toc, page_count=500)
        assert result == ("FUTURE PLANS AND USE OF PROCEEDS", 400, 409)

    def test_section_is_last_toc_entry_falls_back_to_page_count(self):
        toc = [
            [1, "DIRECTORS AND SENIOR MANAGEMENT", 380],
            [1, "FUTURE PLANS AND USE OF PROCEEDS", 400],
        ]
        result = _locate_in_toc_list(toc, page_count=420)
        assert result is not None
        title, start, end = result
        assert start == 400
        assert end == 420  # no next entry → falls back to page_count

    def test_no_matching_section_returns_none(self):
        toc = [
            [1, "RISK FACTORS", 50],
            [1, "BUSINESS", 100],
            [1, "FINANCIAL INFORMATION", 300],
        ]
        assert _locate_in_toc_list(toc, page_count=500) is None

    def test_empty_toc_returns_none(self):
        assert _locate_in_toc_list([], page_count=500) is None

    def test_multiple_matches_returns_first(self):
        # Rare, but some PDFs repeat chapter headings at different nesting
        toc = [
            [1, "FUTURE PLANS AND USE OF PROCEEDS", 400],
            [2, "USE OF PROCEEDS", 402],  # sub-entry, same keywords
            [1, "UNDERWRITING", 410],
        ]
        result = _locate_in_toc_list(toc, page_count=500)
        assert result is not None
        _, start, _ = result
        assert start == 400  # first match wins

    def test_deeper_level_next_entry_does_not_close_section(self):
        # A level-2 entry after a level-1 target should NOT end the section
        toc = [
            [1, "FUTURE PLANS AND USE OF PROCEEDS", 400],
            [2, "Future Plans", 401],  # sub-entry, level 2 > target level 1
            [2, "Use of Proceeds", 402],  # sub-entry, level 2 > target level 1
            [1, "UNDERWRITING", 410],  # same level → closes the section
        ]
        result = _locate_in_toc_list(toc, page_count=500)
        assert result is not None
        _, start, end = result
        assert start == 400
        assert end == 409  # closed by L1 "UNDERWRITING" at 410


# ─────────────────────────────────────────────────────────────────────────────
# Part 1c: _locate_in_markdown  ⚠️  regex fallback — never triggered by real PDF
# ─────────────────────────────────────────────────────────────────────────────


class TestLocateInMarkdown:
    """Tests for the regex fallback path.

    This path has never been triggered by any real prospectus (all 4 PDFs
    have TOC bookmarks). Construct synthetic Markdown to exercise it fully.
    """

    _TYPICAL_DOC = """\
# RISK FACTORS

Some risk text spanning many lines.

## FUTURE PLANS AND USE OF PROCEEDS

We intend to use the net proceeds for the following purposes:

- 45% for R&D
- 35% for overseas expansion
- 20% for working capital

## UNDERWRITING

The underwriting section begins here.

## APPENDIX
"""

    def test_finds_section_between_two_headings(self):
        result = _locate_in_markdown(self._TYPICAL_DOC, total_pages=100)
        assert result is not None
        title, start, end = result
        assert "USE OF PROCEEDS" in title.upper()
        assert 1 <= start <= end <= 100

    def test_section_ends_before_next_same_level_heading(self):
        result = _locate_in_markdown(self._TYPICAL_DOC, total_pages=100)
        assert result is not None
        _, start, end = result
        # "UNDERWRITING" heading comes after; end must be < total_pages
        assert end < 100

    def test_bold_markdown_heading_is_recognised(self):
        # pymupdf4llm sometimes emits bold paragraphs instead of # headings
        md = """\
Some preamble text.

**FUTURE PLANS AND USE OF PROCEEDS**

We intend to use the proceeds as follows:

- 50% for expansion

**UNDERWRITING**

Underwriting details.
"""
        result = _locate_in_markdown(md, total_pages=50)
        assert result is not None
        title, start, end = result
        assert "USE OF PROCEEDS" in title.upper()
        assert start >= 1
        assert end >= start

    def test_returns_none_when_section_absent(self):
        md = """\
## RISK FACTORS

Text here.

## BUSINESS

More text.
"""
        assert _locate_in_markdown(md, total_pages=100) is None

    def test_section_at_end_of_document_falls_back_to_total_pages(self):
        md = """\
## RISK FACTORS

Some text.

## USE OF PROCEEDS

Final section with no heading after it.
"""
        result = _locate_in_markdown(md, total_pages=80)
        assert result is not None
        _, start, end = result
        assert end == 80  # no next heading → end == total_pages

    def test_empty_markdown_returns_none(self):
        assert _locate_in_markdown("", total_pages=100) is None


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: output schema contract tests (extract_use_of_proceeds via mock)
# ─────────────────────────────────────────────────────────────────────────────

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


def _make_mock_doc(toc, page_count=500):
    doc = MagicMock()
    doc.get_toc.return_value = toc
    doc.page_count = page_count
    doc.__enter__ = lambda s: s
    doc.__exit__ = MagicMock(return_value=False)
    return doc


class TestExtractUsOfProceedsSchema:
    """Verify that extract_use_of_proceeds always returns the correct schema.

    PDF I/O is fully mocked
    these tests run in milliseconds.
    """

    def _run_with_toc(self, toc, pdf_path):
        doc = _make_mock_doc(toc)
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value="## USE OF PROCEEDS\n\nText.",
            ),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            result = extract_use_of_proceeds(pdf_path)
        return result

    def test_toc_path_output_contains_all_required_fields(self, tmp_path):
        toc = [[1, "FUTURE PLANS AND USE OF PROCEEDS", 400], [1, "UNDERWRITING", 410]]
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        result = self._run_with_toc(toc, str(pdf))
        assert _REQUIRED_FIELDS <= result.keys()

    def test_toc_path_extraction_method_is_toc(self, tmp_path):
        toc = [[1, "FUTURE PLANS AND USE OF PROCEEDS", 400], [1, "UNDERWRITING", 410]]
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        result = self._run_with_toc(toc, str(pdf))
        assert result["extraction_method"] == "toc"

    def test_regex_path_extraction_method_is_regex(self, tmp_path):
        # Empty TOC forces regex fallback
        doc = _make_mock_doc(toc=[], page_count=100)
        md = "## FUTURE PLANS AND USE OF PROCEEDS\n\nSome text.\n\n## UNDERWRITING\n\nMore.\n"
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4 regex")
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch("hk_ipo.l1_sectioning.pymupdf4llm.to_markdown", return_value=md),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            result = extract_use_of_proceeds(str(pdf))
        assert result["extraction_method"] == "regex"

    def test_tables_field_is_always_a_list(self, tmp_path):
        toc = [[1, "USE OF PROCEEDS", 5], [1, "NEXT CHAPTER", 10]]
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        result = self._run_with_toc(toc, str(pdf))
        assert isinstance(result["tables"], list)

    def test_extraction_method_only_valid_values(self, tmp_path):
        toc = [[1, "USE OF PROCEEDS", 5], [1, "NEXT", 10]]
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        result = self._run_with_toc(toc, str(pdf))
        assert result["extraction_method"] in ("toc", "regex")

    def test_raises_value_error_when_section_not_found(self, tmp_path):
        doc = _make_mock_doc(toc=[], page_count=100)
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4 notfound")
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value="## RISK FACTORS\n\nNo proceeds here.\n",
            ),
        ):
            with pytest.raises(ValueError, match="Cannot locate"):
                extract_use_of_proceeds(str(pdf))

    def test_output_contains_hk_ticker_and_document_date(self, tmp_path):
        """New schema fields hk_ticker and document_date must always be present."""
        toc = [[1, "USE OF PROCEEDS", 5], [1, "NEXT", 10]]
        pdf = tmp_path / "fake.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        result = self._run_with_toc(toc, str(pdf))
        assert "hk_ticker" in result
        assert "document_date" in result

    def test_cover_metadata_uses_head_md_not_separate_reads(self, tmp_path):
        """CR-004: head_md is reused for ticker + date, eliminating redundant
        pymupdf4llm calls. Before the fix, _extract_ticker and
        _extract_document_date each called pymupdf4llm.to_markdown
        independently (pages 0-2), tripling cover-page conversion cost.
        After fix, only 2 calls remain: head_md + section text extract."""
        toc = [[1, "USE OF PROCEEDS", 5], [1, "NEXT", 10]]
        doc = _make_mock_doc(toc)
        call_count = [0]  # use list for mutable counter in closure

        def counting_to_markdown(doc, pages=None):  # noqa: ARG001
            call_count[0] += 1
            return "Stock Code: 03690\nDated 12 May 2025.\n\nThe Group intends to use net proceeds."

        pdf = tmp_path / "03690.pdf"
        pdf.write_bytes(b"%PDF-1.4 meta")
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch("hk_ipo.l1_sectioning.pymupdf4llm.to_markdown", side_effect=counting_to_markdown),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            result = extract_use_of_proceeds(str(pdf))

        # TOC path: 1 call for head_md (language + ticker + date),
        # 1 call for section text = 2 total.
        # Before fix: +2 extra calls (_extract_ticker + _extract_document_date).
        assert call_count[0] <= 2, f"Expected <=2 to_markdown calls, got {call_count[0]}"
        assert result["hk_ticker"] == "03690"


# ─────────────────────────────────────────────────────────────────────────────
# Part 3: cover-page metadata helpers (_ticker_from_markdown, _date_from_markdown)
# ─────────────────────────────────────────────────────────────────────────────


class TestTickerFromMarkdown:
    """Pure-function tests — no PDF I/O, no mocking needed."""

    def test_happy_path_returns_ticker(self):
        md = "Global Offering\nStock Code: 3690\nOffer price HK$66"
        assert _ticker_from_markdown(md) == "3690"

    def test_case_insensitive_match(self):
        md = "stock code : 3750"
        assert _ticker_from_markdown(md) == "3750"

    def test_full_width_colon_accepted(self):
        md = "Stock Code：6031"
        assert _ticker_from_markdown(md) == "6031"

    def test_returns_none_when_no_match(self):
        assert _ticker_from_markdown("No ticker information here.") is None

    def test_returns_none_on_empty_string(self):
        assert _ticker_from_markdown("") is None


class TestDateFromMarkdown:
    """Pure-function tests — no PDF I/O, no mocking needed."""

    def test_cover_date_takes_precedence_over_filename(self):
        # Cover says "7 September 2018"; filename would give "2025-05-12"
        md = "The closing date for applications is 7 September 2018."
        assert _date_from_markdown(md, "2025051200005") == "2018-09-07"

    def test_uses_last_date_when_multiple_present(self):
        # Only the last date match is used (prospectus print date is near the bottom)
        md = "Founded 1 January 2000.\n\nThis prospectus is dated 12 May 2025."
        assert _date_from_markdown(md, "ltn00000000000") == "2025-05-12"

    def test_falls_back_to_filename_when_cover_has_no_date(self):
        assert _date_from_markdown("No date found here.", "ltn20180907011") == "2018-09-07"

    def test_returns_none_when_both_sources_missing(self):
        # filename "fake.pdf" has no YYYYMMDD embedded
        assert _date_from_markdown("No date.", "fake.pdf") is None


class TestParseDateFromFilename:
    def test_ltn_format(self):
        assert _parse_date_from_filename("ltn20180907011") == "2018-09-07"

    def test_numeric_format(self):
        assert _parse_date_from_filename("2025051200005") == "2025-05-12"

    def test_returns_none_for_no_date(self):
        assert _parse_date_from_filename("fake") is None

    def test_rejects_invalid_month(self):
        assert _parse_date_from_filename("ltn20181307011") is None  # month=13


# ── Task 004 — filename-derived ticker ──────────────────────────────────────


class TestTickerFromFilename:
    def test_five_digit_filename_yields_zero_padded_ticker(self):
        from hk_ipo.l1_sectioning import ticker_from_filename

        assert ticker_from_filename("01234.pdf") == "01234"

    def test_four_digit_filename_zero_pads_to_five(self):
        from hk_ipo.l1_sectioning import ticker_from_filename

        assert ticker_from_filename("3690.pdf") == "03690"

    def test_non_numeric_filename_returns_none(self):
        from hk_ipo.l1_sectioning import ticker_from_filename

        assert ticker_from_filename("ltn20180907011.pdf") is None

    def test_path_with_directories_uses_basename(self):
        from hk_ipo.l1_sectioning import ticker_from_filename

        assert ticker_from_filename("/foo/bar/03690.pdf") == "03690"


# ── Task 004 — language detection ──────────────────────────────────────────


class TestDetectLanguage:
    def test_english_majority_text_returns_en(self):
        from hk_ipo.l1_sectioning import detect_language

        text = (
            "The Group intends to use the net proceeds from the Global "
            "Offering for the following purposes. The Company will allocate "
            "approximately 35 per cent of the net proceeds for research."
        ) * 5
        assert detect_language(text) == "en"

    def test_chinese_majority_text_returns_zh(self):
        from hk_ipo.l1_sectioning import detect_language

        text = (
            "根据国家统计局最新发布的数据显示今年第一季度国内生产总值"
            "同比增长百分之五点三经济运行开局良好各项主要指标均保持在"
            "合理区间进出口贸易保持稳定增长居民消费价格指数温和上涨"
            "全国城镇调查失业率有所下降国民经济延续回升向好态势"
        ) * 20
        assert detect_language(text) == "zh"

    def test_mixed_text_returns_mixed_or_majority(self):
        from hk_ipo.l1_sectioning import detect_language

        # 50/50 split — accept either 'mixed' or whichever the heuristic picks
        text = (
            "The Group intends to use the net proceeds. " * 5
            + "本集团拟将全球发售所得款项净额用于以下用途。" * 5
        )
        assert detect_language(text) in ("en", "zh", "mixed")

    def test_empty_text_returns_unknown(self):
        from hk_ipo.l1_sectioning import detect_language

        assert detect_language("") == "unknown"

    def test_langdetect_exception_returns_unknown(self):
        """CR-008: Verify LangDetectException handler returns 'unknown'
        instead of propagating the exception."""
        from unittest.mock import patch

        from langdetect import LangDetectException

        from hk_ipo.l1_sectioning import detect_language

        with patch(
            "hk_ipo.l1_sectioning.detect_langs", side_effect=LangDetectException(999, "test error")
        ):
            assert detect_language("some text that triggers exception") == "unknown"


# ── Task 004 — Chinese stub ────────────────────────────────────────────────


class TestExtractZhStub:
    def test_chinese_pdf_emits_stub_record(self, tmp_path):
        """When detect_language(cover_text) == 'zh', extract returns a stub
        with skipped=True and no section text."""
        from unittest.mock import MagicMock, patch

        from hk_ipo.l1_sectioning import extract_use_of_proceeds

        fake_doc = MagicMock()
        fake_doc.page_count = 200
        fake_doc.get_toc.return_value = []

        pdf = tmp_path / "03690.pdf"
        pdf.write_bytes(b"%PDF-1.4 zh-stub")

        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=fake_doc),
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value="本集团拟将全球发售所得款项净额用于" * 30,
            ),
        ):
            result = extract_use_of_proceeds(str(pdf))

        assert result["language"] == "zh"
        assert result["skipped"] is True
        assert result["text"] == ""
        assert result["tables"] == []
        assert result["hk_ticker"] == "03690"


# ── Task 004 — limit / all_files CLI ───────────────────────────────────────


class TestProcessAllLimit:
    def test_limit_caps_pdfs_processed(self, tmp_path, monkeypatch):
        from pathlib import Path

        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        for stem in ("00001", "00002", "00003"):
            (raw / f"{stem}.pdf").write_bytes(b"fake")

        calls: list[str] = []

        def fake_extract(p, **kwargs):
            calls.append(Path(p).name)
            return {
                "company_file": Path(p).name,
                "hk_ticker": Path(p).stem,
                "document_date": None,
                "section_title": "x",
                "start_page": 1,
                "end_page": 1,
                "text": "x",
                "tables": [],
                "extraction_method": "stub",
                "language": "en",
                "skipped": False,
            }

        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)
        L1.process_all(raw, sec, limit=2)
        assert len(calls) == 2

    def test_non_matching_filename_is_skipped(self, tmp_path, monkeypatch):
        from pathlib import Path

        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        (raw / "ltn20180907011.pdf").write_bytes(b"fake")  # legacy name
        (raw / "03690.pdf").write_bytes(b"fake")  # good
        calls: list[str] = []

        def fake_extract(p, **kwargs):
            calls.append(Path(p).name)
            return {
                "company_file": Path(p).name,
                "hk_ticker": "03690",
                "document_date": None,
                "section_title": "x",
                "start_page": 1,
                "end_page": 1,
                "text": "x",
                "tables": [],
                "extraction_method": "stub",
                "language": "en",
                "skipped": False,
            }

        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)
        L1.process_all(raw, sec, all_files=True)
        assert calls == ["03690.pdf"]  # ltn-named PDF was skipped

    def test_all_files_false_uses_stem_fallback_not_none_json(self, tmp_path, monkeypatch):
        """CR-006: When all_files=False, non-numeric filenames should use stem
        as output filename, not 'None.json' (which would cause collisions)."""
        from pathlib import Path

        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        (raw / "ltn20180907011.pdf").write_bytes(b"fake")
        (raw / "prospectus.pdf").write_bytes(b"fake")
        calls: list[str] = []

        def fake_extract(p, **kwargs):
            calls.append(Path(p).name)
            return {
                "company_file": Path(p).name,
                "hk_ticker": "unknown",
                "document_date": None,
                "section_title": "x",
                "start_page": 1,
                "end_page": 1,
                "text": "x",
                "tables": [],
                "extraction_method": "stub",
                "language": "en",
                "skipped": False,
            }

        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)
        L1.process_all(raw, sec, all_files=False)
        # Both PDFs should be processed
        assert len(calls) == 2
        # No None.json — each gets a unique stem-based name
        out_files = list(sec.glob("*.json"))
        out_names = {f.name for f in out_files}
        assert "None.json" not in out_names
        assert "ltn20180907011.json" in out_names
        assert "prospectus.json" in out_names

    def test_force_false_skips_existing_output(self, tmp_path, monkeypatch):
        """CR-005: process_all respects force flag — without --force, existing
        output files should be skipped (not overwritten)."""
        from pathlib import Path

        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        (raw / "03690.pdf").write_bytes(b"fake")

        # Pre-create an output file with known original content
        existing_out = sec / "03690.json"
        original = '{"original": true, "company_file": "03690.pdf"}'
        existing_out.write_text(original)

        calls: list[str] = []

        def fake_extract(p, **kwargs):
            calls.append(Path(p).name)
            return {
                "company_file": Path(p).name,
                "hk_ticker": "03690",
                "document_date": None,
                "section_title": "new",
                "start_page": 1,
                "end_page": 1,
                "text": "new",
                "tables": [],
                "extraction_method": "stub",
                "language": "en",
                "skipped": False,
            }

        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)

        # force=False — should NOT overwrite existing output
        L1.process_all(raw, sec, force=False, all_files=True)
        assert existing_out.read_text() == original
        assert len(calls) == 0  # extract should never be called

    def test_force_true_overwrites_existing_output(self, tmp_path, monkeypatch):
        """CR-005: process_all with force=True should overwrite existing output."""
        from pathlib import Path

        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        (raw / "03690.pdf").write_bytes(b"fake")

        existing_out = sec / "03690.json"
        original = '{"original": true}'
        existing_out.write_text(original)

        calls: list[str] = []

        def fake_extract(p, **kwargs):
            calls.append(Path(p).name)
            return {
                "company_file": Path(p).name,
                "hk_ticker": "03690",
                "document_date": None,
                "section_title": "new",
                "start_page": 1,
                "end_page": 1,
                "text": "new",
                "tables": [],
                "extraction_method": "stub",
                "language": "en",
                "skipped": False,
            }

        monkeypatch.setattr(L1, "extract_use_of_proceeds", fake_extract)

        # force=True — should overwrite existing output
        L1.process_all(raw, sec, force=True, all_files=True)
        assert existing_out.read_text() != original
        assert len(calls) == 1

    def test_diagnostic_messages_go_to_stderr_not_stdout(self, tmp_path, monkeypatch, caplog):
        """CR-009: process_all diagnostic messages (SKIP) must use logging
        (INFO level), not pollute stdout. Unix convention and internal
        consistency both dictate stderr for non-data diagnostic output."""
        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()

        # Create one valid PDF and pre-create its output to trigger SKIP
        (raw / "00001.pdf").write_bytes(b"fake")
        existing_out = sec / "00001.json"
        existing_out.write_text('{"existing": true}')

        # force=False -> SKIP diagnostic logged at INFO level
        with caplog.at_level("INFO"):
            L1.process_all(raw, sec, force=False, all_files=True)

        # The skip message should appear as an INFO-level log record
        skip_records = [r for r in caplog.records if "00001.json" in r.message]
        assert len(skip_records) >= 1, f"Expected skip diagnostic in log records, got: {caplog.records}"

    def test_warn_no_pdfs_goes_to_stderr_not_stdout(self, tmp_path, monkeypatch, caplog):
        """CR-009: [WARN] No PDF files to process is logged at WARNING level
        via the logging framework (which defaults to stderr), not stdout."""
        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        # raw is empty — triggers WARNING log

        with caplog.at_level("WARNING"):
            L1.process_all(raw, sec, all_files=True)

        warn_records = [r for r in caplog.records if r.levelname == "WARNING" and "No PDF files to process" in r.message]
        assert len(warn_records) >= 1, f"Expected WARNING log, got records: {caplog.records}"

    def test_extract_exception_continues_to_next_pdf(self, tmp_path, monkeypatch, caplog):
        """CR-010: When extract_use_of_proceeds raises for one PDF,
        process_all logs ERROR and continues processing the
        remaining PDFs instead of aborting the entire batch."""
        from pathlib import Path

        from hk_ipo import l1_sectioning as L1

        raw = tmp_path / "raw"
        raw.mkdir()
        sec = tmp_path / "sec"
        sec.mkdir()
        (raw / "00001.pdf").write_bytes(b"fake")
        (raw / "00002.pdf").write_bytes(b"fake")
        (raw / "00003.pdf").write_bytes(b"fake")

        # Track which PDFs were attempted via extract_use_of_proceeds
        attempted: list[str] = []

        def selective_extract(p: str, **kwargs) -> dict:
            attempted.append(Path(p).name)
            if "00002" in Path(p).name:
                raise RuntimeError("simulated extraction failure")
            return {
                "company_file": Path(p).name,
                "hk_ticker": Path(p).stem,
                "document_date": None,
                "section_title": "x",
                "start_page": 1,
                "end_page": 1,
                "text": "x",
                "tables": [],
                "extraction_method": "stub",
                "language": "en",
                "skipped": False,
            }

        monkeypatch.setattr(L1, "extract_use_of_proceeds", selective_extract)

        with caplog.at_level("ERROR"):
            L1.process_all(raw, sec, all_files=True)

        # All 3 PDFs should have been attempted — the failing one does not halt batch
        assert len(attempted) == 3, f"Expected 3 attempts, got {len(attempted)}: {attempted}"
        assert sorted(attempted) == ["00001.pdf", "00002.pdf", "00003.pdf"]

        # ERROR diagnostic must be logged
        error_records = [r for r in caplog.records if r.levelname == "ERROR" and "00002.pdf" in r.message]
        assert len(error_records) >= 1, f"Expected ERROR log for 00002.pdf, got: {caplog.records}"

        # Successful PDFs (00001, 00003) should still produce output files
        assert (sec / "00001.json").exists(), "00001.json should be written"
        assert (sec / "00003.json").exists(), "00003.json should be written"
        assert not (sec / "00002.json").exists(), (
            "00002.json should NOT be written (extract failed)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Part 5: content-hash disk cache (P2-7)
# ─────────────────────────────────────────────────────────────────────────────


class TestContentHashCache:
    """Verify that extract_use_of_proceeds uses data/l1_cache/ to skip
    re-parsing when the PDF content is unchanged between runs.

    Strategy:
      - Write a minimal but valid fake PDF to tmp_path (just bytes, mocked out).
      - Mock pymupdf.open, pymupdf4llm.to_markdown, and pdfplumber.open so the
        test runs in milliseconds and does not need real PDF fixtures.
      - Redirect L1_CACHE_DIR to a tmp directory via monkeypatching the module-
        level _CACHE_DIR_ENV variable.
      - Call extract_use_of_proceeds twice; assert pymupdf.open is called exactly
        once (the second call is a cache hit).
    """

    _MOCK_MD = (
        "Stock Code: 06060\n"
        "Dated 1 January 2024.\n\n"
        "## USE OF PROCEEDS\n\n"
        "We intend to use proceeds as follows:\n\n"
        "## UNDERWRITING\n\nDetails.\n"
    )
    _TOC = [[1, "USE OF PROCEEDS", 5], [1, "UNDERWRITING", 10]]

    def _setup_mocks(self, pdf_path: str):
        """Return a dict of patch targets for the three PDF libraries."""
        doc = MagicMock()
        doc.get_toc.return_value = self._TOC
        doc.page_count = 20
        doc.close = MagicMock()
        return doc

    def test_second_call_skips_pdf_library(self, tmp_path, monkeypatch):
        """PDF is parsed only once; second call returns cached result."""
        import hk_ipo.l1_sectioning as L1

        # Redirect cache dir to a temp directory
        monkeypatch.setattr(L1, "_CACHE_DIR_ENV", tmp_path / "l1_cache")

        # Write fake PDF bytes so _pdf_content_hash can read the file
        fake_pdf = tmp_path / "06060.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake content for hashing")

        doc = self._setup_mocks(str(fake_pdf))

        open_call_count = [0]
        original_open = __builtins__  # noqa: F841 — not used, just context

        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc) as mock_open,
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value=self._MOCK_MD,
            ),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []

            # First call — cache miss, PDF is parsed
            result1 = L1.extract_use_of_proceeds(str(fake_pdf))
            first_call_count = mock_open.call_count

            # Second call — should be a cache hit, PDF library not invoked again
            result2 = L1.extract_use_of_proceeds(str(fake_pdf))
            second_call_count = mock_open.call_count

        assert first_call_count == 1, (
            f"Expected exactly 1 pymupdf.open call on first parse, got {first_call_count}"
        )
        assert second_call_count == 1, (
            f"Expected no extra pymupdf.open call on cache hit, "
            f"got {second_call_count - first_call_count} extra calls"
        )
        assert result1 == result2, "Cached result must be identical to original parse result"

    def test_force_true_bypasses_cache(self, tmp_path, monkeypatch):
        """force=True must skip the cache and re-parse the PDF."""
        import hk_ipo.l1_sectioning as L1

        monkeypatch.setattr(L1, "_CACHE_DIR_ENV", tmp_path / "l1_cache")

        fake_pdf = tmp_path / "06060.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake content for force-test")

        doc = self._setup_mocks(str(fake_pdf))

        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc) as mock_open,
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value=self._MOCK_MD,
            ),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []

            # First call seeds the cache
            L1.extract_use_of_proceeds(str(fake_pdf))
            count_after_first = mock_open.call_count  # == 1

            # Second call with force=True must bypass the cache
            L1.extract_use_of_proceeds(str(fake_pdf), force=True)
            count_after_force = mock_open.call_count

        assert count_after_first == 1
        assert count_after_force == 2, (
            f"force=True should trigger a re-parse; expected 2 total opens, got {count_after_force}"
        )

    def test_cache_file_written_after_parse(self, tmp_path, monkeypatch):
        """After the first parse a .json cache file must exist in l1_cache/."""
        import hk_ipo.l1_sectioning as L1

        cache_dir = tmp_path / "l1_cache"
        monkeypatch.setattr(L1, "_CACHE_DIR_ENV", cache_dir)

        fake_pdf = tmp_path / "06060.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 cache write test")

        doc = self._setup_mocks(str(fake_pdf))

        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value=self._MOCK_MD,
            ),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            L1.extract_use_of_proceeds(str(fake_pdf))

        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1, (
            f"Expected exactly 1 cache file, found {len(cache_files)}: {cache_files}"
        )
        cached_data = json.loads(cache_files[0].read_text(encoding="utf-8"))
        assert cached_data["company_file"] == "06060.pdf"

    def test_corrupt_cache_file_falls_through_to_parse(self, tmp_path, monkeypatch):
        """If the cache JSON is corrupt, the function falls back to re-parsing."""
        import hk_ipo.l1_sectioning as L1

        cache_dir = tmp_path / "l1_cache"
        cache_dir.mkdir()
        monkeypatch.setattr(L1, "_CACHE_DIR_ENV", cache_dir)

        fake_pdf = tmp_path / "06060.pdf"
        pdf_bytes = b"%PDF-1.4 corrupt cache test"
        fake_pdf.write_bytes(pdf_bytes)

        # Pre-write a corrupt cache file matching the hash of the PDF
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
        (cache_dir / f"{content_hash}.json").write_text("NOT VALID JSON{{{{", encoding="utf-8")

        doc = self._setup_mocks(str(fake_pdf))

        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc) as mock_open,
            patch(
                "hk_ipo.l1_sectioning.pymupdf4llm.to_markdown",
                return_value=self._MOCK_MD,
            ),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            result = L1.extract_use_of_proceeds(str(fake_pdf))

        assert mock_open.call_count == 1, "Corrupt cache should cause a re-parse"
        assert result["company_file"] == "06060.pdf"
