"""Planning API routes."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from agents.planner import Plan, PlannerAgent

router = APIRouter()


class PlanRequest(BaseModel):
    """Request payload for task planning."""

    task: str = Field(..., description="Software engineering task description.")

    @field_validator("task")
    @classmethod
    def validate_task_not_empty(cls, value: str) -> str:
        """Validate that task is not empty or whitespace only."""
        if not value or not value.strip():
            raise ValueError("Task description cannot be empty or whitespace only.")
        return value.strip()


@router.post(
    "/plan",
    response_model=Plan,
    status_code=status.HTTP_200_OK,
    summary="Generate Execution Plan",
    description="Accepts a software engineering task and returns a structured execution plan.",
)
async def create_plan(request: PlanRequest) -> Plan:
    """Generate a structured Plan for a given task using the PlannerAgent."""
    agent = PlannerAgent()
    try:
        return agent.plan(request.task)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
