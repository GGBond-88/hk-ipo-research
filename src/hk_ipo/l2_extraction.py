"""L2 提取层：接收 L1 输出的章节文本，调用 LLM（经由 langextract / OpenRouter）
进行结构化信息提取，输出包含以下字段的 JSON 到 data/extracted/：
  - item_name:   资金用途项目名称
  - amount_hkd:  金额（港元）
  - percentage:  占募资总额百分比
  - description: 用途描述
"""


def extract_structured(section_text: str) -> list[dict]:
    """将章节文本结构化提取为资金用途条目列表（占位）。"""
    raise NotImplementedError
