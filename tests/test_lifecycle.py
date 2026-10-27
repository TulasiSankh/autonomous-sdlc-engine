"""Comprehensive tests for task lifecycle management, state transitions, and verification integration."""

import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient

from agents.developer import ImplementationProposal, ProposedFileChange
from api.main import app
from services.code_application_service import CodeApplicationResult, CodeApplicationService
from services.lifecycle_service import TaskLifecycleCoordinator
from services.task_service import (
    MAX_STORED_OUTPUT_BYTES,
    InvalidStateTransitionError,
    TaskRecord,
    TaskService,
    VerificationAttemptRecord,
)
from services.verification_service import (
    BaseVerificationRunner,
    DisabledSecurityRunner,
    VerificationProfile,
    VerificationRequest,
    VerificationResult,
    VerificationService,
)
from services.workspace_service import WorkspaceService
from storage.database import Database


def make_custom_proposal(task_id: str, task: str) -> ImplementationProposal:
    """Helper creating a valid proposal with a file to create."""
    return ImplementationProposal(
        task_id=task_id,
        task=task,
        status="proposed",
        summary=f"Implementation proposal for {task}",
        files_to_change=[
            ProposedFileChange(
                path="module.py", action="create", description="Create module"
            ),
        ],
        execution_steps=["Step 1"],
        verification_commands=["pytest -v"],
        dry_run=True,
    )


class FakeTestRunner(BaseVerificationRunner):
    """Controllable verification runner for deterministic unit testing without host execution."""

    def __init__(
        self,
        status: str = "passed",
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        timed_out: bool = False,
        error_message: str = None,
        runner_id_name: str = "fake_test_runner",
    ) -> None:
        self._status = status
        self._exit_code = exit_code
        self._stdout = stdout
        self._stderr = stderr
        self._timed_out = timed_out
        self._error_message = error_message
        self._runner_id = runner_id_name

    @property
    def runner_id(self) -> str:
        return self._runner_id

    def run(
        self,
        workspace_path: Path,
        command_args: list,
        timeout_seconds: float = 60.0,
        max_output_bytes: int = 65536,
    ) -> VerificationResult:
        return VerificationResult(
            workspace_id=workspace_path.name,
            profile="pytest_standard",
            status=self._status,  # type: ignore[arg-type]
            exit_code=self._exit_code,
            duration_seconds=0.15,
            stdout=self._stdout,
            stderr=self._stderr,
            output_truncated=False,
            timed_out=self._timed_out,
            runner_id=self.runner_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_message=self._error_message,
        )


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Provides a fresh isolated Database instance in tmp_path."""
    db_file = tmp_path / "lifecycle_test.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(db_file))
    return Database(db_file)


@pytest.fixture
def client(isolated_db: Database) -> TestClient:
    """FastAPI TestClient backed by isolated test DB."""
    return TestClient(app)


def test_valid_lifecycle_state_transitions(isolated_db: Database):
    """Verify standard happy-path lifecycle transitions from planned to verified."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Implement caching layer")
    assert record.status == "planned"

    # planned -> proposed
    record = task_service.transition_task_status(record.id, "proposed")
    assert record.status == "proposed"

    # proposed -> changes_applied
    record = task_service.transition_task_status(
        record.id, "changes_applied", workspace_id="ws_123", application_status="applied"
    )
    assert record.status == "changes_applied"
    assert record.workspace_id == "ws_123"
    assert record.application_status == "applied"

    # changes_applied -> verifying
    record = task_service.transition_task_status(record.id, "verifying")
    assert record.status == "verifying"

    # verifying -> verified
    record = task_service.transition_task_status(
        record.id, "verified", verification_status="passed"
    )
    assert record.status == "verified"
    assert record.verification_status == "passed"

    # verified -> proposed (revision flow)
    record = task_service.transition_task_status(record.id, "proposed")
    assert record.status == "proposed"


