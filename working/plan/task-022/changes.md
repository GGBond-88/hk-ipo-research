# Changes: Task-022

## Files
- [new] frontend/src/lib/sharedTypes.ts
- [new] frontend/src/lib/dataClient.ts
- [new] frontend/src/lib/store.ts
- [new] frontend/src/lib/filterUtils.ts
- [new] frontend/src/lib/__tests__/filterUtils.test.ts
- [mod] frontend/src/App.tsx
- [mod] frontend/package.json
- [mod] frontend/vite.config.ts

## Summary
Implemented frontend data layer: shared TypeScript types for all pre-baked JSON shapes, a caching data client (fetchJSON + individual fetch functions for manifest, companies, taxonomy, time series, by-industry, by-geo, cross-dim, and per-ticker sankey data), a Zustand store with filter state (year, industry, country, parent, commitment) and active ticker, and filter utility functions (filterCrossDim, aggregateTimeSeries, aggregateByIndustry, aggregateByGeo). Wired the Zustand store into App.tsx.

Fixed 4 code review issues:
- CR-001: Changed all three aggregation functions to use `amount_hkd_million` instead of raw `percentage` so large IPOs carry proportionally more weight.
- CR-002: Added `.map(s => s.trim())` after `split(',')` in country filter so whitespace after commas does not cause false negatives.
- CR-003: Removed unused `industries` Set from `aggregateByIndustry`.
- CR-004: Added 33 vitest unit tests covering all 4 filterUtils functions (empty inputs, basic aggregation, edge cases, CR-specific scenarios). Added vitest dev dependency, test script, and vitest config in vite.config.ts.
