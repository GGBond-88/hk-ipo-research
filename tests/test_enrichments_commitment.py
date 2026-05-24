"""Unit tests for src/hk_ipo/enrichments/commitment.py."""

from __future__ import annotations


def test_dimension_and_version():
    from hk_ipo.enrichments.commitment import DIMENSION, VERSION

    assert DIMENSION == "commitment"
    assert isinstance(VERSION, int)


def test_committed_firm_language():
    from hk_ipo.enrichments.commitment import classify_commitment

    item = {
        "description": "The Company has committed to invest HK$500 million.",
        "source_text": "We have committed HK$500 million and signed binding agreements.",
    }
    assert classify_commitment(item) == "committed"


def test_discretionary_tentative_language():
    from hk_ipo.enrichments.commitment import classify_commitment

    item = {
        "description": "The Company may consider acquisitions subject to market conditions.",
        "source_text": "We may pursue strategic acquisitions if conditions permit.",
    }
    assert classify_commitment(item) == "discretionary"


def test_committed_when_obligated():
    from hk_ipo.enrichments.commitment import classify_commitment

    item = {
        "description": "We are obligated under the loan agreement to repay within 3 years.",
        "source_text": "Mandatory repayment of HK$200 million under existing obligations.",
    }
    assert classify_commitment(item) == "committed"


def test_discretionary_contingent():
    from hk_ipo.enrichments.commitment import classify_commitment

    item = {
        "description": "Subject to board approval, we may allocate funds for expansion.",
        "source_text": "Any allocation is subject to board approval and market conditions.",
    }
    assert classify_commitment(item) == "discretionary"


def test_default_committed():
    from hk_ipo.enrichments.commitment import classify_commitment

    item = {"description": "Use for research.", "source_text": "Use for research."}
    assert classify_commitment(item) == "committed"


def test_committed_full_form_undertaking():
    """CR-001: 'undertak' truncated stem must match 'undertaking', 'undertaken', etc."""
    from hk_ipo.enrichments.commitment import classify_commitment

    # Include one discretionary keyword ("may") to force a FAIL if "undertakes"
    # is not matched as committed. Tied counts default to "committed".
    item = {
        "description": "The Company undertakes the project.",
        "source_text": "We may undertake further work next year.",
    }
    assert classify_commitment(item) == "committed"


def test_discretionary_full_form_contingencies():
    """CR-001: 'contingen' truncated stem must match 'contingent', 'contingencies', etc."""
    from hk_ipo.enrichments.commitment import classify_commitment

    # Isolate: only "contingent" / "contingencies" are present, no other keywords.
    # Without the fix, n_discretionary = n_committed = 0 → falls back to "committed" (bug).
    item = {
        "description": "Funding is contingent on approval.",
        "source_text": "Various contingencies are noted here.",
    }
    assert classify_commitment(item) == "discretionary"
