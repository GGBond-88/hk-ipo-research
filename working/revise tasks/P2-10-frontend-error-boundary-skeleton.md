# P2-10 -- Frontend ErrorBoundary + skeleton loading states

Status: done
Priority: P2
Effort: M (60-90 min)

## Goal
Wrap the React app in an `ErrorBoundary` that renders a friendly error UI, and replace `null`/blank states in data-fetching views with skeleton placeholders.

## Why
Today a thrown render error blanks the screen and a slow JSON fetch shows nothing. UX improvement only -- no data correctness impact. See revise_plan.md P2-10.

## Files touched
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Create: `frontend/src/components/SkeletonChart.tsx`, `SkeletonTable.tsx`
- Create: `frontend/src/components/__tests__/ErrorBoundary.test.tsx`
- Create: `frontend/src/components/__tests__/Skeleton.test.tsx`
- Modify: `frontend/src/App.tsx` (wrap routes in ErrorBoundary)
- Modify: `frontend/src/views/TemporalView.tsx` (skeleton on loading)
- Modify: `frontend/src/views/IndustryView.tsx` (skeleton on loading)
- Modify: `frontend/src/views/GeographicView.tsx` (skeleton on loading)
- Modify: `frontend/src/views/CrossDimView.tsx` (skeleton on loading)
- Modify: `frontend/src/views/OverviewView.tsx` (skeleton on loading)
- Modify: `frontend/src/views/CompanyView.tsx` (skeleton table on loading)

## What was changed

1. **ErrorBoundary.tsx** -- Class-based React error boundary. Logs error + componentStack via `componentDidCatch`. Renders `<div role="alert">` with error message, warning icon, and a Reload button that calls `window.location.reload()`.

2. **SkeletonChart.tsx** -- Pure CSS pulsing skeleton: title placeholder bar + large chart-area rectangle. Uses `@keyframes skeleton-pulse` for opacity animation. Has `role="status"` and `aria-label="Loading chart data"`.

3. **SkeletonTable.tsx** -- Pure CSS pulsing skeleton: header row + 6 staggered body rows mimicking a table. Uses same `skeleton-pulse` keyframes with staggered `animationDelay`. Has `role="status"` and `aria-label="Loading table data"`.

4. **App.tsx** -- Added `ErrorBoundary` import, wrapped `<ActiveComponent />` in `<ErrorBoundary>`.

5. **Views** -- Replaced all `<p>Loading...</p>` placeholders:
   - TemporalView, IndustryView, GeographicView, CrossDimView (useDashboardData views): now render `<SkeletonChart />` when loading.
   - OverviewView: now renders `<SkeletonChart />` when loading or !companies.
   - CompanyView: now renders `<SkeletonTable />` when loading and !companies.

## Test results
- `npm test -- --run`: 11 test files, 208 tests, all passed (0 failures).
- 10 new tests added: 5 ErrorBoundary tests + 5 SkeletonChart tests + 5 SkeletonTable tests = +15 tests total.
- 1 pre-existing unhandled error (CSP violation in ExportButton CR-011 test) -- unchanged, not a regression.
- `npm run build`: tsc compilation and vite build both succeed.

## Acceptance
- [x] Throwing inside any chart component shows the error UI, not a blank screen. (tested via ErrorBoundary test)
- [x] Loading any view shows a visible placeholder before data arrives. (6 views updated)
- [x] Vitest count grows by >= 2 (15 new tests added).
- [x] No regressions in existing tests. (207 pre-existing tests all pass)

## Dependencies
None.
