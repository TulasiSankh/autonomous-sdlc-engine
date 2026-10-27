"""FastAPI server for the Orbit AI Windows Local Agent service."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from local_agent.config import (
    AGENT_NAME,
    AGENT_VERSION,
    ALLOWED_ORIGINS,
    HOST,
    PORT,
    TOKEN,
)
from local_agent.security import (
    audit_log,
    verify_agent_token,
    verify_host_header,
)
from local_agent.system_inspector import (
    AppDiscoveryResult,
    ProcessCheckResult,
    SystemEnvironmentInfo,
    SystemInspector,
)
from local_agent.tool_registry import (
    LocalActionResult,
    LocalToolDefinition,
    LocalToolRegistry,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local_agent.server")

app = FastAPI(
    title=AGENT_NAME,
    description="Windows Local Computer Execution Agent for Orbit AI",
    version=AGENT_VERSION,
)

# Middleware: CORS restriction to trusted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Singleton tool registry
tool_registry = LocalToolRegistry()


# Middleware: DNS Rebinding Protection
@app.middleware("http")
async def dns_rebinding_middleware(request: Request, call_next):
    # Skip host header check on OPTIONS requests for preflight
    if request.method != "OPTIONS":
        try:
            verify_host_header(request)
        except HTTPException as exc:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class AppQueryRequest(BaseModel):
    app_name: str = Field(..., description="Target application name, e.g. 'vscode' or 'notepad'.")


class ActionExecuteRequest(BaseModel):
    action: str = Field(..., description="Allowlisted action name to execute.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action arguments.")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Agent Health & Status",
    description="Public lightweight ping endpoint returning agent availability and OS metadata.",
)
@app.get("/status", include_in_schema=False)
async def get_health_status() -> Dict[str, Any]:
    """Lightweight public endpoint for the web dashboard to probe agent online/offline status."""
    env = SystemInspector.get_environment_info()
    return {
        "status": "online",
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "os": env.os_name,
        "release": env.os_release,
        "version_str": env.os_version,
        "architecture": env.architecture,
        "username": env.username,
        "hostname": env.hostname,
    }


@app.get(
    "/pairing/token",
    summary="Get Local Pairing Token",
    description="Returns the active pairing token for local frontend authorization.",
)
async def get_pairing_token(request: Request) -> Dict[str, str]:
    """Allows loopback dashboard to obtain or verify the active pairing token."""
    client_ip = request.client.host if request.client else "unknown"
    if client_ip not in ("127.0.0.1", "::1", "localhost"):
        audit_log("pairing_token_denied_non_loopback", f"ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Pairing token can only be retrieved from loopback client.",
        )
    return {"token": TOKEN, "agent_version": AGENT_VERSION}


@app.get(
    "/system/info",
    response_model=SystemEnvironmentInfo,
    summary="Host System Information",
    description="Detailed hardware, OS build, user privileges, and working environment.",
)
async def get_system_info(
    token: str = Depends(verify_agent_token),
) -> SystemEnvironmentInfo:
    """Returns detailed OS and environment information."""
    return SystemInspector.get_environment_info()


@app.get(
    "/tools",
    response_model=List[LocalToolDefinition],
    summary="List Registered Tools",
    description="Lists all approved, sandboxed local actions with schemas.",
)
async def list_tools(
    token: str = Depends(verify_agent_token),
) -> List[LocalToolDefinition]:
    """Returns list of all available tool schemas."""
    return tool_registry.get_tool_definitions()


@app.post(
    "/apps/discover",
    response_model=AppDiscoveryResult,
    summary="Discover Installed Application",
    description="Inspects PATH, registry, and standard installation directories for an application.",
)
async def discover_app(
    request: AppQueryRequest,
    token: str = Depends(verify_agent_token),
) -> AppDiscoveryResult:
    """Discovers application executable location."""
    return SystemInspector.discover_application(request.app_name)


@app.post(
    "/apps/running",
    response_model=ProcessCheckResult,
    summary="Check Application Running Status",
    description="Inspects Windows process table to check if application is active.",
)
async def check_app_running(
    request: AppQueryRequest,
    token: str = Depends(verify_agent_token),
) -> ProcessCheckResult:
    """Checks whether an application is currently running."""
    return SystemInspector.check_application_running(request.app_name)


@app.post(
    "/actions/execute",
    response_model=LocalActionResult,
    summary="Execute Controlled Local Action",
    description="Executes an allowlisted local action and verifies outcome.",
)
async def execute_action(
    request: ActionExecuteRequest,
    token: str = Depends(verify_agent_token),
) -> LocalActionResult:
    """Executes a local tool action and captures verification evidence."""
    return tool_registry.execute_action(request.action, request.parameters)


def run_server():
    """Runs the local agent server with Uvicorn."""
    import uvicorn
    print(f"================================================================")
    print(f" Starting {AGENT_NAME} (v{AGENT_VERSION})")
    print(f" Listening on http://{HOST}:{PORT}")
    print(f" Pairing token: {TOKEN}")
    print(f"================================================================")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    run_server()
