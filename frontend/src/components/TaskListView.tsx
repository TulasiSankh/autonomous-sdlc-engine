import React from 'react';
import type { TaskRecord } from '../types/api';

interface TaskListViewProps {
  tasks: TaskRecord[];
  onSelectTask: (taskId: string) => void;
  onNavigateNewTask?: () => void;
  onDeleteTask?: (taskId: string) => void;
}

type TabType = 'all' | 'todo' | 'in_progress' | 'blocked' | 'completed';

function getRelativeTime(isoString: string): string {
  try {
    const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return 'recently';
  }
}

export const TaskListView: React.FC<TaskListViewProps> = ({ tasks, onSelectTask, onNavigateNewTask, onDeleteTask }) => {
  const [activeTab, setActiveTab] = React.useState<TabType>('all');

  // Compute counts
  const todoTasks = tasks.filter((t) => ['planned', 'queued', 'analyzing', 'planning'].includes((t.status || '').toLowerCase()));
  const inProgressTasks = tasks.filter((t) => ['in_progress', 'executing', 'proposed', 'changes_applied', 'verifying'].includes((t.status || '').toLowerCase()));
  const blockedTasks = tasks.filter((t) => ['blocked', 'verification_blocked', 'failed', 'verification_failed', 'verification_error'].includes((t.status || '').toLowerCase()));
  const completedTasks = tasks.filter((t) => ['completed', 'verified'].includes((t.status || '').toLowerCase()));

  const filteredTasks = React.useMemo(() => {
    switch (activeTab) {
      case 'todo':
        return todoTasks;
      case 'in_progress':
        return inProgressTasks;
      case 'blocked':
        return blockedTasks;
      case 'completed':
        return completedTasks;
      default:
        return tasks;
    }
  }, [tasks, activeTab, todoTasks, inProgressTasks, blockedTasks, completedTasks]);

  const getTaskIcon = (task: TaskRecord, idx: number) => {
    const s = (task.status || '').toLowerCase();
    if (s === 'completed' || s === 'verified') {
      return (
        <span className="task-type-circle completed">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </span>
      );
    }
    const icons = ['code', 'doc', 'shield', 'cloud', 'bolt'];
    const selected = icons[idx % icons.length];
    if (selected === 'code') {
      return (
        <span className="task-type-circle code">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="16 18 22 12 16 6"/>
            <polyline points="8 6 2 12 8 18"/>
          </svg>
        </span>
      );
    }
    if (selected === 'doc') {
      return (
        <span className="task-type-circle doc">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </span>
      );
    }
    if (selected === 'shield') {
      return (
        <span className="task-type-circle shield">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <polyline points="9 12 11 14 15 10"/>
          </svg>
        </span>
      );
    }
    return (
      <span className="task-type-circle cloud">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>
        </svg>
      </span>
    );
  };

  const getPriorityBadge = (idx: number) => {
    if (idx % 3 === 0) return <span className="task-priority-badge high">High</span>;
    if (idx % 3 === 1) return <span className="task-priority-badge medium">Medium</span>;
    return <span className="task-priority-badge low">Low</span>;
  };

  const getStatusPill = (statusStr: string) => {
    const s = (statusStr || '').toLowerCase();
    if (s === 'completed' || s === 'verified') {
      return <span className="task-table-status completed">Completed</span>;
    }
    if (['in_progress', 'executing', 'proposed', 'changes_applied', 'verifying'].includes(s)) {
      return <span className="task-table-status in-progress">In Progress</span>;
    }
    if (['blocked', 'failed', 'verification_blocked', 'verification_failed'].includes(s)) {
      return <span className="task-table-status blocked">Blocked</span>;
    }
    return <span className="task-table-status todo">To Do</span>;
  };

  return (
    <div className="task-list-card">
      <div className="task-list-header">
        <div className="task-list-title-group">
          <span className="task-list-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
              <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
              <path d="m9 14 2 2 4-4"/>
            </svg>
          </span>
          <h3 className="task-list-title">Your Tasks</h3>
        </div>

        <button
          type="button"
          className="task-list-view-all"
          onClick={onNavigateNewTask}
        >
          <span>View all</span>
          <span>→</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="task-tabs-row">
        <button
          type="button"
          className={`task-tab-pill ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => setActiveTab('all')}
        >
          All ({tasks.length})
        </button>
        <button
          type="button"
          className={`task-tab-pill ${activeTab === 'todo' ? 'active' : ''}`}
          onClick={() => setActiveTab('todo')}
        >
          To Do ({todoTasks.length})
        </button>
        <button
          type="button"
          className={`task-tab-pill ${activeTab === 'in_progress' ? 'active' : ''}`}
          onClick={() => setActiveTab('in_progress')}
        >
          In Progress ({inProgressTasks.length})
        </button>
        <button
          type="button"
          className={`task-tab-pill ${activeTab === 'blocked' ? 'active' : ''}`}
          onClick={() => setActiveTab('blocked')}
        >
          Blocked ({blockedTasks.length})
        </button>
        <button
          type="button"
          className={`task-tab-pill ${activeTab === 'completed' ? 'active' : ''}`}
          onClick={() => setActiveTab('completed')}
        >
          Completed ({completedTasks.length})
        </button>
      </div>

      {/* Task Rows List */}
      <div className="task-rows-container">
        {filteredTasks.length === 0 ? (
          <div className="task-rows-empty">
            <p>No tasks found in this view.</p>
          </div>
        ) : (
          filteredTasks.slice(0, 7).map((t, idx) => (
            <div
              key={t.id}
              className="task-row-item"
              onClick={() => onSelectTask(t.id)}
              role="button"
              tabIndex={0}
              id={`task-card-${t.id}`}
              data-testid={`task-card-${t.id}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onSelectTask(t.id);
              }}
            >
              <div className="task-row-left">
                {getTaskIcon(t, idx)}
                <div className="task-row-text">
                  <div className="task-row-title">{t.task}</div>
                  <div className="task-row-sub">
                    {t.plan?.summary || (t.proposal ? 'Implementation proposal ready' : 'Requirements analyzed')}
                  </div>
                </div>
              </div>

              <div className="task-row-right">
                {getPriorityBadge(idx)}
                <span className="task-row-time">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '4px' }}>
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                  </svg>
                  {getRelativeTime(t.updated_at || t.created_at)}
                </span>
                {getStatusPill(t.status)}
                {onDeleteTask && (
                  <button
                    type="button"
                    className="task-row-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteTask(t.id);
                    }}
                    title={`Delete task ${t.id}`}
                    aria-label={`Delete task ${t.id}`}
                    id={`delete-btn-${t.id}`}
                  >
                    🗑️
                  </button>
                )}
                <button
                  type="button"
                  className="task-row-menu-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectTask(t.id);
                  }}
                  title="More actions"
                >
                  ⋮
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