def test_invalid_lifecycle_state_transitions(isolated_db: Database):
    """Verify that illegal transitions raise InvalidStateTransitionError."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Setup metrics collection")

    # Cannot skip directly from planned to verified
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        task_service.transition_task_status(record.id, "verified")
    assert "Cannot transition task" in str(exc_info.value)
    assert "from 'planned' to 'verified'" in str(exc_info.value)

    # Cannot skip directly from planned to verifying
    with pytest.raises(InvalidStateTransitionError):
        task_service.transition_task_status(record.id, "verifying")

    # Move to proposed
    task_service.transition_task_status(record.id, "proposed")

    # Cannot jump from proposed to verified directly without applying changes
    with pytest.raises(InvalidStateTransitionError):
        task_service.transition_task_status(record.id, "verified")

    # Unknown status raises ValueError
    with pytest.raises(ValueError) as val_err:
        task_service.transition_task_status(record.id, "nonexistent_status")
    assert "Unknown task lifecycle status" in str(val_err.value)


def test_coordinator_propose_flow(isolated_db: Database):
    """Verify that coordinator propose attaches proposal and transitions to 'proposed'."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Build logging service")

    coordinator = TaskLifecycleCoordinator(task_service=task_service)
    updated_record, proposal = coordinator.propose(record.id)

    assert updated_record.status == "proposed"
    assert updated_record.proposal is not None
    assert updated_record.proposal.task_id == record.id
    assert proposal.task_id == record.id


def test_coordinator_apply_and_default_blocked_verification(isolated_db: Database, tmp_path: Path):
    """Verify that default verification blocks and transitions task to verification_blocked."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    verif_service = VerificationService(
        workspace_service=ws_service,
        runner=DisabledSecurityRunner(),
    )
    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Implement token bucket")
    prop = make_custom_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=prop)

    # Apply changes
    sample_content = {"module.py": "class TokenBucket:\n    pass\n"}
    record, app_result = coordinator.apply(record.id, file_contents=sample_content)
    assert record.status == "changes_applied"
    assert app_result.status == "applied"
    assert record.workspace_id is not None

    # Setup tests directory inside workspace so validation passes
    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_sample.py").write_text("def test_dummy(): pass\n", encoding="utf-8")

    # Verify with default DisabledSecurityRunner
    record, verif_result = coordinator.verify(record.id)

    assert verif_result.status == "blocked"
    assert record.status == "verification_blocked"
    assert record.verification_status == "blocked"
    assert "blocked" in record.error_summary.lower()
    assert record.status != "verified"


def test_coordinator_passed_verification_with_fake_runner(isolated_db: Database, tmp_path: Path):
    """Verify that a successful test run with exit code 0 marks task as 'verified'."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    fake_runner = FakeTestRunner(status="passed", exit_code=0, stdout="1 passed")
    verif_service = VerificationService(
        workspace_service=ws_service,
        runner=fake_runner,
    )
    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Fix edge case in parser")
    prop = make_custom_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=prop)
    record, app_result = coordinator.apply(record.id, file_contents={"module.py": "# fixed\n"})
    assert app_result.status == "applied"

    # Setup valid tests dir
    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_parser.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    record, result = coordinator.verify(record.id)

    assert result.status == "passed"
    assert result.exit_code == 0
    assert record.status == "verified"
    assert record.verification_status == "passed"
    assert record.error_summary is None


def test_coordinator_failed_verification_with_fake_runner(isolated_db: Database, tmp_path: Path):
    """Verify that a failing test run with non-zero exit code marks task as 'verification_failed'."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    fake_runner = FakeTestRunner(
        status="failed", exit_code=1, stderr="AssertionError: 1 != 2", error_message="Tests failed"
    )
    verif_service = VerificationService(
        workspace_service=ws_service,
        runner=fake_runner,
    )
    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Test failure scenario")
    prop = make_custom_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=prop)
    record, app_result = coordinator.apply(record.id, file_contents={"module.py": "# app\n"})
    assert app_result.status == "applied"

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_fail.py").write_text("def test_f(): assert False\n", encoding="utf-8")

    record, result = coordinator.verify(record.id)

    assert result.status == "failed"
    assert result.exit_code == 1
    assert record.status == "verification_failed"
    assert record.verification_status == "failed"
    assert "tests failed" in record.error_summary.lower()


def test_coordinator_timeout_handling(isolated_db: Database, tmp_path: Path):
    """Verify that execution timeout transitions task to 'verification_timed_out'."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    fake_runner = FakeTestRunner(
        status="timed_out", exit_code=None, timed_out=True, error_message="Execution timed out after 30s"
    )
    verif_service = VerificationService(
        workspace_service=ws_service,
        runner=fake_runner,
    )
    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Handle infinite loop")
    prop = make_custom_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=prop)
    record, app_result = coordinator.apply(record.id, file_contents={"module.py": "while True: pass\n"})
    assert app_result.status == "applied"

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_loop.py").write_text("def test_infinite(): pass\n", encoding="utf-8")

    record, result = coordinator.verify(record.id)

    assert result.status == "timed_out"
    assert record.status == "verification_timed_out"
    assert record.verification_status == "timed_out"
    assert "timed out" in record.error_summary.lower()


