"""MVP entry script: drive a single prospectus PDF through the L1→L2 pipeline.

L3 (validation) and L4 (analysis) are not yet implemented; this script stubs
them with informational prints so the script runs to completion.

Usage:
    python scripts/run_mvp.py <pdf_path>
"""

import json
import sys
from pathlib import Path

# Allow running without a package install (local dev)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hk_ipo import config  # noqa: E402
from hk_ipo.l1_sectioning import extract_use_of_proceeds  # noqa: E402
from hk_ipo.l2_extraction import process_single  # noqa: E402


def main(pdf_path: str) -> None:
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"[ERROR] PDF not found: {pdf}")
        sys.exit(1)

    # ── L1: locate and extract Use of Proceeds section ────────────────────────
    print(f"\n[L1] Sectioning: {pdf.name}")
    config.SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    section_data = extract_use_of_proceeds(str(pdf))
    section_path = config.SECTIONS_DIR / f"{pdf.stem}.json"
    section_path.write_text(
        json.dumps(section_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"     section : {section_data['section_title']!r}")
    print(f"     ticker  : {section_data['hk_ticker']}")
    print(f"     pages   : {section_data['start_page']}–{section_data['end_page']}")
    print(f"     saved   : {section_path.name}")

    # ── L2: structured LLM extraction ─────────────────────────────────────────
    print("\n[L2] Extracting structured data …")
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    result = process_single(section_path, config.EXTRACTED_DIR)
    vp = result["validation_preview"]
    print(f"     items   : {vp['top_level_count']} top-level, pct sum={vp['percentage_sum']}%")

    # ── L3: validation (not yet implemented) ──────────────────────────────────
    print("\n[L3] Validation — not yet implemented, skipping.")

    # ── L4: analysis (not yet implemented) ────────────────────────────────────
    print("\n[L4] Analysis — not yet implemented, skipping.")

    print(f"\nDone. Extracted data written to {config.EXTRACTED_DIR}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_mvp.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
