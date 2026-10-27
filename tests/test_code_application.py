"""Comprehensive unit and security tests for CodeApplicationService."""

from pathlib import Path
import pytest

from agents.developer import (
    DeveloperAgent,
    ImplementationProposal,
    ProposedFileChange,
)
from services.code_application_service import (
    CodeApplicationResult,
    CodeApplicationService,
    FileDiff,
    generate_unified_diff,
)
from services.task_service import TaskService
from services.workspace_service import WorkspaceService
from storage.database import Database


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Fixture providing isolated SQLite database."""
    test_db_path = tmp_path / "test_app_service.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(test_db_path))
    return Database(test_db_path)


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    """Fixture providing a mock source repository."""
    repo = tmp_path / "repo_root"
    repo.mkdir()

    (repo / "api").mkdir()
    (repo / "api" / "main.py").write_text("# Initial API Code\n", encoding="utf-8")
    (repo / "README.md").write_text("# Initial Readme\n", encoding="utf-8")
    return repo


@pytest.fixture
def app_service(
    tmp_path: Path, isolated_db: Database, mock_repo: Path
) -> CodeApplicationService:
    """Fixture providing CodeApplicationService configured with isolated components."""
    task_service = TaskService(db=isolated_db)
    dev_agent = DeveloperAgent(task_service=task_service, workspace_path=mock_repo)
    ws_root = tmp_path / "workspaces_root"
    ws_service = WorkspaceService(workspace_root=ws_root, default_source_repo=mock_repo)

    return CodeApplicationService(
        task_service=task_service,
        developer_agent=dev_agent,
        workspace_service=ws_service,
        source_repo_path=mock_repo,
    )


def test_unified_diff_generator():
    """Verify generate_unified_diff helper outputs standard diff formats."""
    # Modified file
    diff_mod = generate_unified_diff(
        original_text="line 1\nline 2\n",
        modified_text="line 1\nline 2 modified\n",
        relative_path="api/main.py",
        change_type="modified",
    )
    assert "--- a/api/main.py" in diff_mod
    assert "+++ b/api/main.py" in diff_mod
    assert "+line 2 modified" in diff_mod

    # Added file
    diff_add = generate_unified_diff(
        original_text="",
        modified_text="new content\n",
        relative_path="new_file.py",
        change_type="added",
    )
    assert "--- /dev/null" in diff_add
    assert "+++ b/new_file.py" in diff_add
    assert "+new content" in diff_add


def test_successful_workspace_application(
    app_service: CodeApplicationService, mock_repo: Path
):
    """Verify successful application of proposal changes into an isolated workspace."""
    task = app_service.task_service.create_task("Add authentication middleware")
    result = app_service.apply_proposal(task.id)

    assert isinstance(result, CodeApplicationResult)
    assert result.status == "applied"
    assert result.task_id == task.id
    assert result.workspace_id.startswith("ws_")
    assert len(result.changed_files) > 0
    assert len(result.diffs) > 0
    assert len(result.errors) == 0

    # Verify that files were written inside the isolated workspace
    ws_path = app_service.workspace_service.get_workspace_path(result.workspace_id)
    for changed_rel in result.changed_files:
        assert (ws_path / changed_rel).is_file()

    # Verify workspace is retained for inspection
    assert ws_path.is_dir()


def test_added_and_modified_files_with_explicit_content(
    app_service: CodeApplicationService, mock_repo: Path
):
    """Verify application with explicit text contents distinguishes added and modified files."""
    task = app_service.task_service.create_task("Update API routes")

    # Define custom proposal with 1 modify and 1 create
    custom_proposal = ImplementationProposal(
        task_id=task.id,
        task=task.task,
        status="proposed",
        summary="Test proposal",
        files_to_change=[
            ProposedFileChange(
                path="api/main.py", action="modify", description="Update main"
            ),
            ProposedFileChange(
                path="api/routes/auth.py", action="create", description="Add auth route"
            ),
        ],
        execution_steps=["Step 1"],
        verification_commands=["pytest -v"],
        dry_run=True,
    )

    file_contents = {
        "api/main.py": "# Initial API Code\n# Added route registration\n",
        "api/routes/auth.py": "def auth_endpoint():\n    return {'auth': True}\n",
    }

    result = app_service.apply_proposal(
        task.id, file_contents=file_contents, custom_proposal=custom_proposal
    )

    assert result.status == "applied"
    assert len(result.diffs) == 2

    # Check diffs
    diff_map = {d.path: d for d in result.diffs}
    assert diff_map["api/main.py"].change_type == "modified"
    assert "--- a/api/main.py" in diff_map["api/main.py"].diff
    assert "+# Added route registration" in diff_map["api/main.py"].diff

    assert diff_map["api/routes/auth.py"].change_type == "added"
    assert "--- /dev/null" in diff_map["api/routes/auth.py"].diff
    assert "+def auth_endpoint():" in diff_map["api/routes/auth.py"].diff


def test_main_repository_remains_completely_untouched(
    app_service: CodeApplicationService, mock_repo: Path
):
    """Verify that applying code changes leaves the main repository 100% unchanged."""
    before_state = {
        p.relative_to(mock_repo): (p.stat().st_mtime, p.read_bytes())
        for p in mock_repo.rglob("*")
        if p.is_file()
    }

    task = app_service.task_service.create_task("Create utility component")
    result = app_service.apply_proposal(task.id)
    assert result.status == "applied"

    after_state = {
        p.relative_to(mock_repo): (p.stat().st_mtime, p.read_bytes())
        for p in mock_repo.rglob("*")
        if p.is_file()
    }

    assert before_state == after_state


def test_blocked_file_in_proposal_fails_closed(app_service: CodeApplicationService):
    """Verify that proposals containing security-blocked files are rejected before provisioning."""
    task = app_service.task_service.create_task("Modify env secrets")
    bad_proposal = ImplementationProposal(
        task_id=task.id,
        task=task.task,
        status="proposed",
        summary="Blocked proposal",
        files_to_change=[
            ProposedFileChange(
                path=".env", action="modify", description="Malicious env change"
            )
        ],
        execution_steps=["Step 1"],
        verification_commands=[],
        dry_run=True,
    )

    result = app_service.apply_proposal(task.id, custom_proposal=bad_proposal)
    assert result.status == "failed"
    assert any("Blocked path" in err for err in result.errors)
    assert result.workspace_id == ""


def test_path_traversal_in_proposal_fails_closed(app_service: CodeApplicationService):
    """Verify that path traversal attempts in proposals fail closed."""
    task = app_service.task_service.create_task("Path traversal task")
    traversal_proposal = ImplementationProposal(
        task_id=task.id,
        task=task.task,
        status="proposed",
        summary="Traversal proposal",
        files_to_change=[
            ProposedFileChange(
                path="../outside.py", action="create", description="Traversal"
            )
        ],
        execution_steps=["Step 1"],
        verification_commands=[],
        dry_run=True,
    )

    result = app_service.apply_proposal(task.id, custom_proposal=traversal_proposal)
    assert result.status == "failed"
    assert any("Invalid path" in err for err in result.errors)


def test_supplied_content_outside_allowlist_rejected(app_service: CodeApplicationService):
    """Verify that supplied file content targeting unapproved paths is rejected."""
    task = app_service.task_service.create_task("Test allowlist")
    unapproved_contents = {"unapproved_module.py": "def rogue(): pass\n"}

    result = app_service.apply_proposal(task.id, file_contents=unapproved_contents)
    assert result.status == "failed"
    assert any("not in the approved proposal allowlist" in err for err in result.errors)


def test_missing_task_raises_value_error(app_service: CodeApplicationService):
    """Verify that applying a proposal for a non-existent task ID raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        app_service.apply_proposal("task-non-existent-888")


