import { useMemo, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { filterCrossDim } from '../lib/filterUtils';
import { ScatterChart } from '../components/charts/ScatterChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { useStore } from '../lib/store';
import { useDashboardData } from '../lib/useDashboardData';
import { SkeletonChart } from '../components/SkeletonChart';
import { csvValueForCrossDim } from '../lib/crossDimCsvUtils';
import type { CrossDimRow } from '../lib/sharedTypes';

const NUMERIC_KEYS: (keyof CrossDimRow)[] = ['percentage', 'amount_hkd_million', 'total_net_proceeds'];

/** Enrichment tags that can serve as categorical axes or color dimensions. */
const ENRICHMENT_TAG_KEYS: (keyof CrossDimRow)[] = [
  'parent_category', 'geo', 'specificity', 'timeline', 'capex_opex', 'commitment', 'esg_tag'
];

const ALL_AXIS_KEYS = [...NUMERIC_KEYS, ...ENRICHMENT_TAG_KEYS];

export function CrossDimView() {
  const [xKey, setXKey] = useState<keyof CrossDimRow>('percentage');
  const [yKey, setYKey] = useState<keyof CrossDimRow>('amount_hkd_million');
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();
  const { allCrossDim: allData, options, loading, error } = useDashboardData();

  const filteredData = useMemo(() => {
    return filterCrossDim(allData, filters);
  }, [allData, filters]);

  if (loading) return <SkeletonChart />;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

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
                     rows: filteredData.map((r) => [r.hk_ticker, csvValueForCrossDim(xKey, r[xKey]), csvValueForCrossDim(yKey, r[yKey])]) }} />
      </div>
      <ScatterChart ref={chartRef} data={filteredData} xKey={xKey} yKey={yKey} />
    </div>
  );
}
