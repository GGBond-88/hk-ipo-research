/**
 * Pure CSS pulsing skeleton placeholder that mimics a table / list.
 * Used while company-list or tabular data is loading.
 */
export function SkeletonTable() {
  return (
    <div
      role="status"
      aria-label="Loading table data"
      data-testid="skeleton-table"
      style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '0 0 24px',
      }}
    >
      {/* Header row */}
      <div
        style={{
          width: '100%',
          height: 36,
          borderRadius: 4,
          background: '#e8e8e8',
          animation: 'skeleton-pulse 1.5s ease-in-out infinite',
        }}
      />
      {/* Body rows */}
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          style={{
            width: `${90 - i * 7}%`,
            height: 28,
            borderRadius: 4,
            background: '#f0f0f0',
            animation: 'skeleton-pulse 1.5s ease-in-out infinite',
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
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
