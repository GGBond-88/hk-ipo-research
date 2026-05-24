import { useMemo, useRef } from 'react';
import type { EChartsType } from 'echarts';
import { filterCrossDim, aggregateByGeo } from '../lib/filterUtils';
import { StackedBarChart } from '../components/charts/StackedBarChart';
import { FilterBar } from '../components/FilterBar';
import { ExportButton } from '../components/ExportButton';
import { useStore } from '../lib/store';
import { useDashboardData } from '../lib/useDashboardData';
import { SkeletonChart } from '../components/SkeletonChart';
import type { GeoData } from '../lib/sharedTypes';

export function GeographicView() {
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();
  const { allCrossDim, options, loading, error } = useDashboardData();

  const chartData: GeoData = useMemo(() => {
    const filtered = filterCrossDim(allCrossDim, filters);
    return aggregateByGeo(filtered);
  }, [allCrossDim, filters]);

  // Convert GeoData to the Record<string, Record<string, number>> shape StackedBarChart expects
  const geoDataForChart = useMemo(() => {
    const result: Record<string, Record<string, number>> = {};
    Object.entries(chartData).forEach(([key, val]) => {
      result[key] = val.parents;
    });
    return result;
  }, [chartData]);

  if (loading) return <SkeletonChart />;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

  return (
    <div>
      <FilterBar options={options} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Parent Breakdown by Region</h3>
        <ExportButton chartRef={chartRef} chartLabel="geographic_parent_breakdown"
          csvData={{ headers: ['Region', 'Growth (HK$M)', 'Financing (HK$M)', 'Working Capital (HK$M)', 'Others (HK$M)'],
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
