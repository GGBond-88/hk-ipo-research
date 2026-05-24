# Task 025: Frontend views (Overview, Company, Temporal, Industry, Geographic, CrossDim)

## Project Overview

- **Goal:** React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** Six views, each reads pre-baked JSON via dataClient, applies Zustand filter state, renders one or two chart components.
- **Tech Stack:** React + TypeScript + ECharts + Zustand.

## Task Objective

Implement all 6 view components. Each is a self-contained page that fetches data on mount, applies global filters, and renders charts with export buttons. Wire them into App.tsx.

This is Task 25 of 27.

---

**Files:**
- Create: `frontend/src/views/OverviewView.tsx`
- Create: `frontend/src/views/CompanyView.tsx`
- Create: `frontend/src/views/TemporalView.tsx`
- Create: `frontend/src/views/IndustryView.tsx`
- Create: `frontend/src/views/GeographicView.tsx`
- Create: `frontend/src/views/CrossDimView.tsx`
- Modify: `frontend/src/App.tsx` (wire in all views)

- [ ] **Step 1: Create `frontend/src/views/OverviewView.tsx`**

The Overview view filters companies and per-use data by the global filter state. The chart is derived from filtered `cross_dim.json` (re-aggregated by industry+parent), so changing year/industry/country filters updates the stacked bar chart.

```tsx
import { useEffect, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCompanies, fetchCrossDim } from '../lib/dataClient';
import { useStore } from '../lib/store';
import { filterCrossDim, aggregateByIndustry } from '../lib/filterUtils';
import { StackedBarChart } from '../components/charts/StackedBarChart';
import { ExportButton } from '../components/ExportButton';
import type { CompaniesData, CrossDimRow, IndustryData } from '../lib/sharedTypes';

export function OverviewView() {
  const [companies, setCompanies] = useState<CompaniesData | null>(null);
  const [allCrossDim, setAllCrossDim] = useState<CrossDimRow[]>([]);
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();

  useEffect(() => {
    Promise.all([fetchCompanies(), fetchCrossDim()])
      .then(([c, cd]) => { setCompanies(c); setAllCrossDim(cd); })
      .catch(console.error);
  }, []);

  if (!companies) return <p>Loading...</p>;

  // Filter companies for KPI tiles
  const filteredCompanies = companies.companies.filter((c) => {
    if (filters.year && c.listing_date?.slice(0, 4) !== filters.year) return false;
    if (filters.industry && c.industry_primary !== filters.industry) return false;
    return true;
  });

  // Filter cross_dim for the chart (apply full filter state including country)
  const filteredCross = filterCrossDim(allCrossDim, filters);
  const chartData: IndustryData = aggregateByIndustry(filteredCross);

  const totalRaised = filteredCompanies.reduce((s, c) => s + (c.total_net_proceeds ?? 0), 0);
  const needsReview = filteredCompanies.filter((c) => c.needs_human_review).length;

  return (
    <div>
      <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
        <KpiTile label="Companies" value={filteredCompanies.length} />
        <KpiTile label="Total Raised (HK$M)" value={totalRaised.toLocaleString()} />
        <KpiTile label="Needs Review" value={needsReview}
          highlight={needsReview > 0} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Parent Allocation by Industry</h3>
        <ExportButton chartRef={chartRef} chartLabel="overview_stacked_bar"
          csvData={{ headers: ['Industry', 'Growth %', 'Financing %', 'Working Capital %', 'Others %'],
                     rows: Object.entries(chartData).map(([ind, v]) =>
                       [ind,
                        String(v.parents['Growth'] ?? 0),
                        String(v.parents['Financing'] ?? 0),
                        String(v.parents['Working Capital'] ?? 0),
                        String(v.parents['Others'] ?? 0)]) }} />
      </div>
      <StackedBarChart ref={chartRef} data={chartData} xLabel="Industry" />
    </div>
  );
}

function KpiTile({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div style={{
      flex: 1, padding: 16, borderRadius: 8, textAlign: 'center',
      background: highlight ? '#fff3e0' : '#f5f5f5',
      border: highlight ? '2px solid #ff9800' : '1px solid #e0e0e0',
    }}>
      <div style={{ fontSize: 13, color: '#666' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/views/CompanyView.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCompanies, fetchSankey } from '../lib/dataClient';
import { useStore } from '../lib/store';
import { FilterBar } from '../components/FilterBar';
import { SankeyChart } from '../components/charts/SankeyChart';
import { ExportButton } from '../components/ExportButton';
import type { CompaniesData, SankeyData } from '../lib/sharedTypes';

export function CompanyView() {
  const [companies, setCompanies] = useState<CompaniesData | null>(null);
  const [sankey, setSankey] = useState<SankeyData | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const activeTicker = useStore((s) => s.activeTicker);
  const setActiveTicker = useStore((s) => s.setActiveTicker);

  useEffect(() => {
    fetchCompanies().then(setCompanies).catch(console.error);
  }, []);

  useEffect(() => {
    if (activeTicker) {
      fetchSankey(activeTicker).then(setSankey).catch(console.error);
    } else {
      setSankey(null);
    }
  }, [activeTicker]);

  const tickerList = companies?.companies?.map((c) => ({
    hk_ticker: c.hk_ticker,
    company_name_en: c.company_name_en,
  })) ?? [];

  const activeCompany = companies?.companies?.find((c) => c.hk_ticker === activeTicker);

  return (
    <div>
      <FilterBar
        showTickerPicker
        tickers={tickerList}
        options={{ years: [], industries: [], countries: [], parents: [], commitments: [] }}
      />
      {activeCompany?.needs_human_review && (
        <div style={{ padding: '8px 16px', background: '#fff3e0', borderRadius: 4, marginBottom: 12 }}>
          Needs Human Review
        </div>
      )}
      {sankey ? (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>
              {activeTicker} - {activeCompany?.company_name_en}
              {" "}(Total: HK${sankey.total_net_proceeds}M)
            </h3>
            <ExportButton chartRef={chartRef} chartLabel={`sankey_${activeTicker}`} />
          </div>
          <SankeyChart ref={chartRef} data={sankey} />
        </>
      ) : (
        <p>{activeTicker ? 'Loading Sankey...' : 'Select a company above to view its Sankey diagram.'}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/views/TemporalView.tsx`**

