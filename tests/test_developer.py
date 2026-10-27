"""Unit tests for DeveloperAgent, ImplementationProposal, and path validation."""

from pathlib import Path
import pytest

from agents.developer import (
    DeveloperAgent,
    ImplementationProposal,
    ProposedFileChange,
    validate_relative_path,
)
from agents.planner import Plan
from services.task_service import TaskRecord, TaskService
from storage.database import Database


@pytest.fixture
def isolated_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Fixture ensuring all tests use a temporary isolated SQLite database."""
    test_db_path = tmp_path / "test_developer.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(test_db_path))
    return Database(test_db_path)


@pytest.fixture
def task_service(isolated_test_db: Database) -> TaskService:
    """TaskService instance wired to the isolated test database."""
    return TaskService(db=isolated_test_db)


def test_developer_valid_task_proposal(task_service: TaskService, tmp_path: Path):
    """Verify that DeveloperAgent generates a structured ImplementationProposal for a valid task."""
    task_desc = "Add user authentication endpoint to API"
    task = task_service.create_task(task_desc)

    agent = DeveloperAgent(task_service=task_service, workspace_path=tmp_path)
    proposal = agent.propose(task.id)

    assert isinstance(proposal, ImplementationProposal)
    assert proposal.task_id == task.id
    assert proposal.task == task_desc
    assert proposal.status == "proposed"
    assert proposal.dry_run is True
    assert "authentication" in proposal.summary.lower()

    # Verify proposed files
    assert len(proposal.files_to_change) > 0
    for file_change in proposal.files_to_change:
        assert isinstance(file_change, ProposedFileChange)
        assert file_change.action in ("create", "modify")
        assert len(file_change.path) > 0
        assert len(file_change.description) > 0

    # Verify steps and verification commands
    assert len(proposal.execution_steps) > 0
    assert any("[Proposed]" in step for step in proposal.execution_steps)
    assert len(proposal.verification_commands) > 0


def test_developer_missing_task_id(task_service: TaskService):
    """Verify that attempting to propose for a non-existent task ID raises ValueError."""
    agent = DeveloperAgent(task_service=task_service)
    with pytest.raises(ValueError, match="not found"):
        agent.propose("task-non-existent-999")


@pytest.mark.parametrize("invalid_id", ["", "   ", "\t\n  "])
def test_developer_empty_and_whitespace_task_id(invalid_id: str, task_service: TaskService):
    """Verify that empty or whitespace-only task IDs raise ValueError."""
    agent = DeveloperAgent(task_service=task_service)
    with pytest.raises(ValueError, match="cannot be empty or whitespace only"):
        agent.propose(invalid_id)


@pytest.mark.parametrize("invalid_type", [None, 12345, [], {}])
def test_developer_non_string_task_id(invalid_type, task_service: TaskService):
    """Verify that non-string task IDs raise ValueError."""
    agent = DeveloperAgent(task_service=task_service)
    with pytest.raises(ValueError, match="must be a string"):
        agent.propose(invalid_type)


def test_developer_invalid_or_corrupted_plan_data(task_service: TaskService):
    """Verify that corrupted or missing plan data raises ValueError."""
    agent = DeveloperAgent(task_service=task_service)

    # 1. Missing plan object
    corrupted_record_none = TaskRecord.model_construct(
        id="task-mock-1",
        task="Mock task",
        status="planned",
        plan=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(ValueError, match="corrupted or missing plan data"):
        agent.generate_proposal(corrupted_record_none)

    # 2. Plan with empty execution steps
    corrupted_plan = Plan(
        task="Task with empty steps",
        summary="Summary",
        steps=[],
        files_to_inspect=[],
        acceptance_criteria=[],
        tests_to_run=[],
        risks=[],
    )
    corrupted_record_empty_steps = TaskRecord(
        id="task-mock-2",
        task="Task with empty steps",
        status="planned",
        plan=corrupted_plan,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(ValueError, match="contains no execution steps"):
        agent.generate_proposal(corrupted_record_empty_steps)


def test_validate_relative_path_safe_and_traversal():
    """Verify that validate_relative_path accepts safe paths and rejects traversals or absolute paths."""
    # Valid relative paths
    assert validate_relative_path("api/main.py") == "api/main.py"
    assert validate_relative_path("services/task_service.py") == "services/task_service.py"
    assert validate_relative_path("subdir/nested/module.py") == "subdir/nested/module.py"

    # Traversal attempts
    with pytest.raises(ValueError, match="Parent directory traversal"):
        validate_relative_path("../outside.py")

    with pytest.raises(ValueError, match="Parent directory traversal"):
        validate_relative_path("dir/../../escape.py")

    # Absolute paths (POSIX and Windows)
    with pytest.raises(ValueError, match="Absolute paths are not permitted"):
        validate_relative_path("/etc/passwd")

    with pytest.raises(ValueError, match="Absolute paths are not permitted"):
        validate_relative_path("C:/Windows/System32")

    with pytest.raises(ValueError, match="Absolute paths are not permitted"):
        validate_relative_path("\\server\\share\\file.txt")

    # Empty and invalid types
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_relative_path("   ")

    with pytest.raises(ValueError, match="must be a string"):
        validate_relative_path(None)  # type: ignore[arg-type]


def test_developer_dry_run_leaves_workspace_unchanged(task_service: TaskService, tmp_path: Path):
    """Verify that propose() operates in dry-run mode and creates/modifies zero files in workspace."""
    workspace = tmp_path / "sandbox_workspace"
    workspace.mkdir()
    existing_file = workspace / "existing_file.py"
    existing_file.write_text("# Existing content\n", encoding="utf-8")

    # Snapshot workspace state before proposal
    before_files = {p.relative_to(workspace): p.stat().st_mtime for p in workspace.rglob("*")}

    task = task_service.create_task("Refactor authentication routes")
    agent = DeveloperAgent(task_service=task_service, workspace_path=workspace)
    proposal = agent.propose(task.id)

    assert proposal.dry_run is True

    # Snapshot workspace state after proposal
    after_files = {p.relative_to(workspace): p.stat().st_mtime for p in workspace.rglob("*")}

    assert before_files == after_files
    assert existing_file.read_text(encoding="utf-8") == "# Existing content\n"


def test_developer_dependency_injection_of_task_service(isolated_test_db: Database):
    """Verify that DeveloperAgent honors an explicitly injected TaskService instance."""
    custom_service = TaskService(db=isolated_test_db)
    agent = DeveloperAgent(task_service=custom_service)

    assert agent.task_service is custom_service
    task = custom_service.create_task("Custom injected task")

    proposal = agent.propose(task.id)
    assert proposal.task_id == task.id
    assert proposal.task == "Custom injected task"


def test_developer_diff_generation_missing_and_existing_files(
    task_service: TaskService, tmp_path: Path
):
    """Verify that DeveloperAgent generates candidate unified diffs for both existing and missing files."""
    workspace = tmp_path / "mock_repo"
    workspace.mkdir()
    existing_file = workspace / "existing_module.py"
    existing_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    # Create task with a plan that references both an existing file and a missing file
    task = task_service.create_task("Update existing module and create new helper")
    task_record = task_service.get_task(task.id)
    assert task_record is not None
    assert task_record.plan is not None

    agent = DeveloperAgent(task_service=task_service, workspace_path=workspace)
    proposal = agent.propose(task.id)

    assert proposal.dry_run is True
    assert len(proposal.diffs) > 0

    # Ensure diffs exist for all proposed files
    diff_paths = {d.path for d in proposal.diffs}
    for file_change in proposal.files_to_change:
        assert file_change.path in diff_paths

    for diff in proposal.diffs:
        assert len(diff.path) > 0
        assert diff.change_type in ("added", "modified")
        assert "+++" in diff.diff
        if diff.change_type == "added":
            assert "--- /dev/null" in diff.diff

