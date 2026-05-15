"""MVP 入口脚本：驱动单份招股书 PDF 经 L1→L2→L3→L4 完整流水线处理。

用法：
    python scripts/run_mvp.py <pdf_path>
"""

import sys
from pathlib import Path

# 将 src/ 加入路径，兼容未安装的本地开发场景
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hk_ipo import config  # noqa: E402
from hk_ipo.l1_sectioning import extract_use_of_proceeds  # noqa: E402
from hk_ipo.l2_extraction import extract_structured  # noqa: E402
from hk_ipo.l3_validation import validate  # noqa: E402
from hk_ipo.l4_analysis import run_analysis  # noqa: E402


def main(pdf_path: str) -> None:
    print(f"[L1] Sectioning: {pdf_path}")
    section_text = extract_use_of_proceeds(pdf_path)

    print("[L2] Extracting structured data …")
    items = extract_structured(section_text)

    print("[L3] Validating …")
    ok, errors = validate(items)
    if not ok:
        print("Validation errors:", errors)
        sys.exit(1)

    print("[L4] Running analysis …")
    run_analysis(str(config.EXTRACTED_DIR))
    print("Done. Reports written to", config.REPORTS_DIR)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_mvp.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
