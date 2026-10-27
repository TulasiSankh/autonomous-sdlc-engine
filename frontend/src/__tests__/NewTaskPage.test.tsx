import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { NewTaskPage } from '../pages/NewTaskPage';
import { apiClient } from '../services/apiClient';
import type { Plan, TaskRecord } from '../types/api';

describe('NewTaskPage component', () => {
  const mockPlan: Plan = {
    task: 'Add authentication middleware',
    summary: 'Strategic execution plan for authentication',
    steps: ['1. Create auth router', '2. Implement token verification'],
    files_to_inspect: ['api/main.py'],
    acceptance_criteria: ['Protected endpoints'],
    tests_to_run: ['pytest tests/test_auth.py'],
    risks: ['Edge case tokens'],
  };

  const mockCreatedTask: TaskRecord = {
    id: 'task-created-999',
    task: 'Add authentication middleware',
    status: 'planned',
    plan: mockPlan,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    revision_count: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders step indicator, header, and main textarea', () => {
    render(<NewTaskPage onTaskCreated={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getByTestId('new-task-page')).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Create a new task' })).toBeDefined();
    expect(screen.getByText('AI Agent Ready')).toBeDefined();
    expect(screen.getByText('Tell your AI engineering agent what you want to build or fix.')).toBeDefined();

    // Step indicators
    expect(screen.getByText('Describe Task')).toBeDefined();
    expect(screen.getByText('Review Plan')).toBeDefined();
    expect(screen.getByText('Create Task')).toBeDefined();

    // Main textarea
    const textarea = screen.getByPlaceholderText(/Add authentication middleware to protect API routes/);
    expect(textarea).toBeDefined();

    // Preview button initially disabled
    const previewBtn = screen.getByRole('button', { name: /Preview Execution Plan/ });
    expect((previewBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('populates textarea when clicking a quick-start suggestion chip', () => {
    render(<NewTaskPage onTaskCreated={vi.fn()} onCancel={vi.fn()} />);

    const authChip = screen.getByRole('button', { name: /Add authentication middleware/ });
    fireEvent.click(authChip);

    const textarea = screen.getByPlaceholderText(/Add authentication middleware to protect API routes/) as HTMLTextAreaElement;
    expect(textarea.value).toBe('Add authentication middleware');

    // Char count update
    expect(screen.getByText('29 characters')).toBeDefined();

    // Preview button is now enabled
    const previewBtn = screen.getByRole('button', { name: /Preview Execution Plan/ });
    expect((previewBtn as HTMLButtonElement).disabled).toBe(false);
  });

  it('calls createPlanPreview and renders plan preview upon clicking Preview Plan', async () => {
    vi.spyOn(apiClient, 'createPlanPreview').mockResolvedValue(mockPlan);

    render(<NewTaskPage onTaskCreated={vi.fn()} onCancel={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/Add authentication middleware to protect API routes/);
    fireEvent.change(textarea, { target: { value: 'Add authentication middleware' } });

    const previewBtn = screen.getByRole('button', { name: /Preview Execution Plan/ });
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(apiClient.createPlanPreview).toHaveBeenCalledWith('Add authentication middleware');
    });

    // Check that PlanCard and preview banner are rendered
    expect(screen.getByText(/Proposed Architecture Plan/)).toBeDefined();
    expect(screen.getByText('Strategic execution plan for authentication')).toBeDefined();
    expect(screen.getByText('1. Create auth router')).toBeDefined();

    // Action buttons in preview section
    expect(screen.getByRole('button', { name: /Edit Description/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /Create & Persist Task/ })).toBeDefined();
  });

  it('allows editing description and navigating back from preview', async () => {
    vi.spyOn(apiClient, 'createPlanPreview').mockResolvedValue(mockPlan);

    render(<NewTaskPage onTaskCreated={vi.fn()} onCancel={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/Add authentication middleware to protect API routes/);
    fireEvent.change(textarea, { target: { value: 'Add authentication middleware' } });

    const previewBtn = screen.getByRole('button', { name: /Preview Execution Plan/ });
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(screen.getByText('Strategic execution plan for authentication')).toBeDefined();
    });

    const editBtn = screen.getByRole('button', { name: /Edit Description/ });
    fireEvent.click(editBtn);

    // Textarea value is preserved
    expect((textarea as HTMLTextAreaElement).value).toBe('Add authentication middleware');
  });

  it('persists task via apiClient.createTask and invokes onTaskCreated', async () => {
    vi.spyOn(apiClient, 'createPlanPreview').mockResolvedValue(mockPlan);
    vi.spyOn(apiClient, 'createTask').mockResolvedValue(mockCreatedTask);
    const handleCreated = vi.fn();

    render(<NewTaskPage onTaskCreated={handleCreated} onCancel={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/Add authentication middleware to protect API routes/);
    fireEvent.change(textarea, { target: { value: 'Add authentication middleware' } });

    const previewBtn = screen.getByRole('button', { name: /Preview Execution Plan/ });
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(screen.getByText('Strategic execution plan for authentication')).toBeDefined();
    });

    const createBtn = screen.getByRole('button', { name: /Create & Persist Task/ });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(apiClient.createTask).toHaveBeenCalledWith('Add authentication middleware', expect.anything());
      expect(handleCreated).toHaveBeenCalledWith(mockCreatedTask);
    });
  });

  it('triggers onCancel when clicking Cancel or Back link', () => {
    const handleCancel = vi.fn();
    render(<NewTaskPage onTaskCreated={vi.fn()} onCancel={handleCancel} />);

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);
    expect(handleCancel).toHaveBeenCalledTimes(1);

    const backLink = screen.getByText('← Back to Dashboard');
    fireEvent.click(backLink);
    expect(handleCancel).toHaveBeenCalledTimes(2);
  });
});
