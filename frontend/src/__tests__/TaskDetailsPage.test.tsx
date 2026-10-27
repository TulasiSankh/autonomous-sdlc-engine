import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { TaskDetailsPage } from '../pages/TaskDetailsPage';
import { apiClient } from '../services/apiClient';
import type { ImplementationProposal, TaskRecord } from '../types/api';

describe('TaskDetailsPage - DeveloperAgent Proposal Workflow', () => {
  const mockPlannedTask: TaskRecord = {
    id: 'task-test-001',
    task: 'Add health check probe and version metadata',
    status: 'planned',
    plan: {
      task: 'Add health check probe and version metadata',
      summary: 'Inspect API routers and add version metadata probe',
      steps: [
        '1. Inspect api/main.py and api/routes/',
        '2. Propose new version endpoint in api/routes/version.py',
      ],
      files_to_inspect: ['api/main.py', 'api/routes/version.py'],
      acceptance_criteria: ['Returns 200 with application version'],
      tests_to_run: ['pytest tests/test_version.py'],
      risks: ['Ensure port binding unaffected'],
    },
    created_at: '2026-10-13T10:00:00Z',
    updated_at: '2026-10-13T10:00:00Z',
    revision_count: 0,
  };

  const mockGeneratedProposal: ImplementationProposal = {
    task_id: 'task-test-001',
    task: 'Add health check probe and version metadata',
    status: 'proposed',
    summary: "Implementation proposal for task 'Add health check probe and version metadata'. Proposes 1 file change(s).",
    files_to_change: [
      {
        path: 'api/routes/version.py',
        action: 'create',
        description: "Create module 'api/routes/version.py' to implement task requirements.",
      },
    ],
    execution_steps: [
      '[Proposed] 1. Inspect api/main.py and api/routes/',
      '[Proposed] 2. Propose new version endpoint in api/routes/version.py',
    ],
    verification_commands: ['pytest tests/test_version.py'],
    dry_run: true,
    diffs: [
      {
        path: 'api/routes/version.py',
        change_type: 'added',
        diff: [
          '--- /dev/null',
          '+++ b/api/routes/version.py',
          '@@ -0,0 +1,5 @@',
          '+"""Implementation for: Add health check probe and version metadata"""',
          '+',
          '+# Proposed action: Create module api/routes/version.py',
        ].join('\n'),
      },
    ],
  };

  const mockProposedTask: TaskRecord = {
    ...mockPlannedTask,
    status: 'proposed',
    proposal: mockGeneratedProposal,
    updated_at: '2026-10-13T10:05:00Z',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders planned task with empty proposal state and generate proposal buttons', () => {
    render(
      <TaskDetailsPage
        task={mockPlannedTask}
        onBack={vi.fn()}
        onRefreshTask={vi.fn().mockResolvedValue(mockPlannedTask)}
      />
    );

    expect(screen.getByTestId('task-details-page')).toBeDefined();
    expect(screen.getAllByText('task-test-001').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Add health check probe and version metadata').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('No implementation proposal has been generated for this task yet.')).toBeDefined();

    // Primary action button available in header
    expect(screen.getByRole('button', { name: '⚡ Generate Proposal' })).toBeDefined();
  });

  it('generates proposal, renders candidate diffs, and updates lifecycle state', async () => {
    const onRefreshTask = vi.fn().mockResolvedValue(mockProposedTask);
    vi.spyOn(apiClient, 'createTaskProposal').mockResolvedValue(mockGeneratedProposal);

    render(
      <TaskDetailsPage
        task={mockPlannedTask}
        onBack={vi.fn()}
        onRefreshTask={onRefreshTask}
      />
    );

    const generateBtn = screen.getByRole('button', { name: '⚡ Generate Proposal' });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(apiClient.createTaskProposal).toHaveBeenCalledWith('task-test-001');
      expect(onRefreshTask).toHaveBeenCalledWith('task-test-001');
    });

    // Check that success notice is displayed
    expect(
      screen.getByText(/Implementation proposal formulated by DeveloperAgent with candidate diffs/i)
    ).toBeDefined();

    // Check that proposal summary is rendered
    expect(
      screen.getByText(/Implementation proposal for task 'Add health check probe and version metadata'/i)
    ).toBeDefined();

    // Check that proposed file changes and candidate diffs are rendered
    const pathElements = screen.getAllByText('api/routes/version.py');
    expect(pathElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('diff-viewer')).toBeDefined();
    expect(
      screen.getByText('+"""Implementation for: Add health check probe and version metadata"""')
    ).toBeDefined();

    // Check that Apply Proposal buttons are now available
    const applyButtons = screen.getAllByRole('button', { name: /Apply Proposal/ });
    expect(applyButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('displays error banner and provides retry option when proposal generation fails', async () => {
    const onRefreshTask = vi.fn().mockResolvedValue(mockProposedTask);
    const mockError = new Error('Task plan is missing required steps.');
    vi.spyOn(apiClient, 'createTaskProposal')
      .mockRejectedValueOnce(mockError)
      .mockResolvedValueOnce(mockGeneratedProposal);

    render(
      <TaskDetailsPage
        task={mockPlannedTask}
        onBack={vi.fn()}
        onRefreshTask={onRefreshTask}
      />
    );

    const generateBtn = screen.getByRole('button', { name: '⚡ Generate Proposal' });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      const banner = screen.getByTestId('error-banner');
      expect(within(banner).getByText(/DeveloperAgent failed to generate proposal/i)).toBeDefined();
    });

    // Retry proposal generation using ErrorBanner retry button
    const banner = screen.getByTestId('error-banner');
    const retryBtn = within(banner).getByRole('button', { name: /Retry/ });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(apiClient.createTaskProposal).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId('diff-viewer')).toBeDefined();
    });
  });

  it('renders candidate diffs directly when task already has a persisted proposal', () => {
    render(
      <TaskDetailsPage
        task={mockProposedTask}
        onBack={vi.fn()}
        onRefreshTask={vi.fn().mockResolvedValue(mockProposedTask)}
      />
    );

    // Should immediately display candidate diff viewer
    expect(screen.getByTestId('diff-viewer')).toBeDefined();
    const pathElements = screen.getAllByText('api/routes/version.py');
    expect(pathElements.length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText('+"""Implementation for: Add health check probe and version metadata"""')
    ).toBeDefined();

    // Regenerate Proposal button is available
    expect(screen.getByRole('button', { name: /Regenerate Proposal/ })).toBeDefined();
    // Apply Proposal button is available
    const applyButtons = screen.getAllByRole('button', { name: /Apply Proposal/ });
    expect(applyButtons.length).toBeGreaterThanOrEqual(1);
  });
});
