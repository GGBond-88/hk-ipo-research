# hk-ipo-research

港股 IPO 招股书「Use of Proceeds（募集资金用途）」章节的自动化提取与分析工具。

## 项目简介

本项目以四层流水线处理港交所上市公司招股书 PDF，最终输出结构化的募资用途数据及跨公司对比分析报告，适用于投行研究、学术研究及投资尽调场景。

L2 提取层直接调用 OpenAI-compatible API（通过 OpenRouter），内置自校正循环：首次提取失败 L3 校验时，自动将错误反馈给模型进行二次提取；仍失败则标记 `needs_human_review: true`。

## 四层架构

| 层级 | 模块 | 职责 |
|------|------|------|
| **L1** | `l1_sectioning.py` | PDF 解析与章节定位：将原始 PDF 转为 Markdown，定位并切割 "Use of Proceeds" 章节 |
| **L2** | `l2_extraction.py` | LLM 结构化提取：直接调用 OpenAI SDK，从章节文本提取「项目 / 金额 / 百分比 / 分类 / 原文」，输出 JSON；内置自校正循环 |
| **L3** | `l3_validation.py` | 数值校验：校验金额加总与百分比一致性（±1%），验证分类词汇表与 schema 版本 |
| **L4** | `l4_analysis.py` | 统计分析与可视化：汇总多份招股书，生成行业对比图表与 CSV 摘要报告 |

## 目录结构

```
hk-ipo-research/
├── data/
│   ├── raw_pdfs/      # 原始招股书 PDF（不入 git）
│   ├── sections/      # L1 输出的章节文本（不入 git）
│   ├── extracted/     # L2 输出的结构化 JSON（不入 git）
│   └── reports/       # L4 生成的分析报告（CSV / PNG / Markdown）
├── src/hk_ipo/
│   ├── schema.py          # 单一事实源：字段定义、分类词汇表、SCHEMA_VERSION
│   ├── l1_sectioning.py
│   ├── l2_extraction.py
│   ├── l3_validation.py
│   └── l4_analysis.py
├── tests/             # 130 个单元测试（pytest）
└── scripts/
    ├── run_pipeline.py    # 批量运行 L1→L2→L3→L4
    └── run_mvp.py         # 单文件快速验证
```

## 安装

```bash
git clone https://github.com/GGBond-88/hk-ipo-research.git
cd hk-ipo-research

# 安装（含开发依赖）
pip install -e ".[dev]"

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OPENROUTER_API_KEY
# 可选：L2_TEXT_MODEL=deepseek/deepseek-v4-pro（默认值）
```

## 使用

### 批量处理（推荐）

```bash
# 处理 data/raw_pdfs/ 下的所有 PDF，并行 6 线程
python scripts/run_pipeline.py

# 强制重新处理（忽略已有输出）
python scripts/run_pipeline.py --force

# 自定义 PDF 目录和并发数
python scripts/run_pipeline.py --pdf-dir /path/to/pdfs --workers 4

# 跳过 L4 分析（仅提取和验证）
python scripts/run_pipeline.py --skip-l4
```

### 单文件快速验证

```bash
python scripts/run_mvp.py data/raw_pdfs/your_prospectus.pdf
```

### 分层单独运行

```bash
# L1：PDF 解析
python -m hk_ipo.l1_sectioning --all

# L2：LLM 提取（--force 覆盖已有输出）
python -m hk_ipo.l2_extraction --all --force

# L3：校验
python -m hk_ipo.l3_validation --all

# L4：分析报告
python -m hk_ipo.l4_analysis
```

### 运行测试

```bash
pytest tests/          # 130 个测试
ruff check src/ tests/ # lint
```

## L2 输出格式

```json
{
  "company_file": "example.pdf",
  "hk_ticker": "9999",
  "document_date": "2025-01-01",
  "schema_version": "1.0",
  "total_net_proceeds_hkd_million": 5000.0,
  "currency": "HKD",
  "uses": [
    {
      "use_id": "use_001",
      "category": "Manufacturing expansion",
      "percentage": 60.0,
      "amount_hkd_million": 3000.0,
      "description": "Build new factory in Europe.",
      "source_text": "Approximately 60% or HK$3,000 million will be used..."
    }
  ],
  "validation_preview": {
    "percentage_sum": 100.0,
    "top_level_count": 2,
    "total_items_count": 2
  }
}
```

## 依赖说明

- **pymupdf4llm / pdfplumber**：PDF 解析（L1）
- **openai**：直接调用 LLM（L2），通过 OpenRouter 路由至 deepseek/deepseek-v4-pro
- **pydantic**：输出 schema 校验
- **pandas / matplotlib**：数据分析与可视化（L4）
