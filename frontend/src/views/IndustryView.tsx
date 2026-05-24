import { useMemo, useRef } from 'react';
import type { EChartsType } from 'echarts';
import { filterCrossDim, aggregateByIndustry } from '../lib/filterUtils';
import { HeatmapChart } from '../components/charts/HeatmapChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { useStore } from '../lib/store';
import { useDashboardData } from '../lib/useDashboardData';
import { SkeletonChart } from '../components/SkeletonChart';

export function IndustryView() {
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();
  const { allCrossDim, options, loading, error } = useDashboardData();

  const chartData = useMemo(() => {
    const filtered = filterCrossDim(allCrossDim, filters);
    return aggregateByIndustry(filtered);
  }, [allCrossDim, filters]);

  if (loading) return <SkeletonChart />;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Industry x Parent Allocation Heatmap</h3>
        <ExportButton chartRef={chartRef} chartLabel="industry_heatmap"
          csvData={{ headers: ['Industry', 'Growth (HK$M)', 'Financing (HK$M)', 'Working Capital (HK$M)', 'Others (HK$M)'],
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
