"""Isolated execution workspace service.

Manages sandboxed workspaces located outside the main repository,
enforcing path confinement, security blocklists, and verified cleanup.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

# Blocked filenames, prefixes, and directory segments that must never be copied into a workspace
BLOCKED_EXACT_NAMES: Set[str] = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".git",
    ".gitignore",
    ".gitmodules",
    ".gitattributes",
}

BLOCKED_NAME_PATTERNS: List[str] = [
    ".env.",
    "credential",
    "secret",
    "token",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
    ".pfx",
    ".p12",
]

BLOCKED_DIR_SEGMENTS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    "data",
}

BLOCKED_EXTENSIONS: Set[str] = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".key",
    ".pem",
}

DEFAULT_WORKSPACE_ROOT: Path = Path(tempfile.gettempdir()) / "sdlc_workspaces"


class WorkspaceInfo(BaseModel):
    """Metadata describing an active isolated workspace."""

    workspace_id: str = Field(..., description="Unique identifier of the workspace.")
    workspace_path: str = Field(..., description="Absolute filesystem path to the workspace directory.")
    created_at: str = Field(..., description="ISO 8601 creation timestamp.")
    task_id: Optional[str] = Field(None, description="Optional associated task ID.")
    status: str = Field(default="active", description="Status of the workspace.")


class RegisteredProject(BaseModel):
    """Metadata describing a registered project repository/folder."""

    id: str = Field(..., description="Unique slug or identifier (e.g. 'hrms', 'engine').")
    name: str = Field(..., description="Human-friendly project name.")
    path: str = Field(..., description="Absolute filesystem path to the project directory.")
    project_type: str = Field(default="unknown", description="Detected project type: nextjs, nodejs, python_fastapi, python, react, rust, go, unknown.")
    registered_at: str = Field(..., description="ISO 8601 registration timestamp.")
    available_scripts: Dict[str, str] = Field(default_factory=dict, description="Parsed scripts (npm scripts, Makefile targets, pytest, etc.).")
    default_command: Optional[str] = Field(default=None, description="Recommended startup or run command.")
    test_command: Optional[str] = Field(default=None, description="Recommended test execution command.")
    is_valid: bool = Field(default=True, description="Whether the folder currently exists on disk.")


class RegisteredProjectInspection(BaseModel):
    """Detailed structural inspection of a project folder."""

    project: RegisteredProject
    config_files: List[str] = Field(default_factory=list, description="Configuration files detected (package.json, pyproject.toml, etc.).")
    git_status: Optional[str] = Field(default=None, description="Current Git status summary if available.")
    error: Optional[str] = Field(default=None, description="Error message if inspection encountered issues.")


class WorkspaceFileOperationResult(BaseModel):
    """Result of a file copy or write operation inside a workspace."""

    workspace_id: str = Field(..., description="Workspace ID where the operation occurred.")
    relative_path: str = Field(..., description="Path of the target file relative to the workspace root.")
    action: str = Field(..., description="Operation performed ('copied', 'written', 'read').")
    bytes_transferred: int = Field(default=0, description="Number of bytes read or written.")
    success: bool = Field(default=True, description="Whether the operation completed successfully.")


class WorkspaceCleanupResult(BaseModel):
    """Result of a workspace cleanup and deletion operation."""

    workspace_id: str = Field(..., description="Identifier of the workspace cleaned up.")
    workspace_path: str = Field(..., description="Path that was removed.")
    deleted: bool = Field(..., description="Whether the directory was successfully deleted.")
    message: str = Field(..., description="Status summary of the cleanup operation.")



def is_blocked_path(relative_path: str) -> bool:
    """Checks whether a relative path contains blocked security, secret, or runtime patterns.

    Args:
        relative_path: Normalized relative path to test.

    Returns:
        True if the path should be blocked from copying or accessing, False otherwise.
    """
    pure = PurePath(relative_path)
    lower_path = relative_path.lower()
    file_name = pure.name.lower()

    # Exact filename match
    if file_name in BLOCKED_EXACT_NAMES or file_name.startswith(".env"):
        return True

    # Substring security patterns
    for pattern in BLOCKED_NAME_PATTERNS:
        if pattern in file_name:
            return True

    # Blocked directory segments
    for part in pure.parts:
        if part.lower() in BLOCKED_DIR_SEGMENTS:
            return True

    # Blocked extensions
    suffix = pure.suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        return True

    return False


class WorkspaceService:
    """Manages secure, isolated temporary workspaces for autonomous SDLC tasks."""

    METADATA_FILENAME: str = ".sdlc_workspace.json"

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        default_source_repo: Optional[Path] = None,
    ) -> None:
        env_root = os.getenv("SDLC_WORKSPACE_ROOT")
        if workspace_root is not None:
            self.workspace_root: Path = Path(workspace_root).resolve()
        elif env_root:
            self.workspace_root = Path(env_root).resolve()
        else:
            self.workspace_root = DEFAULT_WORKSPACE_ROOT.resolve()

        self.default_source_repo: Path = (
            Path(default_source_repo).resolve()
            if default_source_repo is not None
            else Path(__file__).resolve().parent.parent
        )

        # Track active workspaces created by this service instance
        self._tracked_workspaces: Dict[str, Path] = {}
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, task_id: Optional[str] = None) -> WorkspaceInfo:
        """Creates a uniquely named workspace directory with verification metadata.

        Args:
            task_id: Optional task identifier for associating with the workspace.

        Returns:
            A WorkspaceInfo instance describing the new workspace.
        """
        workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
        ws_path = (self.workspace_root / workspace_id).resolve()
        ws_path.mkdir(parents=True, exist_ok=False)

        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "workspace_id": workspace_id,
            "created_at": now,
            "task_id": task_id,
            "service": "autonomous-sdlc-workspace-service",
            "version": "0.1.0",
        }

        # Write internal tracking marker
        meta_file = ws_path / self.METADATA_FILENAME
        meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        self._tracked_workspaces[workspace_id] = ws_path

        return WorkspaceInfo(
            workspace_id=workspace_id,
            workspace_path=str(ws_path),
            created_at=now,
            task_id=task_id,
            status="active",
        )

    def get_workspace_path(self, workspace_id: str) -> Path:
        """Validates and retrieves the verified path for a tracked workspace.

        Args:
            workspace_id: Unique workspace identifier.

        Returns:
            Resolved Path of the workspace.

        Raises:
            ValueError: If workspace_id is invalid or untracked.
        """
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("Workspace ID must be a non-empty string.")

        clean_id = workspace_id.strip()
        ws_path = (self.workspace_root / clean_id).resolve()

        # Security check: must reside strictly directly inside workspace_root
        if ws_path.parent != self.workspace_root:
            raise ValueError(f"Workspace path escape attempt detected: '{workspace_id}'.")

        if not ws_path.is_dir():
            raise ValueError(f"Workspace '{clean_id}' does not exist.")

        # Verification check: must contain the valid metadata marker
        meta_file = ws_path / self.METADATA_FILENAME
        if not meta_file.is_file():
            raise ValueError(f"Directory at '{ws_path}' is not a verified SDLC workspace.")

        return ws_path

    def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Retrieves WorkspaceInfo for a tracked workspace if it exists and is valid.

        Args:
            workspace_id: Unique workspace identifier.

        Returns:
            WorkspaceInfo instance, or None if the workspace does not exist or is invalid.
        """
        try:
            ws_path = self.get_workspace_path(workspace_id)
            meta_file = ws_path / self.METADATA_FILENAME
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            return WorkspaceInfo(
                workspace_id=workspace_id,
                workspace_path=str(ws_path),
                created_at=data.get("created_at", ""),
                task_id=data.get("task_id"),
                status="active",
            )
        except Exception:
            return None

    def _resolve_safe_target_path(self, ws_path: Path, relative_path: str) -> Path:
        """Resolves and validates a relative path inside a workspace, preventing escapes and symlink bypasses.

        Args:
            ws_path: Validated workspace root path.
            relative_path: Relative path string to target.

        Returns:
            The resolved target Path safely contained in the workspace.

        Raises:
            ValueError: If the path is absolute, traversals are detected, or symlinks escape.
        """
        if not isinstance(relative_path, str):
            raise ValueError("Target path must be a string.")

        cleaned = relative_path.strip()
        if not cleaned:
            raise ValueError("Target path cannot be empty or whitespace only.")

        # Reject absolute paths or Windows drive letters
        if cleaned.startswith(("/", "\\")) or (len(cleaned) > 1 and cleaned[1] == ":"):
            raise ValueError(f"Absolute paths are not allowed: '{cleaned}'.")

        pure = PurePath(cleaned)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"Path traversal is not allowed: '{cleaned}'.")

        if "\0" in cleaned:
            raise ValueError("Invalid null byte in path.")

        # Prohibit editing internal tracking metadata
        if pure.name == self.METADATA_FILENAME:
            raise ValueError(f"Modification of internal metadata '{self.METADATA_FILENAME}' is prohibited.")

        target = ws_path / pure

        # Symlink protection: Check all existing parent components to ensure none escape
        curr = target.parent
        while curr != ws_path and curr != curr.parent:
            if curr.is_symlink():
                resolved_link = curr.resolve()
                if not resolved_link.is_relative_to(ws_path):
                    raise ValueError(f"Symlink in path escapes workspace confinement: '{cleaned}'.")
            curr = curr.parent

        if target.is_symlink():
            resolved_target = target.resolve()
            if not resolved_target.is_relative_to(ws_path):
                raise ValueError(f"Symlink target escapes workspace confinement: '{cleaned}'.")

        return target

    def copy_file_to_workspace(
        self,
        workspace_id: str,
        relative_file_path: str,
        source_repo_path: Optional[Path] = None,
    ) -> WorkspaceFileOperationResult:
        """Copies an explicitly selected file from the source repository into the workspace.

        Args:
            workspace_id: Target workspace ID.
            relative_file_path: Relative path of the file to copy.
            source_repo_path: Optional source repository path (defaults to engine root).

        Returns:
            WorkspaceFileOperationResult with details of the copied file.

        Raises:
            ValueError: If the file is blocked, traverses paths, or inputs are invalid.
            FileNotFoundError: If the source file does not exist.
        """
        if is_blocked_path(relative_file_path):
            raise ValueError(
                f"Copy rejected: File '{relative_file_path}' matches security blocklist "
                "(secrets, env files, caches, or runtime state)."
            )

        ws_path = self.get_workspace_path(workspace_id)
        target_file = self._resolve_safe_target_path(ws_path, relative_file_path)

        source_root = (source_repo_path if source_repo_path is not None else self.default_source_repo).resolve()
        source_pure = PurePath(relative_file_path.strip())
        if source_pure.is_absolute() or ".." in source_pure.parts:
            raise ValueError(f"Path traversal in source path: '{relative_file_path}'.")

        source_file = (source_root / source_pure).resolve()
        if not source_file.is_relative_to(source_root):
            raise ValueError(f"Source file escapes source repository boundary: '{relative_file_path}'.")

        if not source_file.is_file():
            raise FileNotFoundError(f"Source file does not exist: '{source_file}'.")

        # Create target directories inside workspace and copy content
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)

        size = target_file.stat().st_size
        return WorkspaceFileOperationResult(
            workspace_id=workspace_id,
            relative_path=PurePath(relative_file_path).as_posix(),
            action="copied",
            bytes_transferred=size,
            success=True,
        )

    def write_file_to_workspace(
        self,
        workspace_id: str,
        relative_file_path: str,
        content: str,
    ) -> WorkspaceFileOperationResult:
        """Writes explicit text content to a file inside the isolated workspace only.

        Args:
            workspace_id: Target workspace ID.
            relative_file_path: Relative file path to write to inside the workspace.
            content: Text content to write.

        Returns:
            WorkspaceFileOperationResult.

        Raises:
            ValueError: If path validation fails or invalid arguments are supplied.
        """
        if not isinstance(content, str):
            raise ValueError("Content must be a string.")

        ws_path = self.get_workspace_path(workspace_id)
        target_file = self._resolve_safe_target_path(ws_path, relative_file_path)

        target_file.parent.mkdir(parents=True, exist_ok=True)
        encoded_bytes = content.encode("utf-8")
        target_file.write_bytes(encoded_bytes)

        return WorkspaceFileOperationResult(
            workspace_id=workspace_id,
            relative_path=PurePath(relative_file_path).as_posix(),
            action="written",
            bytes_transferred=len(encoded_bytes),
            success=True,
        )

    def read_file_from_workspace(self, workspace_id: str, relative_file_path: str) -> str:
        """Reads text content from a file inside the workspace.

        Args:
            workspace_id: Target workspace ID.
            relative_file_path: Relative file path to read.

        Returns:
            File content string.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        ws_path = self.get_workspace_path(workspace_id)
        target_file = self._resolve_safe_target_path(ws_path, relative_file_path)

        if not target_file.is_file():
            raise FileNotFoundError(f"File '{relative_file_path}' does not exist in workspace '{workspace_id}'.")

        return target_file.read_text(encoding="utf-8")

    def cleanup_workspace(self, workspace_id: str) -> WorkspaceCleanupResult:
        """Safely removes a verified workspace directory created by this service.

        Refuses to delete the source repository, parent directories, or any directory
        lacking the internal SDLC workspace marker.

        Args:
            workspace_id: Identifier of the workspace to delete.

        Returns:
            WorkspaceCleanupResult.

        Raises:
            ValueError: If workspace validation fails.
        """
        ws_path = self.get_workspace_path(workspace_id)

        # Safety check: Never delete the default source repository or system roots
        if ws_path == self.default_source_repo or ws_path in self.default_source_repo.parents:
            raise ValueError("Refusing to delete source repository path.")

        if ws_path == self.workspace_root or ws_path in self.workspace_root.parents:
            raise ValueError("Refusing to delete workspace root directory.")

        # Remove the directory tree
        shutil.rmtree(ws_path, ignore_errors=False)
        self._tracked_workspaces.pop(workspace_id, None)

        return WorkspaceCleanupResult(
            workspace_id=workspace_id,
            workspace_path=str(ws_path),
            deleted=True,
            message=f"Workspace '{workspace_id}' safely deleted.",
        )

    # =========================================================================
    # Workspace & Project Registration (Milestone 2)
    # =========================================================================

    def _get_registry_file(self) -> Path:
        """Returns the path to the persistent registered projects store."""
        reg_file = self.default_source_repo / "data" / "registered_workspaces.json"
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        if not reg_file.exists():
            # Seed with current autonomous-sdlc-engine repository by default
            seed_data = [
                {
                    "id": "autonomous-sdlc-engine",
                    "name": "Autonomous SDLC Engine (Current Project)",
                    "path": str(self.default_source_repo),
                    "project_type": "python_fastapi",
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "available_scripts": {
                        "backend_tests": ".venv\\Scripts\\pytest -v",
                        "start_backend": ".venv\\Scripts\\python -m uvicorn api.main:app --reload --port 8000",
                        "frontend_dev": "npm run dev",
                    },
                    "default_command": ".venv\\Scripts\\python -m uvicorn api.main:app --port 8000",
                    "test_command": ".venv\\Scripts\\pytest -v",
                    "is_valid": True,
                }
            ]
            reg_file.write_text(json.dumps(seed_data, indent=2), encoding="utf-8")
        return reg_file

    def list_registered_projects(self) -> List[RegisteredProject]:
        """Lists all registered workspace project directories with disk aliveness checks."""
        reg_file = self._get_registry_file()
        try:
            items = json.loads(reg_file.read_text(encoding="utf-8"))
        except Exception:
            items = []

        results: List[RegisteredProject] = []
        for item in items:
            p_path = Path(item["path"]).resolve()
            is_valid = p_path.exists() and p_path.is_dir()
            item["is_valid"] = is_valid
            results.append(RegisteredProject.model_validate(item))
        return results

    def register_project(self, folder_path: str, name: Optional[str] = None) -> RegisteredProject:
        """Registers a project folder, validating its existence, detecting its type and scripts.

        Args:
            folder_path: Absolute or relative path to project directory.
            name: Optional human-friendly name (defaults to directory name).

        Returns:
            The RegisteredProject record.

        Raises:
            ValueError: If folder path does not exist, is not a directory, or fails safety checks.
        """
        if not isinstance(folder_path, str) or not folder_path.strip():
            raise ValueError("Project folder path must be a non-empty string.")

        target = Path(folder_path.strip()).resolve()
        if not target.exists():
            raise ValueError(f"Project folder does not exist on disk: '{target}'.")
        if not target.is_dir():
            raise ValueError(f"Project path is not a directory: '{target}'.")

        # System directory safety check
        if os.name == "nt":
            sys_root = Path(os.environ.get("SystemRoot", "C:\\Windows")).resolve()
            try:
                target.relative_to(sys_root)
                raise ValueError(f"Cannot register Windows system directory: '{target}'.")
            except ValueError as err:
                if "Cannot register" in str(err):
                    raise

        # Check if root drive alone was given (e.g. C:\ or E:\)
        if len(target.parts) <= 1:
            raise ValueError(f"Refusing to register an entire drive root: '{target}'.")

        proj_name = (name or target.name or str(target)).strip()
        slug = re.sub(r"[^a-zA-Z0-9_\-]+", "-", proj_name.lower()).strip("-") or "project"

        # Inspect project files to identify type and scripts
        inspection = self.inspect_project_path(target)
        detected_type = inspection.project.project_type
        scripts = inspection.project.available_scripts
        default_cmd = inspection.project.default_command
        test_cmd = inspection.project.test_command

        record = RegisteredProject(
            id=slug,
            name=proj_name,
            path=str(target),
            project_type=detected_type,
            registered_at=datetime.now(timezone.utc).isoformat(),
            available_scripts=scripts,
            default_command=default_cmd,
            test_command=test_cmd,
            is_valid=True,
        )

        # Update JSON store
        reg_file = self._get_registry_file()
        try:
            current = json.loads(reg_file.read_text(encoding="utf-8"))
        except Exception:
            current = []

        # Deduplicate or replace existing
        updated = [p for p in current if p.get("id") != slug and Path(p.get("path", "")).resolve() != target]
        updated.append(record.model_dump())
        reg_file.write_text(json.dumps(updated, indent=2), encoding="utf-8")

        return record

    def inspect_project_path(self, target_dir: Path) -> RegisteredProjectInspection:
        """Inspects project structure, configuration files, and available scripts."""
        target = Path(target_dir).resolve()
        config_files: List[str] = []
        scripts: Dict[str, str] = {}
        project_type = "unknown"
        default_cmd: Optional[str] = None
        test_cmd: Optional[str] = None

        if not target.exists() or not target.is_dir():
            dummy = RegisteredProject(
                id=target.name.lower() or "unknown",
                name=target.name or "Unknown",
                path=str(target),
                project_type="unknown",
                registered_at=datetime.now(timezone.utc).isoformat(),
                is_valid=False,
            )
            return RegisteredProjectInspection(
                project=dummy,
                config_files=[],
                error=f"Directory does not exist: '{target}'",
            )

        # Check for package.json (Next.js / Node / React)
        pkg_json = target / "package.json"
        if pkg_json.is_file():
            config_files.append("package.json")
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                pkg_scripts = data.get("scripts", {})
                for k, v in pkg_scripts.items():
                    scripts[f"npm run {k}"] = str(v)

                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "next" in deps:
                    project_type = "nextjs"
                    default_cmd = "npm run dev"
                elif "react" in deps:
                    project_type = "react"
                    default_cmd = "npm run start" if "start" in pkg_scripts else "npm run dev"
                else:
                    project_type = "nodejs"
                    default_cmd = "npm start" if "start" in pkg_scripts else "node index.js"

                if "test" in pkg_scripts:
                    test_cmd = "npm test"
            except Exception:
                pass

        # Check for Next.js explicit config
        if (target / "next.config.js").is_file() or (target / "next.config.mjs").is_file() or (target / "next.config.ts").is_file():
            project_type = "nextjs"
            default_cmd = "npm run dev"
            config_files.append("next.config")

        # Check for Python (FastAPI, Django, Flask, pytest, pyproject.toml)
        pyproject = target / "pyproject.toml"
        reqs = target / "requirements.txt"
        has_python = False

        if pyproject.is_file():
            config_files.append("pyproject.toml")
            has_python = True
        if reqs.is_file():
            config_files.append("requirements.txt")
            has_python = True

        if has_python:
            if project_type == "unknown":
                project_type = "python"
            # Detect FastAPI
            try:
                txt = (reqs.read_text(encoding="utf-8") if reqs.is_file() else "") + (pyproject.read_text(encoding="utf-8") if pyproject.is_file() else "")
                if "fastapi" in txt.lower() or "uvicorn" in txt.lower():
                    project_type = "python_fastapi"
                    default_cmd = "python -m uvicorn api.main:app --reload --port 8000"
                if "pytest" in txt.lower() or (target / "tests").is_dir() or (target / "pytest.ini").is_file():
                    test_cmd = "pytest -v"
            except Exception:
                pass

        # Check for Git
        git_status_summary = None
        git_dir = target / ".git"
        if git_dir.is_dir():
            config_files.append(".git")
            try:
                cmd = shutil.which("git") or "git"
                res = subprocess.run(
                    [cmd, "status", "--short"],
                    cwd=str(target),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                    shell=False,
                )
                if res.returncode == 0:
                    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                    git_status_summary = f"{len(lines)} modified/untracked file(s)" if lines else "Working tree clean"
            except Exception:
                git_status_summary = "Git initialized"

        proj = RegisteredProject(
            id=re.sub(r"[^a-zA-Z0-9_\-]+", "-", target.name.lower()).strip("-") or "project",
            name=target.name,
            path=str(target),
            project_type=project_type,
            registered_at=datetime.now(timezone.utc).isoformat(),
            available_scripts=scripts,
            default_command=default_cmd,
            test_command=test_cmd,
            is_valid=True,
        )

        return RegisteredProjectInspection(
            project=proj,
            config_files=config_files,
            git_status=git_status_summary,
        )

    def resolve_project_for_task(self, task_description: str) -> Optional[RegisteredProject]:
        """Matches a task description to a registered project if explicitly or implicitly mentioned."""
        projects = self.list_registered_projects()
        desc_lower = task_description.lower()

        # 1. Exact or keyword match on project name / ID
        for proj in projects:
            p_id = proj.id.lower()
            p_name = proj.name.lower()
            if p_id in desc_lower or p_name in desc_lower:
                return proj

        # 2. Match common aliases (e.g. 'hrms' -> matches any project with hrms in name or path)
        for proj in projects:
            for token in re.findall(r"[a-zA-Z0-9_\-]+", desc_lower):
                if len(token) >= 3 and (token in proj.id.lower() or token in Path(proj.path).name.lower()):
                    return proj

        return None

