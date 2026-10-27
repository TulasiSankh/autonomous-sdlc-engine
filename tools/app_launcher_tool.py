"""Application Launcher tool for opening directories or files in installed applications (VS Code, Antigravity, etc.)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tools.base import BaseTool, ToolExecutionResult


class AppLauncherTool(BaseTool):
    """Tool that safely discovers and launches local desktop applications with a target path."""

    name = "app_launcher"
    description = "Opens a folder or file in an installed application such as VS Code or Antigravity."
    supported_actions = ["open_in_app", "launch", "check_app_installed", "detect"]

    # Known application binary names and fallback paths
    APP_CANDIDATES: Dict[str, List[str]] = {
        "vscode": ["code", "code.cmd", "code.exe"],
        "code": ["code", "code.cmd", "code.exe"],
        "antigravity": ["antigravity", "antigravity.exe", "agy", "agy.cmd"],
        "sublime": ["subl", "sublime_text.exe"],
        "notepad": ["notepad.exe", "notepad"],
        "explorer": ["explorer.exe", "open", "xdg-open"],
    }

    def __init__(
        self,
        launcher_fn: Optional[Callable[[List[str]], bool]] = None,
        custom_app_paths: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initializes the application launcher.
        
        Args:
            launcher_fn: Custom subprocess launcher function (for testing/mocking).
            custom_app_paths: Map of app_name -> full executable path.
        """
        self._launcher_fn = launcher_fn
        self._custom_app_paths = custom_app_paths or {}

    def get_parameters_schema(self, action: Optional[str] = None) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The application to launch: 'vscode', 'code', 'antigravity', etc.",
                },
                "target_path": {
                    "type": "string",
                    "description": "Optional path to the directory or file to open in the application.",
                },
            },
            "required": ["app_name"],
        }

    def find_application_executable(self, app_name: str) -> Optional[str]:
        """Locates the executable for a given application on the system.
        
        Args:
            app_name: Name or alias of the application (e.g. 'vscode', 'code', 'antigravity').
            
        Returns:
            Resolved path or command string, or None if not found.
        """
        clean_app = app_name.strip().lower()

        # 1. Check custom configured paths
        if clean_app in self._custom_app_paths:
            path = self._custom_app_paths[clean_app]
            if Path(path).exists() or shutil.which(path):
                return path

        # 2. Check environment variables
        env_var_name = f"{clean_app.upper()}_PATH"
        env_path = os.getenv(env_var_name)
        if env_path and (Path(env_path).exists() or shutil.which(env_path)):
            return env_path

        if clean_app in ("vscode", "code"):
            code_env = os.getenv("VSCODE_PATH") or os.getenv("CODE_PATH")
            if code_env and (Path(code_env).exists() or shutil.which(code_env)):
                return code_env

        if "antigravity" in clean_app or clean_app in ("agy",):
            antigravity_home = (
                os.getenv("ANTIGRAVITY_HOME")
                or os.getenv("ANTIGRAVITY_PATH")
                or os.getenv("AGY_PATH")
            )
            if antigravity_home and (Path(antigravity_home).exists() or shutil.which(antigravity_home)):
                return antigravity_home

        # 3. Check candidates on system PATH
        candidates = self.APP_CANDIDATES.get(clean_app, [clean_app])
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        # 4. Platform-specific default install locations on Windows
        if sys.platform == "win32":
            local_app_data = os.getenv("LOCALAPPDATA", "")
            program_files = os.getenv("ProgramFiles", "")
            program_files_x86 = os.getenv("ProgramFiles(x86)", "")
            user_home: Optional[Path] = None
            try:
                user_home = Path.home()
            except Exception:
                user_home = None

            if clean_app in ("vscode", "code"):
                common_locations = []
                if local_app_data:
                    common_locations.extend([
                        Path(local_app_data) / "Programs" / "Microsoft VS Code" / "Code.exe",
                        Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
                    ])
                if program_files:
                    common_locations.extend([
                        Path(program_files) / "Microsoft VS Code" / "Code.exe",
                        Path(program_files) / "Microsoft VS Code" / "bin" / "code.cmd",
                    ])
                if program_files_x86:
                    common_locations.append(
                        Path(program_files_x86) / "Microsoft VS Code" / "Code.exe"
                    )
                for loc in common_locations:
                    if loc.exists():
                        return str(loc)

            if "antigravity" in clean_app or clean_app in ("agy",):
                common_agy = []
                if user_home:
                    common_agy.extend([
                        user_home / ".gemini" / "antigravity-ide" / "bin" / "antigravity.exe",
                        user_home / ".gemini" / "antigravity-ide" / "antigravity.exe",
                        user_home / ".gemini" / "antigravity" / "bin" / "antigravity.exe",
                    ])
                if local_app_data:
                    common_agy.extend([
                        Path(local_app_data) / "Programs" / "Antigravity" / "Antigravity.exe",
                        Path(local_app_data) / "Programs" / "Antigravity" / "bin" / "antigravity.cmd",
                    ])
                for loc in common_agy:
                    if loc.exists():
                        return str(loc)

            if clean_app == "notepad":
                sys32_notepad = Path(os.getenv("SystemRoot", "C:\\Windows")) / "System32" / "notepad.exe"
                if sys32_notepad.exists():
                    return str(sys32_notepad)

            # 5. Fallback to Windows Registry & App Paths discovery via SystemInspector
            if local_app_data or program_files:
                try:
                    from local_agent.system_inspector import SystemInspector
                    disc = SystemInspector.discover_application(clean_app)
                    if disc.is_installed and disc.executable_path:
                        return disc.executable_path
                except Exception:
                    pass

        return None

    def find_executable(self, app_name: str) -> Optional[str]:
        """Alias for find_application_executable."""
        return self.find_application_executable(app_name)

    def execute(self, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        self.validate_action(action)

        app_name = params.get("app_name")
        if not app_name or not str(app_name).strip():
            return ToolExecutionResult(
                success=False,
                error="Missing required parameter 'app_name'.",
            )

        clean_app = str(app_name).strip()
        executable = self.find_executable(clean_app)

        if action in ("check_app_installed", "detect"):
            is_installed = executable is not None
            return ToolExecutionResult(
                success=True,
                output={
                    "app_name": clean_app,
                    "is_installed": is_installed,
                    "detected": is_installed,
                    "executable_path": executable,
                    "path": executable,
                },
                metadata={
                    "app_name": clean_app,
                    "is_installed": is_installed,
                    "blocked": not is_installed,
                },
            )

        # Target path is optional (e.g. 'Open VS Code' has no target path)
        target_path_str = params.get("target_path")
        target_path: Optional[Path] = None
        if target_path_str and str(target_path_str).strip():
            target_path = Path(str(target_path_str).strip()).resolve()
            if not target_path.exists():
                return ToolExecutionResult(
                    success=False,
                    error=f"Target path '{target_path}' does not exist. Please create it before opening in an editor.",
                    metadata={"target_path": str(target_path), "blocked": True},
                )

        if executable is None:
            return ToolExecutionResult(
                success=False,
                error=(
                    f"Application '{clean_app}' was not found on PATH or common installation locations. "
                    f"Please install '{clean_app}', ensure it is added to PATH, or set the {clean_app.upper()}_PATH environment variable to configure its executable path."
                ),
                metadata={
                    "app_name": clean_app,
                    "blocked": True,
                    "target_path": str(target_path) if target_path else None,
                },
            )

        cmd = [executable, str(target_path)] if target_path is not None else [executable]

        try:
            if self._launcher_fn is not None:
                launched = self._launcher_fn(cmd)
                if not launched:
                    return ToolExecutionResult(
                        success=False,
                        error=f"Custom launcher returned False for command: {cmd}",
                        metadata={"app_name": clean_app, "blocked": True},
                    )
                return ToolExecutionResult(
                    success=True,
                    output=(
                        f"Successfully launched '{clean_app}' with '{target_path}'."
                        if target_path
                        else f"Successfully launched '{clean_app}'."
                    ),
                    metadata={
                        "app_name": clean_app,
                        "executable": executable,
                        "target_path": str(target_path) if target_path else None,
                        "mock_launched": True,
                    },
                )
            else:
                # Build the command — for VS Code always pass --new-window so that
                # VS Code's single-instance IPC protocol forces a new visible window
                # instead of silently delegating to an already-running instance.
                is_vscode = clean_app in ("vscode", "code")
                if is_vscode:
                    # --new-window must come before the target path
                    extra_args = ["--new-window"]
                    if target_path is not None:
                        extra_args.append(str(target_path))
                    cmd = [executable] + extra_args
                else:
                    cmd = [executable, str(target_path)] if target_path is not None else [executable]

                # Launch asynchronously without shell=True.
                # Use CREATE_NEW_PROCESS_GROUP so Ctrl+C doesn't propagate.
                # Do NOT use DETACHED_PROCESS — it disconnects the process from
                # the current desktop window station and prevents GUI windows from
                # appearing on screen.
                creation_flags = 0
                startupinfo = None
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
                    try:
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.lpDesktop = r"WinSta0\Default"
                    except Exception:
                        startupinfo = None

                proc = subprocess.Popen(
                    cmd,
                    creationflags=creation_flags,
                    startupinfo=startupinfo,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                )

                # Brief wait so VS Code's launcher can hand off to IPC and
                # spawn child processes before we poll for instant-crash.
                import time as _time
                _time.sleep(0.3)

                # Capture immediate exit failure if process crashed instantly
                immediate_exit = proc.poll()
                if immediate_exit is not None and immediate_exit != 0:
                    return ToolExecutionResult(
                        success=False,
                        error=f"Application '{clean_app}' terminated immediately with exit code {immediate_exit}.",
                        metadata={"app_name": clean_app, "executable": executable, "exit_code": immediate_exit},
                    )

                active_pid = proc.pid
                # On Windows, single-instance applications or execution aliases (Notepad/VSCode)
                # may hand off immediately to a delegated process. Capture the active running PID.
                if sys.platform == "win32":
                    try:
                        from local_agent.system_inspector import SystemInspector
                        if not SystemInspector.verify_pid_alive(proc.pid):
                            app_check = SystemInspector.check_application_running(clean_app)
                            if app_check.is_running and app_check.pids:
                                active_pid = max(app_check.pids)
                    except Exception:
                        pass

                output_msg = (
                    f"Successfully launched '{clean_app}' with '{target_path}' (PID: {active_pid})."
                    if target_path
                    else f"Successfully launched '{clean_app}' (PID: {active_pid})."
                )
                return ToolExecutionResult(
                    success=True,
                    output=output_msg,
                    metadata={
                        "app_name": clean_app,
                        "executable": executable,
                        "target_path": str(target_path) if target_path else None,
                        "pid": active_pid,
                    },
                )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Failed to launch '{clean_app}': {str(exc)}",
                metadata={"app_name": clean_app, "executable": executable},
            )
