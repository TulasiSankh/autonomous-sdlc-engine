"""FastAPI routes for interacting with and monitoring the Windows Local Agent."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from local_agent.config import TOKEN
from services.local_agent_client import (
    LocalAgentClient,
    LocalAgentOfflineError,
    get_local_agent_client,
)

router = APIRouter(prefix="/local-agent", tags=["Local Agent"])


class AppQuery(BaseModel):
    app_name: str = Field(..., description="Application name to inspect.")


class ActionRequest(BaseModel):
    action: str = Field(..., description="Action name to execute.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action arguments.")


@router.get(
    "/status",
    summary="Get Local Agent Status",
    description="Returns whether the Windows Local Agent is online, its OS, architecture, and version.",
)
async def get_agent_status(
    client: LocalAgentClient = Depends(get_local_agent_client),
) -> Dict[str, Any]:
    """Probes the local agent service and returns structured status."""
    is_online = client.is_online()
    details = client.get_status() if is_online else None
    return {
        "online": is_online,
        "details": details,
        "message": (
            "Orbit AI Windows Local Agent is connected and ready."
            if is_online
            else "Orbit AI Windows Local Agent is offline. Run 'python start_local_agent.py' to start."
        ),
    }


@router.get(
    "/token",
    summary="Get Local Agent Pairing Token",
    description="Returns pairing token for frontend dashboard communication with the local agent.",
)
async def get_token() -> Dict[str, str]:
    """Returns the pairing token."""
    return {"token": TOKEN}


@router.post(
    "/discover",
    summary="Discover Installed Application",
    description="Queries local agent for discovery of an application on the Windows computer.",
)
async def discover_application(
    query: AppQuery,
    client: LocalAgentClient = Depends(get_local_agent_client),
) -> Dict[str, Any]:
    """Discovers application executable via local agent."""
    try:
        return client.discover_app(query.app_name)
    except LocalAgentOfflineError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(err),
        ) from err


@router.post(
    "/running",
    summary="Check Application Running Status",
    description="Queries Windows process table via local agent.",
)
async def check_application_running(
    query: AppQuery,
    client: LocalAgentClient = Depends(get_local_agent_client),
) -> Dict[str, Any]:
    """Checks whether an application is running."""
    try:
        return client.check_app_running(query.app_name)
    except LocalAgentOfflineError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(err),
        ) from err


@router.post(
    "/execute",
    summary="Execute Controlled Local Action",
    description="Executes a local tool action via the Windows Local Agent.",
)
async def execute_local_action(
    req: ActionRequest,
    client: LocalAgentClient = Depends(get_local_agent_client),
) -> Dict[str, Any]:
    """Executes a local tool action."""
    try:
        return client.execute_action(req.action, req.parameters)
    except LocalAgentOfflineError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(err),
        ) from err