def test_coordinator_runner_error_handling(isolated_db: Database, tmp_path: Path):
    """Verify that runner execution error transitions task to 'verification_error'."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    fake_runner = FakeTestRunner(
        status="error", exit_code=None, error_message="Failed to launch verification runner: Binary not found"
    )
    verif_service = VerificationService(
        workspace_service=ws_service,
        runner=fake_runner,
    )
    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Test runner crash")
    prop = make_custom_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=prop)
    record, app_result = coordinator.apply(record.id, file_contents={"module.py": "# crash\n"})
    assert app_result.status == "applied"

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_crash.py").write_text("def test_c(): pass\n", encoding="utf-8")

    record, result = coordinator.verify(record.id)

    assert result.status == "error"
    assert record.status == "verification_error"
    assert record.verification_status == "error"
    assert "binary not found" in record.error_summary.lower()


def test_truthful_reporting_guarantee_never_mark_verified_on_failure():
    """Ensure that under no circumstances can an abnormal run mark task as verified."""
    # Test matrix of non-passing states
    for bad_status in ("failed", "blocked", "timed_out", "error"):
        if bad_status == "failed":
            target = "verification_failed"
        elif bad_status == "blocked":
            target = "verification_blocked"
        elif bad_status == "timed_out":
            target = "verification_timed_out"
        else:
            target = "verification_error"

        assert target != "verified"


def test_verify_without_workspace_fails_closed(isolated_db: Database):
    """Verify that calling verify on a task without an isolated workspace raises ValueError."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Task with no workspace")

    coordinator = TaskLifecycleCoordinator(task_service=task_service)
    with pytest.raises(ValueError) as exc_info:
        coordinator.verify(record.id)
    assert "no associated workspace" in str(exc_info.value)


def test_historical_verification_attempt_retention(isolated_db: Database, tmp_path: Path):
    """Verify that multiple verification runs are preserved in chronological history."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    # Runner that we will dynamically update
    fake_runner = FakeTestRunner(status="blocked", exit_code=None, error_message="Blocked attempt 1")
    verif_service = VerificationService(
        workspace_service=ws_service,
        runner=fake_runner,
    )
    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Multi-run verification history")
    prop = make_custom_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=prop)
    record, app_result = coordinator.apply(record.id, file_contents={"module.py": "# v1\n"})
    assert app_result.status == "applied"

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_module.py").write_text("def test_m(): pass\n", encoding="utf-8")

    # Run 1: Blocked
    coordinator.verify(record.id)

    # Run 2: Failed
    fake_runner._status = "failed"
    fake_runner._exit_code = 1
    fake_runner._error_message = "Test failed in run 2"
    coordinator.verify(record.id)

    # Run 3: Passed
    fake_runner._status = "passed"
    fake_runner._exit_code = 0
    fake_runner._error_message = None
    final_record, _ = coordinator.verify(record.id)

    # Verify history
    history = coordinator.get_verification_history(record.id)
    assert len(history) == 3
    assert history[0].status == "blocked"
    assert history[1].status == "failed"
    assert history[1].exit_code == 1
    assert history[2].status == "passed"
    assert history[2].exit_code == 0

    # Verify latest verification on task record
    assert final_record.latest_verification is not None
    assert final_record.latest_verification.status == "passed"
    assert final_record.status == "verified"


def test_verification_output_bounding_in_database(isolated_db: Database, tmp_path: Path):
    """Verify that huge stdout/stderr is bounded before writing to database."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Output bounds check")

    huge_stdout = "X" * 100000
    huge_stderr = "Y" * 100000

    fake_verif_result = VerificationResult(
        workspace_id="ws_huge",
        profile="pytest_standard",
        status="passed",
        exit_code=0,
        duration_seconds=1.2,
        stdout=huge_stdout,
        stderr=huge_stderr,
        output_truncated=False,
        timed_out=False,
        runner_id="fake_runner",
        timestamp=datetime.now(timezone.utc).isoformat(),
        error_message=None,
    )

    attempt_record = task_service.record_verification_attempt(record.id, fake_verif_result)
    assert attempt_record.output_truncated is True
    assert len(attempt_record.stdout.encode("utf-8")) <= MAX_STORED_OUTPUT_BYTES + 100
    assert "... [DATABASE TRUNCATED STDOUT] ..." in attempt_record.stdout
    assert len(attempt_record.stderr.encode("utf-8")) <= MAX_STORED_OUTPUT_BYTES + 100
    assert "... [DATABASE TRUNCATED STDERR] ..." in attempt_record.stderr

    # Check retrieval from DB
    history = task_service.get_verification_history(record.id)
    assert len(history) == 1
    assert history[0].output_truncated is True


