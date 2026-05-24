# Task 027: README update, ruff check, final verification

## Project Overview

- **Goal:** Eight-stage CLI + React dashboard for HKEX use-of-proceeds analytics. All implementation complete.
- **Architecture:** L1 -> L2 -> L3 -> L4 -> L5 enrichments -> L6 SQLite -> L7 export -> Frontend dashboard.
- **Tech Stack:** Python 3.10+, React + Vite + TypeScript + ECharts.

## Task Objective

Update README.md with the v2.0 architecture, new pipeline diagram, enrichment tool list, dashboard quickstart, and CLI usage. Run final lint and test pass. This is the cleanup/handoff task.

This is Task 27 of 27.

---

**Files:**
- Modify: `README.md`
- (No code changes unless ruff uncovers issues)

- [ ] **Step 1: Run ruff on the entire project**

Run: `ruff check src/ tests/ scripts/`

Expected: No errors. If errors exist, fix them before proceeding.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -q`

Expected: All tests pass (E2E may skip if no API key). Note the test count.

- [ ] **Step 3: Update `README.md`**

Read the current README, then replace it with the v2.0 content:

```markdown
# HK IPO Use-of-Proceeds Research

Extract, classify, and analyze "Use of Proceeds" sections from HKEX Global Offering prospectuses.

## Architecture (v2.0)

```
data/raw_pdfs/                                 [manual drop-in]
        |
        v
+-------------------------------------------------------------+
| L1  l1_sectioning.py    PDF -> Markdown -> Use-of-Proceeds  |
|                         section text + tables.              |
|                         Detects language; skips zh PDFs.    |
+-------------------------------------------------------------+
        |  data/sections/<ticker>.json
        v
+-------------------------------------------------------------+
| L2  l2_extraction.py    LLM Pass 1: flat extraction         |
|                         category_raw, percentage, amount    |
+-------------------------------------------------------------+
        |  data/extracted/<ticker>.json
        v
+-------------------------------------------------------------+
| L3  l3_validation.py    Numeric checks (sum +/-1%),         |
|                         field presence, schema_version.     |
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| L4  l4_categorize.py    LLM Pass 2: classify into           |
|                         Parent / Main / Sub taxonomy and    |
|                         enforce 100%-sum constraints.       |
+-------------------------------------------------------------+
        |  data/categorized/<ticker>.json
        v
+-------------------------------------------------------------+
| L5  enrichments/        Modular tools (one CLI per dim):    |
|       geo.py, country.py, industry.py, specificity.py,      |
|       timeline.py, capex_opex.py, esg_tag.py, commitment.py |
+-------------------------------------------------------------+
        |  data/enriched/<ticker>.json
        v
+-------------------------------------------------------------+
| L6  storage/loader.py   Idempotent upsert into SQLite       |
+-------------------------------------------------------------+
        |  data/ipo.db
        v
+-------------------------------------------------------------+
| L7  analysis/export.py  Pre-bake JSON for dashboard         |
+-------------------------------------------------------------+
        |  frontend/public/data/*.json
        v
+-------------------------------------------------------------+
| frontend/   React + Vite + ECharts dashboard                |
|             Sankey, stacked bars, time series, heatmap,     |
|             scatter, filterable table views.                |
+-------------------------------------------------------------+
```

## Quickstart

### 1. Setup

```bash
# Python dependencies
pip install -e ".[dev]"

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Place PDFs

Drop prospectus PDFs named after their HK ticker (e.g., `01234.pdf`) into:

```
data/raw_pdfs/
```

### 3. Run the pipeline

```bash
# Full pipeline (all stages)
python scripts/run_pipeline.py --all --workers 4

# Dry-run cost estimation (no API calls)
python scripts/run_pipeline.py --dry-run-cost

# Run specific stages only
python scripts/run_pipeline.py --only L1,L2,L4 --limit 3

# With frontend build
python scripts/run_pipeline.py --all --build-frontend
```

### 4. View the dashboard

```bash
cd frontend
npm run dev      # http://localhost:5173
```

Or open `frontend/dist/index.html` after `npm run build`.

## Per-Stage CLI

Each stage is independently runnable:

```bash
python -m hk_ipo.l1_sectioning --all [--limit N] [--force]
python -m hk_ipo.l2_extraction --all [--force] [--workers 6]
python -m hk_ipo.l3_validation --all [--strict]
python -m hk_ipo.l4_categorize --all [--limit N] [--model deepseek/deepseek-v4-pro]

