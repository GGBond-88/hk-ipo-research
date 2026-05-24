# Task 007: L4 categorizer — unit tests (RED)

## Project Overview

- **Goal:** Build a CLI-driven data pipeline plus React dashboard that locates "Use of Proceeds" sections in HKEX prospectus PDFs, extracts each use with a two-pass LLM (flat extraction + hierarchical classification), enriches with eight tag dimensions, persists to SQLite, and renders interactive charts from pre-baked JSON.
- **Architecture:** Eight-stage CLI pipeline (L1 sectioning -> L2 flat extraction -> L3 validation -> L4 hierarchical categorize -> L5 enrichments -> L6 SQLite loader -> L7 JSON export -> React/Vite/ECharts dashboard). Each stage is independently runnable and idempotent. SQLite is source of truth; frontend reads pre-baked JSON only.
- **Tech Stack:** Python 3.10+, pydantic v2, OpenAI SDK + OpenRouter, SQLite (stdlib), pytest.

## Task Objective

Write failing unit tests for `l4_categorize.py` covering the closed taxonomy Parent/Main assignment, auto-rebalance rules, violation flagging, new sub-label proposals, and the golden-fixture acceptance criterion A4.5. The module does not exist yet, so all tests will fail with import errors -- this is the RED phase of the TDD inner loop.

This is Task 7 of 27.

---

**Files:**
- Create: `tests/test_l4_categorize.py`

- [ ] **Step 1: Write the full unit test file**

Create `tests/test_l4_categorize.py`:

