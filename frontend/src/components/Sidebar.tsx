import React from 'react';

interface SidebarProps {
  activeNav: string;
  onNavigate: (nav: string) => void;
  tasksCount?: number;
  isAgentOnline?: boolean;
  onOpenAgentModal?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav,
  onNavigate,
  tasksCount = 0,
  isAgentOnline = true,
  onOpenAgentModal,
}) => {
  return (
    <aside className="app-sidebar" aria-label="Sidebar Navigation">
      <div className="sidebar-nav-section">
        <button
          type="button"
          className={`sidebar-nav-item ${activeNav === 'dashboard' ? 'active' : ''}`}
          onClick={() => onNavigate('dashboard')}
          id="sidebar-nav-dashboard"
        >
          <span className="sidebar-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </span>
          <span className="sidebar-nav-label">Dashboard</span>
        </button>

        <button
          type="button"
          className={`sidebar-nav-item ${activeNav === 'tasks' ? 'active' : ''}`}
          onClick={() => onNavigate('tasks')}
          id="sidebar-nav-tasks"
        >
          <span className="sidebar-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect width="18" height="18" x="3" y="4" rx="2" ry="2"/>
              <line x1="16" x2="16" y1="2" y2="6"/>
              <line x1="8" x2="8" y1="2" y2="6"/>
              <line x1="3" x2="21" y1="10" y2="10"/>
              <path d="m9 16 2 2 4-4"/>
            </svg>
          </span>
          <span className="sidebar-nav-label">Tasks</span>
          {tasksCount > 0 && <span className="sidebar-badge">{tasksCount}</span>}
        </button>

        <button
          type="button"
          className={`sidebar-nav-item ${activeNav === 'agent-runs' ? 'active' : ''}`}
          onClick={() => onNavigate('agent-runs')}
          id="sidebar-nav-agent-runs"
        >
          <span className="sidebar-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" x2="12" y1="8" y2="12"/>
              <line x1="12" x2="12.01" y1="16" y2="16"/>
            </svg>
          </span>
          <span className="sidebar-nav-label">Agent Runs</span>
        </button>

        <button
          type="button"
          className={`sidebar-nav-item ${activeNav === 'workspaces' ? 'active' : ''}`}
          onClick={() => onNavigate('workspaces')}
          id="sidebar-nav-workspaces"
        >
          <span className="sidebar-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m7.5 4.27 9 5.15"/>
              <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>
              <path d="m3.3 7 8.7 5 8.7-5"/>
              <path d="M12 22V12"/>
            </svg>
          </span>
          <span className="sidebar-nav-label">Workspaces</span>
        </button>

        <button
          type="button"
          className={`sidebar-nav-item ${activeNav === 'settings' ? 'active' : ''}`}
          onClick={() => onNavigate('settings')}
          id="sidebar-nav-settings"
        >
          <span className="sidebar-nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </span>
          <span className="sidebar-nav-label">Settings</span>
        </button>
      </div>

      {/* Quick Access Section */}
      <div className="sidebar-quick-access">
        <div className="sidebar-section-header">Quick Access</div>

        <button
          type="button"
          className="sidebar-quick-item"
          onClick={() => {}}
          title="Open VS Code"
        >
          <span className="quick-icon-badge vscode">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 18 22 12 16 6"/>
              <polyline points="8 6 2 12 8 18"/>
            </svg>
          </span>
          <span className="quick-label">VS Code</span>
        </button>

        <button
          type="button"
          className="sidebar-quick-item"
          onClick={() => {}}
          title="GitHub Integration"
        >
          <span className="quick-icon-badge github">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
            </svg>
          </span>
          <span className="quick-label">GitHub</span>
        </button>

        <button
          type="button"
          className="sidebar-quick-item"
          onClick={() => {}}
          title="Notepad"
        >
          <span className="quick-icon-badge notepad">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" x2="8" y1="13" y2="13"/>
              <line x1="16" x2="8" y1="17" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </span>
          <span className="quick-label">Notepad</span>
        </button>

        <button
          type="button"
          className="sidebar-quick-item"
          onClick={() => {}}
          title="Workspace E: Drive"
        >
          <span className="quick-icon-badge folder">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
            </svg>
          </span>
          <span className="quick-label">E: Drive</span>
        </button>
      </div>

      {/* Bottom Agent Online Pill Card */}
      <div className="sidebar-footer">
        <button
          type="button"
          className="sidebar-agent-card"
          onClick={onOpenAgentModal}
          title="Orbit AI PC Agent Status"
        >
          <div className="agent-card-left">
            <span className={`agent-online-dot ${isAgentOnline ? 'online' : 'offline'}`} />
            <div className="agent-card-text">
              <div className="agent-card-title">{isAgentOnline ? 'Agent Online' : 'Agent Offline'}</div>
              <div className="agent-card-sub">Ready to help</div>
            </div>
          </div>
          <span className="agent-card-arrow">›</span>
        </button>
      </div>
    </aside>
  );
};
