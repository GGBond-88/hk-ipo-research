# Changes: Task-021

## Files
- [new] frontend/package.json
- [new] frontend/vite.config.ts
- [new] frontend/tsconfig.json
- [new] frontend/tsconfig.node.json
- [new] frontend/index.html
- [new] frontend/src/main.tsx
- [new] frontend/src/App.tsx
- [new] frontend/src/vite-env.d.ts
- [new] tests/e2e/test_dashboard_dev_e2e.py
- [mod] .gitignore

## Summary
Scaffolded the frontend project with Vite + React + TypeScript + ECharts. Created all configuration files (package.json, vite.config.ts, tsconfig.json, tsconfig.node.json), entry point (index.html, main.tsx), and App.tsx with a tabbed layout placeholder for 6 views (Overview, Company, Temporal, Industry, Geographic, Cross-Dim). Dependencies installed: react 18.3.1, echarts 5.5.1, echarts-for-react 3.0.2, zustand 4.5.2, dayjs 1.11.13, and dev tooling (vite 5.4.0, typescript 5.5.3, @vitejs/plugin-react 4.3.1). Dev server starts on localhost, and production build produces dist/ with index.html and bundled JS assets.

Post-review fixes applied:
- CR-001: Added `node_modules/` to root `.gitignore` to prevent frontend dependencies from being committed.
- CR-002: Reverted -- tsconfig.json and tsconfig.node.json kept as prescribed by task specification. The `tsc -b` type-check gap for `vite.config.ts` is acceptable for a scaffold.
- CR-003: Reverted alongside CR-002. Composite build artifacts no longer produced. `*.tsbuildinfo` gitignore entry retained (tsc -b creates tsconfig.tsbuildinfo in all modes).
- SR-001: Reverted tsconfig.json and tsconfig.node.json to exact task spec content.
- SR-002: Removed extra `public/data/` directory not specified in the task.

Black-box testing added:
- Created `tests/e2e/test_dashboard_dev_e2e.py`: automated black-box test that starts the Vite dev server on a free port, curls the page via HTTP, and verifies the response contains the expected page title and React mount point. Covers the Step 9 requirement ("npm run dev starts without error").
