import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../components/StatusBadge';

describe('StatusBadge component', () => {
  it('renders planned status correctly', () => {
    render(<StatusBadge status="planned" id="test-badge-planned" />);
    const badge = screen.getByTestId('status-badge');
    expect(badge).toBeDefined();
    expect(badge.textContent).toContain('Planned');
    expect(badge.className).toContain('planned');
  });

  it('renders verified status correctly', () => {
    render(<StatusBadge status="verified" />);
    const badge = screen.getByTestId('status-badge');
    expect(badge.textContent).toContain('Verified');
    expect(badge.className).toContain('verified');
  });

  it('renders changes_applied status correctly', () => {
    render(<StatusBadge status="changes_applied" />);
    const badge = screen.getByTestId('status-badge');
    expect(badge.textContent).toContain('Changes Applied');
    expect(badge.className).toContain('changes_applied');
  });

  it('renders verification_failed status correctly', () => {
    render(<StatusBadge status="verification_failed" />);
    const badge = screen.getByTestId('status-badge');
    expect(badge.textContent).toContain('Verification Failed');
    expect(badge.className).toContain('verification_failed');
  });

  it('renders verification_blocked status correctly', () => {
    render(<StatusBadge status="verification_blocked" />);
    const badge = screen.getByTestId('status-badge');
    expect(badge.textContent).toContain('Verification Blocked');
    expect(badge.className).toContain('verification_blocked');
  });

  it('renders computer task statuses correctly', () => {
    const statuses = [
      { status: 'ready', text: 'Ready', cls: 'planned' },
      { status: 'in_progress', text: 'In Progress', cls: 'verifying' },
      { status: 'completed', text: 'Completed', cls: 'verified' },
      { status: 'failed', text: 'Failed', cls: 'verification_failed' },
      { status: 'blocked', text: 'Blocked', cls: 'verification_blocked' },
      { status: 'cancelled', text: 'Cancelled', cls: 'verification_blocked' },
    ] as const;

    statuses.forEach(({ status, text, cls }) => {
      const { unmount } = render(<StatusBadge status={status} />);
      const badge = screen.getByTestId('status-badge');
      expect(badge.textContent).toContain(text);
      expect(badge.className).toContain(cls);
      unmount();
    });
  });

  it('handles unknown status fallback gracefully', () => {
    render(<StatusBadge status="custom_state" />);
    const badge = screen.getByTestId('status-badge');
    expect(badge.textContent).toContain('custom_state');
  });
});
