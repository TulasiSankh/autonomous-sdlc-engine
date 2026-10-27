"""Comprehensive Automated Test Suite for Windows Local Agent & Action Execution.

Covers all 12 required scenarios specified in Section 8:
1. VS Code installed and not running.
2. VS Code already running.
3. VS Code installed outside PATH (Windows Registry / AppData lookup).
4. VS Code not installed.
5. Local agent offline (blocked status with actionable advice).
6. Process launch failure (OS / permission error).
7. Process verification failure (process exits immediately).
8. Unauthorized API request (invalid token or DNS rebinding Host header).
9. Invalid application name or path (allowlist and security confinement).
10. Task retry and duplicate submission.
11. False success prevention (null PID / failed verification cannot complete).
12. Frontend lifecycle updates and database persistence.
+ Real Windows integration test that launches and verifies VS Code if present.
"""

import os
import sys
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from local_agent.server import app as local_agent_app
from local_agent.config import get_or_create_token, HOST, PORT, TOKEN
from local_agent.system_inspector import (
    SystemInspector,
    AppDiscoveryResult,
    ProcessCheckResult,
    SystemEnvironmentInfo,
)
from local_agent.process_launcher import ProcessLauncher, ProcessLaunchResult
from local_agent.tool_registry import tool_registry, LocalActionResult
from local_agent.security import validate_authorized_path
from services.local_agent_client import LocalAgentClient, LocalAgentOfflineError
from orchestrator.execution_engine import ExecutionEngine
from agents.planner import PlannerAgent
from storage.database import Database
from services.task_service import TaskService, TaskRecord
from tools.base import ToolExecutionResult
from tools.verification_tool import VerificationTool
from tools.app_launcher_tool import AppLauncherTool


@pytest.fixture
def agent_token():
    return get_or_create_token()


@pytest.fixture
def agent_client():
    return TestClient(local_agent_app)


@pytest.fixture
def temp_task_service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    db = Database(db_path=db_path)
    service = TaskService(db=db)
    yield service
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


# ==============================================================================
# Scenario 1: VS Code installed and not running
# ==============================================================================
def test_scenario_1_vscode_installed_and_not_running():
    fake_code_path = "C:\\Program Files\\Microsoft VS Code\\Code.exe"

    mock_disc = AppDiscoveryResult(
        app_name="vscode",
        is_installed=True,
        executable_path=fake_code_path,
        discovery_method="path",
        locations_checked=["PATH"],
    )
    mock_running = ProcessCheckResult(
        app_name="vscode",
        is_running=False,
        pids=[],
        summary="Not running",
    )
    mock_launch = ProcessLaunchResult(
        success=True,
        pid=54321,
        executable=fake_code_path,
        started_at="2026-10-14T10:00:00Z",
        verified_alive=True,
        output_message="Process launched with PID 54321",
        verification_evidence={"pid": 54321, "kernel_alive": True},
    )

    with patch.object(SystemInspector, "discover_application", return_value=mock_disc):
        with patch.object(SystemInspector, "check_application_running", return_value=mock_running):
            with patch.object(ProcessLauncher, "launch", return_value=mock_launch):
                res = tool_registry.execute_action("open_vscode", {})
                assert res.success is True
                assert res.output["pid"] == 54321
                assert "54321" in res.output["message"]
                assert res.verification_evidence["kernel_alive"] is True


# ==============================================================================
# Scenario 2: VS Code already running
# ==============================================================================
def test_scenario_2_vscode_already_running():
    fake_code_path = "C:\\Program Files\\Microsoft VS Code\\Code.exe"

    mock_disc = AppDiscoveryResult(
        app_name="vscode",
        is_installed=True,
        executable_path=fake_code_path,
        discovery_method="registry",
        locations_checked=["Registry App Paths"],
    )
    mock_running = ProcessCheckResult(
        app_name="vscode",
        is_running=True,
        pids=[1234, 5678],
        summary="Running with 2 processes",
    )
    mock_launch = ProcessLaunchResult(
        success=True,
        pid=1234,
        executable=fake_code_path,
        started_at="2026-10-14T10:00:00Z",
        verified_alive=True,
        output_message="Attached to running process PID 1234",
        verification_evidence={"pid": 1234, "kernel_alive": True},
    )

    with patch.object(SystemInspector, "discover_application", return_value=mock_disc):
        with patch.object(SystemInspector, "check_application_running", return_value=mock_running):
            with patch.object(ProcessLauncher, "launch", return_value=mock_launch):
                res = tool_registry.execute_action("open_vscode", {})
                assert res.success is True
                assert res.verification_evidence["already_running_prior"] is True


