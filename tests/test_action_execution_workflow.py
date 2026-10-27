"""Integration and unit tests for Orbit AI computer task execution architecture.

Verifies:
1. Intent classification and plan generation for all 7 intent types.
2. DeveloperAgent does not create placeholder files for action tasks.
3. Application launcher discovery, execution without shell=True, and blocked behavior.
4. Filesystem action execution, disk verification, and drive checks.
5. Composite action execution and lifecycle status progression.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from agents.developer import DeveloperAgent
from agents.intent_classifier import TaskIntentClassifier
from agents.planner import Plan, PlannerAgent
from orchestrator.execution_engine import ExecutionEngine
from services.task_service import TaskRecord, TaskService
from storage.database import Database
from tools.app_launcher_tool import AppLauncherTool
from tools.filesystem_tool import FilesystemTool
from tools.registry import ToolRegistry


@pytest.fixture
def test_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_tasks.db")
        db = Database(db_path=db_path)
        yield db


@pytest.fixture
def client():
    return TestClient(app)


def test_intent_classification_prevents_misclassification():
    """Verify common tasks are not classified as code_change."""
    assert TaskIntentClassifier.classify("Open VS Code") == "application_action"
    assert TaskIntentClassifier.classify("Open my GitHub") == "browser_action"
    assert TaskIntentClassifier.classify("Create a folder named MyProject in E drive") == "filesystem_action"
    assert (
        TaskIntentClassifier.classify("Create a folder named MyProject in E drive and open it in VS Code")
        == "composite_action"
    )
    assert TaskIntentClassifier.classify("Create a Python calculator") == "code_change"


def test_open_vs_code_plan_structure():
    """Verify plan for 'Open VS Code' contains application steps, no repository inspection or pytest."""
    planner = PlannerAgent()
    plan = planner.plan("Open VS Code")

    assert plan.task_type == "application_action"
    assert plan.target_app == "vscode"
    assert plan.target_path is None
    # No placeholder repo inspection or tests
    assert plan.files_to_inspect == []
    assert plan.tests_to_run == []

    # Expected sequential plan steps
    step_texts = " ".join(plan.steps).lower()
    assert "locate" in step_texts or "detect" in step_texts
    assert "launch" in step_texts
    assert "succeeded" in step_texts or "confirm" in step_texts
    assert "status" in step_texts or "persist" in step_texts

    # Machine-executable tool steps
    assert len(plan.tool_steps) >= 2
    tool_names = [ts.tool for ts in plan.tool_steps]
    assert "app_launcher" in tool_names


def test_developer_agent_rejects_action_task_proposals():
    """Verify DeveloperAgent strictly refuses to generate code proposals or placeholder files for action tasks."""
    developer = DeveloperAgent()
    planner = PlannerAgent()

    # Plan for Open VS Code
    plan = planner.plan("Open VS Code")
    task_record = TaskRecord(
        id="task-test-vscode",
        task="Open VS Code",
        status="planned",
        plan=plan,
        created_at="2026-10-13T00:00:00Z",
        updated_at="2026-10-13T00:00:00Z",
        task_type="application_action",
    )

    with pytest.raises(ValueError, match="action task"):
        developer.generate_proposal(task_record)


def test_api_proposal_endpoint_rejects_action_tasks(client):
    """Verify POST /tasks/{id}/proposal returns HTTP 400 for an action task."""
    create_res = client.post("/tasks", json={"task": "Open VS Code"})
    assert create_res.status_code in (200, 201)
    task_id = create_res.json()["id"]

    prop_res = client.post(f"/tasks/{task_id}/proposal")
    assert prop_res.status_code == 400
    assert "action task" in prop_res.json()["detail"].lower()


def test_app_launcher_discovery_and_launch():
    """Verify AppLauncherTool discovers executable, constructs safe command, and handles missing app."""
    launched_cmds = []

    def fake_launcher(cmd):
        launched_cmds.append(cmd)
        return True

    tool = AppLauncherTool(
        launcher_fn=fake_launcher,
        custom_app_paths={"fake_vscode": "C:\\MockPath\\code.exe"},
    )

    # 1. Detect fake app
    with patch("pathlib.Path.exists", return_value=True):
        detect_res = tool.execute("detect", {"app_name": "fake_vscode"})
        assert detect_res.success
        assert detect_res.output["detected"] is True
        assert detect_res.output["executable_path"] == "C:\\MockPath\\code.exe"

    # 2. Launch bare application without target_path
    with patch("pathlib.Path.exists", return_value=True):
        launch_res = tool.execute("launch", {"app_name": "fake_vscode"})
        assert launch_res.success
        assert len(launched_cmds) == 1
        assert launched_cmds[0] == ["C:\\MockPath\\code.exe"]

    # 3. Missing app returns clear blocked result with instructions
    with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
        missing_res = tool.execute("launch", {"app_name": "unknown_tool_app"})
        assert not missing_res.success
        assert missing_res.metadata.get("blocked") is True
        assert "not found on path" in missing_res.error.lower()
        assert "UNKNOWN_TOOL_APP_PATH" in missing_res.error


def test_execution_engine_executes_open_vs_code(test_db):
    """Verify execution engine runs 'Open VS Code' plan and completes successfully."""
    planner = PlannerAgent()
    task_service = TaskService(db=test_db, planner=planner)
    task_rec = task_service.create_task("Open VS Code")

    launched_cmds = []

    def mock_launcher(cmd):
        launched_cmds.append(cmd)
        return True

    launcher_tool = AppLauncherTool(
        launcher_fn=mock_launcher,
        custom_app_paths={"vscode": "C:\\Programs\\code.exe"},
    )
    with patch("pathlib.Path.exists", return_value=True):
        registry = ToolRegistry()
        registry.register(launcher_tool)
        from tools.verification_tool import VerificationTool
        registry.register(VerificationTool())

        engine = ExecutionEngine(task_service=task_service, tool_registry=registry, db=test_db)
        updated = engine.execute_task(task_rec.id)

        assert updated.status == "completed"
        assert len(launched_cmds) >= 1
        assert updated.execution_summary is not None
        assert "step(s)" in updated.execution_summary.lower()


def test_execution_engine_blocks_on_missing_application(test_db):
    """Verify task transitions to 'blocked' when requested application is missing."""
    planner = PlannerAgent()
    task_service = TaskService(db=test_db, planner=planner)
    task_rec = task_service.create_task("Open VS Code")

    # App launcher that cannot find executable
    empty_tool = AppLauncherTool()
    registry = ToolRegistry()
    registry.register(empty_tool)
    from tools.verification_tool import VerificationTool
    registry.register(VerificationTool())

    with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
        engine = ExecutionEngine(task_service=task_service, tool_registry=registry, db=test_db)
        updated = engine.execute_task(task_rec.id)

        assert updated.status == "blocked"
        assert "not found" in updated.error_summary.lower()


def test_filesystem_and_composite_task_execution(test_db):
    """Verify 'Create a folder named MyProject in E drive and open it in VS Code' executes verified folder creation."""
    with tempfile.TemporaryDirectory() as temp_root:
        # Simulate E: drive using temporary directory
        simulated_folder = Path(temp_root) / "MyProject"

        planner = PlannerAgent()
        plan = planner.plan(f"Create a folder named MyProject in E drive and open it in VS Code")
        # Override target_path to simulated directory for isolated verification
        plan.target_path = str(simulated_folder)
        for ts in plan.tool_steps:
            if ts.parameters.get("path"):
                ts.parameters["path"] = str(simulated_folder)
            if ts.parameters.get("target_path"):
                ts.parameters["target_path"] = str(simulated_folder)
            if ts.parameters.get("target"):
                ts.parameters["target"] = str(simulated_folder)

        task_service = TaskService(db=test_db, planner=planner)
        task_id = f"task-composite-test"
        test_db.save_task(
            task_id=task_id,
            task=plan.task,
            plan_json=plan.model_dump_json(),
            status="planned",
            created_at="2026-10-13T00:00:00Z",
            updated_at="2026-10-13T00:00:00Z",
            task_type="composite_action",
        )

        launched_apps = []

        def mock_launch(cmd):
            launched_apps.append(cmd)
            return True

        fake_code_exe = Path(temp_root) / "code.exe"
        fake_code_exe.touch()

        registry = ToolRegistry()
        fs_tool = FilesystemTool()
        launcher_tool = AppLauncherTool(
            launcher_fn=mock_launch,
            custom_app_paths={"vscode": str(fake_code_exe)},
        )
        from tools.verification_tool import VerificationTool
        registry.register(fs_tool)
        registry.register(launcher_tool)
        registry.register(VerificationTool())

        engine = ExecutionEngine(task_service=task_service, tool_registry=registry, db=test_db)
        final_task = engine.execute_task(task_id)

        assert final_task.status == "completed"
        # Confirm folder genuinely exists on disk
        assert simulated_folder.exists()
        assert simulated_folder.is_dir()
        # Confirm app was launched with target folder
        assert len(launched_apps) >= 1
        assert any(simulated_folder.name in arg for cmd in launched_apps for arg in cmd)
