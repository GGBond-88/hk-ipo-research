# Task 021: Frontend scaffold — Vite + React + TypeScript + ECharts

## Project Overview

- **Goal:** Build the React dashboard that reads pre-baked JSON from `public/data/` and renders 6 views with interactive ECharts charts.
- **Architecture:** Vite + React + TypeScript + ECharts (echarts-for-react) + Zustand + dayjs. Static build; no backend.
- **Tech Stack:** Node.js >= 18, npm, Vite, React 18+, TypeScript 5+, ECharts 5, Zustand 4, dayjs.

## Task Objective

Scaffold the frontend project: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `main.tsx`, and `App.tsx` with a tabbed layout placeholder for 6 views. No visual testing yet -- just verify `npm run dev` starts without error.

This is Task 21 of 27.

---

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "hk-ipo-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "dayjs": "^1.11.13",
    "echarts": "^5.5.1",
    "echarts-for-react": "^3.0.2",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "zustand": "^4.5.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.3",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
});
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>HK IPO Use-of-Proceeds Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/vite-env.d.ts`**

```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 7: Create `frontend/src/main.tsx`**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 8: Create `frontend/src/App.tsx` (placeholder with tabs)**

```tsx
import { useState } from 'react';

const VIEWS = [
  { key: 'overview', label: 'Overview' },
  { key: 'company', label: 'Company' },
  { key: 'temporal', label: 'Temporal' },
  { key: 'industry', label: 'Industry' },
  { key: 'geo', label: 'Geographic' },
  { key: 'cross', label: 'Cross-Dim' },
] as const;

type ViewKey = (typeof VIEWS)[number]['key'];

function App() {
  const [view, setView] = useState<ViewKey>('overview');

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1400, margin: '0 auto', padding: 16 }}>
      <h1>HK IPO Use-of-Proceeds Dashboard</h1>
      <nav style={{ display: 'flex', gap: 4, marginBottom: 24 }}>
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            style={{
              padding: '8px 16px',
              background: view === v.key ? '#1a73e8' : '#f0f0f0',
              color: view === v.key ? '#fff' : '#333',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontWeight: view === v.key ? 600 : 400,
            }}
          >
            {v.label}
          </button>
        ))}
      </nav>
      <main>
        <p>Selected view: {view}</p>
        <p>Data will be loaded from public/data/ once the data client is wired in.</p>
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 9: Install dependencies and verify dev server starts**

Run:
```bash
cd frontend
npm install
npm run dev
```

Expected: Dev server starts on `localhost:5173`. No console errors. Kill it after verifying (Ctrl+C).

- [ ] **Step 10: Verify `npm run build` works**

Run:
```bash
cd frontend
npm run build
```

Expected: `dist/` directory produced containing `index.html` and `assets/` with JS files. No TypeScript errors.
