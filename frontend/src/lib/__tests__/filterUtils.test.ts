import { describe, it, expect } from 'vitest';
import { filterCrossDim, aggregateTimeSeries, aggregateByIndustry, aggregateByGeo } from '../filterUtils';
import type { FilterState } from '../store';
import type { CrossDimRow } from '../sharedTypes';

// ── Test helpers ──────────────────────────────────────────────────────────

function makeRow(overrides: Partial<CrossDimRow> = {}): CrossDimRow {
  return {
    hk_ticker: '00001',
    industry: 'Technology',
    listing_date: '2023-06-15',
    total_net_proceeds: 1000,
    use_id: 'U001',
    parent_category: 'Growth',
    percentage: 30,
    amount_hkd_million: 300,
    countries: 'CN,US',
    geo: 'mainland',
    commitment: 'committed',
    specificity: 'specific',
    timeline: '0-12m',
    capex_opex: 'capex',
    esg_tag: 'green',
    ...overrides,
  };
}

function emptyFilters(): FilterState {
  return { year: null, industry: null, country: null, parent: null, commitment: null };
}

// ── filterCrossDim ────────────────────────────────────────────────────────

describe('filterCrossDim', () => {
  it('returns empty array for empty rows', () => {
    expect(filterCrossDim([], emptyFilters())).toEqual([]);
  });

  it('returns all rows when no filters are active', () => {
    const rows = [makeRow(), makeRow({ hk_ticker: '00002' })];
    expect(filterCrossDim(rows, emptyFilters())).toEqual(rows);
  });

  it('filters by year extracted from listing_date', () => {
    const row2023 = makeRow({ hk_ticker: 'A', listing_date: '2023-01-01' });
    const row2024 = makeRow({ hk_ticker: 'B', listing_date: '2024-01-01' });
    const result = filterCrossDim(
      [row2023, row2024],
      { ...emptyFilters(), year: '2023' },
    );
    expect(result).toEqual([row2023]);
  });

  it('excludes rows with null listing_date when filtering by year', () => {
    const row = makeRow({ listing_date: null });
    const result = filterCrossDim(
      [row],
      { ...emptyFilters(), year: '2023' },
    );
    expect(result).toEqual([]);
  });

  it('filters by industry exact match', () => {
    const tech = makeRow({ hk_ticker: 'A', industry: 'Technology' });
    const fin = makeRow({ hk_ticker: 'B', industry: 'Finance' });
    const result = filterCrossDim(
      [tech, fin],
      { ...emptyFilters(), industry: 'Technology' },
    );
    expect(result).toEqual([tech]);
  });

  it('excludes rows with null industry when filtering by industry', () => {
    const row = makeRow({ industry: null });
    const result = filterCrossDim(
      [row],
      { ...emptyFilters(), industry: 'Technology' },
    );
    expect(result).toEqual([]);
  });

  it('filters by parent_category', () => {
    const growth = makeRow({ hk_ticker: 'A', parent_category: 'Growth' });
    const capex = makeRow({ hk_ticker: 'B', parent_category: 'CapEx' });
    const result = filterCrossDim(
      [growth, capex],
      { ...emptyFilters(), parent: 'Growth' },
    );
    expect(result).toEqual([growth]);
  });

  it('filters by country with exact match', () => {
    const cnRow = makeRow({ hk_ticker: 'A', countries: 'CN,US' });
    const jpRow = makeRow({ hk_ticker: 'B', countries: 'JP' });
    const result = filterCrossDim(
      [cnRow, jpRow],
      { ...emptyFilters(), country: 'CN' },
    );
    expect(result).toEqual([cnRow]);
  });

  it('trims whitespace in comma-separated countries (CR-002)', () => {
    const row = makeRow({ hk_ticker: 'A', countries: 'CN, HK, US' });
    // Without trimming, " HK" would not match "HK"
    const result = filterCrossDim(
      [row],
      { ...emptyFilters(), country: 'HK' },
    );
    expect(result).toEqual([row]);
  });

  it('excludes row with null countries when filtering by country', () => {
    const row = makeRow({ countries: null });
    const result = filterCrossDim(
      [row],
      { ...emptyFilters(), country: 'CN' },
    );
    expect(result).toEqual([]);
  });

  it('filters by commitment', () => {
    const committed = makeRow({ hk_ticker: 'A', commitment: 'committed' });
    const disc = makeRow({ hk_ticker: 'B', commitment: 'discretionary' });
    const result = filterCrossDim(
      [committed, disc],
      { ...emptyFilters(), commitment: 'committed' },
    );
    expect(result).toEqual([committed]);
  });

  it('applies multiple filters with AND logic', () => {
    const match = makeRow({ hk_ticker: 'A', listing_date: '2023-01-01', industry: 'Tech', parent_category: 'Growth', commitment: 'committed' });
    const wrongYear = makeRow({ hk_ticker: 'B', listing_date: '2024-01-01', industry: 'Tech', parent_category: 'Growth', commitment: 'committed' });
    const wrongInd = makeRow({ hk_ticker: 'C', listing_date: '2023-01-01', industry: 'Finance', parent_category: 'Growth', commitment: 'committed' });
    const result = filterCrossDim(
      [match, wrongYear, wrongInd],
      { year: '2023', industry: 'Tech', country: null, parent: null, commitment: null },
    );
    expect(result).toEqual([match]);
  });

  it('returns empty when no rows match filter', () => {
    const rows = [makeRow({ industry: 'Tech' })];
    const result = filterCrossDim(
      rows,
      { ...emptyFilters(), industry: 'NonexistentIndustry' },
    );
    expect(result).toEqual([]);
  });
});

