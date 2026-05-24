import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] caught render error:', error, errorInfo.componentStack);
  }

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 300,
            padding: 32,
            textAlign: 'center',
            fontFamily: 'system-ui, sans-serif',
          }}
        >
          <div
            style={{
              fontSize: 48,
              marginBottom: 16,
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: '#ffebee',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#d32f2f',
            }}
          >
            !
          </div>
          <h2 style={{ margin: '0 0 8px', color: '#333' }}>Something went wrong</h2>
          <p style={{ color: '#666', maxWidth: 480, margin: '0 0 24px' }}>
            An unexpected error occurred while rendering this view.
            {this.state.error?.message && (
              <span style={{ display: 'block', marginTop: 8, fontSize: 13, color: '#999' }}>
                {this.state.error.message}
              </span>
            )}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              padding: '10px 24px',
              fontSize: 15,
              fontWeight: 600,
              background: '#1a73e8',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </div>
      );
    }

    return this.props.children;
  }

  override componentDidUpdate(
    _prevProps: ErrorBoundaryProps,
    prevState: ErrorBoundaryState,
  ): void {
    // Reset error state if children change so a navigation can recover.
    if (prevState.hasError && !this.state.hasError) {
      /* explicitly cleared via reload */
    }
  }
}
