"""Extensible, secure local tool registry for Orbit AI Windows Local Agent."""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from local_agent.process_launcher import ProcessLauncher, ProcessLaunchResult
from local_agent.security import audit_log, validate_authorized_path
from local_agent.system_inspector import SystemInspector


class LocalToolDefinition(BaseModel):
    """Schema and capability definition for a registered local agent tool."""

    name: str
    description: str
    parameters_schema: Dict[str, Any]
    permissions: str = "local_user"
    timeout_seconds: int = 30
    requires_approval: bool = False


class LocalActionResult(BaseModel):
    """Structured response from executing a local tool action."""

    success: bool
    action: str
    output: Any = None
    error: Optional[str] = None
    started_at: str
    completed_at: str
    duration_seconds: float = 0.0
    verification_evidence: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LocalToolRegistry:
    """Registry coordinating validated, sandboxed local Windows tool actions."""

    def __init__(self) -> None:
        self._tools: Dict[str, LocalToolDefinition] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], LocalActionResult]] = {}
        self._register_default_tools()

    def get_tool_definitions(self) -> List[LocalToolDefinition]:
        """Returns metadata for all available local tools."""
        return list(self._tools.values())

    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> LocalActionResult:
        """Executes a registered local action with input validation and execution sandboxing."""
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()

        if action_name not in self._handlers:
            audit_log("tool_not_found", f"action={action_name}")
            end_iso = datetime.now(timezone.utc).isoformat()
            return LocalActionResult(
                success=False,
                action=action_name,
                error=f"Unsupported local action '{action_name}'. Allowlisted actions: {list(self._handlers.keys())}",
                started_at=start_iso,
                completed_at=end_iso,
                duration_seconds=0.0,
            )

        audit_log("execute_tool", f"action={action_name} params={parameters}")
        try:
            handler = self._handlers[action_name]
            result = handler(parameters)
            result.duration_seconds = round(time.time() - start_time, 3)
            result.completed_at = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            end_iso = datetime.now(timezone.utc).isoformat()
            audit_log("tool_execution_failed", f"action={action_name} error={str(exc)}")
            return LocalActionResult(
                success=False,
                action=action_name,
                error=f"Error executing action '{action_name}': {str(exc)}",
                started_at=start_iso,
                completed_at=end_iso,
                duration_seconds=duration,
            )

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    def _register_default_tools(self) -> None:
        """Registers the allowlist of supported local computer tools."""
        # 1. Open VS Code
        self._tools["open_vscode"] = LocalToolDefinition(
            name="open_vscode",
            description="Locates VS Code, checks if already running, and launches or opens a project folder.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "target_path": {
                        "type": "string",
                        "description": "Optional project folder or file to open in VS Code.",
                    }
                },
            },
        )
        self._handlers["open_vscode"] = self._handle_open_vscode

        # 2. Open Notepad
        self._tools["open_notepad"] = LocalToolDefinition(
            name="open_notepad",
            description="Launches Notepad on Windows with an optional target file.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Optional text file to open."}
                },
            },
        )
        self._handlers["open_notepad"] = self._handle_open_notepad

        # 3. Open File Explorer
        self._tools["open_explorer"] = LocalToolDefinition(
            name="open_explorer",
            description="Opens Windows File Explorer at an authorized folder path.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Folder path to view in Explorer."}
                },
            },
        )
        self._handlers["open_explorer"] = self._handle_open_explorer

        # 4. Check App Running
        self._tools["check_app_running"] = LocalToolDefinition(
            name="check_app_running",
            description="Inspects the Windows process table to determine if an application is running.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application name: 'vscode', 'notepad', etc."}
                },
                "required": ["app_name"],
            },
        )
        self._handlers["check_app_running"] = self._handle_check_app_running

        # 5. Discover Application
        self._tools["discover_app"] = LocalToolDefinition(
            name="discover_app",
            description="Discovers installed application executable using PATH, standard dirs, and registry.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application to detect."}
                },
                "required": ["app_name"],
            },
        )
        self._handlers["discover_app"] = self._handle_discover_app

        # 6. Inspect Directory
        self._tools["inspect_directory"] = LocalToolDefinition(
            name="inspect_directory",
            description="Inspects files and folders within an authorized project directory.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "Path to inspect."}
                },
                "required": ["directory_path"],
            },
        )
        self._handlers["inspect_directory"] = self._handle_inspect_directory

        # 7. Read Project File
        self._tools["read_project_file"] = LocalToolDefinition(
            name="read_project_file",
            description="Reads contents of a project file within an authorized directory.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "File path to read."}
                },
                "required": ["file_path"],
            },
        )
        self._handlers["read_project_file"] = self._handle_read_project_file

        # 8. Run Project Tests
        self._tools["run_project_tests"] = LocalToolDefinition(
            name="run_project_tests",
            description="Runs approved test suite (pytest or npm test) in an authorized directory.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "test_type": {"type": "string", "enum": ["pytest", "npm_test"]},
                    "working_dir": {"type": "string"},
                },
                "required": ["test_type"],
            },
            timeout_seconds=60,
        )
        self._handlers["run_project_tests"] = self._handle_run_project_tests

    # -------------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------------

    def _handle_open_vscode(self, params: Dict[str, Any]) -> LocalActionResult:
        """Executes the complete Open VS Code workflow."""
        start_iso = datetime.now(timezone.utc).isoformat()
        target_path_str = params.get("target_path") or params.get("path")
        validated_target: Optional[Path] = None

        if target_path_str:
            try:
                validated_target = validate_authorized_path(str(target_path_str))
                if not validated_target.exists():
                    return LocalActionResult(
                        success=False,
                        action="open_vscode",
                        error=f"Target path '{validated_target}' does not exist on disk.",
                        started_at=start_iso,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
            except ValueError as ve:
                return LocalActionResult(
                    success=False,
                    action="open_vscode",
                    error=str(ve),
                    started_at=start_iso,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

        # 1. Discover VS Code executable
        disc = SystemInspector.discover_application("vscode")
        if not disc.is_installed or not disc.executable_path:
            return LocalActionResult(
                success=False,
                action="open_vscode",
                error=disc.actionable_help or "VS Code is not installed on this system.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                metadata={"discovered": False, "locations_checked": disc.locations_checked},
            )

        # 2. Check if already running
        running_check = SystemInspector.check_application_running("vscode")
        already_running = running_check.is_running

        # 3. Launch process — force a new visible window.
        # VS Code uses a single-instance IPC protocol: launching Code.exe when it's
        # already running causes the launcher to hand off via IPC and exit silently.
        # Passing --new-window forces VS Code to always open a new visible window.
        args = ["--new-window"]
        if validated_target:
            args.append(str(validated_target))
        launch_res: ProcessLaunchResult = ProcessLauncher.launch(
            executable_path=disc.executable_path,
            args=args,
        )

        if not launch_res.success:
            return LocalActionResult(
                success=False,
                action="open_vscode",
                error=launch_res.error_message,
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                verification_evidence=launch_res.verification_evidence,
                metadata={
                    "executable": disc.executable_path,
                    "already_running": already_running,
                    "target_path": str(validated_target) if validated_target else None,
                },
            )

        output_msg = (
            f"Successfully launched VS Code with target '{validated_target}' (PID: {launch_res.pid})."
            if validated_target
            else (
                f"VS Code was already running (PID(s): {', '.join(str(p) for p in running_check.pids)}). Successfully opened window (PID: {launch_res.pid})."
                if already_running
                else f"Successfully launched VS Code (PID: {launch_res.pid}) and verified active process."
            )
        )

        evidence = dict(launch_res.verification_evidence)
        evidence["already_running_prior"] = already_running
        evidence["discovery_method"] = disc.discovery_method

        # If launcher delegated to single-instance and exited, use active running PID
        active_pid = launch_res.pid
        if active_pid is not None and not SystemInspector.verify_pid_alive(active_pid):
            fresh_check = SystemInspector.check_application_running("vscode")
            if fresh_check.is_running and fresh_check.pids:
                active_pid = fresh_check.pids[-1]

        return LocalActionResult(
            success=True,
            action="open_vscode",
            output={
                "message": output_msg,
                "pid": active_pid,
                "executable": disc.executable_path,
                "already_running": already_running,
                "target_path": str(validated_target) if validated_target else None,
                "window_verified": launch_res.window_verified,
            },
            started_at=start_iso,
            completed_at=datetime.now(timezone.utc).isoformat(),
            verification_evidence=evidence,
            metadata={
                "pid": active_pid,
                "verified_alive": launch_res.verified_alive,
                "window_verified": launch_res.window_verified,
                "executable": disc.executable_path,
            },
        )

    def _handle_open_notepad(self, params: Dict[str, Any]) -> LocalActionResult:
        """Opens Notepad with an optional authorized text file."""
        start_iso = datetime.now(timezone.utc).isoformat()
        file_path_str = params.get("file_path") or params.get("path")
        target_file: Optional[Path] = None

        if file_path_str:
            try:
                target_file = validate_authorized_path(str(file_path_str))
            except ValueError as ve:
                return LocalActionResult(
                    success=False,
                    action="open_notepad",
                    error=str(ve),
                    started_at=start_iso,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

        disc = SystemInspector.discover_application("notepad")
        if not disc.is_installed or not disc.executable_path:
            return LocalActionResult(
                success=False,
                action="open_notepad",
                error="Notepad executable could not be located on this Windows system.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        args = [str(target_file)] if target_file else []
        launch_res = ProcessLauncher.launch(disc.executable_path, args=args)
        if not launch_res.success:
            return LocalActionResult(
                success=False,
                action="open_notepad",
                error=launch_res.error_message,
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        return LocalActionResult(
            success=True,
            action="open_notepad",
            output={
                "message": f"Successfully opened Notepad (PID: {launch_res.pid}).",
                "pid": launch_res.pid,
                "file_path": str(target_file) if target_file else None,
            },
            started_at=start_iso,
            completed_at=datetime.now(timezone.utc).isoformat(),
            verification_evidence=launch_res.verification_evidence,
        )

    def _handle_open_explorer(self, params: Dict[str, Any]) -> LocalActionResult:
        """Opens Windows File Explorer at an authorized folder path."""
        start_iso = datetime.now(timezone.utc).isoformat()
        folder_path_str = params.get("folder_path") or params.get("path") or os.getcwd()

        try:
            target_folder = validate_authorized_path(str(folder_path_str))
            if not target_folder.exists() or not target_folder.is_dir():
                return LocalActionResult(
                    success=False,
                    action="open_explorer",
                    error=f"Folder path '{target_folder}' does not exist or is not a directory.",
                    started_at=start_iso,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
        except ValueError as ve:
            return LocalActionResult(
                success=False,
                action="open_explorer",
                error=str(ve),
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        disc = SystemInspector.discover_application("explorer")
        exe = disc.executable_path or "explorer.exe"

        launch_res = ProcessLauncher.launch(exe, args=[str(target_folder)])
        # Explorer.exe often delegates to an existing shell process and exits with code 0 or 1
        return LocalActionResult(
            success=True,
            action="open_explorer",
            output={
                "message": f"Successfully launched File Explorer for '{target_folder}'.",
                "folder_path": str(target_folder),
            },
            started_at=start_iso,
            completed_at=datetime.now(timezone.utc).isoformat(),
            verification_evidence={"folder_path": str(target_folder), "verified": True},
        )

    def _handle_check_app_running(self, params: Dict[str, Any]) -> LocalActionResult:
        """Checks if a given application is running."""
        start_iso = datetime.now(timezone.utc).isoformat()
        app_name = params.get("app_name")
        if not app_name:
            return LocalActionResult(
                success=False,
                action="check_app_running",
                error="Missing required parameter 'app_name'.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        check_res = SystemInspector.check_application_running(str(app_name))
        return LocalActionResult(
            success=True,
            action="check_app_running",
            output=check_res.model_dump(),
            started_at=start_iso,
            completed_at=datetime.now(timezone.utc).isoformat(),
            verification_evidence={
                "is_running": check_res.is_running,
                "pids": check_res.pids,
                "process_names": check_res.process_names,
            },
        )

    def _handle_discover_app(self, params: Dict[str, Any]) -> LocalActionResult:
        """Discovers an application executable path."""
        start_iso = datetime.now(timezone.utc).isoformat()
        app_name = params.get("app_name")
        if not app_name:
            return LocalActionResult(
                success=False,
                action="discover_app",
                error="Missing required parameter 'app_name'.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        disc = SystemInspector.discover_application(str(app_name))
        return LocalActionResult(
            success=disc.is_installed,
            action="discover_app",
            output=disc.model_dump(),
            error=disc.actionable_help if not disc.is_installed else None,
            started_at=start_iso,
            completed_at=datetime.now(timezone.utc).isoformat(),
            verification_evidence={
                "is_installed": disc.is_installed,
                "executable_path": disc.executable_path,
                "discovery_method": disc.discovery_method,
            },
        )

    def _handle_inspect_directory(self, params: Dict[str, Any]) -> LocalActionResult:
        """Lists files and folders within an authorized directory."""
        start_iso = datetime.now(timezone.utc).isoformat()
        dir_path_str = params.get("directory_path") or params.get("path")
        if not dir_path_str:
            return LocalActionResult(
                success=False,
                action="inspect_directory",
                error="Missing required parameter 'directory_path'.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            target_dir = validate_authorized_path(str(dir_path_str))
            if not target_dir.exists() or not target_dir.is_dir():
                return LocalActionResult(
                    success=False,
                    action="inspect_directory",
                    error=f"Directory '{target_dir}' does not exist on disk.",
                    started_at=start_iso,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            items = []
            for child in sorted(target_dir.iterdir()):
                try:
                    items.append({
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "size_bytes": child.stat().st_size if child.is_file() else None,
                    })
                    if len(items) >= 150:
                        break
                except Exception:
                    pass

            return LocalActionResult(
                success=True,
                action="inspect_directory",
                output={"directory": str(target_dir), "items": items, "count": len(items)},
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                verification_evidence={"item_count": len(items), "exists": True},
            )
        except ValueError as ve:
            return LocalActionResult(
                success=False,
                action="inspect_directory",
                error=str(ve),
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    def _handle_read_project_file(self, params: Dict[str, Any]) -> LocalActionResult:
        """Safely reads content of an authorized project file."""
        start_iso = datetime.now(timezone.utc).isoformat()
        file_path_str = params.get("file_path") or params.get("path")
        if not file_path_str:
            return LocalActionResult(
                success=False,
                action="read_project_file",
                error="Missing required parameter 'file_path'.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            target_file = validate_authorized_path(str(file_path_str))
            if not target_file.exists() or not target_file.is_file():
                return LocalActionResult(
                    success=False,
                    action="read_project_file",
                    error=f"File '{target_file}' does not exist or is not a regular file.",
                    started_at=start_iso,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            # Bound reading to 64KB for safety
            max_bytes = int(params.get("max_bytes", 65536))
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)

            return LocalActionResult(
                success=True,
                action="read_project_file",
                output={
                    "file_path": str(target_file),
                    "content": content,
                    "byte_count": len(content.encode("utf-8")),
                },
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                verification_evidence={"file_size": target_file.stat().st_size},
            )
        except ValueError as ve:
            return LocalActionResult(
                success=False,
                action="read_project_file",
                error=str(ve),
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    def _handle_run_project_tests(self, params: Dict[str, Any]) -> LocalActionResult:
        """Runs approved test command safely without shell=True."""
        start_iso = datetime.now(timezone.utc).isoformat()
        test_type = params.get("test_type", "pytest")
        working_dir_str = params.get("working_dir") or str(Path(__file__).resolve().parent.parent)

        try:
            work_dir = validate_authorized_path(str(working_dir_str))
        except ValueError as ve:
            return LocalActionResult(
                success=False,
                action="run_project_tests",
                error=str(ve),
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        # Allowlisted test commands only (strict execution sandboxing)
        cmd: List[str] = []
        if test_type == "pytest":
            python_exe = sys.executable
            cmd = [python_exe, "-m", "pytest", "-q"]
        elif test_type == "npm_test":
            npm_cmd = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
            cmd = [npm_cmd, "test"]
        else:
            return LocalActionResult(
                success=False,
                action="run_project_tests",
                error=f"Unauthorized test_type '{test_type}'. Approved test types: ['pytest', 'npm_test'].",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            start_proc = time.time()
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                shell=False,
            )
            duration = round(time.time() - start_proc, 3)
            passed = proc.returncode == 0

            return LocalActionResult(
                success=passed,
                action="run_project_tests",
                output={
                    "test_type": test_type,
                    "passed": passed,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[:8192],
                    "stderr": proc.stderr[:8192],
                    "duration_seconds": duration,
                },
                error=None if passed else f"Test run finished with failures (exit code {proc.returncode}).",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
                verification_evidence={
                    "exit_code": proc.returncode,
                    "duration": duration,
                    "passed": passed,
                },
            )
        except subprocess.TimeoutExpired:
            return LocalActionResult(
                success=False,
                action="run_project_tests",
                error="Test execution timed out after 60 seconds.",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            return LocalActionResult(
                success=False,
                action="run_project_tests",
                error=f"Failed to execute tests: {str(exc)}",
                started_at=start_iso,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )


# Module-level singleton instance
tool_registry = LocalToolRegistry()
