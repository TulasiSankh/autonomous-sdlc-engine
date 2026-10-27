import React from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  icon?: string;
  id?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionText,
  onAction,
  icon = '📂',
  id,
}) => {
  return (
    <div className="empty-state" id={id} data-testid="empty-state">
      <div className="empty-icon" aria-hidden="true">
        {icon}
      </div>
      <h3 className="empty-title">{title}</h3>
      <p className="empty-description">{description}</p>
      {actionText && onAction && (
        <button
          type="button"
          className="btn btn-primary"
          onClick={onAction}
          style={{ marginTop: '0.5rem' }}
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