# ==============================================================================
# Scenario 3: VS Code installed outside PATH (Windows Registry / AppData lookup)
# ==============================================================================
def test_scenario_3_vscode_installed_outside_path():
    fake_appdata_code = "C:\\Users\\user\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"

    # Simulate PATH containing no 'code'
    with patch("shutil.which", return_value=None):
        # Simulate registry returning the user AppData install path
        with patch("winreg.OpenKey"):
            with patch("winreg.QueryValueEx", return_value=(fake_appdata_code, 1)):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.is_file", return_value=True):
                        discovery = SystemInspector.discover_application("vscode")
                        assert discovery.is_installed is True
                        assert "registry" in discovery.discovery_method
                        assert "AppData" in discovery.executable_path


# ==============================================================================
# Scenario 4: VS Code not installed
# ==============================================================================
def test_scenario_4_vscode_not_installed():
    mock_disc = AppDiscoveryResult(
        app_name="vscode",
        is_installed=False,
        executable_path=None,
        actionable_help="Visual Studio Code was not found. Download from https://code.visualstudio.com/Download",
    )

    with patch.object(SystemInspector, "discover_application", return_value=mock_disc):
        res = tool_registry.execute_action("open_vscode", {})
        assert res.success is False
        assert "not found" in res.error.lower()
        assert "https://code.visualstudio.com" in res.error


# ==============================================================================
# Scenario 5: Local agent offline (transitions task to blocked)
# ==============================================================================
def test_scenario_5_local_agent_offline(temp_task_service):
    client = LocalAgentClient()

    # Simulate connection error to local agent daemon
    with patch("httpx.Client.get", side_effect=Exception("Connection refused [Errno 111]")):
        assert client.is_online() is False
        with pytest.raises(LocalAgentOfflineError) as exc_info:
            client.execute_action("open_vscode", {})
        assert "offline" in str(exc_info.value).lower()

    # Test that execution engine transitions task to 'blocked' with clear advice
    task = temp_task_service.create_task("Open VS Code")

    engine = ExecutionEngine(task_service=temp_task_service, local_agent_client=client)
    with patch.object(client, "is_online", return_value=False):
        executed_task = engine.execute_task(task.id)
        assert executed_task.status == "blocked"
        assert "offline" in executed_task.error_summary.lower()
        assert "start_local_agent" in executed_task.error_summary


# ==============================================================================
# Scenario 6: Process launch failure (OS / permission error)
# ==============================================================================
def test_scenario_6_process_launch_failure():
    with patch("pathlib.Path.exists", return_value=True):
        with patch("subprocess.Popen", side_effect=PermissionError("Access is denied (WinError 5)")):
            result = ProcessLauncher.launch("C:\\Windows\\System32\\test.exe")
            assert result.success is False
            assert result.pid is None
            assert "Access is denied" in result.error_message


# ==============================================================================
# Scenario 7: Process verification failure (process terminates immediately)
# ==============================================================================
def test_scenario_7_process_verification_failure():
    # Mock process that dies immediately after launch
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.poll.return_value = 1  # Exited with error code 1

    with patch("pathlib.Path.exists", return_value=True):
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch.object(SystemInspector, "verify_pid_alive", return_value=False):
                result = ProcessLauncher.launch("C:\\test\\crash.exe", verification_delay_seconds=0.01)
                assert result.success is False
                assert (
                    "terminated immediately" in result.error_message
                    or "exited prematurely" in result.error_message
                    or "failed" in result.error_message.lower()
                )


# ==============================================================================
# Scenario 8: Unauthorized API request & DNS rebinding protection
# ==============================================================================
def test_scenario_8_unauthorized_api_request(agent_client, agent_token):
    # 1. No token provided
    res_no_token = agent_client.get("/system/info")
    assert res_no_token.status_code == 401

    # 2. Invalid token provided
    res_bad_token = agent_client.get("/system/info", headers={"X-Orbit-Agent-Token": "invalid-token-12345"})
    assert res_bad_token.status_code == 401

    # 3. Valid token succeeds
    res_valid = agent_client.get("/system/info", headers={"X-Orbit-Agent-Token": agent_token})
    assert res_valid.status_code == 200
    assert "os_name" in res_valid.json()

    # 4. DNS rebinding attack (Host header pointing to external attacker domain)
    res_rebinding = agent_client.get(
        "/system/info",
        headers={
            "X-Orbit-Agent-Token": agent_token,
            "Host": "attacker.com",
        },
    )
    assert res_rebinding.status_code == 403
    assert "DNS rebinding" in res_rebinding.json()["detail"]


