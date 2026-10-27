import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { DashboardPage } from '../pages/DashboardPage';
import { TaskDetailsPage } from '../pages/TaskDetailsPage';
import { apiClient } from '../services/apiClient';
import type { TaskRecord, TaskStepExecutionRecord } from '../types/api';

describe('Task Deletion and Computer Task Execution Workflows', () => {
  const mockTasks: TaskRecord[] = [
    {
      id: 'task-101',
      task: 'Open my GitHub',
      status: 'planned',
      task_type: 'computer_task',
      plan: {
        task: 'Open my GitHub',
        summary: 'Open GitHub in browser plan',
        task_type: 'computer_task',
        target_url: 'https://github.com',
        tool_steps: [
          {
            step_number: 1,
            description: 'Open GitHub homepage in default browser',
            tool: 'browser',
            action: 'open_url',
            parameters: { url: 'https://github.com' },
            expected_outcome: 'GitHub homepage opened in default browser',
            requires_approval: false,
          },
        ],
        steps: ['1. Open GitHub URL'],
        files_to_inspect: [],
        acceptance_criteria: ['Browser launched successfully'],
        tests_to_run: [],
        risks: [],
      },
      created_at: '2026-10-13T10:00:00Z',
      updated_at: '2026-10-13T10:00:00Z',
      revision_count: 0,
    },
    {
      id: 'task-102',
      task: 'Add version endpoint',
      status: 'planned',
      task_type: 'sdlc_task',
      plan: {
        task: 'Add version endpoint',
        summary: 'Add version endpoint plan',
        steps: ['1. Add endpoint'],
        files_to_inspect: [],
        acceptance_criteria: [],
        tests_to_run: [],
        risks: [],
      },
      created_at: '2026-10-13T11:00:00Z',
      updated_at: '2026-10-13T11:00:00Z',
      revision_count: 0,
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('Dashboard: opens confirmation dialog on Delete click and cancels safely without deleting', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'deleteTask').mockResolvedValue({
      task_id: 'task-101',
      success: true,
      message: 'Task task-101 successfully deleted',
    });

    render(
      <DashboardPage
        tasks={mockTasks}
        loading={false}
        error={null}
        onSelectTask={vi.fn()}
        onNavigateNewTask={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    // Initial tasks present
    expect(screen.getByTestId('task-card-task-101')).toBeDefined();
    expect(screen.getByTestId('task-card-task-102')).toBeDefined();

    // Click Delete on first task
    const deleteBtn = screen.getByRole('button', { name: 'Delete task task-101' });
    fireEvent.click(deleteBtn);

    // Modal dialog opens
    const modal = screen.getByTestId('delete-confirm-modal');
    expect(modal).toBeDefined();
    expect(screen.getByText('"Open my GitHub"')).toBeDefined();

    // Click Cancel in modal
    const cancelBtn = within(modal).getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    // Modal closes, task is still in dashboard, delete API was NOT called
    await waitFor(() => {
      expect(screen.queryByTestId('delete-confirm-modal')).toBeNull();
    });
    expect(deleteSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId('task-card-task-101')).toBeDefined();
  });

  it('Dashboard: confirms deletion, calls backend DELETE API, and removes task from list', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'deleteTask').mockResolvedValue({
      task_id: 'task-101',
      success: true,
      message: 'Task task-101 successfully deleted',
    });

    render(
      <DashboardPage
        tasks={mockTasks}
        loading={false}
        error={null}
        onSelectTask={vi.fn()}
        onNavigateNewTask={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    // Click Delete on first task
    const deleteBtn = screen.getByRole('button', { name: 'Delete task task-101' });
    fireEvent.click(deleteBtn);

    // Modal opens, confirm delete
    const modal = screen.getByTestId('delete-confirm-modal');
    const confirmBtn = within(modal).getByRole('button', { name: '🗑️ Delete Task' });
    fireEvent.click(confirmBtn);

    // delete API is called with task-101
    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('task-101');
    });

    // Task card disappears from list
    await waitFor(() => {
      expect(screen.queryByTestId('task-card-task-101')).toBeNull();
    });

    // Second task remains
    expect(screen.getByTestId('task-card-task-102')).toBeDefined();
  });

  it('TaskDetailsPage: opens delete modal, cancels safely without deleting', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'deleteTask');
    const onBack = vi.fn();

    render(
      <TaskDetailsPage
        task={mockTasks[0]}
        onBack={onBack}
        onRefreshTask={vi.fn().mockResolvedValue(mockTasks[0])}
      />
    );

    // Delete button in header
    const deleteHeaderBtn = screen.getByTitle('Delete this task');
    fireEvent.click(deleteHeaderBtn);

    // Confirmation modal opens
    const modal = screen.getByTestId('delete-confirm-modal');
    expect(modal).toBeDefined();
    expect(screen.getByText('"Open my GitHub"')).toBeDefined();

    // Click Cancel
    fireEvent.click(within(modal).getByRole('button', { name: 'Cancel' }));

    // Modal closes, onBack not called, delete not called
    await waitFor(() => {
      expect(screen.queryByTestId('delete-confirm-modal')).toBeNull();
    });
    expect(deleteSpy).not.toHaveBeenCalled();
    expect(onBack).not.toHaveBeenCalled();
  });

  it('TaskDetailsPage: confirms deletion, calls API, triggers callbacks and navigates back', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'deleteTask').mockResolvedValue({
      task_id: 'task-101',
      success: true,
      message: 'Task deleted',
    });
    const onBack = vi.fn();
    const onTaskDeleted = vi.fn();

    render(
      <TaskDetailsPage
        task={mockTasks[0]}
        onBack={onBack}
        onRefreshTask={vi.fn().mockResolvedValue(mockTasks[0])}
        onTaskDeleted={onTaskDeleted}
      />
    );

    // Click delete header button
    fireEvent.click(screen.getByTitle('Delete this task'));

    // Confirm deletion inside modal
    const modal = screen.getByTestId('delete-confirm-modal');
    fireEvent.click(within(modal).getByRole('button', { name: '🗑️ Delete Task' }));

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('task-101');
      expect(onTaskDeleted).toHaveBeenCalledWith('task-101');
      expect(onBack).toHaveBeenCalledTimes(1);
    });
  });

  it('TaskDetailsPage: renders computer task tool steps and triggers execution', async () => {
    const completedStep: TaskStepExecutionRecord = {
      id: 'step-exec-1',
      task_id: 'task-101',
      step_number: 1,
      step_description: 'Open GitHub homepage in browser',
      tool_name: 'browser',
      action: 'open_url',
      parameters_json: JSON.stringify({ url: 'https://github.com' }),
      status: 'completed',
      output_json: JSON.stringify({ url: 'https://github.com', opened: true }),
      error_message: null,
      duration_seconds: 0.25,
      requires_approval: false,
      started_at: '2026-10-13T10:01:00Z',
    };

    const executedTask: TaskRecord = {
      ...mockTasks[0],
      status: 'completed',
      execution_summary: 'All 1 tool execution step(s) completed and verified successfully.',
      step_executions: [completedStep],
    };

    vi.spyOn(apiClient, 'executeTask').mockResolvedValue(executedTask);

    const onRefresh = vi.fn().mockResolvedValue(executedTask);

    render(
      <TaskDetailsPage
        task={mockTasks[0]}
        onBack={vi.fn()}
        onRefreshTask={onRefresh}
      />
    );

    // Initial state: shows tool step plan
    expect(screen.getByText('Local Computer Tool Execution')).toBeDefined();
    expect(screen.getAllByText(/browser/i).length).toBeGreaterThan(0);

    // Click Execute Task button
    const executeBtn = screen.getByRole('button', { name: /⚡ Execute Task/i });
    fireEvent.click(executeBtn);

    // Verify executeTask API was invoked
    await waitFor(() => {
      expect(apiClient.executeTask).toHaveBeenCalledWith('task-101', false);
    });
  });
});
