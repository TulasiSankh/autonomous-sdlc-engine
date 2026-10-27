"""Sandboxed verification and test execution service.

Evaluates test outcomes for applied workspaces under strict policy enforcement,
environment sanitization, bounded output limits, and fail-closed security controls.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import os
from pathlib import Path, PurePath
import subprocess
import sys
import time
from typing import Dict, List, Literal, Optional, Set
from pydantic import BaseModel, Field

from services.workspace_service import WorkspaceService

# Maximum captured output bytes per stream (stdout/stderr) to prevent memory exhaustion
DEFAULT_MAX_OUTPUT_BYTES: int = 65536  # 64 KB
DEFAULT_TIMEOUT_SECONDS: float = 30.0

VerificationStatus = Literal["passed", "failed", "timed_out", "blocked", "error"]
VerificationProfile = Literal["pytest_standard", "pytest_fast", "pytest_strict"]

# Sensitive environment variable keys that must be stripped before process launch
SENSITIVE_ENV_PREFIXES: List[str] = [
    "OPENAI",
    "ANTHROPIC",
    "GEMINI",
    "AWS",
    "AZURE",
    "GITHUB",
    "GITLAB",
    "SLACK",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "SDLC",
]


class VerificationRequest(BaseModel):
    """Input parameters for a workspace verification run."""

    workspace_id: str = Field(..., description="Unique ID of a tracked, verified workspace.")
    profile: VerificationProfile = Field(
        default="pytest_standard", description="Pre-configured verification profile."
    )
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        ge=1.0,
        le=300.0,
        description="Maximum execution duration before terminating.",
    )


class VerificationResult(BaseModel):
    """Structured, immutable outcome of a verification run."""

    workspace_id: str = Field(..., description="Workspace ID where verification ran.")
    profile: str = Field(..., description="Verification profile executed.")
    status: VerificationStatus = Field(..., description="Execution outcome status.")
    exit_code: Optional[int] = Field(None, description="Process exit code (if executed).")
    duration_seconds: float = Field(default=0.0, description="Elapsed execution duration.")
    stdout: str = Field(default="", description="Captured standard output (bounded).")
    stderr: str = Field(default="", description="Captured standard error (bounded).")
    output_truncated: bool = Field(default=False, description="Whether output exceeded byte limits.")
    timed_out: bool = Field(default=False, description="Whether the run exceeded timeout.")
    runner_id: str = Field(..., description="Identifier of the runner mechanism used.")
    timestamp: str = Field(..., description="ISO 8601 timestamp of verification.")
    error_message: Optional[str] = Field(None, description="Diagnostic error explanation if failed/blocked.")


def sanitize_environment(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Produces a sanitized environment dictionary with all secrets and tokens stripped.

    Args:
        base_env: Optional base environment to filter. Defaults to os.environ.

    Returns:
        Sanitized environment dictionary containing only essential system variables.
    """
    source = base_env if base_env is not None else os.environ
    sanitized: Dict[str, str] = {}

    for key, value in source.items():
        upper_key = key.upper()
        # Drop any sensitive patterns
        if any(upper_key.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES):
            continue
        if any(term in upper_key for term in ("SECRET", "TOKEN", "KEY", "PASS", "AUTH")):
            continue
        sanitized[key] = value

    # Standardize minimal python environment
    sanitized["PYTHONUNBUFFERED"] = "1"
    sanitized["PYTHONDONTWRITEBYTECODE"] = "1"
    return sanitized


