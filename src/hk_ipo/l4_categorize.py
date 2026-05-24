"""L4 hierarchical categorisation: LLM Pass 2 for HK IPO use-of-proceeds.

Assigns each use item a Parent/Main/Sub classification from the closed
taxonomy in `hk_ipo.taxonomy`. Enforces strict sum constraints at every
level (auto-rebalance <= 0.5% delta
flag > 0.5% for human review).

Input:  data/extracted/<ticker>.json  (post-L2 flat extraction)
Output: data/categorized/<ticker>.json
Side-effect: appends new sub-category proposals to data/taxonomy_proposals.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openai
import portalocker

from hk_ipo.logging_setup import get_logger
from hk_ipo.schema import SCHEMA_VERSION
from hk_ipo.taxonomy import PARENT_CATEGORIES, PARENT_TREE, parent_for_main

logger = get_logger(__name__)


def _llm_assign_parent(main: str, parent_categories: list[str]) -> str | None:
    """Fall back to an LLM call to determine the Parent for a Main category
    that is not in the closed taxonomy.

    Returns a Parent category string if the LLM assigns one, or None on failure.
    """
    from hk_ipo import config as cfg
    from hk_ipo.llm_client import LLMClient

    model = cfg.L2_TEXT_MODEL
    valid_parents = [p for p in parent_categories if p != "Others"]
    prompt = (
        "You are a financial taxonomy assistant. "
        "Given a use-of-proceeds main-category label, return the single Parent "
        "category it belongs to.\n\n"
        f"Valid Parent categories: {', '.join(valid_parents)}\n\n"
        f"Main category label: \"{main}\"\n\n"
        "Reply with ONLY the Parent category name, nothing else. "
        "If you cannot determine the parent, reply with \"Others\"."
    )
    try:
        response = LLMClient.get().chat(
            stage="L4",
            model=model,
            messages=[
                {"role": "system", "content": "You classify financial categories."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=32,
        )
        raw = response.choices[0].message.content or ""
        result = raw.strip().strip('"').strip("'")
        if result in parent_categories:
            return result
        return None
    except openai.APIError:
        return None


def assign_parent(main: str, parent_categories: list[str]) -> str:
    """Data-driven parent assignment from the taxonomy, with LLM fallback.

    First tries an exact lookup of `main` in the closed taxonomy via
    `parent_for_main`. If the main is not in the taxonomy, falls back to
    an LLM call. Falls back to 'Others' when neither succeeds.

    The `parent_categories` parameter is used as a validation guard:
    if the result is not in the supplied list, the function falls back
    to "Others".
    """
    # Data-driven lookup: exact match against the canonical taxonomy
    parent = parent_for_main(main)
    if parent is not None:
        if parent in parent_categories:
            return parent
        return "Others"

    # LLM fallback for novel / non-canonical main labels
    llm_parent = _llm_assign_parent(main, parent_categories)
    if llm_parent is not None and llm_parent in parent_categories:
        return llm_parent
    return "Others"


# ── Rebalance logic ────────────────────────────────────────────────────────


def _tiebreak_key(name: str) -> str:
    """Sort key that inverts alphabetical order so max() picks the
    alphabetically-first name when values are equal.

    max() with a tuple key (value, key_fn) picks the highest value, and on
    tie picks the highest key_fn value. We invert ASCII so 'A' > 'Z' under
    the secondary sort, which means max() picks alphabetically-first.

    Non-ASCII characters are mapped to a safe range that sorts after all
    inverted-ASCII characters, so they lose ties against ASCII names.
    """
    buf: list[str] = []
    for ch in name:
        cp = ord(ch)
        if cp <= 0x7F:
            buf.append(chr(0x7F - cp))
        else:
            # Map non-ASCII to a safe area far above the inverted-ASCII range.
            # chr(0x80) is the first character above 0x7F; we add the code
            # point modulo a safe window to preserve ordering among non-ASCII
            # characters without risking out-of-range chr() calls.
            buf.append(chr(0x1000 + (cp % 0xEFFF)))
    return "".join(buf)


def rebalance_layer(
    allocations: dict[str, float],
    tolerance: float = 0.5,
    target: float = 100.0,
    layer: str = "parent",
) -> tuple[dict[str, float], list[dict[str, str | float]]]:
    """Adjust allocations to sum to `target`.

    If |sum - target| <= tolerance, add delta to the largest sibling.
    If > tolerance, return unchanged (caller must flag).

    `layer` is used in the rebalanced log entry (e.g. "parent", "main").
    If two or more siblings share the largest value, tie-break by
    alphabetically-first category name (deterministic, reproducible).

    Returns (adjusted_allocations, rebalanced_log).
    """
    if not allocations:
        return {}, []
    total = sum(allocations.values())
    delta = round(target - total, 4)
    if abs(delta) < 1e-6:
        return dict(allocations), []
    if abs(delta) > tolerance:
        return dict(allocations), []

    # Largest sibling; tie-break alphabetically for determinism
    largest = max(allocations, key=lambda k: (allocations[k], _tiebreak_key(k)))
    adjusted = dict(allocations)
    original = adjusted[largest]
    adjusted[largest] = round(original + delta, 4)
    log_entry = {
        "layer": layer,
        "key": largest,
        "original": original,
        "adjusted": adjusted[largest],
        "delta": round(delta, 4),
    }
    return adjusted, [log_entry]


# ── Validation ─────────────────────────────────────────────────────────────


def validate_parent_sums(
    breakdown: dict[str, float],
    tolerance: float = 0.5,
) -> list[dict[str, Any]]:
    """Check that parent allocations sum to 100% within tolerance.

    Returns a list of violation dicts, each with a 'type' key.
    An empty breakdown is vacuously valid.
    """
    if not breakdown:
        return []
    total = sum(breakdown.values())
    if abs(total - 100.0) > tolerance:
        return [
            {
                "type": "parent_sum_violation",
                "message": (
                    f"parent_sum_violation: parent allocation sum={total:.2f}%, "
                    f"expected 100.0 +/- {tolerance}%"
                ),
                "total": round(total, 4),
                "expected": 100.0,
                "tolerance": tolerance,
            }
        ]
    return []


def validate_main_sums(
    main_sums: dict[str, dict[str, float]],
    parent_breakdown: dict[str, float],
    tolerance: float = 0.5,
) -> list[dict[str, Any]]:
    """Check that main allocations under each parent sum to that parent's share.

    Returns a list of violation dicts, each with a 'type' key.
    An empty parent_breakdown is vacuously valid.
    """
    if not parent_breakdown:
        return []
    violations: list[dict[str, Any]] = []
    for parent, expected_share in parent_breakdown.items():
        mains = main_sums.get(parent, {})
        total = sum(mains.values())
        if abs(total - expected_share) > tolerance:
            violations.append(
                {
                    "type": "main_sum_violation",
                    "message": (
                        f"main_sum_violation: under parent={parent!r}, "
                        f"main sum={total:.2f}%, expected={expected_share:.2f} "
                        f"+/- {tolerance}%"
                    ),
                    "parent": parent,
                    "total": round(total, 4),
                    "expected": expected_share,
                    "tolerance": tolerance,
                }
            )
    return violations


# ── Sub-label proposals ────────────────────────────────────────────────────


def record_sub_proposal(
    proposals: list[dict[str, Any]],
    parent: str,
    main: str,
    sub_label: str,
    ticker: str,
) -> None:
    """Record a novel sub-category label if it is not in the closed vocab."""
    if not sub_label or not sub_label.strip():
        return
    closed_subs: list[str] = PARENT_TREE.get(parent, {}).get(main, [])
    if sub_label in closed_subs:
        return
    for p in proposals:
        if (
            p["proposed_label"] == sub_label
            and p["parent_category"] == parent
            and p["main_category"] == main
        ):
            p["occurrences"] += 1
            return
    proposals.append(
        {
            "proposed_label": sub_label,
            "parent_category": parent,
            "main_category": main,
            "occurrences": 1,
            "first_seen_ticker": ticker,
            "first_seen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "promoted": 0,
        }
    )


def append_sub_proposals_csv(
    proposals: list[dict[str, Any]],
    csv_path: Path,
) -> None:
    """Append new sub-category proposals to a CSV file.

    Does NOT create a file when the proposals list is empty.
    When the target file does not exist yet, writes a header row first.
    Existing rows (matched by (proposed_label, parent, main) tuple) are
    not duplicated.

    Uses portalocker for thread/process-safe concurrent appends so that
    parallel L4 workers do not corrupt the shared taxonomy_proposals.csv.
    """
    if not proposals:
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with portalocker.Lock(
        str(csv_path), "a+", timeout=10, encoding="utf-8-sig", newline=""
    ) as fh:
        # Read existing entries for dedup (under the lock)
        fh.seek(0)
        existing: set[tuple[str, str, str]] = set()
        content = fh.read()
        if content.strip():
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                existing.add(
                    (
                        row.get("proposed_label", ""),
                        row.get("parent_category", ""),
                        row.get("main_category", ""),
                    )
                )
        file_is_new = not content.strip()

        # Seek to end for append
        fh.seek(0, 2)
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "proposed_label",
                "parent_category",
                "main_category",
                "occurrences",
                "first_seen_ticker",
                "first_seen_at",
                "promoted",
            ],
        )
        if file_is_new:
            writer.writeheader()
        for p in proposals:
            key = (p["proposed_label"], p["parent_category"], p["main_category"])
            if key not in existing:
                writer.writerow(p)


# ── Golden fixture ─────────────────────────────────────────────────────────


def load_golden_fixture(path: Path) -> dict[str, Any]:
    """Load a hand-labeled golden fixture from a file path.

    Raises FileNotFoundError if the path does not exist.
    Raises ValueError if the JSON is malformed or missing the 'uses' key.
    """
    if not path.exists():
        raise FileNotFoundError(f"Golden fixture not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "uses" not in data:
        raise ValueError("Golden fixture must have a 'uses' key")
    return data


def compute_main_category_match_rate(
    expected: dict[str, dict[str, str]],
    predicted: dict[str, dict[str, str]],
) -> float:
    """Share of use_ids where predicted main matches expected main.

    When both expected and predicted are empty, returns 1.0 (vacuously
    true — no expectations to violate). When expected is non-empty but
    predicted is empty, returns 0.0 (none of the expected items were
    matched). When expected is empty but predicted is non-empty, returns
    0.0 (predictions without ground truth are not credited).
    """
    if not expected:
        if not predicted:
            return 1.0
        return 0.0
    matches = 0
    for uid, exp in expected.items():
        if uid in predicted and predicted[uid].get("main") == exp.get("main"):
            matches += 1
    return matches / len(expected)


# ── Prompt builder ─────────────────────────────────────────────────────────


def build_categorization_prompt(
    uses: list[dict[str, Any]],
    taxonomy: dict[str, dict[str, list[str]]],
) -> str:
    """Build the user prompt for the L4 LLM categorization call."""
    taxonomy_str = json.dumps(taxonomy, indent=2, ensure_ascii=False)
    uses_str = json.dumps(
        [
            {
                "use_id": u.get("use_id", ""),
                "category_raw": u.get("category_raw", ""),
                "percentage": u.get("percentage"),
                "description": u.get("description", ""),
            }
            for u in uses
        ],
        indent=2,
        ensure_ascii=False,
    )
    return (
        "## Taxonomy (closed Parent/Main vocabulary; Sub is semi-open)\n\n"
        f"```json\n{taxonomy_str}\n```\n\n"
        "## Task\n"
        "For each use item below, assign:\n"
        "- `parent_category`: exactly one of Growth / Financing / Working Capital / Others\n"
        "- `main_category`: exactly one Main under that Parent from the taxonomy above\n"
        "- `sub_category`: the most specific Sub under that Main, or propose a new label\n"
        "  following the naming conventions if no existing Sub fits\n\n"
        "## Rules\n"
        "1. All percentages under one Parent must sum to that Parent's total allocation.\n"
        "2. Use the taxonomy exactly — do not invent new Parent or Main labels.\n"
        "3. If no Sub category fits, propose a new one with a concise descriptive name.\n"
        "4. Output raw JSON (no markdown fences) with this structure:\n"
        '  {"uses": [{"use_id": "...", "parent_category": "...", '
        '"main_category": "...", "sub_category": "..."}], '
        '"parent_breakdown": {"Growth": X, "Financing": Y, '
        '"Working Capital": Z, "Others": W}}\n\n'
        "## Use items to classify\n\n"
        f"```json\n{uses_str}\n```\n"
    )


# ── Output construction ────────────────────────────────────────────────────


def build_categorized_output(
    l2_data: dict[str, Any],
    uses_with_hierarchy: list[dict[str, Any]],
    parent_breakdown: dict[str, float],
    main_sums: dict[str, dict[str, float]],
    rebalanced: list[dict[str, Any]],
    violations: list[dict[str, Any]],
    sub_proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the complete L4 categorized output record."""
    output = dict(l2_data)
    output["uses"] = uses_with_hierarchy
    output["schema_version"] = SCHEMA_VERSION
    output["validation"] = {
        "parent_sum": round(sum(parent_breakdown.values()), 2),
        "parent_breakdown": parent_breakdown,
        "main_sums_by_parent": {p: round(sum(m.values()), 2) for p, m in main_sums.items()},
        "rebalanced": rebalanced,
        "violations": violations,
    }
    # Always ensure extraction_metadata exists in output (per spec).
    output["extraction_metadata"] = output.pop("extraction_metadata", {})
    # Include sub-category proposals so callers (e.g. process_single) can
    # persist them without re-deriving the same filter logic.
    output["sub_proposals"] = sub_proposals
    needs_review = len(violations) > 0
    if "needs_human_review" not in output:
        output["needs_human_review"] = needs_review
    if needs_review and not output.get("review_reasons"):
        output["review_reasons"] = [v.get("message", str(v)) for v in violations]
    return output


