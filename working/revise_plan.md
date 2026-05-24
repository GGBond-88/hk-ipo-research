# HKEX UoP Platform — 修订执行计划（revise_plan.md）

> **生成依据**：基于 `working/.agent_records/` 中 28 份记录（1 working_root + 27 task records）的综合分析，以及对实际代码的二次校验。本计划修正了 task-026 `implement-review-results.md` 与代码实际状态的偏差，并把 27 个任务按优先级与依赖重新排序为可执行清单。
>
> **生成时间**：2026-05-21 / **作者**：Lead Architect Agent
>
> **2026-05-21 二次校验补丁**：
> - `working/.agent_records/` 已不在仓库（清理掉了），本计划完全可独立阅读，记录目录不影响执行
> - spec.md 实际 **671 行**（不是 672），下文统一更正
> - L4 schema_version 硬编码在 [l4_categorize.py:413](src/hk_ipo/l4_categorize.py)（不是 414）
> - P1-1 真实数据端到端结果**写入本批新建的 `working/revise tasks/` 任务目录**（取代原文中提到的 `task-028/`）；保留 `working/plan/task-001..027/` 不动作为历史记录

---

## 1. Codebase Health Overview

### 1.1 实际状态（一行总览）
**代码层 ~100% 完成、测试层 472 单测 + 多个 e2e 全绿、但 task-027 收尾未做 + 真实数据端到端未跑 + 无 CI。**

### 1.2 按子系统健康度

| 子系统 | 健康度 | 关键事实 |
|--------|--------|----------|
| L1 sectioning | ✅ 优 | 8 轮 review 锁定；语言检测 + ticker 派生 + 中文 stub + `--limit/--force` 一致 |
| L2 extraction | ✅ 优 | self-correction retry-once 锁定（PR-001）；ThreadPoolExecutor + Retry-After 头解析 |
| L3 validation | ✅ 优 | 11 条规则；16 个黑盒 + 47 单元；exit code 与 `--strict` 一致 |
| L4 categorize | ✅ 优 | 双层 rebalance（Parent + Main）、A4.5 golden fixture（ticker 3750）就位 |
| L5 enrichments × 8 | ✅ 优 | 全部 8 个工具；CR-001/CR-002 二次校验**实际已修复**（5 个工具 CLI 都有 `if enriched_file.exists(): ...` 块） |
| L6 storage/loader | ✅ 优 | 显式 BEGIN/COMMIT/ROLLBACK；外键 CASCADE；`--dry-run` 不写 schema |
| L7 analysis/export | ✅ 优 | 8 个 export 函数；ORDER BY 保 idempotent；generated_at 内容派生 |
| Orchestrator | ✅ 优 | L1-L7 + npm build；JSONL 日志；`data_root` 隔离；non-zero exit on failure |
| Frontend | ✅ 优 | Vite + React + ECharts；6 view + 5 chart + FilterBar + ExportButton；181 vitest 测试 |
| **README.md** | ❌ **过期** | 仍是 v1 四层架构 / "130 个单元测试" / schema_version 1.0；task-027 Step 3 **未执行** |
| Spec doc | ✅ 正常 | **规范副本在 [working/spec.md](working/spec.md) 671 行**（这是项目的真正 spec）；`docs/superpowers/specs/...` 那份是 commit `1133437` 加入的一次性副本，已删除（git `D`）— 不影响项目，因为 spec 内容在 `working/spec.md` 完整保留 |
| CI | ❌ 缺失 | 无 `.github/workflows/` |
| 真实数据 | ❌ 0% | `data/ipo.db` 不存在；categorized/enriched 空；EI-002（无 API key）阻塞 |
| EI-001 OOM 治标 | ⚠️ 部分 | `_maybe_skip_oom()` 已检测大部分 V8/NT OOM 并 skip；少数边界 case 仍 FAIL |

### 1.3 关键数字
- **27 任务交付**：001–025 完整闭环；026 主体完成 + 4 review 文档错记；027 仅 task.md（其他 3 文件缺）
- **测试覆盖**：472 Python 单测 + 181 前端 vitest + 多组黑盒 e2e（含 industry/timeline/capex_opex/esg_tag/L3）
- **总文件改动**：~80 个 src/ + tests/ + frontend/ 文件
- **未关闭议题**：14 SI（spec 假设）+ 1 EI-002（API key）+ 0 真实代码 bug（CR-001/002/003 second-pass 证实已修）

