"""L3 校验层：对 L2 提取的结构化数据进行数值完整性校验，包括：
  - 各项金额加总是否与募资总额一致（允许±1% 误差）
  - 各项百分比加总是否约等于 100%
  - 字段类型与格式规范化（金额统一为 float，货币单位标准化）

校验通过后写入 data/extracted/<name>_validated.json，失败时记录错误报告。
"""


def validate(extracted: list[dict]) -> tuple[bool, list[str]]:
    """校验提取结果，返回 (是否通过, 错误信息列表)（占位）。"""
    raise NotImplementedError
