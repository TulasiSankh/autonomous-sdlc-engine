"""Controlled process launcher for executing authorized local Windows actions."""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    import psutil  # type: ignore
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from local_agent.security import audit_log
from local_agent.system_inspector import SystemInspector


class ProcessLaunchResult(BaseModel):
    """Result of a controlled process launch attempt."""

    success: bool
    pid: Optional[int] = None
    executable: str
    args: List[str] = Field(default_factory=list)
    started_at: str
    duration_seconds: float = 0.0
    verified_alive: bool = False
    window_verified: bool = False
    window_evidence: Dict[str, Any] = Field(default_factory=dict)
    exit_code: Optional[int] = None
    output_message: str
    error_message: Optional[str] = None
    verification_evidence: Dict[str, Any] = Field(default_factory=dict)


class ProcessLauncher:
    """Safely launches Windows desktop applications without shell=True and verifies real execution."""

    @classmethod
    def launch(
        cls,
        executable_path: str,
        args: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        verification_delay_seconds: float = 0.5,
        verify_window: bool = True,
    ) -> ProcessLaunchResult:
        """Launches an executable in a detached process and confirms it is running and visible."""
        start_time = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        clean_args = args or []

        # Validate executable existence
        exe_path = Path(executable_path).resolve()
        if not exe_path.exists():
            return ProcessLaunchResult(
                success=False,
                executable=str(exe_path),
                args=clean_args,
                started_at=now_iso,
                output_message="",
                error_message=f"Executable path '{exe_path}' does not exist on disk.",
            )

        cmd = [str(exe_path)] + clean_args
        audit_log("launch_process", f"cmd={cmd}")

        creation_flags = 0
        startupinfo = None
        if sys.platform == "win32":
            # Explicitly route to interactive desktop WinSta0\Default so GUI windows appear on screen
            creation_flags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.lpDesktop = r"WinSta0\Default"
            except Exception:
                startupinfo = None

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=working_dir if working_dir and Path(working_dir).exists() else None,
                creationflags=creation_flags,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )

            actual_delay = max(verification_delay_seconds, 1.2)
            time.sleep(actual_delay)
            exit_code = proc.poll()
            duration = round(time.time() - start_time, 3)

            # Check if process terminated immediately with error
            if exit_code is not None and exit_code != 0:
                audit_log("process_crashed", f"pid={proc.pid} exit_code={exit_code}")
                return ProcessLaunchResult(
                    success=False,
                    pid=proc.pid,
                    executable=str(exe_path),
                    args=clean_args,
                    started_at=now_iso,
                    duration_seconds=duration,
                    verified_alive=False,
                    window_verified=False,
                    exit_code=exit_code,
                    output_message="",
                    error_message=f"Process terminated immediately after launch with exit code {exit_code}.",
                    verification_evidence={
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "exit_code": exit_code,
                        "alive": False,
                    },
                )

            # Check process aliveness
            is_alive = SystemInspector.verify_pid_alive(proc.pid)
            app_check = SystemInspector.check_application_running(exe_path.stem)
            if not is_alive:
                is_alive = app_check.is_running

            reported_pid = proc.pid
            if _PSUTIL_AVAILABLE and app_check.is_running and app_check.pids:
                reported_pid = max(app_check.pids)

            # Visible window verification
            window_verified = False
            window_evidence: Dict[str, Any] = {}
            if verify_window and sys.platform == "win32":
                win_check = SystemInspector.verify_visible_window(exe_path.stem, target_pid=reported_pid, timeout_seconds=2.5)
                window_verified = win_check.get("verified", False)
                window_evidence = win_check

            verification_evidence = {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "launcher_pid": proc.pid,
                "reported_pid": reported_pid,
                "alive": is_alive,
                "window_verified": window_verified,
                "verification_method": "windows_kernel_process_query",
                "process_name": exe_path.name,
                "running_instances": app_check.pids if app_check.is_running else [],
                "cmd": cmd,
                "window_evidence": window_evidence,
            }

            if not is_alive:
                audit_log("verification_failed", f"pid={proc.pid} not found in process table")
                return ProcessLaunchResult(
                    success=False,
                    pid=proc.pid,
                    executable=str(exe_path),
                    args=clean_args,
                    started_at=now_iso,
                    duration_seconds=duration,
                    verified_alive=False,
                    window_verified=False,
                    output_message="",
                    error_message=f"Process was created (PID: {proc.pid}) but could not be verified alive in the Windows process table.",
                    verification_evidence=verification_evidence,
                )

            audit_log("process_verified_running", f"pid={reported_pid} name={exe_path.name} window_verified={window_verified}")
            output_msg = (
                f"Successfully launched '{exe_path.name}' (PID: {reported_pid}) and verified visible window."
                if window_verified
                else f"Successfully launched '{exe_path.name}' (PID: {reported_pid}) and verified active Windows process."
            )

            return ProcessLaunchResult(
                success=True,
                pid=reported_pid,
                executable=str(exe_path),
                args=clean_args,
                started_at=now_iso,
                duration_seconds=duration,
                verified_alive=True,
                window_verified=window_verified,
                window_evidence=window_evidence,
                output_message=output_msg,
                verification_evidence=verification_evidence,
            )

        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            audit_log("launch_exception", str(exc))
            return ProcessLaunchResult(
                success=False,
                executable=str(exe_path),
                args=clean_args,
                started_at=now_iso,
                duration_seconds=duration,
                output_message="",
                error_message=f"Failed to launch process '{exe_path}': {str(exc)}",
            )
