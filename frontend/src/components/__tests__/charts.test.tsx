import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';
import type { EChartsType } from 'echarts';
import type { SankeyData, IndustryData, TimeSeriesPoint, CrossDimRow } from '../../lib/sharedTypes';

// ── Mock echarts-for-react ────────────────────────────────────────────────
// Capture the option prop so we can inspect data transformations without
// requiring a real ECharts instance.

interface MockEChartsCoreProps {
  option: unknown;
  onChartReady?: (instance: EChartsType) => void;
  onEvents?: Record<string, (...args: unknown[]) => void>;
  style?: React.CSSProperties;
  notMerge?: boolean;
}

let capturedOption: unknown = null;
let capturedOnChartReady: ((instance: EChartsType) => void) | undefined;
let capturedOnEvents: Record<string, (...args: unknown[]) => void> | undefined;

const mockEchartsInstance = {
  getDataURL: vi.fn().mockReturnValue('data:image/png;base64,mock'),
  setOption: vi.fn(),
  dispose: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
} as unknown as EChartsType;

vi.mock('echarts-for-react', () => ({
  default: (props: MockEChartsCoreProps) => {
    capturedOption = props.option;
    capturedOnChartReady = props.onChartReady;
    capturedOnEvents = props.onEvents;
    return null;
  },
}));

// Import after mock so the modules get the mocked echarts-for-react.
import { SankeyChart } from '../charts/SankeyChart';
import { StackedBarChart } from '../charts/StackedBarChart';
import { TimeSeriesChart } from '../charts/TimeSeriesChart';
import { HeatmapChart } from '../charts/HeatmapChart';
import { ScatterChart } from '../charts/ScatterChart';

// ── Test data factories ──────────────────────────────────────────────────

function makeSankeyData(overrides: Partial<SankeyData> = {}): SankeyData {
  return {
    nodes: [
      { name: 'Growth' },
      { name: 'Financing' },
      { name: 'Working Capital' },
      { name: 'Others' },
      { name: 'Product Development' },
      { name: 'Debt Repayment' },
    ],
    links: [
      { source: 'Growth', target: 'Product Development', value: 50 },
      { source: 'Financing', target: 'Debt Repayment', value: 30 },
      { source: 'Working Capital', target: 'Product Development', value: 20 },
    ],
    total_net_proceeds: 100,
    ...overrides,
  };
}

function makeIndustryData(): IndustryData {
  return {
    'Technology': { companies: 5, parents: { Growth: 40, Financing: 20, 'Working Capital': 30, Others: 10 } },
    'Finance': { companies: 3, parents: { Growth: 10, Financing: 60, 'Working Capital': 20, Others: 10 } },
  };
}

function makeTimeSeriesData(): TimeSeriesPoint[] {
  return [
    { year: '2020', Growth: 35, Financing: 25, 'Working Capital': 30, Others: 10 },
    { year: '2021', Growth: 40, Financing: 20, 'Working Capital': 25, Others: 15 },
    { year: '2022', Growth: 30, Financing: 30, 'Working Capital': 30, Others: 10 },
  ];
}

function makeCrossDimRows(): CrossDimRow[] {
  return [
    {
      hk_ticker: '00001.HK',
      industry: 'Technology',
      listing_date: '2020-01-01',
      total_net_proceeds: 1000,
      use_id: 'u1',
      parent_category: 'Growth',
      percentage: 40,
      amount_hkd_million: 400,
      countries: 'HK,CN',
      geo: 'domestic_hk',
      commitment: 'committed',
      specificity: 'specific',
      timeline: '0-12m',
      capex_opex: 'capex',
      esg_tag: 'green',
    },
    {
      hk_ticker: '00002.HK',
      industry: 'Finance',
      listing_date: '2021-06-15',
      total_net_proceeds: 500,
      use_id: 'u2',
      parent_category: 'Financing',
      percentage: 60,
      amount_hkd_million: 300,
      countries: 'US',
      geo: 'overseas',
      commitment: 'discretionary',
      specificity: 'general',
      timeline: '12-24m',
      capex_opex: 'financial',
      esg_tag: null,
    },
  ];
}

