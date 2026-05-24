# Task 024: Frontend chart components

## Project Overview

- **Goal:** React dashboard for HKEX use-of-proceeds analytics.
- **Architecture:** Each chart component wraps ECharts via `echarts-for-react`, accepts a `chartRef` (forwarded ref), and renders from pre-baked JSON data props.
- **Tech Stack:** React + TypeScript + ECharts (echarts-for-react).

## Task Objective

Implement all 5 chart components: SankeyChart, StackedBarChart, TimeSeriesChart, HeatmapChart, ScatterChart. Each renders from typed props and forwards a ref so ExportButton can call `getDataURL`.

This is Task 24 of 27.

---

**Files:**
- Create: `frontend/src/components/charts/SankeyChart.tsx`
- Create: `frontend/src/components/charts/StackedBarChart.tsx`
- Create: `frontend/src/components/charts/TimeSeriesChart.tsx`
- Create: `frontend/src/components/charts/HeatmapChart.tsx`
- Create: `frontend/src/components/charts/ScatterChart.tsx`

- [ ] **Step 1: Create `frontend/src/components/charts/SankeyChart.tsx`**

```tsx
import { forwardRef, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { SankeyData } from '../../lib/sharedTypes';

interface Props {
  data: SankeyData;
  onNodeClick?: (nodeName: string) => void;
}

const PARENT_COLORS: Record<string, string> = {
  Growth: '#5470c6',
  Financing: '#fac858',
  'Working Capital': '#91cc75',
  Others: '#ee6666',
};

export const SankeyChart = forwardRef<EChartsType, Props>(({ data, onNodeClick }, ref) => {
  const option = useMemo(() => ({
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          return `${params.data.source} -> ${params.data.target}<br/>HK$${params.data.value}M`;
        }
        return `${params.name}`;
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

  const handleClick = (params: any) => {
    if (params.dataType === 'node' && onNodeClick) {
      onNodeClick(params.name);
    }
  };

  return (
    <ReactEChartsCore
      ref={ref as any}
      option={option}
      style={{ height: 500, width: '100%' }}
      onEvents={{ click: handleClick }}
      notMerge
    />
  );
});

SankeyChart.displayName = 'SankeyChart';
```

- [ ] **Step 2: Create `frontend/src/components/charts/StackedBarChart.tsx`**

```tsx
import { forwardRef, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { IndustryData } from '../../lib/sharedTypes';

interface Props {
  data: IndustryData | Record<string, Record<string, number>>;
  xLabel?: string;
}

export const StackedBarChart = forwardRef<EChartsType, Props>(({ data, xLabel }, ref) => {
  const option = useMemo(() => {
    const parents = ['Growth', 'Financing', 'Working Capital', 'Others'];
    const entries = Object.entries(data);

    return {
      tooltip: { trigger: 'axis' as const },
      legend: { bottom: 0, data: parents },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        name: xLabel ?? '',
        axisLabel: { rotate: 30, fontSize: 10 },
      },
      yAxis: { type: 'value' as const, name: '% allocation' },
      series: parents.map((p) => ({
        name: p,
        type: 'bar' as const,
        stack: 'total',
        data: entries.map(([, v]) => {
          const parentsData = (v as any).parents ?? v;
          return parentsData[p] ?? 0;
        }),
      })),
    };
  }, [data, xLabel]);

  return (
    <ReactEChartsCore ref={ref as any} option={option}
      style={{ height: 400, width: '100%' }} notMerge />
  );
});

StackedBarChart.displayName = 'StackedBarChart';
```

- [ ] **Step 3: Create `frontend/src/components/charts/TimeSeriesChart.tsx`**

```tsx
import { forwardRef, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { TimeSeriesPoint } from '../../lib/sharedTypes';

interface Props {
  data: TimeSeriesPoint[];
}

export const TimeSeriesChart = forwardRef<EChartsType, Props>(({ data }, ref) => {
  const option = useMemo(() => {
    const parents = ['Growth', 'Financing', 'Working Capital', 'Others'];
    return {
      tooltip: { trigger: 'axis' as const },
      legend: { bottom: 0, data: parents },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        data: data.map((d) => d.year),
      },
      yAxis: { type: 'value' as const, name: '%' },
      series: parents.map((p) => ({
        name: p,
        type: 'line' as const,
        stack: 'total',
        areaStyle: {},
        data: data.map((d) => (d as any)[p] ?? 0),
      })),
    };
  }, [data]);

  return (
    <ReactEChartsCore ref={ref as any} option={option}
      style={{ height: 400, width: '100%' }} notMerge />
  );
});

TimeSeriesChart.displayName = 'TimeSeriesChart';
```

- [ ] **Step 4: Create `frontend/src/components/charts/HeatmapChart.tsx`**

```tsx
import { forwardRef, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { IndustryData } from '../../lib/sharedTypes';

interface Props {
  data: IndustryData;
}

export const HeatmapChart = forwardRef<EChartsType, Props>(({ data }, ref) => {
  const option = useMemo(() => {
    const parents = ['Growth', 'Financing', 'Working Capital', 'Others'];
    const industries = Object.keys(data);
    const heatData: [number, number, number][] = [];
    industries.forEach((ind, iIdx) => {
      const pData = data[ind].parents ?? {};
      parents.forEach((p, pIdx) => {
        heatData.push([pIdx, iIdx, pData[p] ?? 0]);
      });
    });

    return {
      tooltip: { position: 'top' as const },
      grid: { left: 120, right: 20, top: 20, bottom: 60 },
      xAxis: {
        type: 'category' as const,
        data: parents,
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
    <ReactEChartsCore ref={ref as any} option={option}
      style={{ height: 500, width: '100%' }} notMerge />
  );
});

HeatmapChart.displayName = 'HeatmapChart';
```

- [ ] **Step 5: Create `frontend/src/components/charts/ScatterChart.tsx`**

```tsx
import { forwardRef, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { CrossDimRow } from '../../lib/sharedTypes';

interface Props {
  data: CrossDimRow[];
  xKey: keyof CrossDimRow;
  yKey: keyof CrossDimRow;
}

export const ScatterChart = forwardRef<EChartsType, Props>(({ data, xKey, yKey }, ref) => {
  const option = useMemo(() => {
    const byIndustry = new Map<string, CrossDimRow[]>();
    data.forEach((d) => {
      const ind = d.industry ?? 'Unknown';
      if (!byIndustry.has(ind)) byIndustry.set(ind, []);
      byIndustry.get(ind)!.push(d);
    });

    return {
      tooltip: {
        formatter: (params: any) => {
          const d = params.value as [number, number, string, string];
          return `${d[2]}<br/>${xKey}: ${d[0]}<br/>${yKey}: ${d[1]}<br/>Ticker: ${d[3]}`;
        },
      },
      legend: { bottom: 0 },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'value' as const, name: String(xKey) },
      yAxis: { type: 'value' as const, name: String(yKey) },
      series: Array.from(byIndustry.entries()).map(([ind, rows]) => ({
        name: ind,
        type: 'scatter' as const,
        data: rows.map((r) => [
          (r as any)[xKey] ?? 0,
          (r as any)[yKey] ?? 0,
          ind,
          r.hk_ticker,
        ]),
      })),
    };
  }, [data, xKey, yKey]);

  return (
    <ReactEChartsCore ref={ref as any} option={option}
      style={{ height: 400, width: '100%' }} notMerge />
  );
});

ScatterChart.displayName = 'ScatterChart';
```

- [ ] **Step 6: Verify build**

Run:
```bash
cd frontend
npm run build
```

Expected: No TypeScript errors.
