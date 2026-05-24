import { useStore } from '../lib/store';
import type { FilterState } from '../lib/store';
import type { FilterOptions } from '../lib/filterOptions';

interface FilterBarProps {
  options: FilterOptions;
  showTickerPicker?: boolean;
  tickers?: { hk_ticker: string; company_name_en: string }[];
}

const LABELS: Record<keyof FilterState, string> = {
  year: 'Year',
  industry: 'Industry',
  country: 'Country',
  parent: 'Parent',
  commitment: 'Commitment',
};

type FilterKey = keyof FilterState;

const DIM_KEYS: FilterKey[] = ['year', 'industry', 'country', 'parent', 'commitment'];

function toSelectItems(values: string[]): { value: string; label: string }[] {
  return values.map((v) => ({ value: v, label: v }));
}

export function FilterBar({ options, showTickerPicker, tickers }: FilterBarProps) {
  const { year, industry, country, parent, commitment, setFilter, resetFilters,
          activeTicker, setActiveTicker } = useStore();

  const optionMap: Record<FilterKey, string[]> = {
    year: options.years,
    industry: options.industries,
    country: options.countries,
    parent: options.parents,
    commitment: options.commitments,
  };

  const valueMap: Record<FilterKey, string> = {
    year: year ?? '', industry: industry ?? '',
    country: country ?? '', parent: parent ?? '',
    commitment: commitment ?? '',
  };

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginBottom: 16 }}>
      {DIM_KEYS.filter((dim) => optionMap[dim].length > 0).map((dim) => (
        <label key={dim} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 14 }}>
          {LABELS[dim]}:
          <select
            value={valueMap[dim]}
            onChange={(e) => setFilter(dim, e.target.value || null)}
            style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}
          >
            <option value="">All</option>
            {toSelectItems(optionMap[dim]).map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
      ))}
      {showTickerPicker && tickers && tickers.length > 0 && (
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 14 }}>
          Company:
          <select
            value={activeTicker ?? ''}
            onChange={(e) => setActiveTicker(e.target.value || null)}
            style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc' }}
          >
            <option value="">Select...</option>
            {tickers.map((t) => (
              <option key={t.hk_ticker} value={t.hk_ticker}>
                {t.hk_ticker} - {t.company_name_en}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="button"
        onClick={resetFilters}
        style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid #ccc',
                 background: '#fff', cursor: 'pointer', fontSize: 13 }}
      >
        Reset Filters
      </button>
    </div>
  );
}
