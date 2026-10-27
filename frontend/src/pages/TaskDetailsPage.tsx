import React, { useEffect, useState } from 'react';
import type {
  CodeApplicationResult,
  ImplementationProposal,
  LocalAgentStatusResponse,
  TaskRecord,
  TaskStepExecutionRecord,
} from '../types/api';
import { DeleteConfirmModal } from '../components/DeleteConfirmModal';
import { DiffViewer } from '../components/DiffViewer';
import { ErrorBanner } from '../components/ErrorBanner';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PlanCard } from '../components/PlanCard';
import { StatusBadge } from '../components/StatusBadge';
import { apiClient } from '../services/apiClient';

interface TaskDetailsPageProps {
  task: TaskRecord;
  onBack: () => void;
  onRefreshTask: (taskId: string) => Promise<TaskRecord>;
  onTaskDeleted?: (taskId: string) => void;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export const TaskDetailsPage: React.FC<TaskDetailsPageProps> = ({
  task,
  onBack,
  onRefreshTask,
  onTaskDeleted,
}) => {
  const [currentTask, setCurrentTask] = useState<TaskRecord>(task);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isGeneratingProposal, setIsGeneratingProposal] = useState<boolean>(false);
  const [isApplying, setIsApplying] = useState<boolean>(false);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [proposal, setProposal] = useState<ImplementationProposal | null>(
    task.proposal || null
  );
  const [applicationResult, setApplicationResult] = useState<CodeApplicationResult | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastFailedAction, setLastFailedAction] = useState<'proposal' | 'apply' | 'verify' | 'refresh' | 'execute' | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<boolean>(false);

  // Local Windows Agent telemetry state
  const [localAgentStatus, setLocalAgentStatus] = useState<LocalAgentStatusResponse | null>(null);

  // Computer task execution & deletion states
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isExecutingComputerTask, setIsExecutingComputerTask] = useState<boolean>(false);
  const [approveSensitiveActions, setApproveSensitiveActions] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [stepExecutions, setStepExecutions] = useState<TaskStepExecutionRecord[]>(
    task.step_executions || []
  );

  useEffect(() => {
    let mounted = true;
    const fetchAgentStatus = async () => {
      try {
        const res = await apiClient.getLocalAgentStatus();
        if (mounted) setLocalAgentStatus(res);
      } catch {
        if (mounted) {
          setLocalAgentStatus({
            online: false,
            message: 'Local execution agent offline (127.0.0.1:8001)',
          });
        }
      }
    };
    fetchAgentStatus();
    return () => {
      mounted = false;
    };
  }, []);

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      setActionError(null);
      const updated = await onRefreshTask(currentTask.id);
      setCurrentTask(updated);
      if (updated.proposal) {
        setProposal(updated.proposal);
      }
      setLastFailedAction(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(`Failed to refresh task state: ${msg}`);
      setLastFailedAction('refresh');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleGenerateProposal = async () => {
    try {
      setIsGeneratingProposal(true);
      setActionError(null);
      setSuccessNotice(null);
      const generated = await apiClient.createTaskProposal(currentTask.id);
      setProposal(generated);
      const updated = await onRefreshTask(currentTask.id);
      setCurrentTask(updated);
      setSuccessNotice('Implementation proposal formulated by DeveloperAgent with candidate diffs (dry_run=true).');
      setLastFailedAction(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(`DeveloperAgent failed to generate proposal: ${msg}`);
      setLastFailedAction('proposal');
    } finally {
      setIsGeneratingProposal(false);
    }
  };

  const handleApplyProposal = async () => {
    try {
      setIsApplying(true);
      setActionError(null);
      setSuccessNotice(null);
      const appResult = await apiClient.applyTaskProposal(currentTask.id);
      setApplicationResult(appResult);
      const updated = await onRefreshTask(currentTask.id);
      setCurrentTask(updated);
      setSuccessNotice(
        `Applied proposal into isolated workspace '${appResult.workspace_id}'. Lifecycle state transitioned to 'changes_applied'.`
      );
      setLastFailedAction(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(`CodeApplicationService failed to apply proposal: ${msg}`);
      setLastFailedAction('apply');
    } finally {
      setIsApplying(false);
    }
  };

  const handleRunVerification = async () => {
    try {
      setIsVerifying(true);
      setActionError(null);
      setSuccessNotice(null);
      const verifResult = await apiClient.verifyTask(currentTask.id);
      const updated = await onRefreshTask(currentTask.id);
      setCurrentTask(updated);
      if (verifResult.status === 'blocked') {
        setSuccessNotice(
          `Verification executed safely with default DisabledSecurityRunner (status='blocked'). Task transitioned to 'verification_blocked'.`
        );
      } else {
        setSuccessNotice(`Verification run completed with status '${verifResult.status}'.`);
      }
      setLastFailedAction(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(`VerificationService failed: ${msg}`);
      setLastFailedAction('verify');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleRetry = () => {
    if (lastFailedAction === 'proposal') {
      handleGenerateProposal();
    } else if (lastFailedAction === 'apply') {
      handleApplyProposal();
    } else if (lastFailedAction === 'verify') {
      handleRunVerification();
    } else if (lastFailedAction === 'execute') {
      handleExecuteComputerTask();
    } else {
      handleRefresh();
    }
  };

  const handleExecuteComputerTask = async () => {
    try {
      setIsExecutingComputerTask(true);
      setActionError(null);
      setSuccessNotice(null);
      const updated = await apiClient.executeTask(currentTask.id, approveSensitiveActions);
      setCurrentTask(updated);
      setStepExecutions(updated.step_executions || []);
      if (updated.status === 'completed') {
        setSuccessNotice('Execution completed and outcome independently verified.');
      } else if (updated.status === 'blocked') {
        setActionError(updated.error_summary || 'Requires user approval for sensitive operations.');
        setLastFailedAction('execute');
      } else if (updated.status === 'failed') {
        setActionError(updated.error_summary || 'One or more tool steps failed.');
        setLastFailedAction('execute');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(`Tool execution failed: ${msg}`);
      setLastFailedAction('execute');
    } finally {
      setIsExecutingComputerTask(false);
    }
  };

  const handleCancelTask = async () => {
    try {
      setIsCancelling(true);
      await apiClient.cancelTask(currentTask.id);
      const updated = await onRefreshTask(currentTask.id);
      setCurrentTask(updated);
      setSuccessNotice('Cancellation requested for active execution.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(`Failed to cancel: ${msg}`);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDeleteTask = async () => {
    try {
      setIsDeleting(true);
      setDeleteError(null);
      await apiClient.deleteTask(currentTask.id);
      if (onTaskDeleted) {
        onTaskDeleted(currentTask.id);
      }
      onBack();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setDeleteError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  const copyTaskId = () => {
    navigator.clipboard?.writeText(currentTask.id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const canApplyProposal =
    (proposal !== null || currentTask.proposal !== null) &&
    (currentTask.status === 'planned' || currentTask.status === 'proposed');

  const canVerify =
    currentTask.status === 'changes_applied' ||
    currentTask.status === 'verification_failed' ||
    currentTask.status === 'verification_blocked' ||
    currentTask.status === 'verification_error';

  const toolSteps = currentTask.plan?.tool_steps || [];
  const ACTION_TYPES = [
    'application_action',
    'browser_action',
    'filesystem_action',
    'composite_action',
    'command_action',
    'computer_task',
    'unsupported',
  ];
  const isComputerTask =
    ACTION_TYPES.includes(currentTask.task_type || '') ||
    toolSteps.length > 0 ||
    Boolean(currentTask.plan?.target_app);
  const isExecuting =
    currentTask.status === 'in_progress' ||
    currentTask.status === 'executing' ||
    currentTask.status === 'verifying';

  const normStatus = (currentTask.status || '').toLowerCase();

  const LIFECYCLE_STEPS = [
    { key: 'queued', label: 'Queued', icon: '⏳' },
    { key: 'analyzing', label: 'Analyzing', icon: '🔍' },
    { key: 'planning', label: 'Planning', icon: '📐' },
    { key: 'executing', label: 'Executing', icon: '⚡' },
    { key: 'verifying', label: 'Verifying', icon: '🛡️' },
    { key: 'completed', label: 'Completed', icon: '✅' },
  ];

  let activeStageIndex = 0;
  if (normStatus === 'queued') activeStageIndex = 0;
  else if (normStatus === 'analyzing') activeStageIndex = 1;
  else if (['planning', 'planned', 'proposed'].includes(normStatus)) activeStageIndex = 2;
  else if (['executing', 'in_progress', 'changes_applied'].includes(normStatus)) activeStageIndex = 3;
  else if (normStatus.startsWith('verification') || normStatus === 'verifying') activeStageIndex = 4;
  else if (['completed', 'verified'].includes(normStatus)) activeStageIndex = 5;
  else if (['blocked', 'failed', 'cancelled'].includes(normStatus)) {
    activeStageIndex = toolSteps.length > 0 ? 3 : 2;
  }

  // Extract real execution telemetry from step records
  let discoveredAppPath: string | null = null;
  let discoveryMethod: string | null = null;
  let launchedPid: number | null = null;
  let verifiedPid: number | null = null;
  let windowVerified: boolean = false;
  let windowTitle: string | null = null;

  for (const step of stepExecutions) {
    let out: Record<string, unknown> | null = null;
    if (step.output_json) {
      try {
        out = JSON.parse(step.output_json);
      } catch {
        out = null;
      }
    } else if (
      (step as unknown as { output?: unknown }).output &&
      typeof (step as unknown as { output?: unknown }).output === 'object'
    ) {
      out = (step as unknown as { output?: Record<string, unknown> }).output as Record<string, unknown>;
    }
    
    // Parse step parameters if available
    let params: Record<string, unknown> | null = null;
    if (step.parameters_json) {
      try {
        params = JSON.parse(step.parameters_json);
      } catch {
        params = null;
      }
    }

    if (step.action === 'detect' && out) {
      if (out.executable_path && typeof out.executable_path === 'string') {
        discoveredAppPath = out.executable_path;
        if (out.source) discoveryMethod = String(out.source);
        else discoveryMethod = 'Windows Registry / PATH / AppData';
      }
    }

    if (step.action === 'launch' || step.action === 'open_in_app' || step.action === 'open_vscode' || step.action === 'open_notepad') {
      if (out && typeof out.pid === 'number') {
        launchedPid = out.pid;
      } else if (params && typeof params.pid === 'number') {
        launchedPid = params.pid;
      } else if (step.output_json) {
        const pidMatch = step.output_json.match(/PID:?\s*(\d+)/i);
        if (pidMatch) launchedPid = parseInt(pidMatch[1], 10);
      }
      if (out && out.executable && typeof out.executable === 'string') {
        discoveredAppPath = out.executable;
      }
    }

    if (step.action === 'verify_process_running' && step.status === 'completed') {
      if (params && typeof params.pid === 'number') {
        verifiedPid = params.pid;
      } else if (out && typeof out.pid === 'number') {
        verifiedPid = out.pid;
      } else if (step.output_json) {
        const pidMatch = step.output_json.match(/PID:?\s*(\d+)/i);
        if (pidMatch) verifiedPid = parseInt(pidMatch[1], 10);
      }
      if (!verifiedPid && launchedPid) {
        verifiedPid = launchedPid;
      }
    }

    if (step.action === 'verify_visible_window') {
      if (step.status === 'completed') {
        windowVerified = true;
        if (out && typeof out.title === 'string') windowTitle = out.title;
      } else {
        windowVerified = false;
      }
    }
  }

  return (
    <div className="container" data-testid="task-details-page">
      {/* Breadcrumb Navigation */}
      <div className="breadcrumb">
        <span
          className="breadcrumb-link"
          onClick={onBack}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onBack();
          }}
        >
          ← Back to Dashboard
        </span>
        <span>/</span>
        <span style={{ color: 'var(--text-primary)' }}>{currentTask.id}</span>
      </div>

      {actionError && <ErrorBanner message={actionError} onRetry={handleRetry} />}

      {successNotice && (
        <div className="alert-banner info" style={{ marginBottom: '1.5rem' }}>
          <span>ℹ️</span>
          <div style={{ flex: 1 }}>{successNotice}</div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setSuccessNotice(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Task Header Card */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <span className="task-id-tag" style={{ fontSize: '0.9rem', padding: '0.25rem 0.65rem' }}>
              {currentTask.id}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={copyTaskId}
              title="Copy Task ID"
            >
              {copiedId ? '✓ Copied' : '📋 Copy ID'}
            </button>
            <StatusBadge status={currentTask.status} />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {isComputerTask ? (
              <>
                {isExecuting ? (
                  <button
                    id="cancel-execution-btn"
                    type="button"
                    className="btn btn-warning btn-sm"
                    onClick={handleCancelTask}
                    disabled={isCancelling}
                  >
                    {isCancelling ? 'Cancelling...' : '⏹️ Cancel Execution'}
                  </button>
                ) : (
                  <button
                    id="execute-task-btn"
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleExecuteComputerTask}
                    disabled={isExecutingComputerTask || isRefreshing}
                  >
                    {isExecutingComputerTask
                      ? 'Executing Tools...'
                      : currentTask.status === 'completed'
                      ? '⚡ Re-execute Task'
                      : '⚡ Execute Task'}
                  </button>
                )}
              </>
            ) : (
              <>
                {(!proposal || currentTask.status === 'planned') && (
                  <button
                    id="generate-proposal-header-btn"
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleGenerateProposal}
                    disabled={isGeneratingProposal || isApplying || isVerifying}
                  >
                    {isGeneratingProposal ? 'Generating Proposal...' : '⚡ Generate Proposal'}
                  </button>
                )}

                {proposal && (currentTask.status === 'proposed' || currentTask.status === 'planned') && (
                  <button
                    id="regenerate-proposal-header-btn"
                    type="button"
                    className="btn btn-outline-accent btn-sm"
                    onClick={handleGenerateProposal}
                    disabled={isGeneratingProposal || isApplying || isVerifying}
                    title="Regenerate proposal via DeveloperAgent"
                  >
                    {isGeneratingProposal ? 'Regenerating...' : '🔄 Regenerate Proposal'}
                  </button>
                )}

                {canApplyProposal && (
                  <button
                    id="apply-proposal-btn"
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleApplyProposal}
                    disabled={isApplying || isGeneratingProposal}
                  >
                    {isApplying ? 'Applying to Sandbox...' : '⚙️ Apply Proposal'}
                  </button>
                )}

                {canVerify && (
                  <button
                    id="run-verification-btn"
                    type="button"
                    className="btn btn-outline-accent btn-sm"
                    onClick={handleRunVerification}
                    disabled={isVerifying}
                  >
                    {isVerifying ? 'Verifying...' : '🛡️ Run Verification'}
                  </button>
                )}
              </>
            )}

            <button
              id="refresh-task-btn"
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              {isRefreshing ? 'Refreshing...' : '🔄 Refresh Status'}
            </button>

            <button
              id="delete-task-details-btn"
              type="button"
              className="btn btn-outline-danger btn-sm"
              onClick={() => setShowDeleteModal(true)}
              disabled={isDeleting || isExecuting}
              title={isExecuting ? 'Cannot delete task while execution is in progress' : 'Delete this task'}
            >
              🗑️ Delete Task
            </button>
          </div>
        </div>

        <h2 style={{ fontSize: '1.4rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
          {currentTask.task}
        </h2>

        <div
          style={{
            display: 'flex',
            gap: '1.5rem',
            flexWrap: 'wrap',
            fontSize: '0.8125rem',
            color: 'var(--text-muted)',
          }}
        >
          <div>
            <strong style={{ color: 'var(--text-secondary)' }}>Created:</strong>{' '}
            {formatDate(currentTask.created_at)}
          </div>
          <div>
            <strong style={{ color: 'var(--text-secondary)' }}>Updated:</strong>{' '}
            {formatDate(currentTask.updated_at)}
          </div>
          <div>
            <strong style={{ color: 'var(--text-secondary)' }}>Revision Iterations:</strong>{' '}
            <span
              style={{
                color: currentTask.revision_count > 0 ? '#fbbf24' : 'var(--text-primary)',
                fontWeight: 600,
              }}
            >
              {currentTask.revision_count} / 3
            </span>
          </div>
        </div>
      </div>

      {/* Lifecycle Progression Stepper */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1.1rem 1.4rem' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '0.85rem',
            flexWrap: 'wrap',
            gap: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1rem' }}>🔄</span>
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Task Lifecycle Progression
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status:</span>
            <StatusBadge status={currentTask.status} size="sm" />
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.5rem',
            flexWrap: 'wrap',
          }}
        >
          {LIFECYCLE_STEPS.map((step, idx) => {
            const isCompleted =
              idx < activeStageIndex ||
              currentTask.status === 'completed' ||
              currentTask.status === 'verified';
            const isCurrent =
              idx === activeStageIndex &&
              currentTask.status !== 'completed' &&
              currentTask.status !== 'verified';
            const isStoppedHere =
              isCurrent && ['blocked', 'failed', 'cancelled'].includes(normStatus);

            return (
              <div
                key={step.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-pill)',
                  border: isStoppedHere
                    ? '1.5px solid #fca5a5'
                    : isCurrent
                    ? '1.5px solid #93c5fd'
                    : isCompleted
                    ? '1.5px solid #a7f3d0'
                    : '1px solid var(--border-light)',
                  background: isStoppedHere
                    ? '#fef2f2'
                    : isCurrent
                    ? '#eff6ff'
                    : isCompleted
                    ? '#ecfdf5'
                    : '#f8fafc',
                  color: isStoppedHere
                    ? '#b91c1c'
                    : isCurrent
                    ? '#1d4ed8'
                    : isCompleted
                    ? '#047857'
                    : 'var(--text-muted)',
                  fontSize: '0.78rem',
                  fontWeight: isCurrent || isCompleted ? 700 : 500,
                  transition: 'all 0.2s',
                }}
              >
                <span>{step.icon}</span>
                <span>{step.label}</span>
                {isCompleted && <span style={{ color: '#10b981', fontWeight: 800 }}>✓</span>}
                {isStoppedHere && <span style={{ color: '#ef4444', fontWeight: 800 }}>✕</span>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Detailed Grid: Left column content, Right column metadata */}
      <div className="detail-grid">
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Section: Execution Plan */}
          <div>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
              Execution Plan
            </h3>
            <PlanCard plan={currentTask.plan} titlePrefix="PlannerAgent" />
          </div>

          {/* Section: Computer Task Execution (when isComputerTask) */}
          {isComputerTask && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Windows Local Execution & Discovery Diagnostics Card */}
              <div className="card" style={{ padding: '1.25rem' }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '0.85rem',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.2rem' }}>🖥️</span>
                    <div>
                      <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)', display: 'block' }}>
                        Windows Local Agent & Execution Telemetry
                      </strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Direct Windows inspection, detached process launching, and process table verification
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        padding: '0.2rem 0.6rem',
                        borderRadius: 'var(--radius-pill)',
                        fontWeight: 700,
                        background: localAgentStatus?.online ? '#ecfdf5' : '#fef2f2',
                        color: localAgentStatus?.online ? '#047857' : '#b91c1c',
                        border: `1px solid ${localAgentStatus?.online ? '#a7f3d0' : '#fecaca'}`,
                      }}
                    >
                      {localAgentStatus?.online ? '● Local Agent Online' : '○ Local Agent Offline'}
                    </span>
                    {localAgentStatus?.details?.os && (
                      <span
                        style={{
                          fontSize: '0.75rem',
                          color: 'var(--text-muted)',
                          fontFamily: 'var(--font-mono)',
                          background: 'var(--bg-subtle)',
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                          border: '1px solid var(--border-light)',
                        }}
                      >
                        {localAgentStatus.details.os} ({localAgentStatus.details.architecture})
                      </span>
                    )}
                  </div>
                </div>

                {!localAgentStatus?.online && (
                  <div
                    className="alert-banner warning"
                    style={{
                      marginBottom: '1rem',
                      padding: '0.85rem 1rem',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <span style={{ fontSize: '1.1rem' }}>⚠️</span>
                    <div style={{ flex: 1, fontSize: '0.8125rem' }}>
                      <strong>Local Agent Service Offline:</strong> Orbit AI communicates with a loopback service on port 8001 to execute Windows actions. Start it by running:
                      <code
                        style={{
                          display: 'block',
                          marginTop: '0.4rem',
                          background: 'rgba(0,0,0,0.06)',
                          padding: '0.35rem 0.6rem',
                          borderRadius: '4px',
                          fontFamily: 'var(--font-mono)',
                          color: '#92400e',
                        }}
                      >
                        python start_local_agent.py
                      </code>
                    </div>
                  </div>
                )}

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                    gap: '0.75rem',
                    fontSize: '0.8125rem',
                  }}
                >
                  <div
                    style={{
                      background: 'var(--bg-subtle)',
                      padding: '0.7rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Target Application
                    </div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                      {currentTask.plan?.target_app || 'Local Computer Tool'}
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'var(--bg-subtle)',
                      padding: '0.7rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Discovered Executable Path
                    </div>
                    <div
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.72rem',
                        color: discoveredAppPath ? '#047857' : 'var(--text-muted)',
                        marginTop: '0.25rem',
                        wordBreak: 'break-all',
                      }}
                    >
                      {discoveredAppPath || (currentTask.status === 'completed' ? 'Auto-detected in PATH / Registry' : 'Pending discovery')}
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'var(--bg-subtle)',
                      padding: '0.7rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Discovery Method
                    </div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                      {discoveryMethod || 'Windows Registry / PATH / AppData'}
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'var(--bg-subtle)',
                      padding: '0.7rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Process Verification
                    </div>
                    <div
                      style={{
                        fontWeight: 700,
                        color: verifiedPid ? '#047857' : launchedPid ? '#0284c7' : 'var(--text-muted)',
                        marginTop: '0.25rem',
                      }}
                    >
                      {verifiedPid
                        ? `PID ${verifiedPid} (Verified Alive)`
                        : launchedPid
                        ? `PID ${launchedPid} (Launched)`
                        : 'Unverified'}
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'var(--bg-subtle)',
                      padding: '0.7rem 0.85rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Visible Window Verification
                    </div>
                    <div
                      style={{
                        fontWeight: 700,
                        color: windowVerified ? '#047857' : currentTask.status === 'partially_completed' || currentTask.status === 'failed' ? '#b91c1c' : 'var(--text-muted)',
                        marginTop: '0.25rem',
                      }}
                    >
                      {windowVerified
                        ? `✅ Window Confirmed (${windowTitle || 'Interactive Desktop'})`
                        : currentTask.status === 'partially_completed'
                        ? '❌ No Visible Window Found'
                        : 'Pending Verification'}
                    </div>
                  </div>
                </div>

                {/* If missing app advice needed */}
                {(currentTask.status === 'failed' || currentTask.status === 'blocked') &&
                  currentTask.error_summary?.toLowerCase().includes('not installed') && (
                    <div
                      className="alert-banner warning"
                      style={{
                        marginTop: '0.85rem',
                        marginBottom: 0,
                        padding: '0.75rem 0.9rem',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <span>💡</span>
                      <div style={{ flex: 1, fontSize: '0.8125rem' }}>
                        <strong>Application Not Found:</strong> Visual Studio Code was not detected in PATH, Registry App Paths, or common installation folders.
                        Download it from{' '}
                        <a
                          href="https://code.visualstudio.com/Download"
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: 'var(--accent-primary)', fontWeight: 700, textDecoration: 'underline' }}
                        >
                          https://code.visualstudio.com/Download
                        </a>{' '}
                        and ensure "Add to PATH" is selected during installation.
                      </div>
                    </div>
                  )}
              </div>
              {/* Outcome summary card */}
              {(currentTask.status === 'completed' ||
                currentTask.status === 'partially_completed' ||
                currentTask.status === 'failed' ||
                currentTask.status === 'blocked' ||
                currentTask.status === 'cancelled') && (
                <div
                  className={`card outcome-summary-card ${currentTask.status}`}
                  style={{
                    borderLeft: `5px solid ${
                      currentTask.status === 'completed' && (currentTask.verification_status === 'passed' || windowVerified)
                        ? 'var(--accent-mint)'
                        : currentTask.status === 'partially_completed'
                        ? '#f59e0b'
                        : currentTask.status === 'blocked'
                        ? '#fbbf24'
                        : currentTask.status === 'cancelled'
                        ? 'var(--text-muted)'
                        : '#ef4444'
                    }`,
                    background:
                      currentTask.status === 'completed' && (currentTask.verification_status === 'passed' || windowVerified)
                        ? '#f0fdf4'
                        : currentTask.status === 'partially_completed'
                        ? '#fffbeb'
                        : currentTask.status === 'blocked'
                        ? '#fffbeb'
                        : currentTask.status === 'cancelled'
                        ? '#f8fafc'
                        : '#fef2f2',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.5rem',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '1.25rem' }}>
                        {currentTask.status === 'completed' && (currentTask.verification_status === 'passed' || windowVerified)
                          ? '✅'
                          : currentTask.status === 'partially_completed'
                          ? '⚠️'
                          : currentTask.status === 'blocked'
                          ? '⚠️'
                          : currentTask.status === 'cancelled'
                          ? '⏹️'
                          : '❌'}
                      </span>
                      <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                        {currentTask.status === 'completed' && (currentTask.verification_status === 'passed' || windowVerified)
                          ? 'Outcome Independently Verified'
                          : currentTask.status === 'partially_completed'
                          ? 'Partially Completed (Window Verification Failed)'
                          : currentTask.status === 'blocked'
                          ? 'Execution Blocked'
                          : currentTask.status === 'cancelled'
                          ? 'Execution Cancelled'
                          : 'Execution Failed'}
                      </strong>
                    </div>
                    <StatusBadge status={currentTask.status} size="sm" />
                  </div>

                  <p
                    style={{
                      fontSize: '0.875rem',
                      color: 'var(--text-secondary)',
                      marginBottom: '0.75rem',
                    }}
                  >
                    {currentTask.execution_summary ||
                      currentTask.error_summary ||
                      'Task outcome logged.'}
                  </p>

                  <div
                    style={{
                      display: 'flex',
                      gap: '1rem',
                      flexWrap: 'wrap',
                      fontSize: '0.8125rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    {currentTask.plan.target_url && (
                      <div>
                        🌐 Target URL:{' '}
                        <a
                          href={currentTask.plan.target_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: 'var(--text-accent)' }}
                        >
                          {currentTask.plan.target_url}
                        </a>
                      </div>
                    )}
                    {currentTask.plan.target_path && (
                      <div>
                        📁 Target Path: <code>{currentTask.plan.target_path}</code>
                      </div>
                    )}
                    {currentTask.plan.target_app && (
                      <div>
                        🚀 App: <strong>{currentTask.plan.target_app}</strong>
                      </div>
                    )}
                    {currentTask.completed_at && (
                      <div>
                        🕒 Finished: {formatDate(currentTask.completed_at)}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tool Execution Steps List */}
              <div className="card">
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '1rem',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                  }}
                >
                  <div>
                    <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>
                      Local Computer Tool Execution
                    </h3>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      Real execution through modular registry (Browser, Filesystem, Application Launcher, Command, Verification)
                    </p>
                  </div>

                  {toolSteps.some((s) => s.requires_approval) && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        background: '#fffbeb',
                        padding: '0.35rem 0.65rem',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid #fde68a',
                      }}
                    >
                      <input
                        type="checkbox"
                        id="approve-sensitive-box"
                        checked={approveSensitiveActions}
                        onChange={(e) => setApproveSensitiveActions(e.target.checked)}
                        style={{ cursor: 'pointer' }}
                      />
                      <label
                        htmlFor="approve-sensitive-box"
                        style={{
                          fontSize: '0.75rem',
                          color: '#92400e',
                          cursor: 'pointer',
                          fontWeight: 600,
                        }}
                      >
                        Approve sensitive operations
                      </label>
                    </div>
                  )}
                </div>

                {isExecutingComputerTask && (
                  <div style={{ padding: '1.5rem', textAlign: 'center' }}>
                    <LoadingSpinner message="Executing planned tools on local computer and verifying outcomes..." />
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {toolSteps.map((step, index) => {
                    const stepNum = step.step_number ?? (step as unknown as { step_index?: number }).step_index ?? (index + 1);
                    const execution = stepExecutions.find(
                      (s) => s.step_number === stepNum || ((s as unknown as { step_index?: number }).step_index === index)
                    );
                    const stepStatus =
                      execution?.status ||
                      (isExecutingComputerTask ? 'running' : 'pending');

                    const toolName = (step.tool || (step as unknown as { tool_name?: string }).tool_name || 'tool').toString();
                    let toolIcon = '⚡';
                    if (toolName === 'browser') toolIcon = '🌐';
                    else if (toolName === 'filesystem') toolIcon = '📁';
                    else if (toolName === 'app_launcher') toolIcon = '🚀';
                    else if (toolName === 'command') toolIcon = '⌨️';
                    else if (toolName === 'verification') toolIcon = '🛡️';

                    let parsedOutput: Record<string, unknown> | null = null;
                    if (execution?.output_json) {
                      try {
                        parsedOutput = JSON.parse(execution.output_json);
                      } catch {
                        parsedOutput = null;
                      }
                    } else if (execution && (execution as unknown as { output?: unknown }).output && typeof (execution as unknown as { output?: unknown }).output === 'object') {
                      parsedOutput = (execution as unknown as { output?: Record<string, unknown> }).output as Record<string, unknown>;
                    }

                    const stepParams = step.parameters || (step as unknown as { params?: Record<string, unknown> }).params;

                    return (
                      <div
                        key={stepNum}
                        className={`step-execution-item ${stepStatus}`}
                        style={{
                          border: '1px solid var(--border-light)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '0.875rem 1rem',
                          background:
                            stepStatus === 'completed'
                              ? '#f0fdf4'
                              : stepStatus === 'failed'
                              ? '#fef2f2'
                              : 'var(--bg-surface)',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '0.35rem',
                            flexWrap: 'wrap',
                            gap: '0.5rem',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                            <span
                              style={{
                                fontWeight: 700,
                                fontSize: '0.8125rem',
                                color: 'var(--text-muted)',
                              }}
                            >
                              #{stepNum}
                            </span>
                            <span
                              className="tool-chip"
                              style={{
                                fontSize: '0.75rem',
                                padding: '0.15rem 0.5rem',
                                background: '#e0e7ff',
                                color: '#4338ca',
                                borderRadius: '4px',
                                fontWeight: 600,
                              }}
                            >
                              {toolIcon} {toolName.toUpperCase()}: {step.action}
                            </span>
                            {step.requires_approval && (
                              <span
                                style={{
                                  fontSize: '0.7rem',
                                  padding: '0.1rem 0.4rem',
                                  background: '#fef3c7',
                                  color: '#b45309',
                                  borderRadius: '4px',
                                  fontWeight: 600,
                                }}
                              >
                                ⚠️ Sensitive
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            {execution?.duration_seconds ? (
                              <span
                                style={{
                                  fontSize: '0.75rem',
                                  color: 'var(--text-muted)',
                                  fontFamily: 'var(--font-mono)',
                                }}
                              >
                                {execution.duration_seconds.toFixed(2)}s
                              </span>
                            ) : null}
                            <StatusBadge status={stepStatus} size="sm" />
                          </div>
                        </div>

                        {step.description && (
                          <div
                            style={{
                              fontSize: '0.875rem',
                              fontWeight: 600,
                              color: 'var(--text-primary)',
                              marginBottom: '0.25rem',
                            }}
                          >
                            {step.description}
                          </div>
                        )}

                        {step.expected_outcome && (
                          <div
                            style={{
                              fontSize: '0.8125rem',
                              color: 'var(--text-secondary)',
                              marginBottom: '0.35rem',
                            }}
                          >
                            🎯 <strong>Expected outcome:</strong> {step.expected_outcome}
                          </div>
                        )}

                        {/* Parameter previews */}
                        {stepParams && Object.keys(stepParams).length > 0 && (
                          <div
                            style={{
                              fontSize: '0.75rem',
                              color: 'var(--text-muted)',
                              marginTop: '0.35rem',
                              fontFamily: 'var(--font-mono)',
                              background: 'rgba(0,0,0,0.02)',
                              padding: '0.3rem 0.5rem',
                              borderRadius: '4px',
                            }}
                          >
                            Params: {JSON.stringify(stepParams)}
                          </div>
                        )}

                        {/* Output preview */}
                        {parsedOutput && (
                          <div
                            style={{
                              marginTop: '0.5rem',
                              fontSize: '0.75rem',
                              color: '#166534',
                              background: '#dcfce7',
                              padding: '0.4rem 0.65rem',
                              borderRadius: '4px',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            <strong>Output:</strong>{' '}
                            {typeof parsedOutput === 'object' && parsedOutput.message
                              ? String(parsedOutput.message)
                              : JSON.stringify(parsedOutput)}
                          </div>
                        )}

                        {/* Error preview */}
                        {execution?.error_message && (
                          <div
                            style={{
                              marginTop: '0.5rem',
                              fontSize: '0.75rem',
                              color: '#991b1b',
                              background: '#fee2e2',
                              padding: '0.4rem 0.65rem',
                              borderRadius: '4px',
                            }}
                          >
                            <strong>Error:</strong> {execution.error_message}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Section: Developer Proposal (when SDLC task) */}
          {!isComputerTask && (
            <>
              <div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '0.75rem',
                  }}
            >
              <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>
                Developer Agent Proposal
              </h3>
              {!proposal && (
                <button
                  id="generate-proposal-btn"
                  type="button"
                  className="btn btn-outline-accent btn-sm"
                  onClick={handleGenerateProposal}
                  disabled={isGeneratingProposal}
                >
                  {isGeneratingProposal ? 'Generating Proposal...' : '⚡ Propose Implementation'}
                </button>
              )}
            </div>

            {isGeneratingProposal ? (
              <div className="card">
                <LoadingSpinner message="DeveloperAgent is analyzing plan and formulating file changes..." />
              </div>
            ) : proposal ? (
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-accent)', fontWeight: 600 }}>
                    Summary: {proposal.summary}
                  </div>
                  {proposal.dry_run && (
                    <span
                      style={{
                        fontSize: '0.7rem',
                        background: 'rgba(56, 189, 248, 0.1)',
                        color: '#38bdf8',
                        border: '1px solid rgba(56, 189, 248, 0.3)',
                        padding: '0.15rem 0.5rem',
                        borderRadius: '4px',
                      }}
                    >
                      DRY-RUN (Candidate proposal)
                    </span>
                  )}
                </div>

                {proposal.files_to_change && proposal.files_to_change.length > 0 && (
                  <div>
                    <h4 className="plan-section-title">
                      <span>📝</span>
                      <span>Proposed File Changes ({proposal.files_to_change.length})</span>
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {proposal.files_to_change.map((fc, idx) => (
                        <div
                          key={idx}
                          style={{
                            background: 'rgba(255, 255, 255, 0.02)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--radius-sm)',
                            padding: '0.65rem 0.85rem',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '0.75rem',
                          }}
                        >
                          <span className="meta-field-mono" style={{ color: '#67e8f9' }}>
                            {fc.path}
                          </span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                              {fc.description}
                            </span>
                            <span
                              style={{
                                fontSize: '0.7rem',
                                textTransform: 'uppercase',
                                padding: '0.15rem 0.4rem',
                                borderRadius: '4px',
                                fontWeight: 600,
                                background:
                                  fc.action === 'create'
                                    ? 'rgba(16, 185, 129, 0.15)'
                                    : 'rgba(245, 158, 11, 0.15)',
                                color: fc.action === 'create' ? '#34d399' : '#fbbf24',
                              }}
                            >
                              {fc.action}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {proposal.execution_steps && proposal.execution_steps.length > 0 && (
                  <div>
                    <h4 className="plan-section-title">
                      <span>🛠️</span>
                      <span>Execution Steps</span>
                    </h4>
                    <ul style={{ paddingLeft: '1.25rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                      {proposal.execution_steps.map((st, idx) => (
                        <li key={idx} style={{ marginBottom: '0.25rem' }}>
                          {st}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Candidate Unified Diffs for review before applying */}
                {proposal.diffs && proposal.diffs.length > 0 && (
                  <div>
                    <h4 className="plan-section-title">
                      <span>📄</span>
                      <span>Candidate Code Diff (Review Before Applying)</span>
                    </h4>
                    <DiffViewer
                      diffs={proposal.diffs}
                      title="Candidate Unified Diffs (Proposed Changes)"
                    />
                  </div>
                )}

                {canApplyProposal && (
                  <div
                    style={{
                      borderTop: '1px solid var(--border-subtle)',
                      paddingTop: '1rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      Ready to apply candidate patch to an isolated workspace
                    </span>
                    <button
                      id="apply-proposal-inline-btn"
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleApplyProposal}
                      disabled={isApplying}
                    >
                      {isApplying ? 'Applying Changes...' : '⚙️ Apply Proposal to Workspace'}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div
                className="card"
                style={{
                  textAlign: 'center',
                  padding: '2rem 1rem',
                  border: '1px dashed var(--border-subtle)',
                }}
              >
                {actionError && lastFailedAction === 'proposal' && (
                  <div
                    className="alert-banner warning"
                    style={{ marginBottom: '1rem', textAlign: 'left' }}
                  >
                    <span>⚠️</span>
                    <div style={{ flex: 1 }}>
                      <strong>Proposal generation failed:</strong> {actionError}
                    </div>
                  </div>
                )}
                <p style={{ marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                  No implementation proposal has been generated for this task yet.
                </p>
                <button
                  id="generate-proposal-empty-btn"
                  type="button"
                  className="btn btn-outline-accent btn-sm"
                  onClick={handleGenerateProposal}
                  disabled={isGeneratingProposal}
                >
                  {isGeneratingProposal ? 'Generating Proposal...' : '⚡ Generate Proposal via DeveloperAgent'}
                </button>
              </div>
            )}
          </div>

          {/* Section: Unified Diffs if applicationResult exists */}
          {applicationResult && applicationResult.diffs && applicationResult.diffs.length > 0 && (
            <div>
              <DiffViewer
                diffs={applicationResult.diffs}
                title="Applied Workspace Diffs (Isolated Sandbox)"
              />
            </div>
          )}

          {/* Section: Verification Diagnostics (if present) */}
          {currentTask.latest_verification && (
            <div>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                Latest Verification Run & Diagnostics
              </h3>
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <StatusBadge status={currentTask.latest_verification.status} size="sm" />
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      Profile: <strong>{currentTask.latest_verification.profile}</strong>
                    </span>
                  </div>

                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    Runner: <code>{currentTask.latest_verification.runner_id}</code> | Exit Code:{' '}
                    <strong>{currentTask.latest_verification.exit_code ?? 'N/A'}</strong> | Duration:{' '}
                    <strong>{currentTask.latest_verification.duration_seconds.toFixed(2)}s</strong>
                  </div>
                </div>

                {currentTask.latest_verification.error_message && (
                  <div className="alert-banner warning" style={{ margin: 0 }}>
                    <span>⚠️</span>
                    <span>{currentTask.latest_verification.error_message}</span>
                  </div>
                )}

                {/* Stdout Output Terminal */}
                {currentTask.latest_verification.stdout && (
                  <div className="terminal-window">
                    <div className="terminal-header">
                      <span>Standard Output (stdout)</span>
                      {currentTask.latest_verification.output_truncated && (
                        <span style={{ color: '#fbbf24' }}>[Truncated at 32KB]</span>
                      )}
                    </div>
                    <pre className="terminal-body">{currentTask.latest_verification.stdout}</pre>
                  </div>
                )}

                {/* Stderr Output Terminal */}
                {currentTask.latest_verification.stderr && (
                  <div className="terminal-window">
                    <div className="terminal-header" style={{ borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                      <span style={{ color: '#f87171' }}>Standard Error (stderr)</span>
                    </div>
                    <pre className="terminal-body error-stream">
                      {currentTask.latest_verification.stderr}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}
            </>
          )}
        </div>

        {/* Right Column: Metadata & Lifecycle Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="card">
            <h3 className="plan-section-title">
              <span>📊</span>
              <span>Lifecycle & Confinement</span>
            </h3>

            <div className="meta-field">
              <div className="meta-field-label">Current State</div>
              <div className="meta-field-value">
                <StatusBadge status={currentTask.status} />
              </div>
            </div>

            <div className="meta-field">
              <div className="meta-field-label">Workspace Isolation</div>
              <div className="meta-field-value">
                {currentTask.workspace_id ? (
                  <span className="meta-field-mono">{currentTask.workspace_id}</span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    No workspace allocated (Dry-run mode)
                  </span>
                )}
              </div>
            </div>

            <div className="meta-field">
              <div className="meta-field-label">Code Application Status</div>
              <div className="meta-field-value">
                {currentTask.application_status ? (
                  <span style={{ color: '#c084fc', textTransform: 'capitalize' }}>
                    {currentTask.application_status}
                  </span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Not applied</span>
                )}
              </div>
            </div>

            <div className="meta-field">
              <div className="meta-field-label">Verification Outcome</div>
              <div className="meta-field-value">
                {currentTask.verification_status ? (
                  <StatusBadge status={currentTask.verification_status} size="sm" />
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Unverified</span>
                )}
              </div>
            </div>

            <div className="meta-field">
              <div className="meta-field-label">Revision Budget</div>
              <div className="meta-field-value">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                  <div
                    style={{
                      flex: 1,
                      height: '8px',
                      background: 'rgba(255, 255, 255, 0.1)',
                      borderRadius: '4px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min((currentTask.revision_count / 3) * 100, 100)}%`,
                        height: '100%',
                        background:
                          currentTask.revision_count >= 3
                            ? '#ef4444'
                            : currentTask.revision_count > 0
                            ? '#f59e0b'
                            : '#6366f1',
                      }}
                    />
                  </div>
                  <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                    {currentTask.revision_count}/3
                  </span>
                </div>
              </div>
            </div>

            {currentTask.error_summary && (
              <div className="meta-field" style={{ marginTop: '1rem' }}>
                <div className="meta-field-label" style={{ color: '#f87171' }}>
                  Error Summary
                </div>
                <div
                  style={{
                    background: 'rgba(239, 68, 68, 0.08)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.5rem 0.75rem',
                    fontSize: '0.8125rem',
                    color: '#fca5a5',
                    marginTop: '0.25rem',
                  }}
                >
                  {currentTask.error_summary}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <h4 className="plan-section-title">
              <span>🔒</span>
              <span>Confinement Rules</span>
            </h4>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <div>• Workspace operations restricted to temporary sandbox</div>
              <div>• Credentials (.env, .git, .key) strictly blocked from copy</div>
              <div>• Path traversal (..) strictly rejected</div>
              <div>• DisabledSecurityRunner enforces fail-closed isolation</div>
            </div>
          </div>
        </div>
      </div>

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        taskId={currentTask.id}
        taskTitle={currentTask.task || ''}
        isDeleting={isDeleting}
        error={deleteError}
        onConfirm={handleDeleteTask}
        onCancel={() => {
          setShowDeleteModal(false);
          setDeleteError(null);
        }}
      />
    </div>
  );
};