The Temporal view derives its time-series chart data from `cross_dim.json` so that industry and country filter changes update the chart. It filters the per-use data client-side and re-aggregates by year+parent.

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCompanies, fetchCrossDim, fetchByGeo } from '../lib/dataClient';
import { filterCrossDim, aggregateTimeSeries } from '../lib/filterUtils';
import { TimeSeriesChart } from '../components/charts/TimeSeriesChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { deriveFilterOptions } from '../lib/filterOptions';
import { useStore } from '../lib/store';
import type { CrossDimRow, CompaniesData, GeoData } from '../lib/sharedTypes';

export function TemporalView() {
  const [allCrossDim, setAllCrossDim] = useState<CrossDimRow[]>([]);
  const [options, setOptions] = useState({ years: [] as string[], industries: [] as string[], countries: [] as string[], parents: [] as string[], commitments: [] as string[] });
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();

  useEffect(() => {
    Promise.all([fetchCrossDim(), fetchCompanies(), fetchByGeo()])
      .then(([cd, c, geo]) => {
        setAllCrossDim(cd);
        // Derive filter options from the full unfiltered dataset
        // Use a minimal IndustryData derived from cross_dim for options
        const industries = [...new Set(cd.map((r) => r.industry).filter(Boolean))] as string[];
        setOptions(deriveFilterOptions(
          c,
          cd,
          Object.fromEntries(industries.map((i) => [i, { companies: 0, parents: {} }])),
          geo,
        ));
      }).catch(console.error);
  }, []);

  // Filter and aggregate client-side when filters change
  const tsData = useMemo(() => {
    const filtered = filterCrossDim(allCrossDim, filters);
    return aggregateTimeSeries(filtered);
  }, [allCrossDim, filters]);

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Parent Allocation Over Time</h3>
        <ExportButton chartRef={chartRef} chartLabel="temporal"
          csvData={{ headers: ['Year', 'Growth %', 'Financing %', 'Working Capital %', 'Others %'],
                     rows: tsData.map((p) =>
                       [p.year,
                        String(p.Growth ?? 0),
                        String(p.Financing ?? 0),
                        String(p['Working Capital'] ?? 0),
                        String(p.Others ?? 0)]) }} />
      </div>
      <TimeSeriesChart ref={chartRef} data={tsData} />
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/views/IndustryView.tsx`**

The Industry view filters `cross_dim.json` by year and country, then re-aggregates by industry+parent. Changing year/country filters updates the heatmap.

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCrossDim, fetchCompanies, fetchByGeo } from '../lib/dataClient';
import { filterCrossDim, aggregateByIndustry } from '../lib/filterUtils';
import { HeatmapChart } from '../components/charts/HeatmapChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { deriveFilterOptions } from '../lib/filterOptions';
import { useStore } from '../lib/store';
import type { CrossDimRow, CompaniesData, GeoData } from '../lib/sharedTypes';

export function IndustryView() {
  const [allCrossDim, setAllCrossDim] = useState<CrossDimRow[]>([]);
  const [options, setOptions] = useState({ years: [] as string[], industries: [] as string[], countries: [] as string[], parents: [] as string[], commitments: [] as string[] });
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();

  useEffect(() => {
    Promise.all([fetchCrossDim(), fetchCompanies(), fetchByGeo()])
      .then(([cd, c, geo]) => {
        setAllCrossDim(cd);
        const industries = [...new Set(cd.map((r) => r.industry).filter(Boolean))] as string[];
        setOptions(deriveFilterOptions(
          c, cd,
          Object.fromEntries(industries.map((i) => [i, { companies: 0, parents: {} }])),
          geo,
        ));
      }).catch(console.error);
  }, []);

  const chartData = useMemo(() => {
    const filtered = filterCrossDim(allCrossDim, filters);
    return aggregateByIndustry(filtered);
  }, [allCrossDim, filters]);

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Industry x Parent Allocation Heatmap</h3>
        <ExportButton chartRef={chartRef} chartLabel="industry_heatmap"
          csvData={{ headers: ['Industry', 'Growth %', 'Financing %', 'Working Capital %', 'Others %'],
                     rows: Object.entries(chartData).map(([ind, v]) =>
                       [ind,
                        String(v.parents['Growth'] ?? 0),
                        String(v.parents['Financing'] ?? 0),
                        String(v.parents['Working Capital'] ?? 0),
                        String(v.parents['Others'] ?? 0)]) }} />
      </div>
      <HeatmapChart ref={chartRef} data={chartData} />
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/src/views/GeographicView.tsx`**

The Geographic view filters `cross_dim.json` by year and industry, then re-aggregates by geo dimension. Changing year/industry filters updates the bar chart.

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCrossDim, fetchCompanies, fetchByGeo } from '../lib/dataClient';
import { filterCrossDim, aggregateByGeo } from '../lib/filterUtils';
import { StackedBarChart } from '../components/charts/StackedBarChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { deriveFilterOptions } from '../lib/filterOptions';
import { useStore } from '../lib/store';
import type { CrossDimRow, CompaniesData, GeoData } from '../lib/sharedTypes';

