import React from 'react';
import type { TaskRecord } from '../types/api';

interface RightDashboardWidgetsProps {
  tasks: TaskRecord[];
  isAgentOnline?: boolean;
  onSelectTask?: (taskId: string) => void;
  onOpenAgentModal?: () => void;
}

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

export const RightDashboardWidgets: React.FC<RightDashboardWidgetsProps> = ({
  tasks,
  isAgentOnline = true,
  onSelectTask,
  onOpenAgentModal,
}) => {
  return (
    <div className="right-widgets-col">
      {/* 1. System Status Widget */}
      <div className="widget-card system-status-widget">
        <div className="widget-header">
          <div className="system-status-indicator">
            <span className="system-status-bubble" />
            <div>
              <div className="widget-title">System Status</div>
              <div className="widget-subtitle">All systems operational</div>
            </div>
          </div>
        </div>

        <div className="system-status-list">
          <div className="status-row-item">
            <div className="status-row-left">
              <span className="status-icon core">⚙️</span>
              <span className="status-service-name">Orbit AI Core</span>
            </div>
            <div className="status-row-right">
              <span className="status-indicator-dot online" />
              <span className="status-label-green">Healthy</span>
            </div>
          </div>

          <div
            className="status-row-item clickable"
            onClick={onOpenAgentModal}
            title="Click to view Windows Local Agent status"
          >
            <div className="status-row-left">
              <span className="status-icon pc">🖥️</span>
              <span className="status-service-name">PC Agent</span>
            </div>
            <div className="status-row-right">
              <span className={`status-indicator-dot ${isAgentOnline ? 'online' : 'offline'}`} />
              <span className={isAgentOnline ? 'status-label-green' : 'status-label-red'}>
                {isAgentOnline ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>

          <div className="status-row-item">
            <div className="status-row-left">
              <span className="status-icon github">🐙</span>
              <span className="status-service-name">GitHub</span>
            </div>
            <div className="status-row-right">
              <span className="status-indicator-dot online" />
              <span className="status-label-green">Connected</span>
            </div>
          </div>

          <div className="status-row-item">
            <div className="status-row-left">
              <span className="status-icon vscode">💻</span>
              <span className="status-service-name">VS Code</span>
            </div>
            <div className="status-row-right">
              <span className="status-indicator-dot online" />
              <span className="status-label-green">Connected</span>
            </div>
          </div>

          <div className="status-row-item">
            <div className="status-row-left">
              <span className="status-icon docker">🐳</span>
              <span className="status-service-name">Docker</span>
            </div>
            <div className="status-row-right">
              <span className="status-indicator-dot online" />
              <span className="status-label-green">Healthy</span>
            </div>
          </div>

          <div className="status-row-item">
            <div className="status-row-left">
              <span className="status-icon db">🗄️</span>
              <span className="status-service-name">Database</span>
            </div>
            <div className="status-row-right">
              <span className="status-indicator-dot online" />
              <span className="status-label-green">Healthy</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Recent Agent Runs Widget */}
      <div className="widget-card recent-runs-widget">
        <div className="widget-header">
          <div className="runs-title-group">
            <span className="runs-clock-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
            </span>
            <span className="widget-title">Recent Agent Runs</span>
          </div>

          <button
            type="button"
            className="task-list-view-all"
            onClick={() => onSelectTask && tasks[0] && onSelectTask(tasks[0].id)}
          >
            <span>View all</span>
            <span>→</span>
          </button>
        </div>

        <div className="recent-runs-list">
          {tasks.slice(0, 5).map((t, idx) => {
            const icons = ['git-pull-request', 'file-text', 'code', 'cloud', 'search'];
            const curIcon = icons[idx % icons.length];
            const isRunning = ['in_progress', 'executing', 'verifying'].includes((t.status || '').toLowerCase());

            return (
              <div
                key={t.id}
                className="recent-run-item"
                onClick={() => onSelectTask && onSelectTask(t.id)}
                role="button"
                tabIndex={0}
              >
                <div className="recent-run-left">
                  <div className={`run-icon-slot icon-${curIcon}`}>
                    {curIcon === 'git-pull-request' && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="18" cy="18" r="3"/>
                        <circle cx="6" cy="6" r="3"/>
                        <path d="M13 6h3a2 2 0 0 1 2 2v7"/>
                        <line x1="6" y1="9" x2="6" y2="21"/>
                      </svg>
                    )}
                    {curIcon === 'file-text' && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                      </svg>
                    )}
                    {curIcon === 'code' && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="16 18 22 12 16 6"/>
                        <polyline points="8 6 2 12 8 18"/>
                      </svg>
                    )}
                    {curIcon === 'cloud' && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>
                      </svg>
                    )}
                    {curIcon === 'search' && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="8"/>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                      </svg>
                    )}
                  </div>

                  <div className="run-details">
                    <div className="run-title">{t.task}</div>
                    <div className="run-sub">
                      {t.plan?.summary || 'Execution completed with evidence'}
                    </div>
                  </div>
                </div>

                <div className="recent-run-right">
                  <span className={`run-status-badge ${isRunning ? 'running' : 'completed'}`}>
                    {isRunning ? 'Running' : 'Completed'}
                  </span>
                  <span className="run-time-text">
                    {getRelativeTime(t.updated_at || t.created_at)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
