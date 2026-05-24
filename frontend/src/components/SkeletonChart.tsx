/**
 * Pure CSS pulsing skeleton placeholder that mimics a chart area.
 * Used while dashboard data is loading so the user sees shape instead of blank.
 */
export function SkeletonChart() {
  return (
    <div
      role="status"
      aria-label="Loading chart data"
      data-testid="skeleton-chart"
      style={{
        width: '100%',
        minHeight: 320,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '0 0 24px',
      }}
    >
      {/* Title placeholder */}
      <div
        style={{
          width: '35%',
          height: 22,
          borderRadius: 4,
          background: '#e0e0e0',
          animation: 'skeleton-pulse 1.5s ease-in-out infinite',
        }}
      />
      {/* Chart area placeholder */}
      <div
        style={{
          width: '100%',
          height: 280,
          borderRadius: 8,
          background: '#f0f0f0',
          animation: 'skeleton-pulse 1.5s ease-in-out infinite',
        }}
      />
      <style>{skeletonKeyframes}</style>
    </div>
  );
}

const skeletonKeyframes = `
@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
`;
