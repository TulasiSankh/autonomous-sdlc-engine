"""Tests for diagnostic feedback, DeveloperAgent patch revision, and bounded iteration loop."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from agents.developer import DeveloperAgent, ImplementationProposal, ProposedFileChange, RevisionProposal
from api.main import app
from services.code_application_service import CodeApplicationService
from services.lifecycle_service import DEFAULT_MAX_REVISIONS, RevisionResult, TaskLifecycleCoordinator
from services.task_service import (
    TaskRecord,
    TaskService,
    VerificationAttemptRecord,
    VerificationDiagnostics,
    create_diagnostics_from_attempt,
)
from services.verification_service import (
    BaseVerificationRunner,
    DisabledSecurityRunner,
    VerificationProfile,
    VerificationResult,
    VerificationService,
)
from services.workspace_service import WorkspaceService
from storage.database import Database


class FakeControllableRunner(BaseVerificationRunner):
    """Controllable runner for testing the revision loop deterministically."""

    def __init__(self, outcomes=None, runner_id: str = "fake_controllable_runner"):
        self.outcomes = outcomes or []
        self._runner_id = runner_id
        self.call_count = 0

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
        if self.call_count < len(self.outcomes):
            outcome = self.outcomes[self.call_count]
        else:
            outcome = self.outcomes[-1] if self.outcomes else ("passed", 0, "OK", "", False, None)

        self.call_count += 1
        status, exit_code, stdout, stderr, timed_out, err_msg = outcome

        return VerificationResult(
            workspace_id=workspace_path.name,
            profile="pytest_standard",
            status=status,
            exit_code=exit_code,
            duration_seconds=0.1,
            stdout=stdout,
            stderr=stderr,
            output_truncated=False,
            timed_out=timed_out,
            runner_id=self.runner_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_message=err_msg,
        )


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Provides a fresh isolated Database instance in tmp_path."""
    db_file = tmp_path / "revision_test.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(db_file))
    return Database(db_file)


@pytest.fixture
def client(isolated_db: Database) -> TestClient:
    """FastAPI TestClient backed by isolated test DB."""
    return TestClient(app)


def make_initial_proposal(task_id: str, task: str) -> ImplementationProposal:
    """Helper creating an initial proposal with a module to create."""
    return ImplementationProposal(
        task_id=task_id,
        task=task,
        status="proposed",
        summary=f"Initial proposal for {task}",
        files_to_change=[
            ProposedFileChange(
                path="calculator.py",
                action="create",
                description="Create calculator module",
            )
        ],
        execution_steps=["Create calculator module"],
        verification_commands=["pytest -v"],
        dry_run=True,
    )


