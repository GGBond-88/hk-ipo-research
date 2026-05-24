/** Parent categories shared across all chart components.
 *  Single source of truth -- derived from TaxonomyData.parent_order at runtime,
 *  but hardcoded here as a build-time safety net for chart option construction. */
export const PARENTS = ['Growth', 'Financing', 'Working Capital', 'Others'] as const;

/** Color palette for parent categories used in Sankey node backgrounds. */
export const PARENT_COLORS: Record<string, string> = {
  Growth: '#5470c6',
  Financing: '#fac858',
  'Working Capital': '#91cc75',
  Others: '#ee6666',
};
