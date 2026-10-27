import type {
  CodeApplicationResult,
  HealthResponse,
  ImplementationProposal,
  Plan,
  PlanRequest,
  ReviewReport,
  TaskCreateRequest,
  TaskRecord,
  TaskStepExecutionRecord,
  VerificationResult,
} from '../types/api';

/**
 * Resolves the configured API base URL with trailing slash stripped.
 */
export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  const baseUrl = (envUrl && typeof envUrl === 'string' ? envUrl.trim() : '') || 'http://localhost:8000';
  return baseUrl.replace(/\/+$/, '');
}

export class ApiClientError extends Error {
  status?: number;
  detail?: string;

  constructor(message: string, status?: number, detail?: string) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Core HTTP helper that handles JSON serialization, error unwrapping, and network failures.
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    throw new ApiClientError(
      `Unable to reach backend at ${baseUrl}: ${errorMsg}. Ensure the Autonomous SDLC Engine backend is running.`,
      undefined,
      errorMsg
    );
  }

  if (!response.ok) {
    let errorDetail = '';
    try {
      const errorJson = await response.json();
      if (typeof errorJson?.detail === 'string') {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson?.detail)) {
        errorDetail = errorJson.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
      } else if (errorJson) {
        errorDetail = JSON.stringify(errorJson);
      }
    } catch {
      errorDetail = await response.text().catch(() => '');
    }

    const message = errorDetail || `Request failed with HTTP status ${response.status} (${response.statusText})`;
    throw new ApiClientError(message, response.status, errorDetail);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiClientError('Response from server was not valid JSON.', response.status);
  }
}

export const apiClient = {
  /**
   * Health check endpoint to verify backend operational readiness.
   */
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health');
  },

  /**
   * List all persisted tasks with plans and lifecycle status.
   */
  async listTasks(): Promise<TaskRecord[]> {
    return request<TaskRecord[]>('/tasks');
  },

  /**
   * Fetch a single task by ID.
   */
  async getTask(taskId: string): Promise<TaskRecord> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<TaskRecord>(`/tasks/${encodeURIComponent(cleanId)}`);
  },

  /**
   * Preview a task plan without persisting it.
   */
  async createPlanPreview(task: string): Promise<Plan> {
    const cleanTask = task.trim();
    if (!cleanTask) {
      throw new ApiClientError('Task description cannot be empty or whitespace only.', 422);
    }
    const payload: PlanRequest = { task: cleanTask };
    return request<Plan>('/tasks/plan', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create, plan, and persist a new task. Pass execute_immediately=true to
   * have the backend run the task immediately after planning (one round-trip).
   */
  async createTask(task: string, executeImmediately = false): Promise<TaskRecord> {
    const cleanTask = task.trim();
    if (!cleanTask) {
      throw new ApiClientError('Task description cannot be empty or whitespace only.', 422);
    }
    const payload: TaskCreateRequest = { task: cleanTask, execute_immediately: executeImmediately };
    return request<TaskRecord>('/tasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Generate an implementation proposal for an existing task.
   */
  async createTaskProposal(taskId: string): Promise<ImplementationProposal> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<ImplementationProposal>(`/tasks/${encodeURIComponent(cleanId)}/proposal`, {
      method: 'POST',
    });
  },

  /**
   * Audit code changes using CodeReviewerAgent for security and quality gates.
   */
  async reviewTaskProposal(
    taskId: string,
    fileContents?: Record<string, string>
  ): Promise<ReviewReport> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<ReviewReport>(`/tasks/${encodeURIComponent(cleanId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ file_contents: fileContents || null }),
    });
  },

  /**
   * Apply a proposed implementation to an isolated workspace.
   */
  async applyTaskProposal(
    taskId: string,
    fileContents?: Record<string, string>
  ): Promise<CodeApplicationResult> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    const body = fileContents ? JSON.stringify({ file_contents: fileContents }) : undefined;
    return request<CodeApplicationResult>(`/tasks/${encodeURIComponent(cleanId)}/apply`, {
      method: 'POST',
      body,
    });
  },

  /**
   * Run verification on an applied workspace.
   */
  async verifyTask(taskId: string, profile: string = 'pytest_standard'): Promise<VerificationResult> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<VerificationResult>(`/tasks/${encodeURIComponent(cleanId)}/verify`, {
      method: 'POST',
      body: JSON.stringify({ profile }),
    });
  },

  /**
   * Permanently delete a task record and its logs from the database.
   */
  async deleteTask(taskId: string): Promise<{ success: boolean; message: string; task_id: string }> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<{ success: boolean; message: string; task_id: string }>(
      `/tasks/${encodeURIComponent(cleanId)}`,
      {
        method: 'DELETE',
      }
    );
  },

  /**
   * Execute real local computer task steps sequentially with outcome verification.
   */
  async executeTask(taskId: string, approved: boolean = false): Promise<TaskRecord> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<TaskRecord>(`/tasks/${encodeURIComponent(cleanId)}/execute`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    });
  },

  /**
   * Fetch detailed step-by-step tool execution history for a task.
   */
  async getTaskExecutions(taskId: string): Promise<TaskStepExecutionRecord[]> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<TaskStepExecutionRecord[]>(`/tasks/${encodeURIComponent(cleanId)}/executions`);
  },

  /**
   * Request cancellation of a running task execution.
   */
  async cancelTask(taskId: string): Promise<{ success: boolean; cancelled: boolean; message: string }> {
    const cleanId = taskId.trim();
    if (!cleanId) {
      throw new ApiClientError('Task ID is required.', 400);
    }
    return request<{ success: boolean; cancelled: boolean; message: string }>(
      `/tasks/${encodeURIComponent(cleanId)}/cancel`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Probes the status of the Orbit AI Windows Local Agent.
   */
  async getLocalAgentStatus(): Promise<import('../types/api').LocalAgentStatusResponse> {
    try {
      return await request<import('../types/api').LocalAgentStatusResponse>('/local-agent/status');
    } catch {
      return {
        online: false,
        details: null,
        message: "Orbit AI Windows Local Agent is offline. Run 'python start_local_agent.py' to start.",
      };
    }
  },

  /**
   * Retrieves the pairing token for authenticating with the local agent.
   */
  async getLocalAgentToken(): Promise<{ token: string }> {
    return request<{ token: string }>('/local-agent/token');
  },

  /**
   * Requests application discovery on the host Windows machine.
   */
  async discoverApp(appName: string): Promise<import('../types/api').AppDiscoveryResponse> {
    return request<import('../types/api').AppDiscoveryResponse>('/local-agent/discover', {
      method: 'POST',
      body: JSON.stringify({ app_name: appName }),
    });
  },

  /**
   * Queries the Windows process table to see if an application is active.
   */
  async checkAppRunning(appName: string): Promise<import('../types/api').ProcessCheckResponse> {
    return request<import('../types/api').ProcessCheckResponse>('/local-agent/running', {
      method: 'POST',
      body: JSON.stringify({ app_name: appName }),
    });
  },
};