# ==============================================================================
# Scenario 9: Invalid application name or path
# ==============================================================================
def test_scenario_9_invalid_application_name_or_path():
    # 1. Dangerous disallowed application name
    res_danger = tool_registry.execute_action("launch_arbitrary", {"command": "cmd.exe /c del *.*"})
    assert res_danger.success is False
    assert "Unsupported local action" in res_danger.error

    # 2. Path traversal attack
    with pytest.raises(ValueError):
        validate_authorized_path("..\\..\\Windows\\System32\\calc.exe")

    # 3. Disallowed tool parameter
    res_bad_param = tool_registry.execute_action("read_project_file", {"file_path": "C:\\Windows\\System32\\drivers\\etc\\hosts"})
    assert res_bad_param.success is False
    assert "prohibited" in res_bad_param.error.lower() or "outside authorized" in res_bad_param.error.lower()


# ==============================================================================
# Scenario 10: Task retry and duplicate submission
# ==============================================================================
def test_scenario_10_task_retry_and_duplicate_submission(temp_task_service):
    task = temp_task_service.create_task("Open VS Code")
    engine = ExecutionEngine(task_service=temp_task_service)

    mock_tool = MagicMock()
    mock_tool.execute.side_effect = [
        ToolExecutionResult(
            success=False,
            tool_name="app_launcher",
            action="discover",
            error_message="Simulated temporary network/OS error",
        ),
        ToolExecutionResult(
            success=True,
            tool_name="app_launcher",
            action="discover",
            data={"found": True, "executable_path": "C:\\path\\Code.exe", "mock_launched": True},
        ),
        ToolExecutionResult(
            success=True,
            tool_name="app_launcher",
            action="launch",
            data={"launched": True, "pid": 12345, "mock_launched": True},
        ),
        ToolExecutionResult(
            success=True,
            tool_name="verification",
            action="verify_process_running",
            data={"verified": True, "pid": 12345},
        ),
        ToolExecutionResult(
            success=True,
            tool_name="verification",
            action="verify_visible_window",
            data={"verified": True, "window_verified": True},
        ),
    ]

    with patch.object(engine.registry, "get_tool", return_value=mock_tool):
        task_run1 = engine.execute_task(task.id)
        assert task_run1.status == "failed"

        task_run2 = engine.execute_task(task.id)
        assert task_run2.status == "completed"

        retrieved = temp_task_service.get_task(task.id)
        assert retrieved.id == task.id
        assert retrieved.status == "completed"


# ==============================================================================
# Scenario 11: False success prevention
# ==============================================================================
def test_scenario_11_false_success_prevention():
    v_tool = VerificationTool()

    # If verification is called without PID or with null PID, it must return False
    res_no_pid = v_tool.execute("verify_process_running", {"pid": None, "target": "vscode"})
    assert res_no_pid.success is False
    assert "pid" in res_no_pid.error.lower() or "missing" in res_no_pid.error.lower()

    # Verification Tool with non-existent PID
    res_dead_pid = v_tool.execute("verify_process_running", {"pid": 99999999, "target": "vscode"})
    assert res_dead_pid.success is False
    assert "not currently running" in res_dead_pid.error.lower()


# ==============================================================================
# Scenario 12: Lifecycle updates and database persistence
# ==============================================================================
def test_scenario_12_lifecycle_updates_and_database_persistence(temp_task_service):
    task = temp_task_service.create_task("Open VS Code")

    # Task transitions from planned -> executing -> verifying -> completed
    assert task.status == "planned"

    updated = temp_task_service.transition_task_status(task.id, "executing")
    assert updated.status == "executing"

    updated = temp_task_service.transition_task_status(task.id, "verifying")
    assert updated.status == "verifying"

    updated = temp_task_service.transition_task_status(
        task.id,
        "completed",
        execution_summary="VS Code launched with PID 12345 and confirmed active in Windows kernel.",
    )
    assert updated.status == "completed"
    assert "PID 12345" in updated.execution_summary

    # Ensure persistence to SQLite database
    persisted = temp_task_service.get_task(task.id)
    assert persisted.status == "completed"
    assert "PID 12345" in persisted.execution_summary