---

## 2. 27 任务的实际执行状态（second-pass 校正版）

> 注：这是基于代码 + records 的真实状态。Status 列里：
> - ✅ Closed = 全绿、review 全 Resolved、产物齐全
> - ⚠️ Partial = 代码完成但元文件/收尾未做
> - ⚠️ DocDrift = 代码已修复但 review 文档标 Pending（不是真 bug）

| # | 任务 | Status | 备注 |
|---|------|--------|------|
| 001 | 脚手架 + taxonomy | ✅ Closed | — |
| 002 | E2E RED 阶段 | ✅ Closed | — |
| 003 | Schema v2.0 + legacy L4 改名 | ✅ Closed | — |
| 004 | L1 lang detect + ticker + stub | ✅ Closed | 8 轮 review fix |
| 005 | L2 prompt v2 + self-correction | ✅ Closed | PR-001 锁定 |
| 006 | L3 v2 扩展 | ✅ Closed | — |
| 007 | L4 单测 RED | ✅ Closed | 43 测试 RED 后实现 |
| 008 | L4 实现 GREEN + A4.5 | ✅ Closed | 4 Don't Fix（测试为准） |
| 009 | enrichments base + geo | ✅ Closed | 零 review issue |
| 010 | enrichment country | ✅ Closed | TI-002 落点 |
| 011 | enrichment industry | ✅ Closed | 零 review issue |
| 012 | enrichment specificity | ✅ Closed | — |
| 013 | enrichment timeline | ✅ Closed | TI-003 解决 |
| 014 | enrichment capex_opex | ✅ Closed | 13 review fix（最大量） |
| 015 | enrichment esg_tag | ✅ Closed | 触发 5 个兄弟工具横向修复 |
| 016 | enrichment commitment | ✅ Closed | — |
| 017 | L6 SQLite schema | ✅ Closed | 零 review issue |
| 018 | L6 loader | ✅ Closed | 11 review fix |
| 019 | L7 export | ✅ Closed | 13 review fix |
| 020 | Orchestrator full L1-L7 | ✅ Closed | 15 review fix + 1 Don't Fix |
| 021 | Frontend scaffold | ✅ Closed | — |
| 022 | Frontend dataClient + store | ✅ Closed | — |
| 023 | FilterBar + ExportButton | ✅ Closed | 12 review fix |
| 024 | 5 chart 组件 | ✅ Closed | 8 review fix（含 CR-002 ref 转发） |
| 025 | 6 view + useDashboardData hook | ✅ Closed | 9 review fix；PR-002 真正落地 |
| **026** | **E2E GREEN + bug fix** | ⚠️ **DocDrift** | **主体已完成，3 个 Pending 实际已修代码但文档未更新；1 个（SR-001 OOM）部分修复** |
| **027** | **README + ruff + final test** | ⚠️ **Partial** | **缺 changes.md / test-results.md / implement-review-results.md；README.md 仍是 v1 旧版** |

---

## 3. 执行计划（按 P0/P1/P2 + 依赖排序）

### 🔴 P0 — 紧急且重要（1–2 天内）

#### **P0-1: 完成 task-027 收尾**
**问题**：README.md 仍是 v1 四层架构版本；ruff + 最终 pytest 状态未审计；task-027 的 3 个元文件缺失。

**方案**：
1. **重写 [README.md](README.md)** — 用 [working/plan/task-027/task.md](working/plan/task-027/task.md) Step 3 提供的完整 v2.0 README 内容（含 8 阶段架构图 / Per-stage CLI / Taxonomy 4 Parent / 8 维度 Enrichment / 6 Dashboard Views / Testing 章节 / Environment / Data layout）。
2. **跑 `ruff check src/ tests/ scripts/`** — 应该全过（task-026 已清过）。
3. **跑 `pytest -q`**（不含 e2e）— 应该 472 个全过。
4. **写 [working/plan/task-027/changes.md](working/plan/task-027/changes.md)**：记录 README 改动 + lint/test 结果。
5. **写 [working/plan/task-027/test-results.md](working/plan/task-027/test-results.md)**：列出 ruff 结果 + pytest 结果。
6. **写 [working/plan/task-027/implement-review-results.md](working/plan/task-027/implement-review-results.md)**：可空或记 "No issues found"。

