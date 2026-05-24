# Changes: Task-024

## Files
- [new] frontend/src/components/charts/SankeyChart.tsx
- [new] frontend/src/components/charts/StackedBarChart.tsx
- [new] frontend/src/components/charts/TimeSeriesChart.tsx
- [new] frontend/src/components/charts/HeatmapChart.tsx
- [new] frontend/src/components/charts/ScatterChart.tsx
- [new] frontend/src/lib/chartConstants.ts
- [new] frontend/src/components/__tests__/charts.test.tsx
- [mod] frontend/src/components/charts/SankeyChart.tsx
- [mod] frontend/src/components/charts/StackedBarChart.tsx
- [mod] frontend/src/components/charts/TimeSeriesChart.tsx
- [mod] frontend/src/components/charts/HeatmapChart.tsx
- [mod] frontend/src/components/charts/ScatterChart.tsx

## Summary
Initial implementation of all 5 chart components, followed by a review fix round addressing 7 code review issues:

- **CR-001:** Fixed StackedBarChart missing `xAxis.data` -- added industry name labels to x-axis.
- **CR-002:** Fixed ref forwarding by replacing `ref={ref as any}` with `useImperativeHandle` + `onChartReady` to expose the native ECharts instance (not the React component instance) through the forwarded ref. ExportButton's `getDataURL` call now works correctly.
- **CR-003:** Centralized parent categories and colors in `chartConstants.ts`; all chart components now import from this shared source.
- **CR-004:** Added 31 smoke/behavior tests across all 5 chart components, covering rendering, data transformation, ref forwarding, and edge cases (empty data, missing fields).
- **CR-005:** Removed all `as any` casts from data access paths. StackedBarChart uses a type guard (`hasParents`); TimeSeriesChart uses typed `keyof TimeSeriesPoint` access; ScatterChart uses a typed `toNumeric` helper.
- **CR-006:** Wrapped SankeyChart `handleClick` in `useCallback` and memoized `onEvents` object to prevent unnecessary event handler rebinding.
- **CR-007:** Spec-originating bug fixed in CR-001 by adding `xAxis.data` to the implementation despite the spec's omission.
- **CR-008:** Fixed test mock to capture `onEvents` prop from echarts-for-react, enabling proper SankeyChart click handler tests. Added two new test cases: verifies `onNodeClick` is called when a node is clicked with correct name, and verifies `onNodeClick` is NOT called when an edge (not a node) is clicked. The mock now exposes `capturedOnEvents` so tests can programmatically fire chart events.
