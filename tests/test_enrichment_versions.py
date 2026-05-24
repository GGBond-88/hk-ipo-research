"""Lock-in tests for enrichment block schema (key set and VERSION string).

Each test constructs a minimal fake record, runs the enrichment's _enrich_one,
and asserts:
  - block["version"] == expected VERSION constant
  - set(block.keys()) == expected key set for that dimension

If any enrichment changes its output shape without bumping VERSION and
updating EXPECTED here, these tests fail immediately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── Expected schemas ───────────────────────────────────────────────────────
# Keys: dimension name
# Values: (frozenset of expected block keys, expected VERSION value)

EXPECTED: dict[str, tuple[frozenset[str], int]] = {
    "geo":        (frozenset({"version", "by_use_id"}), 1),
    "country":    (frozenset({"version", "countries", "by_use_id"}), 1),
    "industry":   (frozenset({"version", "primary", "source"}), 1),
    "capex_opex": (frozenset({"version", "by_use_id"}), 1),
    "commitment": (frozenset({"version", "by_use_id"}), 1),
    "esg_tag":    (frozenset({"version", "any_esg", "by_use_id"}), 1),
    "timeline":   (frozenset({"version", "by_use_id"}), 1),
    "specificity": (frozenset({"version", "by_use_id"}), 1),
}

# ── Minimal fake record ────────────────────────────────────────────────────

def _fake_record() -> dict[str, Any]:
    return {
        "hk_ticker": "09999",
        "company_name_en": "Test Corp Ltd",
        "schema_version": "2.0",
        "uses": [
            {
                "use_id": "use_001",
                "description": "Build a factory in Hong Kong",
                "category_raw": "construction",
                "percentage": 100.0,
                "source_text": "We will build a factory in Hong Kong.",
            }
        ],
        "enrichments": {},
    }


# ── Parametrized test ──────────────────────────────────────────────────────

@pytest.mark.parametrize("dimension,expected_keys,expected_version", [
    (d, k, v) for d, (k, v) in EXPECTED.items()
])
def test_enrichment_schema_stable(
    tmp_path: Path,
    dimension: str,
    expected_keys: frozenset[str],
    expected_version: int,
) -> None:
    """Each enrichment block must have exactly the documented keys and VERSION."""
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()

    record = _fake_record()

    if dimension == "geo":
        from hk_ipo.enrichments.geo import _enrich_one
        block = _enrich_one(record, enriched_dir, force=True)

    elif dimension == "country":
        from hk_ipo.enrichments.country import _enrich_one
        block = _enrich_one(record, enriched_dir, force=True)

    elif dimension == "industry":
        from hk_ipo.enrichments.industry import _enrich_one
        # Patch _classify_via_llm so no real LLM call is made
        with patch(
            "hk_ipo.enrichments.industry._classify_via_llm",
            return_value="Software & Services",
        ):
            block = _enrich_one(record, enriched_dir, force=True)

    elif dimension == "capex_opex":
        from hk_ipo.enrichments.capex_opex import _enrich_one
        block = _enrich_one(record, enriched_dir, force=True)

    elif dimension == "commitment":
        from hk_ipo.enrichments.commitment import _enrich_one
        block = _enrich_one(record, enriched_dir, force=True)

    elif dimension == "esg_tag":
        from hk_ipo.enrichments.esg_tag import _enrich_one
        block = _enrich_one(record, enriched_dir, force=True)

    elif dimension == "timeline":
        from hk_ipo.enrichments.timeline import DIMENSION, _enrich_one
        block = _enrich_one(record, enriched_dir, DIMENSION, force=True)

    elif dimension == "specificity":
        from hk_ipo.enrichments.specificity import _enrich_one
        block = _enrich_one(record, enriched_dir, force=True)

    else:
        pytest.fail(f"Unknown dimension: {dimension}")

    assert isinstance(block, dict), f"[{dimension}] _enrich_one must return a dict"
    assert block["version"] == expected_version, (
        f"[{dimension}] VERSION mismatch: got {block['version']!r}, "
        f"expected {expected_version!r}"
    )
    assert set(block.keys()) == expected_keys, (
        f"[{dimension}] key-set mismatch:\n"
        f"  got:      {sorted(block.keys())}\n"
        f"  expected: {sorted(expected_keys)}"
    )

    # Verify the block was also written to disk
    out_file = enriched_dir / "09999.json"
    assert out_file.exists(), f"[{dimension}] enriched file was not written to disk"
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["enrichments"][dimension] == block, (
        f"[{dimension}] block in saved file does not match returned block"
    )