```python
"""Unit tests for L4 hierarchical categorizer (src/hk_ipo/l4_categorize.py).

Tests the pure-logic functions: rebalancing, violation detection, sub-label
proposals, and output serialization. The LLM call is mocked.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────

def _sample_l2_output() -> dict:
    """A realistic post-L2 flat extraction (no hierarchy yet)."""
    return {
        "company_file": "01234.pdf",
        "hk_ticker": "01234",
        "document_date": "2024-06-30",
        "schema_version": "2.0",
        "total_net_proceeds_hkd_million": 5000.0,
        "currency": "HKD",
        "uses": [
            {
                "use_id": "use_001",
                "category_raw": "R&D and technology upgrade",
                "percentage": 35.0,
                "amount_hkd_million": 1750.0,
                "description": "Upgrade core algorithms.",
                "source_text": "Approximately 35% ...",
            },
            {
                "use_id": "use_002",
                "category_raw": "marketing and brand promotion",
                "percentage": 25.0,
                "amount_hkd_million": 1250.0,
                "description": "Brand promotion.",
                "source_text": "Approximately 25% ...",
            },
            {
                "use_id": "use_003",
                "category_raw": "working capital",
                "percentage": 20.0,
                "amount_hkd_million": 1000.0,
                "description": "General working capital.",
                "source_text": "Approximately 20% ...",
            },
            {
                "use_id": "use_004",
                "category_raw": "debt repayment",
                "percentage": 20.0,
                "amount_hkd_million": 1000.0,
                "description": "Repay bank loans.",
                "source_text": "Approximately 20% ...",
            },
        ],
    }


# ── Taxonomy helpers ───────────────────────────────────────────────────────

class TestParentCategorization:
    def test_assign_parent_returns_valid_parent(self):
        from hk_ipo.l4_categorize import assign_parent
        from hk_ipo.taxonomy import PARENT_CATEGORIES
        result = assign_parent("research and development", PARENT_CATEGORIES)
        assert result in PARENT_CATEGORIES

    def test_assign_parent_unknown_returns_others(self):
        from hk_ipo.l4_categorize import assign_parent
        result = assign_parent("completely unknown purpose", ["Growth", "Financing"])
        assert result == "Others"


# ── Sum constraint & rebalance logic ───────────────────────────────────────

class TestRebalanceLogic:

    def test_rebalance_parent_level_delta_within_tolerance(self):
        """Delta <= 0.5% → auto-rebalance the largest sibling."""
        from hk_ipo.l4_categorize import rebalance_layer

        allocations = {"Growth": 60.0, "Financing": 10.0,
                       "Working Capital": 20.0, "Others": 9.5}
        # sum = 99.5 → delta = 0.5, within tolerance
        result, rebalanced = rebalance_layer(allocations, tolerance=0.5)
        assert round(sum(result.values()), 2) == 100.0
        assert len(rebalanced) == 1
        # Largest sibling (Growth=60) absorbs the +0.5
        assert result["Growth"] == pytest.approx(60.5, abs=0.01)

    def test_rebalance_exact_sum_passes_through(self):
        from hk_ipo.l4_categorize import rebalance_layer

        allocations = {"Growth": 65.0, "Financing": 10.0,
                       "Working Capital": 15.0, "Others": 10.0}
        result, rebalanced = rebalance_layer(allocations, tolerance=0.5)
        assert result == allocations
        assert rebalanced == []

    def test_rebalance_delta_exceeds_tolerance_returns_original(self):
        from hk_ipo.l4_categorize import rebalance_layer

        allocations = {"Growth": 60.0, "Financing": 10.0,
                       "Working Capital": 20.0, "Others": 5.0}
        # sum = 95.0 → delta = 5.0 >> 0.5
        result, rebalanced = rebalance_layer(allocations, tolerance=0.5)
        assert result == allocations  # unchanged
        assert rebalanced == []  # not rebalanced, flagged instead

    def test_rebalance_empty_returns_empty(self):
        from hk_ipo.l4_categorize import rebalance_layer
        result, rebalanced = rebalance_layer({}, tolerance=0.5)
        assert result == {}
        assert rebalanced == []

    def test_rebalance_main_level_custom_target(self):
        """Delta <= 0.5% around a custom target → auto-rebalance."""
        from hk_ipo.l4_categorize import rebalance_layer

        # Parent Growth has 65% share; its main allocations sum to 64.7%
        # delta = 0.3, within tolerance
        main_allocs = {
            "R&D and Technology": 35.0,
            "Sales and Marketing": 24.7,
            "Geographic Expansion": 5.0,
        }
        result, rebalanced = rebalance_layer(
            main_allocs, tolerance=0.5, target=65.0, layer="main"
        )
        assert round(sum(result.values()), 2) == 65.0
        assert len(rebalanced) == 1
        assert rebalanced[0]["layer"] == "main"
        # Largest main (R&D=35) absorbs the +0.3 delta
        assert result["R&D and Technology"] == pytest.approx(35.3, abs=0.01)

    def test_rebalance_main_level_exceeds_tolerance_returns_original(self):
        """Delta > 0.5% on main level → no rebalance, return unchanged."""
        from hk_ipo.l4_categorize import rebalance_layer

        main_allocs = {
            "R&D and Technology": 35.0,
            "Sales and Marketing": 15.0,
        }
        # sum = 50.0, target = 65.0 → delta = 15.0 >> 0.5
        result, rebalanced = rebalance_layer(
            main_allocs, tolerance=0.5, target=65.0, layer="main"
        )
        assert result == main_allocs  # unchanged
        assert rebalanced == []

    def test_rebalance_tie_breaks_alphabetically(self):
        """When two siblings share the largest value, the alphabetically-first absorbs the delta."""
        from hk_ipo.l4_categorize import rebalance_layer

        # Both main categories have equal allocation
        allocations = {
            "Sales and Marketing": 30.0,
            "R&D and Technology": 30.0,
        }
        # sum = 60.0, target = 60.3 → delta = +0.3
        result, rebalanced = rebalance_layer(
            allocations, tolerance=0.5, target=60.3, layer="main"
        )
        assert round(sum(result.values()), 2) == 60.3
        assert len(rebalanced) == 1
        # Alphabetically "R&D and Technology" < "Sales and Marketing",
        # so R&D absorbs the delta
        assert result["R&D and Technology"] == pytest.approx(30.3, abs=0.01)
        assert result["Sales and Marketing"] == 30.0


class TestParentSumValidation:
    def test_parent_sum_within_tolerance_passes(self):
        from hk_ipo.l4_categorize import validate_parent_sums

        breakdown = {"Growth": 65.0, "Financing": 10.0,
                     "Working Capital": 15.0, "Others": 10.0}
        violations = validate_parent_sums(breakdown, tolerance=0.5)
        assert violations == []

    def test_parent_sum_exceeds_tolerance_flags(self):
        from hk_ipo.l4_categorize import validate_parent_sums

        breakdown = {"Growth": 60.0, "Financing": 10.0,
                     "Working Capital": 10.0, "Others": 5.0}
        violations = validate_parent_sums(breakdown, tolerance=0.5)
        assert len(violations) >= 1
        assert any("parent_sum_violation" in v for v in violations)


class TestMainSumValidation:
    def test_main_sum_under_parent_within_tolerance_passes(self):
        from hk_ipo.l4_categorize import validate_main_sums

        main_sums = {
            "Growth": {
                "R&D and Technology": 35.0,
                "Sales and Marketing": 25.0,
                "Geographic Expansion": 5.0,
            },
        }
        parent_breakdown = {"Growth": 65.0}
        violations = validate_main_sums(main_sums, parent_breakdown, tolerance=0.5)
        assert violations == []

    def test_main_sum_exceeds_tolerance_flags(self):
        from hk_ipo.l4_categorize import validate_main_sums

        main_sums = {
            "Growth": {
                "R&D and Technology": 35.0,
                "Sales and Marketing": 10.0,
            },
        }
        parent_breakdown = {"Growth": 65.0}
        violations = validate_main_sums(main_sums, parent_breakdown, tolerance=0.5)
        assert len(violations) >= 1
        assert any("main_sum_violation" in v for v in violations)


# ── Sub-label proposals ────────────────────────────────────────────────────

class TestSubLabelProposals:
    def test_new_sub_label_recorded(self):
        from hk_ipo.l4_categorize import record_sub_proposal
        proposals: list[dict] = []
        record_sub_proposal(proposals, "Growth", "R&D and Technology",
                           "Novel AI research", "01234")
        assert len(proposals) == 1
        assert proposals[0]["proposed_label"] == "Novel AI research"
        assert proposals[0]["parent_category"] == "Growth"
        assert proposals[0]["main_category"] == "R&D and Technology"
        assert proposals[0]["first_seen_ticker"] == "01234"

    def test_existing_sub_label_not_duplicated(self):
        from hk_ipo.l4_categorize import record_sub_proposal
        proposals: list[dict] = [
            {"proposed_label": "Novel AI research",
             "parent_category": "Growth",
             "main_category": "R&D and Technology",
             "occurrences": 1, "first_seen_ticker": "01234",
             "first_seen_at": "2026-01-01T00:00:00Z", "promoted": 0},
        ]
        record_sub_proposal(proposals, "Growth", "R&D and Technology",
                           "Novel AI research", "01234")
        assert len(proposals) == 1
        assert proposals[0]["occurrences"] == 2

    def test_sub_label_in_closed_vocab_not_recorded(self):
        from hk_ipo.l4_categorize import record_sub_proposal
        from hk_ipo.taxonomy import PARENT_TREE
        proposals: list[dict] = []
        record_sub_proposal(proposals, "Growth", "R&D and Technology",
                           "Core product R&D", "01234")
        assert proposals == []  # already in the closed vocab


# ── Output construction ────────────────────────────────────────────────────

class TestBuildCategorized:
    def test_output_has_all_required_fields(self):
        from hk_ipo.l4_categorize import build_categorized_output

        output = build_categorized_output(
            l2_data=_sample_l2_output(),
            uses_with_hierarchy=[],
            parent_breakdown={},
            main_sums={},
            sub_sums={},
            rebalanced=[],
            violations=[],
            sub_proposals=[],
        )
        assert output["schema_version"] == "2.0"
        assert "validation" in output
        assert "parent_breakdown" in output["validation"]
        assert "rebalanced" in output["validation"]
        assert "violations" in output["validation"]
        assert "main_sums_by_parent" in output["validation"]

    def test_output_appends_taxonomy_proposals_to_csv(self, tmp_path: Path):
        from hk_ipo.l4_categorize import append_sub_proposals_csv

        proposals = [
            {"proposed_label": "Novel AI research",
             "parent_category": "Growth",
             "main_category": "R&D and Technology",
             "occurrences": 1, "first_seen_ticker": "01234",
             "first_seen_at": "2026-05-19T10:00:00Z", "promoted": 0},
        ]
        csv_path = tmp_path / "taxonomy_proposals.csv"
        append_sub_proposals_csv(proposals, csv_path)
        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "Novel AI research" in content
        assert "Growth" in content
        assert "R&D and Technology" in content


# ── System prompt construction ─────────────────────────────────────────────

class TestBuildCategorizationPrompt:
    def test_prompt_includes_taxonomy(self):
        from hk_ipo.l4_categorize import build_categorization_prompt
        from hk_ipo.taxonomy import PARENT_TREE

        prompt = build_categorization_prompt(_sample_l2_output()["uses"], PARENT_TREE)
        assert "Growth" in prompt
        assert "Financing" in prompt
        assert "Working Capital" in prompt
        assert "Others" in prompt
        assert "R&D and Technology" in prompt

    def test_prompt_includes_use_items(self):
        from hk_ipo.l4_categorize import build_categorization_prompt

        uses = _sample_l2_output()["uses"]
        prompt = build_categorization_prompt(uses, {})
        for u in uses:
            assert u["use_id"] in prompt
            assert u["category_raw"] in prompt


# ── Golden-fixture contract (A4.5) ─────────────────────────────────────────

class TestGoldenFixture:
    def test_golden_fixture_loader(self):
        """The categorizer module must expose a function that loads a
        hand-labeled golden fixture from a path."""
        from hk_ipo.l4_categorize import load_golden_fixture

        data = {
            "uses": [
                {"use_id": "use_001", "parent_category": "Growth",
                 "main_category": "R&D and Technology",
                 "sub_category": "Core product R&D"},
                {"use_id": "use_002", "parent_category": "Growth",
                 "main_category": "Sales and Marketing",
                 "sub_category": "Brand and advertising"},
            ],
        }
        fixture = load_golden_fixture(data)
        assert isinstance(fixture, dict)
        assert len(fixture["uses"]) == 2

    def test_compute_main_category_match_rate(self):
        from hk_ipo.l4_categorize import compute_main_category_match_rate

        expected = {
            "use_001": {"parent": "Growth", "main": "R&D and Technology"},
            "use_002": {"parent": "Growth", "main": "Sales and Marketing"},
            "use_003": {"parent": "Working Capital", "main": "General Working Capital"},
        }
        predicted = {
            "use_001": {"parent": "Growth", "main": "R&D and Technology"},
            "use_002": {"parent": "Growth", "main": "Sales and Marketing"},
            "use_003": {"parent": "Working Capital", "main": "Day-to-day Operations"},
        }
        rate = compute_main_category_match_rate(expected, predicted)
        assert rate == pytest.approx(2 / 3, abs=0.01)

    def test_match_rate_perfect(self):
        from hk_ipo.l4_categorize import compute_main_category_match_rate

        data = {"use_001": {"parent": "Growth", "main": "R&D and Technology"}}
        rate = compute_main_category_match_rate(data, data)
        assert rate == 1.0

    def test_match_rate_empty(self):
        from hk_ipo.l4_categorize import compute_main_category_match_rate
        rate = compute_main_category_match_rate({}, {})
        assert rate == 1.0  # vacuously true


# ── CLI argument parsing (pure logic) ──────────────────────────────────────

class TestCLIParseArgs:
    def test_all_flag_parsed(self):
        from hk_ipo.l4_categorize import parse_args
        args = parse_args(["--all"])
        assert args.all

    def test_single_file_parsed(self):
        from hk_ipo.l4_categorize import parse_args
        args = parse_args(["data/extracted/01234.json"])
        assert args.file == "data/extracted/01234.json"

    def test_limit_flag_parsed(self):
        from hk_ipo.l4_categorize import parse_args
        args = parse_args(["--all", "--limit", "5"])
        assert args.limit == 5

    def test_model_flag_parsed(self):
        from hk_ipo.l4_categorize import parse_args
        args = parse_args(["--all", "--model", "openai/gpt-4o"])
        assert args.model == "openai/gpt-4o"
```

- [ ] **Step 2: Run the tests; verify ALL fail with import errors**

Run: `python -m pytest tests/test_l4_categorize.py -v`

Expected: `ModuleNotFoundError: No module named 'hk_ipo.l4_categorize'` (or every test fails).

This is the RED phase. Do NOT implement anything yet. Task 008 will implement `l4_categorize.py`.
