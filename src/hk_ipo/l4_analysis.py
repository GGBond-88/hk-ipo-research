"""L4 分析层：汇总多份招股书的 L3 校验结果，执行跨公司统计分析，
生成可视化报告（图表 + CSV 摘要）写入 data/reports/。

典型分析维度：
  - 各行业资金用途分布（研发 / 营销 / 运营 / 补充流动资金等）
  - 募资规模 vs 用途结构相关性
  - 时序趋势（按 IPO 日期）
"""

import matplotlib.pyplot as plt  # noqa: F401
import pandas as pd  # noqa: F401


def run_analysis(extracted_dir: str) -> None:
    """读取所有已校验的 JSON 文件，生成分析报告（占位）。"""
    raise NotImplementedError