# Enrichments
python -m hk_ipo.enrichments.geo          --all [--force]
python -m hk_ipo.enrichments.country      --all [--force]
python -m hk_ipo.enrichments.industry     --all [--force] [--source prospectus|manual]
python -m hk_ipo.enrichments.specificity  --all [--force]
python -m hk_ipo.enrichments.timeline     --all [--force]
python -m hk_ipo.enrichments.capex_opex   --all [--force]
python -m hk_ipo.enrichments.esg_tag      --all [--force]
python -m hk_ipo.enrichments.commitment   --all [--force]

python -m hk_ipo.storage.loader --all [--db data/ipo.db] [--dry-run]
python -m hk_ipo.analysis.export --db data/ipo.db --out frontend/public/data/
```

## Taxonomy

Four Parent categories (fixed):
- **Growth** (R&D and Technology, Product Development, Sales and Marketing, Capacity Expansion, Geographic Expansion, Acquisitions and Strategic Investments, Infrastructure and Network)
- **Financing** (Debt Repayment, Refinancing, Interest Payments)
- **Working Capital** (General Working Capital, Inventory Procurement, Receivables / Payables Management, Day-to-day Operations)
- **Others** (General Corporate Purposes, Reserves / Contingencies, Unallocated / Unspecified)

See `src/hk_ipo/taxonomy.py` for the full closed vocabulary.

## Enrichment Dimensions

| Dimension | Scope | Values |
|-----------|-------|--------|
| geo | per use | domestic_hk, mainland, overseas |
| country | per use, list | ISO 2-letter codes |
| industry | per company | GICS industry name |
| specificity | per use | specific, general, vague |
| timeline | per use | 0-12m, 12-24m, 24-36m, 36m+, unspecified |
| capex_opex | per use | capex, opex, financial |
| esg_tag | per use, optional | green, social, governance |
| commitment | per use | committed, discretionary |

## Dashboard Views

- **Overview** — KPI tiles + stacked bar by industry
- **Company** — Sankey diagram per company with ticker picker
- **Temporal** — Time series of parent allocation by listing year
- **Industry** — Heatmap of industry x parent allocation
- **Geographic** — Allocation by geographic region
- **Cross-Dim** — Configurable scatter plot across any two numeric dimensions

## Testing

```bash
# Unit tests
pytest tests/ --ignore=tests/e2e

# End-to-end tests (requires API key and golden PDFs)
pytest tests/e2e -m e2e

# Lint
ruff check src/ tests/
```

## Environment

Set `OPENROUTER_API_KEY` in `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Optional overrides:
```
L2_TEXT_MODEL=openai/gpt-4o
```

## Data Layout

```
data/
  raw_pdfs/           # input PDFs (manual drop-in)
  sections/           # L1 output
  extracted/          # L2 output
  categorized/        # L4 output
  enriched/           # L5 output (mutated by each enrichment)
  ipo.db              # L6 SQLite
  taxonomy_proposals.csv  # L4 novel sub-labels
  industry_overrides.csv  # Optional: ticker -> industry manual overrides
  logs/               # Pipeline run logs

frontend/public/data/ # L7 output — consumed by the dashboard
  manifest.json
  companies.json
  taxonomy.json
  time_series.json
  by_industry.json
  by_geo.json
  cross_dim.json
  sankey/<ticker>.json
```
```

- [ ] **Step 4: Confirm the README renders correctly**

Skim the updated file visually or run `python -c "open('README.md').read()"` to verify no syntax issues.

- [ ] **Step 5: Final ruff check**

Run: `ruff check src/ tests/ scripts/`

Expected: No errors.

- [ ] **Step 6: Final test run**

Run: `python -m pytest -q`

Expected: All tests pass (E2E may skip). Note the final test count.

- [ ] **Step 7: Pipeline smoke test (if API key available)**

If `OPENROUTER_API_KEY` is set and at least one PDF is in `data/raw_pdfs/`:

```bash
python scripts/run_pipeline.py --limit 1 --force
```

Expected: Pipeline runs L1 -> L7 for one PDF. No crashes.

- [ ] **Step 8: Project is complete**

The project is ready for:
- `git status` to review changes
- `git add` + `git commit` to commit
- Manual QA of the dashboard with `cd frontend && npm run build && npx serve dist/`
