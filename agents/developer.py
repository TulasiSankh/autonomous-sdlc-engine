"""Developer Agent module.

Provides deterministic implementation proposals from persisted SDLC task plans
without modifying files or executing shell commands.
"""

import difflib
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Dict, List, Optional
from pydantic import BaseModel, Field

from agents.planner import Plan

if TYPE_CHECKING:
    from services.task_service import TaskRecord, TaskService, VerificationDiagnostics


class ProposedFileChange(BaseModel):
    """Structured description of a proposed file modification or creation."""

    path: str = Field(..., description="Target file path relative to workspace root.")
    action: str = Field(..., description="Proposed action type: 'create' or 'modify'.")
    description: str = Field(..., description="Purpose and scope of the proposed change.")


class FileDiff(BaseModel):
    """Structured representation of a unified diff for a single file."""

    path: str = Field(..., description="Target file path relative to workspace root.")
    change_type: str = Field(..., description="Nature of change: 'added', 'modified', or 'deleted'.")
    diff: str = Field(..., description="Unified diff formatted string.")


def generate_unified_diff(
    original_text: str,
    modified_text: str,
    relative_path: str,
    change_type: str = "modified",
) -> str:
    """Generates a standard unified diff between original and modified file contents.

    Args:
        original_text: Original file text.
        modified_text: Modified file text.
        relative_path: POSIX relative path of the file.
        change_type: Type of change ('added', 'modified', 'deleted').

    Returns:
        Unified diff string with headers and chunks.
    """
    orig_lines = original_text.splitlines(keepends=True)
    mod_lines = modified_text.splitlines(keepends=True)

    if change_type == "added":
        from_file = "/dev/null"
        to_file = f"b/{relative_path}"
    elif change_type == "deleted":
        from_file = f"a/{relative_path}"
        to_file = "/dev/null"
    else:
        from_file = f"a/{relative_path}"
        to_file = f"b/{relative_path}"

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=from_file,
            tofile=to_file,
        )
    )
    return "".join(diff_lines)


class ImplementationProposal(BaseModel):
    """Structured proposal outlining intended code changes prior to execution."""

    task_id: str = Field(..., description="Unique task identifier.")
    task: str = Field(..., description="Original task description.")
    status: str = Field(default="proposed", description="Proposal lifecycle status.")
    summary: str = Field(..., description="Summary of the proposed implementation approach.")
    files_to_change: List[ProposedFileChange] = Field(
        default_factory=list, description="List of proposed file modifications or creations."
    )
    execution_steps: List[str] = Field(
        default_factory=list, description="Step-by-step implementation procedure derived from the plan."
    )
    verification_commands: List[str] = Field(
        default_factory=list, description="Commands to run after implementation to verify correctness."
    )
    dry_run: bool = Field(
        default=True, description="Indicates that no files have been created or modified on disk."
    )
    diffs: List[FileDiff] = Field(
        default_factory=list, description="Candidate unified diffs for proposed changes."
    )


class RevisionProposal(BaseModel):
    """Structured proposal outlining targeted corrective changes based on verification diagnostics."""

    task_id: str = Field(..., description="Unique task identifier.")
    explanation: str = Field(..., description="Concise explanation of the proposed corrective action.")
    suspected_cause: str = Field(..., description="Suspected cause deduced from verification diagnostics.")
    proposed_changes: List[ProposedFileChange] = Field(
        default_factory=list, description="Targeted proposed file modifications or creations."
    )
    suggested_file_contents: Dict[str, str] = Field(
        default_factory=dict, description="Concrete patch contents for proposed files."
    )
    test_strategy: str = Field(..., description="Targeted testing strategy to verify the corrective patch.")
    can_revise: bool = Field(default=True, description="Whether actionable revision is possible from diagnostics.")


