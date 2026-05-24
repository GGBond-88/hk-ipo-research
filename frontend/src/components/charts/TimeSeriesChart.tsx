import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { TimeSeriesPoint } from '../../lib/sharedTypes';
import { PARENTS } from '../../lib/chartConstants';

interface Props {
  data: TimeSeriesPoint[];
}

export const TimeSeriesChart = forwardRef<EChartsType | null, Props>(({ data }, ref) => {
  const [chartInstance, setChartInstance] = useState<EChartsType | null>(null);

  useImperativeHandle<EChartsType | null, EChartsType | null>(ref, () => chartInstance, [chartInstance]);

  const option = useMemo(() => {
    return {
      tooltip: { trigger: 'axis' as const },
      legend: { bottom: 0, data: [...PARENTS] },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        data: data.map((d) => d.year),
      },
      yAxis: { type: 'value' as const, name: 'HKD Million' },
      series: PARENTS.map((p) => ({
        name: p,
        type: 'line' as const,
        stack: 'total',
        areaStyle: {},
        data: data.map((d) => {
          const val = d[p as keyof TimeSeriesPoint];
          return typeof val === 'number' ? val : 0;
        }),
      })),
    };
  }, [data]);

  return (
    <ReactEChartsCore
      option={option}
      style={{ height: 400, width: '100%' }}
      onChartReady={(instance) => setChartInstance(instance)}
      notMerge
    />
  );
});

TimeSeriesChart.displayName = 'TimeSeriesChart';
