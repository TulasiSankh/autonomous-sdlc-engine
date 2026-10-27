"""System inspection module for detecting Windows OS environment, applications, and processes."""

import csv
import ctypes
import getpass
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


class SystemEnvironmentInfo(BaseModel):
    """Detailed host operating system and execution environment info."""

    os_name: str = Field(..., description="Operating system name, e.g. Windows.")
    os_release: str = Field(..., description="Operating system release, e.g. 11 or 10.")
    os_version: str = Field(..., description="Detailed OS build version.")
    architecture: str = Field(..., description="CPU architecture, e.g. AMD64 or x86_64.")
    platform_string: str = Field(..., description="Full platform descriptor.")
    username: str = Field(..., description="Current Windows login username.")
    hostname: str = Field(..., description="Computer hostname.")
    user_home: str = Field(..., description="User home directory path.")
    current_working_dir: str = Field(..., description="Working directory.")
    is_admin: bool = Field(..., description="Whether running with elevated administrator rights.")
    python_version: str = Field(..., description="Python runtime version.")


class AppDiscoveryResult(BaseModel):
    """Structured report of an application discovery attempt."""

    app_name: str
    is_installed: bool
    executable_path: Optional[str] = None
    discovery_method: Optional[str] = None
    version: Optional[str] = None
    locations_checked: List[str] = Field(default_factory=list)
    actionable_help: Optional[str] = None


class ProcessCheckResult(BaseModel):
    """Result of checking whether an application or PID is running."""

    app_name: str
    is_running: bool
    pids: List[int] = Field(default_factory=list)
    process_names: List[str] = Field(default_factory=list)
    details: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str


