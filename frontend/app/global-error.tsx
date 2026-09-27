'use client';

// Root-level fatal fallback. Must render <html>/<body> and use inline styles
// only — if the layout itself crashed, theme CSS can't be trusted.
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f7f3ed',
          color: '#2a2520',
          fontFamily: 'system-ui, -apple-system, sans-serif',
        }}
      >
        <div style={{ textAlign: 'center', padding: '2rem', maxWidth: '24rem' }}>
          <div
            style={{
              fontSize: '2rem',
              marginBottom: '1rem',
            }}
            aria-hidden
          >
            ⚠
          </div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: '0 0 0.5rem' }}>
            Something went wrong
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#6b645c', margin: '0 0 1.5rem' }}>
            An unexpected error occurred. Please try again.
          </p>
          <button
            onClick={reset}
            style={{
              padding: '0.5rem 1.25rem',
              fontSize: '0.875rem',
              border: '1px solid #c44536',
              borderRadius: '0.5rem',
              background: 'transparent',
              color: '#c44536',
              cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      </body>
    </html>
  );
}