def test_failed_test_diagnostics_to_revision_proposal(isolated_db: Database):
    """Verify that actual failed-test diagnostics produce a targeted RevisionProposal."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Implement add function")
    record = task_service.transition_task_status(
        record.id, "proposed", proposal=make_initial_proposal(record.id, record.task)
    )

    diagnostics = VerificationDiagnostics(
        task_id=record.id,
        workspace_id="ws_123",
        profile="pytest_standard",
        status="failed",
        exit_code=1,
        stdout_excerpt="FAILED tests/test_calc.py::test_add - AssertionError: assert 1 + 2 == 4",
        stderr_excerpt="AssertionError: assert 1 + 2 == 4",
        output_truncated=False,
        timed_out=False,
        runner_error="Tests exited with code 1",
        attempt_id="verif_001",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    agent = DeveloperAgent(task_service=task_service)
    proposal = agent.revise_from_diagnostics(record, diagnostics)

    assert isinstance(proposal, RevisionProposal)
    assert proposal.can_revise is True
    assert proposal.task_id == record.id
    assert len(proposal.proposed_changes) > 0
    assert proposal.proposed_changes[0].path == "calculator.py"
    assert "calculator.py" in proposal.suggested_file_contents
    assert "assertionerror" in proposal.suspected_cause.lower()
    assert "NOT been verified" in proposal.explanation
    assert "pytest_standard" in proposal.test_strategy


def test_insufficient_or_empty_diagnostics_returns_no_action(isolated_db: Database):
    """Verify that empty/insufficient diagnostics return a typed no-action result."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Fix silent bug")

    empty_diagnostics = VerificationDiagnostics(
        task_id=record.id,
        workspace_id="ws_123",
        profile="pytest_standard",
        status="failed",
        exit_code=None,
        stdout_excerpt="",
        stderr_excerpt="",
        output_truncated=False,
        timed_out=False,
        runner_error=None,
        attempt_id="verif_empty",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    agent = DeveloperAgent(task_service=task_service)
    proposal = agent.revise_from_diagnostics(record, empty_diagnostics)

    assert proposal.can_revise is False
    assert len(proposal.proposed_changes) == 0
    assert "insufficient diagnostic" in proposal.explanation.lower()


def test_blocked_verification_not_treated_as_code_failure(isolated_db: Database):
    """Verify that a blocked verification is never interpreted as code failure."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Security sandbox check")

    blocked_diagnostics = VerificationDiagnostics(
        task_id=record.id,
        workspace_id="ws_123",
        profile="pytest_standard",
        status="blocked",
        exit_code=None,
        stdout_excerpt="",
        stderr_excerpt="",
        output_truncated=False,
        timed_out=False,
        runner_error="Host execution disabled by security policy",
        attempt_id="verif_blocked",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    agent = DeveloperAgent(task_service=task_service)
    proposal = agent.revise_from_diagnostics(record, blocked_diagnostics)

    assert proposal.can_revise is False
    assert len(proposal.proposed_changes) == 0
    assert "blocked" in proposal.explanation.lower()
    assert "security policy" in proposal.suspected_cause.lower()


def test_passed_verification_diagnostics_returns_no_action(isolated_db: Database):
    """Verify that passed tests require no corrective revision."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Passing task")

    passed_diagnostics = VerificationDiagnostics(
        task_id=record.id,
        workspace_id="ws_123",
        profile="pytest_standard",
        status="passed",
        exit_code=0,
        stdout_excerpt="5 passed",
        stderr_excerpt="",
        output_truncated=False,
        timed_out=False,
        runner_error=None,
        attempt_id="verif_passed",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    agent = DeveloperAgent(task_service=task_service)
    proposal = agent.revise_from_diagnostics(record, passed_diagnostics)

    assert proposal.can_revise is False
    assert len(proposal.proposed_changes) == 0
    assert "already passed" in proposal.explanation.lower()


def test_safe_and_unsafe_paths_in_revision(isolated_db: Database):
    """Verify that path traversal and absolute paths are strictly rejected in revisions."""
    task_service = TaskService(db=isolated_db)
    record = task_service.create_task("Path security test")

    diagnostics = VerificationDiagnostics(
        task_id=record.id,
        workspace_id="ws_123",
        profile="pytest_standard",
        status="failed",
        exit_code=1,
        stdout_excerpt="Failure",
        stderr_excerpt="Failure in module",
        output_truncated=False,
        timed_out=False,
        runner_error="Exit 1",
        attempt_id="verif_002",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    agent = DeveloperAgent(task_service=task_service)

    # 1. Unsafe parent traversal path
    with pytest.raises(ValueError) as err1:
        agent.revise_from_diagnostics(
            record, diagnostics, suggested_patches={"../escape.py": "# hack"}
        )
    assert "parent directory traversal" in str(err1.value).lower()

    # 2. Unsafe absolute path
    with pytest.raises(ValueError) as err2:
        agent.revise_from_diagnostics(
            record, diagnostics, suggested_patches={"/etc/shadow": "# hack"}
        )
    assert "absolute paths are not permitted" in str(err2.value).lower()

    # 3. Safe relative path
    safe_prop = agent.revise_from_diagnostics(
        record, diagnostics, suggested_patches={"utils/math_helper.py": "def add(a, b): return a + b\n"}
    )
    assert safe_prop.can_revise is True
    assert safe_prop.proposed_changes[0].path == "utils/math_helper.py"


def test_coordinator_revise_applies_and_records_diffs(isolated_db: Database, tmp_path: Path):
    """Verify coordinator.revise applies the patch, updates revision count, and records diffs."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    # Runner initially reports failure
    fake_runner = FakeControllableRunner(
        outcomes=[("failed", 1, "assert 1 == 2", "AssertionError", False, "Tests failed")]
    )
    verif_service = VerificationService(workspace_service=ws_service, runner=fake_runner)

    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    # 1. Create, propose, apply, and verify initially
    record = task_service.create_task("Calculator module")
    initial_prop = make_initial_proposal(record.id, record.task)
    coordinator.propose(record.id, custom_proposal=initial_prop)
    record, _ = coordinator.apply(record.id, file_contents={"calculator.py": "def add(a, b): return a - b\n"})

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_calc.py").write_text("def test_calc(): pass\n", encoding="utf-8")

    record, first_verif = coordinator.verify(record.id)
    assert record.status == "verification_failed"
    assert record.revision_count == 0

    # 2. Revise without auto_verify (default)
    corrected_patch = {"calculator.py": "def add(a, b): return a + b\n"}
    updated_record, rev_result, second_verif = coordinator.revise(
        record.id, auto_verify=False, suggested_patches=corrected_patch
    )

    assert rev_result.status == "revised"
    assert rev_result.revision_count == 1
    assert updated_record.revision_count == 1
    assert updated_record.status == "changes_applied"
    assert second_verif is None  # Verification was not automatically run

    # Verify diff was generated
    assert rev_result.application_result is not None
    assert rev_result.application_result.status == "applied"
    assert len(rev_result.application_result.diffs) > 0
    assert "+def add(a, b): return a + b" in rev_result.application_result.unified_diff

    # Content on disk reflects the patch
    assert (ws_path / "calculator.py").read_text(encoding="utf-8") == "def add(a, b): return a + b\n"


def test_revision_budget_enforced_across_coordinator_restarts(isolated_db: Database, tmp_path: Path):
    """Verify that revision budget is enforced and persists across coordinator instances."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    fake_runner = FakeControllableRunner(
        outcomes=[("failed", 1, "", "Failed", False, "Error")]
    )
    verif_service = VerificationService(workspace_service=ws_service, runner=fake_runner)

    coordinator1 = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Budget test task")
    coordinator1.propose(record.id, custom_proposal=make_initial_proposal(record.id, record.task))
    record, _ = coordinator1.apply(record.id, file_contents={"calculator.py": "def add(a, b): return 0\n"})

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_calc.py").write_text("def test_calc(): pass\n", encoding="utf-8")
    record, _ = coordinator1.verify(record.id)

    # Max revisions set to 2
    max_budget = 2

    # Revision 1
    record, rev1, _ = coordinator1.revise(record.id, max_revisions=max_budget)
    assert rev1.status == "revised"
    assert record.revision_count == 1

    # Simulate re-verifying and failing again
    record, _ = coordinator1.verify(record.id)

    # Revision 2
    record, rev2, _ = coordinator1.revise(record.id, max_revisions=max_budget)
    assert rev2.status == "revised"
    assert record.revision_count == 2

    # Simulate coordinator restart / new service instance
    recreated_task_service = TaskService(db=isolated_db)
    coordinator2 = TaskLifecycleCoordinator(
        task_service=recreated_task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    # Attempt revision 3 (exceeds budget of 2)
    record, rev3, _ = coordinator2.revise(record.id, max_revisions=max_budget)
    assert rev3.status == "budget_exhausted"
    assert rev3.revision_count == 2
    assert "budget exhausted" in rev3.message.lower()
    assert record.revision_count == 2


def test_complete_revision_loop_to_verified(isolated_db: Database, tmp_path: Path):
    """Verify that run_revision_loop alternates revision and verification until verified."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    # Outcome 1: fail, Outcome 2: pass
    fake_runner = FakeControllableRunner(
        outcomes=[
            ("failed", 1, "test failed", "AssertionError", False, "Test failed"),
            ("passed", 0, "1 passed", "", False, None),
        ]
    )
    verif_service = VerificationService(workspace_service=ws_service, runner=fake_runner)

    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("End-to-end loop task")
    coordinator.propose(record.id, custom_proposal=make_initial_proposal(record.id, record.task))
    record, _ = coordinator.apply(record.id, file_contents={"calculator.py": "# faulty\n"})

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_calc.py").write_text("def test_calc(): pass\n", encoding="utf-8")

    # Initial verification fails
    record, _ = coordinator.verify(record.id)
    assert record.status == "verification_failed"

    # Run revision loop
    final_task, final_rev, verif_results = coordinator.run_revision_loop(
        record.id,
        max_revisions=3,
        suggested_patches={"calculator.py": "def fixed(): return True\n"},
    )

    assert final_rev.status == "revised"
    assert final_task.status == "verified"
    assert final_task.verification_status == "passed"
    assert len(verif_results) == 1
    assert verif_results[0].status == "passed"
    assert final_task.revision_count == 1

    # Verify history in database contains both attempts
    history = coordinator.get_verification_history(record.id)
    assert len(history) == 2
    assert history[0].status == "failed"
    assert history[1].status == "passed"


def test_no_patch_marked_verified_before_successful_run(isolated_db: Database, tmp_path: Path):
    """Verify that applying a patch leaves task in changes_applied, never verified."""
    ws_root = tmp_path / "workspaces"
    ws_service = WorkspaceService(workspace_root=ws_root)
    task_service = TaskService(db=isolated_db)

    app_service = CodeApplicationService(
        task_service=task_service,
        workspace_service=ws_service,
        source_repo_path=tmp_path,
    )
    fake_runner = FakeControllableRunner(outcomes=[("failed", 1, "", "Err", False, "Failed")])
    verif_service = VerificationService(workspace_service=ws_service, runner=fake_runner)

    coordinator = TaskLifecycleCoordinator(
        task_service=task_service,
        code_application_service=app_service,
        verification_service=verif_service,
    )

    record = task_service.create_task("Verification truth test")
    coordinator.propose(record.id, custom_proposal=make_initial_proposal(record.id, record.task))
    record, _ = coordinator.apply(record.id, file_contents={"calculator.py": "# code\n"})

    ws_path = ws_service.get_workspace_path(record.workspace_id)
    tests_dir = ws_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_calc.py").write_text("def test_c(): pass\n", encoding="utf-8")
    record, _ = coordinator.verify(record.id)

    # Revise without auto_verify
    record, rev_res, verif_res = coordinator.revise(
        record.id,
        auto_verify=False,
        suggested_patches={"calculator.py": "# fixed candidate\n"},
    )

    assert rev_res.status == "revised"
    assert record.status == "changes_applied"
    assert record.status != "verified"
    assert verif_res is None


def test_api_regression_with_revision_count(client: TestClient):
    """Verify that existing HTTP endpoints return the complete schema with revision_count."""
    # Create task
    res = client.post("/tasks", json={"task": "API revision compatibility task"})
    assert res.status_code == 201
    data = res.json()
    assert "revision_count" in data
    assert data["revision_count"] == 0

    task_id = data["id"]

    # Get task
    get_res = client.get(f"/tasks/{task_id}")
    assert get_res.status_code == 200
    assert get_res.json()["revision_count"] == 0

    # Proposal endpoint
    prop_res = client.post(f"/tasks/{task_id}/proposal")
    assert prop_res.status_code == 200

    # List tasks
    list_res = client.get("/tasks")
    assert list_res.status_code == 200
    assert any(t["id"] == task_id and "revision_count" in t for t in list_res.json())