// ── aggregateTimeSeries ───────────────────────────────────────────────────

describe('aggregateTimeSeries', () => {
  it('returns empty array for empty rows', () => {
    expect(aggregateTimeSeries([])).toEqual([]);
  });

  it('aggregates amount_hkd_million by year', () => {
    const rows = [
      makeRow({ listing_date: '2023-01-01', parent_category: 'Growth', amount_hkd_million: 100 }),
      makeRow({ listing_date: '2023-02-01', parent_category: 'Growth', amount_hkd_million: 200 }),
    ];
    const result = aggregateTimeSeries(rows);
    expect(result).toEqual([{ year: '2023', Growth: 300 }]);
  });

  it('aggregates multiple parent categories per year', () => {
    const rows = [
      makeRow({ listing_date: '2023-01-01', parent_category: 'Growth', amount_hkd_million: 100 }),
      makeRow({ listing_date: '2023-02-01', parent_category: 'Financing', amount_hkd_million: 50 }),
    ];
    const result = aggregateTimeSeries(rows);
    expect(result).toEqual([{ year: '2023', Growth: 100, Financing: 50 }]);
  });

  it('sorts years chronologically', () => {
    const rows = [
      makeRow({ listing_date: '2024-01-01', parent_category: 'Growth', amount_hkd_million: 100 }),
      makeRow({ listing_date: '2023-01-01', parent_category: 'Growth', amount_hkd_million: 50 }),
    ];
    const result = aggregateTimeSeries(rows);
    expect(result).toHaveLength(2);
    expect(result[0].year).toBe('2023');
    expect(result[1].year).toBe('2024');
  });

  it('skips rows with null listing_date', () => {
    const rows = [
      makeRow({ listing_date: null, parent_category: 'Growth', amount_hkd_million: 100 }),
      makeRow({ listing_date: '2023-01-01', parent_category: 'Growth', amount_hkd_million: 50 }),
    ];
    const result = aggregateTimeSeries(rows);
    expect(result).toEqual([{ year: '2023', Growth: 50 }]);
  });

  it('weights by amount_hkd_million not percentage (CR-001)', () => {
    // Large IPO (10000M) with 10% allocation = 1000M HKD
    // Small IPO (100M) with 50% allocation = 50M HKD
    // If using raw percentage: 10+50=60; if using amount: 1000+50=1050
    const largeIpo = makeRow({
      hk_ticker: 'BIG',
      listing_date: '2023-01-01',
      total_net_proceeds: 10000,
      amount_hkd_million: 1000,
      percentage: 10,
      parent_category: 'Growth',
    });
    const smallIpo = makeRow({
      hk_ticker: 'SML',
      listing_date: '2023-01-01',
      total_net_proceeds: 100,
      amount_hkd_million: 50,
      percentage: 50,
      parent_category: 'Growth',
    });
    const result = aggregateTimeSeries([largeIpo, smallIpo]);
    expect(result[0].Growth).toBe(1050);
  });

  it('handles rows with zero amount_hkd_million', () => {
    const rows = [
      makeRow({ listing_date: '2023-01-01', parent_category: 'Growth', amount_hkd_million: 0 }),
    ];
    const result = aggregateTimeSeries(rows);
    expect(result).toEqual([{ year: '2023', Growth: 0 }]);
  });
});

// ── aggregateByIndustry ────────────────────────────────────────────────────

