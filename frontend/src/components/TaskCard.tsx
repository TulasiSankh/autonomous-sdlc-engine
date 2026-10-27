import React from 'react';
import type { TaskRecord } from '../types/api';
import { StatusBadge } from './StatusBadge';

interface TaskCardProps {
  task: TaskRecord;
  onSelect: (taskId: string) => void;
  onReviewChanges?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, onSelect, onReviewChanges, onDelete }) => {
  const stepsCount = task.plan?.steps?.length || 0;
  const toolStepsCount = task.plan?.tool_steps?.length || 0;
  const filesToInspect = task.plan?.files_to_inspect?.length || 0;
  const hasProposal = Boolean(task.proposal);
  const proposedFilesCount = task.proposal?.files_to_change?.length || 0;
  const hasChangesApplied = task.status === 'changes_applied' || Boolean(task.workspace_id);
  const ACTION_TYPES = [
    'application_action',
    'browser_action',
    'filesystem_action',
    'composite_action',
    'command_action',
    'computer_task',
  ];
  const isActionIntent = ACTION_TYPES.includes(task.task_type || '');
  const isComputerTask = isActionIntent || toolStepsCount > 0;

  const getTaskTypeBadge = () => {
    switch (task.task_type) {
      case 'application_action':
        return { label: '🖥️ App Launch', cls: 'computer' };
      case 'browser_action':
        return { label: '🌐 Browser', cls: 'computer' };
      case 'filesystem_action':
        return { label: '📁 Filesystem', cls: 'computer' };
      case 'composite_action':
        return { label: '⚡ Composite', cls: 'computer' };
      case 'command_action':
        return { label: '💻 Command', cls: 'computer' };
      case 'unsupported':
        return { label: '⛔ Unsupported', cls: 'computer' };
      case 'computer_task':
        return { label: '⚡ Computer Task', cls: 'computer' };
      default:
        return isComputerTask
          ? { label: '⚡ Computer Task', cls: 'computer' }
          : { label: '🛠️ Code Change', cls: 'sdlc' };
    }
  };
  const badgeInfo = getTaskTypeBadge();

  const handleReviewClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onReviewChanges) {
      onReviewChanges(task.id);
    } else {
      onSelect(task.id);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete) {
      onDelete(task.id);
    }
  };

  return (
    <div
      className="card card-clickable task-card"
      onClick={() => onSelect(task.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onSelect(task.id);
      }}
      aria-label={`View task details for ${task.id}`}
      id={`task-card-${task.id}`}
      data-testid={`task-card-${task.id}`}
    >
      {/* Top Header Row */}
      <div className="task-card-header">
        <div className="task-card-id-row">
          <span className="task-id-tag">{task.id}</span>
          <span className={`task-type-tag ${badgeInfo.cls}`} title={badgeInfo.label}>
            {badgeInfo.label}
          </span>
          {task.workspace_id && (
            <span className="task-workspace-tag" title={`Workspace: ${task.workspace_id}`}>
              📦 {task.workspace_id.slice(0, 8)}...
            </span>
          )}
        </div>
        <StatusBadge status={task.status} size="sm" />
      </div>

      {/* Task Title */}
      <h3 className="task-card-title" title={task.task}>
        {task.task}
      </h3>

      {/* Execution Plan Summary */}
      {task.plan && (
        <div className="task-card-plan-summary">
          <span className="plan-summary-bullet">📐</span>
          <span className="plan-summary-text">
            {toolStepsCount > 0
              ? `${toolStepsCount} automated tool step${toolStepsCount > 1 ? 's' : ''}${task.plan.target_path ? ` • Target: ${task.plan.target_path}` : ''}`
              : stepsCount > 0
              ? `${stepsCount} execution step${stepsCount > 1 ? 's' : ''} • ${filesToInspect} file${filesToInspect === 1 ? '' : 's'} inspected`
              : task.plan.summary || 'Architecture plan drafted'}
          </span>
        </div>
      )}

      {/* Proposal & Workspace Status Row */}
      <div className="task-proposal-status-row">
        {isComputerTask ? (
          task.status === 'completed' ? (
            <span className="proposal-tag ready">
              ✅ Execution Verified
            </span>
          ) : task.status === 'failed' ? (
            <span className="proposal-tag failed">
              ❌ Execution Failed
            </span>
          ) : task.status === 'blocked' ? (
            <span className="proposal-tag blocked">
              ⚠️ Approval Required
            </span>
          ) : (
            <span className="proposal-tag pending">
              ⚡ Ready for Execution
            </span>
          )
        ) : hasProposal ? (
          <span className="proposal-tag ready">
            💡 Proposal Ready ({proposedFilesCount} file{proposedFilesCount === 1 ? '' : 's'})
          </span>
        ) : (
          <span className="proposal-tag pending">
            ⏳ Proposal Pending
          </span>
        )}

        {task.revision_count > 0 && (
          <span className="revision-tag">
            🔄 Revision {task.revision_count}/3
          </span>
        )}
      </div>

      {/* Card Footer: Metadata and Action Buttons */}
      <div className="task-card-footer">
        <div className="task-card-timestamp" title={`Created: ${task.created_at}`}>
          <span>🕒</span>
          <span>{formatDate(task.updated_at || task.created_at)}</span>
        </div>

        <div className="task-card-actions">
          {onDelete && (
            <button
              type="button"
              className="btn btn-outline-danger btn-xs task-delete-button"
              onClick={handleDeleteClick}
              title={`Delete task ${task.id}`}
              aria-label={`Delete task ${task.id}`}
              id={`delete-btn-${task.id}`}
            >
              🗑️ Delete
            </button>
          )}

          {(hasProposal || hasChangesApplied) && !isComputerTask && (
            <button
              type="button"
              className="btn btn-secondary btn-xs"
              onClick={handleReviewClick}
              title="Review proposed changes & diffs"
            >
              Review Changes
            </button>
          )}

          <button
            type="button"
            className="btn btn-primary btn-xs"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(task.id);
            }}
            title="View complete task details & pipeline"
          >
            View Details →
          </button>
        </div>
      </div>
    </div>
  );
};
