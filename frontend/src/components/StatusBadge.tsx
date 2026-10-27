import React from 'react';
import type { LifecycleStatus } from '../types/api';

interface StatusBadgeProps {
  status: LifecycleStatus | string;
  size?: 'sm' | 'md';
  id?: string;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; icon: string; className: string }
> = {
  planned: {
    label: 'Planned',
    icon: '📋',
    className: 'planned',
  },
  proposed: {
    label: 'Proposal Ready',
    icon: '💡',
    className: 'proposed',
  },
  changes_applied: {
    label: 'Changes Applied',
    icon: '⚙️',
    className: 'changes_applied',
  },
  verifying: {
    label: 'Verifying...',
    icon: '⏳',
    className: 'verifying',
  },
  verified: {
    label: 'Verified',
    icon: '✅',
    className: 'verified',
  },
  verification_failed: {
    label: 'Verification Failed',
    icon: '❌',
    className: 'verification_failed',
  },
  verification_blocked: {
    label: 'Verification Blocked',
    icon: '🛡️',
    className: 'verification_blocked',
  },
  verification_timed_out: {
    label: 'Verification Timed Out',
    icon: '⏱️',
    className: 'verification_timed_out',
  },
  verification_error: {
    label: 'Verification Error',
    icon: '⚠️',
    className: 'verification_error',
  },
  queued: {
    label: 'Queued',
    icon: '⏳',
    className: 'planned',
  },
  analyzing: {
    label: 'Analyzing Environment',
    icon: '🔍',
    className: 'verifying',
  },
  planning: {
    label: 'Planning Execution',
    icon: '📐',
    className: 'proposed',
  },
  executing: {
    label: 'Executing Action',
    icon: '⚡',
    className: 'verifying',
  },
  ready: {
    label: 'Ready',
    icon: '⚡',
    className: 'planned',
  },
  in_progress: {
    label: 'In Progress',
    icon: '⚙️',
    className: 'verifying',
  },
  completed: {
    label: 'Completed',
    icon: '✅',
    className: 'verified',
  },
  partially_completed: {
    label: 'Partially Completed',
    icon: '⚠️',
    className: 'proposed',
  },
  failed: {
    label: 'Failed',
    icon: '❌',
    className: 'verification_failed',
  },
  blocked: {
    label: 'Blocked',
    icon: '⚠️',
    className: 'verification_blocked',
  },
  cancelled: {
    label: 'Cancelled',
    icon: '⏹️',
    className: 'verification_blocked',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  id,
}) => {
  const normStatus = (status || 'planned').toLowerCase();
  const config = STATUS_CONFIG[normStatus] || {
    label: status || 'Unknown',
    icon: '•',
    className: 'planned',
  };

  const inlineStyle = size === 'sm' ? { fontSize: '0.7rem', padding: '0.15rem 0.5rem' } : undefined;

  return (
    <span
      id={id}
      className={`status-badge ${config.className}`}
      style={inlineStyle}
      title={`Lifecycle status: ${config.label}`}
      data-testid="status-badge"
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
};
