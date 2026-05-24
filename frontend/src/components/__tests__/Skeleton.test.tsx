import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SkeletonChart } from '../SkeletonChart';
import { SkeletonTable } from '../SkeletonTable';

describe('SkeletonChart', () => {
  it('renders without crashing', () => {
    const { container } = render(<SkeletonChart />);
    expect(container).toBeDefined();
  });

  it('has role="status" for accessibility', () => {
    render(<SkeletonChart />);
    expect(screen.getByRole('status')).toBeDefined();
  });

  it('has aria-label for screen readers', () => {
    render(<SkeletonChart />);
    const el = screen.getByRole('status');
    expect(el.getAttribute('aria-label')).toBe('Loading chart data');
  });

  it('has data-testid for querying', () => {
    render(<SkeletonChart />);
    expect(screen.getByTestId('skeleton-chart')).toBeDefined();
  });

  it('renders keyframes style tag', () => {
    const { container } = render(<SkeletonChart />);
    const styleTag = container.querySelector('style');
    expect(styleTag).not.toBeNull();
    expect(styleTag!.textContent).toContain('skeleton-pulse');
  });
});

describe('SkeletonTable', () => {
  it('renders without crashing', () => {
    const { container } = render(<SkeletonTable />);
    expect(container).toBeDefined();
  });

  it('has role="status" for accessibility', () => {
    render(<SkeletonTable />);
    expect(screen.getByRole('status')).toBeDefined();
  });

  it('has aria-label for screen readers', () => {
    render(<SkeletonTable />);
    const el = screen.getByRole('status');
    expect(el.getAttribute('aria-label')).toBe('Loading table data');
  });

  it('has data-testid for querying', () => {
    render(<SkeletonTable />);
    expect(screen.getByTestId('skeleton-table')).toBeDefined();
  });

  it('renders a header row area plus body rows', () => {
    const { container } = render(<SkeletonTable />);
    // Should have at least 7 child divs inside the root: 1 header + 6 body rows
    const rootDiv = container.firstChild as HTMLElement;
    expect(rootDiv.children.length).toBeGreaterThanOrEqual(7);
  });

  it('renders keyframes style tag', () => {
    const { container } = render(<SkeletonTable />);
    const styleTag = container.querySelector('style');
    expect(styleTag).not.toBeNull();
    expect(styleTag!.textContent).toContain('skeleton-pulse');
  });
});
