import { useEffect, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCompanies, fetchCrossDim } from '../lib/dataClient';
import { useStore } from '../lib/store';
import { filterCrossDim, aggregateByIndustry } from '../lib/filterUtils';
import { StackedBarChart } from '../components/charts/StackedBarChart';
import { ExportButton } from '../components/ExportButton';
import { SkeletonChart } from '../components/SkeletonChart';
import type { CompaniesData, CrossDimRow, IndustryData } from '../lib/sharedTypes';

export function OverviewView() {
  const [companies, setCompanies] = useState<CompaniesData | null>(null);
  const [allCrossDim, setAllCrossDim] = useState<CrossDimRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const filters = useStore();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([fetchCompanies(), fetchCrossDim()])
      .then(([c, cd]) => {
        if (cancelled) return;
        setCompanies(c);
        setAllCrossDim(cd);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'Failed to load dashboard data';
        setError(message);
        console.error(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  if (loading) return <SkeletonChart />;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;
  if (!companies) return <SkeletonChart />;

  // Filter cross_dim for the chart (apply full filter state including country)
  const filteredCross = filterCrossDim(allCrossDim, filters);
  const chartData: IndustryData = aggregateByIndustry(filteredCross);

  // Derive the set of tickers present in the filtered cross_dim data.
  // This ensures KPI tiles reflect the same filtered scope as the chart,
  // not a superset that ignores country/parent/commitment filters.
  const filteredTickers = new Set(filteredCross.map((r) => r.hk_ticker));

  const filteredCompanies = companies.companies.filter((c) =>
    filteredTickers.has(c.hk_ticker)
  );

  const totalRaised = filteredCompanies.reduce((s, c) => s + (c.total_net_proceeds ?? 0), 0);
  const needsReview = filteredCompanies.filter((c) => c.needs_human_review).length;

  return (
    <div>
      <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
        <KpiTile label="Companies" value={filteredCompanies.length} />
        <KpiTile label="Total Raised (HK$M)" value={totalRaised.toLocaleString()} />
        <KpiTile label="Needs Review" value={needsReview}
          highlight={needsReview > 0} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Parent Allocation by Industry</h3>
        <ExportButton chartRef={chartRef} chartLabel="overview_stacked_bar"
          csvData={{ headers: ['Industry', 'Growth (HK$M)', 'Financing (HK$M)', 'Working Capital (HK$M)', 'Others (HK$M)'],
                     rows: Object.entries(chartData).map(([ind, v]) =>
                       [ind,
                        String(v.parents['Growth'] ?? 0),
                        String(v.parents['Financing'] ?? 0),
                        String(v.parents['Working Capital'] ?? 0),
                        String(v.parents['Others'] ?? 0)]) }} />
      </div>
      <StackedBarChart ref={chartRef} data={chartData} xLabel="Industry" />
    </div>
  );
}

function KpiTile({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div style={{
      flex: 1, padding: 16, borderRadius: 8, textAlign: 'center',
      background: highlight ? '#fff3e0' : '#f5f5f5',
      border: highlight ? '2px solid #ff9800' : '1px solid #e0e0e0',
    }}>
      <div style={{ fontSize: 13, color: '#666' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
