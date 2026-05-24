import { useEffect, useState } from 'react';
import { fetchCrossDim, fetchCompanies, fetchByGeo } from './dataClient';
import { deriveFilterOptions } from './filterOptions';
import type { CrossDimRow, CompaniesData, GeoData } from './sharedTypes';
import type { FilterOptions } from './filterOptions';

export interface DashboardData {
  allCrossDim: CrossDimRow[];
  companies: CompaniesData | null;
  geo: GeoData | null;
  options: FilterOptions;
  loading: boolean;
  error: string | null;
}

const EMPTY_OPTIONS: FilterOptions = {
  years: [],
  industries: [],
  countries: [],
  parents: [],
  commitments: [],
};

/**
 * Shared hook for views that need cross_dim, companies, and geo data
 * along with derived filter options. Eliminates duplicated data-fetching
 * logic across TemporalView, IndustryView, GeographicView, and CrossDimView.
 *
 * Tracks loading and error states for user-facing feedback.
 */
export function useDashboardData(): DashboardData {
  const [allCrossDim, setAllCrossDim] = useState<CrossDimRow[]>([]);
  const [companies, setCompanies] = useState<CompaniesData | null>(null);
  const [geo, setGeo] = useState<GeoData | null>(null);
  const [options, setOptions] = useState<FilterOptions>(EMPTY_OPTIONS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([fetchCrossDim(), fetchCompanies(), fetchByGeo()])
      .then(([cd, c, g]) => {
        if (cancelled) return;
        setAllCrossDim(cd);
        setCompanies(c);
        setGeo(g);
        const industries = [...new Set(cd.map((r) => r.industry).filter(Boolean))] as string[];
        setOptions(deriveFilterOptions(
          c,
          cd,
          Object.fromEntries(industries.map((i) => [i, { companies: 0, parents: {} }])),
          g,
        ));
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

  return { allCrossDim, companies, geo, options, loading, error };
}
