"""Task service module for managing SDLC task lifecycles and persistence."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from agents.developer import ImplementationProposal
from agents.planner import Plan, PlannerAgent
from services.verification_service import VerificationResult
from storage.database import Database, get_database

TASK_LIFECYCLE_STATES = (
    "queued",
    "analyzing",
    "planning",
    "planned",
    "ready",
    "in_progress",
    "executing",
    "proposed",
    "changes_applied",
    "verifying",
    "verified",
    "verification_failed",
    "verification_blocked",
    "verification_timed_out",
    "verification_error",
    "completed",
    "failed",
    "blocked",
    "cancelled",
)

VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "queued": {"analyzing", "planning", "planned", "executing", "in_progress", "ready", "cancelled", "blocked", "failed"},
    "analyzing": {"planning", "planned", "executing", "in_progress", "cancelled", "blocked", "failed"},
    "planning": {"planned", "ready", "executing", "in_progress", "cancelled", "blocked", "failed"},
    "planned": {"queued", "analyzing", "planning", "ready", "executing", "in_progress", "proposed", "changes_applied", "cancelled", "completed", "failed", "blocked"},
    "ready": {"executing", "in_progress", "cancelled", "blocked", "failed"},
    "in_progress": {"executing", "verifying", "completed", "failed", "blocked", "cancelled"},
    "executing": {"in_progress", "verifying", "completed", "failed", "blocked", "cancelled"},
    "proposed": {"proposed", "changes_applied", "in_progress", "executing", "cancelled", "blocked", "failed"},
    "changes_applied": {
        "changes_applied",
        "verifying",
        "verified",
        "verification_failed",
        "verification_blocked",
        "verification_timed_out",
        "verification_error",
        "completed",
        "failed",
        "blocked",
        "cancelled",
    },
    "verifying": {
        "verified",
        "verification_failed",
        "verification_blocked",
        "verification_timed_out",
        "verification_error",
        "completed",
        "failed",
        "blocked",
        "cancelled",
    },
    "verified": {"proposed", "changes_applied", "in_progress", "executing", "ready", "planned"},
    "verification_failed": {"proposed", "changes_applied", "verifying", "in_progress", "executing", "ready", "planned"},
    "verification_blocked": {"proposed", "changes_applied", "verifying", "in_progress", "executing", "ready", "planned"},
    "verification_timed_out": {"proposed", "changes_applied", "verifying", "in_progress", "executing", "ready", "planned"},
    "verification_error": {"proposed", "changes_applied", "verifying", "in_progress", "executing", "ready", "planned"},
    "completed": {"ready", "in_progress", "executing", "planned", "queued", "analyzing"},
    "failed": {"ready", "in_progress", "executing", "cancelled", "planned", "queued", "analyzing"},
    "blocked": {"ready", "in_progress", "executing", "cancelled", "planned", "queued", "analyzing"},
    "cancelled": {"ready", "in_progress", "executing", "planned", "queued", "analyzing"},
}

MAX_STORED_OUTPUT_BYTES = 32768  # 32 KB bound for persistent database stdout/stderr


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal SDLC task lifecycle transition is attempted."""
    pass


class VerificationAttemptRecord(BaseModel):
    """Structured persistent log of a single verification run."""

    id: str = Field(..., description="Unique verification attempt identifier.")
    task_id: str = Field(..., description="Associated task identifier.")
    workspace_id: str = Field(..., description="Workspace ID where verification ran.")
    profile: str = Field(..., description="Verification profile executed.")
    status: str = Field(..., description="Outcome status ('passed', 'failed', 'blocked', 'timed_out', 'error').")
    exit_code: Optional[int] = Field(None, description="Exit code if an actual process executed.")
    duration_seconds: float = Field(default=0.0, description="Duration of run in seconds.")
    stdout: str = Field(default="", description="Captured standard output (bounded).")
    stderr: str = Field(default="", description="Captured standard error (bounded).")
    output_truncated: bool = Field(default=False, description="Whether output was truncated.")
    timed_out: bool = Field(default=False, description="Whether execution timed out.")
    runner_id: str = Field(..., description="Runner mechanism identifier.")
    timestamp: str = Field(..., description="ISO 8601 timestamp.")
    error_message: Optional[str] = Field(None, description="Diagnostic error summary if failed or blocked.")


