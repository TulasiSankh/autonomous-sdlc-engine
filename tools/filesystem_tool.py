"""Filesystem tool for safe directory creation, file operations, and path verification."""

import os
import sys
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any, Dict, List, Optional

from tools.base import BaseTool, ToolExecutionResult

MAX_READ_BYTES = 1024 * 1024  # 1 MB bound for file reads


class FilesystemTool(BaseTool):
    """Platform-aware filesystem tool supporting directory creation, listing, file creation, and path checks."""

    name = "filesystem"
    description = "Performs filesystem operations such as creating directories, listing files, and reading/writing files."
    supported_actions = [
        "create_directory",
        "ensure_directory",
        "list_directory",
        "create_file",
        "write_file",
        "read_file",
        "path_exists",
    ]

    def __init__(self, allowed_roots: Optional[List[Path]] = None) -> None:
        """Initializes the filesystem tool.
        
        Args:
            allowed_roots: Optional list of directory roots to confine operations within.
                           If None, general system paths are permitted subject to safety checks.
        """
        self.allowed_roots = [p.resolve() for p in allowed_roots] if allowed_roots else None

    def get_parameters_schema(self, action: Optional[str] = None) -> Dict[str, Any]:
        schemas: Dict[str, Dict[str, Any]] = {
            "create_directory": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path of the directory to create."},
                    "parents": {"type": "boolean", "description": "Create parent directories if they don't exist.", "default": True},
                },
                "required": ["path"],
            },
            "list_directory": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."},
                    "max_items": {"type": "integer", "description": "Maximum number of items to return.", "default": 100},
                },
                "required": ["path"],
            },
            "create_file": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to create or write to."},
                    "content": {"type": "string", "description": "Text content to write."},
                    "overwrite": {"type": "boolean", "description": "Whether to overwrite existing file.", "default": True},
                },
                "required": ["path", "content"],
            },
            "read_file": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read."},
                },
                "required": ["path"],
            },
            "path_exists": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to check for existence."},
                },
                "required": ["path"],
            },
        }
        return schemas.get(action or "create_directory", {})

    def resolve_and_validate_path(self, raw_path: str) -> Path:
        """Validates and resolves a target filesystem path.
        
        Args:
            raw_path: Input path string (e.g. 'E:\\MyProject', './subfolder', etc.).
            
        Returns:
            Resolved Path object.
            
        Raises:
            ValueError: If path contains invalid characters, references a non-existent drive, or violates root confinement.
        """
        if not raw_path or not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("Path must be a non-empty string.")

        clean_path = raw_path.strip()

        # Reject null byte injection
        if "\0" in clean_path:
            raise ValueError("Path contains invalid null byte character.")

        # Check for drive letter on Windows (e.g. 'E:\...', 'Z:\...')
        if sys.platform == "win32":
            win_pure = PureWindowsPath(clean_path)
            if win_pure.drive:
                drive_root = f"{win_pure.drive}\\"
                if not os.path.exists(drive_root):
                    raise ValueError(
                        f"Drive '{win_pure.drive}' does not exist or is not available on this system."
                    )

        target = Path(clean_path).expanduser().resolve()

        # If allowed_roots are configured, ensure target is confined within one of them
        if self.allowed_roots:
            is_confined = any(
                target == root or root in target.parents for root in self.allowed_roots
            )
            if not is_confined:
                raise ValueError(
                    f"Path '{clean_path}' is outside permitted directory roots: "
                    f"{[str(r) for r in self.allowed_roots]}"
                )

        return target

    def execute(self, action: str, params: Dict[str, Any]) -> ToolExecutionResult:
        self.validate_action(action)

        raw_path = params.get("path")
        if not raw_path:
            return ToolExecutionResult(
                success=False,
                error="Missing required parameter 'path'.",
            )

        try:
            target_path = self.resolve_and_validate_path(str(raw_path))
        except ValueError as exc:
            return ToolExecutionResult(
                success=False,
                error=str(exc),
                metadata={"raw_path": raw_path, "blocked": True},
            )

        if action in ("create_directory", "ensure_directory"):
            return self._create_directory(target_path, params.get("parents", True))
        elif action == "list_directory":
            return self._list_directory(target_path, params.get("max_items", 100))
        elif action in ("create_file", "write_file"):
            return self._create_file(
                target_path,
                params.get("content", ""),
                params.get("overwrite", True),
            )
        elif action == "read_file":
            return self._read_file(target_path)
        elif action == "path_exists":
            return self._path_exists(target_path)

        return ToolExecutionResult(success=False, error=f"Unhandled action '{action}'.")

    def _create_directory(self, target_path: Path, parents: bool) -> ToolExecutionResult:
        try:
            if target_path.exists():
                if not target_path.is_dir():
                    return ToolExecutionResult(
                        success=False,
                        error=f"Target path '{target_path}' exists but is a file, not a directory.",
                        metadata={"path": str(target_path)},
                    )
                return ToolExecutionResult(
                    success=True,
                    output=f"Directory already exists: '{target_path}'.",
                    metadata={"path": str(target_path), "already_existed": True},
                )

            target_path.mkdir(parents=parents, exist_ok=True)
            # Truthful verification on disk: never claim creation without confirming existence
            if not target_path.exists() or not target_path.is_dir():
                return ToolExecutionResult(
                    success=False,
                    error=f"Verification failed: directory '{target_path}' could not be confirmed on disk after creation.",
                    metadata={"path": str(target_path)},
                )

            return ToolExecutionResult(
                success=True,
                output=f"Successfully created directory '{target_path}'.",
                metadata={"path": str(target_path), "already_existed": False},
            )
        except PermissionError:
            return ToolExecutionResult(
                success=False,
                error=f"Permission denied: cannot create directory at '{target_path}'.",
                metadata={"path": str(target_path)},
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Failed to create directory '{target_path}': {str(exc)}",
                metadata={"path": str(target_path)},
            )

    def _list_directory(self, target_path: Path, max_items: int) -> ToolExecutionResult:
        if not target_path.exists():
            return ToolExecutionResult(
                success=False,
                error=f"Directory does not exist: '{target_path}'.",
                metadata={"path": str(target_path)},
            )
        if not target_path.is_dir():
            return ToolExecutionResult(
                success=False,
                error=f"Path '{target_path}' is not a directory.",
                metadata={"path": str(target_path)},
            )

        try:
            items: List[Dict[str, Any]] = []
            for entry in list(target_path.iterdir())[:max_items]:
                try:
                    stat = entry.stat()
                    items.append({
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "is_file": entry.is_file(),
                        "size_bytes": stat.st_size if entry.is_file() else None,
                        "modified_at": stat.st_mtime,
                    })
                except Exception:
                    items.append({
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "is_file": entry.is_file(),
                    })

            return ToolExecutionResult(
                success=True,
                output=items,
                metadata={"path": str(target_path), "count": len(items)},
            )
        except PermissionError:
            return ToolExecutionResult(
                success=False,
                error=f"Permission denied reading directory '{target_path}'.",
                metadata={"path": str(target_path)},
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Failed to list directory '{target_path}': {str(exc)}",
                metadata={"path": str(target_path)},
            )

    def _create_file(self, target_path: Path, content: str, overwrite: bool) -> ToolExecutionResult:
        try:
            if target_path.exists() and not overwrite:
                return ToolExecutionResult(
                    success=False,
                    error=f"File already exists and overwrite is disabled: '{target_path}'.",
                    metadata={"path": str(target_path)},
                )

            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

            return ToolExecutionResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to '{target_path}'.",
                metadata={"path": str(target_path), "bytes_written": len(content.encode('utf-8'))},
            )
        except PermissionError:
            return ToolExecutionResult(
                success=False,
                error=f"Permission denied: cannot write to file '{target_path}'.",
                metadata={"path": str(target_path)},
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Failed to write file '{target_path}': {str(exc)}",
                metadata={"path": str(target_path)},
            )

    def _read_file(self, target_path: Path) -> ToolExecutionResult:
        if not target_path.exists():
            return ToolExecutionResult(
                success=False,
                error=f"File not found: '{target_path}'.",
                metadata={"path": str(target_path)},
            )
        if not target_path.is_file():
            return ToolExecutionResult(
                success=False,
                error=f"Path is not a regular file: '{target_path}'.",
                metadata={"path": str(target_path)},
            )

        try:
            size = target_path.stat().st_size
            if size > MAX_READ_BYTES:
                content = target_path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_BYTES]
                return ToolExecutionResult(
                    success=True,
                    output={
                        "content": content,
                        "size": size,
                        "truncated": True,
                        "path": str(target_path),
                    },
                    metadata={"path": str(target_path), "truncated": True, "total_size": size},
                )

            content = target_path.read_text(encoding="utf-8", errors="replace")
            return ToolExecutionResult(
                success=True,
                output={
                    "content": content,
                    "size": size,
                    "truncated": False,
                    "path": str(target_path),
                },
                metadata={"path": str(target_path), "size": size},
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Failed to read file '{target_path}': {str(exc)}",
                metadata={"path": str(target_path)},
            )

    def _path_exists(self, target_path: Path) -> ToolExecutionResult:
        exists = target_path.exists()
        is_dir = target_path.is_dir() if exists else False
        is_file = target_path.is_file() if exists else False
        return ToolExecutionResult(
            success=True,
            output={
                "path": str(target_path),
                "exists": exists,
                "is_dir": is_dir,
                "is_file": is_file,
            },
            metadata={"path": str(target_path), "exists": exists},
        )
