import React, { useRef, useState } from 'react';
import type { Plan, TaskRecord } from '../types/api';
import { ErrorBanner } from '../components/ErrorBanner';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PlanCard } from '../components/PlanCard';
import { RobotAvatar } from '../components/RobotAvatar';
import { apiClient } from '../services/apiClient';

interface NewTaskPageProps {
  onTaskCreated: (createdTask: TaskRecord) => void;
  onCancel: () => void;
}

interface QuickSuggestion {
  text: string;
  icon: string;
}

const QUICK_SUGGESTIONS: QuickSuggestion[] = [
  { text: 'Add authentication middleware', icon: '🔒' },
  { text: 'Implement structured JSON logging', icon: '📊' },
  { text: 'Add API rate limiting', icon: '⚡' },
  { text: 'Improve database health checks', icon: '🩺' },
];

export const NewTaskPage: React.FC<NewTaskPageProps> = ({ onTaskCreated, onCancel }) => {
  const [taskInput, setTaskInput] = useState<string>('');
  const [previewPlan, setPreviewPlan] = useState<Plan | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [executeImmediately, setExecuteImmediately] = useState<boolean>(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previewSectionRef = useRef<HTMLDivElement>(null);

  // Quick suggestion selection
  const handleSelectSuggestion = (suggestionText: string) => {
    setTaskInput(suggestionText);
    setPreviewPlan(null);
    setCurrentStep(1);
    if (error) setError(null);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  // Preview plan generation (dry-run, unsaved)
  const handlePreviewPlan = async () => {
    const trimmed = taskInput.trim();
    if (!trimmed) {
      setError('Please provide a task description before generating an execution plan.');
      return;
    }

    try {
      setError(null);
      setIsLoadingPreview(true);
      const plan = await apiClient.createPlanPreview(trimmed);
      setPreviewPlan(plan);
      setCurrentStep(2);
      // Smoothly scroll down to preview section
      setTimeout(() => {
        previewSectionRef.current?.scrollIntoView?.({ behavior: 'smooth' });
      }, 100);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to generate execution plan: ${msg}`);
      setPreviewPlan(null);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  // Persist task and navigate to Task Details page
  const handleCreateTask = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = taskInput.trim();
    if (!trimmed) {
      setError('Task description cannot be empty or whitespace only.');
      return;
    }

    try {
      setError(null);
      setIsSubmitting(true);
      setCurrentStep(3);
      // If executeImmediately is false, task is persisted as 'planned' so user can inspect and execute it step-by-step
      const created = await apiClient.createTask(trimmed, executeImmediately);
      onTaskCreated(created);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to create task: ${msg}`);
      setCurrentStep(previewPlan ? 2 : 1);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditDescription = () => {
    setCurrentStep(1);
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.scrollIntoView?.({ behavior: 'smooth' });
    }
  };

  return (
    <div className="container new-task-container" data-testid="new-task-page">
      {/* Top Breadcrumb Navigation */}
      <div className="breadcrumb">
        <span
          className="breadcrumb-link"
          onClick={onCancel}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') onCancel();
          }}
          aria-label="Return to Dashboard"
        >
          ← Back to Dashboard
        </span>
        <span>/</span>
        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Create a new task</span>
      </div>

      {/* Simple Step Indicator */}
      <nav className="task-step-indicator" aria-label="Task Creation Progress">
        <div className={`step-item ${currentStep === 1 ? 'active' : currentStep > 1 ? 'completed' : ''}`}>
          <span className="step-circle">{currentStep > 1 ? '✓' : '1'}</span>
          <span className="step-label">Describe Task</span>
        </div>

        <div className={`step-divider ${currentStep > 1 ? 'completed' : ''}`} />

        <div className={`step-item ${currentStep === 2 ? 'active' : currentStep > 2 ? 'completed' : ''}`}>
          <span className="step-circle">{currentStep > 2 ? '✓' : '2'}</span>
          <span className="step-label">Review Plan</span>
        </div>

        <div className={`step-divider ${currentStep === 3 ? 'completed' : ''}`} />

        <div className={`step-item ${currentStep === 3 ? 'active' : ''}`}>
          <span className="step-circle">3</span>
          <span className="step-label">Create Task</span>
        </div>
      </nav>

      {/* Page Header Card */}
      <header className="new-task-header-card">
        <div className="new-task-brand-row">
          <div className="new-task-icon-badge" aria-hidden="true">
            <RobotAvatar size={34} />
          </div>
          <div className="new-task-title-group">
            <div className="new-task-heading-row">
              <h1 className="new-task-title">Create a new task</h1>
              <span className="agent-ready-pill" title="AI engineering agent is online and ready">
                <span className="health-dot-pulsing" aria-hidden="true" /> AI Agent Ready
              </span>
            </div>
            <p className="new-task-subtitle">
              Tell your AI engineering agent what you want to build or fix.
            </p>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

      {/* Main Task Creation Card */}
      <section className="new-task-card" aria-label="Task Prompt Specification">
        <div className="task-input-section">
          <div className="task-label-row">
            <label htmlFor="task-description-input" className="task-input-label">
              What would you like your agent to do?
            </label>
            <span className="char-count">{taskInput.length} characters</span>
          </div>

          <p className="task-input-helper">
            Describe a feature, bug fix, or improvement. Your agent will analyze the task and prepare an execution plan.
          </p>

          <div className="textarea-wrapper">
            <textarea
              ref={textareaRef}
              id="task-description-input"
              className="task-description-textarea"
              placeholder="Example: Add authentication middleware to protect API routes and write tests for unauthorized requests..."
              value={taskInput}
              onChange={(e) => {
                setTaskInput(e.target.value);
                if (error) setError(null);
              }}
              rows={5}
              disabled={isSubmitting || isLoadingPreview}
              required
              aria-label="What would you like your agent to do?"
            />
          </div>

          {/* Quick-start Suggestions */}
          <div className="quick-suggestions-section">
            <span className="quick-suggestions-label">Quick-start suggestions:</span>
            <div className="quick-suggestions-chips">
              {QUICK_SUGGESTIONS.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="suggestion-chip"
                  onClick={() => handleSelectSuggestion(item.text)}
                  disabled={isSubmitting || isLoadingPreview}
                >
                  <span className="chip-icon" aria-hidden="true">{item.icon}</span>
                  <span>{item.text}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Card Footer Actions */}
        <div className="new-task-card-footer">
          <button
            type="button"
            className="btn btn-secondary btn-md"
            onClick={onCancel}
            disabled={isSubmitting || isLoadingPreview}
          >
            Cancel
          </button>

          <button
            id="preview-plan-btn"
            type="button"
            className="btn btn-primary btn-md btn-preview-plan"
            onClick={handlePreviewPlan}
            disabled={!taskInput.trim() || isSubmitting || isLoadingPreview}
          >
            {isLoadingPreview ? (
              <>
                <span className="spinner-icon" aria-hidden="true">⏳</span>
                <span>Analyzing Architecture...</span>
              </>
            ) : (
              <>
                <span aria-hidden="true">✨</span>
                <span>Preview Execution Plan</span>
              </>
            )}
          </button>
        </div>
      </section>

      {/* Loading Spinner for Preview */}
      {isLoadingPreview && (
        <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
          <LoadingSpinner message="PlannerAgent is analyzing architecture and formulating a structured execution plan..." />
        </div>
      )}

      {/* Execution Plan Preview Section (Step 2) */}
      {previewPlan && !isLoadingPreview && (
        <div ref={previewSectionRef} className="plan-preview-wrapper" aria-label="Execution Plan Preview">
          {/* Plan Status Banner */}
          <div className="plan-preview-banner">
            <div className="plan-preview-banner-text">
              <span>🎯</span>
              <span>Proposed Architecture Plan — Synthesized by PlannerAgent</span>
            </div>
            <span className="plan-preview-badge">Dry Run • Unsaved</span>
          </div>

          {/* Render Structured Plan */}
          <PlanCard plan={previewPlan} titlePrefix="Proposed Plan" />

          {/* Action Bar for Plan Confirmation */}
          <div className="plan-preview-actions-bar" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={executeImmediately}
                  onChange={(e) => setExecuteImmediately(e.target.checked)}
                  disabled={isSubmitting}
                />
                <span>Execute immediately on creation</span>
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-secondary btn-md"
                onClick={handleEditDescription}
                disabled={isSubmitting}
              >
                ← Edit Description
              </button>

              <button
                id="submit-create-task-btn"
                type="button"
                className="btn btn-primary btn-md btn-preview-plan"
                onClick={() => handleCreateTask()}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <span className="spinner-icon" aria-hidden="true">⏳</span>
                    <span>Persisting Task to SQLite...</span>
                  </>
                ) : (
                  <>
                    <span aria-hidden="true">🚀</span>
                    <span>Create & Persist Task</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
