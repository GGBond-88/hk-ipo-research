import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import type { CrossDimRow } from '../../lib/sharedTypes';

interface Props {
  data: CrossDimRow[];
  xKey: keyof CrossDimRow;
  yKey: keyof CrossDimRow;
}

/** Safely extract a numeric value from a CrossDimRow field.
 *  CrossDimRow fields may be `string | number | null`. */
function toNumeric(val: CrossDimRow[keyof CrossDimRow]): number {
  if (typeof val === 'number') return val;
  const n = Number(val);
  return Number.isNaN(n) ? 0 : n;
}

/** Determine the ECharts axis type for a given CrossDimRow key by inspecting
 *  the first non-null value in the dataset.  Fields that are `number` in the
 *  schema (percentage, amount_hkd_million, total_net_proceeds) use `'value'`;
 *  string-based enrichment tags use `'category'` so ECharts treats them as
 *  discrete labels rather than coercing them to zero. */
function getAxisType(data: CrossDimRow[], key: keyof CrossDimRow): 'value' | 'category' {
  for (const row of data) {
    const val = row[key];
    if (val === null || val === undefined) continue;
    return typeof val === 'number' ? 'value' : 'category';
  }
  return 'value'; // all values null → default to numeric
}

/** Extract an axis-ready value.  For category axes the raw string is returned
 *  (nulls become 'N/A'); for value axes `toNumeric` is used. */
function getAxisValue(
  val: CrossDimRow[keyof CrossDimRow],
  axisType: 'value' | 'category',
): number | string {
  if (axisType === 'category') {
    if (val === null || val === undefined) return 'N/A';
    return String(val);
  }
  return toNumeric(val);
}

type TooltipValue = [number | string, number | string, string, string];

export const ScatterChart = forwardRef<EChartsType | null, Props>(({ data, xKey, yKey }, ref) => {
  const [chartInstance, setChartInstance] = useState<EChartsType | null>(null);

  useImperativeHandle<EChartsType | null, EChartsType | null>(ref, () => chartInstance, [chartInstance]);

  const option = useMemo(() => {
    const xAxisType = getAxisType(data, xKey);
    const yAxisType = getAxisType(data, yKey);

    const byIndustry = new Map<string, CrossDimRow[]>();
    data.forEach((d) => {
      const ind = d.industry ?? 'Unknown';
      if (!byIndustry.has(ind)) byIndustry.set(ind, []);
      byIndustry.get(ind)!.push(d);
    });

    return {
      tooltip: {
        formatter: (params: { value: TooltipValue }) => {
          const d = params.value;
          return `${d[2]}<br/>${String(xKey)}: ${d[0]}<br/>${String(yKey)}: ${d[1]}<br/>Ticker: ${d[3]}`;
        },
      },
      legend: { bottom: 0 },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: { type: xAxisType, name: String(xKey) },
      yAxis: { type: yAxisType, name: String(yKey) },
      series: Array.from(byIndustry.entries()).map(([ind, rows]) => ({
        name: ind,
        type: 'scatter' as const,
        data: rows.map((r): TooltipValue => [
          getAxisValue(r[xKey], xAxisType),
          getAxisValue(r[yKey], yAxisType),
          ind,
          r.hk_ticker,
        ]),
      })),
    };
  }, [data, xKey, yKey]);

  return (
    <ReactEChartsCore
      option={option}
      style={{ height: 400, width: '100%' }}
      onChartReady={(instance) => setChartInstance(instance)}
      notMerge
    />
  );
});

ScatterChart.displayName = 'ScatterChart';
