"""Comprehensive unit and security tests for WorkspaceService."""

import os
from pathlib import Path
import pytest

from services.workspace_service import (
    WorkspaceCleanupResult,
    WorkspaceFileOperationResult,
    WorkspaceInfo,
    WorkspaceService,
    is_blocked_path,
)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Fixture creating a temporary mock repository structure."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()

    # Valid files
    (repo_dir / "api").mkdir()
    (repo_dir / "api" / "main.py").write_text("# Main API\n", encoding="utf-8")
    (repo_dir / "README.md").write_text("# Readme\n", encoding="utf-8")

    # Blocked sensitive files
    (repo_dir / ".env").write_text("SECRET=123\n", encoding="utf-8")
    (repo_dir / ".env.local").write_text("LOCAL_SECRET=abc\n", encoding="utf-8")
    (repo_dir / ".git").mkdir()
    (repo_dir / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (repo_dir / ".venv").mkdir()
    (repo_dir / ".venv" / "pyvenv.cfg").write_text("version = 3.12\n", encoding="utf-8")
    (repo_dir / "server_secret.key").write_text("PRIVATE_KEY\n", encoding="utf-8")
    (repo_dir / "database.sqlite3").write_bytes(b"SQLite format 3\0")

    return repo_dir


@pytest.fixture
def workspace_service(tmp_path: Path, fake_repo: Path) -> WorkspaceService:
    """Fixture creating a WorkspaceService targeting isolated temp directory."""
    ws_root = tmp_path / "isolated_workspaces"
    return WorkspaceService(workspace_root=ws_root, default_source_repo=fake_repo)


def test_workspace_creation(workspace_service: WorkspaceService):
    """Verify unique workspace creation, structure, metadata file, and model output."""
    ws_info = workspace_service.create_workspace(task_id="task-test-001")

    assert isinstance(ws_info, WorkspaceInfo)
    assert ws_info.workspace_id.startswith("ws_")
    assert ws_info.task_id == "task-test-001"
    assert ws_info.status == "active"

    ws_dir = Path(ws_info.workspace_path)
    assert ws_dir.is_dir()
    assert (ws_dir / WorkspaceService.METADATA_FILENAME).is_file()


def test_copy_permitted_files(workspace_service: WorkspaceService, fake_repo: Path):
    """Verify that allowed source files can be copied cleanly into the workspace."""
    ws_info = workspace_service.create_workspace()
    result = workspace_service.copy_file_to_workspace(ws_info.workspace_id, "api/main.py")

    assert isinstance(result, WorkspaceFileOperationResult)
    assert result.action == "copied"
    assert result.success is True
    assert result.relative_path == "api/main.py"

    ws_path = Path(ws_info.workspace_path)
    copied_file = ws_path / "api" / "main.py"
    assert copied_file.is_file()
    assert copied_file.read_text(encoding="utf-8") == "# Main API\n"


@pytest.mark.parametrize(
    "blocked_file",
    [
        ".env",
        ".env.local",
        ".env.production",
        ".git/config",
        ".venv/pyvenv.cfg",
        "server_secret.key",
        "database.sqlite3",
        "tokens.pem",
    ],
)
def test_blocked_files_rejected(workspace_service: WorkspaceService, blocked_file: str):
    """Verify that all blocked files matching secret or runtime patterns are rejected."""
    ws_info = workspace_service.create_workspace()

    assert is_blocked_path(blocked_file) is True
    with pytest.raises(ValueError, match="security blocklist"):
        workspace_service.copy_file_to_workspace(ws_info.workspace_id, blocked_file)


@pytest.mark.parametrize(
    "traversal_path",
    [
        "../outside.py",
        "../../etc/passwd",
        "/etc/shadow",
        "C:/Windows/System32/cmd.exe",
        "dir/../../escape.txt",
    ],
)
def test_path_traversal_rejection(workspace_service: WorkspaceService, traversal_path: str):
    """Verify that path traversals and absolute paths are rejected for all file operations."""
    ws_info = workspace_service.create_workspace()

    with pytest.raises(ValueError, match="not allowed|traversal|Absolute"):
        workspace_service.copy_file_to_workspace(ws_info.workspace_id, traversal_path)

    with pytest.raises(ValueError, match="not allowed|traversal|Absolute"):
        workspace_service.write_file_to_workspace(ws_info.workspace_id, traversal_path, "content")

    with pytest.raises(ValueError, match="not allowed|traversal|Absolute"):
        workspace_service.read_file_from_workspace(ws_info.workspace_id, traversal_path)


def test_controlled_file_changes_inside_workspace(
    workspace_service: WorkspaceService, fake_repo: Path
):
    """Verify writing text content inside workspace without mutating the source repository."""
    ws_info = workspace_service.create_workspace()
    rel_file = "generated/logic.py"
    content = "def calculate_sum(a, b):\n    return a + b\n"

    write_result = workspace_service.write_file_to_workspace(
        ws_info.workspace_id, rel_file, content
    )
    assert isinstance(write_result, WorkspaceFileOperationResult)
    assert write_result.action == "written"
    assert write_result.bytes_transferred == len(content.encode("utf-8"))

    # Read back and verify
    read_content = workspace_service.read_file_from_workspace(ws_info.workspace_id, rel_file)
    assert read_content == content

    # Verify source repository remains completely untouched
    assert not (fake_repo / "generated" / "logic.py").exists()


def test_metadata_file_tamper_protection(workspace_service: WorkspaceService):
    """Verify that direct writes to the internal workspace metadata file are rejected."""
    ws_info = workspace_service.create_workspace()
    with pytest.raises(ValueError, match="prohibited"):
        workspace_service.write_file_to_workspace(
            ws_info.workspace_id, WorkspaceService.METADATA_FILENAME, "{}"
        )


def test_symlink_escape_protection(workspace_service: WorkspaceService, tmp_path: Path):
    """Verify that symlinks attempting to escape workspace boundaries are detected and blocked."""
    ws_info = workspace_service.create_workspace()
    ws_dir = Path(ws_info.workspace_path)
    external_target = tmp_path / "outside_secret.txt"
    external_target.write_text("confidential", encoding="utf-8")

    link_path = ws_dir / "external_link"
    try:
        os.symlink(external_target, link_path)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this environment")

    # Attempting to access file through symlink escaping workspace
    with pytest.raises(ValueError, match="escapes workspace confinement"):
        workspace_service.read_file_from_workspace(ws_info.workspace_id, "external_link")


def test_symlink_mocked_escape_detection(workspace_service: WorkspaceService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Verify symlink escape detection logic even when OS restrictions prevent real symlinks."""
    ws_info = workspace_service.create_workspace()
    outside_dir = tmp_path / "outside_dir"

    # Monkeypatch is_symlink and resolve on Path to simulate an escaping symlink
    real_resolve = Path.resolve
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "fake_symlink")
    monkeypatch.setattr(Path, "resolve", lambda self, *args, **kwargs: outside_dir if self.name == "fake_symlink" else real_resolve(self, *args, **kwargs))

    with pytest.raises(ValueError, match="escapes workspace confinement"):
        workspace_service.write_file_to_workspace(ws_info.workspace_id, "fake_symlink/file.txt", "data")



def test_cleanup_confinement(
    workspace_service: WorkspaceService, fake_repo: Path, tmp_path: Path
):
    """Verify that cleanup safely deletes only tracked workspaces and refuses arbitrary paths."""
    ws_info = workspace_service.create_workspace()
    ws_path = Path(ws_info.workspace_path)
    assert ws_path.is_dir()

    # Valid cleanup
    cleanup_res = workspace_service.cleanup_workspace(ws_info.workspace_id)
    assert isinstance(cleanup_res, WorkspaceCleanupResult)
    assert cleanup_res.deleted is True
    assert not ws_path.exists()

    # Attempting cleanup on already deleted workspace raises ValueError
    with pytest.raises(ValueError, match="does not exist"):
        workspace_service.cleanup_workspace(ws_info.workspace_id)

    # Attempting to delete an unverified arbitrary directory outside
    fake_dir = tmp_path / "isolated_workspaces" / "arbitrary_dir"
    fake_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="not a verified SDLC workspace"):
        workspace_service.cleanup_workspace("arbitrary_dir")
    assert fake_dir.is_dir()

    # Refuse deleting the source repo
    with pytest.raises(ValueError, match="escape attempt detected|does not exist"):
        workspace_service.cleanup_workspace(str(fake_repo))


def test_missing_files_error_handling(workspace_service: WorkspaceService):
    """Verify FileNotFoundError for missing source or workspace files."""
    ws_info = workspace_service.create_workspace()

    # Source file does not exist
    with pytest.raises(FileNotFoundError):
        workspace_service.copy_file_to_workspace(ws_info.workspace_id, "non_existent.py")

    # Workspace file does not exist
    with pytest.raises(FileNotFoundError):
        workspace_service.read_file_from_workspace(ws_info.workspace_id, "missing_in_ws.py")


@pytest.mark.parametrize("invalid_id", ["", "   ", "\n", 12345, None])
def test_invalid_workspace_id(workspace_service: WorkspaceService, invalid_id):
    """Verify rejection of invalid workspace IDs."""
    with pytest.raises(ValueError, match="must be a non-empty string"):
        workspace_service.get_workspace_path(invalid_id)
