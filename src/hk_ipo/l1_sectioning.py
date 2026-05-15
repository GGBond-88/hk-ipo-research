"""L1 分段层：将原始 PDF 招股书按章节切割，定位并提取 "Use of Proceeds"
章节的全文，以 Markdown 格式写入 data/sections/，供 L2 使用。

主要工具：pymupdf4llm（PDF → Markdown），pdfplumber（表格辅助解析）。
"""


def extract_use_of_proceeds(pdf_path: str) -> str:
    """从指定 PDF 中提取 Use of Proceeds 章节文本（占位）。"""
    raise NotImplementedError
