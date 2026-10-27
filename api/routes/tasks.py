"""Tasks API routes for persistent SDLC task management."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from agents.developer import DeveloperAgent, ImplementationProposal
from agents.reviewer import ReviewReport
from orchestrator.execution_engine import ExecutionEngine, get_execution_engine
from services.code_application_service import CodeApplicationResult
from services.lifecycle_service import TaskLifecycleCoordinator
from services.task_service import (
    InvalidStateTransitionError,
    TaskRecord,
    TaskService,
    TaskStepExecutionRecord,
)
from services.verification_service import VerificationProfile, VerificationResult
from storage.database import get_database

router = APIRouter()


class TaskCreateRequest(BaseModel):
    """Request payload for creating and persisting a new SDLC task."""

    task: str = Field(..., description="Software engineering task description.")
    execute_immediately: bool = Field(
        default=False,
        description="Whether to execute the computer task immediately upon creation.",
    )

    @field_validator("task")
    @classmethod
    def validate_task_not_empty(cls, value: str) -> str:
        """Validate that task is not empty or whitespace only."""
        if not value or not value.strip():
            raise ValueError("Task description cannot be empty or whitespace only.")
        return value.strip()


class TaskApplyRequest(BaseModel):
    """Optional payload for applying specific file contents."""

    file_contents: Optional[Dict[str, str]] = Field(
        None, description="Optional map of {relative_path: text_content} to apply."
    )


class TaskVerifyRequest(BaseModel):
    """Payload for executing verification."""

    profile: VerificationProfile = Field(
        default="pytest_standard",
        description="Approved verification profile to execute."
    )


def get_task_service() -> TaskService:
    """Dependency provider for TaskService with the configured database."""
    return TaskService(db=get_database())


def get_developer_agent(
    service: TaskService = Depends(get_task_service),
) -> DeveloperAgent:
    """Dependency provider for DeveloperAgent using the configured TaskService."""
    return DeveloperAgent(task_service=service)


def get_lifecycle_coordinator(
    task_service: TaskService = Depends(get_task_service),
) -> TaskLifecycleCoordinator:
    """Dependency provider for TaskLifecycleCoordinator."""
    return TaskLifecycleCoordinator(task_service=task_service)


def get_engine(
    task_service: TaskService = Depends(get_task_service),
) -> ExecutionEngine:
    """Dependency provider for ExecutionEngine."""
    return ExecutionEngine(task_service=task_service)


@router.post(
    "",
    response_model=TaskRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create & Plan Task",
    description="Validates a task, generates an execution plan, persists it, and returns the task record.",
)
@router.post(
    "/",
    response_model=TaskRecord,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_task(
    request: TaskCreateRequest,
    service: TaskService = Depends(get_task_service),
    engine: ExecutionEngine = Depends(get_engine),
) -> TaskRecord:
    """Creates, plans, and persists a task."""
    try:
        task_rec = service.create_task(request.task)
        if request.execute_immediately and task_rec.task_type in (
            "application_action",
            "computer_task",
            "filesystem_action",
            "composite_action",
            "browser_action",
            "command_action",
        ):
            return engine.execute_task(task_rec.id)
        return task_rec
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=List[TaskRecord],
    status_code=status.HTTP_200_OK,
    summary="List Tasks",
    description="Retrieves all persisted SDLC tasks.",
)
@router.get(
    "/",
    response_model=List[TaskRecord],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_tasks(
    service: TaskService = Depends(get_task_service),
) -> List[TaskRecord]:
    """Lists all saved tasks."""
    return service.list_tasks()


@router.get(
    "/{task_id}",
    response_model=TaskRecord,
    status_code=status.HTTP_200_OK,
    summary="Get Task by ID",
    description="Retrieves a specific task including its execution plan and status.",
)
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Retrieves a single task by ID or returns HTTP 404."""
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )
    return task


