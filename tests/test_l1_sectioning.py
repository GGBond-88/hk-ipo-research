"""Unit tests for L1 sectioning layer (src/hk_ipo/l1_sectioning.py).

Coverage strategy:
  - Pure functions tested directly with constructed inputs (no PDF I/O).
  - PDF-coupled functions (extract_use_of_proceeds) tested via mock to
    verify output schema without touching real files.
  - Regex fallback path (_locate_in_markdown) receives extra attention
    because it has never been triggered by a real PDF yet.
"""

from unittest.mock import MagicMock, patch

import pytest

from hk_ipo.l1_sectioning import (
    _locate_in_markdown,
    _locate_in_toc_list,
    _matches_section_title,
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
            [2, "Future Plans", 401],      # sub-entry, level 2 > target level 1
            [2, "Use of Proceeds", 402],   # sub-entry, level 2 > target level 1
            [1, "UNDERWRITING", 410],      # same level → closes the section
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
    "company_file", "section_title", "start_page", "end_page",
    "text", "tables", "extraction_method",
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

    PDF I/O is fully mocked; these tests run in milliseconds.
    """

    def _run_with_toc(self, toc):
        doc = _make_mock_doc(toc)
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch("hk_ipo.l1_sectioning.pymupdf4llm.to_markdown", return_value="## USE OF PROCEEDS\n\nText."),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            result = extract_use_of_proceeds("fake.pdf")
        return result

    def test_toc_path_output_contains_all_required_fields(self):
        toc = [[1, "FUTURE PLANS AND USE OF PROCEEDS", 400], [1, "UNDERWRITING", 410]]
        result = self._run_with_toc(toc)
        assert _REQUIRED_FIELDS <= result.keys()

    def test_toc_path_extraction_method_is_toc(self):
        toc = [[1, "FUTURE PLANS AND USE OF PROCEEDS", 400], [1, "UNDERWRITING", 410]]
        result = self._run_with_toc(toc)
        assert result["extraction_method"] == "toc"

    def test_regex_path_extraction_method_is_regex(self):
        # Empty TOC forces regex fallback
        doc = _make_mock_doc(toc=[], page_count=100)
        md = "## FUTURE PLANS AND USE OF PROCEEDS\n\nSome text.\n\n## UNDERWRITING\n\nMore.\n"
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch("hk_ipo.l1_sectioning.pymupdf4llm.to_markdown", return_value=md),
            patch("hk_ipo.l1_sectioning.pdfplumber.open") as mock_plumber,
        ):
            mock_plumber.return_value.__enter__.return_value.pages = []
            result = extract_use_of_proceeds("fake.pdf")
        assert result["extraction_method"] == "regex"

    def test_tables_field_is_always_a_list(self):
        toc = [[1, "USE OF PROCEEDS", 5], [1, "NEXT CHAPTER", 10]]
        result = self._run_with_toc(toc)
        assert isinstance(result["tables"], list)

    def test_extraction_method_only_valid_values(self):
        toc = [[1, "USE OF PROCEEDS", 5], [1, "NEXT", 10]]
        result = self._run_with_toc(toc)
        assert result["extraction_method"] in ("toc", "regex")

    def test_raises_value_error_when_section_not_found(self):
        doc = _make_mock_doc(toc=[], page_count=100)
        with (
            patch("hk_ipo.l1_sectioning.pymupdf.open", return_value=doc),
            patch("hk_ipo.l1_sectioning.pymupdf4llm.to_markdown", return_value="## RISK FACTORS\n\nNo proceeds here.\n"),
        ):
            with pytest.raises(ValueError, match="Cannot locate"):
                extract_use_of_proceeds("fake.pdf")