def validate_relative_path(path: str) -> str:
    """Validates that a path is a safe relative path within workspace boundaries.

    Rejects absolute paths, parent-directory traversals (..), Windows drive letters,
    and empty or whitespace-only inputs.

    Args:
        path: File path string to validate.

    Returns:
        The normalized POSIX relative path string.

    Raises:
        ValueError: If the path is absolute, attempts directory traversal, or is invalid.
    """
    if not isinstance(path, str):
        raise ValueError("Path must be a string.")

    cleaned = path.strip()
    if not cleaned:
        raise ValueError("Path cannot be empty or whitespace only.")

    # Reject absolute root indicators and Windows drive letters
    if cleaned.startswith(("/", "\\")) or (len(cleaned) > 1 and cleaned[1] == ":"):
        raise ValueError(f"Absolute paths are not permitted: '{cleaned}'.")

    pure = PurePath(cleaned)
    if pure.is_absolute():
        raise ValueError(f"Absolute paths are not permitted: '{cleaned}'.")

    # Reject parent directory traversal
    if ".." in pure.parts:
        raise ValueError(f"Parent directory traversal is not permitted: '{cleaned}'.")

    # Reject null characters or suspicious stream operators
    if "\0" in cleaned:
        raise ValueError("Path contains invalid characters.")

    return pure.as_posix()


