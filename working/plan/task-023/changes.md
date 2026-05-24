# Changes: Task-023

## Files
- [new] frontend/src/lib/filterOptions.ts
- [new] frontend/src/components/FilterBar.tsx
- [new] frontend/src/components/ExportButton.tsx
- [new] frontend/src/lib/__tests__/filterOptions.test.ts
- [new] frontend/src/components/__tests__/ExportButton.test.ts
- [new] frontend/src/components/__tests__/ExportButton.test.tsx
- [new] frontend/src/components/__tests__/FilterBar.test.tsx
- [mod] frontend/vite.config.ts
- [new] frontend/src/test-setup.ts

## Summary
Implemented FilterBar component (5 dropdowns wired to Zustand store with reset button and optional ticker picker), ExportButton component (PNG + CSV export via ECharts instance ref with shared download helper), and filterOptions utility (spec-hardcoded parent and commitment filter values).

Review fixes applied:
- SR-001: Reverted parents and commitments to spec-hardcoded values. Updated 8 filterOptions tests.
- CR-001/CR-002: Derive parents and commitments from crossDim data instead of hardcoding (later reverted per SR-001)
- CR-003: Fix empty tickers array rendering broken picker (add length > 0 check)
- CR-004: Extract shared triggerDownload helper, eliminate DRY violation in handlePng
- CR-005: Add 30 unit tests (17 for filterOptions, 13 for ExportButton CSV helpers, 20 for FilterBar)
- CR-006: Strengthen optionMap/valueMap types to Record<FilterKey, ...> and remove defensive ?? [] fallback
- CR-007: Add explicit type="button" to all 3 button elements in FilterBar and ExportButton
- CR-008: Add 15 ExportButton component-level tests (ExportButton.test.tsx) covering rendering, button types, PNG export, CSV export, download lifecycle, and layout
- CR-009: Add explicit : void return type to downloadBlob helper
- CR-010: Extract sanitizeFilename helper replacing whitespace + Windows-forbidden chars (\/:*?"<>|) with underscores; update handlePng/handleCsv to use it; add 18 tests (16 unit + 2 component)
- CR-011: Wrap triggerDownload() in downloadBlob() with try-finally to guarantee URL.revokeObjectURL() cleanup on error; add component test verifying revokeObjectURL called even on CSP violation throw
- CR-012: Add explicit return type { value: string; label: string }[] to toSelectItems() helper for codebase consistency

Infrastructure:
- Installed @testing-library/react, @testing-library/jest-dom, jsdom for component testing
- Updated vite.config.ts test environment from 'node' to 'jsdom'
- Added test-setup.ts for @testing-library/jest-dom matchers

Tests: 5 test files, 120 tests, all passing. Build: tsc -b + vite build, zero TypeScript errors.