# ── LLM call ───────────────────────────────────────────────────────────────


def call_l4_llm(user_prompt: str, model: str | None = None) -> dict[str, Any]:
    """Call the LLM for hierarchical categorisation."""
    from hk_ipo import config as cfg
    from hk_ipo.llm_client import LLMClient

    model_name = model or cfg.L2_TEXT_MODEL
    system = (
        "You are a financial data classification assistant. "
        "You classify use-of-proceeds items into a closed taxonomy."
    )
    response = LLMClient.get().chat(
        stage="L4",
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    if not raw.strip():
        raise ValueError("L4 LLM returned empty response")
    return json.loads(raw)


# ── Main pipeline function ─────────────────────────────────────────────────


def categorize_one(l2_data: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    """Run the full L4 categorisation on one L2 extraction record."""
    taxonomy: dict[str, dict[str, list[str]]] = dict(PARENT_TREE)

    uses = l2_data.get("uses", [])
    if not uses:
        return build_categorized_output(
            l2_data=l2_data,
            uses_with_hierarchy=[],
            parent_breakdown={},
            main_sums={},
            rebalanced=[],
            violations=[],
            sub_proposals=[],
        )

    # Build prompt and call LLM
    prompt = build_categorization_prompt(uses, taxonomy)
    llm_out = call_l4_llm(prompt, model=model)

    # Parse LLM classification results
    classified = llm_out.get("uses", [])
    class_map: dict[str, dict[str, str | None]] = {}
    for c in classified:
        uid = c.get("use_id")
        if not uid:
            continue  # Skip malformed LLM output items with missing use_id
        class_map[uid] = {
            "parent": c.get("parent_category"),
            "main": c.get("main_category"),
            "sub": c.get("sub_category"),
        }

    # Merge hierarchy into use items
    sub_proposals: list[dict[str, Any]] = []
    ticker = l2_data.get("hk_ticker", "unknown")
    uses_with_hierarchy: list[dict[str, Any]] = []
    for u in uses:
        uid = u.get("use_id", "")
        cm = class_map.get(uid, {})
        parent = cm.get("parent") or "Others"
        main = cm.get("main")
        sub = cm.get("sub")

        # Validate parent is in closed vocab
        if parent not in PARENT_CATEGORIES:
            parent = "Others"

        # Validate main is under parent
        if main and main not in taxonomy.get(parent, {}):
            # Try to find a close match or drop
            main = None

        # Record novel sub labels
        if sub and parent in taxonomy and main and main in taxonomy[parent]:
            record_sub_proposal(sub_proposals, parent, main, sub, ticker)

        new_item = dict(u)
        new_item["parent_category"] = parent
        new_item["main_category"] = main
        new_item["sub_category"] = sub
        uses_with_hierarchy.append(new_item)

    # Compute parent breakdown
    parent_breakdown: dict[str, float] = {}
    for u_item in uses_with_hierarchy:
        pct = u_item.get("percentage") or 0
        p = u_item.get("parent_category", "Others")
        parent_breakdown[p] = parent_breakdown.get(p, 0) + pct

    # Compute main sums by parent
    main_sums: dict[str, dict[str, float]] = {}
    for u_item in uses_with_hierarchy:
        pct = u_item.get("percentage") or 0
        p = u_item.get("parent_category", "Others")
        m = u_item.get("main_category") or "Unspecified"
        if p not in main_sums:
            main_sums[p] = {}
        main_sums[p][m] = main_sums[p].get(m, 0) + pct

    # Rebalance parent layer
    adjusted_breakdown, rebalanced = rebalance_layer(
        parent_breakdown, tolerance=0.5, layer="parent"
    )

    # Rebalance main layer: for each parent, adjust main allocations to
    # sum to that parent's share.
    adjusted_main_sums: dict[str, dict[str, float]] = {}
    for parent, expected_share in adjusted_breakdown.items():
        mains = dict(main_sums.get(parent, {}))
        if not mains:
            adjusted_main_sums[parent] = {}
            continue
        adj_mains, main_rebalanced = rebalance_layer(
            mains, tolerance=0.5, target=expected_share, layer="main"
        )
        adjusted_main_sums[parent] = adj_mains
        rebalanced.extend(main_rebalanced)

    # Validate against the rebalanced (final) allocations so that small
    # within-tolerance deltas that were auto-corrected by rebalance_layer
    # are not flagged as violations.
    violations = validate_parent_sums(adjusted_breakdown, tolerance=0.5)
    violations.extend(validate_main_sums(adjusted_main_sums, adjusted_breakdown, tolerance=0.5))

    return build_categorized_output(
        l2_data=l2_data,
        uses_with_hierarchy=uses_with_hierarchy,
        parent_breakdown=adjusted_breakdown,
        main_sums=adjusted_main_sums,
        rebalanced=rebalanced,
        violations=violations,
        sub_proposals=sub_proposals,
    )


# ── File I/O ───────────────────────────────────────────────────────────────


def process_single(
    extracted_file: Path,
    categorized_dir: Path,
    force: bool = False,
    model: str | None = None,
    proposals_csv: Path | None = None,
) -> dict[str, Any]:
    """Process a single extracted JSON file through L4 categorisation."""
    categorized_dir.mkdir(parents=True, exist_ok=True)
    stem = extracted_file.stem
    out_path = categorized_dir / f"{stem}.json"

    if not force and out_path.exists():
        try:
            result = json.loads(out_path.read_text(encoding="utf-8"))
            logger.info("already done: %s", out_path.name)
            return result
        except json.JSONDecodeError:
            logger.warning("cached output is corrupted, re-processing: %s", out_path.name)

    l2_data = json.loads(extracted_file.read_text(encoding="utf-8"))
    logger.info("-> %s", extracted_file.name)
    result = categorize_one(l2_data, model=model)

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    n_uses = len(result.get("uses", []))
    v = result.get("validation", {})
    logger.info("  uses       : %s", n_uses)
    logger.info("  parent sum : %s%%", v.get('parent_sum', '?'))
    logger.info("  violations : %s", len(v.get('violations', [])))
    logger.info("  rebalanced : %s", len(v.get('rebalanced', [])))
    logger.info("  -> saved to  : %s", out_path.name)

    if proposals_csv:
        # Use the sub-category proposals already collected by categorize_one
        # (via record_sub_proposal), avoiding duplicate filtering logic.
        proposals = result.get("sub_proposals", [])
        append_sub_proposals_csv(proposals, proposals_csv)

    return result


def process_all(
    extracted_dir: Path,
    categorized_dir: Path,
    limit: int | None = None,
    force: bool = False,
    model: str | None = None,
    proposals_csv: Path | None = None,
    workers: int = 4,
) -> dict[str, Any]:
    """Process all extracted JSON files in a directory through L4 categorisation
    using a thread pool."""
    jsons = sorted(
        p
        for p in extracted_dir.glob("*.json")
        if ".validated" not in p.name and ".error" not in p.name
    )
    if limit:
        jsons = jsons[:limit]
    if not jsons:
        logger.warning("No extracted JSON files found in %s", extracted_dir)
        return {"succeeded": 0, "failed": 0, "total": 0}

    succeeded = 0
    failed = 0

    def _process_one(jf: Path) -> tuple[str, bool, str]:
        """Process one file; return (filename, ok, log_output)."""
        buf = io.StringIO()
        try:
            result = process_single(
                jf, categorized_dir, force=force, model=model, proposals_csv=proposals_csv
            )
            buf.write(f"-> {jf.name}\n")
            n_uses = len(result.get("uses", []))
            v = result.get("validation", {})
            buf.write(f"  uses       : {n_uses}\n")
            buf.write(f"  parent sum : {v.get('parent_sum', '?')}%\n")
            buf.write(f"  violations : {len(v.get('violations', []))}\n")
            buf.write(f"  rebalanced : {len(v.get('rebalanced', []))}\n")
            buf.write(f"  -> saved to  : {jf.stem}.json\n")
            return jf.name, True, buf.getvalue()
        except (OSError, ValueError, json.JSONDecodeError, openai.APIError) as exc:
            buf.write(f"-> {jf.name}\n")
            buf.write(f"  [ERROR] {exc}\n")
            return jf.name, False, buf.getvalue()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one, jf): jf for jf in jsons}
        for future in concurrent.futures.as_completed(futures):
            filename, ok, log_output = future.result()
            logger.info(log_output.strip())
            if ok:
                succeeded += 1
            else:
                failed += 1

    logger.info(
        "L4 complete: %s succeeded, %s failed (of %s total)",
        succeeded, failed, len(jsons),
    )
    return {"succeeded": succeeded, "failed": failed, "total": len(jsons)}