@router.post(
    "/{task_id}/proposal",
    response_model=ImplementationProposal,
    status_code=status.HTTP_200_OK,
    summary="Generate Implementation Proposal",
    description="Inspects a persisted task plan, generates a dry-run implementation proposal with candidate diffs, and transitions task to proposed state.",
)
async def create_task_proposal(
    task_id: str,
    coordinator: TaskLifecycleCoordinator = Depends(get_lifecycle_coordinator),
) -> ImplementationProposal:
    """Generates an ImplementationProposal for the specified task ID and persists it."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    try:
        _, proposal = coordinator.propose(clean_id)
        return proposal
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        if "action task" in msg.lower() or "cannot generate code proposal" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=msg,
        ) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{task_id}/review",
    response_model=ReviewReport,
    status_code=status.HTTP_200_OK,
    summary="Review Code Proposal",
    description="Audits proposed code changes using CodeReviewerAgent for security vulnerabilities, syntax, and maintainability.",
)
async def review_task_proposal(
    task_id: str,
    request: Optional[TaskApplyRequest] = None,
    coordinator: TaskLifecycleCoordinator = Depends(get_lifecycle_coordinator),
) -> ReviewReport:
    """Audits the latest implementation proposal."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    try:
        file_contents = request.file_contents if request else None
        _, report = coordinator.review(clean_id, file_contents=file_contents)
        return report
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc


@router.post(
    "/{task_id}/apply",
    response_model=CodeApplicationResult,
    status_code=status.HTTP_200_OK,
    summary="Apply Proposal to Isolated Workspace",
    description="Applies validated proposed code changes into an isolated workspace and records diffs.",
)
async def apply_task_proposal(
    task_id: str,
    request: Optional[TaskApplyRequest] = None,
    coordinator: TaskLifecycleCoordinator = Depends(get_lifecycle_coordinator),
) -> CodeApplicationResult:
    """Applies code changes into an isolated workspace and transitions task state to 'changes_applied'."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    try:
        file_contents = request.file_contents if request else None
        _, result = coordinator.apply(clean_id, file_contents=file_contents)
        return result
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc


@router.post(
    "/{task_id}/verify",
    response_model=VerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Verify Applied Task",
    description="Runs verification on an applied workspace and records outcome in persistent history.",
)
async def verify_task(
    task_id: str,
    request: Optional[TaskVerifyRequest] = None,
    coordinator: TaskLifecycleCoordinator = Depends(get_lifecycle_coordinator),
) -> VerificationResult:
    """Runs verification on an applied workspace and updates task lifecycle state."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    profile = request.profile if request else "pytest_standard"
    try:
        _, result = coordinator.verify(clean_id, profile=profile)
        return result
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Task",
    description="Permanently deletes a task record and its execution logs without touching local user files.",
)
async def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> Dict[str, Any]:
    """Permanently deletes a task record from SQLite."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    task = service.get_task(clean_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{clean_id}' not found.",
        )

    try:
        deleted = service.delete_task(clean_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID '{clean_id}' not found.",
            )
        return {
            "success": True,
            "message": f"Task '{clean_id}' successfully deleted.",
            "task_id": clean_id,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


class TaskExecuteRequest(BaseModel):
    """Payload for executing computer task steps."""

    approved: bool = Field(
        default=False,
        description="Whether the user explicitly approved sensitive or destructive actions.",
    )


def get_engine(
    task_service: TaskService = Depends(get_task_service),
) -> ExecutionEngine:
    """Dependency provider for ExecutionEngine."""
    return ExecutionEngine(task_service=task_service)


@router.post(
    "/{task_id}/execute",
    response_model=TaskRecord,
    status_code=status.HTTP_200_OK,
    summary="Execute Computer Task",
    description="Sequentially executes planned tool actions on the local computer and verifies outcome.",
)
async def execute_task(
    task_id: str,
    request: Optional[TaskExecuteRequest] = None,
    engine: ExecutionEngine = Depends(get_engine),
) -> TaskRecord:
    """Triggers sequential tool execution for a computer task."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    approved = request.approved if request else False
    try:
        return engine.execute_task(clean_id, approved=approved)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc


@router.get(
    "/{task_id}/executions",
    response_model=List[TaskStepExecutionRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Task Step Executions",
    description="Retrieves the detailed execution logs and tool outputs for each step of a task.",
)
async def get_task_executions(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> List[TaskStepExecutionRecord]:
    """Retrieves step-by-step tool execution history."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    task = service.get_task(clean_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{clean_id}' not found.",
        )
    return task.step_executions


@router.post(
    "/{task_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel Task Execution",
    description="Requests cancellation of an actively running task execution.",
)
async def cancel_task(
    task_id: str,
    engine: ExecutionEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """Signals cancellation to the execution engine."""
    clean_id = task_id.strip() if task_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task ID cannot be empty or whitespace only.",
        )

    cancelled = engine.request_cancellation(clean_id)
    return {
        "success": True,
        "cancelled": cancelled,
        "message": f"Cancellation request registered for task '{clean_id}'.",
        "task_id": clean_id,
    }


