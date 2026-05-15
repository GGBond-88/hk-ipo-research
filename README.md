# hk-ipo-research

港股 IPO 招股书「Use of Proceeds（募集资金用途）」章节的自动化提取与分析工具。

## 项目简介

本项目以四层流水线处理港交所上市公司招股书 PDF，最终输出结构化的募资用途数据及跨公司对比分析报告，适用于投行研究、学术研究及投资尽调场景。

## 四层架构

| 层级 | 模块 | 职责 |
|------|------|------|
| **L1** | `l1_sectioning.py` | PDF 解析与章节定位：将原始 PDF 转为 Markdown，定位并切割 "Use of Proceeds" 章节 |
| **L2** | `l2_extraction.py` | LLM 结构化提取：从章节文本提取「项目名 / 金额 / 百分比 / 描述」等字段，输出 JSON |
| **L3** | `l3_validation.py` | 数值校验与规范化：校验金额加总与百分比一致性，统一货币格式 |
| **L4** | `l4_analysis.py` | 统计分析与可视化：汇总多份招股书，生成行业对比图表与 CSV 摘要报告 |

## 目录结构

```
hk-ipo-research/
├── data/
│   ├── raw_pdfs/      # 原始招股书 PDF（不入 git）
│   ├── sections/      # L1 输出的章节文本（不入 git）
│   ├── extracted/     # L2/L3 输出的结构化 JSON（不入 git）
│   └── reports/       # L4 生成的分析报告
├── src/hk_ipo/        # 主包
├── tests/             # 单元测试
└── scripts/           # 可执行脚本
```

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd hk-ipo-research

# 安装（含开发依赖）
pip install -e ".[dev]"

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OPENROUTER_API_KEY
```

## 使用

```bash
# 处理单份招股书（MVP 模式）
python scripts/run_mvp.py data/raw_pdfs/your_prospectus.pdf

# 运行测试
pytest tests/
```

## 依赖说明

- **pymupdf4llm / pdfplumber**：PDF 解析（L1）
- **langextract**：LLM 驱动的结构化提取（L2），通过 OpenRouter 调用模型
- **pandas / matplotlib**：数据分析与可视化（L4）