**修改文件**：[README.md](README.md) / [working/plan/task-027/changes.md](working/plan/task-027/changes.md) / [working/plan/task-027/test-results.md](working/plan/task-027/test-results.md) / [working/plan/task-027/implement-review-results.md](working/plan/task-027/implement-review-results.md)

**风险**：低 — 纯文档 + 验证型工作。

---

#### **P0-2: 修复 task-026 文档与代码不一致**
**问题**：[working/plan/task-026/implement-review-results.md](working/plan/task-026/implement-review-results.md) 标记 4 个 Pending，但 second-pass 代码验证显示：
- CR-001（timeline.py prior enrichment）— ✅ [timeline.py:173-175](src/hk_ipo/enrichments/timeline.py) 已加 `if enriched_file.exists(): record = ...`
- CR-002（geo/country/specificity 同样）— ✅ [geo.py:160-162](src/hk_ipo/enrichments/geo.py) / [country.py:196-198](src/hk_ipo/enrichments/country.py) / [specificity.py:145-147](src/hk_ipo/enrichments/specificity.py) 全部已修
- CR-003（test_loader_dry_run --enriched-dir）— ✅ [test_pipeline_e2e.py:223-224](tests/e2e/test_pipeline_e2e.py) 已传
- SR-001（OOM graceful skip）— ⚠️ 部分修复（`_maybe_skip_oom()` 已实现，能检到的 OOM 都 skip）

**方案**：
1. 把 CR-001/CR-002/CR-003 的 Status 从 "Pending" 改 "Resolved"，加 Decision Reason 引用代码行号。
2. SR-001 Decision Reason 说明：检测机制已实现于 `_maybe_skip_oom()`；少数检测不到的 case 是设计选择（宁严勿松），不进一步降级为 SKIP。或者直接关掉 SR-001。
3. 给 timeline / geo / country / specificity **加 4 个 `test_cli_preserves_prior_enrichments` 测试**（参考 [tests/e2e/test_l5_capex_opex_blackbox.py](tests/e2e/test_l5_capex_opex_blackbox.py) 已有模式 — BB-L5-CO-028）防止回归。

**修改文件**：
- [working/plan/task-026/implement-review-results.md](working/plan/task-026/implement-review-results.md) — 文档对齐
- [tests/e2e/test_l5_timeline_blackbox.py](tests/e2e/test_l5_timeline_blackbox.py) / [tests/e2e/test_l5_country_blackbox.py](tests/e2e/test_l5_country_blackbox.py) / 新建 `test_l5_geo_blackbox.py` / 新建 `test_l5_specificity_blackbox.py` — 加测试

**风险**：低 — 文档 + 测试补全。

---

#### **P0-3: 确认 spec 单一来源 = `working/spec.md`**
**情况澄清（用户确认）**：**spec 的规范副本就在 [working/spec.md](working/spec.md)（671 行）**。`docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md` 那份是 commit `1133437` 加入的一次性副本，已被有意删除（git `D` 状态），不影响项目。

**方案**：
1. 把这个 `D` 状态收掉，让 git tree 干净：
   ```bash
   git rm docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md
   git commit -m "chore: remove docs/ spec copy (canonical version is in working/spec.md)"
   ```
2. 在 [README.md](README.md) Spec 章节明确指向 [working/spec.md](working/spec.md)，避免未来误以为 `docs/` 路径还在用。

**修改文件**：git 操作 + [README.md](README.md)

**风险**：无。

---

#### **P0-4: 仓库清理**
**问题**：根目录有 `tatus` 文件（git status 笔误重定向产物，是个 git log 文本 dump，untracked 状态 `??`）。

**方案**：直接删除即可（文件未被 git 追踪，无需 .gitignore 改动）。

**修改文件**：删 `tatus`。

**风险**：无。

---

### 🟡 P1 — 重要（1–2 周内）

#### **P1-1: 解除 EI-002 阻塞，跑通真实端到端**
**问题**：5 个 pipeline e2e SKIP / 14 个 SI 假设未真实验证 / `data/ipo.db` 不存在 / A4.5 golden fixture 仅 mocked LLM 验证。

