# Implement Review Results: Task-023

## Spec Review Issues

### SR-001: Hardcoded filter values replaced with data-derived logic (filterOptions.ts:27-30)
- Status: Resolved
- Description: The task spec (Step 1) explicitly hardcodes `parents` as `['Growth', 'Financing', 'Working Capital', 'Others']` and `commitments` as `['committed', 'discretionary']`. The implementation instead derives both from `crossDim` data: `parents` from `crossDim.map((r) => r.parent_category)` and `commitments` from `crossDim.map((r) => r.commitment)`. While deriving from data may produce a superset of the hardcoded values at runtime, it deviates from the spec in two ways: (a) empty or sparse `crossDim` data yields empty dropdowns where the spec guarantees all four parent categories and both commitment types are always present; (b) additional unexpected parent categories in the data (beyond the four canonical ones) would appear in the filter dropdown and may confuse downstream consumers that assume exactly four parent categories. The spec's hardcoded list acts as a stable, taxonomy-driven contract.
- Decision Reason: Reverted to spec-defined hardcoded values. Updated 8 tests to verify hardcoded parents=['Growth','Financing','Working Capital','Others'] and commitments=['committed','discretionary'] always present regardless of crossDim input. Renamed unused crossDim parameter to _crossDim.

## Code Review Issues

### CR-001: Unused parameters in `deriveFilterOptions` (filterOptions.ts:11-16)
- Status: Resolved
- Description: The function `deriveFilterOptions` declares two parameters (`crossDim: CrossDimRow[]` and `byIndustry: IndustryData`) that are never used in the function body. These are dead code that add noise to the API surface. If these parameters are intentionally included for future extensibility, there should be a comment explaining why. Otherwise, they should be removed, or `_`-prefixed (e.g., `_crossDim`) to signal they are intentionally unused.

### CR-002: Hardcoded parent categories and commitments bypass taxonomy (filterOptions.ts:27-28)
- Status: Resolved
- Description: The `parents` and `commitments` filter options are hardcoded as `['Growth', 'Financing', 'Working Capital', 'Others']` and `['committed', 'discretionary']`. The project has a `TaxonomyData` type (sharedTypes.ts:36-39) with `parent_order: string[]` that defines the taxonomy. If the taxonomy file is updated with new or renamed categories, this hardcoded list will become stale and the filter dropdowns will silently show incomplete or incorrect options. The parents should be derived from the taxonomy data, not hardcoded.

### CR-003: Empty `tickers` array renders broken ticker picker UI (FilterBar.tsx:123)
- Status: Resolved
- Description: The conditional `showTickerPicker && tickers && (...)` evaluates to true when `tickers` is an empty array `[]` (since `[]` is truthy in JavaScript). This renders the "Company:" label with an empty `<select>` dropdown containing only the placeholder option. The condition should be `showTickerPicker && tickers && tickers.length > 0` to avoid rendering a useless empty picker.

### CR-004: `handlePng` duplicates download logic instead of reusing `downloadBlob` (ExportButton.tsx:29-37 vs 172-180)
- Status: Resolved
- Description: The `downloadBlob` helper function (line 172-180) encapsulates the Blob/URL/anchor download pattern, but `handlePng` manually creates its own anchor element and sets href/download without using `downloadBlob`. This violates DRY and creates two different code paths for essentially the same operation (download a file). The duplication means any future improvements to `downloadBlob` (e.g., adding error handling, cleanup) will not apply to PNG export.

### CR-005: No unit tests for FilterBar.tsx (2 of 3 files now covered, but FilterBar.tsx still has zero tests)
- Status: Resolved
- Description: The implementer added tests for `filterOptions.ts` (17 tests) and `ExportButton.tsx` (13 tests for `toCsvContent` CSV helper), which is good progress. However, `FilterBar.tsx` still has zero tests -- there is no `FilterBar.test.tsx` file. The FilterBar component has meaningful behavior worth testing: 5 dropdowns each calling `setFilter`, the "Reset Filters" button calling `resetFilters`, the conditional ticker picker rendering (with the `tickers.length > 0` guard), and the `toSelectItems` helper. Without tests, regressions in filter wiring or rendering logic cannot be caught automatically.

### CR-006: Option map uses loose `Record<string, ...>` type instead of `FilterKey` keys (FilterBar.tsx:31,39)
- Status: Resolved
- Description: Both `optionMap` and `valueMap` were typed as `Record<string, string[]>` and `Record<string, string>` respectively, even though their keys are always `FilterKey` values (from `DIM_KEYS`). Using `Record<FilterKey, string[]>` and `Record<FilterKey, string>` would provide compile-time verification that all filter dimensions are covered and would eliminate the need for the `?? []` defensive fallback on line 56 (since TypeScript would guarantee the key exists). The loose typing silently accepted missing keys. Fixed: both maps now use `Record<FilterKey, ...>`.

### CR-007: Buttons missing explicit `type="button"` attribute (FilterBar.tsx:79-85, ExportButton.tsx:48-53,56-61)
- Status: Resolved
- Description: The `<button>` elements in both `FilterBar.tsx` (line 79, "Reset Filters") and `ExportButton.tsx` (lines 48 and 56, "Export PNG" and "Export CSV") lack an explicit `type="button"` attribute. Per HTML spec, a `<button>` without a `type` defaults to `type="submit"`. If either component is ever placed inside a `<form>` element (which is a reasonable use case, especially for FilterBar inside a dashboard form), clicking these buttons would trigger form submission and a page navigation/reload instead of just executing the onClick handler. Adding `type="button"` to all three `<button>` elements prevents this silent footgun.

