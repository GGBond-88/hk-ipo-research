"""Unit tests for src/hk_ipo/taxonomy.py — closed Parent/Main vocabulary."""

from __future__ import annotations

import hashlib
import json


def test_parent_categories_are_exactly_four():
    from hk_ipo.taxonomy import PARENT_CATEGORIES

    assert PARENT_CATEGORIES == [
        "Growth",
        "Financing",
        "Working Capital",
        "Others",
    ]


def test_parent_tree_has_all_four_parents():
    from hk_ipo.taxonomy import PARENT_TREE

    assert set(PARENT_TREE.keys()) == {"Growth", "Financing", "Working Capital", "Others"}


def test_growth_has_expected_mains():
    from hk_ipo.taxonomy import PARENT_TREE

    growth_mains = set(PARENT_TREE["Growth"].keys())
    expected = {
        "R&D and Technology",
        "Product Development",
        "Sales and Marketing",
        "Capacity Expansion",
        "Geographic Expansion",
        "Acquisitions and Strategic Investments",
        "Infrastructure and Network",
    }
    assert growth_mains == expected


def test_financing_has_expected_mains():
    from hk_ipo.taxonomy import PARENT_TREE

    fin_mains = set(PARENT_TREE["Financing"].keys())
    assert fin_mains == {"Debt Repayment", "Refinancing", "Interest Payments"}


def test_working_capital_has_expected_mains():
    from hk_ipo.taxonomy import PARENT_TREE

    wc_mains = set(PARENT_TREE["Working Capital"].keys())
    expected = {
        "General Working Capital",
        "Inventory Procurement",
        "Receivables / Payables Management",
        "Day-to-day Operations",
    }
    assert wc_mains == expected


def test_others_has_expected_mains():
    from hk_ipo.taxonomy import PARENT_TREE

    others_mains = set(PARENT_TREE["Others"].keys())
    expected = {
        "General Corporate Purposes",
        "Reserves / Contingencies",
        "Unallocated / Unspecified",
    }
    assert others_mains == expected


def test_main_to_parent_map_is_consistent():
    from hk_ipo.taxonomy import MAIN_TO_PARENT, PARENT_TREE

    for parent, mains in PARENT_TREE.items():
        for main in mains:
            assert MAIN_TO_PARENT[main] == parent


def test_sub_categories_default_listed_for_growth_rd():
    from hk_ipo.taxonomy import PARENT_TREE

    subs = PARENT_TREE["Growth"]["R&D and Technology"]
    assert "Core product R&D" in subs
    assert "Platform / infrastructure R&D" in subs
    assert "Clinical / regulatory development" in subs


def test_taxonomy_sha_is_stable():
    from hk_ipo.taxonomy import PARENT_TREE, taxonomy_sha

    expected = hashlib.sha256(json.dumps(PARENT_TREE, sort_keys=True).encode("utf-8")).hexdigest()
    assert taxonomy_sha() == expected
    # Recomputing yields the same digest
    assert taxonomy_sha() == taxonomy_sha()


def test_schema_version_is_two_dot_zero():
    from hk_ipo.taxonomy import SCHEMA_VERSION

    assert SCHEMA_VERSION == "2.0"


# ── parent_for_main lookup ───────────────────────────────────────────────────


def test_parent_for_main_growth_mains():
    from hk_ipo.taxonomy import parent_for_main

    assert parent_for_main("R&D and Technology") == "Growth"
    assert parent_for_main("Product Development") == "Growth"
    assert parent_for_main("Sales and Marketing") == "Growth"
    assert parent_for_main("Capacity Expansion") == "Growth"
    assert parent_for_main("Geographic Expansion") == "Growth"
    assert parent_for_main("Acquisitions and Strategic Investments") == "Growth"
    assert parent_for_main("Infrastructure and Network") == "Growth"


def test_parent_for_main_financing_mains():
    from hk_ipo.taxonomy import parent_for_main

    assert parent_for_main("Debt Repayment") == "Financing"
    assert parent_for_main("Refinancing") == "Financing"
    assert parent_for_main("Interest Payments") == "Financing"


def test_parent_for_main_working_capital_mains():
    from hk_ipo.taxonomy import parent_for_main

    assert parent_for_main("General Working Capital") == "Working Capital"
    assert parent_for_main("Inventory Procurement") == "Working Capital"
    assert parent_for_main("Receivables / Payables Management") == "Working Capital"
    assert parent_for_main("Day-to-day Operations") == "Working Capital"


def test_parent_for_main_others_mains():
    from hk_ipo.taxonomy import parent_for_main

    assert parent_for_main("General Corporate Purposes") == "Others"
    assert parent_for_main("Reserves / Contingencies") == "Others"
    assert parent_for_main("Unallocated / Unspecified") == "Others"


def test_parent_for_main_unknown_returns_none():
    from hk_ipo.taxonomy import parent_for_main

    assert parent_for_main("Nonexistent Category") is None
    assert parent_for_main("") is None
    assert parent_for_main("Random Text") is None
