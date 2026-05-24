# Implement Review Results: Task-022

## Spec Review Issues

## Code Review Issues

### CR-001: Unweighted percentage aggregation produces incorrect cross-company aggregates
- Status: Resolved
- Description: All three aggregation functions (aggregateTimeSeries, aggregateByIndustry, aggregateByGeo) sum raw `percentage` values from CrossDimRow without weighting by monetary amount. A 50% allocation from a 10M HKD IPO contributes identically to a 50% allocation from a 10,000M HKD IPO. This produces mathematically misleading aggregates for cross-company analysis. Note: aggregateByGeo correctly tracks `total_hkd_million` using `amount_hkd_million`, but the `parents` breakdown inconsistently uses raw percentages -- creating internal inconsistency within the same function.
- Decision Reason:

### CR-002: Country filter fails when countries field contains whitespace after commas
- Status: Resolved
- Description: In filterCrossDim (filterUtils.ts:17), `row.countries.split(',').includes(filters.country)` does not trim whitespace from each token. If the data source has spaces after commas (common CSV convention, e.g. "CN, HK, US"), `split(',')` produces `["CN", " HK", " US"]` and `includes("HK")` returns `false` when it should return `true`. This is a correctness bug that silently drops matching rows.
- Decision Reason:

### CR-003: Dead code -- unused `industries` Set in aggregateByIndustry
- Status: Resolved
- Description: In aggregateByIndustry (filterUtils.ts:46,49), a `Set<string>` named `industries` is allocated and populated via `industries.add(ind)` on every row iteration, but the Set is never read anywhere. This dead code wastes memory allocations and indicates incomplete cleanup.
- Decision Reason:

### CR-004: No unit tests for filterUtils.ts business logic
- Status: Resolved
- Description: filterUtils.ts exports four functions (filterCrossDim, aggregateTimeSeries, aggregateByIndustry, aggregateByGeo) that contain the most significant business logic in this task. These are pure functions with multiple edge cases (empty row arrays, null listing_date, null industry/geo/countries, mixed null/real values) but have zero test coverage. Multiple dashboard views will consume these functions -- undetected bugs here cascade into every chart.
- Decision Reason:
