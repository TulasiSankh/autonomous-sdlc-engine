"""Command execution tool for running approved commands with strict timeouts and output limits."""

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tools.base import BaseTool, ToolExecutionResult

MAX_COMMAND_TIMEOUT = 120  # Max 120 seconds
DEFAULT_COMMAND_TIMEOUT = 30  # Default 30 seconds
MAX_OUTPUT_CHARS = 32768  # 32 KB character limit for stdout/stderr


class CommandTool(BaseTool):
    """Tool that runs approved commands in a controlled subprocess."""

    name = "command"
    description = "Executes shell commands or test runners in a controlled, bounded subprocess."
    supported_actions = ["run_command", "execute", "run"]

    # Blocked dangerous command prefixes or patterns
    DANGEROUS_PATTERNS = [
        "format ",
        "mkfs",
        "rm -rf /",
        "rm -rf /*",
        ":(){ :|:& };:",
        "del /f /s /q c:\\",
        "rmdir /s /q c:\\",
        "shutdown",
        "reboot",
    ]

    def __init__(
        self,
        runner_fn: Optional[Callable[..., subprocess.CompletedProcess]] = None,
        working_dir: Optional[Path] = None,
    ) -> None:
        """Initializes the command execution tool.
        
        Args:
            runner_fn: Custom subprocess runner function (useful for tests/mocking).
            working_dir: Default working directory for command execution.
        """
        self._runner_fn = runner_fn
        self.default_working_dir = working_dir or Path.cwd()

    def get_parameters_schema(self, action: Optional[str] = None) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command string to execute (e.g. 'pytest -v', 'npm test', 'git status').",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory in which to execute the command.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30, max 120).",
                    "default": DEFAULT_COMMAND_TIMEOUT,
                },
            },
            "required": ["command"],
        }

    def validate_command(self, command: str) -> str:
        """Validates command safety against known destructive patterns."""
        if not command or not isinstance(command, str) or not command.strip():
            raise ValueError("Command cannot be empty or whitespace only.")

        clean_cmd = command.strip()
        cmd_lower = clean_cmd.lower()

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                raise ValueError(
                    f"Command contains blocked destructive pattern: '{pattern}'."
                )

        return clean_cmd

    def execute(self, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        self.validate_action(action)

        raw_cmd = params.get("command")
        if not raw_cmd:
            return ToolExecutionResult(
                success=False,
                error="Missing required parameter 'command'.",
            )

        try:
            command = self.validate_command(str(raw_cmd))
        except ValueError as exc:
            return ToolExecutionResult(
                success=False,
                error=str(exc),
                metadata={"command": raw_cmd},
            )

        # Timeout validation
        timeout = params.get("timeout_seconds", DEFAULT_COMMAND_TIMEOUT)
        try:
            timeout_int = min(max(int(timeout), 1), MAX_COMMAND_TIMEOUT)
        except (ValueError, TypeError):
            timeout_int = DEFAULT_COMMAND_TIMEOUT

        # Working directory
        raw_work_dir = params.get("working_dir")
        if raw_work_dir:
            cwd = Path(str(raw_work_dir)).resolve()
            if not cwd.exists() or not cwd.is_dir():
                return ToolExecutionResult(
                    success=False,
                    error=f"Working directory does not exist: '{cwd}'.",
                    metadata={"working_dir": str(cwd)},
                )
        else:
            cwd = self.default_working_dir

        start_time = time.time()
        try:
            if self._runner_fn is not None:
                completed = self._runner_fn(
                    command,
                    cwd=str(cwd),
                    timeout=timeout_int,
                )
                stdout = getattr(completed, "stdout", "") or ""
                stderr = getattr(completed, "stderr", "") or ""
                exit_code = getattr(completed, "returncode", 0)
            else:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(cwd),
                    timeout=timeout_int,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                stdout = completed.stdout or ""
                stderr = completed.stderr or ""
                exit_code = completed.returncode

            duration = round(time.time() - start_time, 3)

            # Enforce output bounds
            truncated = len(stdout) > MAX_OUTPUT_CHARS or len(stderr) > MAX_OUTPUT_CHARS
            bounded_stdout = stdout[:MAX_OUTPUT_CHARS]
            bounded_stderr = stderr[:MAX_OUTPUT_CHARS]

            success = (exit_code == 0)

            return ToolExecutionResult(
                success=success,
                output={
                    "command": command,
                    "exit_code": exit_code,
                    "stdout": bounded_stdout,
                    "stderr": bounded_stderr,
                    "duration_seconds": duration,
                    "truncated": truncated,
                },
                error=bounded_stderr if not success and bounded_stderr else (None if success else f"Command exited with non-zero code {exit_code}"),
                metadata={
                    "command": command,
                    "exit_code": exit_code,
                    "duration_seconds": duration,
                    "cwd": str(cwd),
                },
            )

        except subprocess.TimeoutExpired as exc:
            duration = round(time.time() - start_time, 3)
            return ToolExecutionResult(
                success=False,
                error=f"Command timed out after {timeout_int} seconds.",
                metadata={
                    "command": command,
                    "timed_out": True,
                    "timeout_seconds": timeout_int,
                    "duration_seconds": duration,
                },
            )
        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            return ToolExecutionResult(
                success=False,
                error=f"Subprocess execution failed: {str(exc)}",
                metadata={
                    "command": command,
                    "duration_seconds": duration,
                },
            )