function flushOnChartReady(): void {
  if (capturedOnChartReady) {
    act(() => {
      capturedOnChartReady!(mockEchartsInstance);
    });
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────

function getOptionSeries(option: unknown): unknown[] {
  const opt = option as Record<string, unknown>;
  return (opt.series as unknown[]) ?? [];
}

describe('SankeyChart', () => {
  afterEach(() => {
    capturedOnChartReady = undefined;
    capturedOnEvents = undefined;
  });

  it('renders without crashing with valid data', () => {
    const data = makeSankeyData();
    const { container } = render(<SankeyChart data={data} />);
    expect(container).toBeDefined();
  });

  it('renders without crashing with empty nodes and links', () => {
    const data = makeSankeyData({ nodes: [], links: [], total_net_proceeds: 0 });
    const { container } = render(<SankeyChart data={data} />);
    expect(container).toBeDefined();
  });

  it('constructs a sankey series option', () => {
    const data = makeSankeyData();
    render(<SankeyChart data={data} />);
    const series = getOptionSeries(capturedOption);
    expect(series).toHaveLength(1);
    expect((series[0] as Record<string, unknown>).type).toBe('sankey');
  });

  it('maps node colors from PARENT_COLORS constant', () => {
    const data = makeSankeyData();
    render(<SankeyChart data={data} />);
    const series = getOptionSeries(capturedOption);
    const sankeyData = (series[0] as Record<string, unknown>).data as Array<{ name: string; itemStyle: { color: string } }>;
    const growthNode = sankeyData.find((n) => n.name === 'Growth');
    expect(growthNode?.itemStyle.color).toBe('#5470c6');
  });

  it('forwards the native ECharts instance via ref', () => {
    const ref = { current: null as EChartsType | null };
    const data = makeSankeyData();
    render(<SankeyChart ref={ref as React.RefObject<EChartsType | null>} data={data} />);
    flushOnChartReady();
    expect(ref.current).not.toBeNull();
    expect(ref.current?.getDataURL).toBeDefined();
  });

  it('calls onNodeClick when a node is clicked', () => {
    const onNodeClick = vi.fn();
    const data = makeSankeyData();
    render(<SankeyChart data={data} onNodeClick={onNodeClick} />);
    expect(capturedOnEvents).toBeDefined();
    expect(capturedOnEvents!.click).toBeDefined();
    // Simulate a click on a node via the captured onEvents handler
    act(() => {
      capturedOnEvents!.click!({ dataType: 'node', name: 'Growth' });
    });
    expect(onNodeClick).toHaveBeenCalledTimes(1);
    expect(onNodeClick).toHaveBeenCalledWith('Growth');
  });

  it('does not call onNodeClick when an edge is clicked', () => {
    const onNodeClick = vi.fn();
    const data = makeSankeyData();
    render(<SankeyChart data={data} onNodeClick={onNodeClick} />);
    // Simulate a click on an edge/link (not a node)
    act(() => {
      capturedOnEvents!.click!({
        dataType: 'edge',
        data: { source: 'Growth', target: 'Product Development', value: 50 },
      });
    });
    expect(onNodeClick).not.toHaveBeenCalled();
  });
});

describe('StackedBarChart', () => {
  afterEach(() => {
    capturedOnChartReady = undefined;
  });

  it('renders without crashing with IndustryData', () => {
    const data = makeIndustryData();
    const { container } = render(<StackedBarChart data={data} />);
    expect(container).toBeDefined();
  });

  it('renders without crashing with raw Record data', () => {
    const data: Record<string, Record<string, number>> = {
      'Tech': { Growth: 30, Financing: 20, 'Working Capital': 30, Others: 20 },
    };
    const { container } = render(<StackedBarChart data={data} />);
    expect(container).toBeDefined();
  });

  it('has xAxis.data with industry names (CR-001 regression)', () => {
    const data = makeIndustryData();
    render(<StackedBarChart data={data} />);
    const opt = capturedOption as Record<string, unknown>;
    const xAxis = opt.xAxis as Record<string, unknown>;
    expect(xAxis.data).toEqual(['Technology', 'Finance']);
  });

  it('constructs bar series for each parent category', () => {
    const data = makeIndustryData();
    render(<StackedBarChart data={data} />);
    const series = getOptionSeries(capturedOption);
    expect(series).toHaveLength(4); // Growth, Financing, Working Capital, Others
    const types = series.map((s) => (s as Record<string, unknown>).type);
    expect(types.every((t) => t === 'bar')).toBe(true);
  });

  it('forwards the native ECharts instance via ref', () => {
    const ref = { current: null as EChartsType | null };
    const data = makeIndustryData();
    render(<StackedBarChart ref={ref as React.RefObject<EChartsType | null>} data={data} />);
    flushOnChartReady();
    expect(ref.current).not.toBeNull();
    expect(ref.current?.getDataURL).toBeDefined();
  });

  it('renders without crashing with empty data', () => {
    const data: IndustryData = {};
    const { container } = render(<StackedBarChart data={data} />);
    expect(container).toBeDefined();
  });

  it('uses HKD Million as yAxis name not percentage (CR-005)', () => {
    const data = makeIndustryData();
    render(<StackedBarChart data={data} />);
    const opt = capturedOption as Record<string, unknown>;
    const yAxis = opt.yAxis as Record<string, unknown>;
    expect(yAxis.name).toBe('HKD Million');
  });
});

describe('TimeSeriesChart', () => {
  afterEach(() => {
    capturedOnChartReady = undefined;
  });

  it('renders without crashing with valid data', () => {
    const data = makeTimeSeriesData();
    const { container } = render(<TimeSeriesChart data={data} />);
    expect(container).toBeDefined();
  });

  it('renders without crashing with empty array', () => {
    const { container } = render(<TimeSeriesChart data={[]} />);
    expect(container).toBeDefined();
  });

  it('constructs line series for each parent category', () => {
    const data = makeTimeSeriesData();
    render(<TimeSeriesChart data={data} />);
    const series = getOptionSeries(capturedOption);
    expect(series).toHaveLength(4);
    const types = series.map((s) => (s as Record<string, unknown>).type);
    expect(types.every((t) => t === 'line')).toBe(true);
  });

  it('uses year values for xAxis data', () => {
    const data = makeTimeSeriesData();
    render(<TimeSeriesChart data={data} />);
    const opt = capturedOption as Record<string, unknown>;
    const xAxis = opt.xAxis as Record<string, unknown>;
    expect(xAxis.data).toEqual(['2020', '2021', '2022']);
  });

  it('forwards the native ECharts instance via ref', () => {
    const ref = { current: null as EChartsType | null };
    const data = makeTimeSeriesData();
    render(<TimeSeriesChart ref={ref as React.RefObject<EChartsType | null>} data={data} />);
    flushOnChartReady();
    expect(ref.current).not.toBeNull();
    expect(ref.current?.getDataURL).toBeDefined();
  });

  it('handles missing parent values gracefully (returns 0)', () => {
    const data: TimeSeriesPoint[] = [
      { year: '2023', Growth: 50 },
      // Other parent keys intentionally omitted
    ];
    render(<TimeSeriesChart data={data} />);
    const series = getOptionSeries(capturedOption);
    // All series should have data arrays of length 1
    for (const s of series) {
      const d = (s as Record<string, unknown>).data as number[];
      expect(d).toHaveLength(1);
    }
  });

  it('uses HKD Million as yAxis name not raw % (CR-005)', () => {
    const data = makeTimeSeriesData();
    render(<TimeSeriesChart data={data} />);
    const opt = capturedOption as Record<string, unknown>;
    const yAxis = opt.yAxis as Record<string, unknown>;
    expect(yAxis.name).toBe('HKD Million');
  });
});

describe('HeatmapChart', () => {
  afterEach(() => {
    capturedOnChartReady = undefined;
  });

  it('renders without crashing with valid data', () => {
    const data = makeIndustryData();
    const { container } = render(<HeatmapChart data={data} />);
    expect(container).toBeDefined();
  });

  it('renders without crashing with empty data', () => {
    const { container } = render(<HeatmapChart data={{}} />);
    expect(container).toBeDefined();
  });

  it('constructs a heatmap series', () => {
    const data = makeIndustryData();
    render(<HeatmapChart data={data} />);
    const series = getOptionSeries(capturedOption);
    expect(series).toHaveLength(1);
    expect((series[0] as Record<string, unknown>).type).toBe('heatmap');
  });

  it('maps industry names to yAxis categories', () => {
    const data = makeIndustryData();
    render(<HeatmapChart data={data} />);
    const opt = capturedOption as Record<string, unknown>;
    const yAxis = opt.yAxis as Record<string, unknown>;
    expect(yAxis.data).toEqual(['Technology', 'Finance']);
  });

  it('produces correct number of heatmap cells', () => {
    const data = makeIndustryData();
    render(<HeatmapChart data={data} />);
    const series = getOptionSeries(capturedOption);
    const heatData = (series[0] as Record<string, unknown>).data as [number, number, number][];
    // 2 industries x 4 parents = 8 cells
    expect(heatData).toHaveLength(8);
  });

  it('forwards the native ECharts instance via ref', () => {
    const ref = { current: null as EChartsType | null };
    const data = makeIndustryData();
    render(<HeatmapChart ref={ref as React.RefObject<EChartsType | null>} data={data} />);
    flushOnChartReady();
    expect(ref.current).not.toBeNull();
    expect(ref.current?.getDataURL).toBeDefined();
  });
});

describe('ScatterChart', () => {
  afterEach(() => {
    capturedOnChartReady = undefined;
  });

  it('renders without crashing with valid data', () => {
    const data = makeCrossDimRows();
    const { container } = render(<ScatterChart data={data} xKey="percentage" yKey="amount_hkd_million" />);
    expect(container).toBeDefined();
  });

  it('renders without crashing with empty array', () => {
    const { container } = render(<ScatterChart data={[]} xKey="percentage" yKey="amount_hkd_million" />);
    expect(container).toBeDefined();
  });

  it('groups points by industry into separate series', () => {
    const data = makeCrossDimRows();
    render(<ScatterChart data={data} xKey="percentage" yKey="amount_hkd_million" />);
    const series = getOptionSeries(capturedOption);
    // Two industries: Technology, Finance
    expect(series).toHaveLength(2);
    const names = series.map((s) => (s as Record<string, unknown>).name);
    expect(names).toContain('Technology');
    expect(names).toContain('Finance');
  });

  it('defaults missing industry to "Unknown"', () => {
    const data: CrossDimRow[] = [
      {
        ...makeCrossDimRows()[0],
        industry: null,
      },
    ];
    render(<ScatterChart data={data} xKey="percentage" yKey="amount_hkd_million" />);
    const series = getOptionSeries(capturedOption);
    const name = (series[0] as Record<string, unknown>).name;
    expect(name).toBe('Unknown');
  });

  it('forwards the native ECharts instance via ref', () => {
    const ref = { current: null as EChartsType | null };
    const data = makeCrossDimRows();
    render(<ScatterChart ref={ref as React.RefObject<EChartsType | null>} data={data} xKey="percentage" yKey="amount_hkd_million" />);
    flushOnChartReady();
    expect(ref.current).not.toBeNull();
    expect(ref.current?.getDataURL).toBeDefined();
  });

  it('constructs scatter series type for each group', () => {
    const data = makeCrossDimRows();
    render(<ScatterChart data={data} xKey="total_net_proceeds" yKey="amount_hkd_million" />);
    const series = getOptionSeries(capturedOption);
    const types = series.map((s) => (s as Record<string, unknown>).type);
    expect(types.every((t) => t === 'scatter')).toBe(true);
  });

  it('handles numeric keys correctly without as any', () => {
    const data = makeCrossDimRows();
    render(<ScatterChart data={data} xKey="percentage" yKey="amount_hkd_million" />);
    const series = getOptionSeries(capturedOption);
    const techSeries = series.find(
      (s) => (s as Record<string, unknown>).name === 'Technology',
    ) as Record<string, unknown>;
    const scatterData = techSeries.data as [number, number, string, string][];
    expect(scatterData).toHaveLength(1);
    // First point: [percentage, amount_hkd_million, industry, ticker]
    expect(scatterData[0][0]).toBe(40);
    expect(scatterData[0][1]).toBe(400);
    expect(scatterData[0][3]).toBe('00001.HK');
  });

  describe('categorical axis support (CR-006)', () => {
    it('uses category axis for categorical xKey', () => {
      const data = makeCrossDimRows();
      render(<ScatterChart data={data} xKey="parent_category" yKey="amount_hkd_million" />);
      const opt = capturedOption as Record<string, unknown>;
      const xAxis = opt.xAxis as Record<string, unknown>;
      expect(xAxis.type).toBe('category');
    });

    it('uses category axis for categorical yKey', () => {
      const data = makeCrossDimRows();
      render(<ScatterChart data={data} xKey="percentage" yKey="commitment" />);
      const opt = capturedOption as Record<string, unknown>;
      const yAxis = opt.yAxis as Record<string, unknown>;
      expect(yAxis.type).toBe('category');
    });

    it('uses value axis for numeric keys (unchanged)', () => {
      const data = makeCrossDimRows();
      render(<ScatterChart data={data} xKey="total_net_proceeds" yKey="amount_hkd_million" />);
      const opt = capturedOption as Record<string, unknown>;
      const xAxis = opt.xAxis as Record<string, unknown>;
      const yAxis = opt.yAxis as Record<string, unknown>;
      expect(xAxis.type).toBe('value');
      expect(yAxis.type).toBe('value');
    });

    it('preserves raw string values for categorical axes instead of coercing to 0', () => {
      const data = makeCrossDimRows();
      render(<ScatterChart data={data} xKey="parent_category" yKey="geo" />);
      const series = getOptionSeries(capturedOption);
      const techSeries = series.find(
        (s) => (s as Record<string, unknown>).name === 'Technology',
      ) as Record<string, unknown>;
      const scatterData = techSeries.data as [string, string, string, string][];
      expect(scatterData).toHaveLength(1);
      // parent_category for Technology row = 'Growth', geo = 'domestic_hk'
      expect(scatterData[0][0]).toBe('Growth');
      expect(scatterData[0][1]).toBe('domestic_hk');
    });

    it('uses "N/A" for null values within a categorical field', () => {
      // One row with non-null esg_tag so the axis is detected as categorical,
      // one row with null esg_tag to verify null→'N/A' conversion.
      const data: CrossDimRow[] = [
        { ...makeCrossDimRows()[0], esg_tag: 'green' },
        { ...makeCrossDimRows()[1], esg_tag: null },
      ];
      render(<ScatterChart data={data} xKey="esg_tag" yKey="amount_hkd_million" />);
      const opt = capturedOption as Record<string, unknown>;
      const xAxis = opt.xAxis as Record<string, unknown>;
      expect(xAxis.type).toBe('category');
      const series = getOptionSeries(capturedOption);
      // Find the row with null esg_tag (technology row has esg_tag=green, finance row has null)
      const finSeries = series.find(
        (s) => (s as Record<string, unknown>).name === 'Finance',
      ) as Record<string, unknown>;
      const scatterData = finSeries.data as [string, number, string, string][];
      expect(scatterData[0][0]).toBe('N/A');
    });

    it('defaults axis type to value when all values are null', () => {
      const data: CrossDimRow[] = [
        { ...makeCrossDimRows()[0], esg_tag: null },
        { ...makeCrossDimRows()[1], esg_tag: null },
      ];
      render(<ScatterChart data={data} xKey="esg_tag" yKey="amount_hkd_million" />);
      const opt = capturedOption as Record<string, unknown>;
      const xAxis = opt.xAxis as Record<string, unknown>;
      expect(xAxis.type).toBe('value');
    });
  });
});