class BaseVerificationRunner(ABC):
    """Abstract interface for executing verification runs in an isolated context."""

    @property
    @abstractmethod
    def runner_id(self) -> str:
        """Returns unique runner identification string."""
        pass

    @abstractmethod
    def run(
        self,
        workspace_path: Path,
        command_args: List[str],
        timeout_seconds: float,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> VerificationResult:
        """Executes verification and returns a structured VerificationResult."""
        pass


class DisabledSecurityRunner(BaseVerificationRunner):
    """Default runner that intentionally blocks execution when secure containers are unavailable.

    Prevents untrusted, agent-modified code from executing directly on the host machine.
    """

    @property
    def runner_id(self) -> str:
        return "disabled-host-protection"

    def run(
        self,
        workspace_path: Path,
        command_args: List[str],
        timeout_seconds: float,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> VerificationResult:
        now = datetime.now(timezone.utc).isoformat()
        reason = (
            "Execution blocked: Secure container isolation (e.g., Docker or dedicated worker) "
            "is not available on this host. Host execution is disabled by default to prevent "
            "untrusted code execution on the developer machine. "
            "To enable controlled host verification for testing, configure SubprocessSandboxRunner "
            "with allow_host_execution=True or set SDLC_ENABLE_HOST_VERIFICATION=1."
        )
        return VerificationResult(
            workspace_id=workspace_path.name,
            profile="pytest",
            status="blocked",
            exit_code=None,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            output_truncated=False,
            timed_out=False,
            runner_id=self.runner_id,
            timestamp=now,
            error_message=reason,
        )


class SubprocessSandboxRunner(BaseVerificationRunner):
    """Controlled subprocess runner with environment sanitization and resource timeouts.

    Used when host execution is explicitly approved (e.g. CI environments or test fixtures).
    """

    def __init__(self, allow_host_execution: bool = False) -> None:
        env_flag = os.getenv("SDLC_ENABLE_HOST_VERIFICATION", "0") in ("1", "true", "True")
        self.allow_host_execution: bool = allow_host_execution or env_flag

    @property
    def runner_id(self) -> str:
        return "subprocess-sanitized-runner"

    def run(
        self,
        workspace_path: Path,
        command_args: List[str],
        timeout_seconds: float,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> VerificationResult:
        now = datetime.now(timezone.utc).isoformat()
        ws_id = workspace_path.name

        if not self.allow_host_execution:
            return DisabledSecurityRunner().run(
                workspace_path, command_args, timeout_seconds, max_output_bytes
            )

        sanitized_env = sanitize_environment()
        # Ensure PYTHONPATH resolves strictly within the workspace
        sanitized_env["PYTHONPATH"] = str(workspace_path)

        start_time = time.perf_counter()
        timed_out = False
        output_truncated = False

        try:
            process = subprocess.run(
                command_args,
                cwd=str(workspace_path),
                env=sanitized_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,  # Shell execution strictly disabled
            )
            duration = time.perf_counter() - start_time
            exit_code = process.returncode
            raw_stdout = process.stdout or ""
            raw_stderr = process.stderr or ""

            # Check if truncation is needed
            if len(raw_stdout.encode("utf-8")) > max_output_bytes:
                stdout = raw_stdout[: max_output_bytes // 2] + "\n... [STDOUT TRUNCATED] ...\n"
                output_truncated = True
            else:
                stdout = raw_stdout

            if len(raw_stderr.encode("utf-8")) > max_output_bytes:
                stderr = raw_stderr[: max_output_bytes // 2] + "\n... [STDERR TRUNCATED] ...\n"
                output_truncated = True
            else:
                stderr = raw_stderr

            status: VerificationStatus = "passed" if exit_code == 0 else "failed"

            return VerificationResult(
                workspace_id=ws_id,
                profile=command_args[2] if len(command_args) > 2 else "custom",
                status=status,
                exit_code=exit_code,
                duration_seconds=round(duration, 4),
                stdout=stdout,
                stderr=stderr,
                output_truncated=output_truncated,
                timed_out=False,
                runner_id=self.runner_id,
                timestamp=now,
                error_message=None if exit_code == 0 else f"Process exited with code {exit_code}",
            )

        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start_time
            raw_stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.output if isinstance(exc.output, str) else "")
            raw_stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return VerificationResult(
                workspace_id=ws_id,
                profile="pytest",
                status="timed_out",
                exit_code=None,
                duration_seconds=round(duration, 4),
                stdout=raw_stdout,
                stderr=raw_stderr,
                output_truncated=False,
                timed_out=True,
                runner_id=self.runner_id,
                timestamp=now,
                error_message=f"Execution timed out after {timeout_seconds} seconds.",
            )

        except Exception as exc:
            duration = time.perf_counter() - start_time
            return VerificationResult(
                workspace_id=ws_id,
                profile="pytest",
                status="error",
                exit_code=None,
                duration_seconds=round(duration, 4),
                stdout="",
                stderr="",
                output_truncated=False,
                timed_out=False,
                runner_id=self.runner_id,
                timestamp=now,
                error_message=f"Failed to launch verification runner: {exc}",
            )


class VerificationService:
    """Coordinates workspace policy validation and sandboxed test execution."""

    SUPPORTED_PROFILES: Dict[str, List[str]] = {
        "pytest_standard": [sys.executable, "-m", "pytest", "tests", "-v", "--tb=short"],
        "pytest_fast": [sys.executable, "-m", "pytest", "tests", "-q", "--maxfail=1"],
        "pytest_strict": [sys.executable, "-m", "pytest", "tests", "-v", "-W", "error", "--strict-markers"],
    }

    def __init__(
        self,
        workspace_service: Optional[WorkspaceService] = None,
        runner: Optional[BaseVerificationRunner] = None,
    ) -> None:
        self.workspace_service: WorkspaceService = (
            workspace_service if workspace_service is not None else WorkspaceService()
        )
        # Default securely to DisabledSecurityRunner unless explicitly configured
        self.runner: BaseVerificationRunner = (
            runner if runner is not None else DisabledSecurityRunner()
        )

    def validate_workspace_for_verification(self, workspace_path: Path) -> List[str]:
        """Validates that a workspace contains valid project configuration and tests before execution.

        Args:
            workspace_path: Path to the workspace directory.

        Returns:
            List of validation errors, if any.
        """
        errors: List[str] = []

        if not workspace_path.is_dir():
            errors.append(f"Workspace path '{workspace_path}' is not a directory.")
            return errors

        # Ensure a tests/ directory exists
        tests_dir = workspace_path / "tests"
        if not tests_dir.is_dir():
            errors.append("Workspace does not contain a 'tests/' directory.")
        else:
            # Check for at least one python test file
            test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
            if not test_files:
                errors.append("No test files (test_*.py or *_test.py) found in 'tests/' directory.")

        return errors

    def verify_workspace(
        self,
        request: VerificationRequest,
    ) -> VerificationResult:
        """Validates workspace integrity and executes the approved verification profile.

        Args:
            request: VerificationRequest containing workspace ID, profile, and timeout.

        Returns:
            VerificationResult describing execution status and test results.

        Raises:
            ValueError: If workspace_id is invalid or profile is not in the allowlist.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Enforce Profile Allowlist
        if request.profile not in self.SUPPORTED_PROFILES:
            raise ValueError(
                f"Unsupported verification profile '{request.profile}'. "
                f"Allowed profiles are: {list(self.SUPPORTED_PROFILES.keys())}."
            )

        command_args = list(self.SUPPORTED_PROFILES[request.profile])

        # 2. Enforce Workspace Tracking and Provenance
        try:
            ws_path = self.workspace_service.get_workspace_path(request.workspace_id)
        except ValueError as exc:
            return VerificationResult(
                workspace_id=request.workspace_id,
                profile=request.profile,
                status="error",
                exit_code=None,
                duration_seconds=0.0,
                stdout="",
                stderr="",
                output_truncated=False,
                timed_out=False,
                runner_id=self.runner.runner_id,
                timestamp=now,
                error_message=f"Workspace verification failed: {exc}",
            )

        # 3. Validate Test Configuration
        validation_errors = self.validate_workspace_for_verification(ws_path)
        if validation_errors:
            return VerificationResult(
                workspace_id=request.workspace_id,
                profile=request.profile,
                status="error",
                exit_code=None,
                duration_seconds=0.0,
                stdout="",
                stderr="",
                output_truncated=False,
                timed_out=False,
                runner_id=self.runner.runner_id,
                timestamp=now,
                error_message="; ".join(validation_errors),
            )

        # 4. Delegate to Runner
        result = self.runner.run(
            workspace_path=ws_path,
            command_args=command_args,
            timeout_seconds=request.timeout_seconds,
        )
        return result
