# Implement Review Results: Task-024

## Spec Review Issues

## Code Review Issues

### CR-001: StackedBarChart missing xAxis.data -- industry labels never displayed
- Status: Resolved
- Description: In StackedBarChart.tsx:19-23, `xAxis` is configured as `type: 'category'` but has no `data` property. The `entries` variable (line 14) captures industry names from `Object.entries(data)` keys, but those keys are never bound to `xAxis.data`. ECharts with `type: 'category'` and no explicit `data` falls back to index positions (0, 1, 2...) as category labels, so the x-axis will display numeric indices instead of actual industry names. The fix is to add `data: entries.map(([k]) => k)` to the `xAxis` config. This bug originates in the task specification (task.md line 114-119), which also omits the `data` property.
- Decision Reason:

### CR-002: Ref forwarding broken at runtime -- EChartsReact component instance has no getDataURL
- Status: Resolved
- Description: All 5 chart components use `forwardRef<EChartsType, Props>` and pass `ref={ref as any}` to `ReactEChartsCore` (which is the default export of `echarts-for-react`, a class-based `PureComponent`). However, `EChartsReactCore` (verified in `node_modules/echarts-for-react/lib/core.js` and `esm/core.d.ts`) does NOT have a `getDataURL` method -- `getDataURL` exists only on the native ECharts instance accessible via `getEchartsInstance()`. The ExportButton component calls `chartRef.current.getDataURL(...)` directly. At runtime, clicking "Export PNG" with these chart components will throw `TypeError: ref.current.getDataURL is not a function` because the forwarded ref yields the React component instance, not the native ECharts instance. The correct approach requires either calling `getEchartsInstance()` on the component ref, capturing the instance via `onChartReady` and forwarding via `useImperativeHandle`, or using a wrapper. The `as any` cast masks this problem from TypeScript but does not fix it. This affects all 5 files (SankeyChart.tsx:54, StackedBarChart.tsx:39, TimeSeriesChart.tsx:33, HeatmapChart.tsx:53, ScatterChart.tsx:46).
- Decision Reason:

### CR-003: Parent category strings duplicated across 5+ files
- Status: Resolved
- Description: The parent category array `['Growth', 'Financing', 'Working Capital', 'Others']` is hardcoded in StackedBarChart.tsx:13, TimeSeriesChart.tsx:12, and HeatmapChart.tsx:12. The same categories also appear as `PARENT_COLORS` keys in SankeyChart.tsx:11-16 and as optional fields in `sharedTypes.ts` (`TimeSeriesPoint` lines 43-47). Any change to the taxonomy (e.g., adding a 5th parent category) requires updating 5+ files spread across types and components, creating a high risk of inconsistency. These should be centralized in a single shared constant (e.g., derived from `TaxonomyData.parent_order` or a dedicated constants file), and the chart components should reference that shared source.
- Decision Reason:

### CR-004: Zero test coverage for 5 chart components
- Status: Resolved
- Description: There are no unit tests, integration tests, or e2e tests for any of the 5 chart components (SankeyChart, StackedBarChart, TimeSeriesChart, HeatmapChart, ScatterChart). The task's Step 6 only verifies the TypeScript build passes, which checks type correctness but does not exercise the rendering logic, data transformations, event handlers, or edge cases. Even basic smoke tests (renders without crashing with valid data, renders gracefully with empty data, passes correct option to echarts-for-react) are absent. The CR-001 and CR-002 bugs would have been caught by even minimal rendering tests. The `frontend/src/components/__tests__/` directory has no chart-related test files.
- Decision Reason:

### CR-005: Widespread use of `as any` defeats strict TypeScript
- Status: Resolved
- Description: The tsconfig has `"strict": true`, but multiple `as any` casts in the chart components bypass all type checking:
  - SankeyChart.tsx:54 -- `ref={ref as any}` (see CR-002)
  - StackedBarChart.tsx:31 -- `(v as any).parents` for data access
  - StackedBarChart.tsx:39 -- `ref={ref as any}`
  - TimeSeriesChart.tsx:27 -- `(d as any)[p]` instead of typed index access like `d[p as keyof TimeSeriesPoint]`
  - TimeSeriesChart.tsx:33 -- `ref={ref as any}`
  - HeatmapChart.tsx:53 -- `ref={ref as any}`
  - ScatterChart.tsx:36-37 -- `(r as any)[xKey]` and `(r as any)[yKey]` even though `xKey`/`yKey` are typed as `keyof CrossDimRow`; TypeScript should accept `r[xKey]` directly without the cast
  - ScatterChart.tsx:46 -- `ref={ref as any}`
  
  While the ref casting is driven by a design mismatch (CR-002), the data access casts in StackedBarChart, TimeSeriesChart, and ScatterChart are avoidable with proper typed access patterns. These casts silently swallow type errors that could catch real bugs.
- Decision Reason:

### CR-006: SankeyChart handleClick recreated on every render
- Status: Resolved
- Description: In SankeyChart.tsx:46-49, `handleClick` is a plain function defined inside the component body. It is passed via `onEvents={{ click: handleClick }}` on line 58. The `onEvents` object is also an inline object literal, creating new references every render. Looking at `EChartsReactCore.componentDidUpdate` (core.js:46-49), when `onEvents` changes reference, echarts-for-react unbinds all existing event handlers and rebinds them. This means every render of SankeyChart causes unnecessary event handler rebinding on the ECharts instance. The fix is to wrap `handleClick` in `useCallback` and memoize the `onEvents` object (or extract `onEvents` to a `useMemo`).
- Decision Reason:

### CR-007: Task specification faithfully copies bug -- xAxis.data omission in StackedBarChart spec
- Status: Resolved
- Description: The task specification (task.md step 2, lines 114-119) contains the same missing `xAxis.data` property bug that appears in the implementation (see CR-001). The spec provides an explicit code snippet that omits the `data` field from the xAxis config while computing `entries` keys from the data. This means the bug was introduced during task planning, not during implementation. The implementer faithfully reproduced the spec code, but the code snippet itself is incorrect.
- Decision Reason:

### CR-008: Test mock does not capture onEvents prop -- SankeyChart click interaction is untestable
- Status: Resolved
- Description: The echarts-for-react mock in charts.test.tsx:29-34 captures `props.option` and `props.onChartReady` but never stores `props.onEvents` (even though the `MockEChartsCoreProps` interface at line 13 declares it). The test "calls onNodeClick when a node is clicked" at line 178-187 has a misleading name: it assigns `capturedOption` (the ECharts option object) to a variable named `onEvents` on line 182, never fires a click event, and its only assertion (`expect(onNodeClick).not.toHaveBeenCalled()`) is trivially true because nothing in the mock ever invokes event handlers. This means the SankeyChart click-handler behavior (the `useCallback`-wrapped `handleClick` and `useMemo`-wrapped `onEvents`, which were the subject of CR-006) is completely untested. The mock should capture `onEvents` into a module-level variable and expose it so tests can programmatically fire events (e.g., `capturedOnEvents.click?.({ dataType: 'node', name: 'Growth' })`), allowing verification of the entire click-handler chain.
- Decision Reason:
