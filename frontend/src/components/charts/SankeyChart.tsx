import { forwardRef, useCallback, useImperativeHandle, useMemo, useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { SankeyData } from '../../lib/sharedTypes';
import { PARENT_COLORS } from '../../lib/chartConstants';

interface Props {
  data: SankeyData;
  onNodeClick?: (nodeName: string) => void;
}

type ChartClickParams = {
  dataType?: string;
  name?: string;
  data?: {
    source?: string;
    target?: string;
    value?: number;
  };
};

export const SankeyChart = forwardRef<EChartsType | null, Props>(({ data, onNodeClick }, ref) => {
  const [chartInstance, setChartInstance] = useState<EChartsType | null>(null);

  useImperativeHandle<EChartsType | null, EChartsType | null>(ref, () => chartInstance, [chartInstance]);

  const option = useMemo(() => ({
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: ChartClickParams) => {
        if (params.dataType === 'edge') {
          return `${params.data?.source ?? ''} -> ${params.data?.target ?? ''}<br/>HK$${params.data?.value ?? 0}M`;
        }
        return `${params.name ?? ''}`;
      },
    },
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: { focus: 'adjacency' },
      nodeAlign: 'left',
      data: data.nodes.map((n) => ({
        name: n.name,
        itemStyle: {
          color: PARENT_COLORS[n.name] ?? '#999',
        },
      })),
      links: data.links,
      label: { show: true, fontSize: 11 },
      lineStyle: { color: 'gradient', curveness: 0.5 },
    }],
  }), [data]);

  const handleClick = useCallback((params: ChartClickParams) => {
    if (params.dataType === 'node' && onNodeClick) {
      onNodeClick(params.name ?? '');
    }
  }, [onNodeClick]);

  const onEvents = useMemo(() => ({ click: handleClick }), [handleClick]);

  return (
    <ReactEChartsCore
      option={option}
      style={{ height: 500, width: '100%' }}
      onEvents={onEvents}
      onChartReady={(instance) => setChartInstance(instance)}
      notMerge
    />
  );
});

SankeyChart.displayName = 'SankeyChart';
