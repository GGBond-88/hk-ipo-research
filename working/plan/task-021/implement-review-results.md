# Implement Review Results: Task-021

## Spec Review Issues

### SR-001: tsconfig.json and tsconfig.node.json content deviates from task specification
- Status: Resolved
- Description: The task specification prescribes exact JSON content for tsconfig.json and tsconfig.node.json. The implemented files differ:
  - tsconfig.json: Added `"references": [{ "path": "./tsconfig.node.json" }]` not in the spec (line 21).
  - tsconfig.node.json: Removed `"noEmit": true` and `"allowImportingTsExtensions": true` that were in the spec. Added `"composite": true` and `"declaration": true` (lines 11-12) not in the spec.
  These changes were introduced by the CR-002 fix to wire `vite.config.ts` type-checking into `tsc -b`. While functionally correct, the file content no longer matches the task specification's prescribed content. The spec should be updated to reflect the corrected configuration, or the approach should be reverted to match the spec as-written.
- Decision Reason: Reverted tsconfig.json and tsconfig.node.json to exact task specification content. The composite/project-references approach added complexity and build-artifact overhead inappropriate for a scaffold task. The spec-prescribed build script `tsc -b && vite build` succeeds with the task-specified configs.

### SR-002: Extra `public/data/` directory not specified in the task
- Status: Resolved
- Description: The task specification lists exactly 8 files to create. The implementation includes an extra `frontend/public/data/` directory with `.gitkeep` placeholder files (`public/data/.gitkeep`, `public/data/sankey/.gitkeep`). These are not mentioned in the task's file list or in the changes.md summary. While these may be preparation for future tasks, they are beyond the scope of Task 021's scaffold. Either remove them or document them as intentional additions in changes.md.
- Decision Reason: Removed the `public/data/` directory and its contents. It was not specified in the task scope and was beyond the scaffold phase. Future tasks will handle data directory creation when needed.

## Code Review Issues

### CR-001: Missing `node_modules/` in `.gitignore` -- frontend dependencies at risk of being committed
- Status: Resolved
- Description: The root `.gitignore` contains `dist/` but has no `node_modules/` pattern. The `frontend/` directory includes a `node_modules/` tree (hundreds of files from `npm install`). Running `git add frontend/` or `git add -A` would stage these into the repository. A `node_modules/` entry must be added to `.gitignore` (or `frontend/.gitignore`) before the frontend directory is first committed.
- Decision Reason:

### CR-002: `tsconfig.json` missing project `references` to `tsconfig.node.json` -- dead config file and unchecked `vite.config.ts`
- Status: Resolved
- Description: The `build` script (`tsc -b && vite build`) uses `tsc -b` (project-build mode), but `tsconfig.json` has no `"references": [{ "path": "./tsconfig.node.json" }]`. Without a `references` entry, `tsc -b` only type-checks files covered by `tsconfig.json` (`include: ["src"]`). The separate `tsconfig.node.json` (which covers `vite.config.ts`) is never consumed, so `vite.config.ts` is never type-checked by the build script. Add `"references": [{ "path": "./tsconfig.node.json" }]` to `tsconfig.json` to wire the two configs together so `tsc -b` type-checks both `src/` and `vite.config.ts`.
- Decision Reason:

### CR-003: Composite `tsc -b` emits generated build artifacts that are not gitignored
- Status: Resolved
- Description: The CR-002 fix added `"composite": true` and `"declaration": true` to `frontend/tsconfig.node.json` and removed `"noEmit": true` (required for composite mode). This causes `tsc -b` to emit generated files alongside the source in `frontend/`: `vite.config.d.ts`, `vite.config.js`, `tsconfig.node.tsbuildinfo`, and `tsconfig.tsbuildinfo`. None of these are covered by `.gitignore`. When the `frontend/` directory is committed, these build artifacts will be accidentally staged. For a Vite-bundled project, emitting `.js` and `.d.ts` from `vite.config.ts` is both unnecessary and polluting -- Vite handles all bundling. Fix options: (a) add `*.tsbuildinfo` and specific artifact patterns to `.gitignore`, or (b) restructure the composite config with `"declarationDir"` pointing to a gitignored directory, or (c) replace the composite approach with a non-composite `tsc --noEmit` check for `tsconfig.node.json` so the build script reads `tsc -b && tsc --noEmit -p tsconfig.node.json && vite build`. The simplest fix for a scaffold is option (a): `gitignore` the generated artifacts.
- Decision Reason:
