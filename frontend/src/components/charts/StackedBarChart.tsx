import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { IndustryData } from '../../lib/sharedTypes';
import { PARENTS } from '../../lib/chartConstants';

interface Props {
  data: IndustryData | Record<string, Record<string, number>>;
  xLabel?: string;
}

/** Type guard: narrows union to the IndustryData branch (value with .parents). */
function hasParents(
  v: { companies: number; parents: Record<string, number> } | Record<string, number>,
): v is { companies: number; parents: Record<string, number> } {
  return 'parents' in v && v.parents != null && typeof v.parents === 'object';
}

export const StackedBarChart = forwardRef<EChartsType | null, Props>(({ data, xLabel }, ref) => {
  const [chartInstance, setChartInstance] = useState<EChartsType | null>(null);

  useImperativeHandle<EChartsType | null, EChartsType | null>(ref, () => chartInstance, [chartInstance]);

  const option = useMemo(() => {
    const entries = Object.entries(data);

    return {
      tooltip: { trigger: 'axis' as const },
      legend: { bottom: 0, data: [...PARENTS] },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        data: entries.map(([k]) => k),
        name: xLabel ?? '',
        axisLabel: { rotate: 30, fontSize: 10 },
      },
      yAxis: { type: 'value' as const, name: 'HKD Million' },
      series: PARENTS.map((p) => ({
        name: p,
        type: 'bar' as const,
        stack: 'total',
        data: entries.map(([, v]) => {
          const parentsData = hasParents(v) ? v.parents : v;
          return parentsData[p] ?? 0;
        }),
      })),
    };
  }, [data, xLabel]);

  return (
    <ReactEChartsCore
      option={option}
      style={{ height: 400, width: '100%' }}
      onChartReady={(instance) => setChartInstance(instance)}
      notMerge
    />
  );
});

StackedBarChart.displayName = 'StackedBarChart';
