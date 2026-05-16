"""Batch pipeline entry script: run L1→L2→L3→L4 over a directory of PDFs.

Usage:
    python scripts/run_pipeline.py [--pdf-dir PATH] [--workers N] [--force] [--skip-l4]
"""

import argparse
import sys
from pathlib import Path

# Allow running without a package install (local dev)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hk_ipo import config  # noqa: E402
from hk_ipo.l1_sectioning import process_all as l1_process_all  # noqa: E402
from hk_ipo.l2_extraction import process_all as l2_process_all  # noqa: E402
from hk_ipo.l3_validation import process_all as l3_process_all  # noqa: E402
from hk_ipo.l4_analysis import run_analysis  # noqa: E402


def _print_summary_row(stage: str, total: object, ok: object, failed: object) -> None:
    print(f"  {stage:<8} {str(total):>6}  {str(ok):>10}  {str(failed):>6}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch pipeline: L1→L2→L3→L4 over a directory of PDFs"
    )
    parser.add_argument(
        "--pdf-dir",
        default=str(config.RAW_PDFS_DIR),
        metavar="PATH",
        help=f"Directory containing PDF files (default: {config.RAW_PDFS_DIR})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        metavar="N",
        help="Number of parallel workers for L2 extraction (default: 6)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if output already exists",
    )
    parser.add_argument(
        "--skip-l4",
        action="store_true",
        help="Skip L4 analysis",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        print(f"[ERROR] PDF directory not found: {pdf_dir}")
        sys.exit(1)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"[WARN] No PDF files found in {pdf_dir}")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  HK IPO Pipeline  —  {len(pdfs)} PDF(s) in {pdf_dir}")
    print(f"{'='*60}")

    # ── L1: sectioning ────────────────────────────────────────────────────────
    print(f"\n[L1] Sectioning {len(pdfs)} PDF(s) …")
    config.SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    l1_process_all(pdf_dir, config.SECTIONS_DIR)

    sections = sorted(config.SECTIONS_DIR.glob("*.json"))
    l1_summary = {
        "total": len(pdfs),
        "succeeded": len(sections),
        "failed": len(pdfs) - len(sections),
    }

    # ── L2: structured LLM extraction ─────────────────────────────────────────
    print(f"\n[L2] Extracting {len(sections)} section(s) with {args.workers} worker(s) …")
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    l2_summary = l2_process_all(
        sections_dir=config.SECTIONS_DIR,
        extracted_dir=config.EXTRACTED_DIR,
        max_workers=args.workers,
        force=args.force,
    )

    # ── L3: validation ────────────────────────────────────────────────────────
    print("\n[L3] Validating extracted JSON files …")
    l3_summary = l3_process_all(
        extracted_dir=config.EXTRACTED_DIR,
        validated_dir=config.EXTRACTED_DIR,
    )

    # ── L4: cross-company analysis ────────────────────────────────────────────
    if args.skip_l4:
        print("\n[L4] Skipped (--skip-l4 flag set).")
        l4_note = "skipped"
    else:
        print("\n[L4] Running cross-company analysis …")
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        run_analysis(str(config.EXTRACTED_DIR), str(config.REPORTS_DIR))
        l4_note = f"→ {config.REPORTS_DIR}"

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  Pipeline summary")
    print(f"{'='*60}")
    print(f"  {'Stage':<8} {'Total':>6}  {'Passed/OK':>10}  {'Failed':>6}")
    print(f"  {'-'*54}")
    _print_summary_row("L1", l1_summary["total"], l1_summary["succeeded"], l1_summary["failed"])
    _print_summary_row(
        "L2",
        l2_summary.get("total", 0),
        l2_summary.get("succeeded", 0),
        l2_summary.get("failed", 0),
    )
    _print_summary_row("L3", l3_summary["total"], l3_summary["passed"], l3_summary["failed"])
    print(f"  {'L4':<8} {'—':>6}  {'—':>10}  {l4_note}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
