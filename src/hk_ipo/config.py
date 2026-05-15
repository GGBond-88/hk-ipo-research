"""项目配置：从 .env 加载密钥，定义各数据层目录的路径常量。"""

from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_PDFS_DIR: Path = DATA_DIR / "raw_pdfs"
SECTIONS_DIR: Path = DATA_DIR / "sections"
EXTRACTED_DIR: Path = DATA_DIR / "extracted"
REPORTS_DIR: Path = DATA_DIR / "reports"

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
