import React from 'react';

interface ErrorBannerProps {
  message: string;
  detail?: string;
  onRetry?: () => void;
  id?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  detail,
  onRetry,
  id,
}) => {
  return (
    <div className="alert-banner error" id={id} role="alert" data-testid="error-banner">
      <span style={{ fontSize: '1.25rem' }} aria-hidden="true">
        ⚠️
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, color: '#fca5a5' }}>{message}</div>
        {detail && (
          <div
            style={{
              fontSize: '0.8125rem',
              color: '#f87171',
              marginTop: '0.35rem',
              fontFamily: 'var(--font-mono)',
              wordBreak: 'break-word',
            }}
          >
            {detail}
          </div>
        )}
      </div>
      {onRetry && (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={onRetry}
          style={{ alignSelf: 'center', borderColor: 'rgba(239, 68, 68, 0.4)' }}
        >
          Retry
        </button>
      )}
    </div>
  );
};
