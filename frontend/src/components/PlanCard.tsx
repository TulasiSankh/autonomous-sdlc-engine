import React from 'react';
import type { Plan } from '../types/api';

interface PlanCardProps {
  plan: Plan;
  titlePrefix?: string;
}

export const PlanCard: React.FC<PlanCardProps> = ({ plan, titlePrefix = 'Execution Plan' }) => {
  if (!plan) return null;

  return (
    <div className="card plan-container" data-testid="plan-card">
      <div>
        <h3 className="plan-section-title">
          <span>🎯</span>
          <span>{titlePrefix} Summary</span>
        </h3>
        <div className="plan-summary-box">
          {plan.summary || `Strategic plan for task: ${plan.task}`}
        </div>
      </div>

      {plan.steps && plan.steps.length > 0 && (
        <div>
          <h4 className="plan-section-title">
            <span>🪜</span>
            <span>Execution Steps ({plan.steps.length})</span>
          </h4>
          <ol className="plan-steps-list">
            {plan.steps.map((step, idx) => (
              <li key={idx} className="plan-step-item">
                <span className="step-number">{idx + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {plan.files_to_inspect && plan.files_to_inspect.length > 0 && (
        <div>
          <h4 className="plan-section-title">
            <span>📁</span>
            <span>Candidate Files to Inspect ({plan.files_to_inspect.length})</span>
          </h4>
          <div className="tag-list">
            {plan.files_to_inspect.map((file, idx) => (
              <span key={idx} className="path-badge">
                <span aria-hidden="true">📄</span>
                <span>{file}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {plan.acceptance_criteria && plan.acceptance_criteria.length > 0 && (
        <div>
          <h4 className="plan-section-title">
            <span>✨</span>
            <span>Acceptance Criteria</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {plan.acceptance_criteria.map((criteria, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.5rem',
                  fontSize: '0.875rem',
                  color: 'var(--text-primary)',
                }}
              >
                <span style={{ color: '#34d399', fontWeight: 'bold' }}>✓</span>
                <span>{criteria}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {plan.tests_to_run && plan.tests_to_run.length > 0 && (
        <div>
          <h4 className="plan-section-title">
            <span>🧪</span>
            <span>Verification Commands</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {plan.tests_to_run.map((cmd, idx) => (
              <code key={idx} className="command-snippet">
                $ {cmd}
              </code>
            ))}
          </div>
        </div>
      )}

      {plan.risks && plan.risks.length > 0 && (
        <div>
          <h4 className="plan-section-title">
            <span>⚠️</span>
            <span>Technical Risks & Edge Cases</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {plan.risks.map((risk, idx) => (
              <div key={idx} className="risk-item">
                <span>⚡</span>
                <span>{risk}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