class VerificationDiagnostics(BaseModel):
    """Structured, sanitized diagnostic context from a verification attempt."""

    task_id: str = Field(..., description="Unique task identifier.")
    workspace_id: str = Field(..., description="Workspace ID where verification executed.")
    profile: str = Field(..., description="Verification profile executed.")
    status: str = Field(..., description="Outcome status ('failed', 'timed_out', 'error', 'blocked', 'passed').")
    exit_code: Optional[int] = Field(None, description="Process exit code if an actual process ran.")
    stdout_excerpt: str = Field(default="", description="Bounded standard output excerpt.")
    stderr_excerpt: str = Field(default="", description="Bounded standard error excerpt.")
    output_truncated: bool = Field(default=False, description="Whether output streams were truncated.")
    timed_out: bool = Field(default=False, description="Whether execution timed out.")
    runner_error: Optional[str] = Field(None, description="Runner error message or diagnostic detail.")
    attempt_id: Optional[str] = Field(None, description="Identifier of the verification attempt.")
    timestamp: str = Field(..., description="ISO 8601 timestamp of verification.")


def create_diagnostics_from_attempt(
    attempt: VerificationAttemptRecord, max_excerpt_length: int = 8192
) -> VerificationDiagnostics:
    """Extracts structured, bounded diagnostics from a VerificationAttemptRecord."""
    raw_stdout = attempt.stdout or ""
    raw_stderr = attempt.stderr or ""
    return VerificationDiagnostics(
        task_id=attempt.task_id,
        workspace_id=attempt.workspace_id,
        profile=attempt.profile,
        status=attempt.status,
        exit_code=attempt.exit_code,
        stdout_excerpt=raw_stdout[:max_excerpt_length],
        stderr_excerpt=raw_stderr[:max_excerpt_length],
        output_truncated=attempt.output_truncated or len(raw_stdout) > max_excerpt_length or len(raw_stderr) > max_excerpt_length,
        timed_out=attempt.timed_out,
        runner_error=attempt.error_message,
        attempt_id=attempt.id,
        timestamp=attempt.timestamp,
    )


class TaskStepExecutionRecord(BaseModel):
    """Structured persistent log of an individual tool step execution."""

    id: str = Field(..., description="Unique step execution identifier.")
    task_id: str = Field(..., description="Associated task identifier.")
    step_number: int = Field(..., description="1-indexed step number.")
    step_description: str = Field(..., description="Human-readable step description.")
    tool_name: str = Field(..., description="Executed tool name.")
    action: str = Field(..., description="Executed tool action.")
    parameters_json: str = Field(default="{}", description="JSON serialized parameters.")
    status: str = Field(..., description="'pending', 'running', 'completed', 'failed', 'blocked', 'cancelled'.")
    output_json: Optional[str] = Field(None, description="JSON serialized tool output.")
    error_message: Optional[str] = Field(None, description="Error message if step failed.")
    started_at: Optional[str] = Field(None, description="ISO timestamp when step started.")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when step finished.")
    duration_seconds: float = Field(default=0.0, description="Step duration in seconds.")
    requires_approval: bool = Field(default=False, description="Whether approval was required.")


class TaskRecord(BaseModel):
    """Structured representation of a persistent SDLC or computer task."""

    id: str = Field(..., description="Unique task identifier.")
    task: str = Field(..., description="Original task description.")
    status: str = Field(..., description="Current lifecycle status of the task.")
    plan: Plan = Field(..., description="Structured execution plan generated for the task.")
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")
    updated_at: str = Field(..., description="ISO 8601 last update timestamp.")
    workspace_id: Optional[str] = Field(None, description="Isolated workspace identifier if created.")
    proposal: Optional[ImplementationProposal] = Field(None, description="Latest proposal if generated.")
    application_status: Optional[str] = Field(None, description="Latest application status.")
    verification_status: Optional[str] = Field(None, description="Latest verification status.")
    error_summary: Optional[str] = Field(None, description="Concise error summary.")
    revision_count: int = Field(default=0, description="Number of patch revision iterations attempted.")
    latest_verification: Optional[VerificationAttemptRecord] = Field(
        None, description="Summary of latest verification run."
    )
    task_type: Optional[str] = Field(default="sdlc", description="'computer_task' or 'sdlc'.")
    execution_summary: Optional[str] = Field(None, description="Summary of computer task execution outcome.")
    completed_at: Optional[str] = Field(None, description="ISO timestamp of task completion.")
    step_executions: List[TaskStepExecutionRecord] = Field(default_factory=list, description="List of recorded tool execution steps.")


