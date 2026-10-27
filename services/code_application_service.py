"""Controlled code application service.

Applies DeveloperAgent implementation proposals to isolated workspaces managed
by WorkspaceService, strictly enforcing path confinement and generating unified diffs.
"""

import difflib
from pathlib import Path, PurePath
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from agents.developer import (
    DeveloperAgent,
    FileDiff,
    ImplementationProposal,
    ProposedFileChange,
    generate_unified_diff,
    validate_relative_path,
)
from services.task_service import TaskRecord, TaskService
from services.workspace_service import (
    WorkspaceInfo,
    WorkspaceService,
    is_blocked_path,
)


class CodeApplicationResult(BaseModel):
    """Structured result of applying an implementation proposal to an isolated workspace."""

    task_id: str = Field(..., description="Task identifier.")
    workspace_id: str = Field(..., description="Isolated workspace identifier.")
    status: str = Field(..., description="Operation status ('applied', 'failed', 'partial_failure').")
    summary: str = Field(..., description="Summary of applied changes.")
    changed_files: List[str] = Field(default_factory=list, description="Relative paths of changed files.")
    diffs: List[FileDiff] = Field(default_factory=list, description="Unified diff per changed file.")
    unified_diff: str = Field(default="", description="Aggregated unified diff representation.")
    errors: List[str] = Field(default_factory=list, description="Structured error messages encountered.")


