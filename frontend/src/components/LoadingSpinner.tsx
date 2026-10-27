import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  id?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = 'Loading...',
  size = 'md',
  id,
}) => {
  const spinnerSize = size === 'sm' ? 24 : size === 'lg' ? 56 : 40;

  return (
    <div className="loading-container" id={id} data-testid="loading-spinner">
      <div
        className="spinner"
        style={{ width: spinnerSize, height: spinnerSize }}
        aria-hidden="true"
      />
      {message && <p style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)' }}>{message}</p>}
    </div>
  );
};