class TaskService:
    """Service orchestrating task creation, planning, and SQLite persistence."""

    def __init__(
        self,
        db: Optional[Database] = None,
        planner: Optional[PlannerAgent] = None,
    ) -> None:
        self.db: Database = db if db is not None else get_database()
        self.planner: PlannerAgent = planner if planner is not None else PlannerAgent()

    def create_task(self, task: str) -> TaskRecord:
        """Validates the task, generates an execution plan, and persists it as 'planned'.

        Args:
            task: Task description.

        Returns:
            The newly created and persisted TaskRecord.

        Raises:
            ValueError: If task validation fails.
        """
        # PlannerAgent validates task and generates structured Plan
        plan = self.planner.plan(task)

        task_id = f"task-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        status = "planned"
        task_type = getattr(plan, "task_type", "code_change") or "code_change"

        self.db.save_task(
            task_id=task_id,
            task=plan.task,
            plan_json=plan.model_dump_json(),
            status=status,
            created_at=now,
            updated_at=now,
            task_type=task_type,
        )

        return TaskRecord(
            id=task_id,
            task=plan.task,
            status=status,
            plan=plan,
            created_at=now,
            updated_at=now,
            task_type=task_type,
        )

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Retrieves a task by ID.

        Args:
            task_id: Unique task identifier.

        Returns:
            The TaskRecord if found, else None.
        """
        row = self.db.get_task(task_id)
        if not row:
            return None
        return self._row_to_record(row)

    def list_tasks(self) -> List[TaskRecord]:
        """Lists all saved tasks ordered by creation time descending.

        Returns:
            List of TaskRecord objects.
        """
        rows = self.db.list_tasks()
        return [self._row_to_record(row) for row in rows]

    def delete_task(self, task_id: str) -> bool:
        """Permanently deletes a task record from SQLite after verifying it is not executing.

        Never deletes user project files or unrelated directories.

        Args:
            task_id: Unique task identifier.

        Returns:
            True if deleted, False if task does not exist.

        Raises:
            ValueError: If the task is actively executing.
        """
        task = self.get_task(task_id)
        if not task:
            return False

        if task.status in {"in_progress", "verifying"}:
            raise ValueError(
                f"Cannot delete task '{task_id}' while it is actively executing ({task.status}). "
                "Please cancel execution or wait for it to finish first."
            )

        return self.db.delete_task(task_id)

    def transition_task_status(
        self,
        task_id: str,
        new_status: str,
        workspace_id: Optional[str] = None,
        proposal: Optional[ImplementationProposal] = None,
        application_status: Optional[str] = None,
        verification_status: Optional[str] = None,
        error_summary: Optional[str] = None,
        clear_error: bool = False,
        revision_count: Optional[int] = None,
        execution_summary: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> TaskRecord:
        """Transitions a task to a new lifecycle state if the transition is permitted.

        Args:
            task_id: Unique task identifier.
            new_status: Target lifecycle status.
            workspace_id: Optional workspace ID.
            proposal: Optional ImplementationProposal.
            application_status: Optional application status.
            verification_status: Optional verification status.
            error_summary: Optional concise error summary.
            clear_error: Whether to reset error summary to None.
            revision_count: Optional revision count to persist.
            execution_summary: Optional execution summary for computer tasks.
            completed_at: Optional ISO timestamp when task completed.

        Returns:
            Updated TaskRecord.

        Raises:
            ValueError: If task is missing or status is unknown.
            InvalidStateTransitionError: If the transition violates SDLC rules.
        """
        current_record = self.get_task(task_id)
        if current_record is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        if new_status not in TASK_LIFECYCLE_STATES:
            raise ValueError(
                f"Unknown task lifecycle status '{new_status}'. Allowed states: {TASK_LIFECYCLE_STATES}"
            )

        allowed_next = VALID_TRANSITIONS.get(current_record.status, set())
        if new_status not in allowed_next:
            raise InvalidStateTransitionError(
                f"Cannot transition task '{task_id}' from '{current_record.status}' to '{new_status}'. "
                f"Allowed transitions: {sorted(list(allowed_next))}"
            )

        now = datetime.now(timezone.utc).isoformat()
        proposal_json = proposal.model_dump_json() if proposal is not None else None

        self.db.update_task_fields(
            task_id=task_id,
            updated_at=now,
            status=new_status,
            workspace_id=workspace_id or current_record.workspace_id,
            proposal_json=proposal_json or (
                current_record.proposal.model_dump_json() if current_record.proposal else None
            ),
            application_status=application_status or current_record.application_status,
            verification_status=verification_status or current_record.verification_status,
            error_summary=error_summary,
            clear_error=clear_error,
            revision_count=revision_count if revision_count is not None else current_record.revision_count,
            execution_summary=execution_summary or current_record.execution_summary,
            completed_at=completed_at or (now if new_status == "completed" and not current_record.completed_at else current_record.completed_at),
        )

        updated = self.get_task(task_id)
        if updated is None:
            raise ValueError(f"Failed to reload task '{task_id}' after transition.")
        return updated

    def record_verification_attempt(
        self,
        task_id: str,
        verification_result: VerificationResult,
    ) -> VerificationAttemptRecord:
        """Persists a bounded verification attempt record in the database.

        Args:
            task_id: Associated task ID.
            verification_result: Outcome from VerificationService.

        Returns:
            VerificationAttemptRecord representing the stored entry.
        """
        attempt_id = f"verif-{uuid.uuid4().hex[:12]}"
        raw_stdout = verification_result.stdout or ""
        raw_stderr = verification_result.stderr or ""

        # Enforce bounded storage limits
        truncated = verification_result.output_truncated
        stdout_bytes = raw_stdout.encode("utf-8")
        if len(stdout_bytes) > MAX_STORED_OUTPUT_BYTES:
            raw_stdout = (
                stdout_bytes[:MAX_STORED_OUTPUT_BYTES].decode("utf-8", errors="ignore")
                + "\n... [DATABASE TRUNCATED STDOUT] ...\n"
            )
            truncated = True

        stderr_bytes = raw_stderr.encode("utf-8")
        if len(stderr_bytes) > MAX_STORED_OUTPUT_BYTES:
            raw_stderr = (
                stderr_bytes[:MAX_STORED_OUTPUT_BYTES].decode("utf-8", errors="ignore")
                + "\n... [DATABASE TRUNCATED STDERR] ...\n"
            )
            truncated = True

        record_dict = {
            "id": attempt_id,
            "task_id": task_id,
            "workspace_id": verification_result.workspace_id,
            "profile": verification_result.profile,
            "status": verification_result.status,
            "exit_code": verification_result.exit_code,
            "duration_seconds": verification_result.duration_seconds,
            "stdout": raw_stdout,
            "stderr": raw_stderr,
            "output_truncated": truncated,
            "timed_out": verification_result.timed_out,
            "runner_id": verification_result.runner_id,
            "timestamp": verification_result.timestamp,
            "error_message": verification_result.error_message,
        }

        self.db.save_verification_record(record_dict)

        return VerificationAttemptRecord(
            id=attempt_id,
            task_id=task_id,
            workspace_id=verification_result.workspace_id,
            profile=verification_result.profile,
            status=verification_result.status,
            exit_code=verification_result.exit_code,
            duration_seconds=verification_result.duration_seconds,
            stdout=raw_stdout,
            stderr=raw_stderr,
            output_truncated=truncated,
            timed_out=verification_result.timed_out,
            runner_id=verification_result.runner_id,
            timestamp=verification_result.timestamp,
            error_message=verification_result.error_message,
        )

    def get_verification_history(self, task_id: str) -> List[VerificationAttemptRecord]:
        """Retrieves all verification attempts for a task in chronological order.

        Args:
            task_id: Unique task identifier.

        Returns:
            List of VerificationAttemptRecord objects.
        """
        rows = self.db.get_verification_records(task_id)
        return [VerificationAttemptRecord.model_validate(r) for r in rows]

    def _row_to_record(self, row: Dict[str, Any]) -> TaskRecord:
        """Converts a SQLite row dictionary into a TaskRecord model."""
        plan_data = json.loads(row["plan_json"])
        plan = Plan.model_validate(plan_data)

        proposal = None
        if row.get("proposal_json"):
            try:
                proposal = ImplementationProposal.model_validate(json.loads(row["proposal_json"]))
            except Exception:
                proposal = None

        latest_verification = None
        latest_row = self.db.get_latest_verification_record(row["id"])
        if latest_row:
            try:
                latest_verification = VerificationAttemptRecord.model_validate(latest_row)
            except Exception:
                latest_verification = None

        step_executions: List[TaskStepExecutionRecord] = []
        try:
            step_rows = self.db.get_step_executions(row["id"])
            step_executions = [TaskStepExecutionRecord.model_validate(s) for s in step_rows]
        except Exception:
            step_executions = []

        return TaskRecord(
            id=row["id"],
            task=row["task"],
            status=row["status"],
            plan=plan,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            workspace_id=row.get("workspace_id"),
            proposal=proposal,
            application_status=row.get("application_status"),
            verification_status=row.get("verification_status"),
            error_summary=row.get("error_summary"),
            revision_count=int(row.get("revision_count") or 0),
            latest_verification=latest_verification,
            task_type=row.get("task_type") or "sdlc",
            execution_summary=row.get("execution_summary"),
            completed_at=row.get("completed_at"),
            step_executions=step_executions,
        )
