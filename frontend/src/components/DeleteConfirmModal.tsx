import React from 'react';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  taskId: string;
  taskTitle: string;
  isDeleting: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  taskId,
  taskTitle,
  isDeleting,
  error,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDeleting) onCancel();
      }}
      data-testid="delete-confirm-modal"
    >
      <div className="modal-dialog delete-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="delete-modal-header">
          <div className="delete-warning-icon">🗑️</div>
          <div>
            <h3 id="delete-modal-title" className="delete-modal-heading">
              Delete Task
            </h3>
            <span className="task-id-tag">{taskId}</span>
          </div>
        </div>

        <div className="delete-modal-body">
          <p className="delete-modal-prompt">
            Are you sure you want to permanently delete this task?
          </p>
          <div className="delete-task-preview-box">
            <strong>"{taskTitle}"</strong>
          </div>
          <p className="delete-modal-note">
            ℹ️ This permanently removes the task record and execution history from Orbit AI.
            <strong> Your local files, folders, and original project directories will never be deleted.</strong>
          </p>

          {error && (
            <div className="alert alert-error delete-modal-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="delete-modal-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={isDeleting}
            id="cancel-delete-btn"
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={onConfirm}
            disabled={isDeleting}
            id="confirm-delete-btn"
          >
            {isDeleting ? 'Deleting...' : '🗑️ Delete Task'}
          </button>
        </div>
      </div>
    </div>
  );
};
