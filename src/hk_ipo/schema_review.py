"""Schema review tool: scan extracted JSON files for category_proposed values
and report clusters of similar strings.

CLI: python -m hk_ipo.schema_review

This tool is READ-ONLY — it never modifies schema.py or any data files.
"""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
from typing import Any


def _normalise(s: str) -> str:
    """Lowercase and strip whitespace for comparison."""
    return s.lower().strip()


def _group_by_similarity(
    values: list[str],
    threshold: float = 0.7,
) -> list[list[str]]:
    """Group similar strings into clusters using SequenceMatcher.

    Simple O(n²) grouping: each string is assigned to the first existing
    cluster whose representative is sufficiently similar; otherwise a new
    cluster is created. No external ML dependencies.

    Parameters
    ----------
    values:     Unique strings to cluster.
    threshold:  Minimum SequenceMatcher ratio to consider strings similar.
    """
    clusters: list[list[str]] = []
    representatives: list[str] = []  # normalised representative for each cluster

    for val in values:
        norm_val = _normalise(val)
        placed = False
        for idx, rep in enumerate(representatives):
            ratio = difflib.SequenceMatcher(None, norm_val, rep).ratio()
            if ratio >= threshold:
                clusters[idx].append(val)
                placed = True
                break
        if not placed:
            clusters.append([val])
            representatives.append(norm_val)

    return clusters


def _scan_dir(extracted_dir: Path) -> dict[str, Any]:
    """Scan *.json files in extracted_dir (excluding .validated.json, .error.json).

    Returns a summary dict with:
        files_scanned, total_uses, uses_with_proposed,
        proposed_values: list[str],
        proposed_by_file: dict[str, list[str]]   (filename → list of proposed values)
    """
    jsons = sorted(
        p
        for p in extracted_dir.glob("*.json")
        if ".validated" not in p.name and ".error" not in p.name
    )

    total_uses = 0
    proposed_values: list[str] = []
    proposed_by_file: dict[str, list[str]] = {}

    for jf in jsons:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue

        uses = data.get("uses", [])
        total_uses += len(uses)
        file_proposed: list[str] = []
        for u in uses:
            cp = u.get("category_proposed")
            if cp and isinstance(cp, str) and cp.strip():
                proposed_values.append(cp.strip())
                file_proposed.append(cp.strip())
        if file_proposed:
            proposed_by_file[jf.name] = file_proposed

    return {
        "files_scanned": len(jsons),
        "total_uses": total_uses,
        "uses_with_proposed": len(proposed_values),
        "proposed_values": proposed_values,
        "proposed_by_file": proposed_by_file,
    }


def generate_report(extracted_dir: Path) -> str:
    """Generate a text report for category_proposed values found in extracted_dir."""
    scan = _scan_dir(extracted_dir)

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("Schema Review Report")
    lines.append("=" * 70)
    lines.append(f"Files scanned     : {scan['files_scanned']}")
    lines.append(f"Total uses        : {scan['total_uses']}")
    lines.append(f"Uses with proposed: {scan['uses_with_proposed']}")
    lines.append("")

    proposed_values = scan["proposed_values"]
    proposed_by_file = scan["proposed_by_file"]

    if not proposed_values:
        lines.append("No category_proposed values found.")
        lines.append("=" * 70)
        return "\n".join(lines)

    # Build a map: value → list of files it appears in
    value_to_files: dict[str, list[str]] = {}
    for filename, vals in proposed_by_file.items():
        for v in vals:
            value_to_files.setdefault(v, []).append(filename)

    # Unique values (preserve order of first appearance)
    seen: set[str] = set()
    unique_values: list[str] = []
    for v in proposed_values:
        if v not in seen:
            seen.add(v)
            unique_values.append(v)

    clusters = _group_by_similarity(unique_values)

    lines.append(f"Clusters ({len(clusters)} total):")
    lines.append("-" * 70)

    for i, cluster in enumerate(clusters, 1):
        # Files for this entire cluster
        cluster_files: set[str] = set()
        for v in cluster:
            cluster_files.update(value_to_files.get(v, []))

        count = sum(len(value_to_files.get(v, [])) for v in cluster)
        lines.append(f"Cluster {i} ({count} occurrence(s) in {len(cluster_files)} file(s)):")
        lines.append(f"  Examples : {', '.join(repr(v) for v in cluster[:3])}")
        lines.append(f"  Files    : {', '.join(sorted(cluster_files))}")

        if len(cluster_files) >= 2:
            representative = cluster[0]
            lines.append(
                f"  *** Recommendation: Consider promoting {representative!r} "
                f"to CATEGORY_L2 if it appears in ≥2 files ***"
            )
        lines.append("")

    lines.append("=" * 70)
    lines.append(
        "NOTE: This report is read-only. Edit schema.py manually to add new categories."
    )
    lines.append("=" * 70)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Schema review: scan extracted JSON files for category_proposed clusters"
    )
    parser.add_argument(
        "--extracted-dir",
        metavar="DIR",
        default=None,
        help="Directory containing extracted JSON files (default: data/extracted/)",
    )
    args = parser.parse_args()

    if args.extracted_dir is not None:
        extracted_dir = Path(args.extracted_dir)
    else:
        from hk_ipo.config import EXTRACTED_DIR
        extracted_dir = EXTRACTED_DIR

    if not extracted_dir.exists():
        print(f"[WARN] Directory does not exist: {extracted_dir}")
        print("No files to scan.")
        return

    report = generate_report(extracted_dir)
    print(report)


if __name__ == "__main__":
    main()
