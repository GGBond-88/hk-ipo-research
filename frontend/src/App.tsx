import { useState } from 'react';
import { useStore } from './lib/store';
import { ErrorBoundary } from './components/ErrorBoundary';
import { OverviewView } from './views/OverviewView';
import { CompanyView } from './views/CompanyView';
import { TemporalView } from './views/TemporalView';
import { IndustryView } from './views/IndustryView';
import { GeographicView } from './views/GeographicView';
import { CrossDimView } from './views/CrossDimView';

const VIEWS = [
  { key: 'overview', label: 'Overview', component: OverviewView },
  { key: 'company', label: 'Company', component: CompanyView },
  { key: 'temporal', label: 'Temporal', component: TemporalView },
  { key: 'industry', label: 'Industry', component: IndustryView },
  { key: 'geo', label: 'Geographic', component: GeographicView },
  { key: 'cross', label: 'Cross-Dim', component: CrossDimView },
] as const;

type ViewKey = (typeof VIEWS)[number]['key'];

function App() {
  const [view, setView] = useState<ViewKey>('overview');
  const activeTicker = useStore((s) => s.activeTicker);
  const ActiveComponent = VIEWS.find((v) => v.key === view)!.component;

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1400, margin: '0 auto', padding: 16 }}>
      <h1 style={{ marginBottom: 4 }}>HK IPO Use-of-Proceeds Dashboard</h1>
      {activeTicker && (
        <p style={{ color: '#666', margin: 0 }}>
          Active company: <strong>{activeTicker}</strong>
        </p>
      )}
      <nav style={{ display: 'flex', gap: 4, marginBottom: 24, marginTop: 8 }}>
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
        <ErrorBoundary>
          <ActiveComponent />
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default App;
