# Task 022: Frontend data client + Zustand store

## Project Overview

- **Goal:** Build the React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** Static dashboard reads pre-baked JSON. The data client fetches and caches JSON files. Zustand store holds global filter state.
- **Tech Stack:** Vite + React + TypeScript + Zustand.

## Task Objective

Implement `lib/dataClient.ts` (fetch + cache all JSON files) and `lib/store.ts` (Zustand store with `{year, industry, country, parent, commitment}` filter state). Wire the store into App.tsx.

This is Task 22 of 27.

---

**Files:**
- Create: `frontend/src/lib/sharedTypes.ts`
- Create: `frontend/src/lib/dataClient.ts`
- Create: `frontend/src/lib/store.ts`
- Create: `frontend/src/lib/filterUtils.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/lib/sharedTypes.ts`**

```typescript
// ── Data shapes for pre-baked JSON files ────────────────────────────────

export interface Company {
  hk_ticker: string;
  company_name_en: string;
  listing_date: string | null;
  document_date: string | null;
  industry_primary: string | null;
  industry_source: string | null;
  total_net_proceeds: number | null;
  currency: string;
  needs_human_review: boolean;
}

export interface CompaniesData {
  companies: Company[];
  count: number;
}

export interface SankeyNode {
  name: string;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
  total_net_proceeds: number;
}

export interface TaxonomyData {
  categories: Record<string, Record<string, string[]>>;
  parent_order: string[];
}

export interface TimeSeriesPoint {
  year: string;
  Growth?: number;
  Financing?: number;
  "Working Capital"?: number;
  Others?: number;
}

export interface IndustryData {
  [industry: string]: {
    companies: number;
    parents: Record<string, number>;
  };
}

export interface GeoData {
  [geo: string]: {
    total_hkd_million: number;
    companies: number;
    /** Parent-category breakdown per geo region */
    parents: Record<string, number>;
  };
}

export interface CrossDimRow {
  hk_ticker: string;
  industry: string | null;
  listing_date: string | null;
  total_net_proceeds: number | null;
  use_id: string;
  parent_category: string;
  percentage: number;
  amount_hkd_million: number;
  /** Comma-separated ISO 2-letter country codes (from L5 country enrichment) */
  countries: string | null;
  /** Geographic scope: domestic_hk | mainland | overseas */
  geo: string | null;
  /** Commitment: committed | discretionary */
  commitment: string | null;
  /** Specificity: specific | general | vague */
  specificity: string | null;
  /** Deployment timeline: 0-12m | 12-24m | 24-36m | 36m+ | unspecified */
  timeline: string | null;
  /** Capital vs operating expenditure: capex | opex | financial */
  capex_opex: string | null;
  /** ESG tag: green | social | governance | null if absent */
  esg_tag: string | null;
}

export interface Manifest {
  generated_at: string;
  schema_version: string;
  company_count: number;
  taxonomy_sha: string;
}
```

- [ ] **Step 2: Create `frontend/src/lib/dataClient.ts`**

```typescript
import type {
  CompaniesData, SankeyData, TaxonomyData, TimeSeriesPoint,
  IndustryData, GeoData, CrossDimRow, Manifest,
} from './sharedTypes';

const BASE = './data';

const cache = new Map<string, unknown>();

async function fetchJSON<T>(filename: string): Promise<T> {
  if (cache.has(filename)) {
    return cache.get(filename) as T;
  }
  const resp = await fetch(`${BASE}/${filename}`);
  if (!resp.ok) throw new Error(`Failed to fetch ${filename}: ${resp.status}`);
  const data = (await resp.json()) as T;
  cache.set(filename, data);
  return data;
}

export async function fetchManifest(): Promise<Manifest> {
  return fetchJSON<Manifest>('manifest.json');
}

export async function fetchCompanies(): Promise<CompaniesData> {
  return fetchJSON<CompaniesData>('companies.json');
}

export async function fetchTaxonomy(): Promise<TaxonomyData> {
  return fetchJSON<TaxonomyData>('taxonomy.json');
}

export async function fetchTimeSeries(): Promise<TimeSeriesPoint[]> {
  return fetchJSON<TimeSeriesPoint[]>('time_series.json');
}

export async function fetchByIndustry(): Promise<IndustryData> {
  return fetchJSON<IndustryData>('by_industry.json');
}

export async function fetchByGeo(): Promise<GeoData> {
  return fetchJSON<GeoData>('by_geo.json');
}

export async function fetchCrossDim(): Promise<CrossDimRow[]> {
  return fetchJSON<CrossDimRow[]>('cross_dim.json');
}

export async function fetchSankey(ticker: string): Promise<SankeyData> {
  return fetchJSON<SankeyData>(`sankey/${ticker}.json`);
}

export function clearCache(): void {
  cache.clear();
}
```

- [ ] **Step 3: Create `frontend/src/lib/store.ts`**

```typescript
import { create } from 'zustand';

export interface FilterState {
  year: string | null;
  industry: string | null;
  country: string | null;
  parent: string | null;
  commitment: string | null;
}

export interface AppState extends FilterState {
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  resetFilters: () => void;
  activeTicker: string | null;
  setActiveTicker: (ticker: string | null) => void;
}

const initialFilters: FilterState = {
  year: null,
  industry: null,
  country: null,
  parent: null,
  commitment: null,
};

export const useStore = create<AppState>((set) => ({
  ...initialFilters,
  setFilter: (key, value) => set({ [key]: value }),
  resetFilters: () => set(initialFilters),
  activeTicker: null,
  setActiveTicker: (ticker) => set({ activeTicker: ticker }),
}));
```

- [ ] **Step 4: Create `frontend/src/lib/filterUtils.ts`**

