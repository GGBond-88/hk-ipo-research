# Task 023: Frontend FilterBar + ExportButton components

## Project Overview

- **Goal:** React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** FilterBar reads/writes global Zustand filter state. ExportButton provides per-chart PNG/CSV export via ECharts `getDataURL` and a helper CSV serializer.
- **Tech Stack:** React + TypeScript + Zustand.

## Task Objective

Implement `FilterBar.tsx` (5 dropdowns wired to Zustand) and `ExportButton.tsx` (PNG + CSV export with ECharts instance ref). Both reusable components.

This is Task 23 of 27.

---

**Files:**
- Create: `frontend/src/components/FilterBar.tsx`
- Create: `frontend/src/components/ExportButton.tsx`

- [ ] **Step 1: Get the set of available filter values**

Add a utility file `frontend/src/lib/filterOptions.ts`:

```typescript
import type { CompaniesData, CrossDimRow, IndustryData, GeoData } from './sharedTypes';

export interface FilterOptions {
  years: string[];
  industries: string[];
  countries: string[];
  parents: string[];
  commitments: string[];
}

export function deriveFilterOptions(
  companies: CompaniesData,
  crossDim: CrossDimRow[],
  byIndustry: IndustryData,
  byGeo: GeoData,
): FilterOptions {
  const years = Array.from(
    new Set(
      companies.companies
        .map((c) => c.listing_date?.slice(0, 4))
        .filter(Boolean)
    )
  ).sort() as string[];

  const industries = Object.keys(byIndustry).sort();
  const countries = Object.keys(byGeo).sort();
  const parents = ['Growth', 'Financing', 'Working Capital', 'Others'];
  const commitments = ['committed', 'discretionary'];

  return { years, industries, countries, parents, commitments };
}
```

- [ ] **Step 2: Create `frontend/src/components/FilterBar.tsx`**

```tsx
import { useStore } from '../lib/store';
import type { FilterState } from '../lib/store';
import type { FilterOptions } from '../lib/filterOptions';

interface FilterBarProps {
  options: FilterOptions;
  showTickerPicker?: boolean;
  tickers?: { hk_ticker: string; company_name_en: string }[];
}

const LABELS: Record<keyof FilterState, string> = {
  year: 'Year',
  industry: 'Industry',
  country: 'Country',
  parent: 'Parent',
  commitment: 'Commitment',
};

type FilterKey = keyof FilterState;

const DIM_KEYS: FilterKey[] = ['year', 'industry', 'country', 'parent', 'commitment'];

function toSelectItems(values: string[]) {
  return values.map((v) => ({ value: v, label: v }));
}

export function FilterBar({ options, showTickerPicker, tickers }: FilterBarProps) {
  const { year, industry, country, parent, commitment, setFilter, resetFilters,
          activeTicker, setActiveTicker } = useStore();

  const optionMap: Record<string, string[]> = {
    year: options.years,
    industry: options.industries,
    country: options.countries,
    parent: options.parents,
    commitment: options.commitments,
  };

  const valueMap: Record<string, string> = {
    year: year ?? '', industry: industry ?? '',
    country: country ?? '', parent: parent ?? '',
    commitment: commitment ?? '',
  };

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginBottom: 16 }}>
      {DIM_KEYS.map((dim) => (
        <label key={dim} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 14 }}>
          {LABELS[dim]}:
          <select
            value={valueMap[dim]}
            onChange={(e) => setFilter(dim, e.target.value || null)}
            style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}
          >
            <option value="">All</option>
            {toSelectItems(optionMap[dim] ?? []).map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
      ))}
      {showTickerPicker && tickers && (
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 14 }}>
          Company:
          <select
            value={activeTicker ?? ''}
            onChange={(e) => setActiveTicker(e.target.value || null)}
            style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}
          >
            <option value="">Select...</option>
            {tickers.map((t) => (
              <option key={t.hk_ticker} value={t.hk_ticker}>
                {t.hk_ticker} - {t.company_name_en}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        onClick={resetFilters}
        style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #ccc',
                 background: '#fff', cursor: 'pointer', fontSize: 13 }}
      >
        Reset Filters
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/ExportButton.tsx`**

```tsx
import { type RefObject } from 'react';
import type { EChartsType } from 'echarts';

interface ExportButtonProps {
  chartRef: RefObject<EChartsType | null>;
  chartLabel: string;
  /** Optional CSV data: { headers: string[], rows: string[][] } */
  csvData?: { headers: string[]; rows: string[][] } | null;
}

function toCsvContent(headers: string[], rows: string[][]): string {
  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const headerLine = headers.map(escape).join(',');
  const dataLines = rows.map((row) => row.map(escape).join(','));
  return [headerLine, ...dataLines].join('\n');
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportButton({ chartRef, chartLabel, csvData }: ExportButtonProps) {
  const handlePng = () => {
    const instance = chartRef?.current;
    if (!instance) return;
    const dataUrl = instance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = `${chartLabel.replace(/\s+/g, '_')}.png`;
    link.click();
  };

  const handleCsv = () => {
    if (!csvData) return;
    const content = toCsvContent(csvData.headers, csvData.rows);
    downloadBlob(content, `${chartLabel.replace(/\s+/g, '_')}.csv`, 'text/csv');
  };

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <button
        onClick={handlePng}
        style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #ccc',
                 background: '#fff', cursor: 'pointer', fontSize: 12 }}
      >
        Export PNG
      </button>
      {csvData && (
        <button
          onClick={handleCsv}
          style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #ccc',
                   background: '#fff', cursor: 'pointer', fontSize: 12 }}
        >
          Export CSV
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run:
```bash
cd frontend
npm run build
```

Expected: No TypeScript errors.