export function GeographicView() {
  const [allCrossDim, setAllCrossDim] = useState<CrossDimRow[]>([]);
  const [options, setOptions] = useState({ years: [] as string[], industries: [] as string[], countries: [] as string[], parents: [] as string[], commitments: [] as string[] });
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();

  useEffect(() => {
    Promise.all([fetchCrossDim(), fetchCompanies(), fetchByGeo()])
      .then(([cd, c, geo]) => {
        setAllCrossDim(cd);
        const industries = [...new Set(cd.map((r) => r.industry).filter(Boolean))] as string[];
        setOptions(deriveFilterOptions(
          c, cd,
          Object.fromEntries(industries.map((i) => [i, { companies: 0, parents: {} }])),
          geo,
        ));
      }).catch(console.error);
  }, []);

  const chartData: GeoData = useMemo(() => {
    const filtered = filterCrossDim(allCrossDim, filters);
    return aggregateByGeo(filtered);
  }, [allCrossDim, filters]);

  // Convert GeoData to the { name: { parents: {...} } } shape StackedBarChart expects
  const geoDataForChart: Record<string, { parents: Record<string, number> }> = {};
  Object.entries(chartData).forEach(([key, val]) => {
    geoDataForChart[key] = { parents: val.parents };
  });

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Parent Breakdown by Region</h3>
        <ExportButton chartRef={chartRef} chartLabel="geographic_parent_breakdown"
          csvData={{ headers: ['Region', 'Growth %', 'Financing %', 'Working Capital %', 'Others %'],
                     rows: Object.entries(chartData).map(([k, v]) =>
                       [k,
                        String(v.parents['Growth'] ?? 0),
                        String(v.parents['Financing'] ?? 0),
                        String(v.parents['Working Capital'] ?? 0),
                        String(v.parents['Others'] ?? 0)]) }} />
      </div>
      <StackedBarChart ref={chartRef} data={geoDataForChart} xLabel="Region" />
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend/src/views/CrossDimView.tsx`**

The Cross-Dim view filters `cross_dim.json` by the global filter state (year, industry, country, parent, commitment) before rendering the scatter plot. Changing any filter updates the scatter.

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCrossDim, fetchCompanies, fetchByGeo } from '../lib/dataClient';
import { filterCrossDim } from '../lib/filterUtils';
import { ScatterChart } from '../components/charts/ScatterChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { deriveFilterOptions } from '../lib/filterOptions';
import { useStore } from '../lib/store';
import type { CrossDimRow } from '../lib/sharedTypes';

const NUMERIC_KEYS: (keyof CrossDimRow)[] = ['percentage', 'amount_hkd_million', 'total_net_proceeds'];

/** Enrichment tags that can serve as categorical axes or color dimensions. */
const ENRICHMENT_TAG_KEYS: (keyof CrossDimRow)[] = [
  'parent_category', 'geo', 'specificity', 'timeline', 'capex_opex', 'commitment', 'esg_tag'
];

const ALL_AXIS_KEYS = [...NUMERIC_KEYS, ...ENRICHMENT_TAG_KEYS];

export function CrossDimView() {
  const [allData, setAllData] = useState<CrossDimRow[]>([]);
  const [options, setOptions] = useState({ years: [] as string[], industries: [] as string[], countries: [] as string[], parents: [] as string[], commitments: [] as string[] });
  const [xKey, setXKey] = useState<keyof CrossDimRow>('percentage');
  const [yKey, setYKey] = useState<keyof CrossDimRow>('amount_hkd_million');
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();

  useEffect(() => {
    Promise.all([fetchCrossDim(), fetchCompanies(), fetchByGeo()])
      .then(([cd, c, geo]) => {
        setAllData(cd);
        const industries = [...new Set(cd.map((r) => r.industry).filter(Boolean))] as string[];
        setOptions(deriveFilterOptions(
          c, cd,
          Object.fromEntries(industries.map((i) => [i, { companies: 0, parents: {} }])),
          geo,
        ));
      }).catch(console.error);
  }, []);

  const filteredData = useMemo(() => {
    return filterCrossDim(allData, filters);
  }, [allData, filters]);

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
        <label style={{ fontSize: 14 }}>
          X:{" "}
          <select value={xKey} onChange={(e) => setXKey(e.target.value as keyof CrossDimRow)}
            style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}>
            {ALL_AXIS_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 14 }}>
          Y:{" "}
          <select value={yKey} onChange={(e) => setYKey(e.target.value as keyof CrossDimRow)}
            style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}>
            {ALL_AXIS_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </label>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>{xKey} vs {yKey}</h3>
        <ExportButton chartRef={chartRef} chartLabel={`scatter_${xKey}_vs_${yKey}`}
          csvData={{ headers: ['Ticker', String(xKey), String(yKey)],
                     rows: filteredData.map((r) => [r.hk_ticker, String(r[xKey] ?? 0), String(r[yKey] ?? 0)]) }} />
      </div>
      <ScatterChart ref={chartRef} data={filteredData} xKey={xKey} yKey={yKey} />
    </div>
  );
}
```

- [ ] **Step 7: Update `App.tsx` to wire in all views**

Replace the `App.tsx` placeholder content:

```tsx
import { useState } from 'react';
import { useStore } from './lib/store';
import { OverviewView } from './views/OverviewView';
import { CompanyView } from './views/CompanyView';
import { TemporalView } from './views/TemporalView';
import { IndustryView } from './views/IndustryView';
import { GeographicView } from './views/GeographicView';
import { CrossDimView } from './views/CrossDimView';

const VIEWS = [
  { key: 'overview', label: 'Overview', component: OverviewView },
  { key: 'company', label: 'Company', component: CompanyView },
  { key: 'temporal', label: 'Temporal', component: TemporalView },
  { key: 'industry', label: 'Industry', component: IndustryView },
  { key: 'geo', label: 'Geographic', component: GeographicView },
  { key: 'cross', label: 'Cross-Dim', component: CrossDimView },
] as const;

type ViewKey = (typeof VIEWS)[number]['key'];

function App() {
  const [view, setView] = useState<ViewKey>('overview');
  const activeTicker = useStore((s) => s.activeTicker);
  const ActiveComponent = VIEWS.find((v) => v.key === view)!.component;

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1400, margin: '0 auto', padding: 16 }}>
      <h1 style={{ marginBottom: 4 }}>HK IPO Use-of-Proceeds Dashboard</h1>
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
        <ActiveComponent />
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 8: Verify build**

Run:
```bash
cd frontend
npm run build
```

Expected: No TypeScript errors. Build succeeds.
