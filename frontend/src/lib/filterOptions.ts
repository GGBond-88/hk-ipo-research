import type { CompaniesData, CrossDimRow, IndustryData, GeoData } from './sharedTypes';

export interface FilterOptions {
  years: string[];
  industries: string[];
  countries: string[];
  parents: string[];
  commitments: string[];
}

export function deriveFilterOptions(
  companies: CompaniesData,
  crossDim: CrossDimRow[],
  byIndustry: IndustryData,
  _byGeo: GeoData,
): FilterOptions {
  const years = Array.from(
    new Set(
      companies.companies
        .map((c) => c.listing_date?.slice(0, 4))
        .filter(Boolean)
    )
  ).sort() as string[];

  const industries = Object.keys(byIndustry).sort();

  // Derive country filter options from ISO country codes in CrossDimRow.countries
  // (not from GeoData keys, which are geo region names like 'mainland'/'overseas').
  // This ensures the dropdown values match what filterCrossDim checks against.
  const countries = Array.from(
    new Set(
      crossDim.flatMap((r) =>
        (r.countries ?? '')
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      )
    )
  ).sort();

  const parents = ['Growth', 'Financing', 'Working Capital', 'Others'];
  const commitments = ['committed', 'discretionary'];

  return { years, industries, countries, parents, commitments };
}
