import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

// Mock dataClient before importing the hook
const mockFetchCrossDim = vi.fn();
const mockFetchCompanies = vi.fn();
const mockFetchByGeo = vi.fn();

vi.mock('../dataClient', () => ({
  fetchCrossDim: (...args: unknown[]) => mockFetchCrossDim(...args),
  fetchCompanies: (...args: unknown[]) => mockFetchCompanies(...args),
  fetchByGeo: (...args: unknown[]) => mockFetchByGeo(...args),
}));

import { useDashboardData } from '../useDashboardData';
import type { CrossDimRow, CompaniesData, GeoData } from '../sharedTypes';

function makeCrossDimRows(): CrossDimRow[] {
  return [
    {
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
    },
    {
      hk_ticker: '00002',
      industry: 'Finance',
      listing_date: '2024-01-10',
      total_net_proceeds: 500,
      use_id: 'U002',
      parent_category: 'Financing',
      percentage: 50,
      amount_hkd_million: 250,
      countries: 'HK',
      geo: 'domestic_hk',
      commitment: 'discretionary',
      specificity: 'general',
      timeline: '12-24m',
      capex_opex: 'opex',
      esg_tag: null,
    },
  ];
}

function makeCompaniesData(): CompaniesData {
  return {
    companies: [
      {
        hk_ticker: '00001',
        company_name_en: 'Tech Corp',
        listing_date: '2023-06-15',
        document_date: '2023-05-01',
        industry_primary: 'Technology',
        industry_source: 'HKEX',
        total_net_proceeds: 1000,
        currency: 'HKD',
        needs_human_review: false,
      },
      {
        hk_ticker: '00002',
        company_name_en: 'Finance Ltd',
        listing_date: '2024-01-10',
        document_date: '2023-12-01',
        industry_primary: 'Finance',
        industry_source: 'HKEX',
        total_net_proceeds: 500,
        currency: 'HKD',
        needs_human_review: false,
      },
    ],
    count: 2,
  };
}

function makeGeoData(): GeoData {
  return {
    mainland: { total_hkd_million: 300, companies: 1, parents: { Growth: 300 } },
    domestic_hk: { total_hkd_million: 250, companies: 1, parents: { Financing: 250 } },
  };
}

describe('useDashboardData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchCrossDim.mockResolvedValue(makeCrossDimRows());
    mockFetchCompanies.mockResolvedValue(makeCompaniesData());
    mockFetchByGeo.mockResolvedValue(makeGeoData());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns initial loading state', () => {
    // Delay resolution so we can observe initial state
    mockFetchCrossDim.mockReturnValue(new Promise(() => {}));
    mockFetchCompanies.mockReturnValue(new Promise(() => {}));
    mockFetchByGeo.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useDashboardData());

    expect(result.current.loading).toBe(true);
    expect(result.current.allCrossDim).toEqual([]);
    expect(result.current.companies).toBeNull();
    expect(result.current.geo).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('fetches and returns dashboard data after mount', async () => {
    const { result } = renderHook(() => useDashboardData());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.allCrossDim).toHaveLength(2);
    expect(result.current.companies).not.toBeNull();
    expect(result.current.companies!.companies).toHaveLength(2);
    expect(result.current.geo).not.toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('derives filter options from fetched data', async () => {
    const { result } = renderHook(() => useDashboardData());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const options = result.current.options;
    // Years should be derived from companies listing_date
    expect(options.years).toContain('2023');
    expect(options.years).toContain('2024');
    // Industries should be derived from byIndustry data
    expect(options.industries).toContain('Technology');
    expect(options.industries).toContain('Finance');
    // Countries derived from crossDim.countries ISO codes
    expect(options.countries).toContain('CN');
    expect(options.countries).toContain('US');
    expect(options.countries).toContain('HK');
    // Parents are hardcoded
    expect(options.parents).toEqual(['Growth', 'Financing', 'Working Capital', 'Others']);
    // Commitments are hardcoded
    expect(options.commitments).toEqual(['committed', 'discretionary']);
  });

  it('sets error state when fetchCrossDim fails', async () => {
    mockFetchCrossDim.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useDashboardData());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.error).toContain('Network error');
  });

  it('sets error state when fetchCompanies fails', async () => {
    mockFetchCompanies.mockRejectedValue(new Error('Server error'));

    const { result } = renderHook(() => useDashboardData());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.error).toContain('Server error');
  });

  it('sets error state when fetchByGeo fails', async () => {
    mockFetchByGeo.mockRejectedValue(new Error('Not found'));

    const { result } = renderHook(() => useDashboardData());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.error).toContain('Not found');
  });
});
