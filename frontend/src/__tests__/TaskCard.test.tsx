import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskCard } from '../components/TaskCard';
import type { TaskRecord } from '../types/api';

describe('TaskCard component', () => {
  const mockTask: TaskRecord = {
    id: 'task-test-456',
    task: 'Create a folder in my E drive named MyProject and open it in VS Code',
    status: 'planned',
    task_type: 'computer_task',
    plan: {
      task: 'Create a folder in my E drive named MyProject and open it in VS Code',
      summary: 'Create folder in E drive and open in VS Code',
      task_type: 'computer_task',
      target_path: 'E:\\MyProject',
      target_app: 'VS Code',
      tool_steps: [
        {
          step_number: 1,
          description: 'Create directory E:\\MyProject',
          tool: 'filesystem',
          action: 'create_directory',
          parameters: { path: 'E:\\MyProject' },
          expected_outcome: 'Directory E:\\MyProject exists',
          requires_approval: false,
        },
        {
          step_number: 2,
          description: 'Launch VS Code with project directory',
          tool: 'app_launcher',
          action: 'launch',
          parameters: { app: 'code', target_path: 'E:\\MyProject' },
          expected_outcome: 'VS Code launched with E:\\MyProject',
          requires_approval: false,
        },
      ],
      steps: ['1. Create folder', '2. Open VS Code'],
      files_to_inspect: [],
      acceptance_criteria: ['Directory created and app launched'],
      tests_to_run: [],
      risks: [],
    },
    created_at: '2026-10-13T12:00:00Z',
    updated_at: '2026-10-13T12:00:00Z',
    revision_count: 0,
  };

  it('renders task card with title, id, status, and computer task plan summary', () => {
    render(
      <TaskCard
        task={mockTask}
        onSelect={vi.fn()}
      />
    );

    expect(screen.getByText('task-test-456')).toBeDefined();
    expect(
      screen.getByText('Create a folder in my E drive named MyProject and open it in VS Code')
    ).toBeDefined();
    expect(screen.getByText(/2 automated tool steps/i)).toBeDefined();
    expect(screen.getByText(/Ready for Execution/i)).toBeDefined();
  });

  it('has a visible Delete button and clicking it does NOT trigger onSelect', () => {
    const handleSelect = vi.fn();
    const handleDelete = vi.fn();

    render(
      <TaskCard
        task={mockTask}
        onSelect={handleSelect}
        onDelete={handleDelete}
      />
    );

    const deleteBtn = screen.getByRole('button', { name: 'Delete task task-test-456' });
    expect(deleteBtn).toBeDefined();

    // Clicking delete button
    fireEvent.click(deleteBtn);

    // onDelete must be called with the task id
    expect(handleDelete).toHaveBeenCalledTimes(1);
    expect(handleDelete).toHaveBeenCalledWith('task-test-456');

    // onSelect must NOT be called (event propagation stopped)
    expect(handleSelect).not.toHaveBeenCalled();
  });

  it('triggers onSelect when card body or View Details button is clicked', () => {
    const handleSelect = vi.fn();

    render(
      <TaskCard
        task={mockTask}
        onSelect={handleSelect}
      />
    );

    const viewDetailsBtn = screen.getByRole('button', { name: 'View Details →' });
    fireEvent.click(viewDetailsBtn);

    expect(handleSelect).toHaveBeenCalledWith('task-test-456');
  });

  it('displays verified outcome tag when computer task is completed', () => {
    const completedTask: TaskRecord = {
      ...mockTask,
      status: 'completed',
    };

    render(
      <TaskCard
        task={completedTask}
        onSelect={vi.fn()}
      />
    );

    expect(screen.getByText(/Execution Verified/i)).toBeDefined();
  });
});
