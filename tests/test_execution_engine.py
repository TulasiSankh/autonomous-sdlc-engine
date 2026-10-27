"""Tests for ExecutionEngine coordinating computer task execution."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from agents.planner import Plan, ToolStep
from orchestrator.execution_engine import ExecutionEngine
from services.task_service import TaskRecord, TaskService
from storage.database import Database
from tools.base import ToolExecutionResult
from tools.registry import ToolRegistry


@pytest.fixture
def mock_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path=db_path)
    yield db
    try:
        os.remove(db_path)
    except Exception:
        pass


def test_execute_browser_task_success(mock_db):
    task_service = TaskService(db=mock_db)
    registry = ToolRegistry()

    # Mock browser tool
    mock_browser = MagicMock()
    mock_browser.name = "browser"
    mock_browser.execute.return_value = ToolExecutionResult(
        success=True,
        output={"url": "https://github.com", "launched": True},
    )
    registry.register_tool(mock_browser)

    # Verification tool
    mock_verif = MagicMock()
    mock_verif.name = "verification"
    mock_verif.execute.return_value = ToolExecutionResult(success=True, output={})
    registry.register_tool(mock_verif)

    # Create task
    task_rec = task_service.create_task("Open my GitHub")
    engine = ExecutionEngine(task_service=task_service, tool_registry=registry, db=mock_db)

    updated = engine.execute_task(task_rec.id)
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert "https://github.com" in (updated.execution_summary or "")
    assert len(updated.step_executions) >= 1
    assert updated.step_executions[0].status == "completed"


def test_execute_folder_creation_task_with_verification(mock_db):
    with tempfile.TemporaryDirectory() as tmpdir:
        target_folder = os.path.join(tmpdir, "MyProject")

        task_service = TaskService(db=mock_db)
        registry = ToolRegistry()

        # Mock filesystem tool
        mock_fs = MagicMock()
        mock_fs.name = "filesystem"
        mock_fs.execute.return_value = ToolExecutionResult(
            success=True,
            output={"path": target_folder, "created": True},
        )
        registry.register_tool(mock_fs)

        # Mock app launcher
        mock_launcher = MagicMock()
        mock_launcher.name = "app_launcher"
        mock_launcher.execute.return_value = ToolExecutionResult(
            success=True,
            output={"app_name": "vscode", "target_path": target_folder},
        )
        registry.register_tool(mock_launcher)

        # Mock verification
        mock_verif = MagicMock()
        mock_verif.name = "verification"
        mock_verif.execute.return_value = ToolExecutionResult(
            success=True,
            output={"path": target_folder, "exists": True},
        )
        registry.register_tool(mock_verif)

        task_rec = task_service.create_task(f"Create a folder named {target_folder} and open it in VS Code")
        engine = ExecutionEngine(task_service=task_service, tool_registry=registry, db=mock_db)

        updated = engine.execute_task(task_rec.id)
        assert updated.status == "completed"
        assert len(updated.step_executions) >= 2


def test_execute_task_requires_approval_blocks_when_unapproved(mock_db):
    task_service = TaskService(db=mock_db)
    task_rec = task_service.create_task("Open my GitHub")

    # Manually mark a step as requiring approval
    plan_dict = task_rec.plan.model_dump()
    plan_dict["tool_steps"][0]["requires_approval"] = True
    plan = Plan.model_validate(plan_dict)
    task_service.db.save_task(
        task_id=task_rec.id,
        task=task_rec.task,
        plan_json=plan.model_dump_json(),
        status="planned",
        created_at=task_rec.created_at,
        updated_at=task_rec.updated_at,
        task_type="computer_task",
    )

    engine = ExecutionEngine(task_service=task_service, db=mock_db)
    updated = engine.execute_task(task_rec.id, approved=False)

    assert updated.status == "blocked"
    assert "approval" in (updated.error_summary or "").lower()


def test_execute_task_cancellation(mock_db):
    task_service = TaskService(db=mock_db)
    task_rec = task_service.create_task("Open my GitHub")

    engine = ExecutionEngine(task_service=task_service, db=mock_db)
    engine.request_cancellation(task_rec.id)

    assert engine.is_cancelled(task_rec.id)