# ==============================================================================
# Real Windows Integration Test (Executed only if VS Code is installed)
# ==============================================================================
@pytest.mark.windows_real
def test_real_windows_integration_launch_vscode():
    """Real Windows integration test that checks for installed VS Code,

    inspects discovery, launches it safely (or connects to running instance),
    and verifies the live OS process table.
    """
    if sys.platform != "win32":
        pytest.skip("Skipping Windows-specific test on non-Windows environment.")

    discovery = SystemInspector.discover_application("vscode")
    if not discovery.is_installed or not discovery.executable_path:
        pytest.skip(f"VS Code executable not found on this Windows machine: {discovery}")

    # VS Code is found on this Windows machine
    code_path = discovery.executable_path
    assert os.path.exists(code_path), f"Discovered executable does not exist: {code_path}"

    # Execute through the real tool registry
    result = tool_registry.execute_action("open_vscode", {})
    assert result.success is True, f"Execution failed: {result}"

    # Verify PID reported
    pid = result.output.get("pid") if isinstance(result.output, dict) else None
    assert pid is not None, f"No PID returned from real execution: {result}"

    # Verify against real Windows kernel process table
    is_alive = SystemInspector.verify_pid_alive(pid)
    assert is_alive is True, f"Reported PID {pid} is not alive in Windows kernel process table."


# ==============================================================================
# Scenario 13: Process running without visible window transitions to partially_completed
# ==============================================================================
def test_scenario_13_process_running_without_visible_window(temp_task_service):
    task = temp_task_service.create_task("Open VS Code")
    engine = ExecutionEngine(task_service=temp_task_service)

    mock_tool = MagicMock()
    # Step 1: detect -> OK
    # Step 2: launch -> OK (PID 8888)
    # Step 3: verify_process_running -> OK (process exists)
    # Step 4: verify_visible_window -> FAILS (no window appeared on desktop)
    mock_tool.execute.side_effect = [
        ToolExecutionResult(
            success=True,
            tool_name="app_launcher",
            action="detect",
            output={"app_name": "vscode", "is_installed": True, "executable_path": "C:\\fake\\Code.exe"},
            metadata={"mock_launched": True},
        ),
        ToolExecutionResult(
            success=True,
            tool_name="app_launcher",
            action="launch",
            output={"app_name": "vscode", "pid": 8888},
            metadata={"pid": 8888, "mock_launched": True},
        ),
        ToolExecutionResult(
            success=True,
            tool_name="verification",
            action="verify_process_running",
            output="Process alive",
            metadata={"target": "vscode", "running": True},
        ),
        ToolExecutionResult(
            success=False,
            tool_name="verification",
            action="verify_visible_window",
            error="No visible window matching 'vscode' detected across desktop session within 3.0s timeout.",
            metadata={"target": "vscode", "window_verified": False},
        ),
    ]

    with patch.object(engine.registry, "get_tool", return_value=mock_tool):
        executed_task = engine.execute_task(task.id)
        # Never mark completed when visible window cannot be confirmed
        assert executed_task.status != "completed"
        assert executed_task.status in ("partially_completed", "failed")
        assert executed_task.verification_status == "failed"
        assert "visible window" in executed_task.error_summary.lower()


# ==============================================================================
# Scenario 14: Verification tool directly fails when visible window not present
# ==============================================================================
def test_scenario_14_verification_tool_visible_window_failure():
    v_tool = VerificationTool()

    with patch.object(SystemInspector, "verify_visible_window", return_value={
        "supported": True,
        "verified": False,
        "reason": "No visible window matching 'vscode' detected across desktop session within 3.0s timeout.",
        "windows": [],
    }):
        res = v_tool.execute("verify_visible_window", {"app_name": "vscode", "pid": 1234})
        assert res.success is False
        assert res.metadata["window_verified"] is False
        assert "No visible window" in res.error


# ==============================================================================
# Scenario 15: Verification tool succeeds when window is confirmed visible
# ==============================================================================
def test_scenario_15_verification_tool_visible_window_success():
    v_tool = VerificationTool()

    with patch.object(SystemInspector, "verify_visible_window", return_value={
        "supported": True,
        "verified": True,
        "primary_window": {"hwnd": 123456, "pid": 7777, "title": "Welcome - Visual Studio Code"},
        "windows": [{"hwnd": 123456, "pid": 7777, "title": "Welcome - Visual Studio Code"}],
    }):
        res = v_tool.execute("verify_visible_window", {"app_name": "vscode", "pid": 7777})
        assert res.success is True
        assert res.metadata["window_verified"] is True
        assert "Welcome - Visual Studio Code" in res.output

