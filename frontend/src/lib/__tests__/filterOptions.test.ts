import { describe, it, expect } from 'vitest';
import { deriveFilterOptions } from '../filterOptions';
import type { CompaniesData, CrossDimRow, IndustryData, GeoData } from '../sharedTypes';

function makeCompany(overrides: Record<string, unknown> = {}) {
  return {
    hk_ticker: '00001',
    company_name_en: 'Test Corp',
    listing_date: '2023-06-15',
    document_date: '2023-06-01',
    industry_primary: 'Technology',
    industry_source: 'HKEX',
    total_net_proceeds: 1000,
    currency: 'HKD',
    needs_human_review: false,
    ...overrides,
  };
}

function makeCrossDimRow(overrides: Partial<CrossDimRow> = {}): CrossDimRow {
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

function emptyCompanies(): CompaniesData {
  return { companies: [], count: 0 };
}

function emptyIndustryData(): IndustryData {
  return {};
}

function emptyGeoData(): GeoData {
  return {};
}

describe('deriveFilterOptions', () => {
  // ── years ──────────────────────────────────────────────────────────

  it('returns empty years when companies list is empty', () => {
    const result = deriveFilterOptions(emptyCompanies(), [], emptyIndustryData(), emptyGeoData());
    expect(result.years).toEqual([]);
  });

  it('derives years from company listing_date', () => {
    const companies: CompaniesData = {
      companies: [
        makeCompany({ hk_ticker: 'A', listing_date: '2023-01-15' }),
        makeCompany({ hk_ticker: 'B', listing_date: '2024-06-01' }),
        makeCompany({ hk_ticker: 'C', listing_date: '2023-12-31' }),
      ],
      count: 3,
    };
    const result = deriveFilterOptions(companies, [], emptyIndustryData(), emptyGeoData());
    expect(result.years).toEqual(['2023', '2024']);
  });

  it('sorts years chronologically', () => {
    const companies: CompaniesData = {
      companies: [
        makeCompany({ hk_ticker: 'A', listing_date: '2025-01-01' }),
        makeCompany({ hk_ticker: 'B', listing_date: '2023-01-01' }),
        makeCompany({ hk_ticker: 'C', listing_date: '2024-01-01' }),
      ],
      count: 3,
    };
    const result = deriveFilterOptions(companies, [], emptyIndustryData(), emptyGeoData());
    expect(result.years).toEqual(['2023', '2024', '2025']);
  });

  it('deduplicates duplicate years', () => {
    const companies: CompaniesData = {
      companies: [
        makeCompany({ hk_ticker: 'A', listing_date: '2023-03-01' }),
        makeCompany({ hk_ticker: 'B', listing_date: '2023-07-01' }),
      ],
      count: 2,
    };
    const result = deriveFilterOptions(companies, [], emptyIndustryData(), emptyGeoData());
    expect(result.years).toEqual(['2023']);
  });

  it('filters out null listing_date when deriving years', () => {
    const companies: CompaniesData = {
      companies: [
        makeCompany({ hk_ticker: 'A', listing_date: '2023-01-01' }),
        makeCompany({ hk_ticker: 'B', listing_date: null }),
      ],
      count: 2,
    };
    const result = deriveFilterOptions(companies, [], emptyIndustryData(), emptyGeoData());
    expect(result.years).toEqual(['2023']);
  });

  // ── industries ──────────────────────────────────────────────────────

  it('returns empty industries when byIndustry is empty', () => {
    const result = deriveFilterOptions(emptyCompanies(), [], {}, emptyGeoData());
    expect(result.industries).toEqual([]);
  });

  it('derives industries from byIndustry keys sorted alphabetically', () => {
    const byIndustry: IndustryData = {
      'Technology': { companies: 5, parents: { Growth: 100 } },
      'Finance': { companies: 3, parents: { Financing: 50 } },
      'Healthcare': { companies: 2, parents: { Growth: 30 } },
    };
    const result = deriveFilterOptions(emptyCompanies(), [], byIndustry, emptyGeoData());
    expect(result.industries).toEqual(['Finance', 'Healthcare', 'Technology']);
  });

  // ── countries ────────────────────────────────────────────────────────

  it('returns empty countries when crossDim has no countries data', () => {
    const result = deriveFilterOptions(emptyCompanies(), [], emptyIndustryData(), emptyGeoData());
    expect(result.countries).toEqual([]);
  });

  it('derives countries from crossDim.countries ISO codes sorted alphabetically', () => {
    const rows = [
      makeCrossDimRow({ countries: 'CN,US' }),
      makeCrossDimRow({ countries: 'JP' }),
      makeCrossDimRow({ hk_ticker: 'B', countries: 'CN' }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    expect(result.countries).toEqual(['CN', 'JP', 'US']);
  });

  it('trims whitespace and filters empty strings from crossDim.countries', () => {
    const rows = [
      makeCrossDimRow({ countries: 'CN, HK, US' }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    expect(result.countries).toEqual(['CN', 'HK', 'US']);
  });

  it('handles null countries in crossDim rows gracefully', () => {
    const rows = [
      makeCrossDimRow({ countries: 'CN' }),
      makeCrossDimRow({ countries: null }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    expect(result.countries).toEqual(['CN']);
  });

  // ── parents ─────────────────────────────────────────────────────────

  it('returns spec-defined parents regardless of crossDim input', () => {
    const result = deriveFilterOptions(emptyCompanies(), [], emptyIndustryData(), emptyGeoData());
    expect(result.parents).toEqual(['Growth', 'Financing', 'Working Capital', 'Others']);
  });

  it('returns spec-defined parents even when crossDim has parent_category data', () => {
    const rows = [
      makeCrossDimRow({ parent_category: 'Growth' }),
      makeCrossDimRow({ parent_category: 'Financing' }),
      makeCrossDimRow({ parent_category: 'Growth' }),
      makeCrossDimRow({ parent_category: 'Working Capital' }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    // Spec hardcodes all four parents regardless of crossDim content
    expect(result.parents).toEqual(['Growth', 'Financing', 'Working Capital', 'Others']);
  });

  it('includes all four canonical parents when crossDim includes only a subset', () => {
    const rows = [
      makeCrossDimRow({ parent_category: 'Growth' }),
      makeCrossDimRow({ parent_category: 'Others' }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    expect(result.parents).toEqual(['Growth', 'Financing', 'Working Capital', 'Others']);
  });

  // ── commitments ──────────────────────────────────────────────────────

  it('returns spec-defined commitments regardless of crossDim input', () => {
    const result = deriveFilterOptions(emptyCompanies(), [], emptyIndustryData(), emptyGeoData());
    expect(result.commitments).toEqual(['committed', 'discretionary']);
  });

  it('returns spec-defined commitments even when crossDim has commitment data', () => {
    const rows = [
      makeCrossDimRow({ commitment: 'committed' }),
      makeCrossDimRow({ commitment: 'discretionary' }),
      makeCrossDimRow({ commitment: 'committed' }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    expect(result.commitments).toEqual(['committed', 'discretionary']);
  });

  it('returns spec-defined commitments even when crossDim has null commitments', () => {
    const rows = [
      makeCrossDimRow({ commitment: 'committed' }),
      makeCrossDimRow({ commitment: null }),
    ];
    const result = deriveFilterOptions(emptyCompanies(), rows, emptyIndustryData(), emptyGeoData());
    // Spec hardcodes both commitments regardless of crossDim content
    expect(result.commitments).toEqual(['committed', 'discretionary']);
  });

  // ── integration ──────────────────────────────────────────────────────

  it('returns complete FilterOptions with all dimensions populated', () => {
    const companies: CompaniesData = {
      companies: [
        makeCompany({ hk_ticker: 'A', listing_date: '2023-06-15' }),
        makeCompany({ hk_ticker: 'B', listing_date: '2024-01-01' }),
      ],
      count: 2,
    };
    const byIndustry: IndustryData = {
      'Technology': { companies: 1, parents: { Growth: 100 } },
      'Finance': { companies: 1, parents: { Financing: 50 } },
    };
    const byGeo: GeoData = {
      mainland: { total_hkd_million: 100, companies: 1, parents: { Growth: 100 } },
      domestic_hk: { total_hkd_million: 50, companies: 1, parents: { Financing: 50 } },
    };
    const rows = [
      makeCrossDimRow({ countries: 'CN,US', parent_category: 'Growth', commitment: 'committed' }),
      makeCrossDimRow({ countries: 'HK', parent_category: 'Financing', commitment: 'discretionary' }),
    ];

    const result = deriveFilterOptions(companies, rows, byIndustry, byGeo);

    expect(result).toEqual({
      years: ['2023', '2024'],
      industries: ['Finance', 'Technology'],
      countries: ['CN', 'HK', 'US'],
      parents: ['Growth', 'Financing', 'Working Capital', 'Others'],
      commitments: ['committed', 'discretionary'],
    });
  });

  it('handles all-empty inputs gracefully with spec-hardcoded parents and commitments', () => {
    const result = deriveFilterOptions(emptyCompanies(), [], emptyIndustryData(), emptyGeoData());
    expect(result).toEqual({
      years: [],
      industries: [],
      countries: [],
      parents: ['Growth', 'Financing', 'Working Capital', 'Others'],
      commitments: ['committed', 'discretionary'],
    });
  });
});
