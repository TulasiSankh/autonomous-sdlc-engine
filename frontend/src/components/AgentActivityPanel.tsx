import React, { useState } from 'react';
import type { TaskRecord } from '../types/api';
import { StatusBadge } from './StatusBadge';

interface AgentActivityPanelProps {
  tasks: TaskRecord[];
  onSelectTask?: (taskId: string) => void;
}

interface LifecycleStage {
  id: string;
  number: number;
  title: string;
  description: string;
  icon: string;
  status: 'completed' | 'running' | 'pending' | 'failed' | 'blocked';
  timestamp?: string;
  detail?: string;
}

function formatDate(isoString?: string): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export const AgentActivityPanel: React.FC<AgentActivityPanelProps> = ({
  tasks,
  onSelectTask,
}) => {
  const [selectedTaskId, setSelectedTaskId] = useState<string>(
    tasks[0]?.id || ''
  );

  // Keep selectedTaskId valid if tasks change
  const activeTask = tasks.find((t) => t.id === selectedTaskId) || tasks[0];

  if (!activeTask) {
    return (
      <div className="agent-activity-card" data-testid="agent-activity-panel">
        <div className="activity-panel-header">
          <div className="activity-title-group">
            <span className="activity-icon-badge">🤖</span>
            <div>
              <h3>AI Agent Execution Pipeline</h3>
              <p>Autonomous SDLC lifecycle tracking across engineering phases</p>
            </div>
          </div>
        </div>
        <div className="activity-empty-state">
          <p>No active tasks currently tracked. Create a task below to initiate the autonomous pipeline.</p>
        </div>
      </div>
    );
  }

  // Derive genuine lifecycle stage statuses based on the selected task's real state
  const normStatus = (activeTask.status || '').toLowerCase();
  const hasPlan = Boolean(activeTask.plan && activeTask.plan.steps && activeTask.plan.steps.length > 0);
  const hasProposal = Boolean(activeTask.proposal);
  const hasWorkspace = Boolean(activeTask.workspace_id || normStatus === 'changes_applied' || normStatus.startsWith('verification'));
  const isVerifying = normStatus === 'verifying';
  const isVerified = normStatus === 'verified' || normStatus === 'completed';
  const isFailed = normStatus.includes('failed') || normStatus.includes('error');
  const isBlocked = normStatus.includes('blocked');
  const isExecuting = normStatus === 'executing' || normStatus === 'in_progress';

  const ACTION_TYPES = [
    'application_action',
    'browser_action',
    'filesystem_action',
    'composite_action',
    'command_action',
    'computer_task',
  ];
  const isComputerTask =
    ACTION_TYPES.includes(activeTask.task_type || '') ||
    (Boolean(activeTask.plan?.tool_steps) && (activeTask.plan?.tool_steps?.length || 0) > 0) ||
    Boolean(activeTask.plan?.target_app);

  let stages: LifecycleStage[];

  if (isComputerTask) {
    stages = [
      {
        id: 'requirements',
        number: 1,
        title: 'Inspecting Environment & Permissions',
        description: 'Detects Windows OS, user architecture, and local agent connectivity',
        icon: '💻',
        status: normStatus === 'queued' || normStatus === 'analyzing' ? 'running' : 'completed',
        timestamp: formatDate(activeTask.created_at),
        detail: activeTask.task,
      },
      {
        id: 'discovery',
        number: 2,
        title: 'Discovering Application & Planning Steps',
        description: 'Searches PATH, Windows Registry App Paths, and standard installation dirs',
        icon: '🔍',
        status:
          normStatus === 'queued' || normStatus === 'analyzing'
            ? 'pending'
            : normStatus === 'planning'
            ? 'running'
            : 'completed',
        timestamp: formatDate(activeTask.created_at),
        detail: activeTask.plan?.target_app
          ? `Target Application: ${activeTask.plan.target_app}`
          : `${activeTask.plan?.steps?.length || 0} step(s) planned`,
      },
      {
        id: 'execution',
        number: 3,
        title: 'Controlled Process Execution',
        description: 'Safe process launch through restricted launcher without shell=True',
        icon: '🚀',
        status: isExecuting
          ? 'running'
          : isBlocked
          ? 'blocked'
          : isFailed
          ? 'failed'
          : ['verifying', 'completed', 'verified'].includes(normStatus)
          ? 'completed'
          : 'pending',
        timestamp: formatDate(activeTask.updated_at),
        detail:
          isExecuting
            ? 'Launching process via local agent...'
            : isBlocked
            ? activeTask.error_summary || 'Execution blocked'
            : isFailed
            ? activeTask.error_summary || 'Execution failed'
            : ['verifying', 'completed', 'verified'].includes(normStatus)
            ? 'Process launched successfully'
            : 'Pending execution',
      },
      {
        id: 'verification',
        number: 4,
        title: 'Kernel & Process Table Verification',
        description: 'Queries Windows kernel to verify active PID and sustained execution',
        icon: '🛡️',
        status: isVerifying
          ? 'running'
          : normStatus === 'completed' || normStatus === 'verified'
          ? 'completed'
          : isBlocked
          ? 'blocked'
          : isFailed
          ? 'failed'
          : 'pending',
        timestamp: formatDate(activeTask.updated_at),
        detail:
          normStatus === 'completed' || normStatus === 'verified'
            ? 'Process running in Windows kernel verified'
            : isVerifying
            ? 'Verifying process table...'
            : isBlocked
            ? activeTask.error_summary || 'Verification blocked'
            : isFailed
            ? activeTask.error_summary || 'Verification failed'
            : 'Awaiting execution verification',
      },
      {
        id: 'completed',
        number: 5,
        title: 'Outcome Verified & Persisted',
        description: 'Structured execution evidence, duration, and audit telemetry recorded',
        icon: '✅',
        status:
          normStatus === 'completed' || normStatus === 'verified'
            ? 'completed'
            : isBlocked
            ? 'blocked'
            : isFailed
            ? 'failed'
            : 'pending',
        timestamp: activeTask.completed_at ? formatDate(activeTask.completed_at) : undefined,
        detail:
          normStatus === 'completed' || normStatus === 'verified'
            ? activeTask.execution_summary || 'Task completed with real verified outcome'
            : isBlocked
            ? 'Blocked: actionable guidance recorded'
            : isFailed
            ? 'Failed: failure evidence recorded'
            : 'In progress',
      },
    ];
  } else {
    stages = [
      {
        id: 'requirements',
        number: 1,
        title: 'Analyzing Task Requirements',
        description: 'PlannerAgent parses engineering prompt & detects codebase dependencies',
        icon: '🧠',
        status: 'completed',
        timestamp: formatDate(activeTask.created_at),
        detail: activeTask.task,
      },
      {
        id: 'plan',
        number: 2,
        title: 'Generating Implementation Plan',
        description: 'Formulates structured steps, affected files, criteria, and test commands',
        icon: '📐',
        status: hasPlan ? 'completed' : 'pending',
        timestamp: formatDate(activeTask.created_at),
        detail: hasPlan
          ? `${activeTask.plan.steps.length} steps planned • ${activeTask.plan.files_to_inspect.length} files to inspect`
          : 'Awaiting plan synthesis',
      },
      {
        id: 'proposal',
        number: 3,
        title: 'Creating Code Proposal',
        description: 'DeveloperAgent computes unified diff patch with deterministic dry-run',
        icon: '💻',
        status: hasProposal || normStatus === 'proposed' || hasWorkspace
          ? 'completed'
          : 'pending',
        timestamp: activeTask.proposal ? formatDate(activeTask.updated_at) : undefined,
        detail: activeTask.proposal
          ? `${activeTask.proposal.files_to_change.length} file change(s) proposed`
          : hasWorkspace
          ? 'Proposal synthesized & recorded'
          : 'Pending proposal generation',
      },
      {
        id: 'sandbox',
        number: 4,
        title: 'Applying Changes to Isolated Workspace',
        description: 'Strict workspace confinement, copying repository & applying changes',
        icon: '📦',
        status: hasWorkspace ? 'completed' : 'pending',
        timestamp: activeTask.workspace_id ? formatDate(activeTask.updated_at) : undefined,
        detail: activeTask.workspace_id
          ? `Isolated sandbox: ${activeTask.workspace_id}`
          : 'Pending workspace isolation',
      },
      {
        id: 'verification',
        number: 5,
        title: 'Running Tests & Verification',
        description: 'Sandboxed pytest test execution, exit code inspection & diagnostics',
        icon: '🛡️',
        status: isVerified
          ? 'completed'
          : isBlocked
          ? 'blocked'
          : isFailed
          ? 'failed'
          : isVerifying
          ? 'running'
          : 'pending',
        timestamp: activeTask.latest_verification
          ? formatDate(activeTask.latest_verification.timestamp)
          : undefined,
        detail: isVerified
          ? '100% tests passing in sandbox'
          : isBlocked
          ? 'Execution blocked by fail-closed security profile'
          : isFailed
          ? 'Tests failed in sandbox — diagnostic feedback recorded'
          : isVerifying
          ? 'Executing test suite...'
          : 'Ready for verification run',
      },
    ];
  }

  return (
    <section className="agent-activity-card" data-testid="agent-activity-panel" aria-label="AI Agent Activity Panel">
      <div className="activity-panel-header">
        <div className="activity-title-group">
          <span className="activity-icon-badge">🤖</span>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 600 }}>AI Agent Activity Timeline</h3>
              <span className="live-status-pill">
                <span className="health-dot" /> Live Lifecycle
              </span>
            </div>
            <p style={{ fontSize: '0.875rem', marginTop: '0.15rem' }}>
              Real-time multi-agent progression from requirements to verified workspace code
            </p>
          </div>
        </div>

        {tasks.length > 1 && (
          <div className="activity-task-selector">
            <label htmlFor="activity-task-select" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Inspecting Task:
            </label>
            <select
              id="activity-task-select"
              value={selectedTaskId}
              onChange={(e) => {
                setSelectedTaskId(e.target.value);
                if (onSelectTask) onSelectTask(e.target.value);
              }}
              className="form-select form-select-sm"
              style={{ maxWidth: '280px' }}
            >
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.id} — {t.task.slice(0, 32)}...
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Selected Task Overview Banner */}
      <div className="activity-active-task-bar">
        <div className="active-task-meta">
          <span className="task-id-tag">{activeTask.id}</span>
          <span className="active-task-name" title={activeTask.task}>
            {activeTask.task}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <StatusBadge status={activeTask.status} size="sm" />
          {onSelectTask && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
              onClick={() => onSelectTask(activeTask.id)}
            >
              View Full Details →
            </button>
          )}
        </div>
      </div>

      {/* Timeline Steps */}
      <div className="activity-timeline">
        {stages.map((stage, idx) => {
          const isLast = idx === stages.length - 1;
          const statusClass = `stage-${stage.status}`;

          return (
            <div key={stage.id} className={`timeline-stage-item ${statusClass}`}>
              {/* Connector Line */}
              {!isLast && <div className={`timeline-connector ${stage.status === 'completed' ? 'completed' : ''}`} />}

              {/* Status Circle */}
              <div className="timeline-node">
                <span className="stage-icon">{stage.icon}</span>
                <span className={`status-indicator-dot ${stage.status}`} />
              </div>

              {/* Stage Content */}
              <div className="timeline-content">
                <div className="timeline-title-row">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="stage-number">0{stage.number}</span>
                    <h4 className="stage-heading">{stage.title}</h4>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    {stage.timestamp && (
                      <span className="stage-timestamp">🕒 {stage.timestamp}</span>
                    )}
                    <span className={`stage-badge ${stage.status}`}>
                      {stage.status === 'completed' && '✓ Completed'}
                      {stage.status === 'running' && '⏳ Running'}
                      {stage.status === 'pending' && '○ Pending'}
                      {stage.status === 'failed' && '✕ Failed'}
                      {stage.status === 'blocked' && '🛡️ Blocked'}
                    </span>
                  </div>
                </div>

                <p className="stage-desc">{stage.description}</p>

                {stage.detail && (
                  <div className="stage-detail-chip">
                    <span>{stage.detail}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
