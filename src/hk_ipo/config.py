"""项目配置：从 .env 加载密钥，定义各数据层目录的路径常量。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_PDFS_DIR: Path = DATA_DIR / "raw_pdfs"
SECTIONS_DIR: Path = DATA_DIR / "sections"
EXTRACTED_DIR: Path = DATA_DIR / "extracted"
REPORTS_DIR: Path = DATA_DIR / "reports"

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# L2 model config — override via env vars if needed
L2_TEXT_MODEL: str = os.getenv("L2_TEXT_MODEL", "deepseek/deepseek-v4-pro")
# future vision fallback — unused in MVP
L2_VISION_MODEL: str = os.getenv("L2_VISION_MODEL", "google/gemini-2.5-flash-preview-05-20")
