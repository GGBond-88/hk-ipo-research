import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '../ErrorBoundary';

/**
 * Component that throws when told to, for testing the ErrorBoundary.
 */
function ThrowOnPurpose({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test explosion');
  }
  return <p>All good</p>;
}

// Keep a reference to the original window.location for cleanup.
const originalLocation = window.location;

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress expected console.error from the deliberate throw during tests.
    vi.spyOn(console, 'error').mockImplementation(() => {});
    // Mock window.location.reload so we don't actually reload.
    vi.stubGlobal('location', { reload: vi.fn() });
    vi.clearAllMocks();
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <ThrowOnPurpose shouldThrow={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText('All good')).toBeDefined();
  });

  it('renders error UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowOnPurpose shouldThrow />
      </ErrorBoundary>,
    );
    // The error UI has role="alert" and the heading "Something went wrong".
    expect(screen.getByRole('alert')).toBeDefined();
    expect(screen.getByText('Something went wrong')).toBeDefined();
  });

  it('renders the error message inside the alert', () => {
    render(
      <ErrorBoundary>
        <ThrowOnPurpose shouldThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Test explosion')).toBeDefined();
  });

  it('renders a Reload button that calls window.location.reload', () => {
    render(
      <ErrorBoundary>
        <ThrowOnPurpose shouldThrow />
      </ErrorBoundary>,
    );
    const reloadBtn = screen.getByText('Reload');
    expect(reloadBtn).toBeDefined();

    reloadBtn.click();
    expect(window.location.reload).toHaveBeenCalledTimes(1);
  });

  it('calls console.error from componentDidCatch', () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowOnPurpose shouldThrow />
      </ErrorBoundary>,
    );

    // console.error should have been called by componentDidCatch.
    // React 18 also logs error-boundary mount info to console.error, so check all calls.
    expect(consoleErrorSpy).toHaveBeenCalled();
    const allCalls = consoleErrorSpy.mock.calls.flatMap((c) => c);
    const found = allCalls.some(
      (arg) => typeof arg === 'string' && arg.includes('[ErrorBoundary] caught render error:'),
    );
    expect(found).toBe(true);

    consoleErrorSpy.mockRestore();
  });
});
