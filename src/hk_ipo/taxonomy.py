"""Closed Parent / Main / Sub taxonomy for HK IPO use-of-proceeds classification.

This module is the single source of truth for L4 categorization, L6 loader
referential checks, L7 dashboard export, and frontend display.

Parent categories are FIXED (4).
Main categories under each parent are FIXED (closed list).
Sub categories under each main are SUGGESTED defaults
L4 may emit new sub
labels for review (captured to data/taxonomy_proposals.csv).
"""

from __future__ import annotations

import hashlib
import json

SCHEMA_VERSION: str = "2.0"

PARENT_CATEGORIES: list[str] = [
    "Growth",
    "Financing",
    "Working Capital",
    "Others",
]

PARENT_TREE: dict[str, dict[str, list[str]]] = {
    "Growth": {
        "R&D and Technology": [
            "Core product R&D",
            "Platform / infrastructure R&D",
            "Clinical / regulatory development",
        ],
        "Product Development": [
            "New product launches",
            "Product enhancements",
        ],
        "Sales and Marketing": [
            "Brand and advertising",
            "Channel expansion",
            "Customer acquisition",
        ],
        "Capacity Expansion": [
            "New manufacturing facilities",
            "Capacity upgrades to existing sites",
            "Equipment and machinery",
        ],
        "Geographic Expansion": [
            "Overseas markets",
            "Mainland China expansion",
            "Specific region build-out",
        ],
        "Acquisitions and Strategic Investments": [
            "M&A",
            "Minority strategic investments",
            "Joint ventures",
        ],
        "Infrastructure and Network": [
            "Stores / branches",
            "Data centers and IT infrastructure",
            "Logistics and supply chain",
        ],
    },
    "Financing": {
        "Debt Repayment": [
            "Bank loan repayment",
            "Bond / note redemption",
        ],
        "Refinancing": [],
        "Interest Payments": [],
    },
    "Working Capital": {
        "General Working Capital": [],
        "Inventory Procurement": [],
        "Receivables / Payables Management": [],
        "Day-to-day Operations": [],
    },
    "Others": {
        "General Corporate Purposes": [],
        "Reserves / Contingencies": [],
        "Unallocated / Unspecified": [],
    },
}

MAIN_TO_PARENT: dict[str, str] = {
    main: parent for parent, mains in PARENT_TREE.items() for main in mains
}


def parent_for_main(name: str) -> str | None:
    """Return the Parent category for a Main category name, or None if unknown."""
    return MAIN_TO_PARENT.get(name)


def taxonomy_sha() -> str:
    """SHA-256 of canonical-JSON-serialised PARENT_TREE; used in manifest.json."""
    payload = json.dumps(PARENT_TREE, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
