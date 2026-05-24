# Changes: Task-025

## Files
- [new] frontend/src/views/OverviewView.tsx
- [new] frontend/src/views/CompanyView.tsx
- [new] frontend/src/views/TemporalView.tsx
- [new] frontend/src/views/IndustryView.tsx
- [new] frontend/src/views/GeographicView.tsx
- [new] frontend/src/views/CrossDimView.tsx
- [mod] frontend/src/App.tsx
- [new] frontend/src/lib/useDashboardData.ts
- [new] frontend/src/lib/__tests__/useDashboardData.test.ts
- [mod] frontend/src/components/FilterBar.tsx
- [mod] frontend/src/components/charts/StackedBarChart.tsx
- [mod] frontend/src/components/charts/TimeSeriesChart.tsx
- [mod] frontend/src/components/__tests__/FilterBar.test.tsx
- [mod] frontend/src/components/__tests__/charts.test.tsx
- [mod] frontend/src/components/charts/ScatterChart.tsx
- [mod] frontend/src/views/GeographicView.tsx

## Summary (initial implementation)
Implemented all 6 view components for the HK IPO dashboard. Each view is a self-contained React component that fetches data on mount, applies global Zustand filter state, and renders ECharts charts with PNG/CSV export buttons. App.tsx was updated to wire in all views with a tab-style navigation using dynamic component rendering.

GeographicView had a minor type fix: the task spec code wrapped GeoData entries in `{ parents: val.parents }` producing `Record<string, { parents: Record<string, number> }>`, but StackedBarChart expects `IndustryData | Record<string, Record<string, number>>`. Changed to pass `val.parents` directly as `Record<string, Record<string, number>>`, which the chart's `hasParents()` guard handles correctly.

## Summary (review fixes for CR-006 through CR-007)

### CR-006: ScatterChart categorical axis support
Added `getAxisType()` and `getAxisValue()` helpers to ScatterChart.tsx. `getAxisType()` inspects the first non-null value for a key to determine whether the axis should be `'value'` (numeric fields) or `'category'` (string-based enrichment tags). `getAxisValue()` returns raw string values for category axes (with null mapped to 'N/A') and numeric values via `toNumeric()` for value axes. This preserves all 10 axis options in CrossDimView's dropdowns while correctly rendering categorical enrichment tags as discrete labels. Added 6 regression tests in charts.test.tsx covering categorical x/y axes, mixed numeric+categorical, null-in-categorical, and all-null-default scenarios.

### CR-007: GeographicView memoize chart data transformation
Wrapped `geoDataForChart` in `useMemo(() => { ... }, [chartData])` so the GeoData-to-StackedBarChart-format transformation only recomputes when the underlying memoized `chartData` changes, avoiding wasted computation during loading/error render cycles.

### CR-001: Deduplicated data-fetching logic
Created `frontend/src/lib/useDashboardData.ts` shared custom hook encapsulating data fetching, filter option derivation, loading/error states, and cleanup. Refactored TemporalView, IndustryView, GeographicView, and CrossDimView to use the hook, eliminating ~56 lines of duplicated code.

### CR-002: KPI tile consistency with chart filters
Fixed OverviewView KPI tiles to derive filtered company set from the fully-filtered cross_dim dataset, ensuring KPI tiles (Companies, Total Raised, Needs Review) reflect the same scope as the chart across all filter dimensions.

### CR-003: User-facing error states
Added loading/error states to all 6 views. The 4 hooks-based views get error states from `useDashboardData`. OverviewView and CompanyView have explicit `loading`/`error` useState with cancellation cleanup. Errors render as red text; CompanyView also shows a warning banner for Sankey failures.

### CR-004: FilterBar hides empty dropdowns
Modified FilterBar to render only filter dimensions with non-empty option lists (`.filter(dim => optionMap[dim].length > 0)`). CompanyView's empty option arrays now produce zero filter dropdowns, showing only the ticker picker and reset button.

### CR-005: Correct Y-axis and CSV labels
Changed StackedBarChart Y-axis from `'% allocation'` to `'HKD Million'` and TimeSeriesChart Y-axis from `'%'` to `'HKD Million'`. Updated all CSV column headers from `'Growth %'` style to `'Growth (HK$M)'` style across OverviewView, TemporalView, IndustryView, and GeographicView.

## Summary (review fixes for CR-008 and CR-009)

### CR-008: Align Country filter dropdown with filter logic
Changed `deriveFilterOptions` (filterOptions.ts) to derive country filter options from ISO country codes parsed from `CrossDimRow.countries` (comma-separated ISO 2-letter codes) instead of from `Object.keys(byGeo)` (geo region names like 'mainland'/'overseas'). The `_crossDim` parameter (previously unused) is now `crossDim` and used to extract country ISO codes; `byGeo` is renamed to `_byGeo` as it is no longer needed for option derivation. Updated `filterOptions.test.ts` to use proper geo region names in GeoData test fixtures (not ISO codes); added tests for whitespace trimming and null handling in country extraction. Updated `useDashboardData.test.ts` to expect ISO codes ('CN', 'US', 'HK') in country options.

Files:
- [mod] frontend/src/lib/filterOptions.ts
- [mod] frontend/src/lib/__tests__/filterOptions.test.ts
- [mod] frontend/src/lib/__tests__/useDashboardData.test.ts

### CR-009: Fix CrossDimView CSV null value representation
Created `frontend/src/lib/crossDimCsvUtils.ts` with `csvValueForCrossDim()` helper mirroring ScatterChart.getAxisValue() semantics: null on numeric keys (percentage, amount_hkd_million, total_net_proceeds) outputs '0'; null on categorical keys (enrichment tags) outputs 'N/A'. CrossDimView.tsx updated to use this helper for CSV row generation instead of the blanket `String(r[xKey] ?? 0)`.

Files:
- [new] frontend/src/lib/crossDimCsvUtils.ts
- [new] frontend/src/lib/__tests__/crossDimCsv.test.ts
- [mod] frontend/src/views/CrossDimView.tsx