# ── CLI ────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the L4 categoriser."""
    parser = argparse.ArgumentParser(
        description="L4: hierarchical categorisation of use-of-proceeds items"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Process all files in data/extracted/")
    group.add_argument("file", nargs="?", help="Process one extracted file by path")
    parser.add_argument(
        "--force", action="store_true", help="Re-process files even if output already exists"
    )
    parser.add_argument("--limit", type=int, help="Limit the number of files processed")
    parser.add_argument("--model", help="LLM model to use")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Number of parallel worker threads for --all (default 4)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    from hk_ipo.config import CATEGORIZED_DIR, DATA_DIR, EXTRACTED_DIR

    CATEGORIZED_DIR.mkdir(parents=True, exist_ok=True)
    args = parse_args()
    proposals_csv = DATA_DIR / "taxonomy_proposals.csv"

    if args.all:
        process_all(
            EXTRACTED_DIR,
            CATEGORIZED_DIR,
            limit=args.limit,
            force=args.force,
            model=args.model,
            proposals_csv=proposals_csv,
            workers=args.workers,
        )
    else:
        sf = Path(args.file)
        if not sf.exists():
            logger.error("Not found: %s", sf)
            sys.exit(1)
        process_single(
            sf, CATEGORIZED_DIR, force=args.force, model=args.model, proposals_csv=proposals_csv
        )