class SystemInspector:
    """Inspects Windows local computer hardware, OS, installed apps, and running processes."""

    # Standard candidate file names for known applications
    APP_EXECUTABLES: Dict[str, List[str]] = {
        "vscode": ["code.exe", "Code.exe", "code.cmd"],
        "code": ["code.exe", "Code.exe", "code.cmd"],
        "notepad": ["notepad.exe"],
        "explorer": ["explorer.exe"],
        "terminal": ["wt.exe", "cmd.exe", "powershell.exe"],
    }

    # Registry App Paths keys
    APP_REG_PATHS: Dict[str, List[str]] = {
        "vscode": ["code.exe", "Code.exe"],
        "code": ["code.exe", "Code.exe"],
        "notepad": ["notepad.exe"],
        "explorer": ["explorer.exe"],
    }

    @classmethod
    def get_environment_info(cls) -> SystemEnvironmentInfo:
        """Inspects and returns current host operating system and environment."""
        is_admin = False
        if sys.platform == "win32":
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                is_admin = False
        else:
            is_admin = os.geteuid() == 0 if hasattr(os, "geteuid") else False

        return SystemEnvironmentInfo(
            os_name=platform.system(),
            os_release=platform.release(),
            os_version=platform.version(),
            architecture=platform.machine(),
            platform_string=platform.platform(),
            username=getpass.getuser(),
            hostname=platform.node(),
            user_home=os.path.expanduser("~"),
            current_working_dir=os.getcwd(),
            is_admin=is_admin,
            python_version=platform.python_version(),
        )

    @classmethod
    def discover_application(cls, app_name: str) -> AppDiscoveryResult:
        """Discovers an installed desktop application on Windows using multiple reliable strategies."""
        clean_app = app_name.strip().lower()
        locations_checked: List[str] = []

        # 1. Check Windows Registry App Paths (HKCU & HKLM) - Highest priority for Windows desktop apps
        if winreg and sys.platform == "win32":
            reg_names = cls.APP_REG_PATHS.get(clean_app, [f"{clean_app}.exe"])
            for rname in reg_names:
                for root_key, root_name in [
                    (winreg.HKEY_CURRENT_USER, "HKCU"),
                    (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
                ]:
                    sub_key = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{rname}"
                    locations_checked.append(rf"{root_name}\{sub_key}")
                    try:
                        with winreg.OpenKey(root_key, sub_key) as k:
                            val, _ = winreg.QueryValueEx(k, "")
                            if val and Path(val).exists() and Path(val).is_file():
                                return AppDiscoveryResult(
                                    app_name=clean_app,
                                    is_installed=True,
                                    executable_path=str(Path(val).resolve()),
                                    discovery_method=f"registry_app_paths_{root_name}",
                                    locations_checked=locations_checked,
                                )
                    except Exception:
                        pass

        # 2. Check custom environment variable
        env_var_name = f"{clean_app.upper()}_PATH"
        env_val = os.getenv(env_var_name) or (os.getenv("VSCODE_PATH") if clean_app in ("vscode", "code") else None)
        if env_val:
            locations_checked.append(f"env:{env_var_name} ({env_val})")
            p = Path(env_val)
            if p.exists() and p.is_file():
                return AppDiscoveryResult(
                    app_name=clean_app,
                    is_installed=True,
                    executable_path=str(p.resolve()),
                    discovery_method=f"environment_variable_{env_var_name}",
                    locations_checked=locations_checked,
                )

        # 3. Check system PATH
        candidates = cls.APP_EXECUTABLES.get(clean_app, [f"{clean_app}.exe", clean_app])
        for cand in candidates:
            locations_checked.append(f"PATH:{cand}")
            resolved = shutil.which(cand)
            if resolved:
                res_path = Path(resolved).resolve()
                if res_path.exists():
                    return AppDiscoveryResult(
                        app_name=clean_app,
                        is_installed=True,
                        executable_path=str(res_path),
                        discovery_method="system_path",
                        locations_checked=locations_checked,
                    )

        # 4. Check standard Windows installation directories
        if sys.platform == "win32":
            local_app_data = os.getenv("LOCALAPPDATA", "")
            program_files = os.getenv("ProgramFiles", "")
            program_files_x86 = os.getenv("ProgramFiles(x86)", "")

            std_candidates: List[Path] = []
            if clean_app in ("vscode", "code"):
                if local_app_data:
                    std_candidates.extend([
                        Path(local_app_data) / "Programs" / "Microsoft VS Code" / "Code.exe",
                        Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
                    ])
                if program_files:
                    std_candidates.extend([
                        Path(program_files) / "Microsoft VS Code" / "Code.exe",
                        Path(program_files) / "Microsoft VS Code" / "bin" / "code.cmd",
                    ])
                if program_files_x86:
                    std_candidates.extend([
                        Path(program_files_x86) / "Microsoft VS Code" / "Code.exe",
                        Path(program_files_x86) / "Microsoft VS Code" / "bin" / "code.cmd",
                    ])
            elif clean_app == "notepad":
                sys_root = os.getenv("SystemRoot", "C:\\Windows")
                std_candidates.extend([
                    Path(sys_root) / "System32" / "notepad.exe",
                    Path(sys_root) / "notepad.exe",
                ])
                if local_app_data:
                    std_candidates.append(Path(local_app_data) / "Microsoft" / "WindowsApps" / "notepad.exe")
            elif clean_app == "explorer":
                sys_root = os.getenv("SystemRoot", "C:\\Windows")
                std_candidates.append(Path(sys_root) / "explorer.exe")

            for cand_path in std_candidates:
                locations_checked.append(str(cand_path))
                if cand_path.exists() and cand_path.is_file():
                    return AppDiscoveryResult(
                        app_name=clean_app,
                        is_installed=True,
                        executable_path=str(cand_path.resolve()),
                        discovery_method="standard_directory",
                        locations_checked=locations_checked,
                    )

        # 5. Check Windows Uninstall registry keys for installation directory
        if winreg and sys.platform == "win32" and clean_app in ("vscode", "code"):
            uninstall_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM_WOW64"),
            ]
            for root_key, sub_path, label in uninstall_paths:
                locations_checked.append(rf"{label}\{sub_path}")
                try:
                    with winreg.OpenKey(root_key, sub_path) as ukey:
                        num_subkeys, _, _ = winreg.QueryInfoKey(ukey)
                        for i in range(num_subkeys):
                            try:
                                sk_name = winreg.EnumKey(ukey, i)
                                with winreg.OpenKey(ukey, sk_name) as sk:
                                    try:
                                        disp_name, _ = winreg.QueryValueEx(sk, "DisplayName")
                                        if "visual studio code" in str(disp_name).lower():
                                            try:
                                                inst_loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                                                cand = Path(inst_loc) / "Code.exe"
                                                if cand.exists():
                                                    return AppDiscoveryResult(
                                                        app_name=clean_app,
                                                        is_installed=True,
                                                        executable_path=str(cand.resolve()),
                                                        discovery_method=f"registry_uninstall_{label}",
                                                        locations_checked=locations_checked,
                                                    )
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception:
                    pass

        # Not found anywhere
        help_msg = (
            f"Application '{clean_app}' was not found on your Windows computer. "
            f"Checked {len(locations_checked)} standard locations, PATH, and registry. "
        )
        if clean_app in ("vscode", "code"):
            help_msg += (
                "Please install Visual Studio Code from https://code.visualstudio.com/Download "
                "or set the VSCODE_PATH environment variable to its Code.exe location."
            )
        else:
            help_msg += f"Please ensure '{clean_app}' is installed and added to PATH."

        return AppDiscoveryResult(
            app_name=clean_app,
            is_installed=False,
            executable_path=None,
            discovery_method=None,
            locations_checked=locations_checked,
            actionable_help=help_msg,
        )

    @classmethod
    def get_running_processes(cls) -> List[Dict[str, Any]]:
        """Lists running processes on Windows using tasklist."""
        processes: List[Dict[str, Any]] = []
        if sys.platform != "win32":
            return processes

        try:
            cmd = ["tasklist", "/FO", "CSV", "/NH"]
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            reader = csv.reader(output.splitlines())
            for row in reader:
                if len(row) >= 5:
                    p_name = row[0].strip()
                    try:
                        p_pid = int(row[1].strip())
                    except ValueError:
                        continue
                    p_session = row[2].strip()
                    p_session_num = row[3].strip()
                    p_mem = row[4].strip()
                    processes.append({
                        "name": p_name,
                        "pid": p_pid,
                        "session": p_session,
                        "session_number": p_session_num,
                        "memory": p_mem,
                    })
        except Exception:
            pass

        return processes

    @classmethod
    def check_application_running(cls, app_name: str) -> ProcessCheckResult:
        """Checks if any processes for the specified application are currently active."""
        clean_app = app_name.strip().lower()

        # Map application aliases to candidate process names
        target_names = {"code.exe"} if clean_app in ("vscode", "code") else {
            "notepad.exe" if clean_app == "notepad" else f"{clean_app}.exe"
        }
        if clean_app == "explorer":
            target_names = {"explorer.exe"}

        running = cls.get_running_processes()
        matched: List[Dict[str, Any]] = []
        pids: List[int] = []
        proc_names: List[str] = []

        for p in running:
            pname_lower = p["name"].lower()
            if any(t in pname_lower for t in target_names):
                matched.append(p)
                pids.append(p["pid"])
                if p["name"] not in proc_names:
                    proc_names.append(p["name"])

        is_running = len(pids) > 0
        summary = (
            f"Application '{clean_app}' is currently RUNNING with PID(s): {', '.join(str(p) for p in pids)} ({len(pids)} process instance(s))."
            if is_running
            else f"Application '{clean_app}' is NOT currently running."
        )

        return ProcessCheckResult(
            app_name=clean_app,
            is_running=is_running,
            pids=pids,
            process_names=proc_names,
            details=matched,
            summary=summary,
        )

    @classmethod
    def verify_pid_alive(cls, pid: int) -> bool:
        """Independently verifies via Windows kernel API whether a PID is currently alive."""
        if pid <= 0:
            return False

        if sys.platform == "win32":
            try:
                # OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION (0x1000)
                handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
                if handle:
                    # Check exit code
                    exit_code = ctypes.c_ulong()
                    # STILL_ACTIVE = 259
                    if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                        ctypes.windll.kernel32.CloseHandle(handle)
                        return exit_code.value == 259
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return True
                return False
            except Exception:
                # Fallback to tasklist check
                running = cls.get_running_processes()
                return any(p["pid"] == pid for p in running)
        else:
            try:
                os.kill(int(pid), 0)
                return True
            except OSError:
                return False

    @classmethod
    def verify_visible_window(
        cls,
        app_name: str,
        target_pid: Optional[int] = None,
        timeout_seconds: float = 3.0,
        poll_interval: float = 0.4,
    ) -> Dict[str, Any]:
        """Independently verifies via Windows User32 APIs whether a visible window exists for the app.
        
        Inspects the interactive desktop station ('WinSta0\\Default') as well as any active desktops.
        Handles applications that legitimately run without visible windows, delayed startup,
        and multiple/existing instances.
        """
        clean_app = app_name.strip().lower()
        if "\\" in clean_app or "/" in clean_app:
            clean_app = Path(clean_app).stem.lower()

        # Keywords to match window title for common desktop apps
        app_keywords: Dict[str, List[str]] = {
            "vscode": ["visual studio code", " - code", "welcome - visual studio code"],
            "code": ["visual studio code", " - code", "welcome - visual studio code"],
            "notepad": ["notepad", "untitled - notepad"],
            "explorer": ["file explorer", "explorer"],
        }
        keywords = app_keywords.get(clean_app, [clean_app])

        if sys.platform != "win32":
            # For non-Windows platforms (or mocked Linux in tests), return structured evidence
            return {
                "supported": False,
                "verified": False,
                "reason": "Visible window verification via Win32 API is only supported on Windows.",
                "app_name": clean_app,
                "windows": [],
            }

        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int64, ctypes.c_int64)

        # Collect desktops to inspect
        desktops_to_check = ["Default"]
        try:
            hwinsta = user32.GetProcessWindowStation()
            found_desks: List[str] = []
            def desk_cb(desk_name, lparam):
                if desk_name and str(desk_name) not in found_desks:
                    found_desks.append(str(desk_name))
                return True
            DESKENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_wchar_p, ctypes.c_int64)
            user32.EnumDesktopsW(hwinsta, DESKENUMPROC(desk_cb), 0)
            for d in found_desks:
                if d not in desktops_to_check:
                    desktops_to_check.append(d)
        except Exception:
            pass

        import time as _time
        start_time = _time.time()

        while True:
            for desk_name in desktops_to_check:
                hdesk = user32.OpenDesktopW(desk_name, 0, False, 0x01FF)
                if not hdesk:
                    continue

                visible_windows: List[Dict[str, Any]] = []

                def proc_cb(hwnd, lparam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            w_pid = ctypes.c_ulong()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(w_pid))
                            
                            # Match criteria: title keywords OR matched target_pid
                            matches_title = any(k in title.lower() for k in keywords)
                            matches_pid = (target_pid is not None and int(w_pid.value) == int(target_pid))
                            
                            if matches_title or matches_pid:
                                visible_windows.append({
                                    "hwnd": hwnd,
                                    "pid": w_pid.value,
                                    "title": title,
                                    "desktop": desk_name,
                                    "is_interactive_desktop": (desk_name.lower() == "default"),
                                })
                    return True

                user32.EnumDesktopWindows(hdesk, WNDENUMPROC(proc_cb), 0)
                user32.CloseDesktop(hdesk)

                if visible_windows:
                    primary = visible_windows[0]
                    # Bring window to foreground so it actively opens in front of user
                    try:
                        hwnd_val = primary.get("hwnd")
                        if hwnd_val:
                            # SW_RESTORE = 9, SW_SHOW = 5
                            user32.ShowWindowAsync(hwnd_val, 9)
                            user32.SetForegroundWindow(hwnd_val)
                    except Exception:
                        pass

                    return {
                        "supported": True,
                        "verified": True,
                        "app_name": clean_app,
                        "primary_window": primary,
                        "windows": visible_windows,
                        "count": len(visible_windows),
                        "verification_method": "windows_enum_desktop_windows",
                    }

            if _time.time() - start_time >= timeout_seconds:
                break
            _time.sleep(poll_interval)

        return {
            "supported": True,
            "verified": False,
            "app_name": clean_app,
            "reason": f"No visible window matching '{clean_app}' detected across desktop session within {timeout_seconds}s timeout.",
            "windows": [],
            "verification_method": "windows_enum_desktop_windows",
        }