### CR-008: ExportButton component has no component-level tests (ExportButton.test.ts)
- Status: Resolved
- Description: The test file `ExportButton.test.ts` only tests the exported `toCsvContent` utility function (13 tests). There are zero tests for the `ExportButton` component itself: rendering the PNG button, conditional rendering of the CSV button (present when `csvData` is provided, absent when not), verifying `type="button"` on both buttons, and validating the click handler behavior (PNG button calls `instance.getDataURL`, CSV button triggers download). This means the `triggerDownload` and `downloadBlob` private helpers have no test coverage at all, and the conditional `{csvData && (...)}` rendering logic in the JSX is untested. The FilterBar.test.tsx (20 tests) demonstrates that component-level testing with React Testing Library is feasible and already part of this project's testing infrastructure.
- Decision Reason: Added ExportButton.test.tsx with 15 component-level tests covering: PNG button rendering, CSV button conditional rendering (present/absent with csvData), both button type="button" attributes, PNG export getDataURL call with correct options, PNG download filename, null chartRef handling, CSV Blob content verification, CSV download filename, createObjectURL/revokeObjectURL lifecycle, flex layout. Uses mock ECharts ref and stubbed document.createElement for anchor interception.

### CR-009: `downloadBlob` missing explicit return type annotation (ExportButton.tsx:25)
- Status: Resolved
- Description: The `triggerDownload` helper on line 18 declares an explicit return type (`: void`), but the `downloadBlob` helper on line 25 omits its return type annotation. Both functions have the same return behavior (`void`), and this inconsistency reduces type safety and code clarity. Adding `: void` to `downloadBlob` would make the two functions stylistically consistent and would cause TypeScript to flag any accidental return value insertion in the future.
- Decision Reason: Added `: void` return type to `downloadBlob` matching `triggerDownload` style.

### CR-010: Insufficient filename sanitization in ExportButton (ExportButton.tsx:37,43)
- Status: Resolved
- Description: Both `handlePng` (line 37) and `handleCsv` (line 43) derive the download filename from `chartLabel` using only `chartLabel.replace(/\s+/g, '_')`, which replaces whitespace with underscores. Windows filenames additionally forbid the characters `\`, `/`, `:`, `*`, `?`, `"`, `<`, `>`, and `|`. If a chart has a label such as "Q1/Q2: Revenue Analysis" or "Cost<-->Benefit", the generated filename would be invalid on Windows and the download would silently fail (the browser may block the download or produce an unusable file). The sanitization regex should also strip or replace these additional forbidden characters to ensure cross-platform filename validity.
- Decision Reason: Extracted `sanitizeFilename` helper (exported) that first replaces `/\s+/g` with `_` then replaces `/[\\/:*?"<>|]/g` with `_`. Both `handlePng` and `handleCsv` now use `sanitizeFilename(chartLabel)` instead of bare `chartLabel.replace(/\s+/g, '_')`. Added 16 unit tests for `sanitizeFilename` (ExportButton.test.ts) covering all 10 Windows-forbidden characters, compound labels, edge cases (empty, whitespace-only), and 2 component-level tests (ExportButton.test.tsx) verifying PNG and CSV filenames with forbidden characters.

### CR-011: `downloadBlob` does not guarantee `URL.revokeObjectURL` cleanup on error (ExportButton.tsx:33-38)
- Status: Resolved
- Description: The `downloadBlob` function calls `URL.createObjectURL(blob)` then `triggerDownload(url, filename)` then `URL.revokeObjectURL(url)`. If `triggerDownload` throws an exception (e.g., a Content Security Policy violation from `a.click()`, or any unexpected runtime error), `URL.revokeObjectURL(url)` is never reached. This leaks the blob URL -- it remains allocated in the browser's blob URL store until the page is unloaded. For a dashboard that stays open for long sessions with frequent CSV exports, leaked blob URLs can accumulate and waste memory. The fix is to wrap the call in a try-finally so `revokeObjectURL` always executes.
- Decision Reason: Wrapped `triggerDownload(url, filename)` in try-finally so `URL.revokeObjectURL(url)` always executes. Added component-level test verifying `revokeObjectURL` is called even when `triggerDownload` throws (CSP violation simulation).

### CR-012: `toSelectItems` helper missing explicit return type (FilterBar.tsx:23-25)
- Status: Resolved
- Description: The `toSelectItems` function in `FilterBar.tsx` (line 23) has no explicit return type annotation. Every other function in the changed files has an explicit return type: `deriveFilterOptions(...): FilterOptions`, `toCsvContent(...): string`, `sanitizeFilename(...): string`, `triggerDownload(...): void`, `downloadBlob(...): void`. The implicit return type `{ value: string; label: string }[]` is inferable by TypeScript, but omitting the annotation is inconsistent with the codebase convention and reduces readability for other developers skimming the component. Adding an explicit return type `: { value: string; label: string }[]` (or extracting a named type) would make the function signature self-documenting and consistent.
- Decision Reason: Added explicit return type `: { value: string; label: string }[]` to `toSelectItems`, matching the codebase convention of explicit return types on all functions.
