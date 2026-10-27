/**
 * Typed contracts matching the FastAPI Autonomous SDLC Engine models.
 */

export type LifecycleStatus =
  | 'queued'
  | 'analyzing'
  | 'planning'
  | 'planned'
  | 'ready'
  | 'in_progress'
  | 'executing'
  | 'proposed'
  | 'changes_applied'
  | 'verifying'
  | 'verified'
  | 'verification_failed'
  | 'verification_blocked'
  | 'verification_timed_out'
  | 'verification_error'
  | 'completed'
  | 'failed'
  | 'blocked'
  | 'cancelled';

export interface ToolStep {
  step_number: number;
  description: string;
  tool: 'browser' | 'filesystem' | 'app_launcher' | 'command' | 'verification' | string;
  action: string;
  parameters: Record<string, unknown>;
  expected_outcome: string;
  requires_approval: boolean;
}

export interface Plan {
  task: string;
  summary: string;
  task_type?:
    | 'application_action'
    | 'browser_action'
    | 'filesystem_action'
    | 'composite_action'
    | 'command_action'
    | 'code_change'
    | 'unsupported'
    | 'computer_task'
    | 'sdlc'
    | string;
  steps: string[];
  tool_steps?: ToolStep[];
  files_to_inspect: string[];
  acceptance_criteria: string[];
  tests_to_run: string[];
  risks: string[];
  target_path?: string | null;
  target_url?: string | null;
  target_app?: string | null;
}

export interface ProposedFileChange {
  path: string;
  action: 'create' | 'modify' | string;
  description: string;
}

export interface ImplementationProposal {
  task_id: string;
  task: string;
  status: string;
  summary: string;
  files_to_change: ProposedFileChange[];
  execution_steps: string[];
  verification_commands: string[];
  dry_run: boolean;
  diffs?: FileDiff[];
}

export interface VerificationAttemptRecord {
  id: string;
  task_id: string;
  workspace_id: string;
  profile: string;
  status: 'passed' | 'failed' | 'blocked' | 'timed_out' | 'error' | string;
  exit_code?: number | null;
  duration_seconds: number;
  stdout: string;
  stderr: string;
  output_truncated: boolean;
  timed_out: boolean;
  runner_id: string;
  timestamp: string;
  error_message?: string | null;
}

export interface TaskStepExecutionRecord {
  id: string;
  task_id: string;
  step_number: number;
  step_description: string;
  tool_name: string;
  action: string;
  parameters_json: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked' | 'cancelled' | string;
  output_json?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds: number;
  requires_approval: boolean;
}

export interface TaskRecord {
  id: string;
  task: string;
  status: LifecycleStatus | string;
  plan: Plan;
  created_at: string;
  updated_at: string;
  workspace_id?: string | null;
  proposal?: ImplementationProposal | null;
  application_status?: string | null;
  verification_status?: string | null;
  error_summary?: string | null;
  revision_count: number;
  latest_verification?: VerificationAttemptRecord | null;
  task_type?:
    | 'application_action'
    | 'browser_action'
    | 'filesystem_action'
    | 'composite_action'
    | 'command_action'
    | 'code_change'
    | 'unsupported'
    | 'computer_task'
    | 'sdlc'
    | string;
  execution_summary?: string | null;
  completed_at?: string | null;
  step_executions?: TaskStepExecutionRecord[];
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface PlanRequest {
  task: string;
}

export interface TaskCreateRequest {
  task: string;
  execute_immediately?: boolean;
}

export interface FileDiff {
  path: string;
  change_type: string;
  diff: string;
}

export interface CodeApplicationResult {
  task_id: string;
  workspace_id: string;
  status: 'applied' | 'failed' | 'partial_failure' | string;
  summary: string;
  changed_files: string[];
  diffs: FileDiff[];
  errors: string[];
  applied_at: string;
  unified_diff: string;
}

export interface VerificationResult {
  request_id: string;
  workspace_id: string;
  profile: string;
  status: 'passed' | 'failed' | 'blocked' | 'timed_out' | 'error';
  exit_code?: number | null;
  duration_seconds: number;
  stdout: string;
  stderr: string;
  output_truncated: boolean;
  timed_out: boolean;
  runner_id: string;
  timestamp: string;
  error_message?: string | null;
}

export interface ApiError {
  status?: number;
  message: string;
  detail?: string;
}

export interface LocalAgentStatusDetails {
  status: string;
  agent: string;
  version: string;
  os: string;
  release: string;
  version_str: string;
  architecture: string;
  username: string;
  hostname: string;
}

export interface LocalAgentStatusResponse {
  online: boolean;
  details?: LocalAgentStatusDetails | null;
  message: string;
}

export interface AppDiscoveryResponse {
  app_name: string;
  is_installed: boolean;
  executable_path?: string | null;
  discovery_method?: string | null;
  version?: string | null;
  locations_checked?: string[];
  actionable_help?: string | null;
}

export interface ProcessCheckResponse {
  app_name: string;
  is_running: boolean;
  pids: number[];
  process_names: string[];
  details: Record<string, unknown>[];
  summary: string;
}

export interface ReviewFinding {
  severity: 'blocker' | 'warning' | 'info';
  category: 'security' | 'syntax' | 'correctness' | 'maintainability';
  file_path: string;
  line_number?: number | null;
  message: string;
  recommendation?: string | null;
}

export interface ReviewReport {
  verdict: 'approved' | 'approved_with_warnings' | 'rejected';
  summary: string;
  security_score: number;
  findings: ReviewFinding[];
  auto_approvable: boolean;
}