def test_backward_compatible_database_migration(tmp_path: Path):
    """Verify that an older database without lifecycle columns is automatically migrated."""
    legacy_db_path = tmp_path / "legacy_v1.db"

    # 1. Create legacy schema with only original 6 columns
    conn = sqlite3.connect(str(legacy_db_path))
    conn.execute(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            task TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    dummy_plan = {
        "task": "Legacy task",
        "summary": "Summary",
        "steps": ["Step 1"],
        "files_to_inspect": [],
        "acceptance_criteria": [],
        "tests_to_run": [],
        "risks": [],
    }
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO tasks (id, task, plan_json, status, created_at, updated_at)
        VALUES ('task-legacy-001', 'Legacy task', ?, 'planned', ?, ?);
        """,
        (json.dumps(dummy_plan), now, now),
    )
    conn.commit()
    conn.close()

    # 2. Instantiate new Database class on top of legacy DB
    migrated_db = Database(legacy_db_path)

    # 3. Verify columns now include lifecycle columns
    with migrated_db.get_connection() as c:
        cursor = c.execute("PRAGMA table_info(tasks);")
        columns = {row["name"] for row in cursor.fetchall()}
        assert "workspace_id" in columns
        assert "proposal_json" in columns
        assert "application_status" in columns
        assert "verification_status" in columns
        assert "error_summary" in columns

        # Verify verification_records table was created
        cursor = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='verification_records';"
        )
        assert cursor.fetchone() is not None

    # 4. Verify TaskService can load legacy task cleanly
    task_service = TaskService(db=migrated_db)
    legacy_record = task_service.get_task("task-legacy-001")
    assert legacy_record is not None
    assert legacy_record.id == "task-legacy-001"
    assert legacy_record.task == "Legacy task"
    assert legacy_record.status == "planned"
    assert legacy_record.workspace_id is None
    assert legacy_record.proposal is None
    assert legacy_record.application_status is None
    assert legacy_record.verification_status is None
    assert legacy_record.error_summary is None

    # 5. Verify lifecycle transitions work on legacy record
    updated = task_service.transition_task_status("task-legacy-001", "proposed")
    assert updated.status == "proposed"


def test_existing_endpoints_regression(client: TestClient):
    """Verify existing HTTP endpoints continue to function with complete backward compatibility."""
    # 1. Create task
    create_res = client.post("/tasks", json={"task": "Regression check task"})
    assert create_res.status_code == 201
    task_data = create_res.json()
    assert task_data["status"] == "planned"
    task_id = task_data["id"]

    # 2. Get task
    get_res = client.get(f"/tasks/{task_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == task_id

    # 3. Create proposal
    prop_res = client.post(f"/tasks/{task_id}/proposal")
    assert prop_res.status_code == 200
    assert prop_res.json()["task_id"] == task_id

    # 4. List tasks
    list_res = client.get("/tasks")
    assert list_res.status_code == 200
    assert any(t["id"] == task_id for t in list_res.json())