describe('aggregateByIndustry', () => {
  it('returns empty object for empty rows', () => {
    expect(aggregateByIndustry([])).toEqual({});
  });

  it('aggregates amount_hkd_million by industry', () => {
    const rows = [
      makeRow({ industry: 'Tech', parent_category: 'Growth', amount_hkd_million: 100 }),
      makeRow({ industry: 'Tech', parent_category: 'Growth', amount_hkd_million: 200 }),
    ];
    const result = aggregateByIndustry(rows);
    expect(result).toEqual({
      Tech: { companies: 1, parents: { Growth: 300 } },
    });
  });

  it('defaults null industry to "Unknown"', () => {
    const rows = [
      makeRow({ industry: null, parent_category: 'Growth', amount_hkd_million: 100 }),
    ];
    const result = aggregateByIndustry(rows);
    expect(result).toHaveProperty('Unknown');
    expect(result['Unknown']).toEqual({ companies: 1, parents: { Growth: 100 } });
  });

  it('counts distinct tickers per industry (no duplicates)', () => {
    const rows = [
      makeRow({ industry: 'Tech', hk_ticker: 'T001', amount_hkd_million: 10 }),
      makeRow({ industry: 'Tech', hk_ticker: 'T001', amount_hkd_million: 20 }),
      makeRow({ industry: 'Tech', hk_ticker: 'T002', amount_hkd_million: 30 }),
    ];
    const result = aggregateByIndustry(rows);
    expect(result['Tech'].companies).toBe(2);
  });

  it('aggregates multiple parent categories per industry', () => {
    const rows = [
      makeRow({ industry: 'Tech', parent_category: 'Growth', amount_hkd_million: 100 }),
      makeRow({ industry: 'Tech', parent_category: 'Financing', amount_hkd_million: 50 }),
    ];
    const result = aggregateByIndustry(rows);
    expect(result['Tech'].parents).toEqual({ Growth: 100, Financing: 50 });
  });

  it('weights by amount_hkd_million not percentage (CR-001)', () => {
    const largeIpo = makeRow({
      hk_ticker: 'BIG',
      industry: 'Tech',
      total_net_proceeds: 10000,
      amount_hkd_million: 1000,
      percentage: 10,
      parent_category: 'Growth',
    });
    const smallIpo = makeRow({
      hk_ticker: 'SML',
      industry: 'Tech',
      total_net_proceeds: 100,
      amount_hkd_million: 50,
      percentage: 50,
      parent_category: 'Growth',
    });
    const result = aggregateByIndustry([largeIpo, smallIpo]);
    // 1000 + 50 = 1050 (not 10 + 50 = 60)
    expect(result['Tech'].parents['Growth']).toBe(1050);
  });

  it('handles multiple industries independently', () => {
    const rows = [
      makeRow({ industry: 'Tech', hk_ticker: 'T001', amount_hkd_million: 100 }),
      makeRow({ industry: 'Finance', hk_ticker: 'F001', amount_hkd_million: 200 }),
    ];
    const result = aggregateByIndustry(rows);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result['Tech'].companies).toBe(1);
    expect(result['Finance'].companies).toBe(1);
  });
});

// ── aggregateByGeo ─────────────────────────────────────────────────────────

describe('aggregateByGeo', () => {
  it('returns empty object for empty rows', () => {
    expect(aggregateByGeo([])).toEqual({});
  });

  it('aggregates total_hkd_million and parents by geo', () => {
    const rows = [
      makeRow({ geo: 'mainland', amount_hkd_million: 100, parent_category: 'Growth' }),
      makeRow({ geo: 'mainland', amount_hkd_million: 50, parent_category: 'Financing' }),
    ];
    const result = aggregateByGeo(rows);
    expect(result['mainland']).toEqual({
      total_hkd_million: 150,
      companies: 1,
      parents: { Growth: 100, Financing: 50 },
    });
  });

  it('defaults null geo to "unspecified"', () => {
    const rows = [
      makeRow({ geo: null, amount_hkd_million: 100, parent_category: 'Growth' }),
    ];
    const result = aggregateByGeo(rows);
    expect(result).toHaveProperty('unspecified');
  });

  it('counts distinct tickers per geo (no duplicates)', () => {
    const rows = [
      makeRow({ geo: 'mainland', hk_ticker: 'T001', amount_hkd_million: 10 }),
      makeRow({ geo: 'mainland', hk_ticker: 'T001', amount_hkd_million: 20 }),
      makeRow({ geo: 'mainland', hk_ticker: 'T002', amount_hkd_million: 30 }),
    ];
    const result = aggregateByGeo(rows);
    expect(result['mainland'].companies).toBe(2);
  });

  it('uses amount_hkd_million consistently for both total and parents (CR-001)', () => {
    const largeIpo = makeRow({
      hk_ticker: 'BIG',
      geo: 'overseas',
      total_net_proceeds: 10000,
      amount_hkd_million: 1000,
      percentage: 10,
      parent_category: 'Growth',
    });
    const smallIpo = makeRow({
      hk_ticker: 'SML',
      geo: 'overseas',
      total_net_proceeds: 100,
      amount_hkd_million: 50,
      percentage: 50,
      parent_category: 'Growth',
    });
    const result = aggregateByGeo([largeIpo, smallIpo]);
    // total: 1000+50=1050, parent: 1000+50=1050
    expect(result['overseas'].total_hkd_million).toBe(1050);
    expect(result['overseas'].parents['Growth']).toBe(1050);
  });

  it('handles multiple geo regions independently', () => {
    const rows = [
      makeRow({ geo: 'mainland', hk_ticker: 'T001', amount_hkd_million: 100 }),
      makeRow({ geo: 'overseas', hk_ticker: 'F001', amount_hkd_million: 200 }),
    ];
    const result = aggregateByGeo(rows);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result['mainland'].companies).toBe(1);
    expect(result['overseas'].companies).toBe(1);
  });
});
