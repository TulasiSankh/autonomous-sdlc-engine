"""Execution Engine module coordinating real local computer task execution."""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from agents.planner import Plan, ToolStep
from services.task_service import TaskRecord, TaskService
from storage.database import Database, get_database
from tools.base import ToolExecutionResult
from tools.registry import ToolRegistry, get_default_registry

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Coordinates sequential tool execution, verification, and lifecycle updates."""

    def __init__(
        self,
        task_service: Optional[TaskService] = None,
        tool_registry: Optional[ToolRegistry] = None,
        db: Optional[Database] = None,
        local_agent_client: Optional[Any] = None,
        require_local_agent: Optional[bool] = None,
    ) -> None:
        self.db = db or get_database()
        self.task_service = task_service or TaskService(db=self.db)
        self.registry = tool_registry or get_default_registry()
        self.local_agent_client = local_agent_client
        self.require_local_agent = require_local_agent
        self._cancelled_tasks: Set[str] = set()

    def request_cancellation(self, task_id: str) -> bool:
        """Flags a task execution for cancellation."""
        self._cancelled_tasks.add(task_id)
        task = self.task_service.get_task(task_id)
        if task and task.status in {"in_progress", "verifying"}:
            try:
                self.task_service.transition_task_status(
                    task_id=task_id,
                    new_status="cancelled",
                    error_summary="Execution was cancelled by the user.",
                )
                return True
            except Exception as e:
                logger.error(f"Error updating task status on cancellation: {e}")
        return False

    def is_cancelled(self, task_id: str) -> bool:
        """Checks if cancellation was requested for this task."""
        if task_id in self._cancelled_tasks:
            return True
        task = self.task_service.get_task(task_id)
        return bool(task and task.status == "cancelled")

    def execute_task(self, task_id: str, approved: bool = False) -> TaskRecord:
        """Executes all planned tool steps for a task sequentially with verification.

        Args:
            task_id: Unique task identifier.
            approved: Whether user explicitly approved actions flagged as requiring approval.

        Returns:
            Updated TaskRecord with final status and step executions.

        Raises:
            ValueError: If task not found or has invalid configuration.
        """
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        # Clear cancellation flag for fresh execution
        self._cancelled_tasks.discard(task_id)

        # Validate that task has executable steps
        tool_steps = task.plan.tool_steps or []
        if not tool_steps:
            if task.task_type in ("code_change", "sdlc"):
                raise ValueError(
                    f"Task '{task_id}' is a software engineering task ({task.task_type}). "
                    "Use the proposal, workspace, and verification workflow instead."
                )
            if task.task_type == "unsupported":
                self.task_service.transition_task_status(
                    task_id=task_id,
                    new_status="blocked",
                    error_summary="Requested operation is unsupported and cannot be executed.",
                )
                return self.task_service.get_task(task_id)  # type: ignore
            raise ValueError(f"Task '{task_id}' has no executable tool steps in its plan.")

        # Check for approval requirements
        unapproved_risky_steps = [s for s in tool_steps if s.requires_approval and not approved]
        if unapproved_risky_steps:
            step_names = ", ".join(f"Step {s.step_number} ({s.action})" for s in unapproved_risky_steps)
            self.task_service.transition_task_status(
                task_id=task_id,
                new_status="blocked",
                error_summary=f"Requires user approval before executing sensitive action(s): {step_names}.",
            )
            return self.task_service.get_task(task_id)  # type: ignore

        # Check local agent status if required or configured
        if task.task_type in ("application_action", "computer_task"):
            if self.local_agent_client is not None or self.require_local_agent:
                from services.local_agent_client import get_local_agent_client
                client = self.local_agent_client if self.local_agent_client is not None else get_local_agent_client()
                if not client.is_online():
                    err_msg = (
                        "Local Agent Offline: Orbit AI Windows Local Agent is not running on 127.0.0.1:8001. "
                        "Please start the service using 'python start_local_agent.py' to enable local PC control."
                    )
                    self.task_service.transition_task_status(
                        task_id=task_id,
                        new_status="blocked",
                        error_summary=err_msg,
                        execution_summary=err_msg,
                    )
                    return self.task_service.get_task(task_id)  # type: ignore

        # Transition task to in_progress / executing
        current_status = task.status
        if current_status not in ("in_progress", "executing"):
            try:
                self.task_service.transition_task_status(
                    task_id=task_id,
                    new_status="in_progress",
                    clear_error=True,
                )
            except Exception as e:
                logger.warning(f"Could not transition to in_progress from {current_status}: {e}")

        executed_steps: List[Dict[str, Any]] = []
        overall_success = True
        failure_reason: Optional[str] = None
        captured_pid: Optional[int] = None
        captured_mock_launched: bool = False
        captured_exit_code: Optional[int] = None

        for step in tool_steps:
            # Check for cancellation between steps
            if self.is_cancelled(task_id):
                logger.info(f"Task '{task_id}' cancelled before step {step.step_number}.")
                self._record_step(
                    task_id=task_id,
                    step=step,
                    status="cancelled",
                    error="Execution cancelled by user.",
                )
                self.task_service.transition_task_status(
                    task_id=task_id,
                    new_status="cancelled",
                    error_summary="Execution cancelled by user.",
                )
                return self.task_service.get_task(task_id)  # type: ignore

            # Record step as running
            step_record_id = self._record_step(
                task_id=task_id,
                step=step,
                status="running",
            )

            # Chain outputs between steps (e.g. forward launched PID or command exit_code)
            step_params = dict(step.parameters)
            if captured_pid is not None and "pid" not in step_params and step.action in ("verify_process_running", "verify_app_running", "verify_visible_window"):
                step_params["pid"] = captured_pid
            if captured_mock_launched and "mock_launched" not in step_params and step.action in ("verify_process_running", "verify_app_running", "verify_visible_window"):
                step_params["mock_launched"] = True
            if captured_exit_code is not None and "exit_code" not in step_params and step.action == "verify_command_result":
                step_params["exit_code"] = captured_exit_code

            start_time = time.time()
            try:
                result: ToolExecutionResult = self.registry.execute(
                    tool_name=step.tool,
                    action=step.action,
                    params=step_params,
                )
            except Exception as exc:
                result = ToolExecutionResult(
                    success=False,
                    error=f"Unhandled tool error in {step.tool}.{step.action}: {str(exc)}",
                )

            duration = round(time.time() - start_time, 3)

            # Capture process PID or mock launcher if launched
            if result.success and result.metadata:
                if result.metadata.get("mock_launched"):
                    captured_mock_launched = True
                if result.metadata.get("pid"):
                    try:
                        captured_pid = int(result.metadata["pid"])
                    except Exception:
                        pass
                if "exit_code" in result.metadata:
                    try:
                        captured_exit_code = int(result.metadata["exit_code"])
                    except Exception:
                        pass
            if result.success and isinstance(result.output, dict) and "exit_code" in result.output:
                try:
                    captured_exit_code = int(result.output["exit_code"])
                except Exception:
                    pass

            if result.success:
                self.db.update_step_execution(
                    step_id=step_record_id,
                    status="completed",
                    output_json=json.dumps(result.output or {}),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=duration,
                )
                executed_steps.append({
                    "step_number": step.step_number,
                    "action": step.action,
                    "success": True,
                    "output": result.output,
                    "metadata": result.metadata or {},
                })
            else:
                overall_success = False
                failure_reason = result.error or "Unknown error occurred during step execution."
                is_blocked = (
                    (result.metadata and result.metadata.get("blocked", False))
                    or "not found" in failure_reason.lower()
                    or "does not exist" in failure_reason.lower()
                    or "permission denied" in failure_reason.lower()
                )
                step_status = "blocked" if is_blocked else "failed"
                self.db.update_step_execution(
                    step_id=step_record_id,
                    status=step_status,
                    error_message=failure_reason,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=duration,
                )
                executed_steps.append({
                    "step_number": step.step_number,
                    "action": step.action,
                    "success": False,
                    "blocked": is_blocked,
                    "error": failure_reason,
                    "metadata": result.metadata or {},
                })
                logger.warning(f"Step {step.step_number} {step_status}: {failure_reason}")
                # Stop on failure for safety
                break

        # Verification Phase
        if overall_success and not self.is_cancelled(task_id):
            try:
                self.task_service.transition_task_status(task_id=task_id, new_status="verifying")
            except Exception:
                pass

            verification_passed, verif_msg = self._verify_outcome(task.plan, executed_steps)

            if verification_passed:
                summary_text = self._build_success_summary(task.plan, executed_steps)
                self.task_service.transition_task_status(
                    task_id=task_id,
                    new_status="completed",
                    verification_status="passed",
                    execution_summary=summary_text,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    clear_error=True,
                )
            else:
                # Differentiate between partial launch vs complete failure
                launched_step = any(s.get("action") in ("launch", "open_in_app") and s.get("success") for s in executed_steps)
                new_status = "partially_completed" if launched_step else "failed"
                summary_text = f"Application launched, but visible window verification failed: {verif_msg}" if launched_step else f"Tool execution finished, but outcome verification failed: {verif_msg}"
                self.task_service.transition_task_status(
                    task_id=task_id,
                    new_status=new_status,
                    verification_status="failed",
                    error_summary=summary_text,
                    execution_summary=summary_text,
                )
        elif not self.is_cancelled(task_id):
            is_blocked = any(s.get("blocked") for s in executed_steps)
            new_status = "blocked" if is_blocked else "failed"
            error_text = f"Execution halted at step {len(executed_steps)}: {failure_reason}"
            self.task_service.transition_task_status(
                task_id=task_id,
                new_status=new_status,
                verification_status="failed" if not is_blocked else "blocked",
                error_summary=error_text,
                execution_summary=error_text,
            )

        updated_task = self.task_service.get_task(task_id)
        if updated_task is None:
            raise ValueError(f"Task '{task_id}' could not be retrieved after execution.")
        return updated_task

    def _verify_outcome(self, plan: Plan, executed_steps: List[Dict[str, Any]]) -> tuple[bool, str]:
        """Runs truthful outcome verification checks based on plan outcomes."""
        # If target_path is specified and filesystem action was taken, verify target path exists
        if plan.target_path:
            v_result = self.registry.execute(
                tool_name="verification",
                action="verify_path_exists",
                params={"path": plan.target_path},
            )
            if not v_result.success:
                return False, f"Target directory or file '{plan.target_path}' does not exist on disk."

        # If a URL was launched, confirm browser launch step succeeded
        if plan.target_url:
            browser_steps = [s for s in executed_steps if s.get("action") == "open_url"]
            if not any(s.get("success") for s in browser_steps):
                return False, f"Browser launch for '{plan.target_url}' was not completed successfully."

        # If an application was targeted, confirm app launch step succeeded AND verification succeeded
        if plan.target_app:
            app_steps = [s for s in executed_steps if s.get("action") in ("launch", "open_in_app")]
            if not any(s.get("success") for s in app_steps):
                return False, f"Application launch for '{plan.target_app}' was not completed successfully."

            # Verify that process verification step genuinely passed
            verif_steps = [s for s in executed_steps if s.get("action") in ("verify_process_running", "verify_app_running")]
            if verif_steps and not any(s.get("success") for s in verif_steps):
                return False, f"Process verification for '{plan.target_app}' failed: application is not running."

            # Verify visible window step if included in plan or desktop app
            window_steps = [s for s in executed_steps if s.get("action") == "verify_visible_window"]
            if window_steps and not any(s.get("success") for s in window_steps):
                first_err = window_steps[0].get("error", "No visible window detected on user desktop.")
                return False, f"Window verification for '{plan.target_app}' failed: {first_err}"

        # Verify all executed steps succeeded
        if any(not s.get("success") for s in executed_steps):
            return False, "One or more execution steps failed."

        return True, "All outcomes independently verified."

    def _build_success_summary(self, plan: Plan, executed_steps: List[Dict[str, Any]]) -> str:
        """Generates a concise, informative execution summary."""
        parts = [f"Successfully executed {len(executed_steps)} step(s)."]
        if plan.target_url:
            parts.append(f"Opened URL: {plan.target_url}")
        if plan.target_path:
            parts.append(f"Target location: {plan.target_path}")
        if plan.target_app:
            parts.append(f"Launched in application: {plan.target_app}")
        return " | ".join(parts)

    def _record_step(
        self,
        task_id: str,
        step: ToolStep,
        status: str,
        error: Optional[str] = None,
    ) -> str:
        """Saves a step execution record to SQLite."""
        step_id = f"step-{task_id}-{step.step_number}"
        record = {
            "id": step_id,
            "task_id": task_id,
            "step_number": step.step_number,
            "step_description": step.description,
            "tool_name": step.tool,
            "action": step.action,
            "parameters_json": json.dumps(step.parameters),
            "status": status,
            "output_json": None,
            "error_message": error,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "duration_seconds": 0.0,
            "requires_approval": step.requires_approval,
        }
        self.db.save_step_execution(record)
        return step_id


_engine_instance: Optional[ExecutionEngine] = None


def get_execution_engine() -> ExecutionEngine:
    """Returns the singleton ExecutionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ExecutionEngine()
    return _engine_instance
