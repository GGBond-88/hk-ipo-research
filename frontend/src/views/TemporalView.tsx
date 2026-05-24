import { useMemo, useRef } from 'react';
import type { EChartsType } from 'echarts';
import { filterCrossDim, aggregateTimeSeries } from '../lib/filterUtils';
import { TimeSeriesChart } from '../components/charts/TimeSeriesChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { useStore } from '../lib/store';
import { useDashboardData } from '../lib/useDashboardData';
import { SkeletonChart } from '../components/SkeletonChart';

export function TemporalView() {
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();
  const { allCrossDim, options, loading, error } = useDashboardData();

  // Filter and aggregate client-side when filters change
  const tsData = useMemo(() => {
    const filtered = filterCrossDim(allCrossDim, filters);
    return aggregateTimeSeries(filtered);
  }, [allCrossDim, filters]);

  if (loading) return <SkeletonChart />;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Parent Allocation Over Time</h3>
        <ExportButton chartRef={chartRef} chartLabel="temporal"
          csvData={{ headers: ['Year', 'Growth (HK$M)', 'Financing (HK$M)', 'Working Capital (HK$M)', 'Others (HK$M)'],
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