class DeveloperAgent:
    """Agent responsible for inspecting task plans and formulating implementation proposals."""

    def __init__(
        self,
        task_service: Optional["TaskService"] = None,
        workspace_path: Optional[Path] = None,
    ) -> None:
        if task_service is not None:
            self.task_service = task_service
        else:
            from services.task_service import TaskService

            self.task_service = TaskService()
        self.workspace_path: Path = (workspace_path if workspace_path is not None else Path.cwd()).resolve()

    def validate_task_id(self, task_id: str) -> str:
        """Validates that a task ID is a non-empty string.

        Args:
            task_id: Task identifier string.

        Returns:
            Sanitized task ID.

        Raises:
            ValueError: If task_id is empty, whitespace-only, or not a string.
        """
        if not isinstance(task_id, str):
            raise ValueError("Task ID must be a string.")

        cleaned = task_id.strip()
        if not cleaned:
            raise ValueError("Task ID cannot be empty or whitespace only.")

        return cleaned

    def propose(self, task_id: str) -> ImplementationProposal:
        """Retrieves a persisted task and generates an implementation proposal.

        Args:
            task_id: Unique task identifier.

        Returns:
            An ImplementationProposal with proposed file actions, steps, and test commands.

        Raises:
            ValueError: If task_id is invalid, task is not found, or plan is invalid.
        """
        clean_id = self.validate_task_id(task_id)
        task_record = self.task_service.get_task(clean_id)
        if task_record is None:
            raise ValueError(f"Task with ID '{clean_id}' not found.")

        return self.generate_proposal(task_record)

    def generate_proposal(self, task_record: "TaskRecord") -> ImplementationProposal:
        """Formulates an implementation proposal from the task record and plan.

        Args:
            task_record: Persisted TaskRecord containing the Plan.

        Returns:
            Structured ImplementationProposal.

        Raises:
            ValueError: If plan data is missing or corrupted.
        """
        plan: Plan = task_record.plan
        if plan is None or not isinstance(plan, Plan):
            raise ValueError(f"Task '{task_record.id}' has corrupted or missing plan data.")

        action_task_types = {
            "browser_action",
            "filesystem_action",
            "application_action",
            "command_action",
            "composite_action",
            "computer_task",
            "unsupported",
        }
        if task_record.task_type in action_task_types or getattr(plan, "task_type", None) in action_task_types:
            raise ValueError(
                f"Task '{task_record.id}' is an action task ({task_record.task_type}), not a code change task. "
                "Action tasks execute directly via registered tools and cannot generate software code proposals."
            )

        if not plan.steps:
            raise ValueError(f"Task '{task_record.id}' plan contains no execution steps.")

        proposed_files: List[ProposedFileChange] = []

        # Derive proposed file actions safely from candidate files/directories in plan
        for candidate in plan.files_to_inspect:
            candidate_cleaned = candidate.rstrip("/\\")
            if not candidate_cleaned:
                continue

            # If it's a directory, propose a target implementation module inside it
            if candidate.endswith(("/", "\\")) or (self.workspace_path / candidate_cleaned).is_dir():
                target_filename = self._infer_module_name(task_record.task)
                target_rel_path = f"{candidate_cleaned}/{target_filename}.py"
            else:
                target_rel_path = candidate_cleaned

            # Validate safety of the proposed path
            safe_path = validate_relative_path(target_rel_path)

            full_path = self.workspace_path / safe_path
            action = "modify" if full_path.exists() else "create"
            description = (
                f"Update existing module '{safe_path}' for task requirements."
                if action == "modify"
                else f"Create module '{safe_path}' to implement task requirements."
            )

            proposed_files.append(
                ProposedFileChange(
                    path=safe_path,
                    action=action,
                    description=description,
                )
            )

        # Fallback to an agent module if no candidates were resolvable
        if not proposed_files:
            default_path = validate_relative_path(f"agents/{self._infer_module_name(task_record.task)}.py")
            proposed_files.append(
                ProposedFileChange(
                    path=default_path,
                    action="create",
                    description=f"Create implementation for task '{task_record.task}'.",
                )
            )

        # Map steps into prospective proposed actions
        execution_steps: List[str] = [
            f"[Proposed] {step}" for step in plan.steps
        ]

        # Use the planned test commands as verification commands
        verification_commands: List[str] = list(plan.tests_to_run)

        # Produce candidate unified diffs for all proposed file changes without modifying files on disk
        diffs: List[FileDiff] = []
        for file_change in proposed_files:
            rel_path = file_change.path
            full_path = self.workspace_path / PurePath(rel_path)

            if file_change.action == "modify" and full_path.is_file():
                try:
                    orig_content = full_path.read_text(encoding="utf-8")
                except Exception:
                    orig_content = ""
                candidate_content = (
                    orig_content
                    + f"\n# [Proposed] Implementation for: {task_record.task}\n"
                    f"# Scope: {file_change.description}\n"
                )
                diff_text = generate_unified_diff(
                    orig_content, candidate_content, rel_path, change_type="modified"
                )
                diffs.append(
                    FileDiff(path=rel_path, change_type="modified", diff=diff_text)
                )
            else:
                candidate_content = (
                    f'"""Implementation for: {task_record.task}"""\n\n'
                    f"# Proposed action: {file_change.description}\n"
                )
                diff_text = generate_unified_diff(
                    "", candidate_content, rel_path, change_type="added"
                )
                diffs.append(
                    FileDiff(path=rel_path, change_type="added", diff=diff_text)
                )

        summary = (
            f"Implementation proposal for task '{task_record.task}'. "
            f"Proposes {len(proposed_files)} file change(s) across {len(execution_steps)} step(s). "
            f"No files have been modified (dry_run=True)."
        )

        return ImplementationProposal(
            task_id=task_record.id,
            task=task_record.task,
            status="proposed",
            summary=summary,
            files_to_change=proposed_files,
            execution_steps=execution_steps,
            verification_commands=verification_commands,
            dry_run=True,
            diffs=diffs,
        )

    @staticmethod
    def _infer_module_name(task_desc: str) -> str:
        """Generates a clean snake_case filename segment from a task description."""
        words = [w.lower() for w in task_desc.split() if w.isalnum()]
        filtered = [w for w in words if w not in {"a", "an", "the", "for", "in", "to", "of", "and", "or"}]
        return "_".join(filtered[:4]) if filtered else "task_implementation"

    def revise_from_diagnostics(
        self,
        task_record: "TaskRecord",
        diagnostics: "VerificationDiagnostics",
        suggested_patches: Optional[Dict[str, str]] = None,
    ) -> RevisionProposal:
        """Formulates a targeted corrective patch proposal from verification diagnostics.

        Args:
            task_record: Persisted TaskRecord.
            diagnostics: Structured diagnostic data from the latest verification attempt.
            suggested_patches: Optional explicit mapping of {relative_path: patch_content}.

        Returns:
            RevisionProposal containing proposed changes, explanations, and test strategy.

        Raises:
            ValueError: If proposed patch paths fail security path validation.
        """
        # 1. Do not treat blocked verification as code defect
        if diagnostics.status == "blocked":
            return RevisionProposal(
                task_id=task_record.id,
                explanation="Verification was blocked by security policy or lack of isolation. Cannot deduce code defects from a blocked run.",
                suspected_cause="Security policy refusal or missing container sandbox.",
                proposed_changes=[],
                suggested_file_contents={},
                test_strategy="Enable an approved execution environment before retrying verification.",
                can_revise=False,
            )

        # 2. If already passed, no revision needed
        if diagnostics.status == "passed" and diagnostics.exit_code == 0:
            return RevisionProposal(
                task_id=task_record.id,
                explanation="Tests have already passed successfully. No corrective revision is required.",
                suspected_cause="None (verified).",
                proposed_changes=[],
                suggested_file_contents={},
                test_strategy="Maintain existing passing test suite.",
                can_revise=False,
            )

        # 3. Check for empty or insufficient diagnostics
        combined_diag = (
            diagnostics.stderr_excerpt + " " + diagnostics.stdout_excerpt + " " + (diagnostics.runner_error or "")
        ).strip()
        if not combined_diag and not diagnostics.timed_out and diagnostics.exit_code is None:
            return RevisionProposal(
                task_id=task_record.id,
                explanation="Insufficient diagnostics: contains no error output or diagnostic messages. Cannot formulate targeted fix.",
                suspected_cause="Insufficient diagnostic data.",
                proposed_changes=[],
                suggested_file_contents={},
                test_strategy="Re-run verification with verbose test reporting.",
                can_revise=False,
            )

        # 4. Formulate targeted proposed changes with strict path validation
        target_files: List[ProposedFileChange] = []
        suggested_contents: Dict[str, str] = {}

        if suggested_patches:
            for path_key, patch_text in suggested_patches.items():
                safe_path = validate_relative_path(path_key)
                target_files.append(
                    ProposedFileChange(
                        path=safe_path,
                        action="modify",
                        description=f"Apply corrective patch to '{safe_path}'.",
                    )
                )
                suggested_contents[safe_path] = patch_text
        elif task_record.proposal and task_record.proposal.files_to_change:
            for change in task_record.proposal.files_to_change:
                safe_path = validate_relative_path(change.path)
                target_files.append(
                    ProposedFileChange(
                        path=safe_path,
                        action="modify",
                        description=f"Apply targeted correction to '{safe_path}' based on diagnostics.",
                    )
                )
                suggested_contents[safe_path] = (
                    f"# Corrective patch addressing diagnostics for {task_record.task}\n"
                )
        else:
            fallback_path = validate_relative_path(f"agents/{self._infer_module_name(task_record.task)}.py")
            target_files.append(
                ProposedFileChange(
                    path=fallback_path,
                    action="modify",
                    description=f"Apply targeted correction to '{fallback_path}'.",
                )
            )
            suggested_contents[fallback_path] = f"# Corrective patch for {task_record.task}\n"

        # 5. Formulate truthful explanation and test strategy
        if diagnostics.timed_out:
            suspected_cause = f"Execution timed out during verification profile '{diagnostics.profile}'."
            explanation = (
                f"Proposed timeout mitigation patch for task '{task_record.task}'. "
                f"Fix has NOT been verified yet."
            )
        else:
            error_snippet = (
                diagnostics.stderr_excerpt[:150]
                or diagnostics.runner_error
                or f"Exit code {diagnostics.exit_code}"
            )
            suspected_cause = f"Test failure detected in {diagnostics.profile}: {error_snippet.strip()}."
            explanation = (
                f"Proposed corrective patch for task '{task_record.task}' targeting suspected failures. "
                f"Fix has NOT been verified yet."
            )

        test_strategy = f"Execute {diagnostics.profile} verification profile to evaluate corrective patch."

        return RevisionProposal(
            task_id=task_record.id,
            explanation=explanation,
            suspected_cause=suspected_cause,
            proposed_changes=target_files,
            suggested_file_contents=suggested_contents,
            test_strategy=test_strategy,
            can_revise=True,
        )
