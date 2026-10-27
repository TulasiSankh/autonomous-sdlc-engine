"""Verification tool for independently confirming that requested outcomes were genuinely achieved."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from tools.base import BaseTool, ToolExecutionResult


class VerificationTool(BaseTool):
    """Tool that independently validates task outcomes against real system state."""

    name = "verification"
    description = "Independently validates that real system changes or target outcomes match expectations."
    supported_actions = [
        "verify_path_exists",
        "verify_file_content",
        "verify_url_reachable",
        "verify_command_result",
        "verify_process_running",
        "verify_app_running",
        "verify_visible_window",
    ]

    def get_parameters_schema(self, action: Optional[str] = None) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "check_type": {
                    "type": "string",
                    "description": "Verification check: 'path_exists', 'file_content', 'url_reachable', 'command_result'.",
                },
                "target": {
                    "type": "string",
                    "description": "Path, URL, or identifier to verify.",
                },
                "expected": {
                    "type": "string",
                    "description": "Expected substring, exit code, or value.",
                },
            },
            "required": ["target"],
        }

    def execute(self, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        self.validate_action(action)

        target = params.get("target") or params.get("path") or params.get("url") or params.get("app_name")
        if not target and action not in ("verify_command_result", "verify_visible_window"):
            return ToolExecutionResult(
                success=False,
                error="Missing required parameter 'target'.",
            )

        target_str = str(target).strip() if target else ""

        if action == "verify_path_exists":
            return self._verify_path_exists(
                target_str,
                must_be_dir=params.get("must_be_dir", False),
                must_be_file=params.get("must_be_file", False),
            )
        elif action == "verify_file_content":
            return self._verify_file_content(
                target_str,
                expected_substring=params.get("expected", ""),
            )
        elif action == "verify_url_reachable":
            return self._verify_url_reachable(
                target_str,
                timeout=params.get("timeout", 5),
            )
        elif action == "verify_command_result":
            return self._verify_command_result(
                exit_code=params.get("exit_code"),
                expected_exit_code=params.get("expected_exit_code", 0),
            )
        elif action == "verify_process_running":
            app_target = params.get("app_name") or params.get("target") or ""
            return self._verify_process_running(
                app_target,
                pid=params.get("pid"),
                mock_launched=bool(params.get("mock_launched")),
                require_pid=True,
            )
        elif action == "verify_app_running":
            app_target = params.get("app_name") or params.get("target") or ""
            return self._verify_process_running(
                app_target,
                pid=params.get("pid"),
                mock_launched=bool(params.get("mock_launched")),
                require_pid=False,
            )
        elif action == "verify_visible_window":
            app_target = params.get("app_name") or params.get("target") or target_str
            return self._verify_visible_window(
                app_target,
                pid=params.get("pid"),
                mock_launched=bool(params.get("mock_launched")),
                timeout=float(params.get("timeout", 3.0)),
            )

        return ToolExecutionResult(success=False, error=f"Unhandled verification action '{action}'.")

    def _verify_visible_window(
        self,
        app_name: str,
        pid: Optional[int] = None,
        mock_launched: bool = False,
        timeout: float = 3.0,
    ) -> ToolExecutionResult:
        """Independently verifies that a visible top-level application window exists on the user's interactive desktop."""
        if mock_launched:
            return ToolExecutionResult(
                success=True,
                output=f"Verification passed: Custom mock visible window verified for '{app_name}'.",
                metadata={"target": app_name, "window_verified": True, "mock": True},
            )

        clean_app = app_name.strip().lower()
        if "\\" in clean_app or "/" in clean_app:
            clean_app = Path(clean_app).stem.lower()

        try:
            from local_agent.system_inspector import SystemInspector
            res = SystemInspector.verify_visible_window(clean_app, target_pid=pid, timeout_seconds=timeout)
            if res.get("verified"):
                primary = res.get("primary_window", {})
                w_title = primary.get("title", clean_app)
                w_pid = primary.get("pid", pid)
                return ToolExecutionResult(
                    success=True,
                    output=f"Verification passed: Visible window for '{clean_app}' confirmed on desktop: '{w_title}' (PID {w_pid}).",
                    metadata={
                        "target": clean_app,
                        "window_verified": True,
                        "title": w_title,
                        "pid": w_pid,
                        "evidence": res,
                    },
                )
            else:
                reason = res.get("reason", f"No visible window for '{clean_app}' detected on the user's desktop.")
                return ToolExecutionResult(
                    success=False,
                    error=f"Verification failed: {reason}",
                    metadata={
                        "target": clean_app,
                        "window_verified": False,
                        "pid": pid,
                        "evidence": res,
                    },
                )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Verification error checking visible window for '{clean_app}': {str(exc)}",
                metadata={"target": clean_app, "window_verified": False, "pid": pid},
            )

    def _verify_process_running(
        self,
        app_name: str,
        pid: Optional[int] = None,
        mock_launched: bool = False,
        require_pid: bool = True,
    ) -> ToolExecutionResult:
        """Independently verifies that a process or application is genuinely running on the system."""
        if mock_launched:
            return ToolExecutionResult(
                success=True,
                output=f"Verification passed: Custom mock launcher verified for '{app_name}'.",
                metadata={"target": app_name, "running": True, "mock": True},
            )

        clean_app = app_name.strip().lower()
        if "\\" in clean_app or "/" in clean_app:
            clean_app = Path(clean_app).stem.lower()

        # 1. If PID provided, verify via OS handle / kill check
        if pid is not None and int(pid) > 0:
            pid_int = int(pid)
            is_alive = False
            try:
                if sys.platform == "win32":
                    import ctypes
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_int)
                    if handle:
                        exit_code = ctypes.c_ulong()
                        if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                            ctypes.windll.kernel32.CloseHandle(handle)
                            is_alive = (exit_code.value == 259)  # STILL_ACTIVE
                        else:
                            ctypes.windll.kernel32.CloseHandle(handle)
                            is_alive = True
                else:
                    os.kill(pid_int, 0)
                    is_alive = True
            except Exception:
                is_alive = False

            if is_alive:
                return ToolExecutionResult(
                    success=True,
                    output=f"Verification passed: Process for '{app_name}' (PID {pid_int}) is confirmed active in Windows process table.",
                    metadata={"target": app_name, "pid": pid_int, "running": True},
                )
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: Process PID {pid_int} for '{app_name}' is not currently running.",
                metadata={"target": app_name, "pid": pid_int, "running": False},
            )

        # 2. If PID was required for process launch verification and is missing, strictly fail
        if require_pid:
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: Missing or null PID to verify launched process for '{app_name}'.",
                metadata={"target": app_name, "running": False},
            )

        # 3. Check running processes via SystemInspector for general app check
        try:
            from local_agent.system_inspector import SystemInspector
            check = SystemInspector.check_application_running(clean_app)
            if check.is_running:
                pids_str = ", ".join(str(p) for p in check.pids)
                return ToolExecutionResult(
                    success=True,
                    output=f"Verification passed: Application '{app_name}' is confirmed running (PID(s): {pids_str}).",
                    metadata={"target": app_name, "pids": check.pids, "running": True},
                )
        except Exception:
            pass

        # 4. If not running, verification strictly fails
        return ToolExecutionResult(
            success=False,
            error=f"Verification failed: Application '{app_name}' is not currently running on the operating system.",
            metadata={"target": app_name, "pid": pid, "running": False},
        )

    def _verify_path_exists(
        self, path_str: str, must_be_dir: bool = False, must_be_file: bool = False
    ) -> ToolExecutionResult:
        path = Path(path_str).resolve()
        exists = path.exists()

        if not exists:
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: path '{path}' does not exist on disk.",
                output={"exists": False, "target": str(path)},
                metadata={"target": str(path), "exists": False},
            )

        if must_be_dir and not path.is_dir():
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: path '{path}' exists but is not a directory.",
                output={"exists": True, "is_dir": False, "target": str(path)},
                metadata={"target": str(path), "is_dir": False},
            )

        if must_be_file and not path.is_file():
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: path '{path}' exists but is not a regular file.",
                output={"exists": True, "is_file": False, "target": str(path)},
                metadata={"target": str(path), "is_file": False},
            )

        item_type = "directory" if path.is_dir() else ("file" if path.is_file() else "path")
        return ToolExecutionResult(
            success=True,
            output={
                "message": f"Verification passed: {item_type} '{path}' exists on disk.",
                "exists": True,
                "target": str(path),
                "type": item_type,
            },
            metadata={"target": str(path), "exists": True, "type": item_type},
        )

    def _verify_file_content(self, file_path_str: str, expected_substring: str) -> ToolExecutionResult:
        path = Path(file_path_str).resolve()
        if not path.exists():
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: file '{path}' does not exist.",
                metadata={"target": str(path)},
            )
        if not path.is_file():
            return ToolExecutionResult(
                success=False,
                error=f"Verification failed: '{path}' is not a file.",
                metadata={"target": str(path)},
            )

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if expected_substring and expected_substring not in content:
                return ToolExecutionResult(
                    success=False,
                    error=f"Verification failed: expected content '{expected_substring}' was not found in '{path}'.",
                    metadata={"target": str(path), "expected_found": False},
                )

            return ToolExecutionResult(
                success=True,
                output=f"Verification passed: file '{path}' exists and contains expected content.",
                metadata={"target": str(path), "expected_found": True},
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Verification error while reading '{path}': {str(exc)}",
                metadata={"target": str(path)},
            )

    def _verify_url_reachable(self, url: str, timeout: int = 5) -> ToolExecutionResult:
        try:
            req = Request(url, headers={"User-Agent": "OrbitAI-VerificationBot/1.0"})
            with urlopen(req, timeout=timeout) as response:
                status_code = getattr(response, "status", 200)
                is_ok = 200 <= status_code < 400
                if is_ok:
                    return ToolExecutionResult(
                        success=True,
                        output=f"Verification passed: URL '{url}' is reachable (HTTP {status_code}).",
                        metadata={"url": url, "status_code": status_code},
                    )
                return ToolExecutionResult(
                    success=False,
                    error=f"Verification failed: URL '{url}' returned HTTP {status_code}.",
                    metadata={"url": url, "status_code": status_code},
                )
        except Exception as exc:
            # Network might be offline or URL might require specific user auth
            return ToolExecutionResult(
                success=False,
                error=f"Verification warning: unable to reach '{url}': {str(exc)}",
                metadata={"url": url, "reachable": False},
            )

    def _verify_command_result(
        self, exit_code: Optional[int], expected_exit_code: int = 0
    ) -> ToolExecutionResult:
        if exit_code is None:
            return ToolExecutionResult(
                success=False,
                error="Verification failed: command exit code is missing or execution did not complete.",
            )

        passed = (exit_code == expected_exit_code)
        if passed:
            return ToolExecutionResult(
                success=True,
                output=f"Verification passed: command finished with expected exit code {exit_code}.",
                metadata={"exit_code": exit_code},
            )
        return ToolExecutionResult(
            success=False,
            error=f"Verification failed: expected exit code {expected_exit_code}, but got {exit_code}.",
            metadata={"exit_code": exit_code, "expected": expected_exit_code},
        )
