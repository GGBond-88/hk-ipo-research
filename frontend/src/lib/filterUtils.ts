import type { FilterState } from './store';
import type { CrossDimRow, TimeSeriesPoint, IndustryData, GeoData } from './sharedTypes';

/**
 * Filter per-use rows by the global filter state.
 * Each non-null filter dimension must match; rows failing any filter are excluded.
 */
export function filterCrossDim(rows: CrossDimRow[], filters: FilterState): CrossDimRow[] {
  return rows.filter((row) => {
    if (filters.year) {
      const rowYear = row.listing_date?.slice(0, 4);
      if (rowYear !== filters.year) return false;
    }
    if (filters.industry && row.industry !== filters.industry) return false;
    if (filters.parent && row.parent_category !== filters.parent) return false;
    if (filters.country) {
      if (!row.countries || !row.countries.split(',').map(s => s.trim()).includes(filters.country)) return false;
    }
    if (filters.commitment && row.commitment !== filters.commitment) return false;
    return true;
  });
}

/**
 * Aggregate filtered CrossDimRow[] into time-series points (year -> parent HKD million).
 * Uses amount_hkd_million so that allocations from larger IPOs carry proportionally
 * more weight than allocations from smaller IPOs.
 */
export function aggregateTimeSeries(rows: CrossDimRow[]): TimeSeriesPoint[] {
  const byYear: Record<string, Record<string, number>> = {};
  for (const r of rows) {
    const year = (r.listing_date ?? '').slice(0, 4);
    if (!year) continue;
    if (!byYear[year]) byYear[year] = {};
    byYear[year][r.parent_category] =
      (byYear[year][r.parent_category] ?? 0) + (r.amount_hkd_million ?? 0);
  }
  return Object.entries(byYear)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([year, parents]) => ({ year, ...parents }));
}

/**
 * Aggregate filtered CrossDimRow[] into by-industry data (industry -> parent HKD million).
 * Uses amount_hkd_million so that allocations from larger IPOs carry proportionally
 * more weight than allocations from smaller IPOs.
 */
export function aggregateByIndustry(rows: CrossDimRow[]): IndustryData {
  const result: IndustryData = {};
  for (const r of rows) {
    const ind = r.industry ?? 'Unknown';
    if (!result[ind]) result[ind] = { companies: 0, parents: {} };
    result[ind].parents[r.parent_category] =
      (result[ind].parents[r.parent_category] ?? 0) + (r.amount_hkd_million ?? 0);
  }
  // Count distinct tickers per industry
  const tickersByIndustry = new Map<string, Set<string>>();
  for (const r of rows) {
    const ind = r.industry ?? 'Unknown';
    if (!tickersByIndustry.has(ind)) tickersByIndustry.set(ind, new Set());
    tickersByIndustry.get(ind)!.add(r.hk_ticker);
  }
  for (const [ind, tickers] of tickersByIndustry) {
    if (result[ind]) result[ind].companies = tickers.size;
  }
  return result;
}

/**
 * Aggregate filtered CrossDimRow[] into by-geo data with parent breakdown.
 * Each geo region includes total_hkd_million, company count, and
 * parent-category HKD million amounts so the GeographicView can render
 * a parent-breakdown stacked bar per region.
 * Uses amount_hkd_million consistently for both total and parent breakdown
 * so that allocations from larger IPOs carry proportionally more weight.
 */
export function aggregateByGeo(rows: CrossDimRow[]): GeoData {
  const result: GeoData = {};
  const tickersByGeo = new Map<string, Set<string>>();
  for (const r of rows) {
    const geo = r.geo ?? 'unspecified';
    if (!result[geo]) {
      result[geo] = { total_hkd_million: 0, companies: 0, parents: {} };
    }
    result[geo].total_hkd_million += (r.amount_hkd_million ?? 0);
    result[geo].parents[r.parent_category] =
      (result[geo].parents[r.parent_category] ?? 0) + (r.amount_hkd_million ?? 0);
    if (!tickersByGeo.has(geo)) tickersByGeo.set(geo, new Set());
    tickersByGeo.get(geo)!.add(r.hk_ticker);
  }
  for (const [geo, tickers] of tickersByGeo) {
    if (result[geo]) result[geo].companies = tickers.size;
  }
  return result;
}
