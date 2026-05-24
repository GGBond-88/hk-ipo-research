import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { IndustryData } from '../../lib/sharedTypes';
import { PARENTS } from '../../lib/chartConstants';

interface Props {
  data: IndustryData;
}

export const HeatmapChart = forwardRef<EChartsType | null, Props>(({ data }, ref) => {
  const [chartInstance, setChartInstance] = useState<EChartsType | null>(null);

  useImperativeHandle<EChartsType | null, EChartsType | null>(ref, () => chartInstance, [chartInstance]);

  const option = useMemo(() => {
    const industries = Object.keys(data);
    const heatData: [number, number, number][] = [];
    industries.forEach((ind, iIdx) => {
      const pData = data[ind].parents ?? {};
      PARENTS.forEach((p, pIdx) => {
        heatData.push([pIdx, iIdx, pData[p] ?? 0]);
      });
    });

    return {
      tooltip: { position: 'top' as const },
      grid: { left: 120, right: 20, top: 20, bottom: 60 },
      xAxis: {
        type: 'category' as const,
        data: [...PARENTS],
        position: 'bottom',
      },
      yAxis: {
        type: 'category' as const,
        data: industries,
        axisLabel: { fontSize: 11 },
      },
      visualMap: {
        min: 0,
        max: Math.max(...heatData.map((d) => d[2]), 1),
        calculable: true,
        orient: 'horizontal' as const,
        left: 'center',
        bottom: 0,
      },
      series: [{
        type: 'heatmap',
        data: heatData,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } },
      }],
    };
  }, [data]);

  return (
    <ReactEChartsCore
      option={option}
      style={{ height: 500, width: '100%' }}
      onChartReady={(instance) => setChartInstance(instance)}
      notMerge
    />
  );
});

HeatmapChart.displayName = 'HeatmapChart';