def test_missing_source_file_marked_for_modification(
    app_service: CodeApplicationService,
):
    """Verify that if a file marked for modification is missing from source repo, application fails."""
    task = app_service.task_service.create_task("Modify missing file")
    missing_proposal = ImplementationProposal(
        task_id=task.id,
        task=task.task,
        status="proposed",
        summary="Missing source file",
        files_to_change=[
            ProposedFileChange(
                path="non_existent_file.py",
                action="modify",
                description="Modify missing",
            )
        ],
        execution_steps=["Step 1"],
        verification_commands=[],
        dry_run=True,
    )

    result = app_service.apply_proposal(task.id, custom_proposal=missing_proposal)
    assert result.status == "failed"
    assert any("does not exist in repository" in err for err in result.errors)


def test_empty_proposal_fails_gracefully(app_service: CodeApplicationService):
    """Verify that proposals with zero files to change fail gracefully with structured error."""
    task = app_service.task_service.create_task("Empty proposal task")
    empty_proposal = ImplementationProposal(
        task_id=task.id,
        task=task.task,
        status="proposed",
        summary="Empty",
        files_to_change=[],
        execution_steps=["Step 1"],
        verification_commands=[],
        dry_run=True,
    )

    result = app_service.apply_proposal(task.id, custom_proposal=empty_proposal)
    assert result.status == "failed"
    assert any("contains no files to change" in err for err in result.errors)
