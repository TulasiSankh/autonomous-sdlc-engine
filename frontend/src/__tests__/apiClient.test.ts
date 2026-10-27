import { describe, expect, it, vi, beforeEach } from 'vitest';
import { apiClient, ApiClientError, getApiBaseUrl } from '../services/apiClient';

describe('apiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('resolves the base URL without trailing slash', () => {
    const url = getApiBaseUrl();
    expect(url).toBeDefined();
    expect(url.endsWith('/')).toBe(false);
  });

  it('fetches backend health successfully', async () => {
    const mockHealth = {
      status: 'healthy',
      service: 'autonomous-sdlc-engine',
      version: '0.1.0',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    } as Response);

    const result = await apiClient.getHealth();
    expect(result).toEqual(mockHealth);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.objectContaining({ headers: expect.any(Headers) })
    );
  });

  it('lists tasks successfully', async () => {
    const mockTasks = [
      {
        id: 'task-100',
        task: 'Implement auth',
        status: 'planned',
        plan: {
          task: 'Implement auth',
          summary: 'Summary',
          steps: ['Step 1'],
          files_to_inspect: [],
          acceptance_criteria: [],
          tests_to_run: [],
          risks: [],
        },
        created_at: '2026-10-13T00:00:00Z',
        updated_at: '2026-10-13T00:00:00Z',
        revision_count: 0,
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockTasks,
    } as Response);

    const result = await apiClient.listTasks();
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('task-100');
  });

  it('fetches a single task by ID', async () => {
    const mockTask = {
      id: 'task-200',
      task: 'Fix issue',
      status: 'verified',
      plan: {
        task: 'Fix issue',
        summary: 'Plan',
        steps: [],
        files_to_inspect: [],
        acceptance_criteria: [],
        tests_to_run: [],
        risks: [],
      },
      created_at: '2026-10-13T00:00:00Z',
      updated_at: '2026-10-13T00:00:00Z',
      revision_count: 1,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockTask,
    } as Response);

    const result = await apiClient.getTask('task-200');
    expect(result.id).toBe('task-200');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-200'),
      expect.anything()
    );
  });

  it('handles 404 error when task does not exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: "Task with ID 'task-missing' not found." }),
    } as Response);

    await expect(apiClient.getTask('task-missing')).rejects.toThrow(ApiClientError);
    await expect(apiClient.getTask('task-missing')).rejects.toThrow("Task with ID 'task-missing' not found.");
  });

  it('rejects empty task when creating plan preview', async () => {
    await expect(apiClient.createPlanPreview('')).rejects.toThrow(
      'Task description cannot be empty or whitespace only.'
    );
    await expect(apiClient.createPlanPreview('   ')).rejects.toThrow(
      'Task description cannot be empty or whitespace only.'
    );
  });

  it('creates a task plan preview', async () => {
    const mockPlan = {
      task: 'Add tests',
      summary: 'Add unit tests',
      steps: ['1. Write test'],
      files_to_inspect: ['tests/'],
      acceptance_criteria: ['Passes'],
      tests_to_run: ['pytest -v'],
      risks: ['None'],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockPlan,
    } as Response);

    const plan = await apiClient.createPlanPreview('Add tests');
    expect(plan.summary).toBe('Add unit tests');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/plan'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ task: 'Add tests' }),
      })
    );
  });

  it('creates and persists a task', async () => {
    const mockCreated = {
      id: 'task-300',
      task: 'New feature',
      status: 'planned',
      plan: {
        task: 'New feature',
        summary: 'Feature plan',
        steps: [],
        files_to_inspect: [],
        acceptance_criteria: [],
        tests_to_run: [],
        risks: [],
      },
      created_at: '2026-10-13T00:00:00Z',
      updated_at: '2026-10-13T00:00:00Z',
      revision_count: 0,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockCreated,
    } as Response);

    const created = await apiClient.createTask('New feature');
    expect(created.id).toBe('task-300');
    expect(created.status).toBe('planned');
  });

  it('generates an implementation proposal', async () => {
    const mockProposal = {
      task_id: 'task-400',
      task: 'Refactor DB',
      status: 'proposed',
      summary: 'Proposal summary',
      files_to_change: [{ path: 'storage/db.py', action: 'modify', description: 'Modify DB' }],
      execution_steps: ['Step 1'],
      verification_commands: ['pytest -v'],
      dry_run: true,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockProposal,
    } as Response);

    const proposal = await apiClient.createTaskProposal('task-400');
    expect(proposal.task_id).toBe('task-400');
    expect(proposal.files_to_change).toHaveLength(1);
    expect(proposal.dry_run).toBe(true);
  });

  it('applies a task proposal to an isolated workspace', async () => {
    const mockAppResult = {
      task_id: 'task-500',
      workspace_id: 'ws_abc123',
      status: 'applied',
      summary: 'Applied 1 change',
      changed_files: ['api/routes/version.py'],
      diffs: [{ path: 'api/routes/version.py', change_type: 'added', diff: '+content' }],
      errors: [],
      applied_at: '2026-10-13T00:00:00Z',
      unified_diff: '+content',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAppResult,
    } as Response);

    const result = await apiClient.applyTaskProposal('task-500');
    expect(result.task_id).toBe('task-500');
    expect(result.status).toBe('applied');
    expect(result.workspace_id).toBe('ws_abc123');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-500/apply'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('runs verification on an applied workspace', async () => {
    const mockVerifResult = {
      request_id: 'req_001',
      workspace_id: 'ws_abc123',
      profile: 'pytest_standard',
      status: 'blocked',
      exit_code: null,
      duration_seconds: 0.05,
      stdout: '',
      stderr: '',
      output_truncated: false,
      timed_out: false,
      runner_id: 'disabled-host-protection',
      timestamp: '2026-10-13T00:00:00Z',
      error_message: 'Host execution disabled by security policy',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockVerifResult,
    } as Response);

    const result = await apiClient.verifyTask('task-500', 'pytest_standard');
    expect(result.status).toBe('blocked');
    expect(result.runner_id).toBe('disabled-host-protection');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/task-500/verify'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});