class CodeApplicationService:
    """Service that applies DeveloperAgent proposals inside an isolated WorkspaceService workspace."""

    def __init__(
        self,
        task_service: Optional[TaskService] = None,
        developer_agent: Optional[DeveloperAgent] = None,
        workspace_service: Optional[WorkspaceService] = None,
        source_repo_path: Optional[Path] = None,
    ) -> None:
        self.task_service: TaskService = task_service if task_service is not None else TaskService()
        self.developer_agent: DeveloperAgent = (
            developer_agent
            if developer_agent is not None
            else DeveloperAgent(task_service=self.task_service)
        )
        self.workspace_service: WorkspaceService = (
            workspace_service if workspace_service is not None else WorkspaceService()
        )
        self.source_repo_path: Path = (
            Path(source_repo_path).resolve()
            if source_repo_path is not None
            else Path(__file__).resolve().parent.parent
        )

    def apply_proposal(
        self,
        task_id: str,
        file_contents: Optional[Dict[str, str]] = None,
        custom_proposal: Optional[ImplementationProposal] = None,
        target_workspace_id: Optional[str] = None,
    ) -> CodeApplicationResult:
        """Applies proposed code changes to an isolated workspace for a given task.

        Args:
            task_id: Unique task identifier.
            file_contents: Optional map of {relative_path: new_text_content} to apply.
            custom_proposal: Optional pre-computed ImplementationProposal.
            target_workspace_id: Optional existing workspace ID to apply changes into.

        Returns:
            CodeApplicationResult with diffs, changed files, and operation status.

        Raises:
            ValueError: If task_id is invalid or task is not found.
        """
        clean_task_id = self.developer_agent.validate_task_id(task_id)
        task_record = self.task_service.get_task(clean_task_id)
        if task_record is None:
            raise ValueError(f"Task with ID '{clean_task_id}' not found.")

        # Obtain proposal
        if custom_proposal is not None:
            proposal = custom_proposal
        elif task_record.proposal is not None:
            proposal = task_record.proposal
        else:
            proposal = self.developer_agent.generate_proposal(task_record)

        errors: List[str] = []

        if not proposal.files_to_change:
            return CodeApplicationResult(
                task_id=clean_task_id,
                workspace_id="",
                status="failed",
                summary="Proposal contains no files to change.",
                errors=["Proposal contains no files to change."],
            )

        # 1. Establish proposal allowlist and validate all paths
        approved_paths: Dict[str, ProposedFileChange] = {}
        for file_change in proposal.files_to_change:
            try:
                safe_rel_path = validate_relative_path(file_change.path)
                if is_blocked_path(safe_rel_path):
                    errors.append(f"Blocked path detected in proposal: '{safe_rel_path}'.")
                    continue
                approved_paths[safe_rel_path] = file_change
            except ValueError as err:
                errors.append(f"Invalid path in proposal '{file_change.path}': {err}")

        # Check for disallowed paths supplied in file_contents
        if file_contents:
            for supplied_path in file_contents.keys():
                try:
                    norm_supplied = validate_relative_path(supplied_path)
                    if norm_supplied not in approved_paths:
                        errors.append(
                            f"Supplied path '{supplied_path}' is not in the approved proposal allowlist."
                        )
                    if is_blocked_path(norm_supplied):
                        errors.append(f"Supplied path '{supplied_path}' matches security blocklist.")
                except ValueError as err:
                    errors.append(f"Invalid supplied path '{supplied_path}': {err}")

        if errors:
            return CodeApplicationResult(
                task_id=clean_task_id,
                workspace_id="",
                status="failed",
                summary="Validation failed prior to workspace provisioning.",
                errors=errors,
            )

        # 2. Provision or resolve isolated workspace
        workspace_id: str
        if target_workspace_id:
            ws_meta = self.workspace_service.get_workspace(target_workspace_id)
            if ws_meta is None:
                return CodeApplicationResult(
                    task_id=clean_task_id,
                    workspace_id=target_workspace_id,
                    status="failed",
                    summary=f"Specified target workspace '{target_workspace_id}' does not exist.",
                    errors=[f"Target workspace '{target_workspace_id}' not found."],
                )
            workspace_id = target_workspace_id
        elif task_record.workspace_id and self.workspace_service.get_workspace(task_record.workspace_id) is not None:
            workspace_id = task_record.workspace_id
        else:
            ws_info: WorkspaceInfo = self.workspace_service.create_workspace(task_id=clean_task_id)
            workspace_id = ws_info.workspace_id

        original_contents: Dict[str, str] = {}
        changed_files: List[str] = []
        file_diffs: List[FileDiff] = []
        ws_path = self.workspace_service.get_workspace_path(workspace_id)

        # 3. Copy required existing files from source repository or inspect existing in workspace
        for rel_path, change in approved_paths.items():
            source_file = (self.source_repo_path / PurePath(rel_path)).resolve()
            dest_file = (ws_path / PurePath(rel_path)).resolve()

            if change.action == "modify":
                if dest_file.is_file():
                    try:
                        original_contents[rel_path] = dest_file.read_text(encoding="utf-8")
                    except Exception as exc:
                        errors.append(f"Failed to read '{rel_path}' from workspace: {exc}")
                elif source_file.is_file():
                    try:
                        self.workspace_service.copy_file_to_workspace(
                            workspace_id=workspace_id,
                            relative_file_path=rel_path,
                            source_repo_path=self.source_repo_path,
                        )
                        original_contents[rel_path] = source_file.read_text(encoding="utf-8")
                    except Exception as exc:
                        errors.append(f"Failed to copy '{rel_path}' into workspace: {exc}")
                else:
                    errors.append(
                        f"Source file '{rel_path}' marked for modification does not exist in repository."
                    )
                    continue
            else:
                # File is to be created
                if dest_file.is_file():
                    try:
                        original_contents[rel_path] = dest_file.read_text(encoding="utf-8")
                    except Exception as exc:
                        errors.append(f"Failed to read existing file '{rel_path}' from workspace: {exc}")
                else:
                    original_contents[rel_path] = ""

        # If copying prerequisites failed, fail closed
        if errors:
            return CodeApplicationResult(
                task_id=clean_task_id,
                workspace_id=workspace_id,
                status="failed",
                summary="Failed copying existing source files into workspace.",
                errors=errors,
            )

        # 4. Apply validated text changes inside the workspace
        for rel_path, change in approved_paths.items():
            # Determine content to write
            if file_contents and rel_path in file_contents:
                content_to_apply = file_contents[rel_path]
            else:
                # Deterministic scaffolding if no explicit text was provided
                orig = original_contents.get(rel_path, "")
                if change.action == "create":
                    content_to_apply = (
                        f'"""Implementation for: {task_record.task}"""\n\n'
                        f"# Proposed action: {change.description}\n"
                    )
                else:
                    content_to_apply = orig + f"\n# [Modified] Applied task requirements for: {task_record.task}\n"

            try:
                self.workspace_service.write_file_to_workspace(
                    workspace_id=workspace_id,
                    relative_file_path=rel_path,
                    content=content_to_apply,
                )
                changed_files.append(rel_path)

                # 5. Generate unified diff
                orig_text = original_contents.get(rel_path, "")
                change_type = "added" if change.action == "create" else "modified"
                diff_text = generate_unified_diff(
                    original_text=orig_text,
                    modified_text=content_to_apply,
                    relative_path=rel_path,
                    change_type=change_type,
                )

                file_diffs.append(
                    FileDiff(
                        path=rel_path,
                        change_type=change_type,
                        diff=diff_text,
                    )
                )
            except Exception as exc:
                errors.append(f"Failed applying changes to '{rel_path}': {exc}")

        # Determine final status
        if errors:
            status = "partial_failure" if changed_files else "failed"
            summary = f"Completed with {len(errors)} error(s)."
        else:
            status = "applied"
            summary = (
                f"Successfully applied {len(changed_files)} file change(s) inside "
                f"isolated workspace '{workspace_id}'."
            )

        aggregated_diff = "\n".join(fd.diff for fd in file_diffs if fd.diff)

        return CodeApplicationResult(
            task_id=clean_task_id,
            workspace_id=workspace_id,
            status=status,
            summary=summary,
            changed_files=changed_files,
            diffs=file_diffs,
            unified_diff=aggregated_diff,
            errors=errors,
        )
