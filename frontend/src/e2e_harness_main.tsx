import React, { forwardRef } from 'react';
import ReactDOM from 'react-dom/client';
import type { EChartsType } from 'echarts';
import { FilterBar } from './components/FilterBar';
import { ExportButton } from './components/ExportButton';
import { useStore } from './lib/store';
import type { FilterOptions } from './lib/filterOptions';

// ---------------------------------------------------------------------------
// Mock ECharts component that forwards a ref with a mock getDataURL method.
// This lets us black-box test ExportButton's PNG download path.
// ---------------------------------------------------------------------------

function createMockEChartsInstance(): EChartsType {
  return {
    getDataURL: (opts: { type?: string; pixelRatio?: number; backgroundColor?: string }) =>
      `data:${opts.type ?? 'png'};base64,mockDataURL`,
  } as unknown as EChartsType;
}

const MockChart = forwardRef<EChartsType | null, { style?: React.CSSProperties }>(
  (_props, ref) => {
    const instanceRef = React.useRef<EChartsType | null>(null);
    if (!instanceRef.current) {
      instanceRef.current = createMockEChartsInstance();
    }
    React.useImperativeHandle(ref, () => instanceRef.current!);
    return React.createElement('div', {
      'data-testid': 'mock-chart',
      style: { width: 400, height: 300, background: '#f0f0f0', border: '1px dashed #999', ..._props.style },
    }, 'MockChart');
  },
);
MockChart.displayName = 'MockChart';

// ---------------------------------------------------------------------------
// Demo filter options
// ---------------------------------------------------------------------------

const DEMO_OPTIONS: FilterOptions = {
  years: ['2023', '2024', '2025'],
  industries: ['Finance', 'Healthcare', 'Technology'],
  countries: ['CN', 'HK', 'JP', 'US'],
  parents: ['Growth', 'Financing', 'Working Capital', 'Others'],
  commitments: ['committed', 'discretionary'],
};

const DEMO_TICKERS = [
  { hk_ticker: '00001', company_name_en: 'Alpha Corp' },
  { hk_ticker: '00002', company_name_en: 'Beta Ltd' },
  { hk_ticker: '00003', company_name_en: 'Gamma Industries' },
];

const DEMO_CSV_DATA = {
  headers: ['Name', 'Value', 'Date'],
  rows: [
    ['Alice', '100', '2024-01-15'],
    ['Bob', '200', '2024-02-20'],
    ['Charlie', '300', '2024-03-25'],
  ],
};

// ---------------------------------------------------------------------------
// Store state display (visible in DOM so Playwright can inspect filter state)
// ---------------------------------------------------------------------------

function StoreStateDisplay() {
  const state = useStore();
  return React.createElement('pre', {
    'data-testid': 'store-state',
    style: {
      marginTop: 16, padding: 12, background: '#fafafa',
      border: '1px solid #ddd', borderRadius: 4, fontSize: 12,
      whiteSpace: 'pre-wrap', maxWidth: 600,
    },
  }, JSON.stringify(state, null, 2));
}

// ---------------------------------------------------------------------------
// App root
// ---------------------------------------------------------------------------

function App() {
  const chartRef = React.useRef<EChartsType | null>(null);

  return React.createElement('div', {
    style: { fontFamily: 'system-ui, sans-serif', maxWidth: 900, margin: '0 auto', padding: 16 },
  },
    React.createElement('h1', null, 'E2E Test Harness'),
    React.createElement('p', null, 'FilterBar + ExportButton black-box test page.'),

    // ── FilterBar with ticker picker ──────────────────────────────────
    React.createElement('h2', null, 'FilterBar (with ticker picker)'),
    React.createElement(FilterBar, {
      options: DEMO_OPTIONS,
      showTickerPicker: true,
      tickers: DEMO_TICKERS,
    }),

    // ── FilterBar without ticker picker ───────────────────────────────
    React.createElement('h2', null, 'FilterBar (no ticker picker)'),
    React.createElement(FilterBar, {
      options: DEMO_OPTIONS,
    }),

    // ── ExportButton with mock chart ref ──────────────────────────────
    React.createElement('h2', null, 'ExportButton (PNG + CSV)'),
    React.createElement(MockChart, { ref: chartRef }),
    React.createElement(ExportButton, {
      chartRef,
      chartLabel: 'Test Chart With/Data',
      csvData: DEMO_CSV_DATA,
    }),

    // ── ExportButton without CSV data ─────────────────────────────────
    React.createElement('h2', null, 'ExportButton (PNG only)'),
    React.createElement(ExportButton, {
      chartRef: { current: null },
      chartLabel: 'PNG-Only Chart',
    }),

    // ── Store state ───────────────────────────────────────────────────
    React.createElement('h2', null, 'Zustand Store State'),
    React.createElement(StoreStateDisplay),
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  React.createElement(React.StrictMode, null, React.createElement(App)),
);
