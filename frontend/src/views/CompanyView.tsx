import { useEffect, useRef, useState } from 'react';
import type { EChartsType } from 'echarts';
import { fetchCompanies, fetchSankey } from '../lib/dataClient';
import { useStore } from '../lib/store';
import { FilterBar } from '../components/FilterBar';
import { SankeyChart } from '../components/charts/SankeyChart';
import { ExportButton } from '../components/ExportButton';
import { SkeletonTable } from '../components/SkeletonTable';
import type { CompaniesData, SankeyData } from '../lib/sharedTypes';

export function CompanyView() {
  const [companies, setCompanies] = useState<CompaniesData | null>(null);
  const [sankey, setSankey] = useState<SankeyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const activeTicker = useStore((s) => s.activeTicker);
  const setActiveTicker = useStore((s) => s.setActiveTicker);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchCompanies()
      .then((c) => {
        if (cancelled) return;
        setCompanies(c);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'Failed to load companies';
        setError(message);
        console.error(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (activeTicker) {
      let cancelled = false;
      fetchSankey(activeTicker)
        .then((s) => {
          if (!cancelled) {
            setSankey(s);
            setError(null);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            const message = err instanceof Error ? err.message : 'Failed to load Sankey data';
            setError(message);
            console.error(err);
          }
        });
      return () => { cancelled = true; };
    } else {
      setSankey(null);
    }
  }, [activeTicker]);

  const tickerList = companies?.companies?.map((c) => ({
    hk_ticker: c.hk_ticker,
    company_name_en: c.company_name_en,
  })) ?? [];

  const activeCompany = companies?.companies?.find((c) => c.hk_ticker === activeTicker);

  if (loading && !companies) return <SkeletonTable />;
  if (error && !companies) return <p style={{ color: 'red' }}>Error: {error}</p>;

  return (
    <div>
      <FilterBar
        showTickerPicker
        tickers={tickerList}
        options={{ years: [], industries: [], countries: [], parents: [], commitments: [] }}
      />
      {activeCompany?.needs_human_review && (
        <div style={{ padding: '8px 16px', background: '#fff3e0', borderRadius: 4, marginBottom: 12 }}>
          Needs Human Review
        </div>
      )}
      {error && companies && (
        <div style={{ padding: '8px 16px', background: '#fff3e0', borderRadius: 4, marginBottom: 12, color: '#e65100' }}>
          Warning: {error}
        </div>
      )}
      {sankey ? (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>
              {activeTicker} - {activeCompany?.company_name_en}
              {" "}(Total: HK${sankey.total_net_proceeds}M)
            </h3>
            <ExportButton chartRef={chartRef} chartLabel={`sankey_${activeTicker}`} />
          </div>
          <SankeyChart ref={chartRef} data={sankey} />
        </>
      ) : (
        <p>{activeTicker ? 'Loading Sankey...' : 'Select a company above to view its Sankey diagram.'}</p>
      )}
    </div>
  );
}