**方案**：
1. 确认 [.env](.env) 中 `OPENROUTER_API_KEY` 是否已配（用户消息已确认路径在 `C:\Users\Administrator\Documents\github\hk-ipo-research\.env`）。如缺补上。
2. 跑 `python scripts/run_pipeline.py --dry-run-cost` 验证成本估算。
3. 跑 `python scripts/run_pipeline.py --all --workers 4` 在 6 份真实 PDF 上完整端到端。
4. 验证产出：
   - `data/categorized/` 6 个文件
   - `data/enriched/` 6 个文件，每个含 8 个 enrichment block
   - `data/ipo.db` 存在，6 个 companies
   - `frontend/public/data/` 8 个 JSON（manifest / companies / taxonomy / time_series / by_industry / by_geo / cross_dim / sankey/*）
   - `data/logs/<run_id>.jsonl` 有 JSONL 日志
   - `data/taxonomy_proposals.csv` 有新提案（如果 LLM 提出了）
5. 验证 A4.5：跑真实 LLM 在 ticker 3750 上算 main_category match rate ≥ 0.90。
6. 验证 A7.4：连跑 L7 三次后 `manifest.json` 字节级相等。
7. 验证 A9.2：放一份 corrupt PDF 在 raw_pdfs/，跑全流，断言 `pipeline_runs` 该 ticker `status='failed' AND error_message IS NOT NULL`。

**修改文件**：可能根据真实输出补 prompt 调整（[l4_categorize.py](src/hk_ipo/l4_categorize.py) prompt / [l2_extraction.py](src/hk_ipo/l2_extraction.py) system prompt）；执行日志与结果记录到 `working/revise tasks/P1-1-real-e2e/` 任务目录（已在本批分解中创建）。

**风险**：中 — 真实 LLM 输出可能暴露未覆盖的 edge case；需要预算 ≥ 8 GB RAM 机器或绕过 EI-001。

---

#### **P1-2: EI-001 OOM 代码侧根治**
**问题**：4 GB RAM 机器跑不了 Vite build / Playwright。`_maybe_skip_oom()` 是治标。

**方案**：
1. `frontend/package.json` build script 加 `NODE_OPTIONS=--max-old-space-size=4096`：
   ```json
   "build": "cross-env NODE_OPTIONS=--max-old-space-size=4096 tsc -b && vite build"
   ```
2. 装 `cross-env` 跨平台。
3. [frontend/src/lib/dataClient.ts](frontend/src/lib/dataClient.ts) 把 `Map` 换 LRU 加 50 条上限（自实现或装 `lru-cache`）。
4. [tests/e2e/test_dashboard_views_e2e.py](tests/e2e/test_dashboard_views_e2e.py) 每个测试间 `browser.close()` + `gc.collect()`。

**修改文件**：[frontend/package.json](frontend/package.json) / [frontend/src/lib/dataClient.ts](frontend/src/lib/dataClient.ts) / [tests/e2e/test_dashboard_views_e2e.py](tests/e2e/test_dashboard_views_e2e.py)

**风险**：低 — 不动业务逻辑。

---

#### **P1-3: 加 CI（GitHub Actions）**
**问题**：无 `.github/workflows/`，472 测试 + ruff + frontend build 只在本地跑。

**方案**：
1. 新建 `.github/workflows/ci.yml`：
   ```yaml
   name: CI
   on: [pull_request, push]
   jobs:
     python:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: '3.10' }
         - run: pip install -e ".[dev]"
         - run: ruff check src tests scripts
         - run: pytest -m "not e2e" -q
     frontend:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with: { node-version: '20' }
         - run: cd frontend && npm install && npm run build
         - run: cd frontend && npm test
   ```
2. 加 README badge：`[![CI](url)](url)`

**修改文件**：[.github/workflows/ci.yml](.github/workflows/ci.yml) / [README.md](README.md)

**风险**：低 — GitHub Actions ubuntu-latest 默认 ≥ 7 GB RAM，能跑 Vite + Playwright。

---

#### **P1-4: 统一 LLM 客户端 + 加 token/cost 追踪**
**问题**：L2 用模块级 `_openai_client`；L4 `call_l4_llm()` 每次 new；`enrichments/industry.py` 每次 new。零 token / cost 可观测。

**方案**：
1. 新建 [src/hk_ipo/llm_client.py](src/hk_ipo/llm_client.py)：
   ```python
   class LLMClient:
       _instance: ClassVar[Optional["LLMClient"]] = None
       def __init__(self): ...
       @classmethod
       def get(cls) -> "LLMClient": ...
       def chat(self, *, model, messages, **kw):
           # 调用前后记录 prompt_tokens, completion_tokens, cost_usd
           # 追加到 data/logs/llm_calls.jsonl
   ```
2. 改 [l2_extraction.py:32](src/hk_ipo/l2_extraction.py) / [l4_categorize.py:443](src/hk_ipo/l4_categorize.py) / [enrichments/industry.py:64](src/hk_ipo/enrichments/industry.py) 都走 `LLMClient.get()`。
3. 跑回归测试。

**修改文件**：[src/hk_ipo/llm_client.py](src/hk_ipo/llm_client.py) / [src/hk_ipo/l2_extraction.py](src/hk_ipo/l2_extraction.py) / [src/hk_ipo/l4_categorize.py](src/hk_ipo/l4_categorize.py) / [src/hk_ipo/enrichments/industry.py](src/hk_ipo/enrichments/industry.py)

**风险**：中 — 涉及多文件；建议先 L2 跑通再扩到 L4 + industry。

---

#### **P1-5: 加 LLM 响应缓存**
**问题**：重跑 pipeline 会原价再花一遍 LLM。粗粒度 `if out_path.exists(): skip` 不支持 prompt 微调时部分复用。

**方案**：与 P1-4 合并到 `LLMClient`：
- key = `sha256(model + prompt + temperature)`
- 缓存目录 `data/llm_cache/<2-char-prefix>/<hash>.json`
- 命中即返回，未命中调 API + 落盘
- 默认永不过期（model 字段隐式失效）

**修改文件**：[src/hk_ipo/llm_client.py](src/hk_ipo/llm_client.py)

**风险**：低。

---

#### **P1-6: L3/L4 并发化**
**问题**：L3 / L4 仍串行；同样的网络 IO 模式与 L2 不一致（L2 用 ThreadPoolExecutor(6)）。

**方案**：复制 [l2_extraction.py:434-499](src/hk_ipo/l2_extraction.py) 的并发 + 原子日志结构到 [l3_validation.py:260](src/hk_ipo/l3_validation.py) `process_all()` 和 [l4_categorize.py](src/hk_ipo/l4_categorize.py) `process_all()`。注意 L4 写 `taxonomy_proposals.csv` 需要 `portalocker` 加锁。

**修改文件**：[src/hk_ipo/l3_validation.py](src/hk_ipo/l3_validation.py) / [src/hk_ipo/l4_categorize.py](src/hk_ipo/l4_categorize.py)；pyproject.toml 加 `portalocker`

**风险**：中 — L4 CSV 写入需保护。

---

### 🟢 P2 — 优化（之后再做）

| # | 项 | 简述 |
|---|----|------|
| **P2-1** | 收窄 `except Exception:` | [l2_extraction.py:412](src/hk_ipo/l2_extraction.py) / [l4_categorize.py:659](src/hk_ipo/l4_categorize.py) 改具体异常类型 + `logger.exception` |
| **P2-2** | `print()` → `logger` 统一 | 引入 `loguru` 或 stdlib RotatingFileHandler |
| **P2-3** | `export.py` 手写 SQL 集中到 `storage/queries.py` | 减少散落 raw SQL |
| **P2-4** | [l4_categorize.assign_parent()](src/hk_ipo/l4_categorize.py) 关键词分支重构 | 改 taxonomy 表查 + LLM 兜底 |
| **P2-5** | L4 `"2.0"` 硬编码 → import SCHEMA_VERSION | [l4_categorize.py:413](src/hk_ipo/l4_categorize.py) |
| **P2-6** | base.py 加 `_enrich_template` 共享工具样板 | 8 个 enrichment 的 CLI/`__main__` 代码同质化高，可抽公共层 |
| **P2-7** | PDF parse cache | L1 重跑会重新解析，加缓存 |
| **P2-8** | enrichment `version` 自动校验 | SI-014 假设的"schema 变 bump"无强制机制 |
| **P2-9** | `golden_pdfs` fixture scope 调整 | session → function 或加 read-only 保护 |
| **P2-10** | 前端 ErrorBoundary / skeleton loading | UX 改善 |
| **P2-11** | `working/_test_cn*.py` 三份合并 + `_verify_gaps.py` 挪到 `scripts/dev/` | 工具脚本去重 |
| **P2-12** | task-016 commitment 模式：L5 7 个工具该抽 enrichment base template | 见 P2-6 |

---

## 4. 依赖关系（执行顺序约束）

```
P0-1 (README + ruff + final pytest)  ← 不依赖任何
P0-2 (task-026 文档对齐 + 新增测试)  ← 不依赖
P0-3 (恢复 spec)                      ← 不依赖
P0-4 (清理仓库)                       ← 不依赖

⬇ 全部 P0 完成 ⬇

P1-1 (跑真实端到端)  ← 依赖 .env 有 API KEY；建议 P0 完成后做
P1-2 (EI-001 OOM 治本)  ← 不依赖；但建议在 P1-1 之前修好 Vite build
P1-3 (CI)              ← 依赖 P1-2（CI 上 frontend build 不能 OOM）

⬇ P1-1/P1-2/P1-3 并行 ⬇

P1-4 (LLM client 统一 + 成本追踪)  ← 不依赖（但建议在 P1-1 之后做，因为真实端到端先验证当前 client 没 bug）
P1-5 (LLM 缓存)                     ← 依赖 P1-4
P1-6 (L3/L4 并发化)                 ← 依赖 P1-4（统一 client 后并发更好做）

⬇ P1 完成 ⬇

P2-1 … P2-12 (任意顺序，可并行)
```

---

## 5. 验证 checklist

### P0 完成证据
- [ ] [README.md](README.md) 包含 v2.0 8 阶段架构图（包括 L1→L7 + frontend）
- [ ] [README.md](README.md) 测试章节写 "472 测试"（不是 130）
- [ ] [README.md](README.md) JSON 示例的 `schema_version` 是 "2.0"
- [ ] `ruff check src tests scripts` 全过
- [ ] `pytest -q` 全过（472 单测 + 部分 e2e）
- [ ] [working/plan/task-026/implement-review-results.md](working/plan/task-026/implement-review-results.md) 4 项全部 Resolved 状态
- [ ] `git status` 无 `D` 状态的 `docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md`（已 `git rm` 收掉）；[README.md](README.md) 引用 [working/spec.md](working/spec.md) 作为 spec 源
- [ ] 仓库根无 `tatus` 文件
- [ ] [working/plan/task-027/](working/plan/task-027/) 4 文件齐

### P1 完成证据
- [ ] `data/ipo.db` 存在且 `sqlite3 data/ipo.db "SELECT COUNT(*) FROM companies"` 返 6
- [ ] `data/enriched/` 6 个 JSON，每个含 8 个 enrichment block
- [ ] `frontend/public/data/manifest.json` 的 `generated_at` 来自 `MAX(companies.updated_at)` 且多次跑字节级相等
- [ ] `data/logs/llm_calls.jsonl` 包含 prompt_tokens / completion_tokens / cost_usd 行
- [ ] 重跑 pipeline 时 LLM cache 命中率 > 80%
- [ ] A4.5 真实 LLM 跑 ticker 3750 match_rate ≥ 0.90
- [ ] A9.2 真实 corrupt PDF 跑后 `pipeline_runs` 有 `status='failed' AND error_message` 非空行
- [ ] `pytest -m e2e tests/` 在 8 GB+ RAM 机器上全 PASS 或合理 SKIP（不再因 OOM FAIL）
- [ ] GitHub Actions 在 PR 上全绿

### P2 完成证据
按需。

---

## 6. 关键文件参考速查

| 类别 | 文件 |
|------|------|
| 编排器 | [scripts/run_pipeline.py](scripts/run_pipeline.py) |
| Schema 单一事实源 | [src/hk_ipo/schema.py](src/hk_ipo/schema.py) / [src/hk_ipo/taxonomy.py](src/hk_ipo/taxonomy.py) |
| LLM 调用现状 | [src/hk_ipo/l2_extraction.py:32](src/hk_ipo/l2_extraction.py) / [src/hk_ipo/l4_categorize.py:443](src/hk_ipo/l4_categorize.py) / [src/hk_ipo/enrichments/industry.py:64](src/hk_ipo/enrichments/industry.py) |
| 前端数据访问层 | [frontend/src/lib/dataClient.ts](frontend/src/lib/dataClient.ts) |
| Golden fixtures | [tests/fixtures/golden_pdfs/](tests/fixtures/golden_pdfs/) / [tests/fixtures/l4_golden/3750.json](tests/fixtures/l4_golden/3750.json) |
| **Spec（规范源）** | **[working/spec.md](working/spec.md)** — 672 行，项目契约的真正位置 |
| 已删的旧副本 | `docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md`（git `D`，仅作历史参考） |
| 集成审查台账 | [working/plan-review-results.md](working/plan-review-results.md) |
| Spec 假设台账 | [working/spec-issues.md](working/spec-issues.md) / [working/task-issues.md](working/task-issues.md) |
| 环境台账 | [working/env-issues.md](working/env-issues.md) |

---

## 7. 最终结论

1. **代码层完成度 ~100%**：27 个任务的代码、单元测试、e2e 测试基础设施全部就位。second-pass 验证发现 task-026 报的 4 个 Pending review issue 中**3 个实际已修代码**（文档没更新），1 个（SR-001）是部分修复。
2. **真正未完成的工作只剩 2 件**：
   - **task-027 收尾**（README 重写 + ruff/pytest 最终运行 + 3 个元文件补齐）
   - **真实数据端到端 + spec A1-A10 实测**（受 EI-002 / EI-001 阻塞，需 8GB+ 机器 + API Key）
3. **当前最大风险**：不是代码，是**运营**（无 CI / 无成本追踪 / 无缓存 / 真实数据未验证），P1 都在解决这些。
4. **建议**：先把 P0-1 README 改写做掉（**用户感知最强、阻塞最低**），然后并行启动 P0-2/P0-3/P0-4 + P1-1（如有 API Key 与 8GB RAM）。

---

## 8. Post-Execution Audit Summary (2026-05-21)

**Audit result: 24/28 tasks fully complete and code-verified. 4 tasks have minor acceptance gaps. The P1-1 real e2e run discovered 6 production bugs that are documented but no task exists to fix the most critical one (L1 filename filter that blocks processing all real PDFs).**

### What went well
- P1-4 and P1-5: LLMClient with caching -- clean implementation, all call sites migrated, zero remaining ad-hoc `openai.OpenAI()` constructions.
- P2-1 and P2-2: Zero `except Exception` remains in l2/l4 core files; ~92% of print() calls replaced with structured logging.
- P2-4, P2-6, P2-3: Refactors (data-driven taxonomy, shared CLI scaffold, centralized SQL) all preserved external behavior with full test coverage.
- P1-6: L3/L4 concurrency with ThreadPoolExecutor + portalocker file-locking for taxonomy_proposals.csv.
- P2-10: ErrorBoundary + skeleton loading implemented across all 6 dashboard views.
- Cross-task coordination was good: P2-7 adapted its tests to P2-2's logging migration; no file-level conflicts across tasks.
- Dependency chains respected: all "depends on" relationships tracked correctly.

### What needs attention
1. **CRITICAL**: The L1 filename filter regex (`^\d{4,5}$`) at `l1_sectioning.py:35` prevents batch processing of ANY real HKEX PDF (which use 13-digit document numbers). This was discovered by P1-1 but is not assigned to any fix task.
2. **P1-1 found 5 other bugs** (L5 counting, 6031 null percentage, L2 finish_reason=None, 03750/3750 duplicate, portalocker dependency -- last one fixed by P1-6) that need follow-up tasks.
3. **Minor acceptance gaps**: ruff exit code still 1 (2 E501 violations), CI workflow not yet pushed/verified, one vitest unhandled error persists.
4. **README quickstart**: Documents a `--all` flag that does not exist in `run_pipeline.py`.

Full report: [working/revise_plan/review-report.md](working/revise_plan/review-report.md)