This module provides client-side filtering of per-use `CrossDimRow[]` data against the global Zustand filter state. It also includes helper functions to re-aggregate filtered data into view-specific shapes (time series, by-industry, by-geo) so that each view can derive its chart data from a single filtered source.

```typescript
import type { FilterState } from './store';
import type { CrossDimRow, TimeSeriesPoint, IndustryData, GeoData } from './sharedTypes';

/**
 * Filter per-use rows by the global filter state.
 * Each non-null filter dimension must match; rows failing any filter are excluded.
 */
export function filterCrossDim(rows: CrossDimRow[], filters: FilterState): CrossDimRow[] {
  return rows.filter((row) => {
    if (filters.year) {
      const rowYear = row.listing_date?.slice(0, 4);
      if (rowYear !== filters.year) return false;
    }
    if (filters.industry && row.industry !== filters.industry) return false;
    if (filters.parent && row.parent_category !== filters.parent) return false;
    if (filters.country) {
      if (!row.countries || !row.countries.split(',').includes(filters.country)) return false;
    }
    if (filters.commitment && row.commitment !== filters.commitment) return false;
    return true;
  });
}

/**
 * Aggregate filtered CrossDimRow[] into time-series points (year -> parent %).
 */
export function aggregateTimeSeries(rows: CrossDimRow[]): TimeSeriesPoint[] {
  const byYear: Record<string, Record<string, number>> = {};
  for (const r of rows) {
    const year = (r.listing_date ?? '').slice(0, 4);
    if (!year) continue;
    if (!byYear[year]) byYear[year] = {};
    byYear[year][r.parent_category] =
      (byYear[year][r.parent_category] ?? 0) + (r.percentage ?? 0);
  }
  return Object.entries(byYear)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([year, parents]) => ({ year, ...parents }));
}

/**
 * Aggregate filtered CrossDimRow[] into by-industry data (industry -> parent %).
 */
export function aggregateByIndustry(rows: CrossDimRow[]): IndustryData {
  const result: IndustryData = {};
  const industries = new Set<string>();
  for (const r of rows) {
    const ind = r.industry ?? 'Unknown';
    industries.add(ind);
    if (!result[ind]) result[ind] = { companies: 0, parents: {} };
    result[ind].parents[r.parent_category] =
      (result[ind].parents[r.parent_category] ?? 0) + (r.percentage ?? 0);
  }
  // Count distinct tickers per industry
  const tickersByIndustry = new Map<string, Set<string>>();
  for (const r of rows) {
    const ind = r.industry ?? 'Unknown';
    if (!tickersByIndustry.has(ind)) tickersByIndustry.set(ind, new Set());
    tickersByIndustry.get(ind)!.add(r.hk_ticker);
  }
  for (const [ind, tickers] of tickersByIndustry) {
    if (result[ind]) result[ind].companies = tickers.size;
  }
  return result;
}

/**
 * Aggregate filtered CrossDimRow[] into by-geo data with parent breakdown.
 * Each geo region includes total_hkd_million, company count, and
 * parent-category allocation percentages so the GeographicView can render
 * a parent-breakdown stacked bar per region.
 */
export function aggregateByGeo(rows: CrossDimRow[]): GeoData {
  const result: GeoData = {};
  const tickersByGeo = new Map<string, Set<string>>();
  for (const r of rows) {
    const geo = r.geo ?? 'unspecified';
    if (!result[geo]) {
      result[geo] = { total_hkd_million: 0, companies: 0, parents: {} };
    }
    result[geo].total_hkd_million += (r.amount_hkd_million ?? 0);
    result[geo].parents[r.parent_category] =
      (result[geo].parents[r.parent_category] ?? 0) + (r.percentage ?? 0);
    if (!tickersByGeo.has(geo)) tickersByGeo.set(geo, new Set());
    tickersByGeo.get(geo)!.add(r.hk_ticker);
  }
  for (const [geo, tickers] of tickersByGeo) {
    if (result[geo]) result[geo].companies = tickers.size;
  }
  return result;
}
```

- [ ] **Step 5: Update `frontend/src/App.tsx` to wire in the store**

Replace with:

```tsx
import { useState } from 'react';
import { useStore } from './lib/store';

const VIEWS = [
  { key: 'overview', label: 'Overview' },
  { key: 'company', label: 'Company' },
  { key: 'temporal', label: 'Temporal' },
  { key: 'industry', label: 'Industry' },
  { key: 'geo', label: 'Geographic' },
  { key: 'cross', label: 'Cross-Dim' },
] as const;

type ViewKey = (typeof VIEWS)[number]['key'];

function App() {
  const [view, setView] = useState<ViewKey>('overview');
  const activeTicker = useStore((s) => s.activeTicker);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1400, margin: '0 auto', padding: 16 }}>
      <h1>HK IPO Use-of-Proceeds Dashboard</h1>
      {activeTicker && (
        <p style={{ color: '#666', margin: 0 }}>
          Active company: <strong>{activeTicker}</strong>
        </p>
      )}
      <nav style={{ display: 'flex', gap: 4, marginBottom: 24, marginTop: 8 }}>
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            style={{
              padding: '8px 16px',
              background: view === v.key ? '#1a73e8' : '#f0f0f0',
              color: view === v.key ? '#fff' : '#333',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontWeight: view === v.key ? 600 : 400,
            }}
          >
            {v.label}
          </button>
        ))}
      </nav>
      <main>
        <p>Selected view: {view}</p>
        <p>Store connected; filters: {JSON.stringify(useStore.getState())}</p>
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 6: Verify build succeeds**

Run:
```bash
cd frontend
npm run build
```

Expected: No TypeScript errors. Build produces `dist/`.
